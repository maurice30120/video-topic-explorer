"""Contrôle de fumée du site publié : la racine sert bien le feed, pas autre chose.

Deux niveaux, un seul contrat :
- check_site_content : le contenu (une page de feed, première carte = première
  vidéo du parcours par défaut, lecteur intégré, chemin de sujets) ;
- check_site_dir / check_deployed_url : le site local généré par la CI, puis
  l'URL publique une fois GitHub Pages propagé (avec retries).

Le parcours par défaut du site est « Découvrir » (mode par défaut du feed) :
la première carte attendue est la carte de départ de ce parcours.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

DEFAULT_MODE = "decouvrir"


class SmokeCheckError(Exception):
    """Le site ne répond pas au contrat du feed publié (messages en français)."""


def _first_card_slice(doc: str, start: int) -> str:
    """Extrait la première carte (de l'ouverture de <article> à sa fermeture)."""
    end = doc.find("</article>", start)
    return doc[start:end] if end != -1 else doc[start:]


def check_site_content(doc: str, first_video: str) -> None:
    """Vérifie qu'un contenu HTML est la page du feed attendue à la racine.

    S'applique au site généré comme à la réponse de l'URL publique : mêmes
    contrôles, même contrat.
    """
    problems: list[str] = []

    if 'id="feed"' not in doc:
        problems.append("la page n'est pas le feed (conteneur #feed absent)")
    if "<ol>" in doc or "chemin de sujets :" in doc:
        problems.append("la page ressemble à l'ancienne page liste, pas au feed")
    if f'<body data-mode="{DEFAULT_MODE}"' not in doc:
        problems.append(f"le mode par défaut du feed n'est pas {DEFAULT_MODE}")

    first_card_marker = f'<article class="carte depart" data-video="{first_video}">'
    first_card_at = doc.find(first_card_marker)
    if first_card_at == -1:
        problems.append(
            f"la première carte du parcours par défaut n'est pas la vidéo de départ {first_video}"
        )
    else:
        first_card = _first_card_slice(doc, first_card_at)
        if "<iframe" not in first_card:
            problems.append(f"la première carte ({first_video}) n'a pas de lecteur intégré")
        if 'class="chemin"' not in first_card:
            problems.append(f"la première carte ({first_video}) n'affiche pas son chemin de sujets")
        first_later_card = doc.find('<article class="carte" data-video=')
        if first_later_card != -1 and first_later_card < first_card_at:
            problems.append("une carte apparaît avant la carte de départ du parcours par défaut")

    if problems:
        raise SmokeCheckError(" ; ".join(problems))


def check_site_dir(site_dir: Path, first_video: str, graph_name: str = "graphe.png") -> None:
    """Vérifie le site généré par la CI : le feed à la racine + le graphe statique.

    C'est le miroir local du site publié : index.html servi par la racine,
    plus le graphe référencé par le feed. Aucun réseau.
    """
    site_dir = Path(site_dir)
    index = site_dir / "index.html"
    if not index.is_file():
        raise SmokeCheckError(f"la racine du site ne sert pas le feed : {index} est absent")
    graph = site_dir / graph_name
    if not graph.is_file():
        raise SmokeCheckError(f"le graphe statique est absent du site : {graph}")
    check_site_content(index.read_text(encoding="utf-8"), first_video=first_video)
