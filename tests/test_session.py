"""Harness rouge de la session : la spécification exécutable du parcours sensible à la rétention.

Spec #27, ticket #29. Ce harness est écrit AVANT le module `vte.session`
(ticket #31) : tant que le module n'existe pas, chaque test de ce fichier
échoue — uniquement pour cette raison, par la fixture autouse ci-dessous —
et le reste de la suite reste exécutable et vert : c'est la fenêtre rouge
assumée par le spec. L'implémenteur du ticket #31 n'a pas d'autre guidance
que le contrat ci-dessous, négocié dans le spec #27 (Implementation
Decisions) et le grilling. Les assertions ne testent que le comportement externe de la
fonction session pure ; leurs valeurs attendues viennent du JSON des corpus
figés (data/corpus_arbre.json, version arbre-2026-10 ; fixtures de
conftest.py) et de la conception du corpus arbre
(scripts/make_arbre_corpus.py : 19 branches de 4 vidéos + 20 ponts, une
branche s'épuise, seuls les ponts relient les branches) — jamais du moteur.

LE CONTRAT DU MODULE vte.session
=================================

Constante
---------
`SEUIL_MS = 5000` — le seuil unique, celui du panneau. Mapping binaire,
sans bande intermédiaire : durée >= SEUIL_MS -> rayon 1 ; durée < SEUIL_MS
-> rayon 3.

Fonction pure
-------------
`deroule(corpus, depart, evenements) -> Session`

- `corpus` : corpus figé chargé par `vte.corpus.load_corpus`
  (sujets morts injectés).
- `depart` : identifiant de la première carte, une vidéo du corpus.
  Départ inconnu -> `graph_engine.PathfindingError`, immédiat, même si la
  liste d'événements est vide.
- `evenements` : liste ordonnée d'événements. Un événement est :
  * `{"duree": <millisecondes>}` — la carte courante est quittée après
    cette durée de visionnage (durée abstraite, comparée à SEUIL_MS) ;
    la durée de la dernière carte quittée décide du rayon du pas suivant ;
  * `{"sortie": "<sujet canonique>"}` — sortie de branche dirigée vers un
    sujet canonique réel du corpus figé : le parcours redémarre depuis ce
    sujet, hors déjà-vues (premier pas par sujets communs décroissants
    puis ID croissant, règle de départage unique du moteur).
  Toute autre forme d'événement -> `PathfindingError`, jamais ignorée.

Résultat `Session` (dataclass)
------------------------------
- `depart : str`
- `chaine : list[str]` — cartes montrées, uniques, dans l'ordre ;
  `chaine[0] == depart` ; `chaine == [depart] + [p["to"] for p in pas]`.
- `pas : list[dict]` — un dict par pas effectué, exactement ces clés :
  * "from"        : carte orientante (la dernière carte quittée) ;
                    None pour un pas de sortie dirigée ;
  * "to"          : carte proposée (jamais déjà vue) ;
  * "rayon"       : rayon de hops de sujets du pas ;
                    None pour une sortie dirigée (pas piloté par la durée) ;
  * "cause"       : "duree" (rétention) ou "sortie" (sortie de branche) ;
  * "sujet"       : sujet canonique choisi ; None sauf sortie dirigée ;
  * "duree"       : durée de visionnage ayant orienté le pas ;
                    None pour une sortie ;
  * "topic_path"  : chemin de sujets réel (GLOSSARY) ;
                    [sujet] pour une sortie dirigée ;
  * "explanation" : explication affichable, inchangée du moteur ;
  * "exclusions"  : exclusions cumulées du pas (cartes déjà vues, départ
                    compris), triées par ID croissant.
- `fin : FinSession` — str-Enum à trois valeurs :
  * `FIN_HONNETE = "fin_honnete"` : plus aucune candidate (pas de durée ou
    sortie épuisée) — arrêt normal du feed, événements restants ignorés ;
  * `PROFIL_EPUISE = "profil_epuise"` : tous les événements ont été
    consommés alors que des candidates restaient possibles ;
  * `GARDE_FOU = "garde_fou"` : 50 pas effectués — bug (boucle ou dérive) ;
    la session s'arrête exactement à 50 pas, événements restants ignorés.

Exclusions
----------
Elles croissent monotoniquement : chaque pas ajoute sa carte "to" aux
exclusions du suivant ; jamais de doublon dans la chaîne. Le pas 0 exclut
le départ seul.

Erreurs
-------
La session propage l'erreur explicite unique du moteur,
`graph_engine.PathfindingError` (message français) : départ inconnu,
événement de forme inconnue, sortie vers un sujet mort (message contenant
« mort »), sortie vers un sujet inconnu (message contenant « inconnu »).
Jamais de repli silencieux : un sujet demandé n'est jamais remplacé, un
événement n'est jamais sauté, une erreur n'est jamais déguisée en fin
honnête.

Briques réutilisées
-------------------
La session appelle `graph_engine.next_step(corpus, courant, radius=…,
exclude=…)` pour un pas de durée et `graph_engine.first_step(corpus,
sujet, exclude=…)` pour une sortie dirigée ; elle dérive le rayon de la
durée, cumule les exclusions et tient le garde-fou.

LES HUIT FAMILLES
================

(1) mapping binaire durée->rayon au seuil de 5000 ms, de part et d'autre ;
(2) chaque pas orienté par la dernière carte quittée et sa durée, jamais
    par l'ordre linéaire de la chaîne ;
(3) profils zappeur (tout < seuil -> rayon 3, saut de branche
    systématique sur les 96 départs de l'arbre figé), attentif (tout >=
    seuil -> rayon 1, voisinage de la branche, fin honnête acceptée),
    mixte (le rayon change à l'exact moment du changement de bande) ;
(4) exclusions cumulées, jamais un doublon ;
(5) terminaison : fin honnête, profil épuisé, garde-fou de 50 pas = échec ;
(6) sortie non dirigée : le zap est le repli implicite, sans événement de
    sortie ;
(7) sortie dirigée vers un sujet canonique réel — scénario nominal branche
    Fun -> sujet Science — puis reprise du pilotage par la durée ;
(8) erreur explicite sur sujet mort ou inconnu, jamais de repli silencieux.
"""

