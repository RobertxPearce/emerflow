"""Regional view for the public capacity map (../../capacity-map): every hospital's load.

Each hospital is its own SimPy `Hospital` (different size, how busy it usually
is, and seed), simulated from 08:00 to the current time of day.

- `snapshot()`: the current state, including one ongoing incident.
- `simulate()`: a what-if. Casualties from an incident placed anywhere are spread
  across hospitals by `distribute()`, then every hospital is played forward. The same
  incident is also run with every casualty sent to the nearest trauma center, which is
  what happens without coordination, so the two can be compared.

Statuses, ER waits and the casualty distribution are plain code, not AI, so every
color on the map can be explained.
"""

import math
import zlib
from datetime import datetime, timedelta

from hospital import DAY_START, Hospital, Patient
from workflow import make_casualties

REGION = {"name": "Baltimore, MD", "center": [39.2904, -76.6122]}
MAX_INCIDENT_KM = 40  # simulate() only accepts incidents this close to the region center

# Real hospitals, simulated load. `load` 1.0 = the model's typical occupancy.
HOSPITALS = [
    {"id": "jhh", "name": "Johns Hopkins Hospital", "address": "1800 Orleans St", "lat": 39.2963, "lon": -76.5925, "trauma": "Level I", "scale": 1.3, "load": 1.0},
    {"id": "shock-trauma", "name": "UMMC R Adams Cowley Shock Trauma", "address": "22 S Greene St", "lat": 39.2887, "lon": -76.6245, "trauma": "Level I", "scale": 1.2, "load": 0.97},
    {"id": "bayview", "name": "Johns Hopkins Bayview", "address": "4940 Eastern Ave", "lat": 39.2894, "lon": -76.5487, "trauma": "Level II", "scale": 0.9, "load": 0.9},
    {"id": "mercy", "name": "Mercy Medical Center", "address": "345 St Paul Pl", "lat": 39.2946, "lon": -76.6139, "trauma": None, "scale": 0.7, "load": 0.8},
    {"id": "midtown", "name": "UMMC Midtown Campus", "address": "827 Linden Ave", "lat": 39.2990, "lon": -76.6219, "trauma": None, "scale": 0.5, "load": 0.72},
    {"id": "union-memorial", "name": "MedStar Union Memorial", "address": "201 E University Pkwy", "lat": 39.3302, "lon": -76.6130, "trauma": None, "scale": 0.8, "load": 0.93},
    {"id": "sinai", "name": "Sinai Hospital of Baltimore", "address": "2401 W Belvedere Ave", "lat": 39.3530, "lon": -76.6617, "trauma": "Level II", "scale": 1.0, "load": 0.86},
    {"id": "harbor", "name": "MedStar Harbor Hospital", "address": "3001 S Hanover St", "lat": 39.2494, "lon": -76.6139, "trauma": None, "scale": 0.5, "load": 0.68},
    {"id": "st-agnes", "name": "Ascension Saint Agnes", "address": "900 S Caton Ave", "lat": 39.2723, "lon": -76.6776, "trauma": None, "scale": 0.8, "load": 0.78},
    {"id": "good-sam", "name": "MedStar Good Samaritan", "address": "5601 Loch Raven Blvd", "lat": 39.3587, "lon": -76.5906, "trauma": None, "scale": 0.6, "load": 0.74},
    {"id": "gbmc", "name": "GBMC", "address": "6701 N Charles St, Towson", "lat": 39.3955, "lon": -76.6222, "trauma": None, "scale": 0.8, "load": 0.7},
]

INCIDENT = {
    "id": "i95-collision",
    "title": "Multi-vehicle collision on I-95 near the Fort McHenry Tunnel",
    "lat": 39.2620,
    "lon": -76.5790,
    "casualties": 40,
    "minutes_ago": 50,
    "receiving": 2,  # nearest trauma centers that take the casualties
}

ER_LOS = 240  # minutes an ER bay is typically held (hospital.UNITS["ER"]["los"])
DRIVE_KM_PER_MIN = 0.6  # ~36 km/h through city traffic with lights and sirens
LOAD_MINUTES = 5  # loading a patient into the ambulance at the scene
OVERFLOW_PENALTY = 30  # minutes added per patient a hospital would have beyond its free beds
RESERVE = 0.1  # share of each unit's beds kept back for the hospital's usual patients


def km(a_lat, a_lon, b_lat, b_lon) -> float:
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def drive_minutes(distance_km: float) -> float:
    return LOAD_MINUTES + distance_km / DRIVE_KM_PER_MIN


