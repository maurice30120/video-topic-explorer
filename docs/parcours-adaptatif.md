# Parcours adaptatif

Spécification publiée : [GitHub #38](https://github.com/maurice30120/video-topic-explorer/issues/38). Copie locale : [spec-parcours-adaptatif.md](spec-parcours-adaptatif.md).

Décisions confirmées pendant l’entretien du 24 octobre 2026. La spécification complète est suivie dans #38 et ses sous-tickets.

## Décisions confirmées

- À l’arrivée, démarrer directement le parcours avec une seule vidéo à l’écran, sans grille de sélection.
- Avant le premier point d’intérêt, les zaps font découvrir d’autres sujets.
- Prévoir sur chaque vidéo un bouton de test « Simuler un visionnage long », déclenchant le même effet qu’un temps de visionnage élevé, sans attendre.
- Pour cette étape de test, proposer aussi un bouton « Zapper ». Les deux boutons font apparaître la vidéo suivante selon les règles d’intérêt ou de zap, sans dépendre d’une mesure réelle du visionnage.
- Afficher les deux boutons sous la vidéo actuelle. Chaque action remplace celle-ci par la prochaine vidéo du parcours.
- Après un intérêt, privilégier pour la prochaine vidéo les sujets communs avec la vidéo actuelle. L’exploration peut progressivement s’éloigner du sujet initial, avec un lien à chaque transition.
- Chaque vidéo qui intéresse la personne devient le nouveau point d’intérêt et réoriente la toute prochaine vidéo, même si une autre était prévue.
- Un zap fait perdre le point d’intérêt actif. Cette correction remplace la règle initiale de conservation du dernier point d’intérêt.
- Après un zap, chercher une branche voisine de la vidéo quittée, en évitant la direction qui vient d’être zappée, sans réutiliser un ancien point d’intérêt comme repère actif.
- Après plusieurs zaps, élargir progressivement la recherche ; un nouvel intérêt établit un nouveau point d’intérêt.
- Quand les branches disponibles sont épuisées, reprendre l’exploration depuis un autre arbre choisi au hasard à la racine.
- Prévenir la personne au moment de ce changement : « Tu as exploré les branches disponibles. On repart sur un autre arbre choisi au hasard. »

Exemple : une vidéo sur l’IA intéresse la personne ; elle zappe ensuite les réseaux de neurones : le point d’intérêt est perdu et le parcours tente une direction voisine. Un intérêt pour la robotique établit ensuite un nouveau point d’intérêt.

## Questions encore ouvertes

- L’instrumentation réelle et son seuil sont différés : cette étape teste les transitions au moyen des deux boutons.
- Politique de répétition des vidéos et comportement si aucun autre arbre n’est disponible.

## Tranche #39 livrée

- La page serveur commence par une seule vidéo active et montre « Simuler un visionnage long » et « Zapper ». Le zap reste désactivé jusqu’au ticket #40.
- L’intérêt simulé indique que la vidéo courante devient le point d’intérêt ; le serveur calcule aussitôt une candidate liée, privilégie les sujets communs et transmet son chemin réel.
- Le point d’intérêt et les exclusions de vidéos sont limités à la session en mémoire. Aucune durée de lecture n’est mesurée, aucun like ni profil durable n’est enregistré.
- Si le voisinage local est épuisé, la page garde la dernière vidéo et affiche une fin explicite. La reprise depuis une autre racine relève du ticket #42.

Les feeds exportés en HTML restent précalculés et distincts de cette page interactive. L’ADR 0002 conserve son rôle : la mesure réelle de rétention appartient à l’évaluation ultérieure, pas à ce bouton de test.
