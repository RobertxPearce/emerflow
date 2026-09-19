"""A small internal model of a patient's chart, plus FHIR R4 conversion both ways.

Everything in this directory works on `Chart` objects: the built-in generator
creates them, the Synthea reader converts Synthea's FHIR into them, the conflict
injector copies and changes them, and `to_fhir_bundle` writes them out.
"""

import re
from dataclasses import dataclass, field

from vocab import MEDICATIONS, NO_KNOWN_ALLERGY_SNOMED

RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SNOMED = "http://snomed.info/sct"
HL7 = "http://terminology.hl7.org/CodeSystem"


@dataclass
class Med:
    generic: str | None  # normalized ingredient when known; not written to FHIR as-is
    text: str  # how this record writes it, e.g. "Coumadin 5 mg tablet"
    dose: float | None = None
    unit: str | None = None
    frequency: str | None = None
    rxnorm: str | None = None  # None = record has free text only
    status: str = "active"  # "active" | "not-taken"
    reported_by: str = "clinician"  # "clinician" | "patient"
    note: str | None = None


@dataclass
class Condition:
    name: str
    snomed: str | None = None
    onset: str | None = None
    verification: str = "confirmed"  # "confirmed" | "refuted" (tested for and ruled out)
    note: str | None = None


@dataclass
class Allergy:
    substance: str
    reaction: str | None = None
    no_known: bool = False  # the record explicitly says "no known allergies"


@dataclass
class Chart:
    patient: dict  # id, given, family, gender, birthDate
    conditions: list[Condition] = field(default_factory=list)
    meds: list[Med] = field(default_factory=list)
    allergies: list[Allergy] = field(default_factory=list)


def med_text(generic: str, dose: float, unit: str, style: str = "plain") -> str:
    name = generic if style != "brand" else MEDICATIONS[generic]["brand"]
    return f"{name[0].upper()}{name[1:]} {dose:g} {unit} oral"


# ---- writing FHIR --------------------------------------------------------


def to_fhir_bundle(chart: Chart, source: dict) -> dict:
    """source: {"id", "name", "last_updated"} for the facility that holds this copy."""
    pid = chart.patient["id"]
    org_id = source["id"]
    patient_ref = {"reference": f"Patient/{pid}"}
    resources = [
        {"resourceType": "Organization", "id": org_id, "name": source["name"]},
        {
            "resourceType": "Patient",
            "id": pid,
            "name": [{"given": [chart.patient["given"]], "family": chart.patient["family"]}],
            "gender": chart.patient["gender"],
            "birthDate": chart.patient["birthDate"],
            "managingOrganization": {"reference": f"Organization/{org_id}"},
        },
    ]

    for i, c in enumerate(chart.conditions, 1):
        res = {
            "resourceType": "Condition",
            "id": f"{org_id}-condition-{i}",
            "clinicalStatus": _concept(f"{HL7}/condition-clinical", "active" if c.verification == "confirmed" else "inactive"),
            "verificationStatus": _concept(f"{HL7}/condition-ver-status", c.verification),
            "code": {"text": c.name, **({"coding": [{"system": SNOMED, "code": c.snomed, "display": c.name}]} if c.snomed else {})},
            "subject": patient_ref,
        }
        if c.onset:
            res["onsetDateTime"] = c.onset
        if c.note:
            res["note"] = [{"text": c.note}]
        resources.append(res)

    for i, m in enumerate(chart.meds, 1):
        concept = {"text": m.text}
        if m.rxnorm:
            concept["coding"] = [{"system": RXNORM, "code": m.rxnorm, "display": m.generic or m.text}]
        dosage = []
        if m.dose is not None:
            dosage = [{
                "text": " ".join(str(x) for x in (f"{m.dose:g}", m.unit, m.frequency) if x),
                "doseAndRate": [{"doseQuantity": {"value": m.dose, "unit": m.unit}}],
            }]
        if m.status == "active" and m.reported_by == "clinician":
            res = {"resourceType": "MedicationRequest", "id": f"{org_id}-medreq-{i}", "status": "active", "intent": "order",
                   "medicationCodeableConcept": concept, "subject": patient_ref}
            if dosage:
                res["dosageInstruction"] = dosage
        else:
            # What someone said about a medication: taken as reported by the patient, or not taken.
            res = {"resourceType": "MedicationStatement", "id": f"{org_id}-medstmt-{i}", "status": m.status,
                   "medicationCodeableConcept": concept, "subject": patient_ref}
            if m.reported_by == "patient":
                res["informationSource"] = patient_ref
            if dosage:
                res["dosage"] = dosage
        if m.note:
            res["note"] = [{"text": m.note}]
        resources.append(res)

    for i, a in enumerate(chart.allergies, 1):
        res = {
            "resourceType": "AllergyIntolerance",
            "id": f"{org_id}-allergy-{i}",
            "clinicalStatus": _concept(f"{HL7}/allergyintolerance-clinical", "active"),
            "verificationStatus": _concept(f"{HL7}/allergyintolerance-verification", "confirmed"),
            "patient": patient_ref,
        }
        if a.no_known:
            res["code"] = {"coding": [{"system": SNOMED, "code": NO_KNOWN_ALLERGY_SNOMED, "display": "No known allergy"}],
                           "text": "No known allergies"}
        else:
            res["code"] = {"text": a.substance}
            if a.reaction:
                res["reaction"] = [{"manifestation": [{"text": a.reaction}]}]
        resources.append(res)

    return {
        "resourceType": "Bundle",
        "id": f"{pid}-{org_id}",
        "type": "collection",
        "meta": {"lastUpdated": source["last_updated"], "source": source["name"]},
        "entry": [{"fullUrl": f"{r['resourceType']}/{r['id']}", "resource": r} for r in resources],
    }


