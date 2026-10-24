"""Le panneau servi : la page de colle mince du parcours sensible à la rétention.

Seam testé (le 4e du spec #27, ticket #34) : la page servie par le serveur
local au point d'accès ``/`` — test de présence/câblage uniquement. La page
embarque la mesure de durée par carte (entre l'activation et le départ de
la carte, observateur d'intersection), la demande du pas suivant au moment
exact où la carte courante est quittée — ``GET /etape?from=…&duree=…&exclu=…``,
le rayon étant dérivé côté serveur —, le sélecteur des sujets canoniques
réels du corpus figé et la commande « changer de branche » qui pilote
``GET /sortie?sujet=…&exclu=…`` (navigation explicite : la sortie ne juge
jamais la carte en cours). Aucune référence aux modes Approfondir/Découvrir
ne reste dans la page servie.

Jamais testé ici (Testing Decisions du spec #27) : l'observateur
d'intersection en conditions réelles, les vraies millisecondes, le
comportement runtime du JS — les tests n'affirment que la présence et le
câblage. Les valeurs attendues (sujets canoniques proposés) viennent du
JSON du corpus figé, jamais du moteur. Testé au niveau HTTP (http.client)
comme test_serve.py.
"""
import http.client
import threading
from pathlib import Path

import pytest

from vte import serve


def start_server(corpus, runs_dir):
    httpd = serve.make_server(corpus, Path(runs_dir), host="127.0.0.1", port=0)
    httpd.corpus = corpus
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


def index_doc(httpd):
    status, body = get(httpd, "/")
    assert status == 200
    return body.decode("utf-8")


def test_la_page_embarque_la_mesure_de_duree_par_carte(server):
    """La durée de visionnage d'une carte se mesure entre son activation et
    son départ (observateur d'intersection, horodatage d'activation) — le
    concept de pivot disparaît : chaque carte oriente, avec sa durée."""
    doc = index_doc(server)
    assert "IntersectionObserver" in doc
    assert "Date.now()" in doc  # horodatage de l'activation puis du départ
    assert "pivot" not in doc
    # les cartes portent leur vidéo pour l'observateur
    assert "data-video=" in doc


def test_le_pas_suivant_est_demande_au_depart_de_la_carte_avec_sa_duree(server):
    """La demande part au moment exact où la carte courante est quittée,
    en passant sa durée de visionnage : le serveur dérive le rayon
    (rétention applicative, mapping binaire — le seuil ne vit plus ici)."""
    doc = index_doc(server)
    assert "/etape?from=" in doc
    assert "&duree=" in doc
    assert "&exclu=" in doc
    # le seuil et le rayon vivent côté serveur, pas dans la page
    assert "SEUIL_MS" not in doc


def test_le_selecteur_offre_les_sujets_canoniques_du_corpus(server):
    """Le sélecteur présente les sujets canoniques réels du corpus figé
    (source de vérité indépendante : le JSON du corpus, jamais le moteur)."""
    doc = index_doc(server)
    assert '<select name="sujet"' in doc
    sujets = sorted(
        {t["canonical"] for v in server.corpus["videos"] for t in v.get("topics", [])}
    )
    for sujet in sujets:
        assert f'<option value="{sujet}">' in doc, sujet


def test_la_commande_changer_de_branche_pilote_la_sortie(server):
    """La commande « changer de branche » est présente et câblée au point
    d'accès de la sortie dirigée ; la sortie ne juge jamais la carte en
    cours : sa requête ne porte aucune durée, ni zap ni like."""
    doc = index_doc(server)
    assert "Changer de branche" in doc
    assert "/sortie?sujet=" in doc
    ligne_sortie = [l for l in doc.splitlines() if "/sortie?sujet=" in l][0]
    assert "duree" not in ligne_sortie


def test_aucune_reference_aux_modes_dans_la_page_servie(server):
    """Les modes Approfondir/Découvrir disparaissent de la page servie :
    ni boutons, ni bascules, ni attribut data-mode, ni paramètre de mode."""
    doc = index_doc(server)
    assert "approfondir" not in doc.lower()
    assert "decouvrir" not in doc.lower()
    assert "data-mode" not in doc
    assert 'name="mode"' not in doc


def test_la_fin_honnete_est_explicite_dans_la_page(server):
    """Quand plus aucune candidate ne reste, le feed s'arrête honnêtement :
    la page embarque le message de fin honnête, pas une erreur."""
    doc = index_doc(server)
    assert "fin honnête" in doc


def test_la_chaine_initiale_est_embarquee_avec_les_chemins_de_sujets(server):
    """La page embarque le panneau scroll : cartes de la chaîne initiale,
    chaque transition porte son chemin de sujets (explicabilité)."""
    doc = index_doc(server)
    assert 'class="panneau"' in doc
    cards = [line for line in doc.splitlines() if "data-video=" in line]
    assert len(cards) >= 5, "le panneau doit embarquer une chaîne initiale de 5 cartes"
    assert "point de départ" in doc
    assert "→" in doc  # chemins de sujets affichés sur les transitions
