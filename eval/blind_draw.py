"""Tirage d'ordre aléatoire figé pour le test en aveugle (eval/order.json).

Génère le protocole complet, sans discipline manuelle (user story 18) :
- sélectionne ~5 points de départ (déterministe : liste triée des départs
  éligibles échantillonnée par le RNG seedé ; un départ est éligible si ses
  deux listes existent et ont toutes la même longueur : la longueur d'une
  liste ne doit jamais révéler son origine),
- construit les deux listes par départ via les seams du moteur
  (baseline() et parcours()) : jusqu'à 4 suggestions après le point de
  départ, la même longueur maximale pour les deux origines,
- masque les explications : order.json ne contient que le départ et les
  vidéos (id, titre) — jamais l'origine ni les chemins de sujets,
- tire et fige l'ordre de présentation des 10 listes (lettres A..J),
- écrit eval/order.json (matériel aveugle) et eval/mapping.json (enveloppe
  scellée : lettre → {start, origine}, lue uniquement par reveal.py).
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vte.corpus import load_corpus
from vte.graph_engine import PathfindingError, baseline, parcours

SUGGESTIONS = 4
ORIGINES = ("baseline", "parcours")
RAYON_PARCOURS = 3
"""Rayon du parcours sensible à la rétention dans le test de valeur.

L'ADR-0001 (amendée 2026-10-24) : le parcours sensible à la rétention
prend la place de l'ancien parcours élargi du barème initial. L'axe
CLI/éval est le parcours complet au rayon explicite 3 — le rayon de
« passer vite », celui qui teste l'hypothèse originale de découverte
par chemins.
"""


def eligible_starts(corpus: dict) -> list[str]:
    """Départs triés dont les deux listes existent et ont la même longueur.

    Deux listes de longueurs différentes révéleraient l'origine au
    scoreur en aveugle (liste courte = run partiel) : de tels départs sont
    exclus du protocole.
    """
    eligible = []
    for video in corpus["videos"]:
        start = video["id"]
        try:
            lengths = {len(_blind_list(corpus, start, origine)[:SUGGESTIONS]) for origine in ORIGINES}
        except PathfindingError:
            continue
        if len(lengths) == 1 and 0 not in lengths:
            eligible.append(start)
    return sorted(eligible)


def _blind_list(corpus: dict, start: str, origine: str) -> list[dict]:
    by_id = {video["id"]: video for video in corpus["videos"]}
    if origine == "baseline":
        ids = baseline(corpus, start)[:SUGGESTIONS]
    else:
        ids = parcours(corpus, start, RAYON_PARCOURS).videos[1:1 + SUGGESTIONS]
    return [{"id": vid, "title": by_id[vid]["title"]} for vid in ids]


def build_protocol(corpus: dict, seed: int, starts: list[str] | None = None, count: int = 5) -> tuple[dict, dict]:
    """Fonction pure : (corpus figé, graine) → (ordre aveugle, correspondance)."""
    rng = random.Random(seed)
    if starts is None:
        pool = eligible_starts(corpus)
        if len(pool) < count:
            raise SystemExit(
                f"pas assez de départs éligibles : {len(pool)} trouvé(s), {count} requis"
            )
        starts = rng.sample(pool, count)
    for start in starts:
        lengths = {len(_blind_list(corpus, start, origine)[:SUGGESTIONS]) for origine in ORIGINES}
        if len(lengths) != 1 or 0 in lengths:
            raise SystemExit(
                f"départ {start!r} : listes de longueurs différentes {sorted(lengths)} ; "
                "la longueur ne doit pas révéler l'origine ; choisissez un départ éligible"
            )

    slots = [{"start": start, "origine": origine} for start in starts for origine in ORIGINES]
    rng.shuffle(slots)
    letters = [chr(ord("A") + i) for i in range(len(slots))]

    order = {
        "seed": seed,
        "starts": list(starts),
        "order": letters,
        "letters": {
            letter: {
                "start": slot["start"],
                "videos": _blind_list(corpus, slot["start"], slot["origine"]),
            }
            for letter, slot in zip(letters, slots)
        },
    }
    mapping = {letter: {"start": slot["start"], "origine": slot["origine"]} for letter, slot in zip(letters, slots)}
    return order, mapping


def blind_draw(corpus_path: str, seed: int, out_path: str, mapping_path: str,
               starts: list[str] | None = None, count: int = 5) -> dict:
    corpus = load_corpus(corpus_path)
    order, mapping = build_protocol(corpus, seed=seed, starts=starts, count=count)
    Path(out_path).write_text(json.dumps(order, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(mapping_path).write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return order


def present(order: dict) -> str:
    """Matériel présenté au scoreur : ordre figé, origines masquées."""
    lines = []
    for letter in order["order"]:
        payload = order["letters"][letter]
        lines.append(f"Liste {letter} — départ : {payload['start']}")
        for rank, video in enumerate(payload["videos"], 1):
            lines.append(f"  {rank}. {video['title']} ({video['id']})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tirage d'ordre aléatoire figé (aveugle)")
    parser.add_argument("corpus")
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--count", type=int, default=5, help="nombre de points de départ (~5)")
    parser.add_argument("--starts", default=None, help="départs explicites 'id1,id2,...' (sinon tirage seedé)")
    parser.add_argument("--out", default="eval/order.json")
    parser.add_argument("--mapping", default="eval/mapping.json")
    args = parser.parse_args()
    starts = args.starts.split(",") if args.starts else None
    blind_draw(args.corpus, seed=args.seed, out_path=args.out, mapping_path=args.mapping,
               starts=starts, count=args.count)
    order = json.loads(Path(args.out).read_text(encoding="utf-8"))
    print(present(order))
    print(f"\nOrdre figé dans {args.out} ; correspondance scellée dans {args.mapping} (ne pas ouvrir avant la révélation).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
