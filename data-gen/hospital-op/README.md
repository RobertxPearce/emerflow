# hospital-op: hospital operations data

Simulates a hospital over days or weeks and records what happens: patients arriving at the ER,
waiting for a bay, being treated, admitted or sent home, moving between units, and being
discharged, plus how many nurses are on shift. It can also add a **mass-casualty event** at a
chosen time. The output is what a hospital's bed-management system would log.

```bash
cd data-gen/hospital-op
../.venv/bin/python generate.py                                  # 7 days, seed 42, mass casualty on day 6 at 21:47
../.venv/bin/python generate.py --days 28 --seed 7 --no-mci
../.venv/bin/python generate.py --mci 2026-09-19T21:47 --mci-size 60 --mci-window 30
../.venv/bin/python check.py                                     # verify
```

| Option | Default | |
| --- | --- | --- |
| `--start` | `2026-09-14` | First day. Runs start at midnight |
| `--days` | `7` | Length of the run |
| `--seed` | `42` | Same seed → identical output |
| `--mci` | day 6, 21:47 | Mass-casualty time. `--no-mci` turns it off |
| `--mci-size`, `--mci-window` | `25`, `20` | Casualties, and the minutes over which they arrive |
| `--census-every` | `15` | Minutes between census snapshots |
| `--out` | `./output` | Output folder |

A 7-day run takes about 0.1 seconds.

---

## How the generation works

