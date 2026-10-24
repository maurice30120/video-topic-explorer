"""Pas suivant avec durée et sortie par sujet : le panneau pilote la session en HTTP.

Seam testé (point d'accès HTTP, spec #27) : le serveur reçoit la durée de
visionnage de la carte quittée et dérive le rayon côté serveur — durée
≥ SEUIL_MS (aimé) → rayon 1, durée < SEUIL_MS (pas aimé) → rayon 3
(GLOSSARY, « Rétention applicative » ; mapping binaire, aucun bande
intermédiaire). La sortie de branche dirigée par sujet est servie à un
point d'accès distinct (/sortie) : première candidate par la règle de
départage unique du moteur, hors déjà-vues ; sujet mort ou inconnu →
erreur explicite ; aucune candidate restante → 404 fin honnête. Le
contrat JSON reste identique (départ, arrivée, vidéo, chemin de sujets) ;
/etape n'accepte plus aucun mode, seulement la durée (ticket #35). Testé
au niveau HTTP (http.client) comme test_etape.py.
"""
import http.client
import json
import threading
from pathlib import Path

import pytest

from vte import serve
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
    httpd.corpus = chain_corpus
    yield httpd
    httpd.shutdown()
    httpd.server_close()


# --- /etape avec durée : le rayon dérivé côté serveur ---


def test_etape_duree_longue_derive_le_rayon_1(chain_server):
    """Resté ≥ SEUIL_MS sur la carte quittée (aimé) : le pas reste dans le
    voisinage immédiat — rayon 1. Sur la chaîne, « b » et « c » déjà vues :
    rayon 1 n'atteint plus aucune candidate → 404 fin honnête, alors que
    rayon 3 atteint « d »."""
    status, body = get(chain_server, "/etape?from=a&duree=6000&exclu=b&exclu=c")
    assert status == 404
    data = json.loads(body)
    assert "erreur" in data


def test_etape_duree_courte_derive_le_rayon_3(chain_server):
    """Passé vite (< SEUIL_MS, pas aimé) : le pas s'éloigne — rayon 3. Sur la
    chaîne, « d » devient atteignable depuis « a » malgré « b » et « c » vues."""
    status, body = get(chain_server, "/etape?from=a&duree=4000&exclu=b&exclu=c")
    assert status == 200
    data = json.loads(body)
    by_id = {v["id"]: v for v in chain_server.corpus["videos"]}
    assert data["to"] == "d"
    assert data["topic_path"][0] in topics_of(by_id["a"])
    assert data["topic_path"][-1] in topics_of(by_id["d"])


def test_etape_duree_au_seuil_exact_est_un_regard_long(chain_server):
    """Le seuil est inclusif : 5000 ms = aimé → rayon 1 (même fin honnête que
    6000 ms avec « b » et « c » vues)."""
    status, _ = get(chain_server, "/etape?from=a&duree=5000&exclu=b&exclu=c")
    assert status == 404


def test_etape_duree_juste_sous_le_seuil_est_un_passage_rapide(chain_server):
    """4999 ms < SEUIL_MS : rayon 3 (même candidate « d » que 4000 ms)."""
    status, body = get(chain_server, "/etape?from=a&duree=4999&exclu=b&exclu=c")
    assert status == 200
    assert json.loads(body)["to"] == "d"


def test_etape_duree_respecte_le_contrat_json(server):
    """Le contrat JSON reste identique avec la durée : départ, arrivée, vidéo
    (id, url, titre, sujets), chemin de sujets — chaque paire consecutive du
    chemin co-occurre sur une vraie vidéo du corpus."""
    status, body = get(server, "/etape?from=v1&duree=6000")
    assert status == 200
    data = json.loads(body)
    assert data["from"] == "v1"
    assert data["to"]
    video = data["video"]
    assert video["id"] == data["to"]
    assert video["url"].startswith("https://")
    assert video["title"]
    assert video["topics"]
    path = data["topic_path"]
    assert path
    assert data["explanation"] == " → ".join(path)
    by_id = {v["id"]: v for v in server.corpus["videos"]}
    assert path[0] in topics_of(by_id[data["from"]])
    assert path[-1] in topics_of(by_id[data["to"]])
    for first, second in zip(path, path[1:]):
        assert any({first, second} <= topics_of(v) for v in server.corpus["videos"])


