"""Deterministic FHIR R4 fixtures for tests and the setup smoke test.

These are hand-built bundles, not Synthea output. They exist so the pipeline can
be exercised end-to-end without Java. Each generator is seeded and returns the
same bundle for the same seed, which lets the reproducibility tests assert on a
digest.
"""
from __future__ import annotations

import copy
from typing import Any

SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"

# Codings used by the built-in cohort recipes.
ASTHMA = {"system": SNOMED, "code": "195967001", "display": "Asthma"}
DIABETES = {"system": SNOMED, "code": "44054006", "display": "Type 2 diabetes mellitus"}
HYPERTENSION = {"system": SNOMED, "code": "59621000", "display": "Essential hypertension"}
HEART_FAILURE = {"system": SNOMED, "code": "84114007", "display": "Heart failure"}


def _patient(patient_id: str, *, birth_date: str = "1970-04-12", gender: str = "female") -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "gender": gender,
        "birthDate": birth_date,
        "managingOrganization": {"reference": f"Organization/org-{patient_id}"},
    }


def _encounter(patient_id: str, encounter_id: str, *, start: str = "2024-01-15T09:00:00Z",
               end: str = "2024-01-15T10:30:00Z") -> dict[str, Any]:
    return {
        "resourceType": "Encounter",
        "id": encounter_id,
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": start, "end": end},
    }


def _condition(patient_id: str, condition_id: str, coding: dict[str, str],
               *, encounter_id: str = "", onset: str = "2020-03-01") -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "Condition",
        "id": condition_id,
        "subject": {"reference": f"Patient/{patient_id}"},
        "clinicalStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}],
        },
        "code": {"coding": [dict(coding)], "text": coding.get("display", "")},
        "onsetDateTime": onset,
        "recordedDate": onset,
    }
    if encounter_id:
        resource["encounter"] = {"reference": f"Encounter/{encounter_id}"}
    return resource


def _observation(patient_id: str, observation_id: str, coding: dict[str, str],
                 value: float, unit: str, *, effective: str = "2024-01-15T09:15:00Z") -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"coding": [dict(coding)], "text": coding.get("display", "")},
        "effectiveDateTime": effective,
        "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
    }


def _medication_request(patient_id: str, request_id: str, coding: dict[str, str], *,
                        authored: str = "2024-01-15T09:30:00Z") -> dict[str, Any]:
    return {
        "resourceType": "MedicationRequest",
        "id": request_id,
        "status": "active",
        "intent": "order",
        "subject": {"reference": f"Patient/{patient_id}"},
        "authoredOn": authored,
        "medicationCodeableConcept": {"coding": [dict(coding)], "text": coding.get("display", "")},
    }


def _bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource} for resource in resources],
    }


def synthetic_patient_bundle(index: int, *, seed: int = 42, condition: dict[str, str] | None = None,
                             encounters: int = 1, observations: int = 2,
                             medications: int = 1) -> dict[str, Any]:
    """One deterministic patient bundle. Same (index, seed) always yields the same bundle."""
    patient_id = f"syn-pat-{seed}-{index:04d}"
    resources: list[dict[str, Any]] = [
        _patient(patient_id, birth_date=f"{1950 + (index % 40):04d}-{(index % 12) + 1:02d}-12"),
    ]
    for encounter_index in range(encounters):
        resources.append(_encounter(patient_id, f"syn-enc-{seed}-{index:04d}-{encounter_index}"))
    if condition is not None:
        resources.append(_condition(patient_id, f"syn-cond-{seed}-{index:04d}", condition))
    for obs_index in range(observations):
        resources.append(_observation(
            patient_id, f"syn-obs-{seed}-{index:04d}-{obs_index}",
            {"system": LOINC, "code": "8867-4", "display": "Heart rate"},
            68.0 + obs_index, "/min",
        ))
    for med_index in range(medications):
        resources.append(_medication_request(
            patient_id, f"syn-med-{seed}-{index:04d}-{med_index}",
            {"system": RXNORM, "code": "1049221", "display": "Acetaminophen 325 MG Oral Tablet"},
        ))
    return _bundle(resources)


def valid_single_patient_bundle() -> dict[str, Any]:
    """Adversarial fixture 1: a structurally valid single-patient bundle."""
    return synthetic_patient_bundle(0, seed=7)


def abnormal_observation_bundle() -> dict[str, Any]:
    """Adversarial fixture 2: valid bundle carrying a clinically abnormal value.

    A heart rate of 190/min is abnormal but legitimate content. The plausibility
    audit must not reject or rewrite it.
    """
    bundle = synthetic_patient_bundle(1, seed=7, observations=1)
    for entry in bundle["entry"]:
        resource = entry["resource"]
        if resource.get("resourceType") == "Observation":
            resource["valueQuantity"] = {
                "value": 190, "unit": "/min", "system": "http://unitsofmeasure.org", "code": "/min",
            }
    return bundle


def broken_subject_reference_bundle() -> dict[str, Any]:
    """Adversarial fixture 3: an Observation pointing at a Patient that is not present."""
    bundle = synthetic_patient_bundle(2, seed=7, observations=1)
    for entry in bundle["entry"]:
        resource = entry["resource"]
        if resource.get("resourceType") == "Observation":
            resource["subject"] = {"reference": "Patient/does-not-exist"}
    return bundle


