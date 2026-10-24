"""Propriétés arbre du parcours sensible à la rétention (spec #27, ticket #32).

Le produit prouvé sur la topologie de référence : les familles exhaustives
du harness passent au vert sur le corpus arbre figé
(data/corpus_arbre.json, version arbre-2026-10 — 19 branches de 4 vidéos
+ 20 ponts, 96 vidéos). Depuis chacun des 96 départs :

- zappeur (chaque durée < 5000 ms) : la session s'éloigne à chaque pas
  (rayon 3) et saute de branche systématiquement — passer vite mène loin ;
- attentif (chaque durée >= 5000 ms) : chaque pas est de rayon 1, la
  chaîne reste dans le voisinage de la branche (same branche ou un pont
  de distance) et s'arrête honnêtement quand le voisinage s'épuise —
  rester approfondit ;
- mixte : le temps cause le comportement — le rayon change à l'exact
  moment du changement de bande de durée ;
- chaque transition de chaque session est co-vérifiée dans le JSON du
  corpus, hors moteur : départ dans les sujets de la carte orientante,
  arrivée dans les sujets de la suivante, chemin réel par
  co-occurrences.

Terminaison propre : une session de l'arbre se termine toujours par une
fin définie du contrat (fin honnête ou garde-fou de 50 pas), sans boucle
ni doublon. Les longues sessions attentives atteignent légitimement le
garde-fou : l'assertion est honnête sur les deux fins, le garde-fou
étant lui-même une terminaison définie — la boucle, elle, est impossible
(les exclusions croissent, jamais de doublon). Les valeurs attendues
viennent de la conception du corpus (scripts/make_arbre_corpus.py) et
du seuil unique du spec (5000 ms) — jamais du moteur.
"""

from pathlib import Path

import pytest

from vte import session
from vte.corpus import load_corpus, topics_of

ARBRE_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_arbre.json"

# Sujets cœur : chaque branche de l'arbre porte un sujet cœur unique,
# présent sur toutes ses vidéos ; les ponts en portent deux. Source de
# vérité indépendante : la conception du corpus
# (scripts/make_arbre_corpus.py), pas le moteur.
CORE_TOPICS = {
    "Roslyn", "Compilateurs", "Rust", "TypeScript", "Machine Learning",
    "Noyau Linux", "Asynchrone", "Architecture", "Sécurité", "Bases de données",
    "Accessibilité", "Graphisme", "Éditeurs", "Tests", "Musique", "Fun",
    "Science", "Mathématiques", "Cuisine",
}

# Le seuil unique du spec #27, celui du panneau — valeur attendue du
# spec, jamais celle du module : 5000 ms, sans bande intermédiaire.
SEUIL_MS = 5000

# Au-delà du garde-fou du contrat de session (50 pas) : chaque session
# doit avoir terminé — fin honnête ou garde-fou — avant l'épuisement du
# profil ; une fin « profil épuisé » serait un bug du balayage.
N_QUITTANCES = 60

PROFILS = {
    # zappeur : toutes les quittances sous le seuil (s'éloigne, rayon 3).
    "zappeur": [1000] * N_QUITTANCES,
    # attentif : toutes les quittances au-dessus du seuil (resserre, rayon 1).
    "attentif": [6000] * N_QUITTANCES,
    # mixte : alternance de part et d'autre du seuil, à chaque quittance.
    "mixte": [6000 if i % 2 == 0 else 1000 for i in range(N_QUITTANCES)],
}


def rayon_attendu(duree: int) -> int:
    """Mapping binaire du spec : durée >= 5000 ms -> rayon 1, sinon rayon 3."""
    return 1 if duree >= SEUIL_MS else 3


@pytest.fixture(scope="module")
def arbre() -> dict:
    return load_corpus(ARBRE_CORPUS)


@pytest.fixture(scope="module")
def by_id(arbre) -> dict:
    return {v["id"]: v for v in arbre["videos"]}


@pytest.fixture(scope="module")
def sessions(arbre) -> dict:
    """Toutes les sessions des balayages, calculées une seule fois :
    (profil, départ) -> session du parcours sensible à la rétention."""
    resultat: dict = {}
    for video in arbre["videos"]:
        for profil, durees in PROFILS.items():
            evenements = [{"duree": d} for d in durees]
            resultat[(profil, video["id"])] = session.deroule(
                arbre, video["id"], evenements
            )
    return resultat


def branches_de(by_id: dict, vid: str) -> set[str]:
    """Branches d'une carte : les sujets cœur qu'elle porte (un pont en porte deux)."""
    return topics_of(by_id[vid]) & CORE_TOPICS


def cooccurs(arbre: dict, first: str, second: str) -> bool:
    """Deux sujets co-occurrent-ils sur une vraie vidéo du corpus ?"""
    return any(first in topics_of(v) and second in topics_of(v) for v in arbre["videos"])


def test_le_corpus_des_proprietes_est_l_arbre_figé(arbre):
    """Les propriétés arbre se prouvent sur la topologie de référence du spec :
    le corpus figé version arbre-2026-10 — 96 vidéos, sujet mort déclaré
    « Histoire de l'informatique » (conception du corpus)."""
    assert len(arbre["videos"]) == 96
    assert arbre["dead_topics"] == ["Histoire de l'informatique"]
    for video in arbre["videos"]:
        for topic in video["topics"]:
            assert topic["provenance"]["version"] == "arbre-2026-10"


