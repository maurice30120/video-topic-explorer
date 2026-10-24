"""Tests du protocole d'évaluation en aveugle (ticket #8, ADR-0001).

Vérifie au seam public des trois scripts eval/ : le tirage figé des 15 listes
(3 origines x ~5 départs), le masquage des origines et des explications,
la notation à l'aveugle sur trois critères (cohérence, surprise utile, clarté),
le refus de révélation avant notation complète, le seuil pré-engagé de
l'ADR-0001, et le cycle complet sur le corpus réel.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from conftest import make_video, load_corpus_from_videos

EVAL_DIR = Path(__file__).resolve().parent.parent / "eval"
REAL_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_real.json"
KINDS = ("baseline", "approfondir", "decouvrir")
CRITERIA = ("coherence", "surprise", "clarte")
LEAK_STRINGS = ("baseline", "approfondir", "decouvrir", "kind", "origine", "mode", "transitions", "topic_path")


def load_eval(name: str):
    spec = importlib.util.spec_from_file_location(name, EVAL_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def protocol_corpus():
    """Corpus dense : chaque départ éligible donne trois listes de même longueur (4)."""
    return load_corpus_from_videos([
        make_video("v1", ["C#", ".NET"]),
        make_video("v2", [".NET", "Roslyn"]),
        make_video("v3", ["Roslyn", "Compilateurs"]),
        make_video("v4", ["Compilateurs", "LLVM"]),
        make_video("v5", ["LLVM", "Rust"]),
        make_video("v6", ["Rust", "C#"]),
        make_video("v7", ["C#", "Roslyn"]),
        make_video("v8", [".NET", "Compilateurs"]),
        make_video("v9", ["Roslyn", "LLVM"]),
        make_video("v10", ["Compilateurs", "Rust"]),
    ])


STARTS = ["v1", "v2", "v3", "v4", "v5"]


def draw(protocol_corpus, seed=20261020, starts=STARTS):
    blind_draw = load_eval("blind_draw")
    return blind_draw.build_protocol(protocol_corpus, seed=seed, starts=starts)


class TestBlindDraw:
    def test_freezes_three_lists_per_start(self, protocol_corpus):
        order, mapping = draw(protocol_corpus)
        letters = sorted(order["letters"])
        assert len(letters) == len(STARTS) * 3
        for letter in letters:
            entry = mapping[letter]
            assert entry["start"] in STARTS
            assert entry["origine"] in KINDS
        per_start = {start: [] for start in STARTS}
        for letter, entry in mapping.items():
            per_start[entry["start"]].append(entry["origine"])
        for start in STARTS:
            assert sorted(per_start[start]) == sorted(KINDS)

    def test_order_payload_masks_origins_and_explanations(self, protocol_corpus):
        order, _ = draw(protocol_corpus)
        text = json.dumps(order, ensure_ascii=False).lower()
        for leak in LEAK_STRINGS:
            assert leak not in text, f"fuite d'origine : {leak!r} dans order.json"
        for letter, payload in order["letters"].items():
            assert payload["videos"], f"liste vide pour {letter}"
            for video in payload["videos"]:
                assert set(video) == {"id", "title"}

    def test_blind_lists_match_engine(self, protocol_corpus):
        from vte import graph_engine

        order, mapping = draw(protocol_corpus)
        for letter, entry in mapping.items():
            payload = order["letters"][letter]
            assert payload["start"] == entry["start"]
            if entry["origine"] == "baseline":
                expected = graph_engine.baseline(protocol_corpus, entry["start"])[:4]
            else:
                run = graph_engine.parcours(protocol_corpus, entry["start"], entry["origine"])
                expected = run.videos[1:5]
            assert [video["id"] for video in payload["videos"]] == expected

    def test_same_seed_same_draw(self, protocol_corpus):
        first_order, first_mapping = draw(protocol_corpus, seed=7)
        second_order, second_mapping = draw(protocol_corpus, seed=7)
        assert first_order == second_order
        assert first_mapping == second_mapping

    def test_auto_selects_deterministic_starts(self, protocol_corpus):
        blind_draw = load_eval("blind_draw")
        first = blind_draw.build_protocol(protocol_corpus, seed=7, count=5)
        second = blind_draw.build_protocol(protocol_corpus, seed=7, count=5)
        assert first[0]["starts"] == second[0]["starts"]
        assert len(first[0]["starts"]) == 5
        assert len(set(first[0]["starts"])) == 5

    def test_unequal_length_start_is_ineligible_and_rejected(self):
        """La longueur d'une liste ne doit jamais révéler son origine (story 19, ticket #8)."""
        blind_draw = load_eval("blind_draw")
        corpus = load_corpus_from_videos([
            make_video("s", ["Go"]),
            make_video("b1", ["Go", "Concurrency"]),
            make_video("b2", ["Go", "Channels"]),
            make_video("c1", ["Concurrency", "Pipelines"]),
            make_video("c2", ["Channels", "Patterns"]),
        ])
        lengths = {kind: len(blind_draw._blind_list(corpus, "s", kind)) for kind in KINDS}
        assert len(set(lengths.values())) > 1, "garde-fou : le départ de test est bien inégal"
        assert "s" not in blind_draw.eligible_starts(corpus)
        with pytest.raises(SystemExit, match="longueur"):
            blind_draw.build_protocol(corpus, seed=7, starts=["s"])

    def test_auto_draw_lists_share_length_per_start(self, protocol_corpus):
        """Aucune fuite d'origine par la longueur sur un tirage complet (3 x 5 listes)."""
        blind_draw = load_eval("blind_draw")
        order, mapping = blind_draw.build_protocol(protocol_corpus, seed=20261020, count=5)
        per_start = {}
        for letter, entry in mapping.items():
            per_start.setdefault(entry["start"], []).append(len(order["letters"][letter]["videos"]))
        assert len(per_start) == 5
        for lengths in per_start.values():
            assert len(set(lengths)) == 1, f"longueurs différentes pour un départ : {lengths}"

    def test_writes_order_and_mapping_files(self, protocol_corpus, tmp_path):
        blind_draw = load_eval("blind_draw")
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(json.dumps({"videos": protocol_corpus["videos"]}, ensure_ascii=False), encoding="utf-8")
        order_path = tmp_path / "order.json"
        mapping_path = tmp_path / "mapping.json"
        payload = blind_draw.blind_draw(
            str(corpus_path), seed=7, out_path=str(order_path),
            mapping_path=str(mapping_path), starts=STARTS,
        )
        assert payload == json.loads(order_path.read_text(encoding="utf-8"))
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        assert sorted(mapping) == sorted(payload["letters"])


