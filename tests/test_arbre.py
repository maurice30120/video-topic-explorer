"""Parcours dans l'arbre étoffé (data/corpus_arbre.json) : 19 branches × 4 vidéos + 20 ponts.

Vérifie le cœur du produit (GLOSSARY) sur un corpus riche :
- chaque vidéo regardée oriente la suivante : la transition part d'un sujet
  de la vidéo visionnée et aboutit à un sujet de la suivante, par un chemin
  de sujets réel présent dans le corpus ;
- le saut de branche est systématique : une branche de 4 vidéos s'épuise
  avant les 5 vidéos du parcours, la chaîne traverse donc un pont ;
- le parcours reste intéressant : complet, sans doublon, et l'union des
  parcours couvre tout l'arbre.

Le corpus est figé (version arbre-2026-10) : ces tests caractérisent le
comportement attendu du moteur sur cette topologie, sans réseau ni LLM.
"""

import json
from pathlib import Path

import pytest

from vte import graph_engine
from vte.corpus import load_corpus, topics_of

ARBRE_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_arbre.json"

# Sujets cœur : chaque branche de l'arbre porte un sujet cœur unique,
# présent sur toutes ses vidéos. Source de vérité indépendante : la
# conception du corpus (scripts/make_arbre_corpus.py), pas le moteur.
CORES = {
    "ro": "Roslyn",
    "co": "Compilateurs",
    "ru": "Rust",
    "ts": "TypeScript",
    "ml": "Machine Learning",
    "nx": "Noyau Linux",
    "as": "Asynchrone",
    "ar": "Architecture",
    "se": "Sécurité",
    "ba": "Bases de données",
    "we": "Accessibilité",
    "gp": "Graphisme",
    "ed": "Éditeurs",
    "te": "Tests",
    "mu": "Musique",
    "fu": "Fun",
    "sc": "Science",
    "ma": "Mathématiques",
    "ci": "Cuisine",
}
CORE_TOPICS = set(CORES.values())

# Ponts surprenants : des paires de branches qu'on n'attend pas voisines.
SURPRISE_BRIDGES = {
    ("Musique", "Mathématiques"),
    ("Science", "Musique"),
    ("Cuisine", "Science"),
    ("Fun", "Graphisme"),
    ("Machine Learning", "Science"),
    ("Mathématiques", "Tests"),
}


@pytest.fixture(scope="module")
def arbre() -> dict:
    return load_corpus(ARBRE_CORPUS)


def branches_of(arbre: dict, video: dict) -> set[str]:
    """Branches d'une vidéo : les sujets cœur qu'elle porte (les ponts en portent deux)."""
    return topics_of(video) & CORE_TOPICS


def cooccurs(arbre: dict, first: str, second: str) -> bool:
    """Deux sujets co-occurrent-ils sur une vraie vidéo du corpus ?"""
    return any(first in topics_of(v) and second in topics_of(v) for v in arbre["videos"])


def test_arbre_etoffe_connexe_branches_vivantes(arbre):
    """96 vidéos, une seule composante connectée, chaque sujet cœur relie au moins deux vidéos."""
    assert len(arbre["videos"]) >= 96
    stats = graph_engine.graph_stats(arbre)
    assert stats["components"] == 1
    for core in CORE_TOPICS:
        assert core in stats["linking_topics"], f"sujet cœur mort : {core}"


def test_ponts_surprenants_presents(arbre):
    """L'arbre réserve des surprises : des branches éloignées se touchent par un pont
    (Musique × Mathématiques, Cuisine × Science, Fun × Graphisme…)."""
    for first, second in SURPRISE_BRIDGES:
        touches = any(
            first in topics_of(v) and second in topics_of(v) for v in arbre["videos"]
        )
        assert touches, f"pont surprenant absent : {first} × {second}"


