"""Corpus élargi (data/corpus_elargi.json) : corpus réel + panel de genres.

Vérifie sur le panel élargi (musique, fun, science, économie, jeux vidéo) :
- les invariants du corpus figé : IDs YouTube valides, 3-5 sujets, provenance ;
- une seule composante connectée : chaque genre atteignable, ponts réels ;
- les ponts nommés entre genres partagent bien un sujet canonique ;
- les parcours depuis des départs du panel : chaîne continue, sans doublon,
  sujets du chemin présents dans le graphe, sujets morts exclus.

Le corpus est figé (version 2026-10) : ces tests caractérisent le
comportement attendu du moteur sur ce panel, sans réseau ni LLM.
"""

from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import load_corpus, topics_of

ELARGI_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_elargi.json"

# Genres du panel (miroir des sections commentées de scripts/make_elargi_corpus.py).
GENRES = {
    "musique": ["dQw4w9WgXcQ", "fJ9rUzIMcZQ", "9bZkp7q19f0", "5qap5aO4i9A", "44NUPu7cVfI", "Rd9K0Q_Ykx0", "BsGCGB_LZAo"],
    "fun": ["jNQXAC9IVRw", "xuCn8ux2gbs", "ZZ5LpwO-An4"],
    "science": ["aircAruvnKk", "fNk_zzaMoSs", "h6fcK_fRYaI", "MBRqu0YOH14", "2Vrhk5OjBP8", "rhgwIhB58PA"],
    "economie": ["3ez10ADR_gM", "GtksJpfoM_g"],
    "jeux": ["a1hHOVIkrcc", "nn2MXwplMZA", "QhWdBhc3Wjc", "emtlJ5SXLM4"],
}

# Ponts réels entre genres : (genre_a, genre_b, sujet canonique partagé).
NAMED_BRIDGES = [
    ("science", "technique", "Machine Learning"),      # 3Blue1Brown ↔ cluster ML du corpus réel
    ("musique", "science", "Apprentissage"),           # Lofi Girl ↔ 3Blue1Brown, Veritasium
    ("musique", "technique", "Tutoriels"),             # design sonore ↔ corpus réel
    ("fun", "jeux", "Histoire"),                       # bill wurtz ↔ Boss Keys Zelda
    ("economie", "science", "Pédagogie"),             # CrashCourse ↔ Veritasium
    ("musique", "fun", "Mème internet"),               # Rick Astley ↔ HEYYEYAA
]


@pytest.fixture(scope="module")
def elargi_corpus():
    return load_corpus(ELARGI_CORPUS)


def test_genres_cover_panel_exactly(elargi_corpus):
    corpus_ids = {v["id"] for v in elargi_corpus["videos"]}
    for genre, ids in GENRES.items():
        for vid in ids:
            assert vid in corpus_ids, f"vidéo du panel absente du corpus : {vid}"
    panel = {vid for ids in GENRES.values() for vid in ids}
    assert len(panel) == 22


def test_elargi_contains_real_corpus(elargi_corpus):
    real = load_corpus(ELARGI_CORPUS.parent / "corpus_real.json")
    real_ids = {v["id"] for v in real["videos"]}
    elargi_ids = {v["id"] for v in elargi_corpus["videos"]}
    assert real_ids < elargi_ids
    assert len(elargi_ids) == len(real_ids) + 22


def test_elargi_topics_3_to_5_with_provenance(elargi_corpus):
    for video in elargi_corpus["videos"]:
        assert 3 <= len(video["topics"]) <= 5, f"{video['id']} : {len(video['topics'])} sujets"
        for topic in video["topics"]:
            assert topic["raw"] == topic["canonical"]
            assert topic["provenance"]["source"]


def test_elargi_graph_single_component(elargi_corpus):
    graph = graph_engine.build_graph(elargi_corpus)
    components = list(graph_engine.nx.connected_components(graph))
    assert len(components) == 1, (
        f"le panel doit rester une seule composante : {len(components)} composantes"
    )


def test_elargi_named_bridges_share_topic(elargi_corpus):
    topics_of_ = {v["id"]: topics_of(v) for v in elargi_corpus["videos"]}
    real_ids = {
        v["id"] for v in load_corpus(ELARGI_CORPUS.parent / "corpus_real.json")["videos"]
    }

    def genre_topics(genre):
        ids = real_ids if genre == "technique" else GENRES[genre]
        return set().union(*(topics_of_[vid] for vid in ids))

    for genre_a, genre_b, bridge in NAMED_BRIDGES:
        assert bridge in genre_topics(genre_a) & genre_topics(genre_b), (
            f"pont absent entre {genre_a} et {genre_b} : {bridge}"
        )


PANEL_STARTS = [
    "dQw4w9WgXcQ",   # musique (Rick Astley)
    "xuCn8ux2gbs",   # fun (bill wurtz)
    "aircAruvnKk",   # science (3Blue1Brown)
    "3ez10ADR_gM",   # économie (CrashCourse)
    "a1hHOVIkrcc",   # jeux (Boss Keys)
    "GtksJpfoM_g",   # économie (Economics Explained)
]


@pytest.mark.parametrize("start", PANEL_STARTS)
@pytest.mark.parametrize("rayon", [1, 3])
def test_elargi_parcours_chain_invariants(elargi_corpus, start, rayon):
    run = graph_engine.parcours(elargi_corpus, start, rayon)
    assert run.videos[0] == start
    assert len(run.videos) == len(set(run.videos))
    assert len(run.videos) <= 5
    graph = graph_engine.build_graph(elargi_corpus)
    for transition in run.transitions:
        for topic in transition["topic_path"]:
            assert graph.has_node(f"topic:{topic}")


@pytest.mark.parametrize("start", PANEL_STARTS)
def test_elargi_parcours_reproducible(elargi_corpus, start):
    first = graph_engine.parcours(elargi_corpus, start, 3)
    second = graph_engine.parcours(elargi_corpus, start, 3)
    assert first.to_dict() == second.to_dict()


def test_elargi_dead_topics_excluded_from_runs(elargi_corpus):
    dead = set(elargi_corpus["dead_topics"])
    assert dead
    for start in PANEL_STARTS:
        run = graph_engine.parcours(elargi_corpus, start, 3)
        for transition in run.transitions:
            for topic in transition["topic_path"]:
                assert topic not in dead
