"""Cohort selection over generated FHIR bundles.

Synthea population generation is probabilistic, so a requested patient count is
not a promise that the same number of patients will carry a target diagnosis.
This module reports exactly what happened. It never invents a condition, never
edits a bundle and never pads a cohort to reach a target.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .fhir_parse import bundle_resources


@dataclass
class CohortCriteria:
    version: str
    system: str
    codes: set[str]
    match: str = "any"
    resource_types: tuple[str, ...] = ("Condition",)

    @classmethod
    def from_recipe(cls, cohort: dict[str, Any] | None) -> "CohortCriteria | None":
        if not cohort:
            return None
        codes = cohort.get("codes") or []
        if not isinstance(codes, list) or not codes:
            return None
        return cls(
            version=str(cohort.get("version", "cohort/1.0")),
            system=str(cohort.get("system", "")),
            codes={str(code) for code in codes},
            match=str(cohort.get("match", "any")),
            resource_types=tuple(cohort.get("resource_types") or ("Condition",)),
        )


@dataclass
class CohortSelection:
    generated_patients: int = 0
    matched_patients: int = 0
    selected_patients: int = 0
    discarded_patients: int = 0
    target_patients: int = 0
    status: str = "complete"
    criteria_version: str = ""
    criteria_system: str = ""
    selected: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_patients": self.generated_patients,
            "matched_patients": self.matched_patients,
            "selected_patients": self.selected_patients,
            "discarded_patients": self.discarded_patients,
            "target_patients": self.target_patients,
            "cohort_status": self.status,
            "criteria_version": self.criteria_version,
            "criteria_system": self.criteria_system,
        }


def _bundle_matches(bundle: dict[str, Any], criteria: CohortCriteria) -> bool:
    hits: set[str] = set()
    for resource in bundle_resources(bundle):
        if str(resource.get("resourceType")) not in criteria.resource_types:
            continue
        concept = resource.get("code")
        if not isinstance(concept, dict):
            continue
        for coding in concept.get("coding", []) or []:
            if not isinstance(coding, dict):
                continue
            if criteria.system and coding.get("system") != criteria.system:
                continue
            if str(coding.get("code")) in criteria.codes:
                hits.add(str(coding.get("code")))
    if criteria.match == "all":
        return criteria.codes.issubset(hits)
    return bool(hits)


def select_cohort(bundles: list[tuple[str, dict[str, Any]]],
                  criteria: CohortCriteria | None, *,
                  target_patients: int = 0) -> CohortSelection:
    """Select whole patient bundles that satisfy the criteria.

    When no criteria are configured every bundle is selected and the status is
    ``not_applicable``. When criteria exist and fewer patients match than the
    target, the status is ``partial_cohort`` and the shortfall is reported.
    """
    selection = CohortSelection(generated_patients=len(bundles))
    if criteria is None:
        selection.selected = list(bundles)
        selection.selected_patients = len(bundles)
        selection.matched_patients = len(bundles)
        selection.status = "not_applicable"
        selection.target_patients = target_patients or len(bundles)
        return selection

    selection.criteria_version = criteria.version
    selection.criteria_system = criteria.system
    selection.target_patients = target_patients

    matched: list[tuple[str, dict[str, Any]]] = [
        (source_file, bundle) for source_file, bundle in bundles
        if _bundle_matches(bundle, criteria)
    ]
    selection.matched_patients = len(matched)
    limit = target_patients if target_patients > 0 else len(matched)
    selection.selected = matched[:limit]
    selection.selected_patients = len(selection.selected)
    selection.discarded_patients = len(bundles) - selection.selected_patients
    if target_patients > 0 and selection.selected_patients < target_patients:
        selection.status = "partial_cohort"
    else:
        selection.status = "complete"
    return selection


def pseudonymous_key(patient_id: str, *, dataset_salt: str = "hsptl") -> str:
    """Stable, non-reversible key for dashboard lists and audit metadata."""
    import hashlib
    raw = f"{dataset_salt}:{patient_id}".encode("utf-8")
    return "syn_" + hashlib.sha256(raw).hexdigest()[:24]