from pathlib import Path

import pytest

try:
    from vte import session
except ImportError as _erreur_import:  # fenêtre rouge assumée : ticket #29 → #31
    session = None
    _ERREUR_IMPORT = _erreur_import

from vte import graph_engine
from vte.corpus import load_corpus, topics_of

from conftest import make_video, load_corpus_from_videos


@pytest.fixture(autouse=True, scope="module")
def _le_module_session_doit_exister():
    """Fenêtre rouge assumée du spec #27 : tant que vte.session n'existe pas
    (ticket #31), chaque test de ce harness échoue — uniquement pour cette
    raison. Le reste de la suite reste exécutable et vert."""
    if session is None:
        pytest.fail(
            "vte.session n'existe pas encore (ticket #31) — harness rouge : "
            f"{_ERREUR_IMPORT}"
        )

ARBRE_CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus_arbre.json"

# Sujets cœur de l'arbre : chaque branche porte un sujet cœur unique présent
# sur toutes ses vidéos ; les ponts en portent deux. Source de vérité
# indépendante : la conception du corpus (scripts/make_arbre_corpus.py).
CORE_TOPICS = {
    "Roslyn", "Compilateurs", "Rust", "TypeScript", "Machine Learning",
    "Noyau Linux", "Asynchrone", "Architecture", "Sécurité", "Bases de données",
    "Accessibilité", "Graphisme", "Éditeurs", "Tests", "Musique", "Fun",
    "Science", "Mathématiques", "Cuisine",
}

DEPART_FUN = "vid-fu-001"  # première carte de la branche Fun de l'arbre figé


def zap(n: int) -> list[dict]:
    """Profil zappeur : n quittances rapides, sous le seuil."""
    return [{"duree": 1000} for _ in range(n)]


def attentif(n: int) -> list[dict]:
    """Profil attentif : n quittances longues, au-dessus du seuil."""
    return [{"duree": 6000} for _ in range(n)]


def mixte(n: int) -> list[dict]:
    """Profil mixte : alternance longue / courte de part et d'autre du seuil."""
    return [{"duree": 6000 if i % 2 == 0 else 1000} for i in range(n)]


@pytest.fixture(scope="module")
def arbre() -> dict:
    """Le corpus arbre figé (data/corpus_arbre.json, version arbre-2026-10)."""
    return load_corpus(ARBRE_CORPUS)


