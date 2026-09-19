"""Generate artificial hospital-operations data.

    ../.venv/bin/python generate.py                       # 7 days, seed 42, mass-casualty event on day 6
    ../.venv/bin/python generate.py --days 14 --seed 7 --no-mci
    ../.venv/bin/python generate.py --mci 2026-09-19T21:47 --mci-size 40

Writes CSV/JSON files to ./output (see README for every column).
The same seed and options always produce identical files.
"""

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import config as C
from model import Hospital

HERE = Path(__file__).resolve().parent


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2026-09-14", help="first day (YYYY-MM-DD); the run starts at midnight")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mci", default=None, help="mass-casualty time (YYYY-MM-DDTHH:MM). Default: day 6 at 21:47")
    ap.add_argument("--no-mci", action="store_true", help="no mass-casualty event")
    ap.add_argument("--mci-size", type=int, default=25, help="casualties")
    ap.add_argument("--mci-window", type=float, default=20, help="minutes over which casualties arrive")
    ap.add_argument("--census-every", type=int, default=15, help="minutes between census snapshots")
    ap.add_argument("--out", default=str(HERE / "output"))
    return ap.parse_args()


def fmt(h: Hospital, t: float | None) -> str:
    return "" if t is None else h.iso(t)


def minutes(a: float | None, b: float | None) -> str:
    return "" if a is None or b is None else str(round((b - a) * 60))


def write_csv(path: Path, rows: list[dict]):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    args = parse_args()
    start = datetime.fromisoformat(args.start).replace(hour=0, minute=0, second=0)
    mci_at = None
    if not args.no_mci:
        default = start + timedelta(days=min(args.days, 6) - 1, hours=21, minutes=47)  # day 6 (or last day), 21:47
        mci_time = datetime.fromisoformat(args.mci) if args.mci else default
        mci_at = (mci_time - start).total_seconds() / 3600
        if not 0 <= mci_at < args.days * 24:
            raise SystemExit(f"--mci {mci_time} is outside the simulated period")

    h = Hospital(start, args.seed, args.census_every)
    h.run(args.days, mci_at, args.mci_size, args.mci_window)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    (out / "units.json").write_text(json.dumps(
        [{"code": u, "name": c["name"], "beds": c["beds"], "nurse_ratio": c["nurse_ratio"]} for u, c in C.UNITS.items()],
        indent=2) + "\n")
    with (out / "events.jsonl").open("w") as f:
        for e in h.events:
            f.write(json.dumps(e) + "\n")
    write_csv(out / "census.csv", h.census)
    write_csv(out / "staffing.csv", h.staffing)
    write_csv(out / "patients.csv", [
        {
            "patient_id": p.id,
            "source": p.source,
            "esi": p.esi or "",
            "mci_triage": p.triage or "",
            "arrived": fmt(h, p.arrived),
            "ed_bed_at": fmt(h, p.ed_bed_at) if p.arrived is not None else "",
            "ed_wait_min": minutes(p.arrived, p.ed_bed_at) if p.source in ("ed", "mci") else "",
            "decision_at": fmt(h, p.decision_at),
            "admitted_at": fmt(h, p.admitted_at),
            "boarding_min": minutes(p.decision_at, p.admitted_at),
            "left_at": fmt(h, p.left_at),
            "disposition": p.disposition,
            "path": ">".join(unit for unit, _ in p.path),
        }
        for p in h.patients
    ])

    summary = summarize(h, mci_at)
    manifest = {
        "generator": "data-gen/hospital-op",
        "start": start.isoformat(),
        "days": args.days,
        "seed": args.seed,
        "mci": None if mci_at is None else {"time": h.iso(mci_at), "size": args.mci_size, "window_min": args.mci_window},
        "files": ["units.json", "events.jsonl", "census.csv", "staffing.csv", "patients.csv"],
        "summary": summary,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print_summary(summary, out)


def summarize(h: Hospital, mci_at: float | None) -> dict:
    by_source = Counter(p.source for p in h.patients)
    waits = defaultdict(list)
    for p in h.patients:
        if p.source == "ed" and p.ed_bed_at is not None:
            waits[p.esi].append((p.ed_bed_at - p.arrived) * 60)
    boarding = [(p.admitted_at - p.decision_at) * 60 for p in h.patients if p.admitted_at and p.decision_at]
    peak = {}
    for row in h.census:
        peak[row["unit"]] = max(peak.get(row["unit"], 0), row["occupancy_pct"])
    short_hours = Counter(r["unit"] for r in h.staffing if r["short_by"] > 0)
    summary = {
        "patients_by_source": dict(by_source),
        "ed_median_wait_min_by_esi": {str(k): round(statistics.median(v)) for k, v in sorted(waits.items())},
        "median_boarding_min": round(statistics.median(boarding)) if boarding else 0,
        "peak_occupancy_pct": peak,
        "hours_short_staffed": {u: short_hours.get(u, 0) for u in C.UNITS},
    }
    if mci_at is not None:
        mci = [p for p in h.patients if p.source == "mci"]
        by_triage = defaultdict(list)
        for p in mci:
            if p.ed_bed_at is not None:
                by_triage[p.triage].append((p.ed_bed_at - p.arrived) * 60)
        summary["mci"] = {
            "casualties": len(mci),
            "median_wait_for_er_bay_min": {k: round(statistics.median(v)) for k, v in by_triage.items()},
            "never_got_er_bay": sum(1 for p in mci if p.ed_bed_at is None),
        }
    return summary


def print_summary(s: dict, out: Path):
    print(f"Wrote {out}/")
    print(f"  patients:          {s['patients_by_source']}")
    print(f"  ER median wait:    {s['ed_median_wait_min_by_esi']} (minutes, by ESI)")
    print(f"  median boarding:   {s['median_boarding_min']} min (admitted, waiting in ER for a bed)")
    print(f"  peak occupancy:    {s['peak_occupancy_pct']}")
    print(f"  short-staffed hrs: {s['hours_short_staffed']}")
    if "mci" in s:
        print(f"  mass casualty:     {s['mci']}")


if __name__ == "__main__":
    main()