@pytest.mark.parametrize("mode", ["decouvrir", "approfondir"])
def test_parcours_complet_sans_doublon_depuis_chaque_depart(arbre, mode):
    """Quel que soit le départ (les 69 vidéos), le parcours aboutit : 5 vidéos distinctes."""
    for video in arbre["videos"]:
        run = graph_engine.parcours(arbre, video["id"], mode)
        assert run.complete, f"{video['id']} ({mode}) : {run.reason}"
        assert run.videos[0] == video["id"]
        assert len(run.videos) == graph_engine.MAX_PATH
        assert len(set(run.videos)) == len(run.videos)


@pytest.mark.parametrize("mode", ["decouvrir", "approfondir"])
def test_le_visionnage_oriente_la_suivante(arbre, mode):
    """Chaque transition part d'un sujet de la vidéo regardée, aboutit à un sujet
    de la suivante, et le chemin est réel : deux sujets consécutifs co-occurrent
    sur une vidéo du corpus (vérifié dans le JSON, pas par le moteur)."""
    for video in arbre["videos"]:
        run = graph_engine.parcours(arbre, video["id"], mode)
        by_id = {v["id"]: v for v in arbre["videos"]}
        for step in run.transitions:
            watched = by_id[step["from"]]
            watched_topics = topics_of(watched)
            next_topics = topics_of(by_id[step["to"]])
            path = step["topic_path"]
            assert path[0] in watched_topics, f"{step['from']} → {step['to']} : départ hors sujet regardé"
            assert path[-1] in next_topics, f"{step['from']} → {step['to']} : arrivée hors sujet suivant"
            for first, second in zip(path, path[1:]):
                assert cooccurs(arbre, first, second), f"chemin irréel : {first} → {second}"


@pytest.mark.parametrize("mode", ["decouvrir", "approfondir"])
def test_saut_de_branche_systematique(arbre, mode):
    """Une branche de 4 vidéos s'épuise avant les 5 du parcours : chaque chaîne
    traverse un pont et visite au moins deux branches, quel que soit le départ."""
    by_id = {v["id"]: v for v in arbre["videos"]}
    for video in arbre["videos"]:
        run = graph_engine.parcours(arbre, video["id"], mode)
        visited = set()
        for vid in run.videos:
            visited |= branches_of(arbre, by_id[vid])
        assert len(visited) >= 2, f"{video['id']} ({mode}) : jamais de saut de branche ({run.videos})"


@pytest.mark.parametrize("mode", ["decouvrir", "approfondir"])
def test_l_arbre_entier_est_exploite(arbre, mode):
    """Parcours intéressant : en partant de partout, l'union des chaînes couvre les 14 branches."""
    visited = set()
    for video in arbre["videos"]:
        run = graph_engine.parcours(arbre, video["id"], mode)
        for vid in run.videos:
            by_id = {v["id"]: v for v in arbre["videos"]}
            visited |= branches_of(arbre, by_id[vid])
    assert visited == CORE_TOPICS, f"branches jamais visitées : {CORE_TOPICS - visited}"


def test_parcours_deterministe(arbre):
    """Le même visionnage oriente toujours la même suite : deux runs identiques."""
    run1 = graph_engine.parcours(arbre, "vid-ro-001", "decouvrir")
    run2 = graph_engine.parcours(arbre, "vid-ro-001", "decouvrir")
    assert run1.videos == run2.videos
    assert [t["topic_path"] for t in run1.transitions] == [t["topic_path"] for t in run2.transitions]


def test_corpus_arbre_json_figé_coherent_avec_le_moteur():
    """Le fichier est auto-cohérent : sujets morts déclarés = sujets portés par une seule vidéo."""
    corpus = json.loads(ARBRE_CORPUS.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for video in corpus["videos"]:
        for topic in video["topics"]:
            counts[topic["canonical"]] = counts.get(topic["canonical"], 0) + 1
    dead = set(corpus.get("dead_topics", ()))
    assert dead == {t for t, n in counts.items() if n < 2}
