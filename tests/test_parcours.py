"""Tests du moteur de parcours : comportement externe de la fonction pure.

Couvre : rayon par mode, continuité de la chaîne, absence de doublon,
exclusion des sujets morts, départage déterministe, parcours partiel avec
motif, départ isolé, reproductibilité sans appel LLM, baseline.
"""

from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import load_corpus

from conftest import make_video


def test_mode_radius_approfondir_stays_near(chain_corpus):
    run = graph_engine.parcours(chain_corpus, "a", "approfondir")
    assert run.radius == 1
    assert run.videos[0] == "a"
    for transition in run.transitions:
        assert len(transition["topic_path"]) <= 2  # rayon 1 : au plus sujet du départ → sujet voisin


def test_mode_radius_decouvrir_goes_far(chain_corpus):
    run = graph_engine.parcours(chain_corpus, "a", "decouvrir")
    assert run.radius == 3
    assert "d" in run.videos  # atteignable seulement via Roslyn → Compilateurs → LLVM


def test_chain_continuity_every_video_connected_to_previous(rich_corpus):
    for mode in ("approfondir", "decouvrir"):
        run = graph_engine.parcours(rich_corpus, "v1", mode)
        assert run.videos[0] == "v1"
        for transition in run.transitions:
            assert transition["from"] in run.videos
            assert transition["to"] in run.videos
            idx_from = run.videos.index(transition["from"])
            idx_to = run.videos.index(transition["to"])
            assert idx_to == idx_from + 1
            assert len(transition["topic_path"]) >= 1


def test_no_duplicate_and_max_five(rich_corpus):
    run = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    assert len(run.videos) == len(set(run.videos))
    assert len(run.videos) <= 5


def test_dead_topics_excluded_from_candidates(chain_corpus):
    run = graph_engine.parcours(chain_corpus, "a", "approfondir")
    assert "dead" not in run.videos
    assert "SujetUnique" in chain_corpus["dead_topics"]


def test_dead_topics_kept_in_graph_visual(chain_corpus):
    graph = graph_engine.build_graph(chain_corpus)
    assert "topic:SujetUnique" in graph
    assert graph.has_edge("video:dead", "topic:SujetUnique")


def test_deterministic_tiebreak_two_runs_identical(rich_corpus):
    first = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    second = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    assert first.to_dict() == second.to_dict()


def test_deterministic_tiebreak_prefers_common_then_id():
    corpus = load_corpus_from_videos([
        make_video("start", ["A"]),
        make_video("z", ["A", "B"]),
        make_video("b", ["A", "B"]),
    ])
    run = graph_engine.parcours(corpus, "start", "approfondir")
    assert run.videos[1] == "b"  # à égalité de sujets communs, ID croissant gagne


def test_partial_path_has_reason(chain_corpus):
    run = graph_engine.parcours(chain_corpus, "d", "approfondir")
    assert not run.complete  # seulement 4 vidéos atteignables
    assert run.reason
    assert run.videos[0] == "d"


def test_isolated_start_explicit_message(chain_corpus):
    with pytest.raises(graph_engine.PathfindingError) as exc:
        graph_engine.parcours(chain_corpus, "dead", "approfondir")
    assert "isolé" in str(exc.value)


def test_no_llm_call_reproducible_offline(rich_corpus, tmp_path):
    first = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    graph_engine.save_run(first, tmp_path / "run.json")
    reloaded = tmp_path / "run.json"
    second = graph_engine.parcours(load_corpus_from_videos(rich_corpus["videos"]), "v1", "decouvrir")
    assert first.to_dict() == second.to_dict()
    assert json.loads(reloaded.read_text(encoding="utf-8")) == second.to_dict()


import json  # noqa: E402


def test_radius_never_auto_widened():
    corpus = load_corpus_from_videos([
        make_video("s", ["X"]),
        make_video("m", ["X", "Y"]),
        make_video("m2", ["Y", "Z"]),
        make_video("t", ["Z"]),
    ])
    narrow = graph_engine.parcours(corpus, "s", "approfondir")  # rayon 1
    assert narrow.radius == 1
    assert "t" not in narrow.videos  # Z est à 2 hops : jamais atteint sans élargissement
    wide = graph_engine.parcours(corpus, "s", "decouvrir")  # rayon 3
    assert "t" in wide.videos


def test_topic_start(rich_corpus):
    run = graph_engine.parcours(rich_corpus, "Roslyn", "approfondir")
    assert run.start_kind == "topic"
    assert run.videos


def test_baseline_sorted_by_common_topics_desc():
    corpus = load_corpus_from_videos([
        make_video("start", ["A", "B"]),
        make_video("one", ["A"]),
        make_video("two", ["A", "B"]),
        make_video("three", ["A", "B", "C"]),
        make_video("none", ["Z"]),
    ])
    assert graph_engine.baseline(corpus, "start") == ["three", "two", "one"]


def test_baseline_excludes_start():
    corpus = load_corpus_from_videos([
        make_video("start", ["A"]),
        make_video("other", ["A"]),
    ])
    assert graph_engine.baseline(corpus, "start") == ["other"]


def test_topic_radius_respects_hops(rich_corpus):
    graph = graph_engine.build_graph(rich_corpus)
    seeds = {"C#"}
    assert graph_engine.topic_radius(graph, seeds, 1) == {"C#", "Testing", ".NET", "Roslyn"}
    mid = graph_engine.topic_radius(graph, seeds, 3)
    assert "Compilateurs" in mid
    assert "LLVM" in mid
    assert "Rust" not in mid  # Rust est à 4 hops de sujets de C#
    far = graph_engine.topic_radius(graph, seeds, 5)
    assert "Rust" in far


