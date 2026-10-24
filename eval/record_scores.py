"""Saisie des notes en aveugle : l'origine (baseline / Approfondir / Découvrir) n'est jamais révélée.

Les notes sont 1-5 sur deux critères : cohérence et surprise utile.
La révélation (reveal.py) ne peut s'exécuter qu'après notation complète.
"""

import argparse
import json
from pathlib import Path


def scores_complete(order: dict, scores: dict) -> list[str]:
    missing = []
    for letter in order["letters"]:
        for criterion in ("coherence", "surprise"):
            if letter not in scores or criterion not in scores.get(letter, {}):
                missing.append(f"{letter}/{criterion}")
    return missing


def record(scores_path: Path) -> int:
    while True:
        entry = input("Liste (lettre) et notes 'coherence,surprise' (ex. A 4 3), ou 'q' : ").strip()
        if entry == "q":
            break
        parts = entry.split()
        if len(parts) != 3 or not all(p.isdigit() and 1 <= int(p) <= 5 for p in parts[1:]):
            print("format attendu : <lettre> <coherence 1-5> <surprise 1-5>")
            continue
        letter, coherence, surprise = parts[0], int(parts[1]), int(parts[2])
        scores[letter] = {"coherence": coherence, "surprise": surprise}
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
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else {}
    missing = scores_complete(order, scores)
    status = "NOTATION COMPLÈTE — vous pouvez lancer reveal.py" if not missing else f"manquant : {missing}"
    record(scores_path)
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
