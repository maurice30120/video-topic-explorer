# Video Topic Explorer — exploration YouTube par graphe de sujets

**Statut : spécifications uniquement.** Aucun moteur de recommandation n'est encore implémenté.

## Pourquoi ce projet ?

L'objectif est de découvrir des vidéos par des **chemins entre sujets**, et non de prédire si elles vont plaire. Un même graphe pourra servir à des modes choisis explicitement : **Approfondir** ou **Découvrir**. Chaque transition doit être explicable.

## Documents

- [MVP — expérience minimale](docs/MVP.md) : **périmètre prioritaire** pour vérifier que les parcours par graphe apportent de la valeur.
- [Cahier des charges — vision produit](docs/CAHIER_DES_CHARGES.md) : principes validés, propositions et questions ouvertes, sans engagement d'implémentation immédiate.

## MVP en bref

1. Environ 30 vidéos YouTube sur des sujets liés.
2. Gemini extrait 3 à 5 sujets par vidéo.
3. Un JSON local et NetworkX constituent un graphe vidéo ↔ sujet.
4. Deux modes manuels parcourent **le même graphe** : Approfondir et Découvrir.
5. Une page HTML affiche jusqu'à cinq vidéos ordonnées et explique leurs transitions.
6. Le graphe est visible **sur demande** pour comprendre l'algorithme.
7. Comparaison avec une liste classique de vidéos par thème.

**Stack cible MVP :** Python, Gemini, NetworkX, JSON, HTML minimal. Pas de base SQL, d'agents, d'apprentissage de préférences ni d'autoplay.

## Vie privée

Le dépôt est créé **privé**. Ne jamais committer de clé API, de données de visionnage personnelles ou de préférences réelles sans décision explicite. Utiliser des variables d'environnement pour les secrets et des données fictives pour les tests partagés.

## Principes

- Explicabilité fondée sur des liens **réels** du graphe, pas sur une justification inventée.
- Parcours déterministes avec un corpus JSON figé.
- Ne pas interpréter le fait d'ignorer une vidéo comme un désintérêt durable.
- D'abord démontrer l'utilité, ensuite seulement complexifier.

*Spécifications issues des échanges du 20 octobre 2026.*
