"""Checks the generator: same seed → identical files, and the data is internally consistent.

    ../.venv/bin/python check.py
"""

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["units.json", "events.jsonl", "census.csv", "staffing.csv", "patients.csv"]


def generate(out: Path, *args: str):
    subprocess.run([sys.executable, str(HERE / "generate.py"), "--out", str(out), *args], check=True, capture_output=True)


def digest(out: Path) -> str:
    return hashlib.sha256(b"".join((out / f).read_bytes() for f in FILES)).hexdigest()


def rows(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


def check_consistency(out: Path):
    census = rows(out / "census.csv")
    assert all(int(r["occupied"]) <= int(r["capacity"]) for r in census), "a unit went over capacity"

    staffing = rows(out / "staffing.csv")
    assert all(int(r["short_by"]) == max(0, int(r["nurses_required"]) - int(r["nurses_on_shift"])) for r in staffing)

    patients = rows(out / "patients.csv")
    ids = {p["patient_id"] for p in patients}
    for p in patients:
        times = [p[k] for k in ("arrived", "ed_bed_at", "decision_at", "admitted_at", "left_at") if p[k]]
        assert times == sorted(times), f"{p['patient_id']}: timestamps out of order {times}"

    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [e["time"] for e in events] == sorted(e["time"] for e in events), "events are not in time order"
    assert all(e.get("patient", next(iter(ids))) in ids for e in events), "event refers to unknown patient"
    return len(patients), len(events)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        a, b, c = Path(tmp, "a"), Path(tmp, "b"), Path(tmp, "c")
        generate(a, "--seed", "1")
        generate(b, "--seed", "1")
        generate(c, "--seed", "2")
        assert digest(a) == digest(b), "same seed produced different files"
        assert digest(a) != digest(c), "different seeds produced identical files"
        for out in (a, c):
            n_patients, n_events = check_consistency(out)
        long_run = Path(tmp, "long")
        generate(long_run, "--days", "28", "--seed", "3", "--mci-size", "60")
        check_consistency(long_run)
    print(f"OK: deterministic by seed; capacity, ordering and staffing checks pass ({n_patients} patients, {n_events} events per week).")


if __name__ == "__main__":
    main()
