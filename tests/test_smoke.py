"""Tests du contrôle de fumée du site (vte.smoke) : seam pipeline.

Le contenu généré par la CI doit être vérifiable sans réseau : la racine du
site sert le feed (pas la page liste), la première carte est la première
vidéo du parcours par défaut avec son lecteur intégré et son chemin de
sujets, le graphe statique est présent. Le déploiement lui-même se vérifie
par le contrôle de fumée distant (check_deployed_url, avec fetch injecté).
"""
import pytest

from vte import graph_engine, smoke
from vte.render import build_feed_html, build_html, render_feed_html


def both_runs(corpus: dict, start: str) -> dict:
    return {
        mode: graph_engine.parcours(corpus, start, mode).to_dict()
        for mode in ("decouvrir", "approfondir")
    }


def feed_doc(rich_corpus) -> str:
    return build_feed_html(rich_corpus, both_runs(rich_corpus, "v1"))


def test_content_accepts_generated_feed(rich_corpus):
    smoke.check_site_content(feed_doc(rich_corpus), first_video="v1")


def test_content_rejects_list_page(rich_corpus):
    run = graph_engine.parcours(rich_corpus, "v1", "decouvrir").to_dict()
    list_page = build_html(rich_corpus, run)

    with pytest.raises(smoke.SmokeCheckError, match="feed"):
        smoke.check_site_content(list_page, first_video="v1")


def test_content_rejects_wrong_first_card(rich_corpus):
    with pytest.raises(smoke.SmokeCheckError, match="v2"):
        smoke.check_site_content(feed_doc(rich_corpus), first_video="v2")


def test_content_rejects_feed_without_embedded_player(rich_corpus):
    doc = feed_doc(rich_corpus).replace("iframe", "Cadre")

    with pytest.raises(smoke.SmokeCheckError, match="lecteur"):
        smoke.check_site_content(doc, first_video="v1")
