"""A deliberately careless checker, to show what the traps catch.

It compares records by literal text and treats anything missing as a conflict.
So it flags brand names, abbreviations, gaps and ruled-out diagnoses. The
score it gets is the baseline a real checker (DeepChart) should beat.

    python3 naive_checker.py > naive_predictions.jsonl
    python3 score.py naive_predictions.jsonl
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def facts(bundle: dict) -> dict[str, dict[str, str]]:
    """category → {first word of the name (lowercase): full text}"""
    out = defaultdict(dict)
    for entry in bundle["entry"]:
        r = entry["resource"]
        kind = r["resourceType"]
        text = r.get("code", r.get("medicationCodeableConcept", {})).get("text", "")
        if not text:
            continue
        name = text.split()[0].lower()
        if kind in ("MedicationRequest", "MedicationStatement"):
            dosage = (r.get("dosageInstruction") or r.get("dosage") or [{}])[0].get("text", "")
            out["medication"][name] = f"{text} {dosage}".lower()
        elif kind == "Condition":
            out["condition"][r["code"]["text"]] = text  # ignores verificationStatus ("ruled out")
        elif kind == "AllergyIntolerance":
            out["allergy"][text] = text
    return out


def check(folder: Path):
    for patient_dir in sorted(folder.iterdir()):
        per_source = [facts(json.loads(p.read_text())) for p in sorted(patient_dir.glob("*.json"))]
        for category in ("medication", "condition", "allergy"):
            names = set().union(*(s[category].keys() for s in per_source))
            for name in sorted(names):
                values = {s[category].get(name) for s in per_source}
                if len(values) > 1:  # different text, or missing somewhere
                    yield {"patient_id": patient_dir.name, "category": category, "item": name}


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "output" / "sources"
    for prediction in check(folder):
        print(json.dumps(prediction))


if __name__ == "__main__":
    main()