def status(er: dict, icu: dict) -> str:
    """open / busy / critical, from ER and ICU load. Critical = people are waiting for a bed or the ER is full."""
    er_pct = er["occupied"] / er["capacity"]
    icu_pct = icu["occupied"] / icu["capacity"]
    if er["waiting"] > 0 or icu["waiting"] > 0 or er_pct >= 0.97:
        return "critical"
    if max(er_pct, icu_pct) >= 0.85:
        return "busy"
    return "open"


def er_wait_minutes(er: dict) -> int:
    """Rough ER wait. With no free bay, a bay frees up about every ER_LOS / capacity minutes;
    a nearly full ER also slows triage."""
    ahead = er["waiting"] + 1 - (er["capacity"] - er["occupied"])  # people before you with no bay
    full = 40  # a (nearly) full ER: triage is slow even before a queue forms
    if ahead > 0:
        return max(full, round(10 + ahead * ER_LOS / er["capacity"]))
    pct = er["occupied"] / er["capacity"]
    return full if pct >= 0.97 else 25 if pct >= 0.85 else 10


def sim_minutes(now: datetime) -> int:
    """Minutes since the simulation's 08:00 start for this time of day (at least 1 h of history)."""
    return max((now.hour * 60 + now.minute - DAY_START) % (24 * 60), 60)


def new_sim(cfg: dict, day: int) -> Hospital:
    return Hospital(zlib.crc32(cfg["id"].encode()) ^ day, load=cfg["load"], scale=cfg["scale"])


def hospital_view(cfg: dict, sim: Hospital, **extra) -> dict:
    units = {u["code"]: u for u in sim.snapshot()["units"]}
    er, icu = units["ER"], units["ICU"]
    return {
        **{k: cfg[k] for k in ("id", "name", "address", "lat", "lon", "trauma")},
        "status": status(er, icu),
        "er": {k: er[k] for k in ("occupied", "capacity", "waiting")},
        "icu": {k: icu[k] for k in ("occupied", "capacity", "waiting")},
        "beds_free": sum(max(u["capacity"] - u["occupied"], 0) for u in units.values()),
        "er_wait_min": er_wait_minutes(er),
        "receiving_incident": False,
        **extra,
    }


# ---- current state ------------------------------------------------------


def snapshot(now: datetime | None = None, incident: bool = True) -> dict:
    now = now or datetime.now()
    minutes = sim_minutes(now)
    day = now.date().toordinal()

    receiving = []
    if incident and minutes > INCIDENT["minutes_ago"]:
        trauma = [h for h in HOSPITALS if h["trauma"]]
        trauma.sort(key=lambda h: km(h["lat"], h["lon"], INCIDENT["lat"], INCIDENT["lon"]))
        receiving = [h["id"] for h in trauma[: INCIDENT["receiving"]]]
    casualties = make_casualties(day, INCIDENT["casualties"]) if receiving else []

    hospitals = []
    for cfg in HOSPITALS:
        sim = new_sim(cfg, day)
        if cfg["id"] in receiving:
            sim.run_until(minutes - INCIDENT["minutes_ago"])
            share = casualties[receiving.index(cfg["id"]) :: len(receiving)]
            for p, offset, need in share:
                sim.env.process(sim.casualty(Patient(id=p.id, severity=p.severity), offset, need))
        sim.run_until(minutes)
        hospitals.append(hospital_view(cfg, sim, receiving_incident=cfg["id"] in receiving))

    incidents = []
    if receiving:
        names = [h["name"] for h in hospitals if h["id"] in receiving]
        started = now - timedelta(minutes=INCIDENT["minutes_ago"])
        incidents.append({
            "id": INCIDENT["id"],
            "kind": "mass_casualty",
            "title": INCIDENT["title"],
            "lat": INCIDENT["lat"],
            "lon": INCIDENT["lon"],
            "casualties": INCIDENT["casualties"],
            "started": started.isoformat(timespec="minutes"),
            "receiving": names,
            "summary": f"{INCIDENT['casualties']} casualties being taken to {' and '.join(names)}.",
        })

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "simulated": True,
        "region": REGION,
        "hospitals": hospitals,
        "incidents": incidents,
    }


# ---- what-if: an incident anywhere ---------------------------------------


def distribute(casualties, free: dict[str, dict[str, int]], distance: dict[str, float], trauma: set[str]) -> dict[str, str]:
    """Send each casualty where they'd get a bed soonest. Sickest first.

    `free` is {hospital: {unit: free beds}} minus the RESERVE for usual patients. Score = drive
    time + OVERFLOW_PENALTY for every patient the hospital would have beyond its free beds on the
    units they need (surgery patients need an ICU bed afterwards). Severity 1-2 go to trauma
    centers only. Returns {patient id: hospital id}. Plain code: same input, same plan.
    """
    free = {h: dict(units) for h, units in free.items()}
    plan = {}
    for p, _, need in sorted(casualties, key=lambda c: (c[0].severity, c[1])):
        units = [need, "ICU"] if need == "OR" else [need]
        options = [h for h in free if p.severity > 2 or h in trauma]

        def score(h):
            overflow = sum(max(0, 1 - free[h][u]) for u in units)
            return drive_minutes(distance[h]) + OVERFLOW_PENALTY * overflow

        best = min(options, key=score)
        for u in units:
            free[best][u] -= 1
        plan[p.id] = best
    return plan


