"""Tests du rendu du graphe statique : moteur unique, PNG ou SVG selon l'extension.

Seam testé : vte.render.render_graph(corpus, run, out) — le format se déduit
du fichier demandé (.png ou .svg), un seul moteur de rendu dessine les deux,
avec le même layout et le même surlignage du sous-graphe du parcours.
"""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from vte.render import render_graph

HIGHLIGHT_VIDEO_COLOR = "#2171b5"
HIGHLIGHT_TOPIC_COLOR = "#e6550d"


def test_svg_output_is_wellformed_with_highlighted_subgraph(rich_corpus, tmp_path):
    run = {
        "start": "v1", "start_kind": "video",
        "radius": 3,
        "videos": ["v1", "v2", "v3"],
        "transitions": [
            {"to": "v2", "topic_path": ["C#", ".NET"]},
            {"to": "v3", "topic_path": ["C#", "Testing"]},
        ],
        "complete": True, "reason": None,
    }
    out = tmp_path / "graphe.svg"
    render_graph(rich_corpus, run, out)

    root = ET.parse(out).getroot()
    assert root.tag.endswith("svg")
    svg_text = out.read_text(encoding="utf-8")
    # le corpus complet est dessiné (nœuds normaux) ...
    assert "#9ecae1" in svg_text
    assert "#fdd0a2" in svg_text
    # ... et le sous-graphe du parcours est surligné dans les deux couleurs
    assert HIGHLIGHT_VIDEO_COLOR in svg_text
    assert HIGHLIGHT_TOPIC_COLOR in svg_text


def test_unsupported_extension_raises_explicit_error(rich_corpus, tmp_path):
    with pytest.raises(ValueError, match=r"\.png ou \.svg"):
        render_graph(rich_corpus, None, tmp_path / "graphe.gif")


def test_png_output_from_the_same_engine(rich_corpus, tmp_path):
    run = None
    out = tmp_path / "graphe.png"
    render_graph(rich_corpus, run, out)
    assert out.read_bytes().startswith(b"\x89PNG")


# ---------------------------------------------------------------- smoke tests


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "vte.cli", *args],
        capture_output=True, text=True,
    )


def test_smoke_cli_graph_renders_wellformed_svg(tmp_path):
    """AC #21 : demander le rendu en SVG via la CLI produit un SVG bien formé, surligné."""
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "videos": [
            {"id": "v1", "url": "https://e.com/1", "title": "Un",
             "description": "d", "topics": [{"raw": "A", "canonical": "A",
             "justification": "j", "provenance": {"source": "t", "model": "m", "version": "0"}}]},
            {"id": "v2", "url": "https://e.com/2", "title": "Deux",
             "description": "d", "topics": [{"raw": "A", "canonical": "A",
             "justification": "j", "provenance": {"source": "t", "model": "m", "version": "0"}}]},
        ]
    }), encoding="utf-8")
    run_path = tmp_path / "run.json"
    result = _run_cli("run", str(corpus_path), "--start", "v1",
                      "--rayon", "1", "--out", str(run_path))
    assert result.returncode == 0, result.stderr

    svg_path = tmp_path / "graphe.svg"
    result = _run_cli("graph", str(corpus_path), "--run", str(run_path), "--out", str(svg_path))
    assert result.returncode == 0, result.stderr
    root = ET.parse(svg_path).getroot()
    assert root.tag.endswith("svg")
    svg_text = svg_path.read_text(encoding="utf-8")
    assert HIGHLIGHT_VIDEO_COLOR in svg_text
    assert HIGHLIGHT_TOPIC_COLOR in svg_text
