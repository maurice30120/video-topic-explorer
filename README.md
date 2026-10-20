# Video Topic Explorer — MVP

Parcours explicable de vidéos YouTube dans un graphe de sujets. Pipeline Python local, déterministe, auditable. Spécification : [docs/MVP.md](docs/MVP.md), issue #2.

## Installation

```bash
pip install -e ".[extract,render,test]"   # ou : pip install networkx pytest
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
python -m vte.cli graph data/corpus_real.json --run data/runs/demo.json --out out/graphe.png
python -m vte.cli baseline data/corpus_real.json --start ghnY4S8unMM
```

## Démarrage rapide (corpus de démonstration fictif)

```bash
python scripts/make_demo_corpus.py                 # ~35 vidéos fictives en 6 clusters + ponts
python -m vte.cli run data/corpus_demo.json --start vid-001 --mode decouvrir --out data/runs/demo.json
```

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
