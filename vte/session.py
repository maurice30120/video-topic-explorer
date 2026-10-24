"""Session du parcours sensible à la rétention — fonction pure.

(corpus figé, départ, événements de visionnage) → session : la durée de
visionnage de la dernière carte quittée décide du rayon du pas suivant —
rester longtemps (aimé) garde le parcours dans le voisinage immédiat
(rayon 1), passer vite (pas aimé) s'éloigne (rayon 3). La sortie de
branche dirigée redémarre le parcours depuis un sujet canonique réel,
hors déjà-vues. Les deux canaux restent distincts : la rétention juge
(implicite), la sortie navigue (explicite) — la sortie ne juge jamais la
carte en cours, et après une sortie le pilotage par la durée reprend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import graph_engine
from .corpus import videos_by_id

SEUIL_MS = 5000
"""Seuil unique de rétention applicative (spec #27) : durée de visionnage
≥ seuil = aimé ; < seuil = pas aimé. Pas de bande intermédiaire."""

GARDE_FOU = 50

RAYON_PROCHE = 1
"""Rayon du pas suivant quand la carte quittée a été aimée (restée longtemps)."""

RAYON_PASSER_VITE = 3
"""Rayon du pas suivant quand la carte quittée a été passée vite : le pas
s'éloigne. Constante unique du concept — reprise par le feed statique
(render.RAYON_FEED), le départ du panneau (serve) et l'axe CLI/éval
(eval.RAYON_PARCOURS), où elle porte le même sens (spec #27)."""


def rayon_depuis_duree(duree_ms: int) -> int:
    """Rétention applicative → rayon du pas suivant (mapping binaire, spec #27).

    Rester longtemps (durée ≥ SEUIL_MS) c'est aimer : le pas reste dans le
    voisinage immédiat (RAYON_PROCHE). Passer vite (durée < SEUIL_MS) c'est ne
    pas aimer : le pas s'éloigne (RAYON_PASSER_VITE). Pas de bande
    intermédiaire. Source unique du mapping — le serveur l'importe pour
    dériver le rayon du pas suivant côté serveur.
    """
    return RAYON_PROCHE if duree_ms >= SEUIL_MS else RAYON_PASSER_VITE


class FinSession(str, Enum):
    """Fin d'une session : arrêt honnête, profil épuisé, ou garde-fou."""

    FIN_HONNETE = "fin_honnete"
    PROFIL_EPUISE = "profil_epuise"
    GARDE_FOU = "garde_fou"


@dataclass
class Session:
    """Résultat auditable d'une session du parcours sensible à la rétention."""

    depart: str
    chaine: list[str] = field(default_factory=list)
    pas: list[dict[str, Any]] = field(default_factory=list)
    fin: FinSession = FinSession.PROFIL_EPUISE


def deroule(
    corpus: dict[str, Any], depart: str, evenements: list[dict[str, Any]]
) -> Session:
    """Fonction pure : (corpus figé, départ, événements de visionnage) → session.

    Un événement est une durée de visionnage (la carte courante est quittée
    après cette durée, comparée à SEUIL_MS) ou une sortie de branche dirigée
    vers un sujet canonique réel. Toute autre forme d'événement, un départ
    inconnu ou une sortie vers un sujet mort ou inconnu lèvent
    ``graph_engine.PathfindingError`` — jamais de repli silencieux.

    Chaque pas est orienté par la dernière carte quittée et sa durée (cause
    « duree ») ou par le choix explicite d'un sujet (cause « sortie », sans
    durée ni rayon). Les exclusions croissent monotoniquement : le feed ne
    montre jamais deux fois la même carte. La fin est honnête quand plus
    aucune candidate ne reste (événements restants ignorés), le profil est
    épuisé quand les événements s'éteignent avec des candidates restantes,
    et le garde-fou (50 pas) qualifie un bug — boucle ou dérive.
    """
    if depart not in videos_by_id(corpus):
        raise graph_engine.PathfindingError(f"vidéo inconnue : {depart!r}")

    chaine = [depart]
    exclusions = {depart}
    pas: list[dict[str, Any]] = []
    fin = FinSession.PROFIL_EPUISE

    for evenement in evenements:
        cles = set(evenement) if isinstance(evenement, dict) else set()
        if cles == {"duree"}:
            courant = chaine[-1]
            duree = evenement["duree"]
            rayon = rayon_depuis_duree(duree)
            pas_moteur = graph_engine.next_step(
                corpus, courant, radius=rayon, exclude=set(exclusions)
            )
            orientant, cause, sujet, duree_pas = courant, "duree", None, duree
        elif cles == {"sortie"}:
            sujet = evenement["sortie"]
            pas_moteur = graph_engine.first_step(corpus, sujet, exclude=set(exclusions))
            orientant, rayon, cause, duree_pas = None, None, "sortie", None
        else:
            raise graph_engine.PathfindingError(f"événement inconnu : {evenement!r}")

        if pas_moteur is None:
            fin = FinSession.FIN_HONNETE
            break

        pas.append({
            "from": orientant,
            "to": pas_moteur["to"],
            "rayon": rayon,
            "cause": cause,
            "sujet": sujet,
            "duree": duree_pas,
            "topic_path": pas_moteur["topic_path"],
            "explanation": pas_moteur["explanation"],
            "exclusions": sorted(exclusions),
        })
        chaine.append(pas_moteur["to"])
        exclusions.add(pas_moteur["to"])

        if len(pas) >= GARDE_FOU:
            fin = FinSession.GARDE_FOU
            break

    return Session(depart=depart, chaine=chaine, pas=pas, fin=fin)