def _branches_de(arbre: dict, by_id: dict, vid: str) -> set[str]:
    """Branches d'une carte : les sujets cœur qu'elle porte (un pont en porte deux)."""
    return topics_of(by_id[vid]) & CORE_TOPICS


def _le_chemin_est_reel(arbre: dict, by_id: dict, pas: dict) -> None:
    """Co-vérification hors moteur : le chemin part des sujets de la carte
    orientante, aboutit aux sujets de la suivante, et chaque paire de sujets
    consécutifs co-occurrent sur une vraie vidéo du corpus."""
    chemin = pas["topic_path"]
    assert chemin[0] in topics_of(by_id[pas["from"]]), pas
    assert chemin[-1] in topics_of(by_id[pas["to"]]), pas
    for premier, second in zip(chemin, chemin[1:]):
        assert any(
            {premier, second} <= topics_of(video) for video in arbre["videos"]
        ), f"suite de sujets sans vidéo porteuse : {premier} → {second}"


# --- Le corpus des balayages et le seuil unique ---------------------------------


def test_le_seuil_unique_est_celui_du_panneau():
    """Le seuil unique du parcours sensible à la rétention est celui du panneau
    actuel : 5000 ms (spec #27, Implementation Decisions)."""
    assert session.SEUIL_MS == 5000


def test_le_corpus_des_balayages_est_l_arbre_figé_version_arbre_2026_10(arbre):
    """Les balayages exhaustifs s'appuient sur le corpus arbre figé : 96 vidéos,
    sujet mort déclaré « Histoire de l'informatique », provenance arbre-2026-10
    sur chaque sujet du JSON."""
    assert len(arbre["videos"]) == 96
    assert arbre["dead_topics"] == ["Histoire de l'informatique"]
    for video in arbre["videos"]:
        for topic in video["topics"]:
            assert topic["provenance"]["version"] == "arbre-2026-10"


# --- Famille 1 : mapping binaire durée->rayon, de part et d'autre du seuil ------


@pytest.mark.parametrize("duree, rayon", [(1000, 3), (4999, 3), (5000, 1), (6000, 1)])
def test_mapping_binaire_de_part_et_autre_du_seuil(rich_corpus, duree, rayon):
    """Une seule carte quittée : durée >= 5000 ms -> rayon 1 (rester approfondit),
    durée < 5000 ms -> rayon 3 (passer vite éloigne). Pas de bande intermédiaire :
    4999 ms s'éloigne, 5000 ms reste."""
    s = session.deroule(rich_corpus, "v1", [{"duree": duree}])
    assert len(s.pas) == 1
    pas = s.pas[0]
    assert pas["cause"] == "duree"
    assert pas["duree"] == duree
    assert pas["rayon"] == rayon
    assert pas["from"] == "v1"
    assert s.chaine == ["v1", pas["to"]]


# --- Famille 2 : chaque pas orienté par la dernière carte quittée et sa durée --


def test_chaque_pas_est_oriente_par_la_derniere_carte_quitee_et_sa_duree(arbre):
    """Le pas i part de la carte i — la dernière quittée — avec la durée de
    l'événement i : jamais d'une carte antérieure, jamais de l'ordre linéaire
    de la chaîne. Le chemin de sujets part des sujets de la carte orientante
    et aboutit aux sujets de la suivante (co-vérifié dans le JSON)."""
    evenements = mixte(6)
    s = session.deroule(arbre, DEPART_FUN, evenements)
    assert len(s.pas) == 6
    by_id = {v["id"]: v for v in arbre["videos"]}
    for i, pas in enumerate(s.pas):
        assert pas["from"] == s.chaine[i]
        assert pas["duree"] == evenements[i]["duree"]
        assert pas["cause"] == "duree"
        attendu = 1 if evenements[i]["duree"] >= session.SEUIL_MS else 3
        assert pas["rayon"] == attendu
        _le_chemin_est_reel(arbre, by_id, pas)


def test_le_rayon_ne_suit_pas_l_ordre_lineaire_de_la_chaine(arbre):
    """Six cartes, durées alternées : les rayons alternent exactement
    [1, 3, 1, 3, 1, 3]. Une session orientée par la première carte ou par la
    position dans la chaîne donnerait des rayons constants — c'est la durée de
    chaque carte, au moment exact de sa quittance, qui cause le comportement."""
    s = session.deroule(arbre, DEPART_FUN, mixte(6))
    assert [p["rayon"] for p in s.pas] == [1, 3, 1, 3, 1, 3]


