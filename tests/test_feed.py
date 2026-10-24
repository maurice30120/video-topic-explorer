"""Tests du feed vertical (build_feed_html / render_feed_html) : seam rendus.

Une page unique, une carte par vidéo avec lecteur intégré, chemin de sujets
en légende, basculeur de mode, carte de fin. Sans Gemini, sans UI, sans réseau.
"""
from vte import graph_engine
from vte.render import build_feed_html


def both_runs(corpus: dict, start: str) -> dict:
    return {
        mode: graph_engine.parcours(corpus, start, mode).to_dict()
        for mode in ("decouvrir", "approfondir")
    }


def test_feed_card_per_video_with_embedded_player(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs)

    assert doc.startswith("<!doctype html>")
    assert 'lang="fr"' in doc
    for video_id in runs["decouvrir"]["videos"]:
        assert f'data-video="{video_id}"' in doc
        assert f"https://www.youtube-nocookie.com/embed/x{video_id}?" in doc
    assert doc.count("<iframe") == len(runs["decouvrir"]["videos"]) + len(
        runs["approfondir"]["videos"]
    )
