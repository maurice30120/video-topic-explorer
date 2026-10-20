# MVP — Exploration de vidéos par graphe de sujets

**Version :** 0.1 — 20 octobre 2026  
**Statut :** spécification du premier essai, aucune implémentation requise à ce stade.  
**Confidentialité :** dépôt privé ; aucune préférence réelle ou clé API versionnée.

## 1. Hypothèse à tester

Un parcours explicable dans un graphe de sujets permet-il de découvrir des vidéos de façon plus cohérente, enrichissante et surprenante qu'une liste classique regroupée par thème ?

Il ne s'agit **pas** de prédire si une vidéo plaira à une personne. Le produit doit montrer comment des sujets sont reliés et conduire à des vidéos qui illustrent leur voisinage.

## 2. Démonstration minimale

À partir d'environ **30 vidéos YouTube** dont les sujets se croisent :

1. Gemini extrait **3 à 5 sujets** par vidéo depuis le titre, la description et, si disponible, une transcription.
2. Un traitement simple normalise les synonymes et variantes évidentes.
3. NetworkX construit un graphe **biparti : vidéo ↔ sujet**. Les associations proviennent du corpus.
4. L'utilisateur choisit un sujet ou une vidéo de départ et un des deux modes :
   - **Approfondir** : rester près du point de départ et explorer des sous-thèmes proches.
   - **Découvrir** : progresser vers des sujets moins proches tout en gardant des liens explicables.
5. Une page HTML présente un **enchaînement ordonné de cinq vidéos maximum**, sans doublon, avec une explication de chaque transition.
6. Une option permet d'**afficher le graphe** correspondant ; il sert à visualiser l'algorithme, pas à constituer la navigation principale.
7. On compare les résultats à une baseline : **une simple liste thématique** construite sur le même corpus.

Exemple *illustratif uniquement* : C# → Roslyn → Compilateurs → LLVM → Rust. Ce chemin ne doit pas être codé en dur et n'est pas garanti par le jeu de données.

## 3. Entrées

- Un fichier de départ regroupant environ 30 URL/identifiants de vidéos.
- Métadonnées minimales : identifiant, URL, titre ; description ou transcription si accessibles.
- Un mode explicite : Approfondir ou Découvrir.
- Un point de départ explicite : sujet ou vidéo.

Le premier essai peut fonctionner avec une collecte manuelle de métadonnées si l'accès YouTube est difficile. Ne pas bloquer le test sur la récupération des transcriptions.

## 4. Traitements

### Extraction

Gemini produit pour chaque vidéo une liste de 3 à 5 sujets pertinents et, si possible, une courte justification fondée sur les données fournies. Sauvegarder immédiatement les résultats pour ne pas rappeler le LLM à chaque parcours.

### Normalisation

Fusionner seulement les alias évidents (par exemple « C Sharp » et « C# »). Conserver le libellé brut et le libellé canonique afin de pouvoir auditer ou corriger les regroupements.

### Construction du graphe

Chaque sujet et chaque vidéo est un nœud distinct. Chaque association extraite devient une arête vidéo-sujet. Les liens entre sujets peuvent être **déduits** du partage de vidéos, mais ne sont pas présentés comme des relations sémantiques certaines. Pas de taxonomie enrichie ni de relations typées complexes au MVP.

### Parcours

Le même graphe sert aux deux modes. Des algorithmes de parcours locaux et simples suffisent au premier test ; le Personalized PageRank n'est **pas** une obligation initiale. Les parcours doivent être reproductibles à corpus, point de départ et paramètres identiques. Une vidéo ne doit pas apparaître deux fois dans une même séquence.

Si une composante est déconnectée ou que cinq suggestions fiables sont impossibles, afficher le parcours partiel et la raison. Ne jamais inventer de transition.

### Explications

Chaque transition affiche les sujets communs ou les sujets intermédiaires réellement présents dans le graphe. La justification peut être contrôlée en affichant le sous-graphe correspondant. Le texte ne doit pas être une rationalisation inventée a posteriori par Gemini.

## 5. Sorties attendues

- Un **JSON local** inspectable : vidéos, sujets normalisés, liens et provenance de l'extraction.
- Une **page HTML minimale** : sélection du point de départ, choix du mode, liste ordonnée et justifications.
- Une **visualisation facultative** du graphe ou du sous-graphe pertinent.
- Des erreurs et limites présentées clairement, sans données fictives cachées.

## 6. Architecture maximale

    ~30 vidéos
       ↓
    Script Python + Gemini (une extraction mise en cache)
       ↓
    JSON local
       ↓
    NetworkX (graphe et deux parcours simples)
       ↓
    HTML minimal + affichage facultatif du graphe

Un script Python lisible (éventuellement réparti en deux ou trois petits fichiers), un JSON et une page HTML suffisent. Pas de base SQL, agent autonome, serveur complexe ni pipeline distribué.

## 7. Règles de comportement

- Le **mode est sélectionné manuellement** ; ne pas inférer l'humeur.
- Ne pas pénaliser un sujet parce qu'une vidéo est ignorée : l'absence de clic n'est pas un jugement négatif.
- La qualité d'une vidéo n'est pas confondue avec la proximité thématique.
- Aucun apprentissage des goûts ni entraînement de modèle pour le MVP.
- Aucune lecture automatique enchaînée n'est requise.
- Les clés API et goûts personnels restent hors Git ; fournir seulement des exemples neutres.

## 8. Vérification de la valeur

Comparer, avec **le même corpus et les mêmes points de départ** :

1. Une liste par sujet commun (baseline).
2. Un parcours **Approfondir**.
3. Un parcours **Découvrir**.

Évaluer qualitativement : cohérence, intérêt des nouveaux sujets, différence perceptible entre les modes, clarté des explications et utilité par rapport à la baseline. Refaire le test depuis plusieurs points de départ.

### Critères d'acceptation

- [ ] Un corpus d'environ 30 vidéos est enrichi et conservé en JSON.
- [ ] 3 à 5 sujets sont extraits par vidéo lorsque les données suffisent ; exceptions visibles.
- [ ] Un seul graphe vidéo-sujet alimente les deux modes.
- [ ] Chaque mode produit jusqu'à cinq vidéos distinctes.
- [ ] Chaque transition est expliquée par des liens **existants et vérifiables**.
- [ ] Le graphe est affichable à la demande, sans encombrer l'écran principal.
- [ ] Les parcours sur JSON figé sont reproductibles **sans appel Gemini**.
- [ ] Une comparaison qualitative avec la baseline permet de décider si l'idée mérite d'être poursuivie.

## 9. Hors périmètre

Entraînement ou fine-tuning ; apprentissage comportemental ; algorithme optimisant le taux de clic ; multi-utilisateurs ; comptes ; historique de visionnage ; ingestion continue ; GraphRAG ; LLM multi-agents ; base de données ; moteur d'embeddings ; application YouTube complète ; lecture automatique ; relations sémantiques typées ; industrialisation.

## 10. Risques et décision finale

Les principaux risques sont la variabilité des concepts extraits, un graphe déconnecté ou trop dense, le manque de vidéos pertinentes et les limites d'accès aux données de YouTube. Garder la sortie brute de Gemini, tester sur JSON figé et éviter les appels multiples limite ces risques.

**Décision go/no-go :** poursuivre seulement si les parcours apportent une valeur sensible par rapport à une simple liste thématique. Dans le cas contraire, revoir l'hypothèse ou la qualité des sujets avant d'enrichir la technologie.