def test_etape_duree_respecte_les_exclusions(server):
    """Avec la durée : les cartes déjà montrées restent exclues, sans répéter
    l'exclue."""
    status, body = get(server, "/etape?from=v1&duree=6000&exclu=v2")
    assert status == 200
    data = json.loads(body)
    assert data["to"] != "v2"


def test_etape_sans_duree_n_accepte_aucun_repli(server):
    """Ticket #35 : aucun paramètre ne remplace la durée — sans elle,
    400 explicite, jamais de repli silencieux sur un autre rayon."""
    status, body = get(server, "/etape?from=v1")
    assert status == 400
    data = json.loads(body)
    assert "durée requise" in data["erreur"]


def test_etape_duree_invalide_erreur_explicite(server):
    """Une durée qui n'est pas des millisecondes entières : requête invalide
    → 400, message explicite — jamais de repli silencieux sur un autre rayon."""
    status, body = get(server, "/etape?from=v1&duree=pas-un-nombre")
    assert status == 400
    data = json.loads(body)
    assert "erreur" in data
    assert "durée" in data["erreur"]


def test_etape_depart_inconnu_avec_duree_erreur_explicite(server):
    status, body = get(server, "/etape?from=nimporte-quoi&duree=6000")
    assert status == 400
    data = json.loads(body)
    assert "inconnu" in data["erreur"]


# --- /sortie : la sortie de branche dirigée par sujet, point d'accès distinct ---


def test_sortie_premiere_candidate_200(server):
    """La sortie dirigée vers un sujet canonique réel redémarre le parcours :
    200 avec la première candidate porteuse du sujet, départage par ID
    croissant (règle unique du moteur ; source de vérité indépendante : le
    JSON du corpus). Le contrat JSON reste identique : départ (null — la
    sortie ne juge aucune carte), arrivée, vidéo, chemin de sujets."""
    status, body = get(server, "/sortie?sujet=Roslyn")
    assert status == 200
    data = json.loads(body)
    porteurs = sorted(
        v["id"]
        for v in server.corpus["videos"]
        if "Roslyn" in topics_of(v)
    )
    assert data["from"] is None
    assert data["to"] == porteurs[0]
    assert data["topic_path"] == ["Roslyn"]
    assert data["explanation"] == "sujet de départ : Roslyn"
    video = data["video"]
    assert video["id"] == data["to"]
    assert video["url"].startswith("https://")
    assert video["title"]
    assert "Roslyn" in video["topics"]


def test_sortie_hors_deja_vues(server):
    """La sortie ne répète jamais une carte de la session : les déjà-vues sont
    exclues, la candidate suivante porte le sujet."""
    status, body = get(server, "/sortie?sujet=Roslyn&exclu=v1")
    assert status == 200
    data = json.loads(body)
    assert data["to"] == "v4"
    assert data["topic_path"] == ["Roslyn"]


def test_sortie_sujet_inconnu_erreur_explicite(server):
    """Sortie vers un sujet qui n'existe pas dans le corpus figé : requête
    invalide → 400, message explicite — jamais un repli silencieux."""
    status, body = get(server, "/sortie?sujet=Nimporte")
    assert status == 400
    data = json.loads(body)
    assert "sujet inconnu" in data["erreur"]


def test_sortie_sujet_mort_erreur_explicite(chain_server):
    """Sortie vers un sujet mort (porté par une seule vidéo, GLOSSARY) :
    400 avec message explicite — il ne peut orienter aucun premier pas."""
    status, body = get(chain_server, "/sortie?sujet=SujetUnique")
    assert status == 400
    data = json.loads(body)
    assert "sujet mort" in data["erreur"]


def test_sortie_plus_aucune_candidate_fin_honnete(server):
    """Toutes les porteuses du sujet déjà vues : 404 fin honnête, pas une
    erreur — la fin est explicite."""
    status, body = get(server, "/sortie?sujet=Roslyn&exclu=v1&exclu=v4")
    assert status == 404
    data = json.loads(body)
    assert "erreur" in data
