"""Graphe biparti vidéo-sujet et moteur de parcours — fonction pure.

Le mode se réduit à un rayon de hops de sujets compté depuis l'ensemble des
sujets du point de départ : Approfondir = 1, Découvrir = 2-3.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from .corpus import CorpusError, videos_by_id

MAX_PATH = 5
MODE_RADIUS = {"approfondir": 1, "decouvrir": 3}


class PathfindingError(ValueError):
    """Point de départ invalide ou parcouru impossible."""


@dataclass(frozen=True)
class Transition:
    """Transition entre deux vidéos d'un parcours.

    `topic_path` est le chemin de sujets réellement présent dans le graphe
    (ex. ["Roslyn", "Compilateurs", "LLVM"]) — jamais une justification inventée.
    """

    topic_path: list[str]

    def explanation(self) -> str:
        return " → ".join(self.topic_path)


@dataclass
class Run:
    """Résultat auditable d'un parcours (sérialisé en run.json)."""

    start: str
    start_kind: str  # "video" | "topic"
    mode: str
    radius: int
    videos: list[str] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "start_kind": self.start_kind,
            "mode": self.mode,
            "radius": self.radius,
            "videos": self.videos,
            "transitions": self.transitions,
            "complete": self.complete,
            "reason": self.reason,
        }


def build_graph(corpus: dict[str, Any]) -> nx.Graph:
    """Construit le graphe biparti video:<id> — topic:<canonical>."""
    graph = nx.Graph()
    for video in corpus["videos"]:
        vid_node = f"video:{video['id']}"
        graph.add_node(vid_node, kind="video", label=video["title"], video_id=video["id"])
        for topic in video.get("topics", []):
            canon = topic["canonical"]
            topic_node = f"topic:{canon}"
            graph.add_node(topic_node, kind="topic", label=canon, topic=canon)
            graph.add_edge(vid_node, topic_node)
    return graph


def graph_stats(corpus: dict[str, Any]) -> dict[str, Any]:
    """Stats du graphe biparti : composantes connectées, sujets morts, densité.

    Les sujets morts (portés par une seule vidéo) y sont distingués des sujets
    reliant plusieurs vidéos : ils restent dans le graphe visuel mais sont
    exclus des candidats de parcours.
    """
    graph = build_graph(corpus)
    topic_nodes = [n for n, d in graph.nodes(data=True) if d["kind"] == "topic"]
    sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    degree = {n.removeprefix("topic:"): graph.degree(n) for n in topic_nodes}
    return {
        "videos": graph.number_of_nodes() - len(topic_nodes),
        "topics": len(topic_nodes),
        "edges": graph.number_of_edges(),
        "components": len(sizes),
        "component_sizes": sizes,
        "density": nx.density(graph),
        "dead_topics": sorted(t for t, deg in degree.items() if deg < 2),
        "linking_topics": sorted(t for t, deg in degree.items() if deg >= 2),
    }


def topic_radius(graph: nx.Graph, seed_topics: set[str], radius: int) -> set[str]:
    """Sujets atteignables en au plus `radius` hops de sujets depuis les sujets du départ.

    Les hops se comptent sur le graphe projeté sujet-sujet (deux sujets sont
    voisins s'ils partagent au moins une vidéo).
    """
    projected = nx.Graph()
    topic_nodes = {node for node, data in graph.nodes(data=True) if data["kind"] == "topic"}
    for node in topic_nodes:
        projected.add_node(node)
    for video in {n for n, d in graph.nodes(data=True) if d["kind"] == "video"}:
        topics = sorted(n for n in graph[video] if n in topic_nodes)
        for i, first in enumerate(topics):
            for second in topics[i + 1 :]:
                projected.add_edge(first, second)

    reachable: set[str] = set()
    for seed in seed_topics:
        seed_node = f"topic:{seed}"
        if seed_node not in projected:
            continue
        reachable.update(nx.single_source_shortest_path_length(projected, seed_node, cutoff=radius))
    return {node.removeprefix("topic:") for node in reachable}


def _candidate_explanations(
    graph: nx.Graph,
    from_video: str,
    to_video: str,
    allowed_topics: set[str],
    topic_nodes: set[str],
) -> list[list[str]]:
    """Chemins de sujets réels (sur le graphe projeté) entre deux vidéos."""
    projected = _projected_within(graph, allowed_topics, topic_nodes)
    from_topics = sorted(
        f"topic:{t}"
        for t in topics_in(graph, from_video, allowed_topics)
    )
    to_topics = sorted(f"topic:{t}" for t in topics_in(graph, to_video, allowed_topics))
    paths: list[list[str]] = []
    for start in from_topics:
        if start not in projected:
            continue
        lengths = nx.single_source_shortest_path_length(projected, start)
        for goal in to_topics:
            if goal not in lengths:
                continue
            for path in nx.all_shortest_paths(projected, start, goal):
                paths.append([node.removeprefix("topic:") for node in path])
    return paths


def _projected_within(graph: nx.Graph, allowed_topics: set[str], topic_nodes: set[str]) -> nx.Graph:
    projected = nx.Graph()
    for topic in allowed_topics:
        projected.add_node(f"topic:{topic}")
    for video in {n for n, d in graph.nodes(data=True) if d["kind"] == "video"}:
        topics = sorted(n for n in graph[video] if n in topic_nodes)
        topics = [t for t in topics if t.removeprefix("topic:") in allowed_topics]
        for i, first in enumerate(topics):
            for second in topics[i + 1 :]:
                projected.add_edge(first, second)
    return projected