class TestRecordScores:
    def order_fixture(self):
        return {
            "order": ["A", "B"],
            "letters": {
                "A": {"start": "v1", "videos": [{"id": "v2", "title": "Vidéo v2"}]},
                "B": {"start": "v3", "videos": [{"id": "v2", "title": "Vidéo v2"}]},
            },
        }

    def test_scores_complete_requires_three_criteria(self):
        record_scores = load_eval("record_scores")
        order = self.order_fixture()
        assert record_scores.scores_complete(order, {}) == [
            "A/coherence", "A/surprise", "A/clarte", "B/coherence", "B/surprise", "B/clarte",
        ]
        partial = {"A": {"coherence": 4, "surprise": 3}}
        assert record_scores.scores_complete(order, partial) == ["A/clarte", "B/coherence", "B/surprise", "B/clarte"]
        complete = {
            "A": {"coherence": 4, "surprise": 3, "clarte": 5},
            "B": {"coherence": 3, "surprise": 4, "clarte": 2},
        }
        assert record_scores.scores_complete(order, complete) == []

    def test_record_scores_three_criteria_blind(self, tmp_path, monkeypatch, capsys):
        record_scores = load_eval("record_scores")
        order = self.order_fixture()
        scores_path = tmp_path / "scores.json"
        entries = iter(["A 4 3 5", "x", "B 3 4 2", "q"])
        monkeypatch.setattr("builtins.input", lambda _: next(entries))
        record_scores.record(scores_path, order)
        saved = json.loads(scores_path.read_text(encoding="utf-8"))
        assert saved == {
            "A": {"coherence": 4, "surprise": 3, "clarte": 5},
            "B": {"coherence": 3, "surprise": 4, "clarte": 2},
        }
        shown = capsys.readouterr().out
        assert "départ" in shown
        for leak in LEAK_STRINGS:
            assert leak not in shown.lower()

    def test_presentations_shows_blind_material(self):
        blind_draw = load_eval("blind_draw")
        order = {
            "order": ["A"],
            "letters": {"A": {"start": "v1", "videos": [{"id": "v2", "title": "Vidéo v2"}]}},
        }
        text = blind_draw.present(order)
        assert "Liste A" in text
        assert "Vidéo v2" in text


