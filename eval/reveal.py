"""Révélation : compare les notes en aveugle et applique le seuil go/no-go de l'ADR-0001.

Go (Phase 2) seulement si le parcours sensible à la rétention bat la
baseline sur « surprise utile » avec une marge >= 1 point en moyenne sur
~5 départs, et s'il ne perd pas sur « cohérence » (ADR-0001 amendée le
2026-10-24 : seuil et barème pré-engagés inchangés). Les moyennes de
« clarté » sont calculées et affichées, mais le seuil pré-engagé ne porte
que sur surprise utile et cohérence.
"""

import argparse
import json
from fractions import Fraction
from pathlib import Path

from record_scores import scores_complete

MARGIN = 1.0


def reveal(order_path: str, scores_path: str, mapping_path: str) -> dict:
    order = json.loads(Path(order_path).read_text(encoding="utf-8"))
    scores_file = Path(scores_path)
    scores = json.loads(scores_file.read_text(encoding="utf-8")) if scores_file.exists() else {}
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))

    missing = scores_complete(order, scores)
    if missing:
        raise SystemExit(f"notation incomplète ({missing}) ; la révélation est refusée.")

    buckets: dict[str, list[dict]] = {}
    for letter, entry in mapping.items():
        buckets.setdefault(entry["origine"], []).append(scores[letter])

    def avg(origine, criterion):
        rows = buckets.get(origine, [])
        # Fraction : une marge vraie de 1 ne doit jamais être rejetée par un arrondi.
        return Fraction(sum(row[criterion] for row in rows), len(rows)) if rows else Fraction(0)

    surprise_baseline = avg("baseline", "surprise")
    surprise_parcours = avg("parcours", "surprise")
    coherence_baseline = avg("baseline", "coherence")
    coherence_parcours = avg("parcours", "coherence")

    surprise_margin = surprise_parcours - surprise_baseline
    comparaisons = {
        "parcours": {
            criterion: float(avg("parcours", criterion) - avg("baseline", criterion))
            for criterion in ("coherence", "surprise", "clarte")
        }
    }
    go = (
        surprise_margin >= MARGIN
        and coherence_parcours >= coherence_baseline
    )
    decision = "GO — poursuivre en Phase 2" if go else "NO-GO — revoir l'hypothèse ou la qualité des sujets"

    return {
        "moyennes": {
            "coherence": {
                "baseline": float(coherence_baseline),
                "parcours": float(coherence_parcours),
            },
            "surprise": {"baseline": float(surprise_baseline), "parcours": float(surprise_parcours)},
            "clarte": {origine: float(avg(origine, "clarte")) for origine in ("baseline", "parcours")},
        },
        "marge_surprise": float(surprise_margin),
        "comparaisons": comparaisons,
        "seuil": {"marge_min": MARGIN, "adr": "docs/adr/0001-seuil-go-no-go-pre-engage.md"},
        "decision": decision,
        "correspondance": mapping,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Révélation et décision go/no-go (ADR-0001)")
    parser.add_argument("--order", default="eval/order.json")
    parser.add_argument("--scores", default="eval/scores.json")
    parser.add_argument("--mapping", default="eval/mapping.json")
    parser.add_argument("--out", default="eval/decision.json")
    args = parser.parse_args()
    result = reveal(args.order, args.scores, args.mapping)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
