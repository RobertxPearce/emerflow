# patient-records: medical records with planted disagreements

Creates realistic fake patients, then produces the copies of their records that **four different
facilities** would hold. Each copy is partial, dated, and sometimes **changed on purpose** in the
ways real records drift apart. Every change is listed in an **answer key**, so a record checker
such as DeepChart can be scored: did it catch the real disagreements, and did it avoid false alarms?

```bash
cd data-gen/patient-records
python3 generate.py                          # 50 patients, seed 42 → output/
python3 generate.py --patients 200 --seed 7
python3 check.py                             # verify

python3 naive_checker.py > naive.jsonl       # a deliberately careless checker…
python3 score.py naive.jsonl                 # …and its score
```

Standard library only. No install is needed for the built-in generator.

| Option | Default | |
| --- | --- | --- |
| `--patients` | `50` | Built-in patients to create |
| `--seed` | `42` | Same seed → identical output |
| `--clean-share` | `0.3` | Share of patients with no planted changes (to measure false alarms) |
| `--today` | `2026-09-19` | The date records are "pulled"; facility copies are dated before it |
| `--from-synthea DIR` | — | Use Synthea patients instead of the built-in generator |
| `--out` | `./output` | Output folder (replaced on each run) |

---

## How the generation works

```
 1. true charts            2. facility copies              3. planted changes          4. output
 built-in generator   →    each facility keeps only   →    real disagreements +    →   FHIR bundles
 or Synthea                what it would know, dated        look-alike traps             + answer key
```

All steps work on a small internal model (`chart.py`: `Chart` with conditions, medications and
allergies), so both patient sources go through exactly the same pipeline.

### 1. The true chart (`generate_patients.py`, or Synthea)

**Built-in:**
- Age is centered around 64 (hospital patients skew older), with a random sex and name.
- Chronic conditions are drawn from `vocab.CONDITIONS` with age-adjusted prevalence:
  hypertension, diabetes, atrial fibrillation, heart failure and others.
- Each condition brings 1–2 of its usual medications with a realistic dose and frequency.
  Atrial fibrillation gets exactly one anticoagulant (warfarin or apixaban).
- About 35% of patients get one or two allergies, each with its reaction.

**Synthea** (optional, more detailed patients with full life histories):
- `./get_synthea.sh [patients] [seed]` downloads Synthea (~180 MB, needs Java 17+) and generates
  patients into `synthea/output/fhir/`.
- `python3 generate.py --from-synthea synthea/output/fhir` then runs the same pipeline.
- The reader keeps active disorders (skipping findings such as "Full-time employment"), active
  medications with the dose parsed from their name, and allergies.

This chart is written to `canonical/` and treated as the truth. A checker must **not** read it:
it's only for scoring.

### 2. Facility copies (`inject_conflicts.py`)

Each patient's chart is copied to four facilities. Each keeps only what it would know, dated
before `--today`:

| Facility id | Keeps | Dated |
| --- | --- | --- |
| `st-aurelia-ed` | Everything, **never changed** (the current ER chart) | today |
| `hospital-b-cardiology` | Heart-related conditions and medications, plus allergies | 30–400 days ago |
| `local-clinic` | Everything | 14–300 days ago |
| `retail-pharmacy` | Medications and allergies (no diagnoses) | 1–60 days ago |

Something missing from a facility's copy because it would never have known it is normal. That
is not listed in the answer key.

### 3. Planted changes

For about 70% of patients, 1–3 changes are applied to the non-ER copies. Each change is chosen
by weight and applied to a facility that has the relevant item. The same item is never changed
twice in one copy. Every change goes into the answer key with the expected verdict:

| Mutation | What changes in the copy | Expected | Why (from real-world causes) |
| --- | --- | --- | --- |
| `dose_mismatch` | A different dose of the same drug | **disagreement** | A specialist changed it and this record wasn't updated; a note was copied forward; records were attached, not merged |
| `patient_reported` | A patient-reported statement with a different dose | **disagreement** | The patient says 20 mg, the chart says 10 mg; both got written down |
| `denies_blood_thinner` | Blood thinner removed; statement "Patient denies taking any blood thinners" (`status: not-taken`) | **disagreement** | Explicit "no" vs. the chart's "yes" |
| `no_known_allergies` | Allergies replaced by "No known allergies" (SNOMED 716186003) | **disagreement** | Explicit "no" vs. a documented allergy |
| `brand_name` | "Coumadin 5 mg oral" instead of "Warfarin 5 mg oral"; code removed | not a disagreement | Different names for the same drug |
| `abbreviation` | "warfarin 5mg PO QD" | not a disagreement | Clinical shorthand for the same order |
| `ruled_out` | Adds e.g. "Pulmonary embolism: CT angiogram negative, ruled out" (`verificationStatus: refuted`) | not a disagreement | The word appears, but the patient doesn't have it |
| `omission` | An item deleted from a copy that would normally have it | gap | "Not mentioned" is not the same as "says no" |

The traps (the last four rows) come from the "Six everyday reasons" and "Not mentioned is not
'says no'" sections of the project brief. A good checker flags the first four rows and none of
the others.

### 4. Output format

Records are **FHIR R4** bundles, the standard that hospitals use to share records:

| Chart item | FHIR resource |
| --- | --- |
| Patient, facility | `Patient`, `Organization` (the bundle's `meta.source` and `meta.lastUpdated` say who and when) |
| Diagnosis | `Condition`, with `verificationStatus` `confirmed` or `refuted` and SNOMED CT coding |
| Prescribed medication | `MedicationRequest` with RxNorm coding (or free text only, for brand/abbreviated entries) and `dosageInstruction` |
| Something *said* about a medication | `MedicationStatement`: `status: not-taken` for denials, `informationSource: Patient` for patient-reported doses |
| Allergy | `AllergyIntolerance`, or the "No known allergy" SNOMED concept |

---

## Output files

```
output/
  sources/<patient-id>/<facility-id>.json   what a checker reads: 4 FHIR bundles per patient
  canonical/<patient-id>.json               the true chart (for scoring only)
  answer_key.jsonl                          one planted change per line
  manifest.json                             options and counts by mutation
```

**`answer_key.jsonl`** entry:

```json
{"patient_id": "patient-0007", "source": "hospital-b-cardiology", "mutation": "dose_mismatch",
 "category": "medication", "item": "warfarin", "expected": "disagreement",
 "true_value": "Warfarin 5 mg oral", "source_value": "Warfarin 7.5 mg oral",
 "explanation": "A specialist changed the dose; this record was never updated."}
```

`category` is `medication` (item = generic name), `allergy` (item = substance) or `condition`.
`expected` is `disagreement`, `not_a_disagreement` or `gap`.

---

## Scoring a checker

A checker writes one line per item it flags:

```json
{"patient_id": "patient-0007", "category": "medication", "item": "warfarin"}
```

`python3 score.py predictions.jsonl` reports:
- **recall:** real disagreements caught
- **precision:** share of flags that were real
- **false alarms:** broken down by which trap caused them
- **caught by mutation:** results for each kind of real disagreement

Brand names in predictions are accepted (Coumadin counts as warfarin).

**Baseline.** `naive_checker.py` compares text literally and treats anything missing as a
conflict. On the default run it catches all 16 real disagreements but raises 133 flags. That is
**12% precision**: it is fooled by gaps, ruled-out diagnoses, brand names and abbreviations. A
useful checker needs high recall *and* high precision; this is the number to beat.

## Checking it

`check.py` verifies that:
- the same seed gives identical files, and a different seed gives different files
- every bundle is well-formed (unique ids, all references resolve)
- every answer-key entry is actually visible in the file it names
- a perfect checker scores 100% and the naive one scores low
- the Synthea reader handles a bundle in Synthea's format

## Limits and notes

- **Codes need checking.** RxNorm and SNOMED codes are included for realism and were written by
  hand. Verify them with [RxNav](https://mor.nlm.nih.gov/RxNav/) or a SNOMED browser before
  relying on them.
- **Synthea reader:** tested against a hand-made bundle in Synthea's format, not yet against a
  real Synthea download. Run `get_synthea.sh` once and `check.py` again to confirm.
- **Scope:** only medications, allergies and diagnoses. Lab results, vitals and free-text notes
  are not generated yet. Free-text notes would make the checker's job more realistic; an LLM
  could write them from these structured charts.
- **Linking:** patients here are not linked to the anonymous patients in `../hospital-op`. To link
  them, give the ICU patients in `hospital-op` records from this generator by id.