class TestReveal:
    def write_inputs(self, tmp_path, letters, mapping, scores):
        order = {
            "order": sorted(letters),
            "letters": {letter: {"start": "v1", "videos": [{"id": "v2", "title": "Vidéo v2"}]} for letter in letters},
        }
        order_path = tmp_path / "order.json"
        mapping_path = tmp_path / "mapping.json"
        scores_path = tmp_path / "scores.json"
        order_path.write_text(json.dumps(order, ensure_ascii=False), encoding="utf-8")
        mapping_path.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
        scores_path.write_text(json.dumps(scores, ensure_ascii=False), encoding="utf-8")
        return str(order_path), str(scores_path), str(mapping_path)

    def test_refuses_incomplete_scoring_including_clarte(self, tmp_path):
        reveal = load_eval("reveal")
        mapping = {"A": {"start": "v1", "origine": "baseline"}, "B": {"start": "v1", "origine": "decouvrir"}}
        scores = {"A": {"coherence": 4, "surprise": 2, "clarte": 5},
                  "B": {"coherence": 4, "surprise": 4}}
        paths = self.write_inputs(tmp_path, ["A", "B"], mapping, scores)
        with pytest.raises(SystemExit, match="clarte"):
            reveal.reveal(*paths)

    def test_refuses_scoring_not_yet_started(self, tmp_path):
        """Révélation lancée avant toute notation : refus propre, pas de traceback."""
        reveal = load_eval("reveal")
        mapping = {"A": {"start": "v1", "origine": "baseline"}, "B": {"start": "v1", "origine": "decouvrir"}}
        order = {
            "order": ["A", "B"],
            "letters": {letter: {"start": "v1", "videos": [{"id": "v2", "title": "Vidéo v2"}]} for letter in "AB"},
        }
        tmp_path.joinpath("order.json").write_text(json.dumps(order, ensure_ascii=False), encoding="utf-8")
        tmp_path.joinpath("mapping.json").write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(SystemExit, match="notation incomplète"):
            reveal.reveal(str(tmp_path / "order.json"), str(tmp_path / "scores.json"),
                          str(tmp_path / "mapping.json"))

    def test_decision_go(self, tmp_path):
        reveal = load_eval("reveal")
        mapping = {
            "A": {"start": "v1", "origine": "baseline"},
            "B": {"start": "v1", "origine": "approfondir"},
            "C": {"start": "v2", "origine": "baseline"},
            "D": {"start": "v2", "origine": "approfondir"},
            "E": {"start": "v1", "origine": "decouvrir"},
            "F": {"start": "v2", "origine": "decouvrir"},
        }
        scores = {
            "A": {"coherence": 4, "surprise": 2, "clarte": 3},
            "B": {"coherence": 4, "surprise": 3, "clarte": 3},
            "C": {"coherence": 4, "surprise": 2, "clarte": 3},
            "D": {"coherence": 4, "surprise": 3, "clarte": 3},
            "E": {"coherence": 4, "surprise": 4, "clarte": 5},
            "F": {"coherence": 4, "surprise": 4, "clarte": 5},
        }
        paths = self.write_inputs(tmp_path, sorted(mapping), mapping, scores)
        result = reveal.reveal(*paths)
        assert result["marge_surprise"] == 2.0
        assert result["decision"].startswith("GO")
        assert result["seuil"]["adr"] == "docs/adr/0001-seuil-go-no-go-pre-engage.md"
        for kind in KINDS:
            assert kind in result["moyennes"]["clarte"]
            assert kind in result["moyennes"]["coherence"]
        assert result["moyennes"]["clarte"]["decouvrir"] == 5.0

    def test_decision_no_go_on_surprise_margin(self, tmp_path):
        reveal = load_eval("reveal")
        mapping = {
            "A": {"start": "v1", "origine": "baseline"},
            "B": {"start": "v1", "origine": "approfondir"},
            "C": {"start": "v1", "origine": "decouvrir"},
        }
        scores = {
            "A": {"coherence": 4, "surprise": 3, "clarte": 3},
            "B": {"coherence": 4, "surprise": 3, "clarte": 3},
            "C": {"coherence": 4, "surprise": 3, "clarte": 3},
        }
        paths = self.write_inputs(tmp_path, ["A", "B", "C"], mapping, scores)
        result = reveal.reveal(*paths)
        assert result["marge_surprise"] == 0.0
        assert result["decision"].startswith("NO-GO")

    def test_decision_no_go_on_coherence_loss(self, tmp_path):
        reveal = load_eval("reveal")
        mapping = {
            "A": {"start": "v1", "origine": "baseline"},
            "B": {"start": "v1", "origine": "approfondir"},
            "C": {"start": "v1", "origine": "decouvrir"},
        }
        scores = {
            "A": {"coherence": 4, "surprise": 2, "clarte": 3},
            "B": {"coherence": 4, "surprise": 3, "clarte": 3},
            "C": {"coherence": 3, "surprise": 5, "clarte": 3},
        }
        paths = self.write_inputs(tmp_path, ["A", "B", "C"], mapping, scores)
        result = reveal.reveal(*paths)
        assert result["marge_surprise"] == 3.0
        assert result["decision"].startswith("NO-GO")


