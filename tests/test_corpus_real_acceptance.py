"""Critères d'acceptation du ticket #6 : corpus réel en clusters pontés.

Chaque test correspond à un critère d'acceptation explicite de l'issue #6 :
- ~30 vidéos en ~6 clusters reliés par des ponts réels ;
- métadonnées collectées à la main, pas de clé API YouTube ;
- corpus JSON figé complet (métadonnées + sujets extraits + provenance) ;
- graphe connecté : chaque cluster atteignable, ponts réels entre clusters ;
- aucune donnée de visionnage personnelle dans le dépôt.

L'appartenance aux clusters est celle des commentaires de
`scripts/make_real_corpus.py` (curatage manuel) ; le test de couverture
garantit que ce mapping ne dérive jamais du corpus figé.
"""

import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import load_corpus

REAL_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_real.json"

# Mapping miroir des clusters commentés dans scripts/make_real_corpus.py.
CLUSTERS: dict[str, list[str]] = {
    "roslyn-csharp": [
        "ghnY4S8unMM", "wXXHd8gYqVg", "vGYG8vkrlyk", "-bBA8WvH-BQ",
        "ROK4BMx81EY", "uMqx8NNT4xY", "w9T8pSVcX3Q", "Gv7vuA-7UVA",
    ],
    "compilateurs-llvm": [
        "bUTXhcf_aNc", "mfTYfzKqi5s", "8pdQFUOlHLQ", "VKIv_Bkp4pk",
        "3CI23HA7P9Y", "BT2Cv-Tjq7Q", "DWHDjVI5juo", "brVASZu2OrE",
    ],
    "rust": [
        "d1uraoHM8Gg", "79phqVpE7cU", "g2QTnlv3gBw", "VFIOSWy93H0",
        "bzja9fQWzdA", "erJdCIti_O8", "skos4B5x7qE",
    ],
    "typescript": [
        "UJfF3-13aFo", "10qowKUW82U", "nhVA0-iDbF4", "tXK50czRbdA",
        "cywK3XYYJ2o",
    ],
    "machine-learning": [
        "VwVg9jCtqaU", "7nTtApoOVf8", "xZ0Bdg5yOuk",
    ],
    "noyau-linux": [
        "HX0GH-YJbGw", "0mmPTWLQPRk", "enUkMK5JQY8",
    ],
}

# Vidéos pont explicites, hors clusters (section « Ponts explicites » du script).
BRIDGE_VIDEOS = ["hdxkt5mEnYE"]

# Paires de clusters reliées par une vidéo pont nommée (ponts réels, sujet partagé).
NAMED_BRIDGES = [
    ("roslyn-csharp", "typescript", "uMqx8NNT4xY"),   # Hejlsberg : C# ↔ TypeScript
    ("compilateurs-llvm", "rust", "hdxkt5mEnYE"),     # LLVM ↔ Rust ↔ Compilateurs
    ("rust", "noyau-linux", "HX0GH-YJbGw"),           # Noyau Linux ↔ Rust
    ("compilateurs-llvm", "machine-learning", "xZ0Bdg5yOuk"),  # Optimisation
]

# Champs autorisés : une donnée de visionnage personnelle n'a pas sa place ici.
ALLOWED_VIDEO_KEYS = {"id", "url", "title", "channel", "description", "transcript", "topics"}
ALLOWED_TOPIC_KEYS = {"raw", "canonical", "justification", "provenance"}
PERSONAL_DATA_KEYS = re.compile(r"watch|histor|preference|profil|like[_s]|favori", re.I)
API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


@pytest.fixture(scope="module")
def real_corpus():
    return load_corpus(REAL_CORPUS)


def _topics_by_video(corpus):
    return {v["id"]: {t["canonical"] for t in v["topics"]} for v in corpus["videos"]}


def _cluster_of():
    mapping = {}
    for cluster, ids in CLUSTERS.items():
        for vid in ids:
            mapping[vid] = cluster
    return mapping


def _cluster_adjacency(corpus):
    """Graphe des clusters : arête = sujet canonique partagé entre deux clusters."""
    cluster_of = _cluster_of()
    topics_of = _topics_by_video(corpus)
    topic_to_clusters: dict[str, set[str]] = {}
    for vid, topics in topics_of.items():
        cluster = cluster_of.get(vid)
        if cluster is None:
            continue  # vidéos pont : reliées via leurs clusters d'arrivée
        for topic in topics:
            topic_to_clusters.setdefault(topic, set()).add(cluster)
    adjacency: dict[str, set[str]] = {name: set() for name in CLUSTERS}
    for clusters in topic_to_clusters.values():
        for a, b in combinations(sorted(clusters), 2):
            adjacency[a].add(b)
            adjacency[b].add(a)
    return adjacency


def test_clusters_cover_corpus_exactly(real_corpus):
    corpus_ids = {v["id"] for v in real_corpus["videos"]}
    mapped = set(sum(CLUSTERS.values(), [])) | set(BRIDGE_VIDEOS)
    assert mapped == corpus_ids, (
        "le mapping de clusters du test doit couvrir exactement le corpus figé"
    )


# --- AC 1 : ~30 vidéos en ~6 clusters reliés par 1-2 vidéos pont ---

