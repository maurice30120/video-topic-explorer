"""Chargement et validation du corpus JSON figé.

Le corpus est l'unique source de vérité : vid\éos collect\ées \à la main,
sujets extraits une fois par Gemini (mis en cache), liens et provenance.
Aucun appel LLM n'est effectu\é ici.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Alias \évidents uniquement (d\écision d'impl\émentation de la spec).
# Libell\é brut et libell\é canonique sont conserv\és dans le JSON.
ALIASES: dict[str, str] = {
    "c sharp": "C#",
    "csharp": "C#",
    "rosalyn": "Roslyn",
    "llvm ir": "LLVM",
    "java script": "JavaScript",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
}


class CorpusError(ValueError):
    """Corpus invalide ou incoh\érent."""


def canonical(raw: str) -> str:
    """Normalise un libell\é brut en libell\é canonique (fusion d'alias \évidents)."""
    key = raw.strip()
    if not key:
        raise CorpusError("libellé de sujet vide")
    return ALIASES.get(key.lower(), key)


def load_corpus(path: str | Path) -> dict[str, Any]:
    """Charge et valide un corpus JSON figé.

    Structure attendue::

        {
          "videos": [
            {
              "id": "vid-001",
              "url": "https://www.youtube.com/watch?v=...",
              "title": "...",
              "description": "...",            # optionnel
              "transcript": "...",             # optionnel
              "topics": [                       # 3 \à 5 sujets par vid\éo
                {"raw": "C Sharp", "canonical": "C#",
                 "provenance": {"source": "gemini", "model": "...", "version": "..."}}
              ]
            }
          ]
        }
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    videos = data.get("videos")
    if not isinstance(videos, list) or not videos:
        raise CorpusError("le corpus ne contient aucune vidéo")

    seen_ids: set[str] = set()
    for video in videos:
        vid = video.get("id")
        if not vid or not isinstance(vid, str):
            raise CorpusError("vidéo sans id")
        if vid in seen_ids:
            raise CorpusError(f"vidéo en doublon : {vid}")
        seen_ids.add(vid)
        if not video.get("title"):
            raise CorpusError(f"vidéo sans titre : {vid}")
        topics = video.get("topics", [])
        if not isinstance(topics, list):
            raise CorpusError(f"topics invalides pour {vid}")
        for topic in topics:
            raw = topic.get("raw")
            if not raw:
                raise CorpusError(f"sujet sans libellé brut pour {vid}")
            if topic.get("canonical") != canonical(raw):
                raise CorpusError(
                    f"libellé canonique incohérent pour {vid} : {raw!r}"
                )

    # Un sujet est « mort » s'il n'est porté par aucune vid\éo \à l'exclusion
    # de celle-ci (degré 1 dans le graphe biparti) : il est conserv\é dans le
    # JSON et le graphe visuel, mais exclu des candidats de parcours.
    topic_counts: dict[str, int] = {}
    for video in videos:
        for topic in video.get("topics", []):
            topic_counts[topic["canonical"]] = (
                topic_counts.get(topic["canonical"], 0) + 1
            )
    data["dead_topics"] = sorted(
        topic for topic, count in topic_counts.items() if count < 2
    )
    return data


def videos_by_id(corpus: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {video["id"]: video for video in corpus["videos"]}


def topics_of(video: dict[str, Any]) -> set[str]:
    return {topic["canonical"] for topic in video.get("topics", [])}