The model is a **discrete-event simulation** built with [SimPy](https://simpy.readthedocs.io).
Beds are limited resources. Each patient is a process that requests a bed, waits if none is free
(sickest first), holds it for a random time, and moves on. Everything lives in two files:
`config.py` holds every number, and `model.py` holds the logic.

### 1. Starting state
The run begins with beds already partly full (`start_occupancy` per unit). Each starting patient
is somewhere in the middle of their stay, so the hospital doesn't start empty.

### 2. ER arrivals
- Patients arrive at random (a Poisson process). The rate changes **by hour of day**
  (`HOURLY_PATTERN`: quiet at 4 a.m., busy late morning to evening) and **by weekday**
  (`WEEKDAY_PATTERN`: Mondays busiest). The average is `ED_ARRIVALS_PER_DAY`.
- A varying rate is simulated by "thinning": arrivals are drawn at the peak rate, and each is kept
  with probability (current rate ÷ peak rate).
- Each patient gets an **Emergency Severity Index (ESI)** from 1 (most urgent) to 5, following `ESI_MIX`.

### 3. The ER visit
1. **Triage and registration** (`TRIAGE_MINUTES`).
2. **Wait for an ER bay.** Bays go to the most urgent patient first, so a busy ER makes
   low-urgency patients wait hours while urgent ones are seen quickly.
3. **Treatment** until a decision (`ED_TREATMENT`, by ESI).
4. **Decision:** sent home, or admitted with probability `ADMIT_PROBABILITY[ESI]` to a unit chosen
   from `ADMIT_DESTINATION`.
5. **Boarding:** an admitted patient keeps the ER bay until a bed on the target unit is free, plus
   `ADMIT_PROCESS_HOURS` for report and transport. This is the real-world cause of ER crowding.

### 4. Inpatient stays
- Each unit stay lasts a random `LENGTH_OF_STAY`. The patient then moves according to `NEXT_UNIT`,
  e.g. ICU → step-down (60%), general (25%), home (15%).
- A patient moving units keeps their current bed until the next unit has room.
- Patients going home leave only during `DISCHARGE_HOURS` (10:00–18:00), so beds free up in the
  afternoon, not overnight.
- Every freed bed is unavailable while it's cleaned (`BED_CLEANING_HOURS`).

### 5. Scheduled surgery
On weekdays, `ELECTIVE_CASES_PER_WEEKDAY` operations start between 07:00 and 15:00. They compete
for operating rooms with emergency surgery, which has higher priority. After surgery, patients go
to the ICU, step-down or a general bed.

### 6. Staffing
- 12-hour shifts start at 07:00 and 19:00.
- Nurses per shift are planned from the larger of the current census and the peak census of the
  same shift last time. That number is multiplied by `STAFFING_BUFFER` and divided by the unit's
  nurse ratio.
- Each scheduled nurse calls in sick with probability `SICK_CALL_RATE`.
- Every hour, the required number of nurses (census ÷ ratio) is compared with the nurses on shift.

### 7. Mass-casualty event (optional)
At `--mci`, `--mci-size` casualties arrive spread over `--mci-window` minutes. Each gets a
**START triage** category (`MCI_TRIAGE_MIX`: immediate, delayed, minor, expectant), which sets
their priority. Expectant patients receive comfort care after salvageable patients are served.
They then follow the same ER path as everyone else, which is what overloads the hospital.

### Randomness
All randomness comes from one seeded random generator, so a seed reproduces a run exactly.
Durations use lognormal distributions (always positive, with a long tail), which is how hospital
times usually behave.

---

## Output files

**`census.csv`**: one row per unit every `--census-every` minutes

| Column | |
| --- | --- |
| `time` | ISO timestamp |
| `unit` | `ER`, `ICU`, `SDU` (step-down), `OR`, `GEN` (general beds) |
| `occupied`, `capacity`, `occupancy_pct` | Beds in use (including beds being cleaned) |
| `waiting_for_bed` | Patients queued for this unit |
| `boarding_in_er` | ER only: admitted patients still waiting in an ER bay |

**`events.jsonl`**: one JSON object per line, in time order

| `type` | Extra fields |
| --- | --- |
| `arrival` | `patient`, `esi`, and for casualties `triage`, `mci: true` |
| `ed_bed` | `patient`, `waited_min` |
| `admit_decision` | `patient`, `unit` |
| `admitted` | `patient`, `unit`, `boarded_min` |
| `left_ed` | `patient`, `disposition` (`treated_and_released` or `expectant_comfort_care`) |
| `transfer` | `patient`, `from_unit`, `unit` |
| `discharge` | `patient`, `unit` |
| `elective_arrival` | `patient` |
| `shift_start` | `unit`, `scheduled`, `sick_calls`, `on_shift` |
| `mci_declared` | `size`, `window_min` |

**`patients.csv`**: one row per patient

| Column | |
| --- | --- |
| `patient_id` | `pt-00001`… |
| `source` | `initial` (in a bed at the start), `ed`, `elective`, `mci` |
| `esi`, `mci_triage` | Urgency, and START category for casualties |
| `arrived`, `ed_bed_at`, `decision_at`, `admitted_at`, `left_at` | Timestamps (blank if it didn't happen) |
| `ed_wait_min`, `boarding_min` | Arrival → ER bay; admit decision → left the ER |
| `disposition` | `treated_and_released`, `discharged`, `expectant_comfort_care`, `in_hospital` (still there at the end) |
| `path` | Units visited, e.g. `ER>ICU>SDU>GEN` |

**`staffing.csv`**: hourly per unit: `nurses_on_shift`, `nurses_required`, `short_by`

**`units.json`**: unit codes, names, beds, nurse ratios. **`manifest.json`**: run options plus a
summary (median ER waits by ESI, boarding, peak occupancy, short-staffed hours, casualty waits).

### Example (default run)

```
ER median wait:    {'1': 14, '2': 16, '3': 23, '4': 69, '5': 375} (minutes, by ESI)
median boarding:   101 min
peak occupancy:    {'ER': 100.0, 'ICU': 100.0, 'SDU': 100.0, 'OR': 100.0, 'GEN': 88.9}
mass casualty:     median wait for an ER bay: immediate 24, delayed 61, minor 302, expectant 511 (min)
```

---

## Checking it

`check.py` runs the generator several times and verifies that:
- the same seed gives identical files, and a different seed gives different files
- no unit is ever over capacity
- each patient's timestamps are in order
- events are in time order and refer to real patients
- `short_by` is computed correctly

## Making it more realistic

Every value in `config.py` is marked **[standard]** or **[placeholder]**.
- **Standard:** the nurse ratios are California's mandated minimums.
- **Placeholders:** everything else is a plausible value chosen for the demo, not taken from a dataset.

For numbers you can cite, replace the placeholders with published statistics:
- **Arrival rates, hourly/weekday patterns, ESI mix, ER waits, admission rates:** CDC's National
  Hospital Ambulatory Medical Care Survey (NHAMCS), ED component.
- **Length of stay by unit and diagnosis:** AHRQ's Healthcare Cost and Utilization Project (HCUP).
- **Bed counts and occupancy for a hospital size:** hospital cost reports or AHA survey data.
- **Mass-casualty triage mix:** published after-action reports for comparable incidents.

## Limits

- Patients are anonymous flows (an id, an urgency and a path), not clinical records. Clinical
  detail comes from `../patient-records`.
- It doesn't model diagnoses, doctors, imaging queues, ambulance diversion or patients who leave
  without being seen.
- The ESI → destination and length-of-stay rules are simplified averages.
