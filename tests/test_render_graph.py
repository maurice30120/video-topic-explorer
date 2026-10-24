"""Tests du rendu du graphe statique : moteur unique, PNG ou SVG selon l'extension.

Seam testé : vte.render.render_graph(corpus, run, out) — le format se déduit
du fichier demandé (.png ou .svg), un seul moteur de rendu dessine les deux,
avec le même layout et le même surlignage du sous-graphe du parcours.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

from vte.render import render_graph

HIGHLIGHT_VIDEO_COLOR = "#2171b5"
HIGHLIGHT_TOPIC_COLOR = "#e6550d"


def test_svg_output_is_wellformed_with_highlighted_subgraph(rich_corpus, tmp_path):
    run = {
        "start": "v1", "start_kind": "video", "mode": "decouvrir",
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
