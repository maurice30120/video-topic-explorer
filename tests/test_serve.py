"""Serveur local minimal : parcours lancés depuis leur URL, run.json écrit.

Seam testé (le plus haut possible) : l'interface HTTP du serveur stdlib
(http.server), interrogée avec http.client contre un serveur éphémère
lancé sur le port 0 — sans Selenium, sans navigateur, sans réseau externe.
La logique serveur (dispatch départ/rayon, run.json écrit par parcours lancé,
chemins d'erreur) est testée automatiquement ; la page d'accueil — le
panneau du parcours sensible à la rétention — est testée à part
(test_panneau.py) ; les cosmétiques de la page
restent une vérification manuelle au sens des Testing Decisions du spec #2.
"""
import http.client
import json
import threading
from pathlib import Path

import pytest

from vte import serve


def start_server(corpus, runs_dir):
    httpd = serve.make_server(corpus, Path(runs_dir), host="127.0.0.1", port=0)
    httpd.runs_dir = runs_dir
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def get(httpd, path):
    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


@pytest.fixture
def server(rich_corpus, tmp_path):
    httpd = start_server(rich_corpus, tmp_path / "runs")
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def chain_server(chain_corpus, tmp_path):
    httpd = start_server(chain_corpus, tmp_path / "runs")
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def test_parcours_from_page_renders_result_and_writes_run_json(server, tmp_path):
    """AC #7 : un parcours lancé depuis la page est affiché ET écrit son run.json."""
    status, body = get(server, "/parcours?start=v1&rayon=3")
    doc = body.decode("utf-8")
    assert status == 200
    assert "<h1>Parcours depuis v1</h1>" in doc
    assert "rayon : 3 hop(s) de sujets" in doc
    assert "mode" not in doc
    # chaque vidéo du parcours est listée avec son url
    assert "https://www.youtube.com/watch?v=xv1" in doc
    # run.json écrit pour ce parcours, avec le contenu auditable du moteur
    run_path = tmp_path / "runs" / "v1-r3.json"
    assert run_path.exists()
    run = json.loads(run_path.read_text(encoding="utf-8"))
    assert run["start"] == "v1"
    assert run["radius"] == 3
    assert "mode" not in run
    assert run["start_kind"] == "video"
    assert run["videos"][0] == "v1"
    assert len(run["videos"]) == len(run["transitions"]) + 1


def test_each_parcours_launched_from_page_writes_its_own_run_json(server, tmp_path):
    """AC #7 : chaque parcours lancé depuis la page écrit un run.json (départs/modes variés)."""
    for start, rayon in [("v1", 1), ("Roslyn", 3), ("v5", 3)]:
        status, body = get(server, f"/parcours?start={start}&rayon={rayon}")
        assert status == 200, (start, rayon, body[:200])
        run = json.loads((tmp_path / "runs" / f"{start}-r{rayon}.json").read_text(encoding="utf-8"))
        assert run["start"] == start and run["radius"] == rayon


def test_parcours_page_links_to_graph_on_demand(server):
    """AC #7 : le graphe surligné est affichable à la demande, sans encombrer l'écran principal."""
    status, body = get(server, "/parcours?start=v1&rayon=1")
    doc = body.decode("utf-8")
    assert status == 200
    # pas d'image embarquée dans la page principale : le graphe est à la demande
    assert "<img" not in doc
    # lien vers le graphe surligné pour ce parcours
    # le href est échappé en HTML (&amp;), URL de requête valide pour le navigateur
    assert 'href="/graphe.png?start=v1&amp;rayon=1"' in doc


def test_partial_parcours_served_on_page_with_reason(chain_server, tmp_path):
    """AC #7 : parcours partiel affiché sur la page avec son motif, pas une erreur."""
    # "a" au rayon 1 ne peut pas atteindre 5 vidéos : parcours partiel.
    status, body = get(chain_server, "/parcours?start=a&rayon=1")
    doc = body.decode("utf-8")
    assert status == 200
    assert "<h1>Parcours depuis a</h1>" in doc
    run = json.loads((tmp_path / "runs" / "a-r1.json").read_text(encoding="utf-8"))
    assert run["complete"] is False
    assert run["reason"]
    # le motif exact du run.json apparaît tel quel sur la page
    assert run["reason"] in doc


def test_isolated_start_shown_on_page_with_reason_and_graph_suggestion(server):
    """AC #7 : départ isolé → message explicite sur la page + suggestion d'afficher le graphe."""
    # "isolated" ne porte qu'un sujet mort : aucun parcours possible.
    status, body = get(server, "/parcours?start=isolated&rayon=3")
    doc = body.decode("utf-8")
    assert status == 400
    assert "point de départ isolé" in doc
    # le motif complet du moteur apparaît tel quel, avec la suggestion
    assert "affichez le graphe du corpus" in doc
    # la suggestion est cliquable : lien vers le graphe du corpus
    assert 'href="/graphe.png"' in doc
    # aucun run.json n'est écrit pour un départ isolé : il n'y a pas de parcours
    assert not (Path(server.runs_dir) / "isolated-r3.json").exists()


def test_graph_served_on_demand_with_run_highlighted(server):
    """AC #7 : le graphe statique est servi à la demande, avec le parcours en query."""
    status, body = get(server, "/graphe.png?start=v1&rayon=1")
    assert status == 200
    assert body.startswith(b"\x89PNG")
    assert len(body) > 1000


def test_graph_served_without_run_for_isolated_start_suggestion(server):
    """AC #7 : depuis la page d'erreur, le graphe du corpus complet est affichable."""
    status, body = get(server, "/graphe.png")
    assert status == 200
    assert body.startswith(b"\x89PNG")
    assert len(body) > 1000


def test_rayon_invalide_erreur_explicite(server):
    """Un rayon illisible est une erreur explicite — le parcours complet prend
    un rayon entier (ticket #35 : plus aucun mode)."""
    status, body = get(server, "/parcours?start=v1&rayon=bogus")
    doc = body.decode("utf-8")
    assert status == 400
    assert "rayon invalide" in doc


def test_parcours_sans_rayon_erreur_explicite(server):
    """Sans rayon, erreur explicite du moteur — jamais de repli silencieux."""
    status, body = get(server, "/parcours?start=v1")
    doc = body.decode("utf-8")
    assert status == 400
    assert "rayon requis" in doc


def test_unknown_start_shown_as_explicit_error(server):
    status, body = get(server, "/parcours?start=nimporte-quoi&rayon=1")
    doc = body.decode("utf-8")
    assert status == 400
    assert "sujet inconnu" in doc


def test_cli_serve_subcommand_wired():
    """La page se lance en local : `python -m vte.cli serve <corpus>`."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "vte.cli", "serve", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--runs-dir" in result.stdout
    assert "--port" in result.stdout
