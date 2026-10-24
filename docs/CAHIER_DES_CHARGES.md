# Cahier des charges — Factory de découverte YouTube par graphe de sujets

**Version :** 0.1 — 20 octobre 2026  
**Nature :** vision produit consolidée. **Ce document ne demande pas d'implémenter immédiatement toutes les fonctionnalités.**  
**Légende :** **[VALIDÉ]** principe convenu ; **[PROPOSÉ]** piste envisagée ; **[À ARBITRER]** choix ouvert.

## 1. Objectif et philosophie

**[VALIDÉ]** Créer une factory de pages d'accueil et de parcours vidéo reposant sur les **sujets et les relations entre contenus**. L'objectif n'est pas de prédire si une personne appréciera telle vidéo ou d'optimiser son temps passé à regarder.

**[VALIDÉ]** Le moteur rend compréhensible **pourquoi** une vidéo conduit à une autre. Il favorise la découverte et permet de moduler la distance thématique.

**[VALIDÉ]** Ne pas confondre la qualité intrinsèque, les intérêts durables et l'humeur du moment. L'utilisateur choisit explicitement son mode ; ignorer une vidéo ne constitue pas une preuve de désintérêt.

## 2. Catalogue et découverte de vidéos

- **[VALIDÉ]** Cible initiale : YouTube, avec des vidéos rattachées à des sujets.
- **[PROPOSÉ]** Sources : URL données manuellement, chaînes, mots-clés et, à terme, découverte automatisée de nouveaux sujets.
- **[PROPOSÉ]** Récupérer identifiant, titre, chaîne, durée, description, date et transcription quand disponibles.
- **[PROPOSÉ]** Dédupliquer par identifiant et mettre en cache les métadonnées et extractions.
- **[À ARBITRER]** Modes d'alimentation régulière, recherche automatique, abonnements aux chaînes, fréquence de régénération de la page.
- **[VALIDÉ]** La fabrique produit des sélections, pas un simple appel à un LLM lui demandant quelles vidéos devraient plaire.

## 3. Graphe de connaissances

### Nœuds

- **[VALIDÉ]** Les concepts ou sujets constituent le centre du graphe. Les vidéos y sont associées.
- **[PROPOSÉ]** D'autres types de nœuds, notamment chaînes, catégories et utilisateurs, ne seront ajoutés que si nécessaires.
- **[VALIDÉ]** Le **graphe de sujets est unique** ; chaque mode correspond à une façon différente de le parcourir.

### Relations

- **[VALIDÉ]** Il faut pouvoir justifier les liens vidéo-sujet.
- **[PROPOSÉ]** À terme, construire des relations explicites entre concepts : spécialisation, utilisation, dépendance, technologie associée, alternative, etc.
- **[PROPOSÉ]** Garder la provenance : vidéo, passage éventuel, modèle d'extraction, version, niveau de confiance et éventuelle correction.
- **[PROPOSÉ]** Distinguer les relations **observées ou extraites** de celles **dérivées par l'algorithme**.
- **[PROPOSÉ]** Normaliser alias et synonymes avec identifiants canoniques ; conserver les termes d'origine.
- **[VALIDÉ]** Ne pas introduire dès le MVP une ontologie complexe. Le graphe biparti vidéo-sujet suffit pour tester l'idée.

### Gemini

- **[VALIDÉ]** Gemini aide à **extraire et identifier les sujets** ; il ne remplace pas l'algorithme de parcours et ne juge pas obligatoirement le goût de l'utilisateur.
- **[PROPOSÉ]** Gemini peut suggérer de nouveaux concepts et des liens, mais ces propositions doivent être auditables et susceptibles d'être corrigées.
- **[VALIDÉ]** Les recommandations doivent s'expliquer par des **chemins vérifiables dans le graphe**, pas par une justification inventée après le classement.

## 4. Navigation et modes

