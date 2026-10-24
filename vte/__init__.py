"""Video Topic Explorer — MVP local, déterministe et auditable."""

__version__ = "0.1.0"

DEFAULT_START = "ghnY4S8unMM"
"""Départ par défaut du parcours publié : la vidéo Roslyn du corpus réel.

Constante unique du point de départ — défaut de `vte feed --start`, reprise
par la CI pour le parcours de démonstration du site (le graphe surligné
doit être celui du feed publié).
"""
