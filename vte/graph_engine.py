"""Graphe biparti vidéo-sujet et moteur de parcours — fonction pure.

Le rayon de hops de sujets, compté depuis l'ensemble des sujets vivants du
point de départ, est un paramètre explicite de chaque pas et du parcours
complet (spec #27) : il est dérivé de la rétention applicative côté session
ou serveur — l'ancien enum de mode et sa table mode → rayon sont supprimés.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

import networkx as nx

from .corpus import CorpusError, videos_by_id

MAX_PATH = 5


class StartKind(str, Enum):
    """Nature du point de départ : une vidéo ou un sujet."""

    VIDEO = "video"
    TOPIC = "topic"


class PathfindingError(ValueError):
    """Point de départ invalide ou parcouru impossible."""


@dataclass
class Run:
    """Résultat auditable d'un parcours (sérialisé en run.json)."""

    start: str
    start_kind: StartKind
    radius: int
    videos: list[str] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "start_kind": self.start_kind.value,
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
    return _topics_within(_projected(graph), seed_topics, radius)


def _projected(graph: nx.Graph) -> nx.Graph:
    """Graphe projeté sujet-sujet complet (construit une seule fois par run).

    Deux sujets y sont voisins s'ils partagent au moins une vidéo.
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
    return projected


def _topics_within(projected: nx.Graph, seed_topics: set[str], radius: int) -> set[str]:
    """Sujets atteignables en au plus `radius` hops dans le graphe projeté donné."""
    reachable: set[str] = set()
    for seed in seed_topics:
        seed_node = f"topic:{seed}"
        if seed_node not in projected:
            continue
        reachable.update(nx.single_source_shortest_path_length(projected, seed_node, cutoff=radius))
    return {node.removeprefix("topic:") for node in reachable}


def _shortest_topic_path(
    projected: nx.Graph, graph: nx.Graph, from_video: str, to_video: str
) -> list[str] | None:
    """Plus court chemin de sujets réel entre deux vidéos, sur le graphe complet.

    Le rayon ne plafonne jamais cette recherche (docs/MVP.md §11) :
    seules les candidates sont filtrées par éligibilité, jamais le chemin.
    Le chemin affiché est choisi ici, à l'affichage — il ne participe à aucun tri.
    """
    from_topics = sorted(f"topic:{t}" for t in topics_in(graph, from_video))
    to_topics = sorted(f"topic:{t}" for t in topics_in(graph, to_video))
    best: list[str] | None = None
    for origin in from_topics:
        lengths = nx.single_source_shortest_path_length(projected, origin)
        for goal in to_topics:
            if goal not in lengths:
                continue
            if best is None or lengths[goal] < len(best) - 1:
                best = [
                    node.removeprefix("topic:")
                    for node in nx.shortest_path(projected, origin, goal)
                ]
    return best


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


def _ranked_candidates(
    graph: nx.Graph, seed_topics: set[str], video_ids: Iterable[str]
) -> list[str]:
    """Départage unique (docs/MVP.md §11) : sujets communs décroissants, puis ID croissant.

    Cette seule règle sert le choix de la première vidéo d'un départ par
    sujet comme chaque extension ; la longueur des chemins de sujets n'y
    participe jamais.
    """
    scored = [(len(seed_topics & topics_in(graph, video_id)), video_id) for video_id in video_ids]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [video_id for _, video_id in scored]


def _transition(
    from_video: str | None, to_video: str, topic_path: list[str], explanation: str
) -> dict[str, Any]:
    """Forme unique du pas : départ (None pour un départ par sujet), arrivée,
    nœuds, chemin de sujets réel et son explication."""
    return {
        "from": from_video,
        "from_node": None if from_video is None else f"video:{from_video}",
        "to": to_video,
        "to_node": f"video:{to_video}",
        "topic_path": topic_path,
        "topic_nodes": [f"topic:{t}" for t in topic_path],
        "explanation": explanation,
    }


def parcours(corpus: dict[str, Any], start: str, radius: int | None) -> Run:
    """Fonction pure : (corpus figé, point de départ, rayon explicite) → run.

    - Le rayon est un paramètre explicite (spec #27) : il filtre
      l'éligibilité des candidates par rapport au départ, jamais la
      recherche de chemin.
    - Chaque vidéo suggérée suit la précédente par un chemin de sujets
      réellement présent dans le graphe complet (direct ou via sujets
      intermédiaires).
    - Cinq vidéos distinctes maximum, jamais de doublon.
    - Départage unique : sujets communs décroissants, puis ID croissant —
      la longueur du chemin de sujets n'y intervient jamais.
    - Jamais d'élargissement automatique du rayon.
    - Sujets morts exclus des candidats ; parcours partiel avec motif.
    """
    if radius is None:
        raise PathfindingError(
            "rayon requis : le parcours complet prend un rayon explicite "
            "(dérivé de la rétention côté session, spec #27)"
        )
    if radius < 1:
        raise PathfindingError("le rayon de hops doit être >= 1")

    graph = build_graph(corpus)
    by_id = videos_by_id(corpus)
    dead = set(corpus.get("dead_topics", ()))
    projected = _projected(graph)  # construit une seule fois par run

    start_kind = StartKind.VIDEO if start in by_id else StartKind.TOPIC
    if start_kind is StartKind.TOPIC and f"topic:{start}" not in graph:
        raise PathfindingError(f"sujet inconnu : {start!r}")

    if start_kind is StartKind.VIDEO:
        chain = [start]
        seed_topics = topics_in(graph, start)
    else:
        seed_topics = {start}

    alive_seed = seed_topics - dead
    allowed = _topics_within(projected, alive_seed, radius) - dead
    if not allowed:
        raise PathfindingError(
            "point de départ isolé : aucun sujet vivant atteignable dans le rayon "
            f"({radius} hop(s)) ; affichez le graphe du corpus pour visualiser sa topologie"
        )

    if start_kind is StartKind.TOPIC:
        chain = [
            _ranked_candidates(
                graph,
                alive_seed,
                [video_id for video_id in by_id if start in topics_in(graph, video_id)],
            )[0]
        ]
        run = _extend(graph, chain, allowed, projected, radius, start, start_kind)
        run.transitions.insert(0, _transition(None, chain[0], [start], f"sujet de départ : {start}"))
        return run

    return _extend(graph, chain, allowed, projected, radius, start, start_kind)


def _next_transition(
    graph: nx.Graph, allowed: set[str], projected: nx.Graph, current: str, used: set[str]
) -> dict[str, Any] | None:
    """Pas unique : la prochaine vidéo orientée par la vidéo courante, hors « used ».

    Même éligibilité (rayon depuis le départ) et même départage (sujets communs
    décroissants puis ID croissant) que le parcours complet ; None si épuisé.
    """
    paths: dict[str, list[str]] = {}
    for node, data in graph.nodes(data=True):
        if data["kind"] != "video" or data["video_id"] in used:
            continue
        video_id = data["video_id"]
        if not topics_in(graph, video_id, allowed):
            continue  # le rayon filtre l'éligibilité, jamais la recherche de chemin
        path = _shortest_topic_path(projected, graph, current, video_id)
        if path is not None:
            paths[video_id] = path
    ranked = _ranked_candidates(graph, topics_in(graph, current), paths)
    if not ranked:
        return None
    chosen = ranked[0]
    best = paths[chosen]
    return _transition(current, chosen, best, " → ".join(best))


def next_step(
    corpus: dict[str, Any],
    current: str,
    radius: int | None = None,
    exclude: set[str] | None = None,
) -> dict[str, Any] | None:
    """Fonction pure : (corpus figé, vidéo regardée, rayon, déjà montrées) → pas suivant.

    Le visionnage de la vidéo courante oriente la suggestion : le pas part
    d'un sujet de la vidéo regardée et aboutit à un sujet de la vidéo suggérée,
    par un chemin de sujets réel. Les vidéos déjà montrées (et la vidéo
    regardée) sont exclues : le panneau ne répète jamais une carte.
    Renvoie None quand aucune candidate ne reste — fin honnête, pas une erreur.

    Le rayon est un paramètre explicite (spec #27) : le serveur le dérive de
    la durée de visionnage de la carte quittée (rétention applicative). Il
    filtre l'éligibilité des candidates, jamais la recherche de chemin.
    """
    if radius is None:
        raise PathfindingError(
            "rayon requis : le pas suivant prend un rayon explicite "
            "(dérivé de la durée de visionnage, spec #27)"
        )
    if radius < 1:
        raise PathfindingError("le rayon de hops doit être >= 1")
    by_id = videos_by_id(corpus)
    if current not in by_id:
        raise PathfindingError(f"vidéo inconnue : {current!r}")
    graph = build_graph(corpus)
    projected = _projected(graph)
    dead = set(corpus.get("dead_topics", ()))
    seed = topics_in(graph, current)
    allowed = _topics_within(projected, seed - dead, radius) - dead
    if not allowed:
        raise PathfindingError(
            "point de départ isolé : aucun sujet vivant atteignable dans le rayon "
            f"({radius} hop(s)) ; affichez le graphe du corpus pour visualiser sa topologie"
        )
    used = set(exclude or ()) | {current}
    return _next_transition(graph, allowed, projected, current, used)


def first_step(
    corpus: dict[str, Any], sujet: str, exclude: set[str] | None = None
) -> dict[str, Any] | None:
    """Fonction pure : (corpus figé, sujet, déjà-vues) → premier pas depuis ce sujet.

    Brique de la sortie de branche dirigée : elle réutilise la machinerie des
    départs par sujet. La meilleure candidate parmi les vidéos porteuses du
    sujet, par sujets communs décroissants puis ID croissant (règle de
    départage unique du moteur), hors déjà-vues. Renvoie None quand aucune
    candidate ne reste — fin honnête, pas une erreur.
    """
    graph = build_graph(corpus)
    if f"topic:{sujet}" not in graph:
        raise PathfindingError(f"sujet inconnu : {sujet!r}")
    if sujet in corpus.get("dead_topics", ()):
        raise PathfindingError(
            f"sujet mort : {sujet} (porté par une seule vidéo ; il ne peut orienter aucun premier pas)"
        )
    used = set(exclude or ())
    porteurs = [
        data["video_id"]
        for _, data in graph.nodes(data=True)
        if data["kind"] == "video" and sujet in topics_in(graph, data["video_id"])
    ]
    ranked = _ranked_candidates(graph, {sujet}, [vid for vid in porteurs if vid not in used])
    if not ranked:
        return None
    chosen = ranked[0]
    return _transition(None, chosen, [sujet], f"sujet de départ : {sujet}")


def _extend(
    graph: nx.Graph,
    chain: list[str],
    allowed: set[str],
    projected: nx.Graph,
    radius: int,
    start: str,
    start_kind: StartKind,
) -> Run:
    """Étend la chaîne vidéo par vidéo jusqu'à MAX_PATH ou épuisement des candidates."""
    run = Run(start=start, start_kind=start_kind, radius=radius)
    used = set(chain)
    current = chain[-1]

    while len(chain) < MAX_PATH:
        transition = _next_transition(graph, allowed, projected, current, used)
        if transition is None:
            break
        run.transitions.append(transition)
        chain.append(transition["to"])
        used.add(transition["to"])
        current = transition["to"]

    run.videos = list(chain)
    if len(chain) >= MAX_PATH:
        run.complete = True
    else:
        run.complete = False
        run.reason = (
            f"parcours partiel : plus aucune vidéo atteignable par chemin de sujets "
            f"de rayon {radius} depuis la dernière vidéo (topologie du corpus)"
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
