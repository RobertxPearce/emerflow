"""Checks the generator end to end.

    python3 check.py

- same seed → identical files; different seed → different files
- every bundle is well-formed FHIR (unique ids, references resolve)
- every answer-key entry is actually visible in the source file it names
- scoring: a perfect checker scores 1.0; the naive checker catches everything but raises false alarms
- the Synthea reader handles a bundle in Synthea's format
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from chart import from_synthea_bundle
from naive_checker import check as naive_check
from score import score

HERE = Path(__file__).resolve().parent


def generate(out: Path, *args: str):
    subprocess.run([sys.executable, str(HERE / "generate.py"), "--out", str(out), *args], check=True, capture_output=True)


def digest(out: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(out.rglob("*.json*")):
        h.update(str(path.relative_to(out)).encode() + path.read_bytes())
    return h.hexdigest()


def check_bundle(bundle: dict):
    assert bundle["resourceType"] == "Bundle"
    resources = [e["resource"] for e in bundle["entry"]]
    ids = {f"{r['resourceType']}/{r['id']}" for r in resources}
    assert len(ids) == len(resources), "duplicate resource ids"
    for r in resources:
        for field in ("subject", "patient", "managingOrganization", "informationSource"):
            if field in r:
                assert r[field]["reference"] in ids, f"dangling reference {r[field]['reference']}"


def texts(bundle: dict) -> str:
    return json.dumps(bundle).lower()


def check_answer_key(out: Path):
    key = [json.loads(line) for line in (out / "answer_key.jsonl").read_text().splitlines()]
    for e in key:
        source = json.loads((out / "sources" / e["patient_id"] / f"{e['source']}.json").read_text())
        body = texts(source)
        if e["expected"] == "gap":
            assert e["true_value"].lower() not in body, f"gap not applied: {e}"
        elif e["mutation"] in ("denies_blood_thinner", "no_known_allergies"):
            assert '"not-taken"' in body or "no known allergies" in body, f"negation missing: {e}"
        elif e["mutation"] == "ruled_out":
            assert '"refuted"' in body and e["item"].lower() in body, f"ruled-out condition missing: {e}"
        else:
            assert e["source_value"].split(" (")[0].lower() in body, f"changed value not in file: {e}"
    return key


def check_synthea_reader():
    sample = {"resourceType": "Bundle", "type": "transaction", "entry": [
        {"resource": {"resourceType": "Patient", "id": "abc-123", "gender": "female", "birthDate": "1950-02-03",
                      "name": [{"given": ["Maria491"], "family": "Lopez832"}]}},
        {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]},
                      "code": {"coding": [{"system": "http://snomed.info/sct", "code": "49436004", "display": "Atrial fibrillation (disorder)"}]}}},
        {"resource": {"resourceType": "Condition", "clinicalStatus": {"coding": [{"code": "active"}]},
                      "code": {"coding": [{"code": "160903007", "display": "Full-time employment (finding)"}]}}},
        {"resource": {"resourceType": "MedicationRequest", "status": "active",
                      "medicationCodeableConcept": {"coding": [{"code": "855332", "display": "Warfarin Sodium 5 MG Oral Tablet"}]}}},
        {"resource": {"resourceType": "MedicationRequest", "status": "stopped",
                      "medicationCodeableConcept": {"coding": [{"code": "1", "display": "Old drug 10 MG"}]}}},
        {"resource": {"resourceType": "AllergyIntolerance", "clinicalStatus": {"coding": [{"code": "active"}]},
                      "code": {"coding": [{"display": "Peanut (substance)"}]}}},
    ]}
    chart = from_synthea_bundle(sample)
    assert chart.patient["given"] == "Maria" and chart.patient["family"] == "Lopez"
    assert [c.name for c in chart.conditions] == ["Atrial fibrillation"], chart.conditions
    assert len(chart.meds) == 1 and chart.meds[0].generic == "warfarin" and chart.meds[0].dose == 5
    assert [a.substance for a in chart.allergies] == ["Peanut (substance)"]
    assert from_synthea_bundle({"resourceType": "Bundle", "entry": []}) is None


def main():
    with tempfile.TemporaryDirectory() as tmp:
        a, b, c = Path(tmp, "a"), Path(tmp, "b"), Path(tmp, "c")
        generate(a, "--seed", "1", "--patients", "80")
        generate(b, "--seed", "1", "--patients", "80")
        generate(c, "--seed", "2", "--patients", "80")
        assert digest(a) == digest(b), "same seed produced different files"
        assert digest(a) != digest(c), "different seeds produced identical files"

        bundles = list(a.rglob("*.json"))
        for path in bundles:
            if path.name != "manifest.json":
                check_bundle(json.loads(path.read_text()))
        key = check_answer_key(a)

        perfect = [e for e in key if e["expected"] == "disagreement"]
        assert score(perfect, key)["recall"] == 1.0 and score(perfect, key)["precision"] == 1.0
        naive = score(list(naive_check(a / "sources")), key)
        assert naive["recall"] == 1.0 and naive["precision"] < 0.5, naive

    check_synthea_reader()
    print(f"OK: deterministic, {len(bundles) - 1} FHIR bundles valid, {len(key)} answer-key entries visible in files, "
          f"scoring correct (naive checker precision {naive['precision']}), Synthea reader works on a sample bundle.")


if __name__ == "__main__":
    main()
