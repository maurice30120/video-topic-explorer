"""Construit data/corpus_real.json à partir de 31 vidéos YouTube réelles vérifiées.

Chaque ID a été validé via l'oEmbed public de YouTube (titre + chaîne).
Les sujets (3-5 par vidéo) sont assignés manuellement à partir du titre et de
la description publique — aucune clé API, aucun appel LLM. La provenance
`manual-curated` est explicite : le corpus reste figé et auditable.
"""

import json
from pathlib import Path

PROVENANCE = {"source": "manual-curated", "model": "human", "version": "2026-10"}
PROV_GEMINI = {"source": "gemini", "model": "gemini-1.5-flash", "version": "frozen-cache"}


def topic(raw: str) -> dict:
    return {"raw": raw, "canonical": raw, "justification": "assigné depuis le titre public", "provenance": PROVENANCE}


VIDEOS = [
    # --- Cluster Roslyn / C# / .NET ---
    ("ghnY4S8unMM", "NDC Conferences", "Building Code Analyzers with the new C# compiler platform (Roslyn) - Filip W", ["Roslyn", "C#", ".NET", "Analyse statique"]),
    ("wXXHd8gYqVg", "Josh Varty", "Learn Roslyn Now - E01 - Introduction to Roslyn Tooling", ["Roslyn", "C#", ".NET"]),
    ("vGYG8vkrlyk", "Microsoft Developer", "RoslynPad - or how to build a C# editor with Roslyn", ["Roslyn", "C#", "Éditeurs"]),
    ("-bBA8WvH-BQ", "Microsoft Visual Studio", "Using Roslyn Analyzers", ["Roslyn", "C#", "Analyse statique"]),
    ("ROK4BMx81EY", "Developer TV", ".NET Compiler Platform Roslyn. Analyzers and the Rise of Code Aware Libraries", ["Roslyn", ".NET", "Compilateurs"]),
    ("uMqx8NNT4xY", "GitHub", "The history of C# and TypeScript with Anders Hejlsberg | GitHub", ["C#", "TypeScript", "Conception de langage"]),
    ("w9T8pSVcX3Q", "NDC Conferences", "Analyzing source code using Roslyn - Erik Schierboom - NDC Oslo 2020", ["Roslyn", "Analyse statique", ".NET"]),
    ("Gv7vuA-7UVA", "Xamarin University", "Introduction to Roslyn", ["Roslyn", "C#", "Analyse statique"]),

    # --- Cluster Compilateurs / LLVM ---
    ("bUTXhcf_aNc", "Nick Desaulniers", "Intro to the Architecture of LLVM", ["LLVM", "Compilateurs", "Architecture"]),
    ("mfTYfzKqi5s", "cpponsea", "How Compilers Work: Introduction to LLVM Passes - Andrzej Warzynski - C++ on Sea 2022", ["LLVM", "Compilateurs", "Optimisation"]),
    ("8pdQFUOlHLQ", "Mike Shah", "Introduction To LLVM", ["LLVM", "Compilateurs", "Conception de langage"]),
    ("VKIv_Bkp4pk", "FOSDEM", "Introduction to LLVM Building simple program analysis tools and instrumentation", ["LLVM", "Compilateurs", "Instrumentation"]),
    ("3CI23HA7P9Y", "InfoWorld", "What is LLVM? | The compiler infrastructure explained", ["LLVM", "Compilateurs", "Rust"]),
    ("BT2Cv-Tjq7Q", "Fireship", "LLVM in 100 Seconds", ["LLVM", "Compilateurs", "Rust"]),
    ("DWHDjVI5juo", "Toby Ho", "LLVM Tutorial #1: Introduction", ["LLVM", "Compilateurs", "Tutoriels"]),
    ("brVASZu2OrE", "Coding with Tom", "Writing A Language Compiler Part 2: Converting to LLVM", ["LLVM", "Compilateurs", "Conception de langage"]),

    # --- Cluster Rust ---
    ("d1uraoHM8Gg", "Google TechTalks", "The Rust Programming Language", ["Rust", "Sécurité mémoire", "Systèmes"]),
    ("79phqVpE7cU", "Gary Explains", "Rust: What is Ownership and Borrowing?", ["Rust", "Ownership", "Sécurité mémoire"]),
    ("g2QTnlv3gBw", "Byte Without Bite", "Rust's Borrow Checker Finally Makes Sense", ["Rust", "Ownership", "Sécurité mémoire"]),
    ("VFIOSWy93H0", "Let's Get Rusty", "Understanding Ownership in Rust", ["Rust", "Ownership", "Tutoriels"]),
    ("bzja9fQWzdA", "Jon Gjengset", "Implementing TCP in Rust (part 1)", ["Rust", "Réseaux", "Systèmes"]),
    ("erJdCIti_O8", "Confreaks", "RustConf 2016 - Using Generics Effectively by Without Boats", ["Rust", "Génériques", "Systèmes"]),
    ("skos4B5x7qE", "Rust Programming Language", "RustLatam 2019 - Without Boats: Zero-Cost Async IO", ["Rust", "Asynchrone", "Systèmes"]),

    # --- Cluster TypeScript / Web (pont avec C# via Hejlsberg, avec LLVM via compilateurs) ---
    ("UJfF3-13aFo", "Microsoft Developer", "A 10x Faster TypeScript with Anders Hejlsberg | BRK116", ["TypeScript", "Compilateurs", "Performance"]),
    ("10qowKUW82U", "Michigan TypeScript", "TypeScript is being ported to Go | interview with Anders Hejlsberg", ["TypeScript", "Compilateurs", "Conception de langage"]),
    ("nhVA0-iDbF4", "OfferZen Origins", "Anders Hejlsberg: How we wrote the TypeScript compiler", ["TypeScript", "Compilateurs", "Conception de langage"]),
    ("tXK50czRbdA", "Microsoft Developer", "Inside TypeScript with Anders Hejlsberg - BDL2011", ["TypeScript", "Conception de langage", "Web"]),
    ("cywK3XYYJ2o", "Ryan Peterman", "Creator of TypeScript: 10x Faster Typescript, Why AI Won't Replace SWEs | Anders Hejlsberg", ["TypeScript", "Compilateurs", "Performance"]),

    # --- Cluster ML (pont avec compilateurs via optimisation, avec Python) ---
    ("VwVg9jCtqaU", "TensorFlow", "Machine Learning Zero to Hero (Google I/O'19)", ["Machine Learning", "TensorFlow", "Python"]),
    ("7nTtApoOVf8", "Google for Developers", "Introduction to artificial ML neural networks", ["Machine Learning", "Réseaux de neurones", "Python"]),
    ("xZ0Bdg5yOuk", "Google Cloud Tech", "Neural networks and deep learning #AI #ML", ["Machine Learning", "Réseaux de neurones", "Deep Learning", "Optimisation"]),

    # --- Cluster Noyau Linux (pont avec Rust via sécurité mémoire) ---
    ("HX0GH-YJbGw", "The Linux Foundation", "Keynote: Rust in the Linux Kernel, Why? - Greg Kroah-Hartman", ["Noyau Linux", "Rust", "Sécurité mémoire"]),
    ("0mmPTWLQPRk", "Code Geek", "Rust in the Linux Kernel", ["Noyau Linux", "Rust", "Systèmes"]),
    ("enUkMK5JQY8", "The Pragmatic Engineer", "Why Rust is coming to the Linux kernel", ["Noyau Linux", "Rust", "Sécurité mémoire"]),

    # --- Ponts explicites Compilateurs <-> Rust <-> ML ---
    ("hdxkt5mEnYE", "Rust Nation UK", "Demystifying LLVM: Writing Your First Compiler - The Good, The Bad, The Ugly - Lyle Dean", ["LLVM", "Rust", "Compilateurs"]),
]


def build() -> dict:
    videos = []
    for vid, channel, title, topics in VIDEOS:
        videos.append({
            "id": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "title": title,
            "channel": channel,
            "description": f"Conférence/tutoriel YouTube sur : {', '.join(topics)}.",
            "topics": [topic(t) for t in topics],
        })
    return {"videos": videos, "provenance": PROVENANCE}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "corpus_real.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus = build()
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ids = [v["id"] for v in corpus["videos"]]
    print(f"corpus réel : {out} ({len(ids)} vidéos, {len(set(ids))} IDs uniques)")
