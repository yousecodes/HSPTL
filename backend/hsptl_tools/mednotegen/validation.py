"""Input and generated-payload validation for MedNoteGen."""
from __future__ import annotations
from typing import Any

ALLOWED_RESOURCE_TYPES = {
    "Patient", "Encounter", "Condition", "Observation", "Procedure",
    "MedicationRequest", "MedicationStatement", "Medication", "AllergyIntolerance",
    "CarePlan", "DiagnosticReport", "Immunization", "ServiceRequest",
    "DocumentReference", "Provenance",
}

def validate_resources(resources: list[dict[str, Any]]) -> dict[str, Any]:
    if not resources:
        raise ValueError("No FHIR resources were loaded")
    known = sum(1 for item in resources if item.get("resourceType") in ALLOWED_RESOURCE_TYPES)
    return {"resource_count": len(resources), "supported_resource_count": known,
            "unsupported_resource_count": len(resources) - known}

def validate_generated_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("MedNoteGen output must be an object")
    for key in ("clinic_cases", "pearl_seeds"):
        if not isinstance(payload.get(key, []), list):
            raise ValueError(f"MedNoteGen {key} must be a list")