def _concept(system: str, code: str) -> dict:
    return {"coding": [{"system": system, "code": code}]}


# ---- reading Synthea's FHIR ------------------------------------------------

_DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*(MG|MCG|UNT|UNITS?)\b", re.IGNORECASE)
_SKIP_SUFFIX = ("(finding)", "(situation)", "(person)", "(procedure)", "(regime/therapy)")


def from_synthea_bundle(bundle: dict) -> Chart | None:
    """Convert one Synthea patient bundle. Returns None for non-patient files."""
    resources = [e["resource"] for e in bundle.get("entry", []) if "resource" in e]
    patient = next((r for r in resources if r["resourceType"] == "Patient"), None)
    if patient is None:
        return None
    name = (patient.get("name") or [{}])[0]
    strip_digits = lambda s: re.sub(r"\d+", "", s)  # Synthea appends numbers to names
    chart = Chart(patient={
        "id": patient["id"],
        "given": strip_digits((name.get("given") or ["Unknown"])[0]),
        "family": strip_digits(name.get("family", "Unknown")),
        "gender": patient.get("gender", "unknown"),
        "birthDate": patient.get("birthDate", ""),
    })

    seen = set()
    for r in resources:
        kind = r["resourceType"]
        if kind == "Condition" and _status(r, "clinicalStatus") == "active":
            coding = (r.get("code", {}).get("coding") or [{}])[0]
            display = coding.get("display") or r.get("code", {}).get("text", "")
            if not display or display.endswith(_SKIP_SUFFIX) or display in seen:
                continue
            seen.add(display)
            chart.conditions.append(Condition(name=re.sub(r"\s*\(disorder\)$", "", display), snomed=coding.get("code"),
                                              onset=(r.get("onsetDateTime") or "")[:10] or None))
        elif kind == "MedicationRequest" and r.get("status") == "active" and "medicationCodeableConcept" in r:
            coding = (r["medicationCodeableConcept"].get("coding") or [{}])[0]
            display = coding.get("display") or r["medicationCodeableConcept"].get("text", "")
            if not display or display in seen:
                continue
            seen.add(display)
            generic = next((g for g in MEDICATIONS if g in display.lower()), None)
            match = _DOSE.search(display)
            chart.meds.append(Med(
                generic=generic,
                text=display,
                dose=float(match.group(1)) if match else None,
                unit=match.group(2).lower().replace("unt", "units") if match else None,
                rxnorm=coding.get("code"),
            ))
        elif kind == "AllergyIntolerance" and _status(r, "clinicalStatus") in ("active", None):
            coding = (r.get("code", {}).get("coding") or [{}])[0]
            substance = coding.get("display") or r.get("code", {}).get("text")
            if substance and substance not in seen:
                seen.add(substance)
                chart.allergies.append(Allergy(substance=substance))
    return chart


def _status(resource: dict, field_name: str) -> str | None:
    coding = (resource.get(field_name, {}).get("coding") or [{}])[0]
    return coding.get("code")
