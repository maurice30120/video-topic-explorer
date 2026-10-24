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


def test_feed_single_page_with_pinned_mode_toggle(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs)

    # page unique : les deux parcours embarqués dans le même document
    assert doc.count("<section") == 2
    assert '<section class="parcours" data-mode="decouvrir">' in doc
    assert '<section class="parcours" data-mode="approfondir" hidden>' in doc
    for vid in runs["approfondir"]["videos"]:
        assert f'data-video="{vid}"' in doc

    # basculeur épinglé, Découvrir actif au chargement
    assert '<nav class="modes" aria-label="Mode du parcours">' in doc
    assert '<button class="mode" data-mode="decouvrir" aria-pressed="true"' in doc
    assert '<button class="mode" data-mode="approfondir" aria-pressed="false"' in doc
    assert ">Découvrir</button>" in doc
    assert ">Approfondir</button>" in doc


def test_feed_end_card_shows_reason_replay_and_mode_switch(chain_corpus):
    import html as html_module

    runs = both_runs(chain_corpus, "a")
    doc = build_feed_html(chain_corpus, runs)

    assert '<article class="carte fin">' in doc
    assert "Fin du parcours" in doc
    for run in runs.values():
        assert html_module.escape(run["reason"]) in doc
    assert ">Revoir le parcours</button>" in doc
    assert ">Basculer en Approfondir</button>" in doc
    assert ">Basculer en Découvrir</button>" in doc


def test_feed_end_card_complete_run_announces_completion(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs)
    assert runs["decouvrir"]["complete"] is True
    assert "Parcours complet : 5 vidéos." in doc


def test_feed_discreet_graph_link(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs, graph_href="graphe.png")
    assert '<a class="graphe" href="graphe.png">' in doc
    doc_sans_graphe = build_feed_html(rich_corpus, runs)
    assert 'class="graphe"' not in doc_sans_graphe


def test_feed_shell_mobile_first_snap_focus_and_reduced_motion(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs, graph_href="graphe.png")

    # colonne verticale centrée ~480px, identique au mobile
    assert "480px" in doc
    # défilement aimanté carte par carte
    assert "scroll-snap-type: y mandatory" in doc
    assert "scroll-snap-align: start" in doc
    assert "scroll-snap-stop: always" in doc
    # focus clavier visible et mouvement réduit respectés
    assert ":focus-visible" in doc
    assert "prefers-reduced-motion" in doc
    # comportements lecteur : lecture de la carte active (muette), tap = son, pause des autres
    assert "IntersectionObserver" in doc
    assert "playVideo" in doc
    assert "pauseVideo" in doc
    assert "unMute" in doc
    assert "mute" in doc
    # départ direct sur le parcours du mode par défaut
    assert '<body data-mode="decouvrir">' in doc
    # indication du geste son, en français
    assert "Un appui sur la vidéo active le son." in doc