> **Amendement — 2026-10-24 (spec #27).** Les deux modes manuels ci-dessous
> ont disparu du produit : le **parcours sensible à la rétention** les
> remplace — la durée de visionnage de la dernière carte quittée décide du
> rayon du pas suivant ([ADR-0003](adr/0003-rayon-derive-de-la-retention.md)).
> Les items historiques de cette vision ne sont pas réécrits.

- **[VALIDÉ]** Deux modes initiaux :
  - **Approfondir :** explorer des sujets proches et progresser en profondeur.
  - **Découvrir :** passer progressivement vers des sujets voisins puis plus éloignés, en conservant des transitions intelligibles.
- **[VALIDÉ]** Les modes sont choisis explicitement, jamais déduits automatiquement de l'humeur.
- **[PROPOSÉ]** Un parcours peut démarrer à partir d'une vidéo ou d'un sujet.
- **[PROPOSÉ]** L'utilisateur pourra éventuellement bifurquer, rejouer ou relancer un parcours.
- **[À ARBITRER]** Ajouter des modes futurs (par exemple se détendre, science, humour) seulement après validation de l'utilité.
- **[PROPOSÉ]** Après le MVP, étudier des algorithmes comme Personalized PageRank seulement si les parcours simples sont insuffisants.

## 5. Interface utilisateur

- **[VALIDÉ]** Présenter un enchaînement ordonné de vidéos cohérent avec le mode.
- **[VALIDÉ]** Fournir l'explication de chaque transition.
- **[VALIDÉ]** Le graphe est d'abord une **représentation visuelle du mécanisme** ; il n'est pas nécessaire de naviguer dedans pour utiliser l'application.
- **[VALIDÉ]** Une option permet de **visualiser le graphe à la demande**.
- **[PROPOSÉ]** Page d'accueil générée par une factory, regroupant plusieurs modes ou contextes.
- **[PROPOSÉ]** Lecture YouTube intégrée directement à l'interface via le lecteur officiel lorsqu'elle est activée.
- **[À ARBITRER]** Interface finale entre liste façon YouTube, séquence guidée, bouton « explorer depuis cette vidéo », ou combinaison des trois.
- **[À ARBITRER]** Lecture automatique, bifurcations en direct et présentation des vidéos déjà vues.

## 6. Personnalisation et historique

- **[VALIDÉ]** L'humeur du moment ne doit pas être devinée à partir d'un clic manquant.
- **[VALIDÉ]** Ignorer ou interrompre une vidéo ne doit pas dégrader automatiquement son sujet ni son appréciation qualitative.
- **[PROPOSÉ]** Un historique des vidéos visionnées et des favoris pourrait être disponible dans le produit complet.
- **[PROPOSÉ]** Des centres d'intérêt explicites pourraient servir de points de départ sans modifier le graphe objectif des sujets.
- **[À ARBITRER]** Nature des préférences persistées, confidentialité de l'historique et éventuel apprentissage comportemental.
- **[VALIDÉ]** Pas d'entraînement de modèle de préférences pour valider le MVP.

## 7. Contraintes et qualités

- **Explicabilité [VALIDÉ] :** transitions traçables via les sujets et les liens du graphe.
- **Qualité des découvertes [VALIDÉ] :** préserver les chemins utiles même si les sujets sont éloignés.
- **Simplicité [VALIDÉ] :** pas d'usine à gaz avant validation de valeur.
- **Confidentialité [VALIDÉ] :** dépôt initial **privé**, car le projet pourrait contenir des informations sur les goûts personnels.
- **Reproductibilité [PROPOSÉ] :** JSON figé, paramètres explicites et tests sans réappel au LLM.
- **Résilience [PROPOSÉ] :** absence de transcriptions, vidéos indisponibles, concepts ambigus et graphes déconnectés gérés explicitement.
- **Conformité [PROPOSÉ] :** respecter les conditions d'accès aux vidéos et les quotas des API.
- **Économie [PROPOSÉ] :** mise en cache des appels à Gemini ; coût de découverte observable.

## 8. Architecture par phases

### Phase 1 : MVP — seul périmètre à développer initialement

**[VALIDÉ]** 30 vidéos ; extraction de 3 à 5 sujets par vidéo avec Gemini ; graphe biparti dans **Python/NetworkX** ; **JSON local** ; deux modes ; **parcours de cinq vidéos** ; explications ; **HTML minimal** et vue du graphe facultative.

Pas de BDD, orchestration multi-agents, entraînement, ingestion continue, index vectoriel ni PageRank personnalisé requis.

La référence opérationnelle pour cette phase est [MVP.md](MVP.md).

### Phase 2 : après preuve de valeur

**[PROPOSÉ]** Enrichir les relations sémantiques ; permettre de corriger les extractions ; naviguer depuis les vidéos, bifurquer, conserver des préférences explicites ; ingestion incrémentale et stockage persistant si justifiés.

### Phase 3 : fonctions facultatives

**[PROPOSÉ]** Catalogue élargi, rafraîchissement autonome, moteur de classement amélioré, visualisation avancée, génération de plusieurs pages d'accueil et déploiement.

Aucune de ces phases n'est engagée avant le retour sur le MVP.

## 9. Projets étudiés

- **NetworkX :** retenu pour le graphe et les parcours initiaux.
- **Graphology / Sigma.js :** options si le navigateur devient central pour l'algorithme ou la visualisation.
- **Gorse / Metarank :** moteurs de recommandation et de classement plus larges, non nécessaires au test.
- **Innie :** utile comme exemple d'ingestion et classification, mais son apprentissage des goûts et son graphe d'idées *à l'intérieur d'une vidéo* ne correspondent pas à notre objectif principal.
- **ViewTube / Insidious :** sources d'inspiration pour la lecture, sans importer leur architecture complète au MVP.

Les concepts d'autres projets peuvent inspirer la conception ; réutiliser du code impose le respect des licences applicables.

## 10. Validation produit et décisions ouvertes

**Succès attendu :** le graphe doit produire des **découvertes thématiques intéressantes et explicables**, avec une différence visible entre les modes. À corpus identique, comparer avec une liste thématique simple ; tester plusieurs points de départ.

| Sujet | Statut |
| --- | --- |
| Graphe de sujets avec vidéos rattachées | **VALIDÉ** |
| Prédiction automatique de l'attrait d'une vidéo | **Hors objectif principal** |
| Gemini pour extraire 3 à 5 sujets | **VALIDÉ pour le MVP** |
| Modes manuels Approfondir / Découvrir | **VALIDÉ** |
| Graphe visualisable à la demande | **VALIDÉ** |
| Séquence de cinq vidéos pour le MVP | **VALIDÉ** |
| Python, NetworkX, JSON, HTML minimal | **VALIDÉ** |
| Personalized PageRank | **Non nécessaire initialement** |
| Relation sémantique typée entre concepts | **Option après MVP** |
| UI finale et lecture automatique | **À ARBITRER** |
| Dépôt privé | **VALIDÉ** |

## 11. Garde-fou

**Toute fonctionnalité nouvelle devra résoudre un problème observé dans le MVP ou améliorer un critère de valeur mesuré.** Une sophistication purement technique n'est pas un critère suffisant.
