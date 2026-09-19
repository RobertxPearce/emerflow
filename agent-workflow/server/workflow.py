"""The Hospital Swarm decision process, run against the SimPy hospital.

`run()` yields protocol events (see protocol.py): the step graph, each step
starting and finishing with what it received / decided / why, hospital
snapshots, and pauses so a person can watch it happen.

The agents are rule-based stand-ins for Gemini: they read the simulated state
and say what their unit needs. To use a real model, replace the body of an
agent function and return the same step_done(...) event.
"""

import random
from collections import Counter

from hospital import UNITS, Hospital, Patient, clock
from protocol import end, meta, pause, running, snapshot, step_done, workflow

CRISIS_AT = 13 * 60 + 47  # 21:47
ARRIVAL_WINDOW = 20  # casualties arrive over this many minutes
FOLLOW_UP = 240  # minutes simulated after the plan to measure the outcome

NEEDS = {1: "ICU", 3: "GEN", 4: "ER", 5: "ER"}
FALLBACK = {"ICU": [], "OR": [], "SDU": ["GEN"], "GEN": ["SDU"], "ER": []}
GENERIC = {"warfarin": "warfarin", "coumadin": "warfarin", "apixaban": "apixaban", "eliquis": "apixaban"}


# ---- the graph the UI draws ---------------------------------------------

STEPS = [
    {"id": "trigger", "kind": "trigger", "title": "Mass Casualty Event", "role": "Starts the run when the crisis button is pressed."},
    {"id": "engine", "kind": "code", "title": "Hospital Engine", "role": "SimPy model of the hospital: beds, nurses and patients over time."},
    {"id": "er", "kind": "ai", "title": "ER Agent", "role": "Speaks for the emergency room only."},
    {"id": "icu", "kind": "ai", "title": "ICU Agent", "role": "Speaks for intensive care only."},
    {"id": "staff", "kind": "ai", "title": "Staffing Agent", "role": "Tracks which nurses are free and when."},
    {"id": "coord", "kind": "ai", "title": "Coordinator", "role": "Listens to every department and makes one plan for the whole hospital."},
    {"id": "calc", "kind": "code", "title": "Bed Calculator", "role": "Plain math, no AI. Finds a plan that breaks no rules."},
    {"id": "deepchart", "kind": "ai", "title": "DeepChart Check", "role": "Checks each transfer's reasons against the patient's records."},
    {"id": "review", "kind": "human", "title": "Charge Nurse Review", "role": "A person decides anything the system is unsure about."},
    {"id": "outcome", "kind": "code", "title": "Simulated Outcome", "role": "Runs the same hospital with and without this plan and compares waits."},
]

EDGES = [
    ("trigger", "engine"),
    ("engine", "er"), ("engine", "icu"), ("engine", "staff"),
    ("er", "coord"), ("icu", "coord"), ("staff", "coord"),
    ("coord", "calc"), ("calc", "deepchart"), ("deepchart", "review"), ("review", "outcome"),
]


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")



# ---- the crisis ---------------------------------------------------------


def make_casualties(seed: int, count: int) -> list[tuple[Patient, float, str]]:
    rng = random.Random(seed * 7919 + 1)
    out = []
    for i in range(count):
        sev = rng.choices([1, 2, 3, 4, 5], weights=[15, 20, 35, 20, 10])[0]
        need = NEEDS.get(sev) or ("OR" if rng.random() < 0.3 else "SDU")
        out.append((Patient(id=f"MCI-{i + 1:03d}", severity=sev), rng.uniform(0, ARRIVAL_WINDOW), need))
    return sorted(out, key=lambda c: c[1])


def unit_line(sim: Hospital, u: str) -> str:
    b = sim.beds[u]
    waiting = f", {len(b.queue)} waiting" if b.queue else ""
    return f"{UNITS[u]['name']}: {b.count} / {UNITS[u]['beds']}{waiting}"


def pct(sim: Hospital, u: str) -> int:
    return round(sim.beds[u].count / UNITS[u]["beds"] * 100)


# ---- agents -------------------------------------------------------------


