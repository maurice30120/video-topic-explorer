"""Tests de cohérence sur le corpus réel (31+ vidéos YouTube vérifiées via oEmbed).

Vérifie les invariants du corpus et le comportement du moteur sur données
réelles : chaîne continue, ≤ 5 vidéos, sans doublon, explications réelles,
reproductibilité, exclusion des sujets morts, baseline.
"""

import json
import re
from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import load_corpus

REAL_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_real.json"
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


@pytest.fixture(scope="module")
def real_corpus():
    return load_corpus(REAL_CORPUS)


def test_real_corpus_exists_and_unique(real_corpus):
    ids = [video["id"] for video in real_corpus["videos"]]
    assert len(ids) >= 30
    assert len(ids) == len(set(ids))


def test_real_corpus_videos_are_youtube_ids(real_corpus):
    for video in real_corpus["videos"]:
        assert YOUTUBE_ID.match(video["id"]), f"ID YouTube invalide : {video['id']}"
        assert video["url"] == f"https://www.youtube.com/watch?v={video['id']}"
        assert video["title"]
        assert video.get("channel")


def test_real_corpus_topics_3_to_5(real_corpus):
    for video in real_corpus["videos"]:
        count = len(video["topics"])
        assert 3 <= count <= 5, f"{video['id']} a {count} sujets (attendu 3-5)"
        for topic in video["topics"]:
            assert topic["raw"] == topic["canonical"]
            assert topic["provenance"]["source"]


def test_real_corpus_graph_connected_enough(real_corpus):
    graph = graph_engine.build_graph(real_corpus)
    components = list(graph_engine.nx.connected_components(graph))
    largest = max(components, key=len)
    assert len(largest) >= 0.9 * len(graph), (
        f"composante principale trop petite : {len(largest)}/{len(graph)}"
    )


PARCOURS_STARTS = [
    "ghnY4S8unMM",  # Roslyn / C#
    "uMqx8NNT4xY",  # pont C# ↔ TypeScript (Hejlsberg)
    "BT2Cv-Tjq7Q",  # pont LLVM ↔ Rust
    "UJfF3-13aFo",  # pont TypeScript ↔ Compilateurs
    "HX0GH-YJbGw",  # pont Noyau Linux ↔ Rust
    "d1uraoHM8Gg",  # Rust
    "VwVg9jCtqaU",  # Machine Learning
    "hdxkt5mEnYE",  # pont LLVM ↔ Rust ↔ Compilateurs
]


@pytest.mark.parametrize("start", PARCOURS_STARTS)
@pytest.mark.parametrize("rayon", [1, 3])
def test_real_parcours_chain_invariants(real_corpus, start, rayon):
    run = graph_engine.parcours(real_corpus, start, rayon)
    assert run.videos[0] == start
    assert len(run.videos) == len(set(run.videos))
    assert len(run.videos) <= 5
    assert len(run.transitions) == len(run.videos) - 1
    for i, transition in enumerate(run.transitions):
        assert transition["from"] == run.videos[i]
        assert transition["to"] == run.videos[i + 1]
        path = transition["topic_path"]
        assert 1 <= len(path) <= run.radius + 1
        graph = graph_engine.build_graph(real_corpus)
        for topic in path:
            assert graph.has_node(f"topic:{topic}"), (
                f"sujet inexistant dans le graphe : {topic} — explication inventée interdite"
            )


@pytest.mark.parametrize("start", PARCOURS_STARTS)
def test_real_parcours_reproducible(real_corpus, start):
    first = graph_engine.parcours(real_corpus, start, 3)
    second = graph_engine.parcours(real_corpus, start, 3)
    assert first.to_dict() == second.to_dict()


def test_real_rayon_explicite_porte_par_le_run(real_corpus):
    """Ticket #35 : le rayon explicite est porté par le run, jamais un mode."""
    assert graph_engine.parcours(real_corpus, "ghnY4S8unMM", 1).radius == 1
    assert graph_engine.parcours(real_corpus, "ghnY4S8unMM", 3).radius == 3


def test_real_dead_topics_excluded_from_runs(real_corpus):
    graph = graph_engine.build_graph(real_corpus)
    dead = {t for t in real_corpus["dead_topics"]}
    assert dead, "le corpus réel devrait contenir au moins un sujet mort"
    for start in PARCOURS_STARTS:
        run = graph_engine.parcours(real_corpus, start, 3)
        for transition in run.transitions:
            for topic in transition["topic_path"]:
                assert topic not in dead


def test_real_dead_topics_still_in_graph(real_corpus):
    graph = graph_engine.build_graph(real_corpus)
    for topic in real_corpus["dead_topics"]:
        assert graph.has_node(f"topic:{topic}")


def test_real_baseline_sorted_by_common_topics(real_corpus):
    graph = graph_engine.build_graph(real_corpus)
    start = "ghnY4S8unMM"
    seed = graph_engine.topics_in(graph, start)
    result = graph_engine.baseline(real_corpus, start)
    assert start not in result
    scored = []
    for video in result:
        common = len(seed & graph_engine.topics_in(graph, video))
        assert common > 0, "la baseline ne doit contenir que des vidéos avec sujet commun"
        scored.append(common)
    assert scored == sorted(scored, reverse=True)


def test_real_run_json_serializable(real_corpus, tmp_path):
    run = graph_engine.parcours(real_corpus, "ghnY4S8unMM", 3)
    graph_engine.save_run(run, tmp_path / "run.json")
    loaded = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert loaded == run.to_dict()
    assert loaded["start"] == "ghnY4S8unMM"
    assert loaded["radius"] == 3
