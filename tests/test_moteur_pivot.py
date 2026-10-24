"""Primitives moteur du parcours sensible à la rétention : rayon explicite, premier pas.

Seam testé (moteur pur, sans HTTP ni session) : le rayon devient un
paramètre explicite du pas suivant et du parcours complet — il filtre
l'éligibilité des candidates, jamais la recherche du chemin de sujets
(GLOSSARY, « Chemin de sujets »). Le rayon est dérivé de la rétention
applicative côté session ou serveur — plus aucun mode n'existe (ticket #35).

Le premier pas depuis un sujet est la brique de la sortie de branche
dirigée (GLOSSARY, « Sortie de branche ») : (sujet, déjà-vues) → pas,
meilleure candidate par sujets communs décroissants puis ID croissant
(règle de départage unique du moteur), hors déjà-vues ; sujet mort ou
inconnu → erreur explicite ; aucune candidate restante → fin honnête
(None), pas d'exception.
"""
import pytest

from vte import graph_engine
from vte.corpus import topics_of

from conftest import make_video, load_corpus_from_videos


def _topic_path_est_reel(corpus, from_id, to_id, topic_path):
    """Co-vérification hors moteur : le chemin part des sujets de la carte orientante,
    aboutit aux sujets de la suivante, et chaque paire consecutive co-occurre sur
    une vraie vidéo du corpus."""
    by_id = {video["id"]: video for video in corpus["videos"]}
    assert topic_path[0] in topics_of(by_id[from_id])
    assert topic_path[-1] in topics_of(by_id[to_id])
    for first, second in zip(topic_path, topic_path[1:]):
        assert any(
            {first, second} <= topics_of(video) for video in corpus["videos"]
        ), f"suite de sujets sans vidéo porteuse : {first} → {second}"


# --- Le pas suivant prend un rayon explicite, filtre l'éligibilité, jamais le chemin ---


def test_pas_suivant_rayon_explicite_vaut_la_premiere_transition_du_parcours(rich_corpus):
    """Le pas au rayon N est exactement la première transition du parcours complet au rayon N."""
    rapproche = graph_engine.next_step(rich_corpus, "v1", radius=1)
    elargi = graph_engine.next_step(rich_corpus, "v1", radius=3)
    assert rapproche == graph_engine.parcours(rich_corpus, "v1", 1).transitions[0]
    assert elargi == graph_engine.parcours(rich_corpus, "v1", 3).transitions[0]


def test_pas_suivant_rayon_explicite_filtre_l_eligibilite_pas_le_chemin(chain_corpus):
    """Rayon 1 : « d » n'est pas éligible (aucun sujet commun atteignable) → fin
    honnête ; rayon 3 : « d » est éligible et son chemin de sujets — deux hops
    plus long que le rayon 1 — est trouvé entier sur le graphe complet."""
    eteint = graph_engine.next_step(chain_corpus, "a", radius=1, exclude={"b", "c"})
    assert eteint is None

    atteint = graph_engine.next_step(chain_corpus, "a", radius=3, exclude={"b", "c"})
    assert atteint is not None
    assert atteint["from"] == "a"
    assert atteint["to"] == "d"
    _topic_path_est_reel(chain_corpus, "a", "d", atteint["topic_path"])
    assert len(atteint["topic_path"]) == 3  # Roslyn → Compilateurs → LLVM : jamais plafonné par le rayon


def test_pas_suivant_sans_rayon_erreur_explicite(chain_corpus):
    """Ticket #35 : plus aucun mode ne donne le rayon — sans rayon, erreur explicite."""
    with pytest.raises(graph_engine.PathfindingError, match="rayon requis"):
        graph_engine.next_step(chain_corpus, "a")


def test_le_parcours_complet_prend_un_rayon_explicite(rich_corpus):
    """Le parcours complet prend lui aussi un rayon explicite : le run porte ce
    rayon, jamais un mode (ticket #35)."""
    run = graph_engine.parcours(rich_corpus, "v1", 1)
    assert run.radius == 1
    assert "mode" not in run.to_dict()
    assert graph_engine.parcours(rich_corpus, "v1", 3).radius == 3


# --- Premier pas depuis un sujet : la brique de la sortie de branche dirigée ---


def test_premier_pas_depuis_sujet_reprend_le_depart_par_sujet(rich_corpus):
    """Le premier pas depuis « Roslyn » est exactement la transition initiale du
    départ par sujet : v1 et v4 portent le sujet (vérifié dans le JSON), à sujets
    communs égaux l'ID croissant décide."""
    step = graph_engine.first_step(rich_corpus, "Roslyn")
    assert step["to"] == "v1"  # porteurs triés : à sujets communs égaux, l'ID croissant gagne
    porteurs = [v["id"] for v in rich_corpus["videos"] if "Roslyn" in topics_of(v)]
    assert porteurs == ["v1", "v4"]
    assert step["to"] == "v1"
    assert step["topic_path"] == ["Roslyn"]


def test_premier_pas_hors_deja_vues(rich_corpus):
    """Les déjà-vues sont exclues : la meilleure candidate restante gagne, le
    départage reste l'ID croissant à sujets communs égaux."""
    premiere = graph_engine.first_step(rich_corpus, "C#", exclude={"v1"})
    assert premiere["to"] == "v2"
    deuxieme = graph_engine.first_step(rich_corpus, "C#", exclude={"v1", "v2"})
    assert deuxieme["to"] == "v3"


def test_premier_pas_fin_honnete_quand_toute_candidate_est_deja_vue(rich_corpus):
    """Plus aucune candidate : fin honnête (None), jamais d'exception."""
    step = graph_engine.first_step(rich_corpus, "C#", exclude={"v1", "v2", "v3"})
    assert step is None


def test_premier_pas_sujet_mort_erreur_explicite(chain_corpus):
    """Un sujet mort (porté par une seule vidéo, GLOSSARY) ne peut orienter aucun
    premier pas : erreur explicite, jamais de repli silencieux."""
    assert "SujetUnique" in chain_corpus["dead_topics"]
    with pytest.raises(graph_engine.PathfindingError) as exc:
        graph_engine.first_step(chain_corpus, "SujetUnique")
    assert "mort" in str(exc.value)


def test_premier_pas_sujet_inconnu_erreur_explicite(rich_corpus):
    """Un sujet absent du corpus figé : erreur explicite, jamais de fin honnête déguisée."""
    with pytest.raises(graph_engine.PathfindingError) as exc:
        graph_engine.first_step(rich_corpus, "Nimporte-quoi")
    assert "inconnu" in str(exc.value)
