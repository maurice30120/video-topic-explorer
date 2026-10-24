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


def test_feed_transition_topic_path_in_caption_escaped(tmp_path):
    corpus = {
        "videos": [
            {
                "id": "x",
                "url": "https://www.youtube.com/watch?v=xabc",
                "title": "<script>alert('x')</script> & co",
                "channel": 'Chaîne "A"',
                "description": "d",
                "topics": [
                    {"raw": "T&<>", "canonical": "T&<>", "justification": "j",
                     "provenance": {"source": "fixture", "model": "test", "version": "0"}},
                ],
            },
            {
                "id": "y",
                "url": "https://www.youtube.com/watch?v=yabc",
                "title": "Deux",
                "description": "d",
                "topics": [
                    {"raw": "T&<>", "canonical": "T&<>", "justification": "j",
                     "provenance": {"source": "fixture", "model": "test", "version": "0"}},
                    {"raw": "S", "canonical": "S", "justification": "j",
                     "provenance": {"source": "fixture", "model": "test", "version": "0"}},
                ],
            },
            {
                "id": "z",
                "url": "https://www.youtube.com/watch?v=zabc",
                "title": "Trois",
                "description": "d",
                "topics": [
                    {"raw": "S", "canonical": "S", "justification": "j",
                     "provenance": {"source": "fixture", "model": "test", "version": "0"}},
                ],
            },
        ]
    }
    runs = {
        mode: {
            "start": "x", "start_kind": "video", "mode": mode,
            "radius": 1 if mode == "approfondir" else 3,
            "videos": ["x", "y", "z"],
            "transitions": [
                {"from": "x", "to": "y", "topic_path": ["T&<>", "S"]},
                {"from": "y", "to": "z", "topic_path": ["S"]},
            ],
            "complete": True, "reason": None,
        }
        for mode in ("decouvrir", "approfondir")
    }
    doc = build_feed_html(corpus, runs)

    # chemin de sujets de chaque transition, en légende, échappé
    assert "T&amp;&lt;&gt;" in doc
    assert 'data-sujets="T&amp;&lt;&gt;|S"' in doc
    assert 'data-sujets="S"' in doc
    assert "<script>alert" not in doc
    assert "&lt;script&gt;" in doc
    assert "Chaîne &quot;A&quot;" in doc


def test_feed_first_card_is_departure_without_transition(chain_corpus):
    runs = both_runs(chain_corpus, "a")
    doc = build_feed_html(chain_corpus, runs)
    first, second = runs["decouvrir"]["videos"][:2]
    assert f'<article class="carte depart" data-video="{first}">' in doc
    assert 'class="station depart"' in doc
    # la deuxième carte porte bien le chemin de sa transition
    path = next(t for t in runs["decouvrir"]["transitions"] if t["to"] == second)["topic_path"]
    expected = "|".join(path)
    assert f'data-sujets="{expected}"' in doc
