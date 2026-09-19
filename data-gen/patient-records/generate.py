"""Generate artificial patient records with planted disagreements and an answer key.

    python3 generate.py                                   # 50 built-in patients, seed 42
    python3 generate.py --patients 200 --seed 7
    python3 generate.py --from-synthea synthea/output/fhir   # use Synthea patients instead

Writes to ./output (see README). Standard library only; no install needed.
The same seed and options always produce identical files.
"""

import argparse
import json
import random
import shutil
from collections import Counter
from datetime import date
from pathlib import Path

from chart import from_synthea_bundle, to_fhir_bundle
from generate_patients import generate
from inject_conflicts import derive_sources

HERE = Path(__file__).resolve().parent


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--patients", type=int, default=50, help="built-in patients to create (ignored with --from-synthea)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean-share", type=float, default=0.3, help="share of patients with no planted changes")
    ap.add_argument("--today", default="2026-09-19", help="date the records are 'pulled' (YYYY-MM-DD)")
    ap.add_argument("--from-synthea", metavar="DIR", help="folder of Synthea FHIR bundles (e.g. synthea/output/fhir)")
    ap.add_argument("--out", default=str(HERE / "output"))
    return ap.parse_args()


def load_synthea(folder: Path):
    charts = []
    for path in sorted(folder.glob("*.json")):
        chart = from_synthea_bundle(json.loads(path.read_text()))
        if chart is not None:
            charts.append(chart)
    if not charts:
        raise SystemExit(f"No Synthea patient bundles found in {folder}")
    return charts


def main():
    args = parse_args()
    today = date.fromisoformat(args.today)
    charts = load_synthea(Path(args.from_synthea)) if args.from_synthea else generate(args.patients, args.seed, today)
    rng = random.Random(args.seed * 31 + 7)

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    (out / "canonical").mkdir(parents=True)
    (out / "sources").mkdir()

    key, clean_ids = [], []
    for chart in charts:
        pid = chart.patient["id"]
        truth_source = {"id": "ground-truth", "name": "Ground truth (for scoring only)", "last_updated": today.isoformat()}
        write(out / "canonical" / f"{pid}.json", to_fhir_bundle(chart, truth_source))

        clean = rng.random() < args.clean_share
        copies, entries = derive_sources(rng, chart, today, clean)
        if not entries:
            clean_ids.append(pid)
        key.extend(entries)
        for sid, (copy_chart, info) in copies.items():
            write(out / "sources" / pid / f"{sid}.json", to_fhir_bundle(copy_chart, info))

    with (out / "answer_key.jsonl").open("w") as f:
        for entry in key:
            f.write(json.dumps(entry) + "\n")

    manifest = {
        "generator": "data-gen/patient-records",
        "input": f"synthea:{args.from_synthea}" if args.from_synthea else "built-in",
        "seed": args.seed,
        "today": today.isoformat(),
        "patients": len(charts),
        "patients_without_changes": len(clean_ids),
        "planted_changes": len(key),
        "by_mutation": dict(Counter(e["mutation"] for e in key)),
        "by_expected": dict(Counter(e["expected"] for e in key)),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {out}/")
    print(f"  patients:        {manifest['patients']} ({manifest['patients_without_changes']} with no planted changes)")
    print(f"  planted changes: {manifest['planted_changes']} {manifest['by_expected']}")
    print(f"  by mutation:     {manifest['by_mutation']}")


def write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
