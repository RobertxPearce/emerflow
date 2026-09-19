"""Every number the hospital-operations generator uses, in one place.

Values marked [standard] follow a published rule. Values marked [placeholder]
are plausible starting points chosen for the demo, not taken from a dataset.
Replace them with sourced numbers (see README, "Making it more realistic").
Times are in hours unless the name says otherwise.
"""

# ---- Units ---------------------------------------------------------------
# beds: staffed beds (ER: treatment bays; OR: operating rooms)
# nurse_ratio: patients per nurse. [standard] California's mandated minimums:
#   ICU 1:2, ER 1:4, step-down 1:3, medical-surgical 1:5, OR 1:1 (circulating nurse)
# start_occupancy: share of beds filled at the start of the run [placeholder]
UNITS = {
    "ER": {"name": "Emergency", "beds": 40, "nurse_ratio": 4, "start_occupancy": 0.55},
    "ICU": {"name": "Intensive Care", "beds": 48, "nurse_ratio": 2, "start_occupancy": 0.88},
    "SDU": {"name": "Step-Down", "beds": 30, "nurse_ratio": 3, "start_occupancy": 0.75},
    "OR": {"name": "Surgery", "beds": 12, "nurse_ratio": 1, "start_occupancy": 0.0},
    "GEN": {"name": "General Beds", "beds": 180, "nurse_ratio": 5, "start_occupancy": 0.8},
}

# ---- Emergency department arrivals ---------------------------------------
ED_ARRIVALS_PER_DAY = 160  # [placeholder] average walk-in + ambulance arrivals

# Relative arrival rate by hour of day (0 = midnight). Low overnight, peak late morning
# to evening. [placeholder shape]
HOURLY_PATTERN = [
    0.45, 0.38, 0.32, 0.28, 0.27, 0.30,  # 00-05
    0.45, 0.70, 0.95, 1.20, 1.35, 1.40,  # 06-11
    1.40, 1.38, 1.35, 1.32, 1.30, 1.30,  # 12-17
    1.28, 1.22, 1.12, 0.98, 0.80, 0.60,  # 18-23
]
# Relative rate by weekday (Monday first). Mondays are usually busiest. [placeholder]
WEEKDAY_PATTERN = [1.10, 1.02, 1.00, 0.98, 0.98, 0.95, 0.97]

# Emergency Severity Index (1 = most urgent, 5 = least). [placeholder mix]
ESI_MIX = {1: 0.01, 2: 0.12, 3: 0.45, 4: 0.32, 5: 0.10}

# Triage and registration before an ER bay can be assigned (median minutes, spread). [placeholder]
TRIAGE_MINUTES = (10, 0.5)

# ER treatment time until a decision (median hours, spread). Lognormal. [placeholder]
ED_TREATMENT = {1: (2.0, 0.5), 2: (4.0, 0.5), 3: (4.0, 0.5), 4: (2.0, 0.5), 5: (1.2, 0.5)}

# Chance an ER patient is admitted to the hospital, by ESI. [placeholder]
ADMIT_PROBABILITY = {1: 0.85, 2: 0.55, 3: 0.25, 4: 0.03, 5: 0.01}

# Where admitted patients go, by ESI. Each row sums to 1. [placeholder]
ADMIT_DESTINATION = {
    1: {"ICU": 0.6, "OR": 0.3, "SDU": 0.1},
    2: {"ICU": 0.2, "SDU": 0.35, "GEN": 0.35, "OR": 0.1},
    3: {"GEN": 0.8, "SDU": 0.15, "OR": 0.05},
    4: {"GEN": 1.0},
    5: {"GEN": 1.0},
}

# ---- Inpatient stays -----------------------------------------------------
# After the decision to admit: bed assignment, report and transport, while the
# patient still occupies the ER bay (median hours, spread). [placeholder]
ADMIT_PROCESS_HOURS = (1.5, 0.5)

# A bed stays unavailable after a patient leaves while it is cleaned (median hours, spread). [placeholder]
BED_CLEANING_HOURS = (0.75, 0.4)

# Length of stay per unit (median hours, spread). Lognormal. [placeholder]
LENGTH_OF_STAY = {"ICU": (72, 0.6), "SDU": (48, 0.5), "GEN": (72, 0.6), "OR": (2.5, 0.35)}

# Where patients go after each unit. "home" = discharged. [placeholder]
NEXT_UNIT = {
    "OR": {"ICU": 0.25, "SDU": 0.25, "GEN": 0.5},
    "ICU": {"SDU": 0.6, "GEN": 0.25, "home": 0.15},
    "SDU": {"GEN": 0.5, "home": 0.5},
    "GEN": {"home": 1.0},
}

# Inpatients who are ready to leave are discharged only between these hours,
# which is why beds free up in the afternoon, not overnight. [placeholder]
DISCHARGE_HOURS = (10, 18)

# ---- Scheduled surgery ---------------------------------------------------
ELECTIVE_CASES_PER_WEEKDAY = 22  # [placeholder]
ELECTIVE_START_HOURS = (7, 15)  # first and last case start

# ---- Staffing ------------------------------------------------------------
SHIFT_STARTS = (7, 19)  # 12-hour shifts
# Nurses scheduled = (the larger of: census now, peak census in this shift yesterday)
#                   × buffer ÷ ratio. This is how charge nurses plan ahead. [placeholder]
STAFFING_BUFFER = 1.10
SICK_CALL_RATE = 0.05  # chance each scheduled nurse doesn't show up [placeholder]

# ---- Mass-casualty event (optional) --------------------------------------
# START triage categories: immediate (red), delayed (yellow), minor (green),
# expectant (black). [placeholder mix]
MCI_TRIAGE_MIX = {"immediate": 0.15, "delayed": 0.25, "minor": 0.55, "expectant": 0.05}
MCI_TRIAGE_TO_ESI = {"immediate": 1, "delayed": 2, "minor": 4, "expectant": 1}
