"""Stats du graphe biparti : fonction pure graph_stats et sous-commande CLI `stats`.

Vérifie l'affichage demandé par le ticket #3 : composantes connectées,
sujets morts, densité — sur des corpus JSON figés, sans réseau ni LLM.
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import canonical, load_corpus

DEMO_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_demo.json"


def test_graph_stats_counts_videos_topics_edges_components_density(chain_corpus):
    """Exemple travaillé : 5 vidéos, 6 sujets, 9 liens, 2 composantes.

    Densité du graphe biparti : 9 liens sur C(11, 2) = 55 paires possibles.
    """
    stats = graph_engine.graph_stats(chain_corpus)
    assert stats["videos"] == 5
    assert stats["topics"] == 6
    assert stats["edges"] == 9
    assert stats["components"] == 2
    assert stats["component_sizes"] == [9, 2]
    assert stats["density"] == 9 / 55


def test_graph_stats_distinguishes_dead_topics_from_linking_topics(chain_corpus):
    """C#, Rust et SujetUnique (1 vidéo chacun) sont morts ; Roslyn,
    Compilateurs et LLVM relient chacun 2 vidéos."""
    stats = graph_engine.graph_stats(chain_corpus)
    assert stats["dead_topics"] == ["C#", "Rust", "SujetUnique"]
    assert stats["linking_topics"] == ["Compilateurs", "LLVM", "Roslyn"]

def test_cli_stats_prints_components_dead_topics_and_density(chain_corpus, tmp_path, capsys):
    """`vte stats <corpus>` affiche les stats du graphe (ticket #3)."""
    from vte import cli

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({"videos": chain_corpus["videos"]}), encoding="utf-8")
    code = cli.main(["stats", str(corpus_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "vidéos : 5" in out
    assert "composantes connectées : 2" in out
    assert "sujets morts : C#, Rust, SujetUnique" in out
    assert "sujets reliant plusieurs vidéos : Compilateurs, LLVM, Roslyn" in out
    assert "densité : 0.164" in out

def test_demo_corpus_is_fictitious_with_alias_dead_topic_and_provenance():
    """Ticket #3 : corpus de démo 6-8 vidéos, alias évident normalisé,
    sujet mort et provenance d'extraction sur chaque sujet."""
    if not DEMO_CORPUS.exists():
        pytest.skip("data/corpus_demo.json absent")
    corpus = load_corpus(DEMO_CORPUS)
    assert 6 <= len(corpus["videos"]) <= 8

    # Alias évident : libellé brut conservé, distinct du canonique.
    aliased = [t for v in corpus["videos"] for t in v["topics"] if t["raw"] != t["canonical"]]
    assert aliased, "aucun alias à normaliser dans le corpus de démo"
    assert all(canonical(t["raw"]) == t["canonical"] for t in aliased)

    # La normalisation fusionne : deux libellés bruts distincts -> un canonique.
    raws_by_canonical: dict[str, set[str]] = defaultdict(set)
    for video in corpus["videos"]:
        for topic in video["topics"]:
            raws_by_canonical[topic["canonical"]].add(topic["raw"])
    merged = {c: raws for c, raws in raws_by_canonical.items() if len(raws) >= 2}
    assert any(t["canonical"] in merged for t in aliased)

    # Au moins un sujet mort, conservé dans le JSON et le graphe.
    assert corpus["dead_topics"]
    graph = graph_engine.build_graph(corpus)
    for dead in corpus["dead_topics"]:
        assert f"topic:{dead}" in graph

    # Provenance (source, modèle, version) sur chaque extraction.
    for video in corpus["videos"]:
        for topic in video["topics"]:
            provenance = topic.get("provenance", {})
            assert provenance.get("source")
            assert provenance.get("model")
            assert provenance.get("version")


def test_demo_corpus_stats_are_consistent():
    """graph_stats sur le corpus de démo : sujets morts cohérents au chargement."""
    if not DEMO_CORPUS.exists():
        pytest.skip("data/corpus_demo.json absent")
    corpus = load_corpus(DEMO_CORPUS)
    stats = graph_engine.graph_stats(corpus)
    assert stats["videos"] == len(corpus["videos"])
    assert stats["dead_topics"] == corpus["dead_topics"]
    assert stats["components"] >= 1
