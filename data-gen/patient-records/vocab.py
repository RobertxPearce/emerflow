"""Medical vocabulary used to build charts and plant realistic disagreements.

Codes: RxNorm ingredient ids for drugs, SNOMED CT for conditions. They are
included so the output looks like real interoperable data. Verify them
(RxNav: https://mor.nlm.nih.gov/RxNav/, SNOMED browser) before relying on
them for anything beyond this demo.
"""

# generic → brand, RxNorm ingredient id, possible doses, unit, frequency, group
MEDICATIONS = {
    "warfarin": {"brand": "Coumadin", "rxnorm": "11289", "doses": [2, 5, 7.5], "unit": "mg", "frequency": "once daily", "group": "anticoagulant"},
    "apixaban": {"brand": "Eliquis", "rxnorm": "1364430", "doses": [2.5, 5], "unit": "mg", "frequency": "twice daily", "group": "anticoagulant"},
    "clopidogrel": {"brand": "Plavix", "rxnorm": "32968", "doses": [75], "unit": "mg", "frequency": "once daily", "group": "antiplatelet"},
    "metoprolol": {"brand": "Lopressor", "rxnorm": "6918", "doses": [25, 50, 100], "unit": "mg", "frequency": "twice daily", "group": "beta blocker"},
    "lisinopril": {"brand": "Zestril", "rxnorm": "29046", "doses": [10, 20, 40], "unit": "mg", "frequency": "once daily", "group": "ACE inhibitor"},
    "amlodipine": {"brand": "Norvasc", "rxnorm": "17767", "doses": [5, 10], "unit": "mg", "frequency": "once daily", "group": "calcium channel blocker"},
    "atorvastatin": {"brand": "Lipitor", "rxnorm": "83367", "doses": [20, 40, 80], "unit": "mg", "frequency": "once daily", "group": "statin"},
    "metformin": {"brand": "Glucophage", "rxnorm": "6809", "doses": [500, 1000], "unit": "mg", "frequency": "twice daily", "group": "antidiabetic"},
    "insulin glargine": {"brand": "Lantus", "rxnorm": "274783", "doses": [10, 20, 30], "unit": "units", "frequency": "at bedtime", "group": "insulin"},
    "furosemide": {"brand": "Lasix", "rxnorm": "4603", "doses": [20, 40], "unit": "mg", "frequency": "once daily", "group": "diuretic"},
    "levothyroxine": {"brand": "Synthroid", "rxnorm": "10582", "doses": [50, 75, 100], "unit": "mcg", "frequency": "once daily", "group": "thyroid"},
    "albuterol": {"brand": "ProAir", "rxnorm": "435", "doses": [90], "unit": "mcg", "frequency": "2 puffs as needed", "group": "bronchodilator"},
}

# Groups a clinician would call "blood thinners".
BLOOD_THINNER_GROUPS = {"anticoagulant", "antiplatelet"}

# condition → SNOMED CT, typical medications, how common it is in this population
CONDITIONS = {
    "Hypertension": {"snomed": "38341003", "meds": ["lisinopril", "amlodipine", "metoprolol"], "prevalence": 0.45},
    "Hyperlipidemia": {"snomed": "55822004", "meds": ["atorvastatin"], "prevalence": 0.35},
    "Type 2 diabetes mellitus": {"snomed": "44054006", "meds": ["metformin", "insulin glargine"], "prevalence": 0.2},
    "Atrial fibrillation": {"snomed": "49436004", "meds": ["warfarin", "apixaban", "metoprolol"], "prevalence": 0.12},
    "Coronary artery disease": {"snomed": "53741008", "meds": ["clopidogrel", "atorvastatin", "metoprolol"], "prevalence": 0.12},
    "Heart failure": {"snomed": "84114007", "meds": ["furosemide", "metoprolol", "lisinopril"], "prevalence": 0.08},
    "Hypothyroidism": {"snomed": "40930008", "meds": ["levothyroxine"], "prevalence": 0.1},
    "Asthma": {"snomed": "195967001", "meds": ["albuterol"], "prevalence": 0.08},
    "Chronic obstructive pulmonary disease": {"snomed": "13645005", "meds": ["albuterol"], "prevalence": 0.06},
}

# Conditions that are often tested for and then ruled out (used for the "ruled out" trap).
RULE_OUT_CANDIDATES = {
    "Type 2 diabetes mellitus": "HbA1c 5.4%, diabetes ruled out.",
    "Pulmonary embolism": "CT angiogram negative, pulmonary embolism ruled out.",
    "Myocardial infarction": "Serial troponins negative, myocardial infarction ruled out.",
    "Deep vein thrombosis": "Leg ultrasound negative, DVT ruled out.",
}

# substance → typical reaction
ALLERGIES = {
    "Penicillin": "Hives",
    "Sulfonamide antibiotics": "Rash",
    "Codeine": "Nausea and vomiting",
    "Iodinated contrast": "Hives",
    "Latex": "Contact dermatitis",
    "Peanut": "Anaphylaxis",
    "Shellfish": "Anaphylaxis",
}
ALLERGY_RATE = 0.35  # share of patients with at least one allergy

# SNOMED CT concept used by EHRs to record "no known allergy".
NO_KNOWN_ALLERGY_SNOMED = "716186003"

FIRST_NAMES = {
    "female": ["Maria", "Aisha", "Emily", "Grace", "Sofia", "Linh", "Olivia", "Fatima", "Hannah", "Rosa", "Keisha", "Mei"],
    "male": ["James", "Omar", "Daniel", "Wei", "Carlos", "Andre", "Samuel", "Ravi", "Michael", "Tomas", "Darnell", "Yusuf"],
}
LAST_NAMES = ["Johnson", "Nguyen", "Patel", "Garcia", "Williams", "Kim", "Okafor", "Brown", "Rossi", "Hernandez",
              "Davis", "Cohen", "Ali", "Martin", "Walker", "Chen", "Lopez", "Jackson", "Singh", "Murphy"]
