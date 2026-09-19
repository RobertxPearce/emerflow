"""Turns each true chart into the copies different facilities hold, and plants
disagreements on purpose. Every change is written to the answer key.

Each facility sees only part of the chart (a pharmacy knows medications, a
cardiologist knows the heart-related parts), and each copy is dated. Then
mutations are applied to some copies. Some are real disagreements a checker
should flag; others are traps that only look like disagreements.
"""

import copy
import random
from datetime import date, timedelta

from chart import Allergy, Chart, Condition, Med, med_text
from vocab import BLOOD_THINNER_GROUPS, MEDICATIONS, RULE_OUT_CANDIDATES

DISAGREEMENT = "disagreement"  # a checker should flag this
NOT_A_DISAGREEMENT = "not_a_disagreement"  # looks different, means the same → should NOT be flagged
GAP = "gap"  # one record is silent → should NOT be flagged as a disagreement

CARDIAC_GROUPS = {"anticoagulant", "antiplatelet", "beta blocker", "ACE inhibitor", "calcium channel blocker", "statin", "diuretic"}
CARDIAC_CONDITIONS = {"Hypertension", "Hyperlipidemia", "Atrial fibrillation", "Coronary artery disease", "Heart failure"}

# The ED copy is current and unchanged; the others are older, partial and may be mutated.
SOURCES = [
    {"id": "st-aurelia-ed", "name": "St. Aurelia Emergency Department", "age_days": (0, 0), "keeps": "all"},
    {"id": "hospital-b-cardiology", "name": "Hospital B – Cardiology", "age_days": (30, 400), "keeps": "cardiac"},
    {"id": "local-clinic", "name": "Local primary care clinic", "age_days": (14, 300), "keeps": "all"},
    {"id": "retail-pharmacy", "name": "Retail pharmacy", "age_days": (1, 60), "keeps": "meds"},
]
MUTABLE_SOURCES = [s["id"] for s in SOURCES[1:]]

FREQ_ABBREVIATION = {"once daily": "QD", "twice daily": "BID", "at bedtime": "QHS", "2 puffs as needed": "2 puffs PRN"}
DOSE_CAUSES = [
    "A specialist changed the dose; this record was never updated.",
    "An old note was copied forward with the previous dose.",
    "Records from another hospital were attached, not merged.",
]


def facility_copy(chart: Chart, keeps: str) -> Chart:
    c = copy.deepcopy(chart)
    if keeps == "cardiac":
        c.meds = [m for m in c.meds if m.generic and MEDICATIONS[m.generic]["group"] in CARDIAC_GROUPS]
        c.conditions = [x for x in c.conditions if x.name in CARDIAC_CONDITIONS]
    elif keeps == "meds":
        c.conditions = []
    return c


# ---- mutations -------------------------------------------------------------
# Each takes (rng, facility copy, true chart, touched items) and returns answer-key
# entries, or [] if it doesn't apply to this copy.


def _meds(src: Chart, touched: set, *, varied_dose=False, blood_thinner=False) -> list[Med]:
    out = []
    for m in src.meds:
        if not m.generic or m.dose is None or m.status != "active" or m.generic in touched:
            continue
        info = MEDICATIONS[m.generic]
        if varied_dose and len(info["doses"]) < 2:
            continue
        if blood_thinner and info["group"] not in BLOOD_THINNER_GROUPS:
            continue
        out.append(m)
    return out


def _entry(category, item, expected, true_value, source_value, explanation):
    return {"category": category, "item": item, "expected": expected, "true_value": true_value,
            "source_value": source_value, "explanation": explanation}


def brand_name(rng, src, truth, touched):
    meds = _meds(src, touched)
    if not meds:
        return []
    m = rng.choice(meds)
    before = m.text
    m.text, m.rxnorm = med_text(m.generic, m.dose, m.unit, style="brand"), None
    return [_entry("medication", m.generic, NOT_A_DISAGREEMENT, before, m.text,
                   f"{MEDICATIONS[m.generic]['brand']} is the brand name of {m.generic}; same drug and dose.")]


def abbreviation(rng, src, truth, touched):
    meds = _meds(src, touched)
    if not meds:
        return []
    m = rng.choice(meds)
    before = m.text
    m.text = f"{m.generic} {m.dose:g}{m.unit} PO {FREQ_ABBREVIATION.get(m.frequency, m.frequency)}"
    m.rxnorm = None
    return [_entry("medication", m.generic, NOT_A_DISAGREEMENT, before, m.text,
                   "Clinical shorthand (PO = by mouth, QD/BID = once/twice daily); same drug and dose.")]


def dose_mismatch(rng, src, truth, touched):
    meds = _meds(src, touched, varied_dose=True)
    if not meds:
        return []
    m = rng.choice(meds)
    before = m.text
    m.dose = rng.choice([d for d in MEDICATIONS[m.generic]["doses"] if d != m.dose])
    m.text = med_text(m.generic, m.dose, m.unit)
    return [_entry("medication", m.generic, DISAGREEMENT, before, m.text, rng.choice(DOSE_CAUSES))]


