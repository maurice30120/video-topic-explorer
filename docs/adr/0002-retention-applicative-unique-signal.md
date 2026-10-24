# Rétention applicative comme unique signal d'appréciation

Dans le feed, la vidéo se regarde dans la page via le lecteur intégré. Le temps de visionnage effectif — la **rétention applicative** — est le signal implicite d'appréciation d'une vidéo : rester longtemps, c'est aimer ; passer vite, c'est ne pas aimer. Face à l'alternative du signal explicite (like, note, étoile), l'arbitrage retient le signal implicite : il ne demande aucune action au curioeur, ne casse pas le rythme du défilement, et mesure ce que la personne fait plutôt que ce qu'elle déclare. **Aucun like ni note n'est collecté ; YouTube Analytics est écarté** (donnée propriétaire, indisponible pour des vidéos que le curioeur ne possède pas). **Aucune collecte n'a lieu dans ce MVP** : le site est statique, sans backend ; la mesure de la rétention applicative appartient à l'axe évaluation.

## Conséquences

- Le choix est difficile à inverser : toute donnée collectée plus tard deviendrait inutilisable en changeant de signal. L'instrumentation future doit donc mesurer le temps de visionnage dans la page, pas un autre signal.
- Aucune interface de like ou de note à concevoir ; le feed livre l'expérience de lecture, pas la mesure.
- La rétention applicative étant observée dans la page, YouTube Analytics ne peut jamais s'y substituer, même comme source future.
- Le terme est défini dans `GLOSSARY.md` ; la collecte (instrumentation, stockage, agrégation) est hors périmètre de ce MVP et relève de l'axe évaluation.