# --- Famille 3 : profils zappeur, attentif, mixte -------------------------------


def test_profil_zappeur_balayage_exhaustif_saut_de_branche_systematique(arbre):
    """Depuis chacun des 96 départs de l'arbre figé, le profil zappeur (tout <
    seuil) éloigne chaque pas (rayon 3) et la session saute de branche
    systématiquement : la chaîne visite des branches au-delà de celles du
    départ. Conception du corpus : une branche de 4 vidéos s'épuise sous les
    exclusions cumulées, seuls les ponts relient les branches — passer vite
    mène loin."""
    by_id = {v["id"]: v for v in arbre["videos"]}
    for video in arbre["videos"]:
        s = session.deroule(arbre, video["id"], zap(8))
        depart = video["id"]
        assert all(p["cause"] == "duree" for p in s.pas), depart
        assert all(p["rayon"] == 3 for p in s.pas), depart
        assert len(s.pas) == 8, (depart, s.fin)
        assert s.fin is session.FinSession.PROFIL_EPUISE, (depart, s.fin)
        assert len(set(s.chaine)) == len(s.chaine), depart
        visitees = set()
        for vid in s.chaine:
            visitees |= _branches_de(arbre, by_id, vid)
        assert visitees - _branches_de(arbre, by_id, depart), (
            f"{depart} : jamais de saut de branche ({s.chaine})"
        )
        for pas in s.pas:
            _le_chemin_est_reel(arbre, by_id, pas)


def test_profil_attentif_balayage_chaque_pas_rayon_1(arbre):
    """Depuis chacun des 96 départs, le profil attentif (tout >= seuil)
    resserre chaque pas : rayon 1 partout, chaîne sans doublon, profil épuisé
    — rester mène en profondeur."""
    for video in arbre["videos"]:
        s = session.deroule(arbre, video["id"], attentif(8))
        depart = video["id"]
        assert all(p["cause"] == "duree" and p["rayon"] == 1 for p in s.pas), depart
        assert len(s.pas) == 8, (depart, s.fin)
        assert s.fin is session.FinSession.PROFIL_EPUISE, (depart, s.fin)
        assert len(set(s.chaine)) == len(s.chaine), depart


def test_profil_attentif_reste_dans_le_voisinage_de_la_branche(arbre):
    """Profil attentif depuis la branche Fun : chaque carte de la chaîne porte
    le sujet cœur « Fun » du JSON — le parcours reste dans le voisinage
    immédiat de ce qui est aimé."""
    s = session.deroule(arbre, DEPART_FUN, attentif(3))
    by_id = {v["id"]: v for v in arbre["videos"]}
    assert len(s.chaine) == 4
    for vid in s.chaine:
        assert "Fun" in topics_of(by_id[vid]), vid


def test_profil_attentif_epuise_le_voisinage_en_fin_honnete(rich_corpus):
    """Le corpus rich est une guirlande de huit cartes v1 -> v8 par sujets
    partagés de proche en proche (fixture). Le profil attentif la parcourt
    jusqu'au bout : plus aucune candidate au rayon 1 -> fin honnête, jamais
    une erreur, et les événements restants sont ignorés."""
    s = session.deroule(rich_corpus, "v1", attentif(8) + zap(2))
    assert s.chaine == ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"]
    assert len(s.pas) == 7
    assert s.fin is session.FinSession.FIN_HONNETE


def test_profil_mixte_le_rayon_change_a_l_exact_moment_du_changement_de_bande(arbre):
    """Profil mixte : le rayon change à l'exact moment du changement de bande de
    durée — la cause du pas porte la durée qui l'a orienté, et la suivante
    repart de la carte d'arrivée."""
    evenements = mixte(6)
    s = session.deroule(arbre, DEPART_FUN, evenements)
    attendus = [1 if e["duree"] >= session.SEUIL_MS else 3 for e in evenements]
    assert [p["rayon"] for p in s.pas] == attendus
    for precedent, suivant in zip(s.pas, s.pas[1:]):
        assert suivant["from"] == precedent["to"]


# --- Famille 4 : exclusions cumulées, jamais un doublon -------------------------


