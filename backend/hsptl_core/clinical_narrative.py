"""Deterministic FHIR encounter-to-learning narrative transformation.

Only source-documented facts are presented as findings. Missing clinical
history/examination are explicitly unavailable, never silently normalised.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any


def build_encounter_narrative(case: dict[str, Any]) -> dict[str, Any]:
    encounter = case.get("selected_encounter")
    if not encounter:
        raise ValueError("A specific encounter must be selected")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in case.get("facts", []):
        kind = str(fact.get("resource_type") or "Other")
        groups[kind].append({
            "label": fact.get("code_text") or f"{kind} record",
            "value": " ".join(part for part in [str(fact.get("value_text") or "").strip(), str(fact.get("unit") or "").strip()] if part) or None,
            "date": fact.get("effective_at") or None,
            "status": fact.get("status") or None,
            "conclusion": fact.get("conclusion") or None,
            "provenance": "Documented",
            "source_file": fact.get("source_file") or None,
        })

    def section(title: str, resource_types: tuple[str, ...], note: str) -> dict[str, Any]:
        rows = [item for kind in resource_types for item in groups.get(kind, [])]
        return {"title": title, "items": rows, "availability": "documented" if rows else "unavailable", "note": note}

    encounter_context = [{
        "label": encounter.get("encounter_type") or "Encounter",
        "value": encounter.get("status") or None,
        "date": encounter.get("start_at") or None,
        "status": encounter.get("status") or None,
        "conclusion": None,
        "provenance": "Documented",
        "source_file": encounter.get("source_file") or None,
    }]
    sections = [
        {"title": "Encounter context", "items": encounter_context, "availability": "documented", "note": "Encounter metadata only; it is not a substitute for a clinical history."},
        {"title": "Presenting history", "items": [], "availability": "unavailable", "note": "No structured HPI is available in this imported encounter. Ask what you would need to establish."},
        {"title": "Examination", "items": [], "availability": "unavailable", "note": "No examination findings are documented in the selected encounter. Do not interpret this as a normal examination."},
        section("Observations and measurements", ("Observation",), "Only observations explicitly linked to this encounter are included."),
        section("Diagnostic reports", ("DiagnosticReport", "ImagingStudy"), "Report text and conclusions are shown only when supplied by the source."),
        section("Procedures", ("Procedure",), "Only recorded procedures are included."),
        section("Medication records", ("MedicationRequest", "MedicationAdministration"), "Medication records do not prove adherence or current use."),
        section("Coded conditions", ("Condition",), "Source-coded conditions are separated from learner-facing diagnostic conclusions and are not automatically treated as the answer."),
        section("Allergies", ("AllergyIntolerance",), "An empty section means no linked allergy record was found, not that the patient has no allergies."),
    ]
    patient = case.get("patient", {})
    age = None
    age_provenance = "Unavailable"
    birth_date = patient.get("birth_date") or ""
    encounter_date = (encounter.get("start_at") or "")[:10]
    try:
        born = date.fromisoformat(birth_date[:10])
        seen = date.fromisoformat(encounter_date)
        age = seen.year - born.year - ((seen.month, seen.day) < (born.month, born.day))
        if age < 0:
            age = None
        else:
            age_provenance = "Derived from documented birth date and encounter date"
    except (TypeError, ValueError):
        pass
    return {
        "case_code": f"SYN-{encounter['encounter_key'][:8].upper()}",
        "source_type": "Synthetic FHIR encounter",
        "patient_context": {
            "age": age,
            "age_provenance": age_provenance,
            "gender": patient.get("gender") or None,
            "gender_provenance": "Documented" if patient.get("gender") else "Unavailable",
            "birth_date": birth_date or None,
            "provenance": "Documented",
        },
        "encounter": {key: encounter.get(key) for key in ("start_at", "end_at", "status", "encounter_type")},
        "sections": sections,
        "clinical_prompt": "Construct a problem representation from the available evidence. Identify the missing history and examination you would obtain before committing to a diagnosis.",
        "limitations": [
            "This is a source-faithful learning draft, not a curated diagnostic case.",
            "No diagnosis is inferred from a Condition resource.",
            "No undocumented history, examination, normal findings, or investigation results are generated.",
            "A clinician must review and curate this material before it can become a diagnostic challenge.",
        ],
        "diagnostic_puzzle_eligible": False,
    }
