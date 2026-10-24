# Video Topic Explorer

Découverte de vidéos YouTube par des chemins entre sujets dans un graphe biparti vidéo-sujet. Le produit explique chaque transition ; il ne prédit pas les goûts.

## Language

**Sujet** :
Un concept extrait d'une vidéo, avec un libellé canonique et ses alias bruts conservés pour audit.
_Avoid_ : thème, tag, catégorie

**Transition** :
Une paire ordonnée de vidéos consécutives dans un parcours, plus l'ensemble des sujets réellement présents sur le chemin entre elles dans le graphe.
_Avoid_ : recommandation, saut

**Parcours** :
Une chaîne ordonnée de vidéos distinctes, où chaque vidéo partage un sujet (direct ou via un sujet intermédiaire) avec la précédente. Jusqu'à cinq vidéos au MVP.
_Avoid_ : liste, playlist, séquence

**Approfondir** :
Le mode qui parcourt le graphe en restant dans le voisinage immédiat du point de départ (rayon de 1 hop de sujets) en suivant la branche : chaque extension privilégie la candidate qui partage le plus de sujets avec la vidéo courante.
_Avoid_ : explorer en profondeur, mode focus

**Découvrir** :
Le mode qui parcourt le graphe en s'éloignant progressivement du point de départ (rayon de 2 à 3 hops de sujets) tout en gardant des transitions explicables : le saut de branche arrive tôt, chaque extension privilégie la candidate qui apporte le plus de sujets nouveaux par rapport à la vidéo courante.
_Avoid_ : mode surprise, mode aléatoire

**Baseline** :
Les vidéos partageant au moins un sujet avec le point de départ, triées par nombre de sujets communs décroissant. C'est la liste thématique honnête contre laquelle le graphe est comparé.
_Avoid_ : liste classique, contrôle

**Corpus** :
L'ensemble figé de vidéos, leurs métadonnées et leurs sujets extraits, stocké en JSON local. La source de vérité de tous les parcours. Figé signifie par version : toute réextraction crée une nouvelle version du corpus, jamais une mise à jour continue du corpus en cours d'évaluation.
_Avoid_ : dataset, catalogue, corpus vivant

**Extraction** :
La classification unique, par Gemini, des 3 à 5 sujets d'une vidéo à partir des métadonnées fournies manuellement. Son résultat est figé dans le corpus avec sa provenance ; aucune extraction ne survient pendant les parcours.
_Avoid_ : scraping, analyse automatique de la vidéo, appel LLM en cours de parcours


**Chemin de sujets** :
La suite ordonnée de sujets réellement présents dans le graphe entre deux vidéos d'une transition, affichée telle quelle (ex. `Roslyn → Compilateurs → LLVM`). Jamais rédigée par Gemini.
_Avoid_ : justification, explication générée

**Sujet mort** :
Un sujet associé à une seule vidéo. Présent dans le JSON et le graphe visuel, mais exclu des candidats de parcours car il ne peut créer aucune transition.
_Avoid_ : sujet orphelin, cul-de-sac

**Rétention applicative** :
Le temps de visionnage effectif d'une vidéo par un lecteur du parcours, observé dans la page elle-même. C'est le signal implicite d'appréciation d'une vidéo : rester longtemps, c'est aimer ; passer vite, c'est ne pas aimer.
_Avoid_ : like, note, étoile, rétention YouTube Analytics

**Point d’intérêt** :
Une vidéo dont le visionnage a manifesté un intérêt, servant de repère actif pour approfondir les sujets. Un zap fait perdre ce point d’intérêt.
_Avoid_ : profil de goûts, favori

**Branche voisine** :
Une direction d’exploration liée aux sujets de la vidéo quittée, différente de celle qui vient d’être zappée.
_Avoid_ : vidéo aléatoire, sujet sans rapport
