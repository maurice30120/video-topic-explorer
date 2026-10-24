## Problem Statement

La personne veut découvrir des vidéos en parcourant leurs sujets : s’attarder doit approfondir l’exploration, zapper doit permettre d’essayer ailleurs. Le feed précalculé et le panneau qui ajoute des suggestions en fin de liste ne réorientent pas immédiatement la prochaine vidéo. Une grille d’arrivée ajoute un choix préalable alors que le zap doit suffire à explorer.

## Solution

Démarrer directement avec une vidéo à l’écran. Deux boutons sous cette vidéo permettent de tester le parcours : « Simuler un visionnage long » et « Zapper ». Chaque action affiche immédiatement la prochaine vidéo.

Le visionnage long simulé établit la vidéo comme point d’intérêt et privilégie une prochaine vidéo partageant ses sujets. Chaque nouvel intérêt déplace ce repère : l’exploration progresse de proche en proche au lieu de rester attachée au départ.

Un zap fait perdre le point d’intérêt actif et cherche une branche voisine de la vidéo quittée, en évitant la direction rejetée. Plusieurs zaps élargissent progressivement l’exploration. Sans intérêt actif, le parcours continue à faire découvrir des sujets ; un nouvel intérêt rétablit un repère.

Quand les branches accessibles sont épuisées, repartir d’un autre arbre choisi au hasard à la racine et afficher : « Tu as exploré les branches disponibles. On repart sur un autre arbre choisi au hasard. »

## User Stories

1. En tant que personne découvrant le produit, je veux arriver directement sur une vidéo, afin de commencer sans choisir dans une grille.
2. En tant que personne explorant les sujets, je veux une seule vidéo active à l’écran, afin de suivre clairement le parcours.
3. En tant que personne testant le produit, je veux un bouton « Simuler un visionnage long » sous la vidéo, afin de manifester un intérêt sans attendre.
4. En tant que personne testant le produit, je veux un bouton « Zapper » sous la vidéo, afin de déclencher explicitement l’autre comportement.
5. En tant que personne testant le produit, je veux que les deux boutons agissent sur la vidéo actuelle, afin de comprendre la cause de chaque transition.
6. En tant que personne intéressée par une vidéo, je veux que la toute prochaine vidéo partage au moins un de ses sujets, afin de continuer dans la même direction lorsque le corpus le permet.
7. En tant que personne intéressée par une vidéo, je veux privilégier les candidates ayant le plus de sujets communs, afin de percevoir l’approfondissement.
8. En tant que personne explorant une branche, je veux que chaque nouvelle vidéo appréciée devienne le point d’intérêt, afin de progresser au-delà du sujet initial.
9. En tant que personne testant le parcours, je veux que la prochaine vidéo soit recalculée après mon action, afin qu’une suggestion prévue ne retarde pas l’adaptation.
10. En tant que personne zappant une vidéo, je veux perdre le point d’intérêt actif, afin que mon désintérêt change effectivement l’orientation.
11. En tant que personne zappant une vidéo, je veux essayer une branche voisine, afin de découvrir une autre direction plutôt que poursuivre celle que je rejette.
12. En tant que personne zappant plusieurs vidéos, je veux élargir progressivement la recherche, afin de sortir d’une zone qui ne m’intéresse pas.
13. En tant que personne n’ayant encore apprécié aucune vidéo, je veux pouvoir explorer par zaps successifs, afin de trouver un premier point d’intérêt.
14. En tant que personne retrouvant une vidéo intéressante après des zaps, je veux établir un nouveau point d’intérêt, afin de reprendre l’approfondissement depuis celle-ci.
15. En tant que personne ayant épuisé les branches disponibles, je veux repartir depuis un autre arbre choisi au hasard à la racine, afin de continuer la découverte.
16. En tant que personne changeant automatiquement d’arbre, je veux être prévenue par un message visible, afin de comprendre le changement de sujet.
17. En tant que personne explorant le graphe, je veux voir les chemins de sujets réels lors des transitions liées, afin de comprendre le rapport entre les vidéos.
18. En tant que personne changeant d’arbre, je veux que le redémarrage soit présenté comme tel, afin qu’aucun lien thématique inexistant ne soit inventé.
19. En tant que personne testant le produit, je veux que chaque clic ne produise qu’une seule transition, afin que les résultats restent lisibles même pendant le chargement.
20. En tant que personne confrontée à une erreur de chargement, je veux un message compréhensible et pouvoir réessayer, afin de poursuivre sans perdre le contexte de la vidéo actuelle.
21. En tant que personne évaluant le produit, je veux tester ces comportements sans temps de visionnage réel, afin de comparer rapidement intérêt et zap.
22. En tant que personne maintenant le produit, je veux vérifier les enchaînements via l’interface HTTP publique, afin de tester leur résultat sans dépendre de détails internes.

