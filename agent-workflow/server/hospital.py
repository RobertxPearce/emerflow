"""SimPy model of the pretend hospital. All times are in minutes; t=0 is 08:00."""

import random
from dataclasses import dataclass, field

import simpy

DAY_START = 8 * 60

# beds: capacity · occupancy: typical fill level · los: average length of stay
# nurses: nurses who can accept a new admission or transfer
UNITS = {
    "ER": {"name": "Emergency", "beds": 40, "occupancy": 0.9, "los": 240, "nurses": 10},
    "ICU": {"name": "Intensive Care", "beds": 48, "occupancy": 0.96, "los": 4 * 1440, "nurses": 6},
    "SDU": {"name": "Step-Down", "beds": 30, "occupancy": 0.8, "los": 2 * 1440, "nurses": 4},
    "OR": {"name": "Surgery", "beds": 12, "occupancy": 0.7, "los": 150, "nurses": 6},
    "GEN": {"name": "General Beds", "beds": 180, "occupancy": 0.8, "los": 3 * 1440, "nurses": 12},
}

NURSE_UTILIZATION = 0.8  # share of time nurses are busy with routine work


def clock(t: float) -> str:
    minutes = int(DAY_START + t) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Patient:
    id: str
    severity: int  # 1 = life-threatening, 5 = minor
    arrived: float = 0.0
    placed: float | None = None
    unit: str | None = None
    stable: bool = False  # ICU patient well enough for step-down
    records: list = field(default_factory=list)
    bed: simpy.resources.resource.PriorityRequest | None = None
    stay_proc: simpy.Process | None = None


