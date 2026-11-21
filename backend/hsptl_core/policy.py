"""Feature gates for advanced capabilities. Disabled by default, never silent.

A feature needs BOTH an explicit environment opt-in AND a satisfied requirement
set. `formal_assessment` is hard-blocked: this local-first architecture cannot
provide a trusted assessment boundary, so no flag can enable it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FeaturePolicy:
    key: str
    title: str
    risk: str
    requirements: tuple[str, ...]
    default_enabled: bool = False
    hard_blocked: bool = False
    data_boundary: str = "local_only"
    notes: str = ""


FEATURES: dict[str, FeaturePolicy] = {
    "branching_simulation": FeaturePolicy(
        key="branching_simulation", title="Branching curated simulations", risk="medium",
        requirements=("curated_authored_graph", "named_reviewer", "no_generated_clinical_text"),
        notes="Deterministic traversal of clinician-authored nodes only. Never runs on raw FHIR."),
    "conversational_tutoring": FeaturePolicy(
        key="conversational_tutoring", title="Conversational tutor", risk="high",
        requirements=("provenance_bound_context", "local_or_explicitly_consented_endpoint",
                      "human_review_of_output", "no_patient_specific_advice"),
        notes="Prompt assembly only; no network adapter exists. Generic chat is not the default."),
    "ai_generated_content": FeaturePolicy(
        key="ai_generated_content", title="AI-generated teaching content", risk="high",
        requirements=("source_grounded_generation", "citation_verification", "curator_sign_off"),
        notes="Generated claims need a verified SourceRef before saving as teaching content."),
    "multi_user_sync": FeaturePolicy(
        key="multi_user_sync", title="Multi-user synchronisation", risk="high",
        requirements=("authentication", "encryption_in_transit_and_at_rest", "conflict_resolution",
                      "privacy_review", "deletion_propagation"),
        notes="Only offline export/import bundles exist. No sync server is implemented."),
    "formal_assessment": FeaturePolicy(
        key="formal_assessment", title="Formal / high-stakes assessment", risk="critical",
        hard_blocked=True,
        requirements=("trusted_session_boundary", "server_authoritative_timing", "item_bank_security",
                      "identity_verification", "psychometric_validation", "institutional_governance"),
        notes="This local-first architecture cannot provide a trusted assessment boundary."),
}

BRANCHING_REQUIREMENTS = ("curated_authored_graph", "named_reviewer", "no_generated_clinical_text")


class PolicyError(RuntimeError):
    pass


def _overrides() -> dict[str, bool]:
    out: dict[str, bool] = {}
    for token in os.environ.get("HSPTL_FEATURES", "").split(","):
        token = token.strip()
        if not token:
            continue
        key, _, value = token.partition("=")
        out[key.strip()] = value.strip().casefold() in {"1", "true", "on", "yes"}
    return out


def feature_report(satisfied: dict[str, set[str]] | None = None) -> list[dict[str, Any]]:
    satisfied = satisfied or {}
    overrides = _overrides()
    report = []
    for policy in FEATURES.values():
        met = satisfied.get(policy.key, set())
        unmet = [r for r in policy.requirements if r not in met]
        enabled = (overrides.get(policy.key, policy.default_enabled)
                   and not unmet and not policy.hard_blocked)
        report.append({"key": policy.key, "title": policy.title, "risk": policy.risk,
                       "enabled": bool(enabled), "hard_blocked": policy.hard_blocked,
                       "requirements": list(policy.requirements), "unmet_requirements": unmet,
                       "data_boundary": policy.data_boundary, "notes": policy.notes})
    return report


def is_enabled(key: str, satisfied: dict[str, set[str]] | None = None) -> bool:
    return any(i["key"] == key and i["enabled"] for i in feature_report(satisfied))


def assert_enabled(key: str, satisfied: dict[str, set[str]] | None = None) -> None:
    policy = FEATURES.get(key)
    if policy is None:
        raise PolicyError("Unknown feature")
    if policy.hard_blocked:
        raise PolicyError(f"{policy.title} is not available in this architecture: {policy.notes}")
    if not is_enabled(key, satisfied):
        item = next(i for i in feature_report(satisfied) if i["key"] == key)
        raise PolicyError("Unmet requirements: " + ", ".join(item["unmet_requirements"]))
