"""Corpus fictif (~30 vidéos, ~6 clusters + ponts) pour tests et démos manuelles.

Les métadonnées sont fictives : aucune donnée de visionnage personnelle,
aucune clé API. Les sujets simulent une extraction Gemini figée.
"""

import json
from pathlib import Path

CLUSTERS = {
    "dotnet": (["C#", ".NET", "Roslyn", "Compilateurs", "Visual Studio"], 5),
    "compilateurs": (["Compilateurs", "LLVM", "Roslyn", "Optimisation", "Parsing"], 5),
    "rust": (["Rust", "Sécurité mémoire", "LLVM", "Systèmes", "Ownership"], 5),
    "web": (["JavaScript", "TypeScript", "React", "Node.js", "Web"], 5),
    "ml": (["Machine Learning", "Python", "TensorFlow", "Réseaux de neurones", "Data Science"], 5),
    "sys": (["Systèmes", "Linux", "Noyau", "Sécurité mémoire", "Rust"], 4),
}

BRIDGES = [
    (["Roslyn", "Compilateurs", "C#"], "Roslyn et les compilateurs .NET"),
    (["LLVM", "Rust", "Optimisation"], "LLVM, le dos de Rust"),
    (["TypeScript", "Compilateurs", "Parsing"], "Le compilateur TypeScript"),
    (["Python", "Machine Learning", "Web"], "Servir du ML sur le Web"),
    (["Rust", "Systèmes", "Noyau"], "Rust dans le noyau Linux"),
    (["Machine Learning", "Optimisation", "Compilateurs"], "Compilateurs et ML : optimisation automatique"),
]


def build_corpus() -> dict:
    videos = []
    vid = 0

    def add(topics, title):
        nonlocal vid
        vid += 1
        videos.append({
            "id": f"vid-{vid:03d}",
            "url": f"https://www.youtube.com/watch?v=demo{vid:03d}",
            "title": f"{title} (démo {vid:03d})",
            "description": f"Vidéo de démonstration fictive n°{vid} sur : {', '.join(topics)}.",
            "topics": [
                {
                    "raw": t,
                    "canonical": t,
                    "justification": f"mentionné explicitement dans le titre/description (démo {vid:03d})",
                    "provenance": {"source": "gemini", "model": "demo-fixture", "version": "cached"},
                }
                for t in topics
            ],
        })

    for name, (topics, count) in CLUSTERS.items():
        for i in range(count):
            rotated = topics[i % len(topics):] + topics[: i % len(topics)]
            add(rotated[:4], f"{name} — {topics[i % len(topics)]}")
    for topics, title in BRIDGES:
        add(topics, title)

    return {"videos": videos}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "corpus_demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_corpus(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"corpus démo : {out} ({len(build_corpus()['videos'])} vidéos)")