class Hospital:
    def __init__(self, seed: int, load: float = 1.0, scale: float = 1.0):
        """`load` scales how busy the hospital is (1.0 = typical); `scale` scales beds and nurses."""
        self.rng = random.Random(seed)
        self.env = simpy.Environment()
        self.load = load
        self.capacity = {u: max(1, round(c["beds"] * scale)) for u, c in UNITS.items()}
        self.beds = {u: simpy.PriorityResource(self.env, self.capacity[u]) for u in UNITS}
        self.nurses = {u: simpy.Resource(self.env, max(1, round(c["nurses"] * scale))) for u, c in UNITS.items()}
        self.nurse_busy_until: dict[str, list[float]] = {u: [] for u in UNITS}
        self.in_unit: dict[str, dict[str, Patient]] = {u: {} for u in UNITS}
        self.admissions = 0
        self.discharges = 0
        self._next_id = 1000

        for unit, cfg in UNITS.items():
            for _ in range(round(self.capacity[unit] * min(cfg["occupancy"] * load, 1.0))):
                p = self.new_patient(severity=self.census_severity(unit))
                if unit == "ICU":
                    p.stable = self.rng.random() < 0.2
                    p.records = make_records(self.rng)
                p.stay_proc = self.env.process(self.stay(p, unit, self.rng.expovariate(1 / cfg["los"])))
            self.env.process(self.routine_admissions(unit))
            self.env.process(self.routine_nursing(unit))

    # ---- helpers -------------------------------------------------------

    def new_patient(self, severity: int) -> Patient:
        self._next_id += 1
        return Patient(id=f"P{self._next_id}", severity=severity, arrived=self.env.now)

    def census_severity(self, unit: str) -> int:
        return {"ICU": 1, "OR": 2, "SDU": 2, "ER": 3, "GEN": 3}[unit] + self.rng.choice([0, 1])

    def run_until(self, t: float):
        self.env.run(until=t)

    def free_beds(self, unit: str) -> int:
        return self.capacity[unit] - self.beds[unit].count - len(self.beds[unit].queue)

    def next_nurse_free(self, unit: str) -> float:
        """Minutes until a nurse on this unit can take a new patient."""
        res = self.nurses[unit]
        if res.count < res.capacity and not res.queue:
            return 0.0
        ends = sorted(self.nurse_busy_until[unit])
        return max(0.0, ends[min(len(res.queue), len(ends) - 1)] - self.env.now)

    def snapshot(self) -> dict:
        return {
            "clock": clock(self.env.now),
            "units": [
                {
                    "code": u,
                    "name": c["name"],
                    "occupied": self.beds[u].count,
                    "capacity": self.capacity[u],
                    "waiting": len(self.beds[u].queue),
                }
                for u, c in UNITS.items()
            ],
        }

    # ---- processes -----------------------------------------------------

    def stay(self, p: Patient, unit: str, los: float, bed=None, admit=False):
        """Patient gets a bed on `unit` (waiting if full), stays `los` minutes, leaves."""
        if bed is None:
            bed = self.beds[unit].request(priority=p.severity)
            yield bed
        p.bed, p.unit = bed, unit
        if p.placed is None:
            p.placed = self.env.now
        self.in_unit[unit][p.id] = p
        if admit:
            self.admissions += 1
            self.env.process(self.nurse_task(unit, self.rng.uniform(20, 40)))
        try:
            yield self.env.timeout(los)
            self.beds[unit].release(bed)
            del self.in_unit[unit][p.id]
            self.discharges += 1
        except simpy.Interrupt:
            pass  # transferred elsewhere; the transfer took over the bed

    def nurse_task(self, unit: str, minutes: float):
        with self.nurses[unit].request() as req:
            yield req
            end = self.env.now + minutes
            self.nurse_busy_until[unit].append(end)
            yield self.env.timeout(minutes)
            self.nurse_busy_until[unit].remove(end)

    def routine_admissions(self, unit: str):
        cfg = UNITS[unit]
        rate = self.capacity[unit] * cfg["occupancy"] * self.load / cfg["los"]
        while True:
            yield self.env.timeout(self.rng.expovariate(rate))
            p = self.new_patient(severity=self.census_severity(unit))
            if unit == "ICU":
                p.records = make_records(self.rng)
            p.stay_proc = self.env.process(
                self.stay(p, unit, self.rng.expovariate(1 / cfg["los"]), admit=True)
            )

    def routine_nursing(self, unit: str):
        rate = self.nurses[unit].capacity * NURSE_UTILIZATION / 30
        while True:
            yield self.env.timeout(self.rng.expovariate(rate))
            self.env.process(self.nurse_task(unit, self.rng.uniform(15, 45)))

    def step_down(self, p: Patient):
        """Move a stable ICU patient to step-down: needs a step-down bed and nurse."""
        bed = self.beds["SDU"].request(priority=p.severity)
        yield bed
        yield self.env.process(self.nurse_task("SDU", 20))
        if p.id not in self.in_unit["ICU"]:
            self.beds["SDU"].release(bed)  # discharged while waiting; nothing to move
            return
        p.stay_proc.interrupt()
        self.beds["ICU"].release(p.bed)
        del self.in_unit["ICU"][p.id]
        p.stay_proc = self.env.process(self.stay(p, "SDU", self.rng.expovariate(1 / UNITS["SDU"]["los"]), bed=bed))

    def casualty(self, p: Patient, offset: float, unit: str):
        """A crisis patient arrives after `offset` minutes and goes to `unit`."""
        yield self.env.timeout(offset)
        p.arrived = self.env.now
        los = {"ER": self.rng.uniform(60, 180), "OR": self.rng.uniform(90, 180)}.get(
            unit, self.rng.expovariate(1 / UNITS[unit]["los"])
        )
        stay = self.env.process(self.stay(p, unit, los, admit=True))
        p.stay_proc = stay
        if unit == "OR":
            # After surgery the patient needs an ICU bed.
            yield stay
            icu_bed = self.beds["ICU"].request(priority=1)
            yield icu_bed
            self.env.process(self.stay(p, "ICU", self.rng.expovariate(1 / UNITS["ICU"]["los"]), bed=icu_bed))


# ---- patient records for DeepChart --------------------------------------

SOURCES = ["ICU chart", "Hospital B – Cardiology", "Local clinic"]


def make_records(rng: random.Random) -> list[dict]:
    """Blood-thinner facts from three sources. Some disagreements are planted on purpose."""
    dates = ["2026-09-18", f"2026-0{rng.randint(1, 8)}-{rng.randint(10, 28)}", f"2026-0{rng.randint(1, 8)}-{rng.randint(10, 28)}"]
    scenario = rng.choices(["agree_none", "same_drug", "taking_vs_none", "dose_mismatch"], weights=[45, 25, 20, 10])[0]
    facts = {
        "agree_none": ["none", None, "none"],
        "same_drug": [{"drug": "warfarin", "dose": 5}, {"drug": "Coumadin", "dose": 5}, None],
        "taking_vs_none": ["none", {"drug": "warfarin", "dose": 5}, "none"],
        "dose_mismatch": [{"drug": "apixaban", "dose": 5}, None, {"drug": "Eliquis", "dose": 2.5}],
    }[scenario]
    return [{"source": s, "date": d, "anticoagulant": f} for s, d, f in zip(SOURCES, dates, facts)]