## Implementation Decisions

- Réutiliser le serveur local, son contrat JSON de prochaine étape et le moteur de graphe existants. Le feed servi devient une expérience à une vidéo active ; ne pas ajouter d’écran initial obligatoire de sélection.
- Centraliser la politique d’orientation du parcours : vidéo actuelle, point d’intérêt actif ou absent, vidéos déjà proposées, directions essayées et zaps successifs. Éviter une politique concurrente dans le navigateur.
- L’action d’intérêt établit la vidéo quittée comme point d’intérêt avant de calculer la prochaine vidéo. L’action zap retire ce repère avant de calculer la prochaine vidéo. La correction finale de l’utilisateur prime sur la règle antérieure de conservation du point d’intérêt.
- Le bouton d’intérêt est un outil de simulation de rétention élevée, pas un like permanent ni une nouvelle collecte d’appréciations.
- La recherche après intérêt privilégie les sujets communs avec la vidéo quittée. Après zap, chercher une autre direction liée à cette vidéo ; ne pas continuer à utiliser un ancien point d’intérêt actif. Les zaps répétés élargissent le voisinage exploré.
- Distinguer les directions déjà rejetées des vidéos déjà proposées : changer de branche ne peut pas se réduire au choix d’une autre vidéo du même sujet rejeté.
- Le graphe biparti vidéo–sujet reste la source de vérité. « Arbre » et « racine » désignent ici l’entrée dans une autre direction thématique ; ne pas supposer que chaque arbre correspond à une composante déconnectée, car les branches du corpus de référence sont reliées par des ponts.
- Pour le redémarrage, choisir au hasard une autre entrée thématique disponible dans le corpus, différente de la direction épuisée. Utiliser les sujets canoniques et les éventuelles métadonnées de branches ; ne pas fabriquer une hiérarchie de sujets au moyen d’un modèle génératif.
- Le hasard doit être contrôlable pendant les tests, sans imposer aux tests une racine précise en production.
- Un changement d’arbre réinitialise le point d’intérêt et l’état local des directions rejetées. Il ne simule pas une appréciation de la première vidéo du nouvel arbre.
- Conserver les exclusions de vidéos de la session déjà prévues par la spécification antérieure, sans les interpréter comme des preuves d’intérêt.
- Afficher le message de changement d’arbre lors de la transition concernée. Les transitions liées portent un chemin réel ; le redémarrage est signalé séparément, sans faux chemin.
- Pendant une demande de prochaine vidéo, empêcher les doubles actions concurrentes. En cas d’erreur, ne pas avancer visuellement vers une vidéo inexistante.
- Adapter les tests et documents qui imposent un panneau initial de plusieurs cartes ou qui confondent visibilité et lecture effective. Ne pas supprimer les interfaces CLI ou modifier l’évaluation historique dans cette fonctionnalité.

## Testing Decisions

