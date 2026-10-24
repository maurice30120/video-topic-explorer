"""Rendus : page HTML minimale et graphe statique (PNG) avec sous-graphe surligné."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .graph_engine import build_graph


def build_html(corpus: dict[str, Any], run: dict[str, Any], graph_href: str | None = None) -> str:
    """Construit la page HTML du parcours et la renvoie en chaîne."""
    by_id = {video["id"]: video for video in corpus["videos"]}
    topic_videos: dict[str, list[str]] = {}
    for video in corpus["videos"]:
        for topic in video.get("topics", []):
            topic_videos.setdefault(topic["canonical"], []).append(video["id"])

    items = []
    for index, video_id in enumerate(run["videos"]):
        video = by_id[video_id]
        transition = next((t for t in run["transitions"] if t["to"] == video_id), None)
        path_html = ""
        if transition:
            chain_html = " → ".join(
                f'<a href="#topic-{html.escape(t)}" title="voir les vidéos portant ce sujet">{html.escape(t)}</a>'
                for t in transition["topic_path"]
            )
            path_html = f"<p class='transition'>chemin de sujets : {chain_html}</p>"
        items.append(
            "<li>"
            f"<a href='{html.escape(video.get('url', '#'))}'>{html.escape(video['title'])}</a> "
            f"<span class='vid'>({html.escape(video_id)})</span>"
            f"{path_html}"
            "</li>"
        )

    reason_html = ""
    if not run["complete"] and run.get("reason"):
        reason_html = f"<p class='reason'>{html.escape(run['reason'])}</p>"

    graph_html = ""
    if graph_href:
        graph_html = (
            '<p class="graph-link"><a href="' + html.escape(graph_href) + '">'
            "afficher le graphe du corpus avec le sous-graphe du parcours surligné</a></p>"
        )

    topic_anchors = "\n".join(
        f'<div id="topic-{html.escape(t)}"><strong>{html.escape(t)}</strong> : '
        + ", ".join(topic_videos.get(t, []))
        + "</div>"
        for t in sorted(topic_videos)
    )

    doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Parcours — {html.escape(run['start'])} ({html.escape(run['mode'])})</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; }}
.transition {{ color: #555; margin-left: 1rem; }}
.vid {{ color: #888; font-size: 0.85em; }}
.reason {{ color: #a33; }}
.graph-link {{ margin: 1rem 0; }}
ol li {{ margin: 0.75rem 0; }}
#topics {{ margin-top: 2rem; border-top: 1px solid #ccc; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>Parcours depuis {html.escape(run['start'])}</h1>
<p>mode : <strong>{html.escape(run['mode'])}</strong> — rayon : {run['radius']} hop(s)</p>
<ol>
{chr(10).join(items)}
</ol>
{reason_html}
{graph_html}
<div id="topics">
<h2>Sujets du corpus et leurs vidéos</h2>
{topic_anchors}
</div>
</body>
</html>
"""
    return doc


def render_html(
    corpus: dict[str, Any], run: dict[str, Any], out: Path, graph_href: str | None = None
) -> None:
    """Sauvegarde la page HTML du parcours (voir build_html pour la chaîne)."""
    doc = build_html(corpus, run, graph_href)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")


def render_graph_png(corpus: dict[str, Any], run: dict[str, Any] | None, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    graph = build_graph(corpus)
    highlighted: set[str] = set()
    if run:
        highlighted = {f"video:{v}" for v in run["videos"]}
        for transition in run.get("transitions", []):
            for topic in transition.get("topic_path", []):
                highlighted.add(f"topic:{topic}")

    pos = nx.spring_layout(graph, seed=42)
    plt.figure(figsize=(14, 10))
    normal_nodes = [n for n in graph if n not in highlighted]
    nx.draw_networkx_edges(graph, pos, alpha=0.2)
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in normal_nodes if n.startswith("video:")],
        node_shape="s", node_color="#9ecae1", node_size=120,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in normal_nodes if n.startswith("topic:")],
        node_shape="o", node_color="#fdd0a2", node_size=160,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in highlighted if n.startswith("video:")],
        node_shape="s", node_color="#2171b5", node_size=260,
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=[n for n in highlighted if n.startswith("topic:")],
        node_shape="o", node_color="#e6550d", node_size=360,
    )
    labels = {n: graph.nodes[n].get("label", n.removeprefix("topic:")) for n in graph if n in highlighted}
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=7)
    plt.axis("off")
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=150)
    plt.close()