class TestEndToEndRealCorpus:
    def test_full_cycle_produces_go_no_go_decision(self, tmp_path, monkeypatch):
        blind_draw = load_eval("blind_draw")
        record_scores = load_eval("record_scores")
        reveal = load_eval("reveal")

        order_path = tmp_path / "order.json"
        mapping_path = tmp_path / "mapping.json"
        scores_path = tmp_path / "scores.json"
        decision_path = tmp_path / "decision.json"

        blind_draw.blind_draw(
            str(REAL_CORPUS), seed=20261020,
            out_path=str(order_path), mapping_path=str(mapping_path), count=5,
        )
        order = json.loads(order_path.read_text(encoding="utf-8"))
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        assert len(order["letters"]) == 15
        assert len(order["starts"]) == 5

        scripted = iter(
            [f"{letter} 4 3 4" for letter in order["order"]] + ["q"]
        )
        monkeypatch.setattr("builtins.input", lambda _: next(scripted))
        record_scores.record(scores_path, order)
        assert record_scores.scores_complete(order, json.loads(scores_path.read_text(encoding="utf-8"))) == []

        result = reveal.reveal(str(order_path), str(scores_path), str(mapping_path))
        decision_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert result["decision"].startswith(("GO", "NO-GO"))
        assert result["marge_surprise"] == 0.0
        assert result["moyennes"]["clarte"]["baseline"] == 4.0
        for kind in KINDS:
            per_start = [e for e in mapping.values() if e["origine"] == kind]
            assert len(per_start) == 5