def test_les_exclusions_croissent_monotonement_jamais_de_doublon(arbre):
    """Chaque pas porte les exclusions cumulées du moment : le pas 0 n'exclut
    que le départ, chaque pas en ajoute exactement une — sa carte d'arrivée —
    et aucune carte proposée n'était déjà exclue. La chaîne ne se répète jamais."""
    s = session.deroule(arbre, DEPART_FUN, mixte(6))
    assert s.pas[0]["exclusions"] == [DEPART_FUN]
    for precedent, suivant in zip(s.pas, s.pas[1:]):
        assert set(suivant["exclusions"]) - set(precedent["exclusions"]) == {precedent["to"]}
        assert suivant["exclusions"] == sorted(set(precedent["exclusions"]) | {precedent["to"]})
    for pas in s.pas:
        assert pas["to"] not in pas["exclusions"]
    assert len(set(s.chaine)) == len(s.chaine)


# --- Famille 5 : terminaison — fin honnête, profil épuisé, garde-fou ------------


def test_fin_honnete_quand_plus_aucune_candidate_ne_reste(chain_corpus):
    """La chaîne a -> b -> c -> d s'épuise : le quatrième événement ne trouve
    plus aucune candidate -> fin honnête, l'arrêt normal du feed, jamais une
    erreur ni un garde-fou."""
    s = session.deroule(chain_corpus, "a", zap(4))
    assert s.chaine == ["a", "b", "c", "d"]
    assert len(s.pas) == 3
    assert s.fin is session.FinSession.FIN_HONNETE


def test_profil_epuise_quand_les_evenements_s_eteignent_avec_des_candidates_restantes(rich_corpus):
    """Sept événements pour une guirlande de huit cartes : le profil s'éteint
    avant la chaîne — la fin est « profil épuisé », pas une fin honnête
    déguisée."""
    s = session.deroule(rich_corpus, "v1", attentif(7))
    assert len(s.pas) == 7
    assert s.chaine == ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8"]
    assert s.fin is session.FinSession.PROFIL_EPUISE


def test_zero_evenement_la_session_se_reduit_au_depart(arbre):
    """Aucun événement : la session montre la carte de départ et rien d'autre ;
    un profil vide est un profil épuisé."""
    s = session.deroule(arbre, DEPART_FUN, [])
    assert s.chaine == [DEPART_FUN]
    assert s.pas == []
    assert s.fin is session.FinSession.PROFIL_EPUISE


def test_sortie_vers_un_sujet_aux_porteurs_deja_vus_fin_honnete(rich_corpus):
    """Sortie dirigée vers « C# » alors que ses trois porteurs (v1, v2, v3 du
    JSON) sont déjà vus : plus aucune candidate -> fin honnête, jamais une
    erreur, et les événements restants sont ignorés."""
    s = session.deroule(rich_corpus, "v1", attentif(2) + [{"sortie": "C#"}] + zap(1))
    assert len(s.pas) == 2
    assert s.fin is session.FinSession.FIN_HONNETE


def test_le_garde_fou_de_50_pas_est_un_echec():
    """Sur un anneau de 60 cartes — chaque carte n'a que deux voisines, la
    marche est donc contrainte de proche en proche par ID croissant —, 55
    quittances zappeuses dépassent le garde-fou : la session s'arrête à 50 pas
    exactement et le qualifie de bug. Elle ne boucle ni ne dérive au-delà."""
    anneau = load_corpus_from_videos([
        make_video(f"v{i:02d}", [f"Sujet {i:02d}", f"Sujet {(i + 1) % 60:02d}"])
        for i in range(60)
    ])
    s = session.deroule(anneau, "v00", zap(55))
    assert s.fin is session.FinSession.GARDE_FOU
    assert len(s.pas) == 50
    assert s.chaine == [f"v{i:02d}" for i in range(51)]


# --- Famille 6 : sortie non dirigée — le zap est le repli implicite -------------


def test_le_zap_est_la_sortie_non_dirigee(arbre):
    """Huit quittances rapides depuis la branche Fun, sans aucun événement de
    sortie : la chaîne quitte pourtant la branche (elle visite des branches
    au-delà de Fun, par les ponts). Le zap — durée sous le seuil — est le
    mécanisme implicite de repli, déjà couvert par le mapping binaire : la
    navigation implicite ne juge pas plus la carte que la sortie dirigée."""
    by_id = {v["id"]: v for v in arbre["videos"]}
    s = session.deroule(arbre, DEPART_FUN, zap(8))
    assert all(p["cause"] == "duree" and p["rayon"] == 3 for p in s.pas)
    visitees = set()
    for vid in s.chaine:
        visitees |= _branches_de(arbre, by_id, vid)
    assert visitees - {"Fun"}, s.chaine


