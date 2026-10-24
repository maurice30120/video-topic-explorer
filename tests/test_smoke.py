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


# ------------------------------------------------------------------ site local


def make_site(rich_corpus, tmp_path) -> object:
    site = tmp_path / "site"
    render_feed_html(rich_corpus, both_runs(rich_corpus, "v1"), site / "index.html")
    (site / "graphe.png").write_bytes(b"\x89PNG fake")
    return site


def test_site_dir_accepts_generated_site(rich_corpus, tmp_path):
    site = make_site(rich_corpus, tmp_path)

    smoke.check_site_dir(site, first_video="v1")


def test_site_dir_requires_feed_at_root(rich_corpus, tmp_path):
    site = make_site(rich_corpus, tmp_path)
    (site / "index.html").rename(site / "parcours.html")

    with pytest.raises(smoke.SmokeCheckError, match="index.html"):
        smoke.check_site_dir(site, first_video="v1")


def test_site_dir_requires_graph(rich_corpus, tmp_path):
    site = make_site(rich_corpus, tmp_path)
    (site / "graphe.png").unlink()

    with pytest.raises(smoke.SmokeCheckError, match="graphe.png"):
        smoke.check_site_dir(site, first_video="v1")


# ------------------------------------------------------------------ URL publique


def make_fetch(statuses: list[tuple[int, str]]):
    """Faux adaptateur réseau : réponses programmées, une par appel."""
    calls: list[str] = []

    def fetch(url: str) -> tuple[int, str]:
        calls.append(url)
        return statuses[min(len(calls) - 1, len(statuses) - 1)]

    fetch.calls = calls
    return fetch


def test_deployed_url_accepts_propagated_site(rich_corpus):
    doc = feed_doc(rich_corpus)
    ok = (200, doc)
    fetch = make_fetch([(200, "<!doctype html>not yet"), ok, (200, b"png")])

    smoke.check_deployed_url(
        "https://exemple.github.io/site/", first_video="v1", attempts=3, delay=0, fetch=fetch
    )
    assert fetch.calls[0].endswith("/")
    assert fetch.calls[-1] == "https://exemple.github.io/site/graphe.png"


def test_deployed_url_fails_after_all_attempts(rich_corpus):
    fetch = make_fetch([(503, "unavailable")])

    with pytest.raises(smoke.SmokeCheckError, match="503"):
        smoke.check_deployed_url(
            "https://exemple.github.io/site/", first_video="v1", attempts=4, delay=0, fetch=fetch
        )
    # une tentative par appel racine, le graphe n'est vérifié qu'après une racine saine
    assert len(fetch.calls) == 4


def test_deployed_url_rejects_root_serving_list_page(rich_corpus):
    run = graph_engine.parcours(rich_corpus, "v1", "decouvrir").to_dict()
    fetch = make_fetch([(200, build_html(rich_corpus, run))])

    with pytest.raises(smoke.SmokeCheckError, match="feed"):
        smoke.check_deployed_url(
            "https://exemple.github.io/site/", first_video="v1", attempts=1, delay=0, fetch=fetch
        )


# ------------------------------------------------------------------ CLI vte smoke


def test_cli_smoke_local_site_passes(rich_corpus, tmp_path, capsys):
    from vte.cli import main

    site = make_site(rich_corpus, tmp_path)

    assert main(["smoke", "--site", str(site), "--first-video", "v1"]) == 0
    assert "feed" in capsys.readouterr().out


def test_cli_smoke_local_site_fails_with_exit_code(rich_corpus, tmp_path, capsys):
    from vte.cli import main

    site = make_site(rich_corpus, tmp_path)

    assert main(["smoke", "--site", str(site), "--first-video", "v2"]) == 1
    assert "ERREUR" in capsys.readouterr().err