def missing_patient_bundle() -> dict[str, Any]:
    """Adversarial fixture 4: clinical resources with no Patient at all."""
    bundle = synthetic_patient_bundle(3, seed=7)
    bundle["entry"] = [entry for entry in bundle["entry"]
                       if entry["resource"].get("resourceType") != "Patient"]
    return bundle


def reversed_encounter_period_bundle() -> dict[str, Any]:
    """Adversarial fixture 5: an Encounter whose period ends before it starts."""
    bundle = synthetic_patient_bundle(4, seed=7)
    for entry in bundle["entry"]:
        resource = entry["resource"]
        if resource.get("resourceType") == "Encounter":
            resource["period"] = {"start": "2024-03-02T10:00:00Z", "end": "2024-03-01T09:00:00Z"}
    return bundle


def duplicate_resource_id_bundle() -> dict[str, Any]:
    """Adversarial fixture 6: two different resources share one logical id."""
    bundle = synthetic_patient_bundle(5, seed=7, observations=2)
    observations = [entry["resource"] for entry in bundle["entry"]
                    if entry["resource"].get("resourceType") == "Observation"]
    if len(observations) >= 2:
        observations[1]["id"] = observations[0]["id"]
    return bundle


def invalid_quantity_bundle() -> dict[str, Any]:
    """Adversarial fixture 7: a Quantity whose value is not numeric."""
    bundle = synthetic_patient_bundle(6, seed=7, observations=1)
    for entry in bundle["entry"]:
        resource = entry["resource"]
        if resource.get("resourceType") == "Observation":
            resource["valueQuantity"] = {"value": "one hundred and ninety", "unit": "/min"}
    return bundle


def unmapped_terminology_bundle() -> dict[str, Any]:
    """Adversarial fixture 8: a condition using a code system the mapping set does not cover."""
    bundle = synthetic_patient_bundle(7, seed=7, observations=0, medications=0)
    bundle["entry"].append({
        "fullUrl": "urn:uuid:syn-local-code",
        "resource": {
            "resourceType": "Condition",
            "id": "syn-local-code",
            "subject": {"reference": "Patient/syn-pat-7-0007"},
            "code": {
                "coding": [{"system": "http://example.org/local-codes", "code": "LOCAL-42",
                            "display": "Local teaching code"}],
                "text": "Local teaching code",
            },
            "recordedDate": "2024-01-15",
        },
    })
    return bundle


def unsupported_profile_bundle() -> dict[str, Any]:
    """Adversarial fixture 9: declares a profile the local rule pack cannot verify."""
    bundle = synthetic_patient_bundle(8, seed=7)
    bundle["meta"] = {"profile": ["http://example.org/fhir/StructureDefinition/UnsupportedProfile"]}
    for entry in bundle["entry"]:
        entry["resource"].setdefault("meta", {})["profile"] = [
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
        ]
    return bundle


def malformed_json_text() -> str:
    """Adversarial fixture 10a: JSON that does not parse."""
    return '{"resourceType": "Bundle", "entry": [ {"resource": '


def oversized_ndjson_line(line_limit: int = 1024 * 1024) -> str:
    """Adversarial fixture 10b: one NDJSON line beyond the configured limit."""
    return '{"resourceType":"Patient","id":"huge","note":"' + ("x" * (line_limit + 16)) + '"}'


def partial_cohort_bundles() -> list[dict[str, Any]]:
    """Adversarial fixture 11: a valid cohort with fewer matches than requested."""
    matched = synthetic_patient_bundle(9, seed=7, condition=ASTHMA)
    unmatched = synthetic_patient_bundle(10, seed=7)
    return [matched, unmatched]


def crafted_traversal_bundle() -> dict[str, Any]:
    """Adversarial fixture 10: a Patient.id that attempts directory traversal.

    Generated content is not trusted as a path component. This bundle is
    otherwise well formed so that only the identifier is hostile.
    """
    bundle = synthetic_patient_bundle(3, seed=7, observations=1)
    patient = next(r for r in bundle["entry"] if r["resource"]["resourceType"] == "Patient")
    patient["resource"]["id"] = "../../../../etc/pwned"
    return bundle


ADVERSARIAL_FIXTURES = {
    "valid_single_patient": valid_single_patient_bundle,
    "abnormal_observation": abnormal_observation_bundle,
    "broken_subject_reference": broken_subject_reference_bundle,
    "missing_patient": missing_patient_bundle,
    "reversed_encounter_period": reversed_encounter_period_bundle,
    "duplicate_resource_id": duplicate_resource_id_bundle,
    "invalid_quantity": invalid_quantity_bundle,
    "unmapped_terminology": unmapped_terminology_bundle,
    "unsupported_profile": unsupported_profile_bundle,
    "crafted_traversal": crafted_traversal_bundle,
}


def fixture_copy(name: str) -> dict[str, Any]:
    return copy.deepcopy(ADVERSARIAL_FIXTURES[name]())
