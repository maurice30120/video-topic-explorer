# Video Topic Explorer — MVP

Parcours explicable de vidéos YouTube dans un graphe de sujets. Pipeline Python local, déterministe, auditable. Spécification : [docs/MVP.md](docs/MVP.md), issue #2.

## Installation

```bash
pip install -e ".[extract,render,test]"   # ou : pip install networkx pytest
```

## Commandes courtes

Après `pip install -e .`, la commande `vte` est disponible (`vte serve` lance le serveur local directement). Un `Makefile` offre aussi des cibles courtes :

```bash
make serve   # serveur local : vidéo directe, intérêt simulé, parcours et graphe
make run     # parcours Découvrir depuis la vidéo de départ par défaut
make feed    # feed statique out/site/index.html
make test    # suite pytest
make help    # liste complète
```

## Démarrage rapide (corpus réel de 35 vidéos YouTube vérifiées)

Les 35 vidéos (`data/corpus_real.json`) sont de vraies conférences/tutoriels YouTube,
chaque ID validé via l'oEmbed public. Les sujets (3-5 par vidéo) sont assignés
manuellement depuis les titres publics (provenance `manual-curated`) :
clusters Roslyn/C#, Compilateurs/LLVM, Rust, TypeScript, Machine Learning,
Noyau Linux + ponts inter-clusters.

```bash
python scripts/make_real_corpus.py                                          # régénère data/corpus_real.json
python -m vte.cli run data/corpus_real.json --start ghnY4S8unMM --mode decouvrir --out data/runs/demo.json
python -m vte.cli render data/corpus_real.json --run data/runs/demo.json --out out/parcours.html
python -m vte.cli graph data/corpus_real.json --run data/runs/demo.json --out out/graphe.png  # ou .svg : PNG/SVG selon l'extension
python -m vte.cli baseline data/corpus_real.json --start ghnY4S8unMM
python -m vte.cli feed data/corpus_real.json --out out/site/index.html  # départ par défaut : vte.DEFAULT_START (ghnY4S8unMM)python -m vte.cli stats data/corpus_real.json                                # composantes, sujets morts, densité
python -m vte.cli serve data/corpus_real.json --port 8000                    # page locale : une vidéo et ses actions de parcours
```

## Corpus élargi (57 vidéos : technique + musique, fun, science, économie, jeux)\r\n\r\n`data/corpus_elargi.json` étend le corpus réel avec 22 vidéos YouTube réelles\r\ncouvrant un panel de genres : musique (Rick Astley, Queen, Rick Beato),\r\nfun/culture internet (bill wurtz, « Me at the zoo »), science (3Blue1Brown,\r\nKurzgesagt, Veritasium), économie (CrashCourse, Economics Explained), jeux\r\nvidéo (Game Maker's Toolkit). Chaque ID est validé via l'oEmbed public ;\r\nle panel reste une seule composante connectée via des ponts réels\r\n(« Machine Learning », « Apprentissage », « Tutoriels », « Histoire »,\r\n« Pédagogie », « Mème internet »).\r\n\r\n```bash\r\nmake elargi       # régénère data/corpus_elargi.json\r\nmake elargi-site  # régénère out/site depuis le corpus élargi (feed + parcours + graphe)\r\npython -m vte.cli serve data/corpus_elargi.json --port 8380   # page locale : sélection, parcours, graphe\r\n```\r\n\r\n## Démarrage rapide (corpus de démonstration fictif)

```bash
python scripts/make_demo_corpus.py                 # ~35 vidéos fictives en 6 clusters + ponts
python -m vte.cli run data/corpus_demo.json --start vid-001 --mode decouvrir --out data/runs/demo.json
```

## Provenance des sujets du corpus réel : manuelle aujourd'hui, Gemini pour la prochaine version

**Décision (auditable)** : la version courante de `data/corpus_real.json`
(provenance `manual-curated`, `version 2026-10`) a des sujets **assignés à la
main** depuis les titres publics, pas extraits par Gemini. C'est un substitut
honnête et explicite — chaque sujet porte sa provenance — rendu nécessaire
par le ticket #5 (extraction Gemini) au moment du curatage. Le corpus reste
figé par version ([GLOSSARY.md](GLOSSARY.md), « Corpus ») : une réextraction
crée une **nouvelle version**, jamais une mise à jour du corpus en cours
d'évaluation.

**Le chemin d'extraction est prêt et testé** (`tests/test_extract.py`), sans
être exécuté sur le corpus réel dans cet environnement (pas de
`GEMINI_API_KEY`, pas de SDK installé — aucun appel réseau ici) :

```bash
# 1. Ingestion manuelle des métadonnées (aucune clé API YouTube)
python -m vte.cli ingest mes_videos.json --output data/videos_raw.json

# 2. Extraction Gemini, une seule fois, mise en cache immédiat
#    (GEMINI_API_KEY via variable d'environnement, jamais commise)
export GEMINI_API_KEY=...
python -m vte.cli extract data/videos_raw.json --output data/corpus_gemini.json
```

Pour produire la **prochaine version du corpus** : réutiliser les 35
métadonnées de `data/corpus_real.json` (id, url, titre, chaîne, description)
dans `data/videos_raw.json`, puis lancer `extract` vers un **nouveau fichier**
(ex. `data/corpus_gemini.json`) — pas vers `corpus_real.json`. Chaque sujet
y portera `provenance: {source: gemini, model: ..., version: ...}` ; les
échecs sont flaggés `extraction_error` et jamais acceptés en silence ; le
résultat est figé et jamais rappelé pendant les parcours.

## Flux réel

1. **Ingestion manuelle** (pas de clé API YouTube) :

```bash
python -m vte.cli ingest mes_videos.json --output data/videos_raw.json
```

2. **Extraction Gemini, une seule fois, mise en cache** (require `GEMINI_API_KEY` ; résultat figé dans le corpus, jamais rappelé pendant les parcours) :

```bash
export GEMINI_API_KEY=...
python -m vte.cli extract data/videos_raw.json --output data/corpus.json
```

3. **Parcours** (fonction pure, hors ligne, reproductible) :

```bash
python -m vte.cli run data/corpus.json --start vid-001 --mode approfondir   # rayon 1
python -m vte.cli run data/corpus.json --start vid-001 --mode decouvrir     # rayon 3
```

Chaque parcours produit un `run.json` auditable : départ, mode, rayon, vidéos, chemins de sujets, transitions.

## Évaluation en aveugle (ADR-0001)

```bash
PYTHONPATH=. python eval/blind_draw.py data/corpus.json            # ordre figé → eval/order.json
PYTHONPATH=. python eval/record_scores.py                          # notes sans connaître l'origine
PYTHONPATH=. python eval/reveal.py                                 # go/no-go après notation complète
```

Mapping lettres → origine (baseline / approfondir / decouvrir) : construire `eval/mapping.json` avant la révélation, sans la consulter pendant la notation.

## Tests

```bash
python -m pytest tests/ -q
```

Vocabulaire : [GLOSSARY.md](GLOSSARY.md) si présent ; décisions : [docs/MVP.md](docs/MVP.md), [docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md).
