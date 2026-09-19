"""Checks the swarm's regional data over many random incidents.

    npm run check       (from capacity-map/)

Fails with the scenario that broke a rule, so it can be replayed with region.simulate(...).
"""

import random
from datetime import datetime

import _swarm  # noqa: F401  (adds the swarm server to the import path)
import region

RUNS = 60
TOLERANCE = 3  # minutes of average time to a bed coordination may cost (spreading out adds driving)


def fail(msg, scenario):
    raise SystemExit(f"FAIL: {msg}\n  scenario: {scenario}")


def check_hospital(h, scenario):
    for unit in ("er", "icu"):
        u = h[unit]
        if not 0 <= u["occupied"] <= u["capacity"]:
            fail(f"{h['id']} {unit} occupied {u['occupied']} outside 0..{u['capacity']}", scenario)
        if u["waiting"] < 0:
            fail(f"{h['id']} {unit} negative waiting", scenario)
    if h["status"] != region.status(h["er"], h["icu"]):
        fail(f"{h['id']} status doesn't follow the rules", scenario)


def main():
    rng = random.Random(2026)
    better = same = slower = 0
    for hour in range(24):
        snap = region.snapshot(now=datetime(2026, 9, 19, hour, 15))
        for h in snap["hospitals"]:
            check_hospital(h, {"snapshot_hour": hour})

    for _ in range(RUNS):
        lat, lon = region.REGION["center"]
        scenario = {
            "lat": round(lat + rng.uniform(-0.08, 0.08), 4),
            "lon": round(lon + rng.uniform(-0.1, 0.1), 4),
            "casualties": rng.choice([10, 25, 40, 60, 90]),
            "now": datetime(2026, 9, 19, rng.randint(0, 23), rng.choice([0, 30])),
        }
        sim = region.simulate(**scenario)
        if sum(a["casualties"] for a in sim["assignments"]) != scenario["casualties"]:
            fail("not every casualty was assigned a hospital", scenario)
        trauma = {h["id"] for h in region.HOSPITALS if h["trauma"]}
        for a in sim["assignments"]:
            if a["severe"] and a["hospital_id"] not in trauma:
                fail(f"severe casualties sent to non-trauma hospital {a['hospital_id']}", scenario)
        minutes = [f["minute"] for f in sim["frames"]]
        if minutes != sorted(minutes) or minutes[0] != 0:
            fail("frames out of order", scenario)
        for f in sim["frames"]:
            for h in f["hospitals"]:
                check_hospital(h, scenario)
        c, n = sim["comparison"]["coordinated"], sim["comparison"]["nearest"]
        if c["avg_to_bed_min"] > n["avg_to_bed_min"] + TOLERANCE:
            fail(f"coordination made the average time to a bed worse ({c} vs {n})", scenario)
        if c["without_bed"] > n["without_bed"]:
            fail(f"coordination left more casualties without a bed ({c} vs {n})", scenario)
        better += c["avg_to_bed_min"] < n["avg_to_bed_min"]
        same += c["avg_to_bed_min"] == n["avg_to_bed_min"]
        slower += c["avg_to_bed_min"] > n["avg_to_bed_min"]

    print(
        f"ok: 24 snapshots, {RUNS} incidents. Average time to a bed with coordination: "
        f"faster in {better}, same in {same}, up to {TOLERANCE} min slower in {slower}."
    )


if __name__ == "__main__":
    main()