def test_corpus_size_about_30(real_corpus):
    assert 25 <= len(real_corpus["videos"]) <= 40
    ids = [v["id"] for v in real_corpus["videos"]]
    assert len(ids) == len(set(ids))


def test_clusters_about_6_with_reasonable_size():
    assert 5 <= len(CLUSTERS) <= 8
    for name, ids in CLUSTERS.items():
        assert len(ids) >= 3, f"cluster {name} trop petit : {len(ids)} vidéo(s)"
    assert len(BRIDGE_VIDEOS) <= 2, "au plus 2 vidéos pont explicites hors clusters"


def test_named_bridge_videos_belong_to_corpus(real_corpus):
    corpus_ids = {v["id"] for v in real_corpus["videos"]}
    for _, _, bridge in NAMED_BRIDGES:
        assert bridge in corpus_ids, f"vidéo pont absente du corpus : {bridge}"


# --- AC 4 : graphe connecté, chaque cluster atteignable, ponts réels ---

def test_cluster_graph_connected_via_real_bridges(real_corpus):
    adjacency = _cluster_adjacency(real_corpus)
    start = next(iter(adjacency))
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency[node] - seen)
    assert seen == set(adjacency), (
        f"clusters non atteignables : {set(adjacency) - seen} — ponts manquants"
    )


def test_named_bridge_pairs_share_a_topic(real_corpus):
    topics_of = _topics_by_video(real_corpus)
    for cluster_a, cluster_b, bridge in NAMED_BRIDGES:
        topics_a = set().union(*(topics_of[v] for v in CLUSTERS[cluster_a]))
        topics_b = set().union(*(topics_of[v] for v in CLUSTERS[cluster_b]))
        assert topics_a & topics_b, (
            f"aucun sujet partagé entre {cluster_a} et {cluster_b} : pont inexistant"
        )
        bridge_topics = topics_of[bridge]
        assert bridge_topics & topics_a, (
            f"la vidéo pont {bridge} ne relie pas {cluster_a}"
        )
        assert bridge_topics & topics_b, (
            f"la vidéo pont {bridge} ne relie pas {cluster_b}"
        )


def test_bipartite_graph_single_component(real_corpus):
    graph = graph_engine.build_graph(real_corpus)
    components = list(graph_engine.nx.connected_components(graph))
    assert len(components) == 1, (
        f"le graphe doit être entièrement connecté, pas à 90 % : "
        f"{len(components)} composantes (tailles : "
        f"{sorted((len(c) for c in components), reverse=True)})"
    )
    assert len(components[0]) == len(graph)


# --- AC 2 + AC 3 : collecte manuelle, corpus figé complet, provenance ---

def test_frozen_corpus_metadata_complete(real_corpus):
    for video in real_corpus["videos"]:
        assert video["id"] and video["url"] and video["title"]
        assert video.get("channel"), f"chaîne manquante : {video['id']}"
        assert video.get("description"), f"description manquante : {video['id']}"
        assert video["url"] == f"https://www.youtube.com/watch?v={video['id']}"


def test_frozen_corpus_topics_with_provenance(real_corpus):
    for video in real_corpus["videos"]:
        topics = video["topics"]
        assert 3 <= len(topics) <= 5, f"{video['id']} : {len(topics)} sujets"
        for topic in topics:
            assert topic["raw"] and topic["canonical"] and topic["justification"]
            provenance = topic["provenance"]
            assert provenance["source"], f"provenance manquante : {video['id']}"
            assert provenance["model"], f"modèle manquant : {video['id']}"
            assert provenance["version"], f"version manquante : {video['id']}"
    assert real_corpus.get("provenance", {}).get("source") == "manual-curated", (
        "la version courante du corpus est un curatage manuel : la provenance "
        "au niveau corpus doit le dire explicitement"
    )


def test_manual_collection_no_youtube_api_key():
    """Pas de clé API YouTube dans le corpus figé ni dans les scripts de curatage."""
    targets = [REAL_CORPUS, REAL_CORPUS.parent.parent / "scripts" / "make_real_corpus.py"]
    for path in targets:
        content = path.read_text(encoding="utf-8")
        assert not API_KEY_PATTERN.search(content), f"clé API dans {path.name}"


# --- AC 5 : aucune donnée de visionnage personnelle dans le dépôt ---

def test_no_personal_data_strict_schema(real_corpus):
    for video in real_corpus["videos"]:
        extra = set(video) - ALLOWED_VIDEO_KEYS
        assert not extra, f"champs non prévus sur {video['id']} : {sorted(extra)}"
        for topic in video["topics"]:
            extra_topic = set(topic) - ALLOWED_TOPIC_KEYS
            assert not extra_topic, f"champs de sujet non prévus : {sorted(extra_topic)}"
            assert set(topic["provenance"]) <= {"source", "model", "version"}


def test_no_personal_data_keys_anywhere():
    def key_names(node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield key
                yield from key_names(value)
        elif isinstance(node, list):
            for item in node:
                yield from key_names(item)

    raw = json.loads(REAL_CORPUS.read_text(encoding="utf-8"))
    suspicious = [k for k in key_names(raw) if PERSONAL_DATA_KEYS.search(k)]
    assert not suspicious, f"clés évoquant des données personnelles : {suspicious}"
