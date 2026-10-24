"""Rendus : page HTML minimale et graphe statique (PNG) avec sous-graphe surligné."""

from __future__ import annotations

import html
import json
import re
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

# ------------------------------------------------------------------ feed vertical

MODE_LABELS = {"decouvrir": "Découvrir", "approfondir": "Approfondir"}
MODE_SWITCH_LABELS = {"decouvrir": "Basculer en Approfondir", "approfondir": "Basculer en Découvrir"}
_FEED_MODES = ("decouvrir", "approfondir")


def _embed_url(url: str) -> str | None:
    """URL d'intégration (youtube-nocookie) d'une vidéo YouTube, sinon None."""
    for pattern in (
        r"youtube\.com/watch\?[^#]*?\bv=([\w-]+)",
        r"youtu\.be/([\w-]+)",
        r"youtube\.com/embed/([\w-]+)",
        r"youtube\.com/shorts/([\w-]+)",
    ):
        match = re.search(pattern, url)
        if match:
            return (
                f"https://www.youtube-nocookie.com/embed/{match.group(1)}"
                "?enablejsapi=1&mute=1&playsinline=1&rel=0"
            )
    return None


def _player_html(video: dict[str, Any]) -> str:
    """Lecteur intégré de la vidéo (iframe), ou lien de repli si hors YouTube."""
    embed = _embed_url(video.get("url", ""))
    if embed is None:
        return (
            f'<p class="lecteur lecteur-lien">Vidéo hors YouTube : '
            f'<a href="{html.escape(video.get("url", "#"), quote=True)}">'
            f"{html.escape(video['title'])}</a></p>"
        )
    return (
        '<div class="lecteur">'
        f'<iframe src="{html.escape(embed, quote=True)}" '
        'title="lecteur intégré" allow="autoplay; encrypted-media; picture-in-picture" '
        "allowfullscreen loading=\"lazy\"></iframe>"
        "</div>"
    )


def _stations_html(topic_path: list[str]) -> str:
    """Ligne de sujets de la transition : une pastille par sujet, reliées."""
    stations = "".join(
        f'<span class="station"><span class="pastille"></span>'
        f'<span class="nom">{html.escape(topic)}</span></span>'
        for topic in topic_path
    )
    return f'<div class="ligne-sujets">{stations}</div>'


def _card_html(
    by_id: dict[str, dict],
    video_id: str,
    transition: dict[str, Any] | None,
    departure: bool,
) -> str:
    video = by_id[video_id]
    channel_html = ""
    if video.get("channel"):
        channel_html = f'<p class="chaine">{html.escape(video["channel"])}</p>'
    if transition and transition.get("topic_path"):
        path_attr = html.escape("|".join(transition["topic_path"]), quote=True)
        path_html = (
            f'<div class="chemin" data-sujets="{path_attr}">'
            + _stations_html(transition["topic_path"])
            + "</div>"
        )
    elif departure:
        path_html = (
            '<div class="chemin"><div class="ligne-sujets">'
            '<span class="station depart"><span class="pastille"></span>'
            '<span class="nom">Départ</span></span></div></div>'
        )
    else:
        path_html = ""
    return (
        f'<article class="carte{" depart" if departure else ""}" '
        f'data-video="{html.escape(video_id, quote=True)}">'
        f"{_player_html(video)}"
        '<div class="legende">'
        f'<h2 class="titre">{html.escape(video["title"])}</h2>'
        f"{channel_html}"
        f"{path_html}"
        "</div>"
        "</article>"
    )


def _end_card_html(run: dict[str, Any], mode: str, other_mode: str | None) -> str:
    """Carte de fin : raison d'arrêt du moteur, rejouer, basculer de mode."""
    if run["complete"]:
        reason = f"Parcours complet : {len(run['videos'])} vidéos."
    else:
        reason = run.get("reason") or "Parcours interrompu."
    switch_html = ""
    if other_mode:
        switch_html = (
            f'<button class="action basculer" data-mode-vers="{other_mode}" type="button">'
            f"{MODE_SWITCH_LABELS[mode]}</button>"
        )
    return (
        '<article class="carte fin">'
        '<div class="fin-contenu">'
        '<h2 class="titre">Fin du parcours</h2>'
        f'<p class="raison">{html.escape(reason)}</p>'
        '<div class="actions">'
        '<button class="action rejouer" type="button">Revoir le parcours</button>'
        f"{switch_html}"
        "</div>"
        "</div>"
        "</article>"
    )


def _parcours_html(
    by_id: dict[str, dict],
    run: dict[str, Any],
    mode: str,
    active: bool,
    other_mode: str | None,
) -> str:
    cards = []
    for index, video_id in enumerate(run["videos"]):
        transition = next((t for t in run["transitions"] if t["to"] == video_id), None)
        cards.append(_card_html(by_id, video_id, transition, index == 0))
    cards.append(_end_card_html(run, mode, other_mode))
    return (
        f'<section class="parcours" data-mode="{html.escape(mode, quote=True)}"'
        + ("" if active else " hidden")
        + ">"
        + "".join(cards)
        + "</section>"
    )


def build_feed_html(
    corpus: dict[str, Any],
    runs: dict[str, dict[str, Any]],
    graph_href: str | None = None,
    default_mode: str = "decouvrir",
) -> str:
    """Construit la page unique du feed vertical (les deux modes embarqués) et la renvoie."""
    from .corpus import videos_by_id

    by_id = videos_by_id(corpus)
    modes = [m for m in _FEED_MODES if m in runs]
    if not modes:
        raise ValueError("le feed exige au moins un parcours (mode decouvrir ou approfondir)")
    if default_mode not in modes:
        default_mode = modes[0]
    sections = "\n".join(
        _parcours_html(
            by_id, runs[mode], mode, mode == default_mode,
            next((m for m in modes if m != mode), None),
        )
        for mode in modes
    )
    toggles = "".join(
        f'<button class="mode" data-mode="{mode}" '
        f'aria-pressed="{"true" if mode == default_mode else "false"}" type="button">'
        f"{MODE_LABELS[mode]}</button>"
        for mode in modes
    )
    doc = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parcours — Video Topic Explorer</title>
</head>
<body>
<header class="barre">
<p class="marque">Video Topic Explorer</p>
<nav class="modes" aria-label="Mode du parcours">
{toggles}
</nav>
</header>
<main class="feed" id="feed">
{sections}
</main>
</body>
</html>
"""
    return doc
