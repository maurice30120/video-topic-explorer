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
- L’élargissement après les zaps s’arrête au rayon de « Découvrir » : 3 hops de sujets. Si aucune candidate locale ne reste à ce rayon, reprendre depuis une autre racine.
- Choisir cette racine au hasard parmi les sujets canoniques vivants qui ont une vidéo encore inédite, hors sujets de la vidéo courante, directions rejetées et racines déjà utilisées. La notion de racine ne dépend pas des composantes connexes du graphe.
- Au redémarrage, garder toutes les exclusions de vidéos déjà montrées, effacer le point d’intérêt, les rejets et le compteur de zaps ; la vidéo choisie n’est pas implicitement appréciée.
- Distinguer le redémarrage d’une transition liée : l’API renvoie `kind: "restart"`, le sujet racine et un `topic_path` vide, sans faux `from`/`to`. Si aucune racine admissible avec vidéo inédite ne reste, terminer avec « Plus aucune vidéo inédite n'est disponible. » sans boucle.
- Prévenir la personne au moment de ce changement : « Tu as exploré les branches disponibles. On repart sur un autre arbre choisi au hasard. »

Exemple : une vidéo sur l’IA intéresse la personne ; elle zappe ensuite les réseaux de neurones : le point d’intérêt est perdu et le parcours tente une direction voisine. Un intérêt pour la robotique établit ensuite un nouveau point d’intérêt.

## Questions encore ouvertes

- L’instrumentation réelle et son seuil sont différés : cette étape teste les transitions au moyen des deux boutons.

## Tranches #39 à #42 livrées

- La page serveur commence par une seule vidéo active et montre « Simuler un visionnage long » et « Zapper ». Chaque action remplace immédiatement la vidéo et affiche un chemin réel.
- L’intérêt simulé fait de la vidéo quittée le nouveau point d’intérêt et privilégie ses sujets communs. Un zap efface ce repère et cherche depuis la vidéo quittée une direction différente de celle qui vient d’être rejetée.
- Le serveur garde les directions rejetées séparément des vidéos déjà montrées ; toutes deux restent limitées à la session en mémoire. Un nouvel intérêt rétablit le repère et efface les rejets précédents.
- Chaque zap consécutif augmente d’un hop le rayon autour des sujets non rejetés de la vidéo courante, jusqu’à 3 hops. Un intérêt remet ce rayon à sa valeur locale et efface les directions rejetées.
- Quand ce rayon local est épuisé, le serveur choisit aléatoirement un sujet canonique vivant qui mène à une vidéo non montrée et différente des directions épuisées. Cette entrée peut se trouver dans la même composante du graphe : aucun arbre n’est déduit des composantes.
- La réponse HTTP et la page identifient séparément cette reprise et sa racine, sans fabriquer de chemin de sujets. Les tests injectent un générateur aléatoire reproductible ; en production, le choix reste aléatoire.
- Le point d’intérêt, les directions rejetées et le compteur de zaps sont réinitialisés à la reprise, tandis que les vidéos montrées restent exclues. Un nouvel intérêt peut alors créer un point d’intérêt à partir de la vidéo reprise.
- Si aucune racine avec vidéo inédite ne reste, la page conserve la dernière vidéo, désactive les deux actions et affiche une fin explicite. Aucune durée de lecture réelle, aucun like ni profil durable n’est enregistré.

Les feeds exportés en HTML restent précalculés et distincts de cette page interactive. L’ADR 0002 conserve son rôle : la mesure réelle de rétention appartient à l’évaluation ultérieure, pas à ce bouton de test.
