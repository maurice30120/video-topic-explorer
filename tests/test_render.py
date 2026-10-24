"""Tests du rendu de la page web (render_html) : unitaires + smoke tests.

Unitaires : structure du document, échappement HTML, ancres de sujets,
parcours incomplet avec motif, absence de sujet.
Smoke : pipeline complet corpus -> parcours -> run.json -> page HTML
via la CLI, sans réseau ni LLM.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vte import graph_engine
from vte.render import render_html


def write_run(run: graph_engine.Run) -> dict:
    return run.to_dict()


def test_html_page_contains_title_start_and_rayon(rich_corpus, tmp_path):
    run = graph_engine.parcours(rich_corpus, "v1", 3)
    out = tmp_path / "parcours.html"
    render_html(rich_corpus, write_run(run), out)
    doc = out.read_text(encoding="utf-8")
    assert doc.startswith("<!doctype html>")
    assert "<h1>Parcours depuis v1</h1>" in doc
    assert "<title>Parcours — v1</title>" in doc
    assert f"rayon : {run.radius} hop(s) de sujets" in doc
    assert "mode" not in doc  # ticket #35 : la page ne parle plus en modes


def test_html_lists_run_videos_with_url_and_id(rich_corpus, tmp_path):
    run = graph_engine.parcours(rich_corpus, "v1", 1)
    out = tmp_path / "parcours.html"
    render_html(rich_corpus, write_run(run), out)
    doc = out.read_text(encoding="utf-8")
    assert run.videos[0] == "v1"
    for vid in run.videos:
        assert f"https://www.youtube.com/watch?v=x{vid}" in doc
        assert f"({vid})" in doc
    assert "<ol>" in doc and "</ol>" in doc


def test_html_transitions_show_topic_path_with_anchors(chain_corpus, tmp_path):
    run = graph_engine.parcours(chain_corpus, "a", 3)
    out = tmp_path / "parcours.html"
    render_html(chain_corpus, write_run(run), out)
    doc = out.read_text(encoding="utf-8")
    assert "chemin de sujets :" in doc
    assert 'id="topic-Roslyn"' in doc
    assert "<a href=\"#topic-Roslyn\"" in doc
    for transition in run.transitions:
        chain = " &#8594; ".join(transition["topic_path"])
        assert chain in doc


def test_html_escapes_titles_and_topics(tmp_path):
    corpus = {
        "videos": [
            {
                "id": "x",
                "url": "https://example.com/v",
                "title": "<script>alert('x')</script> & co",
                "description": "d",
                "topics": [
                    {
                        "raw": "T&<>",
                        "canonical": "T&<>",
                        "justification": "j",
                        "provenance": {"source": "fixture", "model": "test", "version": "0"},
                    }
                ],
            }
        ]
    }
    run = {
        "start": "x", "start_kind": "video",
        "radius": 1, "videos": ["x"], "transitions": [],
        "complete": False, "reason": "corpus trop petit",
    }
    out = tmp_path / "page.html"
    render_html(corpus, run, out)
    doc = out.read_text(encoding="utf-8")
    assert "<script>alert" not in doc
    assert "&lt;script&gt;" in doc
    assert 'id="topic-T&amp;&lt;&gt;"' in doc
    assert "corpus trop petit" in doc


def test_html_incomplete_run_shows_reason(rich_corpus, tmp_path):
    corpus = {"videos": [v for v in rich_corpus["videos"] if v["id"] == "v1"]}
    run = graph_engine.parcours(corpus, "v1", 1)
    out = tmp_path / "page.html"
    render_html(corpus, write_run(run), out)
    doc = out.read_text(encoding="utf-8")
    assert run.complete is False
    assert run.reason is not None
    assert f"<p class='reason'>{run.reason}</p>" in doc


def test_html_topic_directory_lists_all_corpus_topics(chain_corpus, tmp_path):
    run = graph_engine.parcours(chain_corpus, "a", 1)
    out = tmp_path / "page.html"
    render_html(chain_corpus, write_run(run), out)
    doc = out.read_text(encoding="utf-8")
    assert 'id="topics"' in doc
    for topic in ("C#", "Roslyn", "Compilateurs", "LLVM", "Rust", "SujetUnique"):
        assert f'id="topic-{topic}"' in doc
    assert "a, b" in doc  # Roslyn partagé par a et b


def test_html_creates_parent_directories(rich_corpus, tmp_path):
    run = graph_engine.parcours(rich_corpus, "v1", 1)
    out = tmp_path / "nested" / "deep" / "parcours.html"
    render_html(rich_corpus, write_run(run), out)
    assert out.exists()


# ---------------------------------------------------------------- smoke tests


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "vte.cli", *args],
        capture_output=True, text=True,
    )


def test_smoke_cli_run_then_render_makes_web_page(tmp_path):
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
    run_path = tmp_path / "runs" / "v1-r1.json"
    result = _run_cli("run", str(corpus_path), "--start", "v1",
                     "--rayon", "1", "--out", str(run_path))
    assert result.returncode == 0, result.stderr
    assert run_path.exists()
    saved = json.loads(run_path.read_text(encoding="utf-8"))
    assert saved["videos"][0] == "v1"

    page = tmp_path / "out" / "parcours.html"
    result = _run_cli("render", str(corpus_path), "--run", str(run_path), "--out", str(page))
    assert result.returncode == 0, result.stderr
    assert page.exists()
    doc = page.read_text(encoding="utf-8")
    assert doc.startswith("<!doctype html>")
    assert "<h1>Parcours depuis v1</h1>" in doc
    assert 'id="topic-A"' in doc
    assert f"chemin de sujets : <a href=\"#topic-B\"" in doc


def test_smoke_render_demo_corpus_end_to_end(tmp_path):
    """Pipeline complet sur le corpus de démo figé : run -> run.json -> page HTML."""
    repo_root = Path(__file__).resolve().parent.parent
    corpus_path = repo_root / "data" / "corpus_demo.json"
    if not corpus_path.exists():
        pytest.skip("data/corpus_demo.json absent")
    run_path = tmp_path / "demo.json"
    result = _run_cli("run", str(corpus_path), "--start", "vid-001",
                      "--rayon", "3", "--out", str(run_path))
    assert result.returncode == 0, result.stderr
    page = tmp_path / "parcours.html"
    result = _run_cli("render", str(corpus_path), "--run", str(run_path), "--out", str(page))
    assert result.returncode == 0, result.stderr
    doc = page.read_text(encoding="utf-8")
    assert "<h1>Parcours depuis vid-001</h1>" in doc
    assert "rayon : 3 hop(s) de sujets" in doc
    assert "chemin de sujets :" in doc