- Points de test validés par l’utilisateur : interface HTTP publique existante pour la sélection et les transitions, complétée par une vérification dans le navigateur des boutons, du remplacement de la vidéo et du message.
- Préférer cette seule frontière automatisée principale : serveur éphémère, corpus figé de test, requêtes HTTP successives portant les événements d’intérêt et de zap. Aucun navigateur automatisé supplémentaire n’est requis pour cette étape.
- Un bon test vérifie les résultats observables : prochaine vidéo, sujets partagés, changement de direction, perte ou établissement du point d’intérêt, message de redémarrage et gestion des erreurs. Il ne teste pas les noms de fonctions, le contenu textuel du JavaScript ou les minuteries internes.
- Art antérieur : tests HTTP du serveur et de prochaine étape utilisant un serveur en thread sur un port éphémère ; fixtures de corpus chaîné et riche ; corpus arbre et vérification indépendante des chemins dans les sujets du JSON.
- Couvrir : arrivée sans grille ; intérêt puis intérêt avec déplacement du repère ; intérêt puis zap avec perte du repère ; zaps sans intérêt initial ; zaps répétés et élargissement ; nouvel intérêt après zap ; épuisement local puis autre entrée aléatoire avec message ; erreur récupérable.
- Concevoir une fixture où les choix de l’ancien point d’intérêt et de la vidéo zappée divergent, afin de prouver que le zap retire réellement l’ancien repère.
- Pour le redémarrage aléatoire, vérifier l’appartenance à un ensemble de racines admissibles et l’exclusion de la direction épuisée ; contrôler le hasard pour rendre les tests reproductibles.
- Vérifier indépendamment les chemins thématiques dans le corpus. Un redémarrage ne doit pas être présenté comme une transition liée si aucun chemin n’est fourni.
- Vérifier manuellement dans le navigateur qu’une seule vidéo est active, que chaque bouton produit une transition immédiate et que le message de changement d’arbre est visible. Cette vérification complète les tests HTTP, qui ne prouvent pas le fonctionnement du JavaScript.

## Out of Scope

- Mesure réelle du temps de lecture, seuil de rétention, collecte analytique ou persistance d’un profil utilisateur.
- Grille de sélection initiale, sélecteur thématique obligatoire, likes, notes ou personnalisation intersessions.
- Nouvelle taxonomie hiérarchique, extraction en direct, recommandations génératives ou modification des vidéos du corpus.
- Réécriture globale des modes, des commandes CLI et du protocole d’évaluation ; modification du seuil go/no-go pré-engagé.
- Tests navigateur automatisés et refonte esthétique indépendante du parcours.
- Bouton « Recommencer » et politique de réutilisation du corpus entièrement épuisé : proposés pendant l’entretien, mais non confirmés. Si aucune autre entrée admissible n’existe, conserver une fin honnête explicite, sans boucle automatique, comme garde-fou hérité.

## Further Notes

- Cette spécification synthétise les choix du 24 octobre 2026, y compris la correction finale : « un zap compte comme une perte de point d’intérêt ».
- Elle remplace la proposition d’entrée par grille de #37 pour le parcours visé. Elle ne ferme ni ne modifie automatiquement ce ticket.
- Elle révise les parties de #27 relatives à l’influence de la dernière carte, au panneau et à la fin locale : état explicite de point d’intérêt, boutons de simulation et reprise aléatoire après épuisement local. Les tickets #28 à #35 doivent être lus avec ces différences avant implémentation ; ils ne sont pas réécrits par cette publication.
- L’ADR 0002 conserve son rôle : aucun signal réel ni mesure analytique n’est collecté ici. L’ADR 0001 et ses critères d’évaluation ne sont pas changés.
- La non-répétition reste un garde-fou hérité de #27. La dernière proposition concernant le redémarrage manuel après épuisement de tout le corpus n’a pas reçu de confirmation ; ne pas la présenter comme une décision validée.
- Les décisions produit de l’entretien sont complétées ici par des choix techniques proposés pour rendre l’implémentation testable, notamment l’état de session, le contrôle du hasard et la protection contre les doubles requêtes.
