"""Tests du feed vertical (build_feed_html / render_feed_html) : seam rendus.

Une page unique, une carte par vidéo avec lecteur intégré, chemin de sujets
en légende, basculeur de mode, carte de fin. Sans Gemini, sans UI, sans réseau.
"""
import pytest

from vte import graph_engine
from vte.graph_engine import Mode
from vte.render import MODE_LABELS, MODE_SWITCH_LABELS, build_feed_html, render_feed_html


def both_runs(corpus: dict, start: str) -> dict:
    return {
        mode: graph_engine.parcours(corpus, start, mode).to_dict()
        for mode in (Mode.DECOUVRIR.value, Mode.APPROFONDIR.value)
    }


def test_mode_labels_are_indexed_by_engine_mode_and_reject_unknown():
    # les labels couvrent exactement les membres du moteur, sans liste dupliquée
    assert set(MODE_LABELS) == set(Mode)
    assert set(MODE_SWITCH_LABELS) == set(Mode)
    # indexation par membre ou par valeur
    assert MODE_LABELS[Mode.DECOUVRIR] == "Découvrir"
    assert MODE_LABELS["approfondir"] == "Approfondir"
    assert MODE_SWITCH_LABELS["decouvrir"] == "Basculer en Approfondir"
    # un mode inconnu lève une erreur française explicite, pas un KeyError brut
    with pytest.raises(ValueError, match="mode de parcours inconnu"):
        MODE_LABELS["inconnu"]
    with pytest.raises(ValueError, match="mode de parcours inconnu"):
        MODE_SWITCH_LABELS["inconnu"]


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


def test_feed_requires_runs_for_both_modes(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    del runs["approfondir"]

    with pytest.raises(ValueError, match="approfondir"):
        build_feed_html(rich_corpus, runs)


def test_feed_discreet_graph_link(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs, graph_href="graphe.png")
    assert '<a class="graphe" href="graphe.png">' in doc
    doc_sans_graphe = build_feed_html(rich_corpus, runs)
    assert 'class="graphe"' not in doc_sans_graphe


def test_feed_shell_mobile_first_snap_focus_and_reduced_motion(rich_corpus):
    runs = both_runs(rich_corpus, "v1")
    doc = build_feed_html(rich_corpus, runs, graph_href="graphe.png")

    # mobile : colonne verticale centrée ~480px ; écran large : salle de
    # projection ~1100px, bornée par la hauteur disponible
    assert "480px" in doc
    assert "1100px" in doc
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


def _feed_js(doc: str) -> str:
    return doc.split("<script>")[1].split("</script>")[0]


def test_feed_player_commands_queue_until_on_ready(rich_corpus):
    js = _feed_js(build_feed_html(rich_corpus, both_runs(rich_corpus, "v1")))
    # le lecteur YouTube signale sa mise en place par onReady ; la page écoute
    assert 'addEventListener("message"' in js
    assert "onReady" in js
    # les commandes passent par une file d'attente vidée à la mise en place
    assert "pending" in js
    assert "readyPlayers" in js
    # le canal ne s'ouvre que si la page salue chaque lecteur « listening »
    assert '"listening"' in js


def test_feed_tap_starts_playback_and_unmutes(rich_corpus):
    js = _feed_js(build_feed_html(rich_corpus, both_runs(rich_corpus, "v1")))
    tap = js[js.index('feed.addEventListener("click"'):]
    # activer le son démarre aussi la lecture, pas seulement le démutage
    assert 'post(iframe, "unMute")' in tap
    assert tap.index('"unMute"') < tap.index('"playVideo"')
    # un appui alors que le son est actif le coupe, sans arrêter la lecture
    assert 'post(iframe, "mute")' in tap


def test_render_feed_html_writes_page_and_parent_dirs(rich_corpus, tmp_path):
    runs = both_runs(rich_corpus, "v1")
    out = tmp_path / "site" / "index.html"
    render_feed_html(rich_corpus, runs, out, graph_href="graphe.png")
    assert out.exists()
    doc = out.read_text(encoding="utf-8")
    assert doc.startswith("<!doctype html>")
    assert 'href="graphe.png"' in doc


def _run_cli(*args: str):
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-m", "vte.cli", *args],
        capture_output=True, text=True,
    )


def test_cli_feed_computes_both_modes_and_writes_single_page(tmp_path):
    import json

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "videos": [
            {"id": "v1", "url": "https://e.com/1", "title": "Un",
             "description": "d", "topics": [{"raw": "A", "canonical": "A",
             "justification": "j", "provenance": {"source": "t", "model": "m", "version": "0"}},
             {"raw": "B", "canonical": "B", "justification": "j",
             "provenance": {"source": "t", "model": "m", "version": "0"}}]},
            {"id": "v2", "url": "https://e.com/2", "title": "Deux",
             "description": "d", "topics": [{"raw": "B", "canonical": "B",
             "justification": "j", "provenance": {"source": "t", "model": "m", "version": "0"}}]},
        ]
    }), encoding="utf-8")
    out = tmp_path / "site" / "index.html"
    result = _run_cli("feed", str(corpus_path), "--start", "v1",
                      "--out", str(out), "--graph-href", "graphe.png")
    assert result.returncode == 0, result.stderr
    doc = out.read_text(encoding="utf-8")

    # les parcours des deux modes sont calculés à la génération et embarqués
    assert doc.count("<section") == 2
    assert '<section class="parcours" data-mode="decouvrir">' in doc
    assert '<section class="parcours" data-mode="approfondir" hidden>' in doc
    assert 'href="graphe.png"' in doc
    # la page démarre sur la première vidéo du parcours Découvrir
    assert '<article class="carte depart" data-video="v1">' in doc


def test_cli_feed_without_start_uses_documented_default(tmp_path):
    import json

    from vte import DEFAULT_START

    def video(vid):
        topics = [{"raw": t, "canonical": t, "justification": "j",
                   "provenance": {"source": "t", "model": "m", "version": "0"}}
                  for t in ("A", "B")]
        return {"id": vid, "url": f"https://e.com/{vid}", "title": vid,
                "description": "d", "topics": topics}

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "videos": [video(DEFAULT_START), video("v2")],
    }), encoding="utf-8")
    out = tmp_path / "site" / "index.html"
    result = _run_cli("feed", str(corpus_path), "--out", str(out))
    assert result.returncode == 0, result.stderr
    doc = out.read_text(encoding="utf-8")
    # le départ est la constante documentée, sans --start ressaisi
    assert f'<article class="carte depart" data-video="{DEFAULT_START}">' in doc


def test_cli_feed_rejects_unknown_start(tmp_path):
    import json

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "videos": [
            {"id": "v1", "url": "https://e.com/1", "title": "Un",
             "description": "d", "topics": [{"raw": "A", "canonical": "A",
             "justification": "j", "provenance": {"source": "t", "model": "m", "version": "0"}}]},
        ]
    }), encoding="utf-8")
    out = tmp_path / "site" / "index.html"
    result = _run_cli("feed", str(corpus_path), "--start", "inconnu", "--out", str(out))
    assert result.returncode == 1
    assert not out.exists()