def er_agent(sim, casualties):
    free = max(sim.free_beds("ER"), 0)
    serious = sum(1 for p, _, _ in casualties if p.severity <= 2)
    minor = sum(1 for _, _, need in casualties if need == "ER")
    return step_done(
        "er",
        f"“{serious} serious. I need beds now.”" if serious else "“No serious arrivals. We can cope.”",
        [unit_line(sim, "ER"), f"{len(casualties)} arrivals, {serious} with severity 1–2"],
        [f"Request: {serious} inpatient beds for serious patients", f"Can treat {min(minor, max(free, 0))} of {minor} minor patients here now"],
        f"{free} ER bays are open and {serious} arrivals are severity 1–2. Serious patients must not wait in the "
        "hallway, so I ask for beds elsewhere and keep the milder patients in the ER.",
    ), {"serious": serious, "er_free": free}


def icu_agent(sim, casualties):
    free = max(sim.free_beds("ICU"), 0)
    critical = sum(1 for _, _, need in casualties if need == "ICU")
    post_op = sum(1 for _, _, need in casualties if need == "OR")
    stable = [p for p in sim.in_unit["ICU"].values() if p.stable]
    return step_done(
        "icu",
        f"“{plural(free, 'bed')} left, critical only.”",
        [unit_line(sim, "ICU"), f"{critical} arrivals need ICU now, {post_op} will need it after surgery", f"{len(stable)} current patients are stable"],
        [f"Offer: {free} beds for severity 1 only", f"{len(stable)} stable patients could move to step-down"],
        "The ICU is my responsibility, so I keep the last beds for the sickest patients. Patients who have been "
        "stable no longer need ICU-level care and could move if step-down can take them.",
    ), {"icu_free": free, "critical": critical, "post_op": post_op, "stable": stable}


def staffing_agent(sim):
    sdu_wait = round(sim.next_nurse_free("SDU"))
    er_busy = sim.nurses["ER"].count
    when = "now" if sdu_wait == 0 else f"in {sdu_wait} min"
    return step_done(
        "staff",
        f"“Step-down nurse free {when}.”",
        [f"Step-down nurses busy: {sim.nurses['SDU'].count} of {sim.nurses['SDU'].capacity}", f"ER nurses busy: {er_busy} of {sim.nurses['ER'].capacity}"],
        [f"Step-down can accept a transfer {when}", "Float pool sent to the ER"],
        "Step-down cannot accept a transfer without a free nurse, so transfers must wait for one.",
    ), {"nurse_in": sdu_wait}


def coordinator(er, icu, staff, sdu_free):
    demand = icu["critical"] + icu["post_op"]
    shortfall = max(0, demand - icu["icu_free"])
    when = "now" if staff["nurse_in"] == 0 else f"in {staff['nurse_in']} min"
    moves = icu["stable"][: min(len(icu["stable"]), shortfall, max(sdu_free, 0))]
    rules = []
    if moves:
        rules.append(f"Move {plural(len(moves), 'stable ICU patient')} to step-down {when}")
        reasoning = (
            f"ICU needs {demand} beds (critical arrivals plus post-op) but has {icu['icu_free']}. Asked ICU: "
            f"“If step-down takes {len(moves)} of your stable patients {when}, can you take "
            f"the critical arrivals now?” ICU agreed."
        )
    else:
        reasoning = (
            f"ICU needs {demand} beds and has {icu['icu_free']}"
            + (", so no transfers are needed." if shortfall == 0 else ", but no stable patients can move. Some will wait.")
        )
    rules += ["ICU accepts severity-1 arrivals only", "Step-down and General beds may cover for each other"]
    return step_done(
        "coord",
        rules[0] if moves else f"ICU covers {min(demand, icu['icu_free'])} of {demand}; no transfers",
        [f"ER: needs {er['serious']} beds", f"ICU: {icu['icu_free']} free, {len(icu['stable'])} stable", f"Staffing: step-down nurse free {when}"],
        [f"Rule: {r}" for r in rules],
        reasoning,
    ), moves