def load_corpus_from_videos(videos):
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump({"videos": videos}, handle, ensure_ascii=False)
        path = handle.name
    corpus = load_corpus(path)
    Path(path).unlink()
    return corpus

def test_decouvrir_saute_de_branche_plus_tot(rich_corpus):
    """Decouvrir classe par sujets nouveaux apportes : le saut de branche
    arrive des la premiere extension (v5 ne partage aucun sujet avec v1),
    la ou Approfondir suit la branche (v2 partage deux sujets avec v1).

    L'invariant « la longueur du chemin ne compte pas, ID croissant a
    egalite » reste couvert par test_etape.py (next_step, meme classement).
    """
    decouvrir = graph_engine.parcours(rich_corpus, "v1", "decouvrir")
    approfondir = graph_engine.parcours(rich_corpus, "v1", "approfondir")
    assert approfondir.videos[1] == "v2"
    assert decouvrir.videos[1] == "v5"


def test_run_transitions_carry_explicit_node_ids(chain_corpus):
    """run.json : chaque transition porte les IDs de noeuds du graphe biparti."""
    run = graph_engine.parcours(chain_corpus, "a", "decouvrir")
    graph = graph_engine.build_graph(chain_corpus)
    for transition in run.transitions:
        assert transition["from_node"] == f"video:{transition['from']}"
        assert transition["to_node"] == f"video:{transition['to']}"
        assert transition["topic_nodes"] == [f"topic:{t}" for t in transition["topic_path"]]
        for node in [transition["from_node"], transition["to_node"], *transition["topic_nodes"]]:
            assert graph.has_node(node), f"noeud inexistant dans le graphe : {node}"


def test_run_topic_start_first_transition_node_ids(rich_corpus):
    """Depart par sujet : la premiere transition part de None, le noeud sujet reste explicite."""
    run = graph_engine.parcours(rich_corpus, "Roslyn", "approfondir")
    first = run.transitions[0]
    assert first["from"] is None
    assert first["from_node"] is None
    assert first["to_node"] == f"video:{first['to']}"
    assert first["topic_nodes"] == ["topic:Roslyn"]


def test_transition_valid_by_real_path_outside_start_radius():
    """Ticket #19 : la candidate reste dans le rayon, le chemin de sujets ne l'est pas.

    C est a 2 hops du sujet de depart A (hors du rayon 1 d'Approfondir), mais
    t et u se suivent par le chemin reel [C] : la transition reste valide et
    affiche ce chemin — le rayon ne plafonne que l'eligibilite des
    candidates, jamais la recherche de chemin.
    """
    corpus = load_corpus_from_videos([
        make_video("s", ["A"]),
        make_video("w", ["A", "B"]),
        make_video("q", ["A", "X"]),
        make_video("t", ["C", "X"]),
        make_video("u", ["B", "C"]),
    ])
    graph = graph_engine.build_graph(corpus)
    assert "C" not in graph_engine.topic_radius(graph, {"A"}, 1)
    run = graph_engine.parcours(corpus, "s", "approfondir")
    steps = {(t["from"], t["to"]): t["topic_path"] for t in run.transitions}
    assert steps[("t", "u")] == ["C"]


def test_mode_and_startkind_minimal_types():
    """Ticket #19 : types dedies minimaux, table unique mode -> rayon de hops."""
    assert graph_engine.Mode("approfondir") is graph_engine.Mode.APPROFONDIR
    assert graph_engine.Mode("decouvrir") is graph_engine.Mode.DECOUVRIR
    assert graph_engine.MODE_RADIUS == {
        graph_engine.Mode.APPROFONDIR: 1,
        graph_engine.Mode.DECOUVRIR: 3,
    }
    assert graph_engine.StartKind.VIDEO == "video"
    assert graph_engine.StartKind.TOPIC == "topic"


def test_parcours_accepts_mode_string_or_member(chain_corpus):
    """Les chaînes restent acceptees ; le run porte le type et se serialize tel quel."""
    by_string = graph_engine.parcours(chain_corpus, "a", "decouvrir")
    by_member = graph_engine.parcours(chain_corpus, "a", graph_engine.Mode.DECOUVRIR)
    assert by_string.to_dict() == by_member.to_dict()
    assert by_member.mode == "decouvrir"
    assert by_member.to_dict()["mode"] == "decouvrir"


def test_unknown_mode_lists_valid_modes(chain_corpus):
    with pytest.raises(graph_engine.PathfindingError) as exc:
        graph_engine.parcours(chain_corpus, "a", "vagabonder")
    message = str(exc.value)
    assert "vagabonder" in message
    assert "approfondir" in message
    assert "decouvrir" in message


def test_topic_start_first_video_follows_extension_sort_rule():
    """Ticket #19 : la premiere video d'un depart par sujet suit la regle commune.

    Tous les porteurs du sujet de depart ont un sujet commun avec lui ; a
    egalite, l'ID croissant gagne — la meme regle de tri que chaque extension.
    """
    corpus = load_corpus_from_videos([
        make_video("z", ["A", "B"]),
        make_video("m", ["A", "B"]),
        make_video("b", ["A", "B"]),
    ])
    run = graph_engine.parcours(corpus, "A", "approfondir")
    assert run.start_kind == "topic"
    assert run.videos[0] == "b"
