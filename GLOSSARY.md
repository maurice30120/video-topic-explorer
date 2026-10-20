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
Le mode qui parcourt le graphe en restant dans le voisinage immédiat du point de départ (rayon de 1 hop de sujets).
_Avoid_ : explorer en profondeur, mode focus

**Découvrir** :
Le mode qui parcourt le graphe en s'éloignant progressivement du point de départ (rayon de 2 à 3 hops de sujets) tout en gardant des transitions explicables.
_Avoid_ : mode surprise, mode aléatoire

**Baseline** :
Les vidéos partageant au moins un sujet avec le point de départ, triées par nombre de sujets communs décroissant. C'est la liste thématique honnête contre laquelle le graphe est comparé.
_Avoid_ : liste classique, contrôle

**Corpus** :
L'ensemble figé d'environ 30 vidéos, leurs métadonnées et leurs sujets extraits, stocké en JSON local. La source de vérité de tous les parcours.
_Avoid_ : dataset, catalogue

**Chemin de sujets** :
La suite ordonnée de sujets réellement présents dans le graphe entre deux vidéos d'une transition, affichée telle quelle (ex. `Roslyn → Compilateurs → LLVM`). Jamais rédigée par Gemini.
_Avoid_ : justification, explication générée

**Sujet mort** :
Un sujet associé à une seule vidéo. Présent dans le JSON et le graphe visuel, mais exclu des candidats de parcours car il ne peut créer aucune transition.
_Avoid_ : sujet orphelin, cul-de-sac