def bed_calculator(sim, casualties, moves):
    free = {u: sim.free_beds(u) for u in UNITS}
    free["ICU"] += len(moves)
    free["SDU"] -= len(moves)
    plan, waiting = {}, []
    for p, _, need in sorted(casualties, key=lambda c: (c[0].severity, c[1])):
        unit = next((u for u in [need, *FALLBACK[need]] if free[u] > 0), None)
        if unit:
            free[unit] -= 1
            plan[p.id] = unit
        else:
            waiting.append(p)
    counts = Counter(plan.values())
    broken = sum(1 for u in UNITS if free[u] < 0 and counts[u])
    return step_done(
        "calc",
        f"{len(plan)} of {len(casualties)} placed · {broken} rules broken",
        [f"{len(casualties)} patients", f"{len(moves)} transfers from the Coordinator", "Free beds per unit after transfers"],
        [" · ".join(f"{u} {n}" for u, n in counts.items())]
        + ([f"{len(waiting)} waiting (severity {', '.join(str(p.severity) for p in waiting)})"] if waiting else ["No one waiting"])
        + [f"{len(moves) + len(plan)} moves proposed"],
    ), plan


def describe(fact) -> str:
    if fact is None:
        return "not mentioned"
    if fact == "none":
        return "no blood thinners"
    return f"{fact['drug']} {fact['dose']:g} mg · taking"


def normalize(fact):
    if fact is None or fact == "none":
        return fact
    return (GENERIC[fact["drug"].lower()], fact["dose"])


def deepchart(moves):
    if not moves:
        return step_done("deepchart", "No transfers to check", ["No transfer reasons"], ["Nothing to check"]), set()
    flagged, lines, notes = set(), [], []
    for p in moves:
        stated = [(r, normalize(r["anticoagulant"])) for r in p.records if r["anticoagulant"] is not None]
        gaps = [r["source"] for r in p.records if r["anticoagulant"] is None]
        if len({n for _, n in stated}) > 1:
            flagged.add(p.id)
            lines += [f"{p.id} · {r['source']} ({r['date']}): {describe(r['anticoagulant'])}" for r, _ in stated]
        else:
            names = {r["anticoagulant"]["drug"] for r, _ in stated if isinstance(r["anticoagulant"], dict)}
            if len(names) > 1:
                notes.append(f"{p.id}: {' and '.join(sorted(names))} are the same drug, not a disagreement.")
            if gaps:
                notes.append(f"{p.id}: {gaps[0]} doesn't mention blood thinners. That's a gap, not a disagreement.")
    ok = len(moves) - len(flagged)
    reasoning = (
        "Where records really disagree I can't tell which one is right, so a person must check. "
        if flagged
        else "All records that mention blood thinners agree. "
    ) + " ".join(notes[:2])
    return step_done(
        "deepchart",
        f"{len(flagged)} of {len(moves)} transfers: records disagree" if flagged else f"All {plural(len(moves), 'transfer')}: records agree",
        [f"{p.id} → step-down, because the ICU chart says: {describe(p.records[0]['anticoagulant'])}" for p in moves],
        lines + ([f"{plural(ok, 'other transfer')}: records agree"] if ok else []) if flagged else [f"{plural(len(moves), 'transfer')} checked, 0 disagreements"],
        reasoning,
        flagged=bool(flagged),
    ), flagged


def review(moves, plan, flagged):
    approved = [p for p in moves if p.id not in flagged]
    paused = [p for p in moves if p.id in flagged]
    return step_done(
        "review",
        f"{len(approved) + len(plan)} moves approved · {len(paused)} awaiting review" if paused else f"All {len(approved) + len(plan)} moves approved",
        [f"{len(moves) + len(plan)} proposed moves", f"{len(paused)} flagged by DeepChart"],
        [f"{len(approved)} transfers and {len(plan)} admissions sent to the units"]
        + [f"{p.id} transfer paused until a nurse confirms medications" for p in paused],
        flagged=bool(paused),
    ), approved


# ---- outcome: same hospital, with and without coordination ---------------


def apply_casualties(sim, casualties, plan):
    for p, offset, need in casualties:
        q = Patient(id=p.id, severity=p.severity)
        sim.env.process(sim.casualty(q, offset, plan.get(p.id, need)))
        sim.casualties.append(q)


def wait_stats(sim):
    now = sim.env.now
    waits = [((q.placed if q.placed is not None else now) - q.arrived, q.severity) for q in sim.casualties]
    serious = [w for w, s in waits if s <= 2]
    return {
        "serious": round(sum(serious) / len(serious)) if serious else 0,
        "all": round(sum(w for w, _ in waits) / len(waits)),
        "longest": round(max(w for w, _ in waits)),
        "unplaced": sum(1 for q in sim.casualties if q.placed is None),
    }


