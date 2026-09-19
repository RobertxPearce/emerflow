"""Scores a checker's flags against the answer key.

    python3 score.py predictions.jsonl [answer_key.jsonl]

predictions.jsonl: one flagged item per line:
    {"patient_id": "patient-0007", "category": "medication", "item": "warfarin"}
category is "medication", "allergy" or "condition". Brand names are accepted
(Coumadin counts as warfarin). Reports:
  caught       real disagreements that were flagged (recall)
  precision    share of flags that were real disagreements
  false alarms flags that were not real disagreements, and which traps caused them
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from vocab import MEDICATIONS

HERE = Path(__file__).resolve().parent
BRAND_TO_GENERIC = {info["brand"].lower(): generic for generic, info in MEDICATIONS.items()}


def normalize(category: str, item: str) -> str:
    item = item.strip().lower()
    if category == "medication":
        item = BRAND_TO_GENERIC.get(item, item)
        item = next((g for g in MEDICATIONS if item.startswith(g.split()[0])), item)
    return item


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def score(predictions: list[dict], key: list[dict]) -> dict:
    as_key = lambda e: (e["patient_id"], e["category"], normalize(e["category"], e["item"]))
    positives = {as_key(e) for e in key if e["expected"] == "disagreement"}
    trap_kind = {as_key(e): e["mutation"] for e in key if e["expected"] != "disagreement"}
    flagged = {as_key(p) for p in predictions}

    caught = flagged & positives
    by_mutation = defaultdict(lambda: [0, 0])
    for e in key:
        if e["expected"] == "disagreement":
            by_mutation[e["mutation"]][1] += 1
            by_mutation[e["mutation"]][0] += as_key(e) in flagged
    false_alarms = flagged - positives
    return {
        "real_disagreements": len(positives),
        "caught": len(caught),
        "recall": round(len(caught) / len(positives), 3) if positives else 1.0,
        "flags": len(flagged),
        "precision": round(len(caught) / len(flagged), 3) if flagged else 1.0,
        "false_alarms": len(false_alarms),
        "false_alarms_from_traps": dict(Counter(trap_kind[k] for k in false_alarms if k in trap_kind)),
        "false_alarms_other": sum(1 for k in false_alarms if k not in trap_kind),
        "caught_by_mutation": {m: f"{c}/{n}" for m, (c, n) in sorted(by_mutation.items())},
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    key_path = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "output" / "answer_key.jsonl"
    result = score(load(Path(sys.argv[1])), load(key_path))
    width = max(len(k) for k in result)
    for k, v in result.items():
        print(f"{k:<{width}}  {v}")


if __name__ == "__main__":
    main()
