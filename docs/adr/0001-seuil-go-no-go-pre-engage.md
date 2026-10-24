# Seuil go/no-go pré-engagé pour le MVP

Le test de valeur du MVP est mené en solo et à l'aveugle (listes non étiquetées, ordre tiré à l'avance), sur ~5 points de départ, notées 1–5 sur cohérence, surprise utile et clarté des transitions. Pour empêcher tout ajustement rétroactif du barème après avoir vu les résultats, le seuil de décision est fixé à l'avance : **passer en Phase 2 seulement si le parcours Découvrir bat la baseline sur « surprise utile » avec une marge ≥ 1 point en moyenne sur les 5 départs, et si aucun des deux modes ne perd contre la baseline sur « cohérence »**. Approfondir seul ne suffit pas : il reproduit la valeur de la baseline (des vidéos proches) ; c'est Découvrir qui teste l'hypothèse originale de découverte par chemins.

## Conséquences

- Le seuil est écrit dans `docs/MVP.md` avant tout test ; le changer après consultation des résultats invalide le test.
- Un échec impose de revoir l'hypothèse ou la qualité des sujets extraits avant tout enrichissement technologique.
