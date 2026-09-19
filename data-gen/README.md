# data-gen

Generates **artificial data** for Hospital Swarm, so the project can be built, demoed and tested
without real patient data. Everything is synthetic, and the same seed always produces the same data.

| Directory | Generates | Used for | Needs |
| --- | --- | --- | --- |
| [`hospital-op/`](hospital-op/) | A week (or more) of hospital operations: ER arrivals, bed occupancy per unit, transfers, discharges, nurse staffing, and an optional mass-casualty event | Agents that decide who goes where; dashboards; testing the bed plan | Python 3.10+, `simpy` |
| [`patient-records/`](patient-records/) | Patients' medical records (FHIR) as held by 4 different facilities, with disagreements planted on purpose, plus an **answer key** listing every one | Building and **scoring** DeepChart (the record checker) | Python 3.10+ only. Synthea is optional |

## Quick start

```bash
cd data-gen
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time

cd hospital-op && ../.venv/bin/python generate.py         # → hospital-op/output/
cd ../patient-records && python3 generate.py              # → patient-records/output/
```

## What each one creates

**`hospital-op/output/`**
- `census.csv`: occupancy per unit every 15 minutes
- `events.jsonl`: every arrival, admission, transfer and discharge
- `patients.csv`: each patient's journey and wait times
- `staffing.csv`: nurses on shift vs. required, hourly
- `units.json`, `manifest.json`

**`patient-records/output/`**
- `sources/<patient>/<facility>.json`: the records a checker sees, as FHIR bundles
- `answer_key.jsonl`: every planted change and whether it should be flagged
- `canonical/<patient>.json`: the true chart, for scoring only
- `manifest.json`

Each directory's README explains how the generation works, every output field, and how to
adjust or verify it (`check.py` in each).
