"""Deterministic quality gates for raw FHIR-derived teaching records.

These checks assess record structure and linkage only. They do not certify
clinical accuracy, diagnostic validity or suitability as a diagnostic puzzle.
"""
from __future__ import annotations

from typing import Any


def assess_fhir_case_quality(*, encounters: list[dict[str, Any]], facts: list[dict[str, Any]],
                              unlinked_facts: int = 0, selected_encounter: dict[str, Any] | None = None) -> dict[str, Any]:
    linked_facts = [fact for fact in facts if fact.get("encounter_key")]
    undated = sum(1 for fact in facts if not fact.get("effective_at"))
    resource_types = {str(fact.get("resource_type", "")) for fact in facts}
    flags: list[dict[str, str]] = []
    if not encounters:
        flags.append({"code": "no_encounters", "severity": "warning", "message": "No encounter resources are documented."})
    if not facts:
        flags.append({"code": "no_clinical_facts", "severity": "blocking", "message": "No supported clinical facts are available."})
    if undated:
        flags.append({"code": "undated_facts", "severity": "info", "message": f"{undated} facts have no usable effective date."})
    if unlinked_facts:
        flags.append({"code": "unlinked_facts", "severity": "warning", "message": f"{unlinked_facts} facts are not linked to an encounter."})
    if len(facts) < 3:
        flags.append({"code": "sparse_record", "severity": "warning", "message": "The available record is sparse; avoid presenting it as a complete clinical narrative."})
    if resource_types and resource_types.issubset({"Condition"}):
        flags.append({"code": "condition_only", "severity": "warning", "message": "Only coded condition entries are available; they are not independently confirmed diagnoses."})
    if selected_encounter and not linked_facts:
        flags.append({"code": "empty_encounter", "severity": "blocking", "message": "No clinical facts are explicitly linked to this encounter."})
    ready_for_review = bool(linked_facts if selected_encounter else facts)
    return {
        "record_status": "review_candidate" if ready_for_review else "incomplete_source_record",
        "ready_for_human_review": ready_for_review,
        "diagnostic_puzzle_eligible": False,
        "diagnostic_puzzle_reason": "Raw FHIR records require clinical curation, a validated answer, learning objectives and source review before becoming a diagnostic case.",
        "counts": {"encounters": len(encounters), "facts": len(facts), "encounter_linked_facts": len(linked_facts),
                   "undated_facts": undated, "unlinked_facts": int(unlinked_facts), "resource_types": sorted(resource_types)},
        "flags": flags,
        "assessment_scope": "Structural completeness and linkage only; not clinical validation.",
    }