def topics_in(graph: nx.Graph, video_id: str, allowed: set[str] | None = None) -> set[str]:
    vid_node = f"video:{video_id}"
    if vid_node not in graph:
        raise PathfindingError(f"vidéo inconnue : {video_id}")
    topics = {
        neighbor.removeprefix("topic:")
        for neighbor in graph[vid_node]
        if neighbor.startswith("topic:")
    }
    if allowed is not None:
        topics &= allowed
    return topics


def parcours(corpus: dict[str, Any], start: str, mode: str, radius: int | None = None) -> Run:
    """Fonction pure : (corpus figé, point de départ, mode) → run.

    - Chaque vidéo suggérée suit la précédente par un chemin de sujets
      réellement présent dans le graphe (direct ou via sujets intermédiaires).
    - Cinq vidéos distinctes maximum, jamais de doublon.
    - Départage à égalité : sujets communs décroissants, puis ID croissant.
    - Jamais d'élargissement automatique du rayon.
    - Sujets morts exclus des candidats ; parcours partiel avec motif.
    """
    if mode not in MODE_RADIUS:
        raise PathfindingError(f"mode inconnu : {mode!r} (attendu : {sorted(MODE_RADIUS)})")
    if radius is None:
        radius = MODE_RADIUS[mode]
    if radius < 1:
        raise PathfindingError("le rayon de hops doit être >= 1")

    graph = build_graph(corpus)
    by_id = videos_by_id(corpus)
    dead = set(corpus.get("dead_topics", ()))
    topic_nodes = {n for n, d in graph.nodes(data=True) if d["kind"] == "topic"}

    start_kind = "video" if start in by_id else "topic"
    if start_kind == "topic" and f"topic:{start}" not in graph:
        raise PathfindingError(f"sujet inconnu : {start!r}")

    if start_kind == "video":
        chain: list[str] = [start]
        seed_topics = topics_in(graph, start)
    else:
        chain = []
        seed_topics = {start}

    alive_seed = seed_topics - dead
    allowed = topic_radius(graph, alive_seed, radius) - dead
    if not allowed:
        raise PathfindingError(
            "point de départ isolé : aucun sujet vivant atteignable dans le rayon "
            f"({radius} hop(s)) ; affichez le graphe du corpus pour visualiser sa topologie"
        )

    if start_kind == "topic":
        if not any(
            topics_in(graph, data["video_id"], allowed)
            for _, data in graph.nodes(data=True)
            if data["kind"] == "video"
        ):
            raise PathfindingError(
                "point de départ isolé : aucune vidéo ne porte ce sujet vivant dans le rayon"
            )
        chain = [min(
            (v for v in by_id if topics_in(graph, v) & {start}),
            key=lambda v: v,
        )]
        run = _extend(graph, corpus, chain, allowed, topic_nodes, mode, radius, start, start_kind)
        run.transitions.insert(0, {
            "from": None,
            "from_node": None,
            "to": chain[0],
            "to_node": f"video:{chain[0]}",
            "topic_path": [start],
            "topic_nodes": [f"topic:{start}"],
            "explanation": f"sujet de départ : {start}",
        })
        return run

    return _extend(graph, corpus, chain, allowed, topic_nodes, mode, radius, start, start_kind)


def _extend(
    graph: nx.Graph,
    corpus: dict[str, Any],
    chain: list[str],
    allowed: set[str],
    topic_nodes: set[str],
    mode: str,
    radius: int,
    start: str,
    start_kind: str,
) -> Run:
    run = Run(start=start, start_kind=start_kind, mode=mode, radius=radius)
    used = set(chain)
    current = chain[-1] if chain else None

    while current is not None and len(chain) < MAX_PATH:
        current_topics = topics_in(graph, current, allowed)
        next_candidates: list[tuple[int, str, list[str]]] = []
        for node, data in graph.nodes(data=True):
            if data["kind"] != "video" or data["video_id"] in used:
                continue
            video_id = data["video_id"]
            video_topics = topics_in(graph, video_id, allowed)
            if not video_topics:
                continue
            paths = _candidate_explanations(graph, current, video_id, allowed, topic_nodes)
            if not paths:
                continue
            paths.sort(key=len)
            common = len(topics_in(graph, current) & topics_in(graph, video_id))
            next_candidates.append((common, video_id, paths[0]))
        next_candidates.sort(key=lambda c: (-c[0], c[1]))
        if not next_candidates:
            break
        common, chosen, best = next_candidates[0]
        run.transitions.append({
            "from": current,
            "from_node": f"video:{current}",
            "to": chosen,
            "to_node": f"video:{chosen}",
            "topic_path": best,
            "topic_nodes": [f"topic:{t}" for t in best],
            "explanation": " → ".join(best),
        })
        chain.append(chosen)
        used.add(chosen)
        current = chosen

    run.videos = list(chain)
    if len(chain) >= MAX_PATH:
        run.complete = True
    else:
        run.complete = False
        run.reason = (
            f"parcours partiel : plus aucune vidéo atteignable par chemin de sujets "
            f"de rayon {radius} depuis la dernière vidéo (topologie du corpus ou mode)"
        )
    return run


def baseline(corpus: dict[str, Any], start: str) -> list[str]:
    """Baseline honnête : vidéos partageant au moins un sujet avec le départ,
    triées par nombre de sujets communs décroissants, puis ID croissant."""
    by_id = videos_by_id(corpus)
    if start not in by_id and f"topic:{start}" not in build_graph(corpus):
        raise PathfindingError(f"point de départ inconnu : {start!r}")
    graph = build_graph(corpus)
    if start in by_id:
        seed = topics_in(graph, start)
    else:
        seed = {start}
    scored: list[tuple[int, str]] = []
    for video in corpus["videos"]:
        if video["id"] == start:
            continue
        common = len(seed & topics_in(graph, video["id"]))
        if common > 0:
            scored.append((common, video["id"]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [video_id for _, video_id in scored]


def save_run(run: Run, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