def outcome(seed, sim, casualties, plan, approved):
    base = Hospital(seed)
    base.run_until(CRISIS_AT)
    for s in (sim, base):
        s.casualties = []
    apply_casualties(base, casualties, {})
    apply_casualties(sim, casualties, plan)
    for p in approved:
        sim.env.process(sim.step_down(p))

    sim.run_until(CRISIS_AT + 60)
    after_hour = sim.snapshot()
    sim.run_until(CRISIS_AT + FOLLOW_UP)
    base.run_until(CRISIS_AT + FOLLOW_UP)
    a, b = wait_stats(sim), wait_stats(base)
    reasoning = (
        "Both runs use the same random seed, so the hospital, arrivals and discharges are identical until the "
        "plan is applied. Any difference in waits comes from the coordination."
    )
    if a["all"] > b["all"]:
        reasoning += (
            " Trade-off: the plan puts the sickest patients first, so less severe patients waited longer on average."
        )
    return step_done(
        "outcome",
        f"Severity 1–2 wait: {a['serious']} min vs {b['serious']} min",
        [f"Same hospital, same seed, simulated {FOLLOW_UP // 60} h past {clock(CRISIS_AT)}", "Run A: with this plan · Run B: no coordination"],
        [
            f"Severity 1–2 average wait: {a['serious']} min (B: {b['serious']} min)",
            f"All patients average wait: {a['all']} min (B: {b['all']} min)",
            f"Longest wait: {a['longest']} min (B: {b['longest']} min)",
            f"Still without a bed at {clock(CRISIS_AT + FOLLOW_UP)}: {a['unplaced']} (B: {b['unplaced']})",
        ],
        reasoning,
    ), after_hour


# ---- the whole run ------------------------------------------------------


def run(seed: int, count: int):
    yield meta(seed=seed, casualties=count)
    yield workflow(STEPS, EDGES)
    sim = Hospital(seed)
    casualties = make_casualties(seed, count)

    yield from running("trigger")
    yield pause(0.5)
    sev = Counter(p.severity for p, _, _ in casualties)
    yield step_done(
        "trigger",
        f"{count} patients inbound · arriving over {ARRIVAL_WINDOW} min",
        [f"Crisis button pressed at {clock(CRISIS_AT)}"],
        [f"{count} patients arriving over {ARRIVAL_WINDOW} min", "Severity mix: " + " · ".join(f"S{s} × {sev[s]}" for s in sorted(sev))],
    )

    yield from running("engine")
    sim.run_until(CRISIS_AT)
    yield pause(0.9)
    yield snapshot(f"At crisis ({clock(CRISIS_AT)})", **sim.snapshot())
    yield step_done(
        "engine",
        f"ER {pct(sim, 'ER')}% · ICU {max(sim.free_beds('ICU'), 0)} free · SDU {max(sim.free_beds('SDU'), 0)} free",
        [f"Simulated 08:00 → {clock(CRISIS_AT)} (seed {seed})", f"{sim.admissions} admissions and {sim.discharges} discharges so far"],
        [unit_line(sim, u) for u in UNITS],
    )

    yield from running("er", "icu", "staff")
    er_step, er = er_agent(sim, casualties)
    icu_step, icu = icu_agent(sim, casualties)
    staff_step, staff = staffing_agent(sim)
    for delay, step in [(0.9, staff_step), (0.3, er_step), (0.3, icu_step)]:
        yield pause(delay)
        yield step

    yield from running("coord")
    yield pause(1.5)
    coord_step, moves = coordinator(er, icu, staff, sim.free_beds("SDU"))
    yield coord_step

    yield from running("calc")
    yield pause(1.0)
    calc_step, plan = bed_calculator(sim, casualties, moves)
    yield calc_step

    yield from running("deepchart")
    yield pause(1.4)
    dc_step, flagged = deepchart(moves)
    yield dc_step

    yield from running("review")
    yield pause(0.7)
    review_step, approved = review(moves, plan, flagged)
    yield review_step

    yield from running("outcome")
    outcome_step, after_hour = outcome(seed, sim, casualties, plan, approved)
    yield pause(1.0)
    yield snapshot(f"1 h after plan ({after_hour['clock']})", **after_hour)
    yield outcome_step
    yield end()