def patient_reported(rng, src, truth, touched):
    meds = _meds(src, touched, varied_dose=True)
    if not meds:
        return []
    m = rng.choice(meds)
    before = m.text
    m.dose = rng.choice([d for d in MEDICATIONS[m.generic]["doses"] if d != m.dose])
    m.text = med_text(m.generic, m.dose, m.unit)
    m.reported_by = "patient"
    m.note = f"Patient reports taking {m.dose:g} {m.unit}."
    return [_entry("medication", m.generic, DISAGREEMENT, before, f"{m.text} (patient-reported)",
                   "The patient reported a different dose than the chart; both were written down.")]


def denies_blood_thinner(rng, src, truth, touched):
    meds = _meds(src, touched, blood_thinner=True)
    if not meds:
        return []
    m = rng.choice(meds)
    src.meds.remove(m)
    src.meds.append(Med(generic=None, text="Blood thinners (anticoagulants/antiplatelets)", status="not-taken",
                        note="Patient denies taking any blood thinners."))
    return [_entry("medication", m.generic, DISAGREEMENT, m.text, "Explicitly: no blood thinners",
                   "This record says the patient takes no blood thinners; the true chart has one.")]


def no_known_allergies(rng, src, truth, touched):
    real = [a for a in src.allergies if not a.no_known and a.substance not in touched]
    if not real:
        return []
    src.allergies = [Allergy(substance="No known allergies", no_known=True)]
    return [_entry("allergy", a.substance, DISAGREEMENT, f"{a.substance} ({a.reaction})", "Explicitly: no known allergies",
                   "This record says no known allergies; the true chart has this allergy.") for a in real]


def omission(rng, src, truth, touched):
    options = [("medication", m) for m in _meds(src, touched)]
    options += [("allergy", a) for a in src.allergies if not a.no_known and a.substance not in touched]
    options += [("condition", c) for c in src.conditions if c.verification == "confirmed" and c.name not in touched]
    if not options:
        return []
    category, item = rng.choice(options)
    if category == "medication":
        src.meds.remove(item)
        return [_entry(category, item.generic, GAP, item.text, "(not mentioned)", "This record is silent about it. A gap, not a disagreement.")]
    if category == "allergy":
        src.allergies.remove(item)
        return [_entry(category, item.substance, GAP, item.substance, "(not mentioned)", "This record is silent about it. A gap, not a disagreement.")]
    src.conditions.remove(item)
    return [_entry(category, item.name, GAP, item.name, "(not mentioned)", "This record is silent about it. A gap, not a disagreement.")]


def ruled_out(rng, src, truth, touched):
    has ={c.name for c in truth.conditions}
    options = [name for name in RULE_OUT_CANDIDATES if name not in has and name not in touched]
    if not options:
        return []
    name = rng.choice(options)
    src.conditions.append(Condition(name=name, verification="refuted", note=RULE_OUT_CANDIDATES[name]))
    return [_entry("condition", name, NOT_A_DISAGREEMENT, "(does not have it)", f"{name}: tested and ruled out",
                   "The record mentions the condition only to say it was ruled out. The patient does not have it.")]


MUTATIONS = {
    "brand_name": (brand_name, 3),
    "abbreviation": (abbreviation, 2),
    "dose_mismatch": (dose_mismatch, 3),
    "patient_reported": (patient_reported, 2),
    "denies_blood_thinner": (denies_blood_thinner, 2),
    "no_known_allergies": (no_known_allergies, 1),
    "omission": (omission, 3),
    "ruled_out": (ruled_out, 2),
}


def derive_sources(rng: random.Random, truth: Chart, today: date, clean: bool):
    """Returns ({source id: (chart copy, source info)}, answer-key entries)."""
    copies = {}
    for s in SOURCES:
        lo, hi = s["age_days"]
        info = {"id": s["id"], "name": s["name"], "last_updated": (today - timedelta(days=rng.randint(lo, hi))).isoformat()}
        copies[s["id"]] = (facility_copy(truth, s["keeps"]), info)

    key = []
    if clean:
        return copies, key
    names = list(MUTATIONS)
    weights = [MUTATIONS[n][1] for n in names]
    touched = {sid: set() for sid in MUTABLE_SOURCES}
    for kind in rng.choices(names, weights=weights, k=rng.choice([1, 1, 2, 2, 3])):
        fn = MUTATIONS[kind][0]
        for sid in rng.sample(MUTABLE_SOURCES, k=len(MUTABLE_SOURCES)):
            if kind == "ruled_out" and SOURCES[[s["id"] for s in SOURCES].index(sid)]["keeps"] == "meds":
                continue  # a pharmacy doesn't record diagnoses
            entries = fn(rng, copies[sid][0], truth, touched[sid])
            if entries:
                for e in entries:
                    touched[sid].add(e["item"])
                    key.append({"patient_id": truth.patient["id"], "source": sid, "mutation": kind, **e})
                break
    return copies, key
