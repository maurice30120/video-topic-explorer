"""Tirage d'ordre aléatoire figé pour le test en aveugle (eval/order.json).

Génère le protocole complet, sans discipline manuelle (user story 18) :
- sélectionne ~5 points de départ (déterministe : liste triée des départs
  éligibles échantillonnée par le RNG seedé ; un départ est éligible s'il
  produit au moins une suggestion dans chacune des trois listes),
- construit les trois listes par départ via les seams du moteur
  (baseline() et parcours()) : jusqu'à 4 suggestions après le point de
  départ, la même longueur maximale pour les trois origines,
- masque les explications : order.json ne contient que le départ et les
  vidéos (id, titre) — jamais le mode, l'origine ni les chemins de sujets,
- tire et fige l'ordre de présentation des 15 listes (lettres A..O),
- écrit eval/order.json (matériel aveugle) et eval/mapping.json (enveloppe
  scellée : lettre → {start, kind}, lue uniquement par reveal.py).
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
KINDS = ("baseline", "approfondir", "decouvrir")


def eligible_starts(corpus: dict) -> list[str]:
    """Départs triés produisant une liste non vide pour chaque origine."""
    eligible = []
    for video in corpus["videos"]:
        start = video["id"]
        try:
            if not baseline(corpus, start)[:SUGGESTIONS]:
                continue
            for mode in ("approfondir", "decouvrir"):
                run = parcours(corpus, start, mode)
                if not run.videos[1:1 + SUGGESTIONS]:
                    break
            else:
                eligible.append(start)
        except PathfindingError:
            continue
    return sorted(eligible)


def _blind_list(corpus: dict, start: str, kind: str) -> list[dict]:
    by_id = {video["id"]: video for video in corpus["videos"]}
    if kind == "baseline":
        ids = baseline(corpus, start)[:SUGGESTIONS]
    else:
        ids = parcours(corpus, start, kind).videos[1:1 + SUGGESTIONS]
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
        for kind in KINDS:
            if not _blind_list(corpus, start, kind):
                raise SystemExit(f"départ {start!r} : liste {kind} vide ; choisissez un départ éligible")

    slots = [{"start": start, "kind": kind} for start in starts for kind in KINDS]
    rng.shuffle(slots)
    letters = [chr(ord("A") + i) for i in range(len(slots))]

    order = {
        "seed": seed,
        "starts": list(starts),
        "order": letters,
        "letters": {
            letter: {
                "start": slot["start"],
                "videos": _blind_list(corpus, slot["start"], slot["kind"]),
            }
            for letter, slot in zip(letters, slots)
        },
    }
    mapping = {letter: {"start": slot["start"], "kind": slot["kind"]} for letter, slot in zip(letters, slots)}
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
