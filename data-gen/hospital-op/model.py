"""SimPy model of hospital operations. Simulation time is in hours from the start.

Each patient is a SimPy process that asks for beds (priority = urgency),
holds them for a random time, and moves between units. Everything that
happens is recorded in `events`, and snapshots are taken on a timer.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import simpy

import config as C


@dataclass
class Patient:
    id: str
    source: str  # "initial" (already in a bed at the start), "ed", "elective", "mci"
    esi: int | None = None  # 1 = most urgent … 5 = least
    triage: str | None = None  # START category, mass-casualty patients only
    arrived: float | None = None
    ed_bed_at: float | None = None
    decision_at: float | None = None
    admitted_at: float | None = None
    left_at: float | None = None
    disposition: str = "in_hospital"
    path: list[tuple[str, float]] = field(default_factory=list)

    @property
    def priority(self) -> int:
        """Lower is served first. Expectant patients get comfort care after salvageable ones."""
        if self.triage == "expectant":
            return 5
        return self.esi if self.esi is not None else 3


class Hospital:
    def __init__(self, start: datetime, seed: int, census_every_min: int = 15):
        self.start = start
        self.rng = random.Random(seed)
        self.env = simpy.Environment()
        self.beds = {u: simpy.PriorityResource(self.env, c["beds"]) for u, c in C.UNITS.items()}
        self.patients: list[Patient] = []
        self.events: list[dict] = []
        self.census: list[dict] = []
        self.staffing: list[dict] = []
        self.boarding: set[str] = set()  # admitted but still in an ER bay
        self.on_shift: dict[str, int] = {}
        self.shift_peak: dict[tuple[str, int], int] = {}  # (unit, shift start hour) → peak census last time
        self.current_peak: dict[str, int] = {}
        self.census_every = census_every_min / 60
        self._next_id = 0

    # ---- helpers ---------------------------------------------------------

    def iso(self, t: float) -> str:
        return (self.start + timedelta(hours=t)).isoformat(timespec="seconds")

    def clock_hour(self, t: float) -> float:
        return (self.start.hour + self.start.minute / 60 + t) % 24

    def weekday(self, t: float) -> int:
        return (self.start + timedelta(hours=t)).weekday()

    def lognormal(self, median: float, spread: float) -> float:
        return median * math.exp(self.rng.gauss(0, spread))

    def pick(self, weights: dict):
        return self.rng.choices(list(weights), weights=list(weights.values()))[0]

    def log(self, type_: str, p: Patient | None = None, **detail):
        event = {"time": self.iso(self.env.now), "type": type_}
        if p is not None:
            event["patient"] = p.id
        event.update(detail)
        self.events.append(event)

    def new_patient(self, source: str, **fields) -> Patient:
        self._next_id += 1
        p = Patient(id=f"pt-{self._next_id:05d}", source=source, **fields)
        self.patients.append(p)
        return p

    def hours_until_discharge_window(self) -> float:
        h = self.clock_hour(self.env.now)
        lo, hi = C.DISCHARGE_HOURS
        if lo <= h < hi:
            return 0.0
        wait = (lo - h) if h < lo else (24 - h + lo)
        return wait + self.rng.uniform(0, 3)  # spread discharges over the first hours of the window

    def release_after_cleaning(self, unit: str, bed):
        """The patient leaves now; the bed becomes available once it has been cleaned."""
        def clean():
            yield self.env.timeout(self.lognormal(*C.BED_CLEANING_HOURS))
            self.beds[unit].release(bed)
        self.env.process(clean())

    # ---- patient journeys ------------------------------------------------

    def ed_visit(self, p: Patient, fraction: float = 1.0):
        """Triage → ER bay → treatment → home, or admitted (boarding in the bay until a bed frees up)."""
        if p.arrived is not None:
            yield self.env.timeout(self.lognormal(*C.TRIAGE_MINUTES) / 60)
        bay = self.beds["ER"].request(priority=p.priority)
        yield bay
        p.ed_bed_at = self.env.now
        p.path.append(("ER", self.env.now))
        if p.arrived is not None:
            self.log("ed_bed", p, waited_min=round((self.env.now - p.arrived) * 60))
        yield self.env.timeout(self.lognormal(*C.ED_TREATMENT[p.esi]) * fraction)
        p.decision_at = self.env.now

        if p.triage == "expectant" or self.rng.random() >= C.ADMIT_PROBABILITY[p.esi]:
            self.release_after_cleaning("ER", bay)
            p.left_at = self.env.now
            p.disposition = "expectant_comfort_care" if p.triage == "expectant" else "treated_and_released"
            self.log("left_ed", p, disposition=p.disposition)
            return

        unit = self.pick(C.ADMIT_DESTINATION[p.esi])
        self.log("admit_decision", p, unit=unit)
        self.boarding.add(p.id)
        bed = self.beds[unit].request(priority=p.priority)
        yield bed
        yield self.env.timeout(self.lognormal(*C.ADMIT_PROCESS_HOURS))  # report, transport
        self.boarding.discard(p.id)
        self.release_after_cleaning("ER", bay)
        p.admitted_at = self.env.now
        self.log("admitted", p, unit=unit, boarded_min=round((self.env.now - p.decision_at) * 60))
        yield from self.inpatient(p, unit, bed)

    def inpatient(self, p: Patient, unit: str, bed=None, fraction: float = 1.0):
        """Stay on a unit, then move to the next one or go home (during discharge hours)."""
        if bed is None:
            bed = self.beds[unit].request(priority=p.priority)
            yield bed
        p.path.append((unit, self.env.now))
        yield self.env.timeout(self.lognormal(*C.LENGTH_OF_STAY[unit]) * fraction)

        nxt = self.pick(C.NEXT_UNIT[unit])
        if nxt == "home":
            yield self.env.timeout(self.hours_until_discharge_window())
            self.release_after_cleaning(unit, bed)
            p.left_at = self.env.now
            p.disposition = "discharged"
            self.log("discharge", p, unit=unit)
            return

        # Keep the current bed until the next unit has room (realistic "waiting for a bed").
        new_bed = self.beds[nxt].request(priority=p.priority)
        yield new_bed
        self.release_after_cleaning(unit, bed)
        self.log("transfer", p, from_unit=unit, unit=nxt)
        yield from self.inpatient(p, nxt, new_bed)

    # ---- generators of patients -----------------------------------------

    def seed_initial_census(self):
        """Fill beds at t=0 so the run doesn't start from an empty hospital."""
        for unit, cfg in C.UNITS.items():
            for _ in range(round(cfg["beds"] * cfg["start_occupancy"])):
                p = self.new_patient("initial", esi=self.pick(C.ESI_MIX))
                remaining = self.rng.random()  # somewhere in the middle of their stay
                if unit == "ER":
                    self.env.process(self.ed_visit(p, fraction=remaining))
                else:
                    self.env.process(self.inpatient(p, unit, fraction=remaining))

    def ed_arrivals(self):
        """Poisson arrivals whose rate changes by hour and weekday (thinning method)."""
        mean_hourly = sum(C.HOURLY_PATTERN) / 24
        base = C.ED_ARRIVALS_PER_DAY / 24 / mean_hourly
        peak = base * max(C.HOURLY_PATTERN) * max(C.WEEKDAY_PATTERN)
        while True:
            yield self.env.timeout(self.rng.expovariate(peak))
            t = self.env.now
            rate = base * C.HOURLY_PATTERN[int(self.clock_hour(t))] * C.WEEKDAY_PATTERN[self.weekday(t)]
            if self.rng.random() < rate / peak:
                p = self.new_patient("ed", esi=self.pick(C.ESI_MIX), arrived=t)
                self.log("arrival", p, esi=p.esi)
                self.env.process(self.ed_visit(p))

    def elective_surgery(self, days: int):
        """Scheduled operations on weekdays; after surgery patients go to a unit."""
        for day in range(days):
            day_start = day * 24 - self.clock_hour(0)
            if self.weekday(day_start + 12) >= 5:
                continue
            lo, hi = C.ELECTIVE_START_HOURS
            for start in sorted(self.rng.uniform(lo, hi) for _ in range(C.ELECTIVE_CASES_PER_WEEKDAY)):
                self.env.process(self.elective_case(day_start + start))
        yield self.env.timeout(0)

    def elective_case(self, at: float):
        if at < self.env.now:
            return
        yield self.env.timeout(at - self.env.now)
        p = self.new_patient("elective", arrived=self.env.now)
        self.log("elective_arrival", p)
        yield from self.inpatient(p, "OR")

    def mass_casualty(self, at: float, size: int, window_min: float):
        yield self.env.timeout(at)
        self.log("mci_declared", size=size, window_min=window_min)
        offsets = sorted(self.rng.uniform(0, window_min / 60) for _ in range(size))
        for offset in offsets:
            triage = self.pick(C.MCI_TRIAGE_MIX)
            p = self.new_patient("mci", triage=triage, esi=C.MCI_TRIAGE_TO_ESI[triage])
            self.env.process(self.mci_arrival(p, offset))

    def mci_arrival(self, p: Patient, offset: float):
        yield self.env.timeout(offset)
        p.arrived = self.env.now
        self.log("arrival", p, esi=p.esi, triage=p.triage, mci=True)
        yield from self.ed_visit(p)

    # ---- recorders -------------------------------------------------------

    def record_census(self):
        while True:
            yield self.env.timeout(self.census_every)
            for unit, cfg in C.UNITS.items():
                b = self.beds[unit]
                self.census.append(
                    {
                        "time": self.iso(self.env.now),
                        "unit": unit,
                        "occupied": b.count,
                        "capacity": cfg["beds"],
                        "occupancy_pct": round(b.count / cfg["beds"] * 100, 1),
                        "waiting_for_bed": len(b.queue),
                        "boarding_in_er": len(self.boarding) if unit == "ER" else 0,
                    }
                )

    def staff_shift(self, shift_hour: int):
        """Schedule nurses for the shift that starts now, minus random sick calls.

        Plans for the larger of the current census and the peak census seen in the
        same shift last time, the way charge nurses plan from yesterday's pattern.
        """
        previous = (C.SHIFT_STARTS[0] + C.SHIFT_STARTS[1] - shift_hour) % 24  # the other shift
        for unit in self.current_peak:
            self.shift_peak[(unit, previous)] = self.current_peak[unit]
        for unit, cfg in C.UNITS.items():
            expected = max(self.beds[unit].count, self.shift_peak.get((unit, shift_hour), 0))
            self.current_peak[unit] = self.beds[unit].count
            scheduled = max(1, math.ceil(expected * C.STAFFING_BUFFER / cfg["nurse_ratio"]))
            sick = sum(self.rng.random() < C.SICK_CALL_RATE for _ in range(scheduled))
            self.on_shift[unit] = scheduled - sick
            self.log("shift_start", unit=unit, scheduled=scheduled, sick_calls=sick, on_shift=scheduled - sick)

    def record_staffing(self):
        yield self.env.timeout(1 / 60)  # let t=0 bed requests settle first
        hour = int(self.clock_hour(self.env.now))
        self.staff_shift(max(h for h in C.SHIFT_STARTS if h <= hour) if hour >= min(C.SHIFT_STARTS) else max(C.SHIFT_STARTS))
        while True:
            # Next full hour (runs always start on the hour, so this stays aligned to the clock).
            yield self.env.timeout(math.floor(self.env.now + 1e-6) + 1 - self.env.now)
            hour = round(self.clock_hour(self.env.now)) % 24
            if hour in C.SHIFT_STARTS:
                self.staff_shift(hour)
            for unit, cfg in C.UNITS.items():
                self.current_peak[unit] = max(self.current_peak.get(unit, 0), self.beds[unit].count)
                required = math.ceil(self.beds[unit].count / cfg["nurse_ratio"])
                self.staffing.append(
                    {
                        "time": self.iso(self.env.now),
                        "unit": unit,
                        "nurses_on_shift": self.on_shift[unit],
                        "nurses_required": required,
                        "short_by": max(0, required - self.on_shift[unit]),
                    }
                )

    # ---- run -------------------------------------------------------------

    def run(self, days: int, mci_at: float | None = None, mci_size: int = 25, mci_window_min: float = 20):
        self.seed_initial_census()
        self.env.process(self.ed_arrivals())
        self.env.process(self.elective_surgery(days))
        self.env.process(self.record_census())
        self.env.process(self.record_staffing())
        if mci_at is not None:
            self.env.process(self.mass_casualty(mci_at, mci_size, mci_window_min))
        self.env.run(until=days * 24)
