"""Saisie des notes en aveugle : l'origine (baseline / parcours sensible à la rétention) n'est jamais révélée.

Les notes sont 1-5 sur trois critères (ADR-0001) : cohérence, surprise utile, clarté.
Le matériel aveugle (départ + vidéos, explications masquées) est affiché depuis
l'ordre figé d'order.json. La révélation (reveal.py) ne peut s'exécuter qu'après
notation complète.
"""

import argparse
import json
from pathlib import Path

from blind_draw import present

CRITERIA = ("coherence", "surprise", "clarte")


def scores_complete(order: dict, scores: dict) -> list[str]:
    missing = []
    for letter in order["letters"]:
        for criterion in CRITERIA:
            if letter not in scores or criterion not in scores.get(letter, {}):
                missing.append(f"{letter}/{criterion}")
    return missing


def record(scores_path: Path, order: dict) -> int:
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else {}
    print(present(order))
    while True:
        entry = input(f"Liste (lettre) et notes '{','.join(CRITERIA)}' (ex. A 4 3 5), ou 'q' : ").strip()
        if entry == "q":
            break
        parts = entry.split()
        if len(parts) != 4 or not all(p.isdigit() and 1 <= int(p) <= 5 for p in parts[1:]):
            print(f"format attendu : <lettre> {' '.join(c + ' 1-5' for c in CRITERIA)}")
            continue
        letter = parts[0]
        if letter not in order["letters"]:
            print(f"lettre inconnue : {letter}")
            continue
        scores[letter] = {criterion: int(value) for criterion, value in zip(CRITERIA, parts[1:])}
        scores_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"enregistré : {letter}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Saisie des notes en aveugle")
    parser.add_argument("--order", default="eval/order.json")
    parser.add_argument("--scores", default="eval/scores.json")
    args = parser.parse_args()
    order = json.loads(Path(args.order).read_text(encoding="utf-8"))
    scores_path = Path(args.scores)
    record(scores_path, order)
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else {}
    missing = scores_complete(order, scores)
    print("NOTATION COMPLÈTE — vous pouvez lancer reveal.py" if not missing else f"manquant : {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
