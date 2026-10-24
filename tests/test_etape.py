"""Étape suivante orientée par la vidéo regardée : moteur (next_step) et serveur (/etape, panneau).

Seam testé : l'état du visionnage est la vidéo sur laquelle le lecteur reste
(rétention applicative, GLOSSARY). Le moteur expose l'étape suivante comme
une fonction pure (corpus, vidéo regardée, rayon, déjà-vues) ; le serveur
sert en JSON le pas orienté par la durée de visionnage de la carte quittée
(rayon dérivé côté serveur, ticket #35 : plus aucun paramètre de mode),
quand le lecteur atteint le bas de la colonne. Testé au niveau HTTP
(http.client) comme test_serve.py.
"""
import http.client
import json
import threading
from pathlib import Path

import pytest

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
    run = graph_engine.parcours(rich_corpus, "v1", 3)
    step = graph_engine.next_step(rich_corpus, "v1", radius=3)
    assert step is not None
    assert step["from"] == "v1"
    assert step["to"] == run.videos[1]
    assert step["topic_path"] == run.transitions[0]["topic_path"]


def test_next_step_change_quand_la_cible_naturelle_est_deja_vue(chain_corpus):
    """Le panneau exclut les cartes déjà montrées : l'étape suivante se réoriente,
    mais reste orientée par la vidéo regardée (départ du chemin dans ses sujets)."""
    by_id = {v["id"]: v for v in chain_corpus["videos"]}
    natural = graph_engine.next_step(chain_corpus, "a", radius=3)
    assert natural["to"] == "b"
    reoriented = graph_engine.next_step(chain_corpus, "a", radius=3, exclude={"b"})
    assert reoriented is not None
    assert reoriented["to"] != "b"
    assert reoriented["topic_path"][0] in topics_of(by_id["a"])


def test_next_step_aucune_candidate_restante_renvoie_none(chain_corpus):
    """Tout est déjà vu : None, pas une erreur — le panneau s'arrête honnêtement."""
    step = graph_engine.next_step(chain_corpus, "a", radius=3, exclude={"b", "c", "d"})
    assert step is None


def test_next_step_depart_inconnu_leve_erreur_explicite(chain_corpus):
    with pytest.raises(graph_engine.PathfindingError):
        graph_engine.next_step(chain_corpus, "inconnu", radius=3)


def test_next_step_exclut_toujours_la_video_regardee(chain_corpus):
    """La vidéo regardée ne peut jamais être suggérée comme suivante d'elle-même."""
    step = graph_engine.next_step(chain_corpus, "a", radius=3, exclude=set())
    assert step["to"] != "a"


# --- Serveur : /etape, la transition orientée servie en JSON au panneau ---


def test_etape_sert_la_transition_orientee_en_json(server):
    status, body = get(server, "/etape?from=v1&duree=4000")
    assert status == 200
    data = json.loads(body)
    run = graph_engine.parcours(server.corpus, "v1", 3)
    assert data["from"] == "v1"
    assert data["to"] == run.videos[1]
    assert data["video"]["id"] == run.videos[1]
    assert data["video"]["title"]
    assert data["video"]["url"].startswith("https://")
    assert data["topic_path"]
    assert data["explanation"] == " → ".join(data["topic_path"])


def test_etape_respecte_les_exclusions(server):
    """Cartes déjà montrées exclues : la réponse se réoriente, sans répéter l'exclue."""
    run = graph_engine.parcours(server.corpus, "v1", 3)
    natural = run.videos[1]
    status, body = get(server, f"/etape?from=v1&duree=4000&exclu={natural}")
    assert status == 200
    data = json.loads(body)
    assert data["to"] != natural


def test_etape_depart_inconnu_erreur_explicite(server):
    status, body = get(server, "/etape?from=nimporte-quoi&duree=4000")
    assert status == 400
    data = json.loads(body)
    assert "inconnu" in data["erreur"]


def test_etape_plus_aucune_candidate(server):
    exclus = "&exclu=".join(f"v{n}" for n in range(2, 9))
    status, body = get(server, f"/etape?from=v1&duree=4000&exclu={exclus}")
    assert status == 404
    data = json.loads(body)
    assert "erreur" in data


def test_etape_sans_duree_erreur_explicite(server):
    """Ticket #35 : sans durée, requête invalide — aucun mode ne donne le rayon,
    jamais de repli silencieux."""
    status, body = get(server, "/etape?from=v1")
    assert status == 400
    data = json.loads(body)
    assert "durée requise" in data["erreur"]
