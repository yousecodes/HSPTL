"""Create privacy-minimised teaching cases from accepted synthetic FHIR bundles.

Only bundles already accepted by the synthetic-data validation pipeline reach
this adapter. Cases are explicitly labelled as machine-QA synthetic record
interpretation exercises, not clinically validated diagnostic scenarios.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path
from typing import Any

from .fhir_parse import load_bundles, bundle_resources


def _display(concept: Any) -> str:
    if not isinstance(concept, dict):
        return ""
    text = str(concept.get("text") or "").strip()
    if text:
        return text[:180]
    for coding in concept.get("coding", []) or []:
        if isinstance(coding, dict) and coding.get("display"):
            return str(coding["display"]).strip()[:180]
    return ""


def _concept_terms(concept: Any) -> set[str]:
    values: set[str] = set()
    if not isinstance(concept, dict):
        return values
    if concept.get("text"):
        values.add(str(concept["text"]).strip().casefold())
    for coding in concept.get("coding", []) or []:
        if isinstance(coding, dict):
            for key in ("display", "code"):
                if coding.get(key):
                    values.add(str(coding[key]).strip().casefold())
    return values


def _age(birth_date: Any, reference_date: Any) -> int | None:
    if not isinstance(birth_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth_date):
        return None
    if not isinstance(reference_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reference_date[:10]):
        return None
    try:
        born = date.fromisoformat(birth_date)
        today = date.fromisoformat(reference_date[:10])
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age if 0 <= age <= 125 else None
    except ValueError:
        return None


def _observation_line(resource: dict[str, Any]) -> str:
    label = _display(resource.get("code"))
    if not label:
        return ""
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict) and isinstance(quantity.get("value"), (int, float)):
        unit = str(quantity.get("unit") or "").strip()
        return f"{label}: {quantity['value']} {unit}".strip()[:180]
    coded = _display(resource.get("valueCodeableConcept"))
    if coded:
        return f"{label}: {coded}"[:180]
    if isinstance(resource.get("valueString"), str):
        return f"{label}: {resource['valueString'][:100]}"[:180]
    return ""


def author_cases_from_accepted_fhir(directory: Path, lottery, *, dataset_id: str,
                                    recipe_id: str, max_cases: int = 100) -> dict[str, Any]:
    """Idempotently enrol bounded, accepted synthetic records in the daily lottery."""
    bundles, problems = load_bundles(Path(directory))
    created = existing = skipped = 0
    reasons: dict[str, int] = {}
    limit = max(1, min(int(max_cases), 500))
    selected_bundles = bundles[:limit]
    truncated = max(0, len(bundles) - len(selected_bundles))
    for source_file, bundle in selected_bundles:
        resources = bundle_resources(bundle)
        patients = [r for r in resources if r.get("resourceType") == "Patient"]
        conditions = [r for r in resources if r.get("resourceType") == "Condition"]
        encounters = [r for r in resources if r.get("resourceType") == "Encounter"]
        observations = [r for r in resources if r.get("resourceType") == "Observation"]
        if len(patients) != 1:
            reason = "requires_exactly_one_patient"
        elif not encounters:
            reason = "requires_encounter_context"
        elif not observations:
            reason = "requires_observations"
        else:
            patient = patients[0]
            valid_conditions = []
            for condition in conditions:
                verification = _concept_terms(condition.get("verificationStatus"))
                clinical = _concept_terms(condition.get("clinicalStatus"))
                if verification.intersection({"entered in error", "entered-in-error", "refuted"}) or clinical.intersection({"resolved", "inactive"}):
                    continue
                display = _display(condition.get("code"))
                if display:
                    valid_conditions.append((condition, display))
            if not valid_conditions:
                reason = "requires_active_coded_condition"
            else:
                # Stable, non-reversible identifier: never expose FHIR patient IDs or names.
                patient_id = str(patient.get("id") or source_file)
                digest = hashlib.sha256(f"{dataset_id}:{patient_id}".encode()).hexdigest()[:20]
                case_id = f"synthetic-{digest}"
                if lottery.get_case(case_id) is not None:
                    existing += 1
                    continue
                condition, diagnosis = valid_conditions[0]
                observation_lines = []
                for observation in observations:
                    line = _observation_line(observation)
                    if line and line not in observation_lines:
                        observation_lines.append(line)
                    if len(observation_lines) >= 5:
                        break
                encounter_dates = [
                    str((enc.get("period") or {}).get("start", ""))[:10]
                    for enc in encounters if isinstance(enc.get("period"), dict)
                ]
                encounter_date = next((value for value in encounter_dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)), "")
                age = _age(patient.get("birthDate"), encounter_date)
                stem = (
                    "This is a fictional Synthea-generated FHIR record, not a real patient. "
                    f"The record contains a coded condition: {diagnosis}. "
                    "The following observations were recorded:\n" +
                    "\n".join(f"- {line}" for line in observation_lines) +
                    "\n\nInterpret the record and distinguish the recorded code from a diagnosis you would independently establish."
                )
                reveal = {
                    "diagnosis": diagnosis,
                    "explanation": (
                        "The answer reproduces the coded display from the synthetic FHIR Condition resource. "
                        "It is a record-interpretation answer, not an independently inferred diagnosis or a clinically validated conclusion. "
                        "Use the recorded observations as data to discuss; do not infer treatment from this exercise."
                    ),
                    "key_takeaways": [
                        "Distinguish a coded condition from an independently established diagnosis.",
                        "Check the code system, clinical status, verification status and encounter context.",
                        "Synthetic-data technical acceptance does not establish clinical validity or population representativeness.",
                    ],
                    "educational_status": "Synthetic FHIR record accepted by automated data-quality checks; warnings may remain; not clinically validated.",
                }
                source_refs = [{
                    "source_type": "synthetic_fhir_dataset",
                    "title": f"Synthea dataset {dataset_id}",
                    "dataset_id": dataset_id,
                    "recipe_id": recipe_id,
                    "source_file_digest": hashlib.sha256(source_file.encode()).hexdigest(),
                    "qa_status": "accepted_by_synthetic_data_pipeline",
                    "clinical_validation": "not_assessed",
                    "note": "Fictional Synthea record. No patient name, identifier, address or contact details are exposed.",
                }]
                from ..content_labels import LABEL_SYNTHETIC
                lottery.register_case(
                    case_id=case_id,
                    title=f"Synthetic record interpretation — {diagnosis[:90]}",
                    specialty="General medicine",
                    difficulty="Intermediate",
                    stem=stem,
                    prompt=("Which condition is coded in this synthetic record? Explain what the recorded "
                            "observations do and do not establish, and identify the additional history, "
                            "examination and evidence needed for a real clinical assessment."),
                    presenting_complaint=f"Synthetic FHIR record with coded condition: {diagnosis}",
                    patient_age_value=age,
                    patient_age_unit="years",
                    label=LABEL_SYNTHETIC,
                    rights_status="permitted",
                    clinical_review_status="synthetic_qa_passed",
                    publication_status="published",
                    reveal=reveal,
                    source_refs=source_refs,
                )
                created += 1
                continue
        skipped += 1
        reasons[reason] = reasons.get(reason, 0) + 1
    skipped += len(problems) + truncated
    if problems:
        reasons["unreadable_fhir_bundle"] = len(problems)
    if truncated:
        reasons["per_run_case_limit"] = truncated
    return {
        "created": created,
        "already_present": existing,
        "skipped": skipped,
        "skip_reasons": reasons,
        "source": "accepted_synthea_fhir",
        "clinical_validation": "not_assessed",
        "publication_status": "provisional_synthetic_educational_use",
        "cases_eligible_for_lottery": created + existing,
        "truncated_bundles": truncated,
        "limit": limit,
    }