def test_zappeur_depuis_chacun_des_96_departs_saut_de_branche_systematique(sessions, by_id):
    """Profil zappeur (tout < seuil) : depuis chacun des 96 départs, chaque pas
    s'éloigne (rayon 3) et la session saute de branche systématiquement —
    elle visite au moins deux branches, au-delà de celles du départ. Une
    branche de 4 vidéos s'épuise sous les exclusions cumulées, seuls les
    ponts relient les branches : passer vite mène loin. Terminaison
    propre : fin honnête ou garde-fou, jamais de boucle ni de doublon."""
    for (profil, depart), s in sessions.items():
        if profil != "zappeur":
            continue
        assert all(p["cause"] == "duree" for p in s.pas), depart
        assert all(p["rayon"] == 3 for p in s.pas), depart
        assert s.chaine == [depart] + [p["to"] for p in s.pas], depart
        assert len(set(s.chaine)) == len(s.chaine), f"{depart} : doublon dans {s.chaine}"
        assert s.fin in (session.FinSession.FIN_HONNETE, session.FinSession.GARDE_FOU), (
            depart, s.fin
        )
        if s.fin is session.FinSession.GARDE_FOU:
            assert len(s.pas) == 50, (depart, len(s.pas))
        visitees = set()
        for vid in s.chaine:
            visitees |= branches_de(by_id, vid)
        assert len(visitees) >= 2, f"{depart} : jamais deux branches ({s.chaine})"
        assert visitees - branches_de(by_id, depart), (
            f"{depart} : jamais de saut au-delà des branches du départ ({s.chaine})"
        )


def test_attentif_depuis_chacun_des_96_departs_rayon_1_dans_le_voisinage(sessions, arbre, by_id):
    """Profil attentif (tout >= seuil) : depuis chacun des 96 départs, chaque
    pas resserre (rayon 1) et la chaîne reste dans le voisinage de la
    branche — chaque transition relie deux cartes de la même branche ou
    d'une branche voisine par un pont du JSON. Terminaison propre : les
    longues sessions atteignent légitimement le garde-fou de 50 pas, les
    autres s'épuisent en fin honnête — jamais de boucle ni de doublon.
    Rester approfondit."""
    for (profil, depart), s in sessions.items():
        if profil != "attentif":
            continue
        assert all(p["cause"] == "duree" for p in s.pas), depart
        assert all(p["rayon"] == 1 for p in s.pas), depart
        assert s.chaine == [depart] + [p["to"] for p in s.pas], depart
        assert len(set(s.chaine)) == len(s.chaine), f"{depart} : doublon dans {s.chaine}"
        assert s.fin in (session.FinSession.FIN_HONNETE, session.FinSession.GARDE_FOU), (
            depart, s.fin
        )
        if s.fin is session.FinSession.GARDE_FOU:
            assert len(s.pas) == 50, (depart, len(s.pas))
        for p in s.pas:
            orientantes = branches_de(by_id, p["from"])
            arrivees = branches_de(by_id, p["to"])
            assert any(
                a == b or cooccurs(arbre, a, b) for a in orientantes for b in arrivees
            ), f"{depart} : {p['from']} → {p['to']} sort du voisinage de la branche"


def test_mixte_depuis_chacun_des_96_departs_le_temps_cause_le_rayon(sessions, by_id):
    """Profil mixte : depuis chacun des 96 départs, le rayon de chaque pas est
    exactement celui de la bande de durée de sa quittance — durée >= 5000 ms
    -> rayon 1, durée < 5000 ms -> rayon 3. Le rayon change à l'exact moment
    du changement de bande (les deux rayons apparaissent dans chaque
    session), chaque pas part de la carte quittée avec sa durée, et la
    session se termine par une fin définie du contrat."""
    for (profil, depart), s in sessions.items():
        if profil != "mixte":
            continue
        attendus = [rayon_attendu(d) for d in PROFILS["mixte"]]
        assert [p["rayon"] for p in s.pas] == attendus[: len(s.pas)], depart
        rayons = [p["rayon"] for p in s.pas]
        assert 1 in rayons and 3 in rayons, f"{depart} : le temps ne cause rien ({rayons})"
        for i, p in enumerate(s.pas):
            assert p["from"] == s.chaine[i], (depart, i)
            assert p["duree"] == PROFILS["mixte"][i], (depart, i)
            assert p["cause"] == "duree", (depart, i)
        for precedent, suivant in zip(s.pas, s.pas[1:]):
            assert suivant["from"] == precedent["to"], depart
        assert len(set(s.chaine)) == len(s.chaine), f"{depart} : doublon dans {s.chaine}"
        assert s.fin in (session.FinSession.FIN_HONNETE, session.FinSession.GARDE_FOU), (
            depart, s.fin
        )


def test_co_verification_independante_de_chaque_transition_de_toutes_les_sessions(sessions, arbre, by_id):
    """Co-vérification hors moteur, sur toutes les sessions des trois profils :
    chaque transition part d'un sujet de la carte orientante, aboutit à un
    sujet de la suivante, et son chemin de sujets est réel — deux sujets
    consécutifs co-occurrent sur une vraie vidéo du JSON du corpus
    (GLOSSARY : chemin de sujets). L'explicabilité est une source de
    vérité indépendante du moteur."""
    for (profil, depart), s in sessions.items():
        for p in s.pas:
            chemin = p["topic_path"]
            assert chemin[0] in topics_of(by_id[p["from"]]), (depart, p)
            assert chemin[-1] in topics_of(by_id[p["to"]]), (depart, p)
            for premier, second in zip(chemin, chemin[1:]):
                assert cooccurs(arbre, premier, second), (
                    f"{depart} : suite de sujets sans vidéo porteuse : {premier} → {second}"
                )
