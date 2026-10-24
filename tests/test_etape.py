"""Étape suivante orientée par la vidéo regardée : moteur (next_step) et serveur (/etape, panneau).

Seam testé : l'état du visionnage est la vidéo sur laquelle le lecteur reste
(rétention applicative, GLOSSARY). Le moteur expose l'étape suivante comme
une fonction pure (corpus, vidéo regardée, mode, déjà-vues) ; le serveur la
sert en JSON pour le panneau, qui l'appelle quand le lecteur atteint le bas
de la colonne. Testé au niveau HTTP (http.client) comme test_serve.py.
"""
import http.client
import json
import threading
from pathlib import Path

import pytest

from conftest import load_corpus_from_videos, make_video

from vte import graph_engine, serve
from vte.corpus import topics_of


def start_server(corpus, runs_dir):
    httpd = serve.make_server(corpus, Path(runs_dir), host="127.0.0.1", port=0)
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
    httpd.corpus = rich_corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def chain_server(chain_corpus, tmp_path):
    httpd = start_server(chain_corpus, tmp_path / "runs")
    yield httpd
    httpd.shutdown()
    httpd.server_close()


# --- Moteur : next_step, la pure fonction « la vidéo regardée oriente la suivante » ---


def test_next_step_oriente_depuis_la_video_regardee(rich_corpus):
    """L'étape suivante est exactement la première transition du parcours depuis cette vidéo."""
    run = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    step = graph_engine.next_step(rich_corpus, "v1", "decouvrir")
    assert step is not None
    assert step["from"] == "v1"
    assert step["to"] == run.videos[1]
    assert step["topic_path"] == run.transitions[0]["topic_path"]


def test_next_step_change_quand_la_cible_naturelle_est_deja_vue(chain_corpus):
    """Le panneau exclut les cartes déjà montrées : l'étape suivante se réoriente,
    mais reste orientée par la vidéo regardée (départ du chemin dans ses sujets)."""
    by_id = {v["id"]: v for v in chain_corpus["videos"]}
    natural = graph_engine.next_step(chain_corpus, "a", "decouvrir")
    assert natural["to"] == "c"  # Découvrir : c apporte deux sujets nouveaux, b un seul
    reoriented = graph_engine.next_step(chain_corpus, "a", "decouvrir", exclude={"c"})
    assert reoriented is not None
    assert reoriented["to"] != "c"
    assert reoriented["topic_path"][0] in topics_of(by_id["a"])


def test_next_step_aucune_candidate_restante_renvoie_none(chain_corpus):
    """Tout est déjà vu : None, pas une erreur — le panneau s'arrête honnêtement."""
    step = graph_engine.next_step(chain_corpus, "a", "decouvrir", exclude={"b", "c", "d"})
    assert step is None


def test_next_step_depart_inconnu_leve_erreur_explicite(chain_corpus):
    with pytest.raises(graph_engine.PathfindingError):
        graph_engine.next_step(chain_corpus, "inconnu", "decouvrir")


def test_next_step_decouvrir_tie_sujets_nouveaux_puis_id_chemin_ne_compte_pas():
    """Découvrir : à égalité de sujets nouveaux et de sujets communs, l'ID
    croissant gagne même si son chemin de sujets est plus long — la longueur
    du chemin ne participe jamais au classement (docs/MVP.md §11).
    """
    corpus = load_corpus_from_videos([
        make_video("cur", ["P"]),
        make_video("conn", ["P", "R"]),
        make_video("z", ["R", "S"]),
        make_video("y", ["S", "T"]),
    ])
    step = graph_engine.next_step(corpus, "cur", "decouvrir", exclude={"conn"})
    assert step["to"] == "y"
    assert step["topic_path"] == ["P", "R", "S"]  # plus long que [P, R] vers z
    reoriented = graph_engine.next_step(corpus, "cur", "decouvrir", exclude={"conn", "y"})
    assert reoriented["to"] == "z"
    assert reoriented["topic_path"] == ["P", "R"]


def test_next_step_exclut_toujours_la_video_regardee(chain_corpus):
    """La vidéo regardée ne peut jamais être suggérée comme suivante d'elle-même."""
    step = graph_engine.next_step(chain_corpus, "a", "decouvrir", exclude=set())
    assert step["to"] != "a"


# --- Serveur : /etape, la transition orientée servie en JSON au panneau ---


def test_etape_sert_la_transition_orientee_en_json(server):
    status, body = get(server, "/etape?from=v1&mode=decouvrir")
    assert status == 200
    data = json.loads(body)
    run = graph_engine.parcours(server.corpus, "v1", "decouvrir")
    assert data["from"] == "v1"
    assert data["to"] == run.videos[1]
    assert data["video"]["id"] == run.videos[1]
    assert data["video"]["title"]
    assert data["video"]["url"].startswith("https://")
    assert data["topic_path"]
    assert data["explanation"] == " → ".join(data["topic_path"])


def test_etape_respecte_les_exclusions(server):
    """Cartes déjà montrées exclues : la réponse se réoriente, sans répéter l'exclue."""
    run = graph_engine.parcours(server.corpus, "v1", "decouvrir")
    natural = run.videos[1]
    status, body = get(server, f"/etape?from=v1&mode=decouvrir&exclu={natural}")
    assert status == 200
    data = json.loads(body)
    assert data["to"] != natural


def test_etape_depart_inconnu_erreur_explicite(server):
    status, body = get(server, "/etape?from=nimporte-quoi&mode=decouvrir")
    assert status == 400
    data = json.loads(body)
    assert "inconnu" in data["erreur"]


def test_etape_plus_aucune_candidate(server):
    exclus = "&exclu=".join(f"v{n}" for n in range(2, 9))
    status, body = get(server, f"/etape?from=v1&mode=decouvrir&exclu={exclus}")
    assert status == 404
    data = json.loads(body)
    assert "erreur" in data


# --- Serveur : le panneau à rétention sur la page d'accueil ---


def test_index_offre_le_panneau_avec_la_chaine_initiale(server):
    """La page d'accueil embarque le panneau scroll : cartes de la chaîne initiale,
    chaque transition porte son chemin de sujets (explicabilité)."""
    status, body = get(server, "/")
    doc = body.decode("utf-8")
    assert status == 200
    assert 'class="panneau"' in doc
    cards = [line for line in doc.splitlines() if "data-video=" in line]
    assert len(cards) >= 5, "le panneau doit embarquer une chaîne initiale de 5 cartes"
    assert "point de départ" in doc
    assert "→" in doc  # chemins de sujets affichés sur les transitions


def test_index_embarque_la_logique_de_retention(server):
    """Rétention applicative : rester sur une carte en fait le pivot ; la suite
    est demandée depuis le pivot, pas depuis l'ordre linéaire des cartes."""
    status, body = get(server, "/")
    doc = body.decode("utf-8")
    assert status == 200
    assert "IntersectionObserver" in doc
    assert "pivot" in doc
    assert "/etape?from=" in doc
    assert "SEUIL_MS" in doc
    # les cartes portent leur vidéo pour l'observateur
    assert 'data-video=' in doc
