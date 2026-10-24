"""Extraction Gemini : testée via un faux SDK, sans réseau ni vraie clé API.

Le seam public est la sous-commande CLI `extract` (vte.cli.main) ; le SDK
`google.generativeai` est remplacé par un faux module injecté dans sys.modules.
GEMINI_API_KEY reçoit une valeur factice : aucune clé réelle n'est requise.
"""

import json
import sys
import types
from pathlib import Path

from vte.cli import main
from vte.corpus import load_corpus

FIXTURE_RAW = Path(__file__).resolve().parent / "fixtures" / "videos_raw_extract.json"
MODEL = "gemini-1.5-flash"
MODEL_VERSION = "gemini-1.5-flash-002"


class FakeResponse:
    def __init__(self, text: str, model_version: str):
        self.text = text
        self.model_version = model_version


class FakeGenerativeModel:
    """Retourne des réponses scriptées par titre de vidéo ; compte les appels."""

    def __init__(self, name: str, script: dict[str, object], counter: list[int]):
        self.name = name
        self.script = script
        self.counter = counter

    def generate_content(self, prompt: str) -> FakeResponse:
        self.counter[0] += 1
        for title, payload in self.script.items():
            if f"Titre : {title}" in prompt:
                if isinstance(payload, Exception):
                    raise payload
                return FakeResponse(payload, MODEL_VERSION)
        raise AssertionError(f"prompt inattendu : {prompt!r}")


def install_fake_gemini(monkeypatch, script: dict[str, object], *, set_key: bool = True) -> list[int]:
    """Injecte le faux SDK ; renvoie le compteur d'appels (à une case)."""
    counter = [0]
    fake = types.ModuleType("google.generativeai")

    def configure(api_key: str | None = None) -> None:
        fake.configured_key = api_key

    def make_model(name: str) -> FakeGenerativeModel:
        return FakeGenerativeModel(name, script, counter)

    fake.configure = configure
    fake.GenerativeModel = make_model
    monkeypatch.setitem(sys.modules, "google", types.ModuleType("google"))
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    if set_key:
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key-tests")
    return counter


def topics_payload(*labels: str) -> str:
    return json.dumps(
        [{"raw": label, "justification": f"justification factice : {label}"} for label in labels],
        ensure_ascii=False,
    )


def test_extract_enriches_corpus_with_real_provenance(monkeypatch, tmp_path):
    """Démo du ticket : quelques vidéos saisies à la main -> corpus enrichi.

    La provenance doit porter la version réelle du modèle rapportée par la
    réponse API, jamais la chaîne littérale « cached ».
    """
    counter = install_fake_gemini(monkeypatch, {
        "Roslyn sous le capot": topics_payload("C Sharp", "Roslyn", "Compilateurs"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Compilateurs", "Optimisation"),
    })
    out = tmp_path / "corpus.json"

    rc = main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL])

    assert rc == 0
    assert counter[0] == 2
    corpus = load_corpus(out)
    assert len(corpus["videos"]) == 2
    for video in corpus["videos"]:
        topics = video["topics"]
        assert 3 <= len(topics) <= 5
        for topic in topics:
            assert topic["justification"]
            provenance = topic["provenance"]
            assert provenance["source"] == "gemini"
            assert provenance["model"] == MODEL
            assert provenance["version"] == MODEL_VERSION
            assert provenance["version"] != "cached"


def test_extract_normalizes_alias_end_to_end(monkeypatch, tmp_path):
    """« C Sharp » -> « C# » : libellé brut conservé, canonique fusionné,
    à travers le chemin complet de l'extracteur (réponse brute -> corpus)."""
    install_fake_gemini(monkeypatch, {
        "Roslyn sous le capot": topics_payload("C Sharp", "Roslyn", "Compilateurs"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Compilateurs", "Optimisation"),
    })
    out = tmp_path / "corpus.json"

    rc = main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL])

    assert rc == 0
    corpus = load_corpus(out)
    by_id = {v["id"]: v for v in corpus["videos"]}
    aliases = {t["raw"]: t["canonical"] for t in by_id["aa11bb22cc33"]["topics"]}
    assert aliases["C Sharp"] == "C#"
    aliases = {t["raw"]: t["canonical"] for t in by_id["dd44ee55ff66"]["topics"]}
    assert aliases["LLVM IR"] == "LLVM"
    # load_corpus revalide la cohérence raw/canonical : le corpus reste chargeable.


