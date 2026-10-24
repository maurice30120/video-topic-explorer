"""Corpus fictif « arbre étoffé » (96 vidéos) pour le panneau à rétention (ticket rétention applicative).

19 branches de 4 vidéos + 20 ponts entre branches voisines, y compris des
ponts surprenants (Musique × Mathématiques, Cuisine × Science, Fun ×
Graphisme). Chaque branche porte un sujet cœur unique présent sur toutes ses
vidéos ; chaque pont porte les deux cœurs des branches qu'il relie.
Topologie choisie pour que le comportement du moteur y soit vérifiable :

- une branche de 4 vidéos s'épuise avant les 5 vidéos d'un parcours :
  la chaîne traverse donc toujours un pont (saut de branche) ;
- les sujets spécifiques sont disjoints entre branches : seuls les ponts
  créent des liens inter-branches ;
- chaque sujet spécifique apparaît sur exactement 2 vidéos de sa branche
  (vivant), les cœurs sur 4 + ponts ;
- un sujet mort déclaré : « Histoire de l'informatique » (vid-ru-004).

Les métadonnées sont fictives, sans donnée de visionnage personnelle ni clé
API ; la provenance simule une extraction figée (style corpus démo).

Régénérer :  python3 scripts/make_arbre_corpus.py
Stats :      python3 -m vte.cli stats data/corpus_arbre.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vte.corpus import canonical

# Branche : (clé, sujet cœur, sujets spécifiques — disjoints entre branches).
BRANCHES = [
    ("ro", "Roslyn", ["C#", ".NET", "Analyse statique", "Génériques"]),
    ("co", "Compilateurs", ["LLVM", "Parsing", "IR", "Optimisation"]),
    ("ru", "Rust", ["Ownership", "Sécurité mémoire", "Systèmes", "Performance"]),
    ("ts", "TypeScript", ["JavaScript", "Web", "Typage", "Transpilation"]),
    ("ml", "Machine Learning", ["Deep Learning", "Réseaux de neurones", "TensorFlow", "Python"]),
    ("nx", "Noyau Linux", ["Pilotes", "Réseaux", "Instrumentation", "Ordonnanceur"]),
    ("as", "Asynchrone", ["Concurrence", "Boucle d'événements", "E/S", "Latence"]),
    ("ar", "Architecture", ["Microservices", "Découpage", "Domaines", "Événements"]),
    ("se", "Sécurité", ["Vulnérabilités", "Sandbox", "Chiffrement", "Audit"]),
    ("ba", "Bases de données", ["Requêtes", "Index", "Transactions", "Stockage"]),
    ("we", "Accessibilité", ["ARIA", "Contraste", "Lecteurs d'écran", "Navigation clavier"]),
    ("gp", "Graphisme", ["Rendu", "GPU", "Shaders", "Images"]),
    ("ed", "Éditeurs", ["LSP", "Complétion", "Refactoring", "Extensions"]),
    ("te", "Tests", ["Propriétés", "Mutation", "Couverture", "Fuzzing"]),
    ("mu", "Musique", ["Théorie musicale", "Harmonie", "Synthèse sonore", "Composition"]),
    ("fu", "Fun", ["Humour", "Improvisation", "Jeux", "Parodie"]),
    ("sc", "Science", ["Physique", "Chimie", "Biologie", "Espace"]),
    ("ma", "Mathématiques", ["Topologie", "Algèbre", "Statistiques", "Probabilités"]),
    ("ci", "Cuisine", ["Recettes", "Fermentation", "Techniques de cuisine", "Matériel"]),
]

# Chaîne de ponts couvrant les 19 branches (une seule composante connectée).
# Idée partagée par les deux branches d'un pont, pour des titres plausibles.
BRIDGES = [
    ("ts", "ro", "deux compilateurs au service du développeur"),
    ("ro", "co", "les analyseurs au cœur des compilateurs"),
    ("co", "ru", "un backend de compilateur pour la sécurité mémoire"),
    ("ru", "nx", "écrire des pilotes sûrs pour le noyau"),
    ("nx", "as", "gestion des interruptions et concurrence"),
    ("as", "ar", "architectures événementielles et latence"),
    ("ar", "ba", "le découpage et ses bases de données"),
    ("ba", "te", "des propriétés testables jusqu'au stockage"),
    ("te", "se", "le fuzzing contre les vulnérabilités"),
    ("se", "gp", "calcul et affichage sûrs des images"),
    ("gp", "ed", "le rendu dans l'éditeur"),
    ("ed", "we", "l'accessibilité dans l'outillage"),
    ("we", "ml", "recommandations et accessibilité"),
    ("ml", "sc", "des réseaux de neurones pour les données de physique"),
    ("sc", "mu", "l'acoustique : quand la physique fait de la musique"),
    ("mu", "ma", "le rythme et l'harmonie en fractions"),
    ("ma", "te", "les tests de propriétés : des maths appliquées au code"),
    ("fu", "gp", "jeux vidéo : le fun du rendu"),
    ("fu", "ci", "la cuisine en improvisation : le fun au fourneau"),
    ("ci", "sc", "la chimie de la fermentation"),
]

DEAD_TOPICS = ["Histoire de l'informatique"]


def make_topic(raw: str) -> dict:
    return {
        "raw": raw,
        "canonical": canonical(raw),
        "justification": "assigné depuis le titre fictif (corpus arbre)",
        "provenance": {"source": "gemini", "model": "demo-fixture", "version": "arbre-2026-10"},
    }


def branch_videos() -> list[dict]:
    """4 vidéos par branche : cœur + deux sujets spécififs adjacents (anneau)."""
    videos = []
    for key, core, specs in BRANCHES:
        for i in range(4):
            topics = [core, specs[i], specs[(i + 1) % 4]]
            if key == "ru" and i == 3:
                topics.append(DEAD_TOPICS[0])
            videos.append({
                "id": f"vid-{key}-{i + 1:03d}",
                "url": f"https://www.youtube.com/watch?v=arbre{key}{i + 1}",
                "title": f"{core} : {specs[i]} et {specs[(i + 1) % 4]}",
                "description": f"Vidéo fictive de la branche {core} n°{i + 1} sur : {', '.join(topics)}.",
                "topics": [make_topic(t) for t in topics],
            })
    return videos


def bridge_videos() -> list[dict]:
    """Un pont par paire de branches voisines : les deux cœurs + un spécifique de chaque côté."""
    by_key = {key: (core, specs) for key, core, specs in BRANCHES}
    videos = []
    for n, (key_a, key_b, idea) in enumerate(BRIDGES, start=1):
        core_a, specs_a = by_key[key_a]
        core_b, specs_b = by_key[key_b]
        topics = [core_a, core_b, specs_a[0], specs_b[0]]
        videos.append({
            "id": f"vid-pont-{n:02d}",
            "url": f"https://www.youtube.com/watch?v=arbrepont{n}",
            "title": f"{core_a} × {core_b} : {idea}",
            "description": f"Vidéo fictive pont n°{n} entre {core_a} et {core_b} sur : {', '.join(topics)}.",
            "topics": [make_topic(t) for t in topics],
        })
    return videos


def build_corpus() -> dict:
    return {
        "videos": branch_videos() + bridge_videos(),
        "dead_topics": list(DEAD_TOPICS),
    }


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "corpus_arbre.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    corpus = build_corpus()
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"corpus arbre : {out} ({len(corpus['videos'])} vidéos)")
