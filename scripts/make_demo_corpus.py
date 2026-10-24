"""Corpus fictif (8 vidéos) pour tests et démos manuelles (ticket #3).

Les métadonnées sont fictives : aucune donnée de visionnage personnelle,
aucune clé API. Les sujets simulent une extraction Gemini figée, avec :
- un alias évident normalisé (« C Sharp » -> « C# », libellé brut conservé) ;
- des sujets morts (portés par une seule vidéo), dont une vidéo isolée ;
- la provenance (source, modèle, version) de chaque extraction.

Régénérer :  python3 scripts/make_demo_corpus.py
Stats :      python3 -m vte.cli stats data/corpus_demo.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vte.corpus import canonical

VIDEOS = [
    # Cluster .NET/compilateurs : « C Sharp » fusionne avec « C# » par alias.
    (["C Sharp", ".NET", "Roslyn"], "Écrire du C Sharp moderne sur .NET"),
    (["C#", ".NET", "Roslyn"], "C# et Roslyn : le compilateur comme service"),
    (["Roslyn", "Compilateurs", "Parsing"], "Comment Roslyn parse votre code"),
    # Vidéo pont vers le cluster Rust.
    (["Compilateurs", "LLVM", "Optimisation"], "Compilateurs et optimisation : le rôle de LLVM"),
    # Cluster Rust/systèmes ; « Histoire de l'informatique » est un sujet mort.
    (["Rust", "LLVM", "Sécurité mémoire"], "Rust, un compilateur plus sûr sur LLVM"),
    (["Rust", "Systèmes", "Sécurité mémoire"], "Rust dans les systèmes : sécurité mémoire"),
    (["Rust", "Systèmes", "Histoire de l'informatique"], "Rust et systèmes : une brève histoire"),
    # Vidéo isolée : ses sujets ne relient aucune autre vidéo (sujets morts).
    (["Poterie", "Tournage", "Artisanat"], "Tournage de poterie : l'artisanat au tour"),
]


def build_corpus() -> dict:
    videos = []
    for vid, (topics, title) in enumerate(VIDEOS, start=1):
        videos.append({
            "id": f"vid-{vid:03d}",
            "url": f"https://www.youtube.com/watch?v=demo{vid:03d}",
            "title": title,
            "description": f"Vidéo de démonstration fictive n°{vid} sur : {', '.join(topics)}.",
            "topics": [
                {
                    "raw": raw,
                    "canonical": canonical(raw),
                    "justification": f"mentionné explicitement dans le titre/description (démo {vid:03d})",
                    "provenance": {"source": "gemini", "model": "demo-fixture", "version": "cached"},
                }
                for raw in topics
            ],
        })
    return {"videos": videos}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "corpus_demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus = build_corpus()
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"corpus démo : {out} ({len(corpus['videos'])} vidéos)")
