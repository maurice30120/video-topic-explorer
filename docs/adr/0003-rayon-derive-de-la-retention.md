# Rayon dérivé de la rétention

Le feed proposait deux modes fixes, Approfondir et Découvrir, choisis avant de commencer à regarder ; pendant la lecture, la rétention applicative — le signal d'appréciation de l'[ADR-0002](0002-retention-applicative-unique-signal.md) — n'influençait aucunement le parcours, et changer de branche n'était possible qu'en zappant des cartes aimées, mentant ainsi au signal. Décision : un seul mode, le **parcours sensible à la rétention**. La durée de visionnage de la dernière carte quittée détermine le rayon du pas suivant — mapping binaire : durée ≥ seuil (aimé) → rayon 1, voisinage immédiat ; durée < seuil (pas aimé) → rayon 3, on s'éloigne. Chaque carte oriente le pas suivant, avec sa durée ; l'ordre linéaire des cartes déjà défilées n'oriente jamais rien. Deux canaux restent distincts et le restent : la **rétention** (appréciation, implicite, jamais une action) et la **sortie de branche** (navigation, explicite, ne juge jamais la carte en cours) — la navigation ne ment jamais au signal d'appréciation.

## Alternatives écartées

- **Mapping gradué vs mapping binaire.** Des bandes de durée (rayon 2 intermédiaire) auraient gradué l'éloignement plus finement ; écarté : un seul seuil et deux rayons suffisent à tester l'hypothèse, et une bande intermédiaire n'ajoute rien au jugement aimé / pas aimé. Les bandes graduées restent hors périmètre de ce pivot.
- **Carte pivot vs chaque carte oriente.** Ne faire orienter que la dernière carte au-dessus du seuil (un « pivot ») aurait donné un point d'ancrage stable ; écarté : chaque carte quittée oriente le pas suivant avec sa durée, sinon une suite de cartes zappées laisserait le parcours dans le voisinage d'une carte ancienne.
- **Sortie implicite (zap) vs sortie explicite (commande).** Le zap est le repli implicite, déjà couvert par le mapping (passer vite s'éloigne) ; écarté comme seul mécanisme de changement de branche : il obligerait à zapper des cartes aimées pour partir, mentant au signal d'appréciation. Le changement de branche est donc une commande explicite.
- **Recherche sémantique en texte libre vs sélecteur de sujets réels.** Écarté pour ce pivot : la sortie dirigée passe par le choix explicite d'un sujet canonique réel du corpus dans un sélecteur, jamais un texte libre qui risquerait de viser un sujet inexistant. Sujet mort ou inconnu → erreur explicite, jamais de repli silencieux. La recherche sémantique pourra venir plus tard comme couche additive sur le même contrat (texte libre → proposition de sujets réels → choix explicite).
- **Un canal unique vs deux canaux.** Fusionner navigation et appréciation (le zap dirigerait les deux) a été écarté : apprécier et naviguer sont deux intentions distinctes ; la rétention reste appréciation, la sortie de branche reste navigation.

## Conséquences

- Les modes Approfondir et Découvrir disparaissent du produit, du code (moteur, CLI, panneau) et du glossaire.
- Le rayon devient un paramètre explicite de chaque pas ; l'enum de mode et sa table mode → rayon sont supprimés.
- Une sortie dirigée est un redépart depuis le sujet canonique choisi ; après elle, le pilotage par la durée reprend.
- L'épuisement des candidates est une fin honnête, pas une erreur ; un sujet mort ou inconnu, lui, est une erreur explicite.
- Le seuil (5000 ms) n'est pas changé par cette décision.
- L'[ADR-0001](0001-seuil-go-no-go-pre-engage.md) est amendée par note datée : le parcours sensible à la rétention remplace Découvrir dans le barème go/no-go ; seuil et barème pré-engagés inchangés.