def placed_minutes(patients, start: float, now: float) -> list[float]:
    """Minutes from the incident until each patient had a bed (or until `now` if still waiting)."""
    return [(q.placed if q.placed is not None else now) - start for q in patients]


def outcome(patients, start: float, now: float) -> dict:
    times = placed_minutes(patients, start, now)
    return {
        "avg_to_bed_min": round(sum(times) / len(times)),
        "longest_to_bed_min": round(max(times)),
        "without_bed": sum(1 for q in patients if q.placed is None),
    }


def simulate(lat: float, lon: float, casualties: int = 40, now: datetime | None = None,
             horizon: int = 180, step: int = 10, seed: int | None = None) -> dict:
    now = now or datetime.now()
    t0 = sim_minutes(now)
    day = now.date().toordinal()
    seed = seed if seed is not None else zlib.crc32(f"{lat:.3f},{lon:.3f},{casualties}".encode())
    arrivals = make_casualties(seed, casualties)
    by_id = {cfg["id"]: cfg for cfg in HOSPITALS}
    distance = {cfg["id"]: km(lat, lon, cfg["lat"], cfg["lon"]) for cfg in HOSPITALS}
    trauma = {cfg["id"] for cfg in HOSPITALS if cfg["trauma"]}

    # Everyone's state at the moment of the incident.
    sims = {cfg["id"]: new_sim(cfg, day) for cfg in HOSPITALS}
    for sim in sims.values():
        sim.run_until(t0)
    free = {h: {u: sim.free_beds(u) - round(sim.capacity[u] * RESERVE) for u in sim.capacity} for h, sim in sims.items()}

    plan = distribute(arrivals, free, distance, trauma)
    nearest = min(trauma, key=lambda h: distance[h])

    def dispatch(sim, patients, hospital):
        """Casualties leave the scene over the arrival window, then drive to `hospital`."""
        out = []
        for p, offset, need in patients:
            q = Patient(id=p.id, severity=p.severity)
            sim.env.process(sim.casualty(q, offset + drive_minutes(distance[hospital]), need))
            out.append(q)
        return out

    coordinated = []
    for h, sim in sims.items():
        coordinated += dispatch(sim, [c for c in arrivals if plan[c[0].id] == h], h)
    baseline_sim = new_sim(by_id[nearest], day)
    baseline_sim.run_until(t0)
    baseline = dispatch(baseline_sim, arrivals, nearest)

    assigned = {h: sum(1 for c in arrivals if plan[c[0].id] == h) for h in sims}
    severe = {h: sum(1 for c in arrivals if plan[c[0].id] == h and c[0].severity <= 2) for h in sims}

    frames = []
    for minute in range(0, horizon + 1, step):
        t = t0 + minute
        for sim in [*sims.values(), baseline_sim]:
            if t > sim.env.now:
                sim.run_until(t)
        frames.append({
            "minute": minute,
            "hospitals": [
                hospital_view(by_id[h], sim, receiving_incident=assigned[h] > 0) for h, sim in sims.items()
            ],
            "without_bed": {
                "coordinated": sum(1 for q in coordinated if q.placed is None),
                "nearest": sum(1 for q in baseline if q.placed is None),
            },
        })

    end = t0 + horizon
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "simulated": True,
        "incident": {
            "lat": lat,
            "lon": lon,
            "casualties": casualties,
            "seed": seed,
            "severity_mix": {str(s): sum(1 for p, _, _ in arrivals if p.severity == s) for s in range(1, 6)},
        },
        "assignments": [
            {"hospital_id": h, "casualties": n, "severe": severe[h], "drive_min": round(drive_minutes(distance[h]))}
            for h, n in sorted(assigned.items(), key=lambda kv: -kv[1]) if n
        ],
        "frames": frames,
        "comparison": {
            "coordinated": outcome(coordinated, t0, end),
            "nearest": {**outcome(baseline, t0, end), "hospital_id": nearest, "hospital": by_id[nearest]["name"]},
        },
    }


if __name__ == "__main__":
    for h in snapshot()["hospitals"]:
        print(f"{h['status']:9} ER {h['er']['occupied']}/{h['er']['capacity']} w{h['er']['waiting']}  "
              f"ICU {h['icu']['occupied']}/{h['icu']['capacity']} w{h['icu']['waiting']}  {h['er_wait_min']:>3}m  {h['name']}")