# --- Famille 7 : sortie dirigée vers un sujet réel, scénario nominal -------------


def test_scenario_nominal_de_drole_a_instructif(arbre):
    """Le scénario nominal du pivot, de bout en bout : session attentive dans
    la branche Fun, sortie dirigée vers le sujet réel Science, puis reprise du
    pilotage par la durée dans la nouvelle branche."""
    evenements = attentif(3) + [{"sortie": "Science"}] + [{"duree": 6000}, {"duree": 1000}]
    s = session.deroule(arbre, DEPART_FUN, evenements)
    by_id = {v["id"]: v for v in arbre["videos"]}
    assert len(s.pas) == 6

    # avant la sortie : chaîne dans la branche Fun, chaque pas piloté par la durée
    for pas in s.pas[:3]:
        assert pas["cause"] == "duree" and pas["rayon"] == 1
        assert "Fun" in topics_of(by_id[pas["to"]]), pas
        assert "Science" not in topics_of(by_id[pas["to"]]), pas

    # la sortie dirigée : un pas de cause « sortie », sans durée ni rayon —
    # elle ne juge pas la carte en cours — vers un porteur réel de Science.
    sortie = s.pas[3]
    assert sortie["cause"] == "sortie"
    assert sortie["sujet"] == "Science"
    assert sortie["rayon"] is None
    assert sortie["duree"] is None
    assert sortie["from"] is None
    assert sortie["topic_path"] == ["Science"]
    assert "Science" in topics_of(by_id[sortie["to"]]), sortie

    # reprise du pilotage par la durée, depuis la carte d'arrivée de la sortie
    rapproche = s.pas[4]
    assert rapproche["from"] == sortie["to"]
    assert rapproche["cause"] == "duree" and rapproche["rayon"] == 1  # 6000 ms >= seuil
    eloigne = s.pas[5]
    assert eloigne["from"] == rapproche["to"]
    assert eloigne["cause"] == "duree" and eloigne["rayon"] == 3  # 1000 ms < seuil

    assert s.chaine == [DEPART_FUN] + [p["to"] for p in s.pas]
    assert len(set(s.chaine)) == len(s.chaine)


# --- Famille 8 : erreur explicite, jamais de repli silencieux --------------------


def test_sortie_dirigee_vers_sujet_mort_erreur_explicite(arbre):
    """« Histoire de l'informatique » est porté par une seule vidéo (vid-ru-004,
    sujet mort déclaré dans le JSON) : la sortie dirigée échoue explicitement —
    message portant « mort » — jamais de repli silencieux vers un autre sujet."""
    assert "Histoire de l'informatique" in arbre["dead_topics"]
    with pytest.raises(graph_engine.PathfindingError) as exc:
        session.deroule(arbre, DEPART_FUN, [{"sortie": "Histoire de l'informatique"}])
    assert "mort" in str(exc.value)


def test_sortie_dirigee_vers_sujet_inconnu_erreur_explicite(arbre):
    """« Sémantique formelle » est absent de tout le JSON : la sortie dirigée
    échoue explicitement — message portant « inconnu » — jamais de fin honnête
    déguisée ni de sujet de remplacement."""
    for video in arbre["videos"]:
        assert "Sémantique formelle" not in topics_of(video)
    with pytest.raises(graph_engine.PathfindingError) as exc:
        session.deroule(arbre, DEPART_FUN, [{"sortie": "Sémantique formelle"}])
    assert "inconnu" in str(exc.value)


def test_depart_inconnu_erreur_explicite_des_le_debut(arbre):
    """Un départ hors du corpus figé échoue immédiatement, même sans aucun
    événement : erreur explicite, jamais de session vide silencieuse."""
    with pytest.raises(graph_engine.PathfindingError):
        session.deroule(arbre, "vid-inconnu", [])


def test_evenement_de_forme_inconnue_erreur_explicite(rich_corpus):
    """Un événement n'est qu'une durée ou une sortie : toute autre forme échoue
    explicitement, jamais ignorée en silence."""
    with pytest.raises(graph_engine.PathfindingError):
        session.deroule(rich_corpus, "v1", [{"nimporte": "quoi"}])
