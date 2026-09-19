"""Built-in patient generator (no Java or downloads needed).

Creates each patient's "true" chart: demographics, chronic conditions, the
medications those conditions are usually treated with, and allergies. These
charts are the ground truth that facility copies are derived from.
"""

import random
from datetime import date, timedelta

from chart import Allergy, Chart, Condition, Med, med_text
from vocab import ALLERGIES, ALLERGY_RATE, CONDITIONS, FIRST_NAMES, LAST_NAMES, MEDICATIONS

ANTICOAGULANTS = ["warfarin", "apixaban"]


def build_chart(rng: random.Random, index: int, today: date) -> Chart:
    gender = rng.choice(["female", "male"])
    age = int(min(95, max(25, rng.gauss(64, 15))))  # hospital patients skew older
    birth = today - timedelta(days=age * 365 + rng.randint(0, 364))
    chart = Chart(patient={
        "id": f"patient-{index:04d}",
        "given": rng.choice(FIRST_NAMES[gender]),
        "family": rng.choice(LAST_NAMES),
        "gender": gender,
        "birthDate": birth.isoformat(),
    })

    # Conditions: more likely with age.
    age_factor = 0.5 + age / 100
    for name, info in CONDITIONS.items():
        if rng.random() < info["prevalence"] * age_factor:
            onset = today - timedelta(days=rng.randint(180, 365 * min(20, max(1, age - 20))))
            chart.conditions.append(Condition(name=name, snomed=info["snomed"], onset=onset.isoformat()))

    # Medications: 1–2 typical drugs per condition, only one anticoagulant.
    chosen: list[str] = []
    for c in chart.conditions:
        options = [m for m in CONDITIONS[c.name]["meds"] if m not in chosen]
        if c.name == "Atrial fibrillation":
            anticoag = rng.choice(ANTICOAGULANTS)
            if anticoag not in chosen and not any(a in chosen for a in ANTICOAGULANTS):
                chosen.append(anticoag)
            options = [m for m in options if m not in ANTICOAGULANTS]
        for generic in rng.sample(options, k=min(len(options), rng.choice([1, 1, 2]))):
            chosen.append(generic)
    for generic in chosen:
        info = MEDICATIONS[generic]
        dose = rng.choice(info["doses"])
        chart.meds.append(Med(generic=generic, text=med_text(generic, dose, info["unit"]), dose=dose, unit=info["unit"],
                              frequency=info["frequency"], rxnorm=info["rxnorm"]))

    # Allergies.
    if rng.random() < ALLERGY_RATE:
        for substance in rng.sample(sorted(ALLERGIES), k=rng.choice([1, 1, 2])):
            chart.allergies.append(Allergy(substance=substance, reaction=ALLERGIES[substance]))

    return chart


def generate(count: int, seed: int, today: date) -> list[Chart]:
    rng = random.Random(seed)
    return [build_chart(rng, i, today) for i in range(1, count + 1)]
