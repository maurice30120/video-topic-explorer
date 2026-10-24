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

**Parcours sensible à la rétention** :
Le mode unique du feed : la durée de visionnage de la dernière carte quittée décide du rayon du pas suivant. Rester longtemps garde le parcours dans le voisinage immédiat de ce qui est aimé ; passer vite s'en éloigne.
_Avoid_ : Approfondir, Découvrir, mode adaptatif, personnalisation

**Pont** :
Une vidéo dont les sujets relient deux branches du graphe ; c'est elle qui rend le saut de branche possible.
_Avoid_ : passerelle, lien, raccourci

**Saut de branche** :
Une transition qui quitte la branche courante pour une branche voisine en empruntant un pont.
_Avoid_ : zapping, dérive, changement de mode

**Sortie de branche** :
L'action explicite de quitter la branche en cours, dirigée par le choix d'un sujet canonique réel ou non dirigée. C'est un acte de navigation : elle ne juge jamais la carte courante.
_Avoid_ : zap, dislike, changement de mode

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
Le temps de visionnage effectif d'une carte par le curioeur, observé dans la page elle-même. C'est le signal implicite d'appréciation : rester longtemps, c'est aimer ; passer vite, c'est ne pas aimer.
_Avoid_ : like, note, étoile, rétention YouTube Analytics

**Fin honnête** :
L'arrêt explicite du feed quand plus aucune candidate ne reste à proposer. Une fin normale du parcours, jamais une erreur.
_Avoid_ : bug, échec, feed vide