def test_extract_cache_never_recalls_an_extracted_video(monkeypatch, tmp_path):
    """AC cache : une vidéo déjà extraite ne déclenche jamais de nouvel appel.

    Second run sur le même corpus : zéro appel Gemini supplémentaire,
    et la provenance d'origine est conservée telle quelle.
    """
    script = {
        "Roslyn sous le capot": topics_payload("C Sharp", "Roslyn", "Compilateurs"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Compilateurs", "Optimisation"),
    }
    counter = install_fake_gemini(monkeypatch, script)
    out = tmp_path / "corpus.json"

    assert main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL]) == 0
    assert counter[0] == 2
    before = json.loads(out.read_text(encoding="utf-8"))

    assert main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL]) == 0
    assert counter[0] == 2  # aucun nouvel appel Gemini
    assert json.loads(out.read_text(encoding="utf-8")) == before  # provenance d'origine intacte


def test_extract_out_of_range_count_is_flagged_not_accepted(monkeypatch, tmp_path, capsys):
    """AC 3-5 sujets : un compte hors plage est enregistré/flaggé dans le
    corpus (extraction_error), jamais accepté en silence ; le batch continue."""
    counter = install_fake_gemini(monkeypatch, {
        "Roslyn sous le capot": topics_payload("C Sharp", "Roslyn", "Compilateurs"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Optimisation"),
    })
    out = tmp_path / "corpus.json"

    rc = main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL])

    assert rc == 1  # l'échec est visible dans le code retour
    corpus = load_corpus(out)
    by_id = {v["id"]: v for v in corpus["videos"]}
    assert "topics" not in by_id["dd44ee55ff66"]
    assert "2 sujets extraits" in by_id["dd44ee55ff66"]["extraction_error"]
    # l'autre vidéo est extraite normalement : le batch continue
    assert len(by_id["aa11bb22cc33"]["topics"]) == 3
    assert counter[0] == 2
    assert "dd44ee55ff66" in capsys.readouterr().err  # exception visible sur stderr


def test_extract_api_failure_is_flagged_and_batch_continues(monkeypatch, tmp_path, capsys):
    """Une vidéo dont l'appel échoue est flaggée (extraction_error) avec son
    motif ; les vidéos suivantes du batch sont quand même extraites."""
    counter = install_fake_gemini(monkeypatch, {
        "Roslyn sous le capot": RuntimeError("quota dépassé"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Compilateurs", "Optimisation"),
    })
    out = tmp_path / "corpus.json"

    rc = main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL])

    assert rc == 1
    corpus = load_corpus(out)
    by_id = {v["id"]: v for v in corpus["videos"]}
    assert by_id["aa11bb22cc33"]["extraction_error"] == "quota dépassé"
    assert "topics" not in by_id["aa11bb22cc33"]
    assert len(by_id["dd44ee55ff66"]["topics"]) == 3  # le batch continue
    assert counter[0] == 2
    assert "quota dépassé" in capsys.readouterr().err


def test_extract_flagged_video_is_retried_next_run(monkeypatch, tmp_path):
    """Le cache ne fige que les extractions réussies : une vidéo flaggée
    (extraction_error) n'est pas « déjà extraite » et est réessayée au run suivant."""
    script = {
        "Roslyn sous le capot": topics_payload("C Sharp", "Roslyn", "Compilateurs"),
        "Promenade dans l'optimiseur LLVM": topics_payload("LLVM IR", "Compilateurs", "Optimisation"),
    }
    counter = install_fake_gemini(monkeypatch, dict(script, **{"Roslyn sous le capot": RuntimeError("quota dépassé")}))
    out = tmp_path / "corpus.json"

    assert main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL]) == 1
    assert counter[0] == 2

    # Le faux Gemini « guérit » : la vidéo flaggée est réessayée, l'autre reste cachée.
    counter2 = install_fake_gemini(monkeypatch, script)
    assert main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL]) == 0
    assert counter2[0] == 1  # un seul nouvel appel : la vidéo réussie n'est pas rappelée

    corpus = load_corpus(out)
    by_id = {v["id"]: v for v in corpus["videos"]}
    assert len(by_id["aa11bb22cc33"]["topics"]) == 3
    assert "extraction_error" not in by_id["aa11bb22cc33"]
    assert by_id["aa11bb22cc33"]["topics"][0]["provenance"]["version"] == MODEL_VERSION


def test_extract_requires_gemini_api_key_from_env(monkeypatch, tmp_path, capsys):
    """AC clé API : exclusivement via variable d'environnement — sans clé,
    aucun appel Gemini n'est tenté et le code retour est explicite."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    install_fake_gemini(monkeypatch, {}, set_key=False)
    out = tmp_path / "corpus.json"

    rc = main(["extract", str(FIXTURE_RAW), "--output", str(out), "--model", MODEL])

    assert rc == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err
    assert not out.exists()  # rien n'est écrit sans clé
