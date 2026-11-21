"""Read Synthea FHIR R4 JSON exports without inventing missing clinical data."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Iterable

FHIR_TYPES = {
    "Patient", "Encounter", "Condition", "Observation", "Procedure",
    "MedicationRequest", "MedicationStatement", "Medication",
    "AllergyIntolerance", "CarePlan", "DiagnosticReport", "Immunization",
    "ServiceRequest", "DocumentReference", "Provenance"
}

class FHIRImportError(ValueError):
    pass

def _resource_iter(payload: Any) -> Iterable[dict]:
    if not isinstance(payload, dict):
        return
    if payload.get("resourceType") == "Bundle":
        for entry in payload.get("entry") or []:
            resource = (entry or {}).get("resource")
            if isinstance(resource, dict):
                yield resource
    elif isinstance(payload.get("resourceType"), str):
        yield payload

def load_fhir_directory(directory: str | Path) -> tuple[list[dict], list[str]]:
    """Load individual resources or FHIR Bundles from a directory."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"FHIR directory does not exist: {root}")
    resources: list[dict] = []
    errors: list[str] = []
    files = sorted(root.glob("*.json"))
    if not files:
        raise FHIRImportError(f"No .json FHIR files found in {root}")
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            for resource in _resource_iter(payload):
                item = dict(resource)
                item["_source_file"] = path.name
                resources.append(item)
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            errors.append(f"{path.name}: {type(exc).__name__}: {exc}")
    if not resources:
        raise FHIRImportError("No valid FHIR resources were found. " + "; ".join(errors[:5]))
    return resources, errors

def ref_id(reference: Any) -> str | None:
    if not isinstance(reference, dict):
        return None
    value = reference.get("reference")
    if not isinstance(value, str) or not value:
        return None
    # Preserve the final resource ID for urn:uuid and Resource/id references.
    return value.rstrip("/").split("/")[-1]

def coding_text(concept: Any) -> str | None:
    if not isinstance(concept, dict):
        return None
    for coding in concept.get("coding") or []:
        if isinstance(coding, dict) and coding.get("display"):
            return str(coding["display"])
    return concept.get("text")

def coding_list(concept: Any) -> list[dict]:
    if not isinstance(concept, dict):
        return []
    out = []
    for coding in concept.get("coding") or []:
        if isinstance(coding, dict):
            out.append({k: coding[k] for k in ("system", "code", "display", "version") if coding.get(k) is not None})
    if concept.get("text"):
        out.append({"text": concept["text"]})
    return out

def value_display(obs: dict) -> dict | None:
    """Return the recorded value[x] without converting or guessing units."""
    for key, value in obs.items():
        if key.startswith("value") and value is not None:
            if key == "valueQuantity" and isinstance(value, dict):
                return {"kind": key, "value": value.get("value"), "unit": value.get("unit"), "system": value.get("system"), "code": value.get("code")}
            return {"kind": key, "value": value}
    if obs.get("component"):
        components = []
        for component in obs["component"]:
            components.append({
                "code": coding_list(component.get("code")),
                "display": coding_text(component.get("code")),
                "value": value_display(component) or {"kind": "not-recorded"}
            })
        return {"kind": "components", "value": components}
    return None

def resource_provenance(resource: dict) -> dict:
    return {
        "resource_type": resource.get("resourceType"),
        "resource_id": resource.get("id"),
        "source_file": resource.get("_source_file"),
        "source_status": resource.get("status"),
        "recorded": resource.get("recorded") or resource.get("meta", {}).get("lastUpdated")
    }
