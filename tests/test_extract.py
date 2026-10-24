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


def install_fake_gemini(monkeypatch, script: dict[str, object]) -> list[int]:
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
