"""Fixtures : corpus JSON figés de test, sans Gemini, sans UI, sans réseau."""

import json
from pathlib import Path

import pytest

from vte.corpus import load_corpus

def make_topic(label: str) -> dict:
    return {"raw": label, "canonical": label, "justification": "fixture",
            "provenance": {"source": "fixture", "model": "test", "version": "0"}}


def make_video(vid: str, topics: list[str], title: str | None = None) -> dict:
    return {
        "id": vid,
        "url": f"https://www.youtube.com/watch?v=x{vid}",
        "title": title or f"Vidéo {vid}",
        "description": "fixture",
        "topics": [make_topic(t) for t in topics],
    }


@pytest.fixture
def chain_corpus():
    """A → B → C → D en chaîne de sujets, plus une vidéo isolée par sujet mort."""
    return load_corpus_from_videos([
        make_video("a", ["C#", "Roslyn"]),
        make_video("b", ["Roslyn", "Compilateurs"]),
        make_video("c", ["Compilateurs", "LLVM"]),
        make_video("d", ["LLVM", "Rust"]),
        make_video("dead", ["SujetUnique"]),
    ])


@pytest.fixture
def rich_corpus():
    """Clusters reliés pour tester le rayon et le départage d'égalité."""
    return load_corpus_from_videos([
        make_video("v1", ["C#", ".NET", "Roslyn"]),
        make_video("v2", ["C#", ".NET"]),
        make_video("v3", ["C#", "Testing"]),
        make_video("v4", ["Roslyn", "Compilateurs"]),
        make_video("v5", ["Compilateurs", "LLVM"]),
        make_video("v6", ["LLVM", "Rust"]),
        make_video("v7", ["Rust", "Systèmes"]),
        make_video("v8", ["Systèmes", "Linux"]),
        make_video("isolated", ["OrphanTopic"]),
    ])


def load_corpus_from_videos(videos: list[dict]) -> dict:
    return load_corpus_from_dict({"videos": videos})


def load_corpus_from_dict(payload: dict) -> dict:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        path = handle.name
    corpus = load_corpus(path)
    Path(path).unlink()
    return corpus
