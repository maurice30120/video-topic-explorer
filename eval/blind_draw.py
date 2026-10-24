"""Tirage d'ordre aléatoire figé pour le test en aveugle (eval/order.json)."""

import argparse
import json
import random
from pathlib import Path

from vte.corpus import load_corpus
from vte.graph_engine import build_graph


def blind_draw(corpus_path: str, seed: int, out_path: str) -> dict:
    corpus = load_corpus(corpus_path)
    graph = build_graph(corpus)
    video_ids = sorted(
        d["video_id"] for _, d in graph.nodes(data=True) if d["kind"] == "video"
    )
    rng = random.Random(seed)
    order = video_ids[:]
    rng.shuffle(order)
    payload = {
        "seed": seed,
        "order": order,
        "letters": {chr(ord("A") + i): vid for i, vid in enumerate(order)},
    }
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Tirage d'ordre aléatoire figé (aveugle)")
    parser.add_argument("corpus")
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--out", default="eval/order.json")
    args = parser.parse_args()
    payload = blind_draw(args.corpus, args.seed, args.out)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
