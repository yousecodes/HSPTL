"""In-process runtime event monitors. They run before every HSPTL 4.0 append."""
from __future__ import annotations

from typing import Any


FORBIDDEN_SKIN_KEYS = {
    "clinical_facts", "diagnoses", "evidence", "appraisal_rules",
    "routing_predicates", "preconditions", "clinical_thresholds", "medical_rules",
}


def inspect_event(event_type: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []

    if event_type == "platform.pathway.enacted":
        state = payload.get("state")
        if not isinstance(state, dict) or state.get("enactment_id") != payload.get("enactment_id"):
            violations.append({"monitor": "M-PROFORMA-STATE-001", "reason": "Enactment state identity must match the event identity."})
        if isinstance(state, dict) and state.get("status") == "abstain":
            violations.append({"monitor": "M-PROFORMA-ABSTAIN-001", "reason": "An abstaining enactment must use platform.pathway.abstained."})

    elif event_type == "platform.pathway.stepped":
        state = payload.get("state")
        if not isinstance(state, dict) or state.get("enactment_id") != payload.get("enactment_id"):
            violations.append({"monitor": "M-PROFORMA-STATE-001", "reason": "Stepped enactment state identity must match the event identity."})
        if isinstance(state, dict) and state.get("status") == "abstain":
            violations.append({"monitor": "M-PROFORMA-ABSTAIN-001", "reason": "An abstaining step must use platform.pathway.abstained."})

    elif event_type == "platform.pathway.abstained":
        state = payload.get("state")
        if not isinstance(state, dict) or state.get("enactment_id") != payload.get("enactment_id") or state.get("status") != "abstain":
            violations.append({"monitor": "M-PROFORMA-ABSTAIN-002", "reason": "Abstention event must carry the matching enactment state with status=abstain."})

    elif event_type == "platform.learning_object.composed":
        obj = payload.get("object")
        if not isinstance(obj, dict) or not obj.get("object_id"):
            violations.append({"monitor": "M-COMPOSE-IDENTITY-001", "reason": "Composed object must have a stable object_id."})
        elif obj.get("assertion_lineage"):
            derivation = obj.get("derivation")
            source_events = derivation.get("source_events") if isinstance(derivation, dict) else None
            if not isinstance(source_events, list) or not source_events:
                violations.append({"monitor": "M-LINEAGE-001", "reason": "An assertion with evidence lineage must have replayable source-event references."})
            lineage_kinds = [item.get("kind") for item in obj["assertion_lineage"] if isinstance(item, dict)]
            required = {"assertion", "evidence_entity", "appraisal", "source_event", "source_span"}
            if not required.issubset(set(lineage_kinds)):
                violations.append({"monitor": "M-LINEAGE-002", "reason": "Assertion lineage is incomplete."})

    elif event_type == "platform.route.decided":
        if payload.get("eligibility") != "pass":
            violations.append({"monitor": "M-ROUTE-ELIGIBILITY-001", "reason": "A route may be emitted only after PROforma eligibility passes."})

    elif event_type == "platform.pulse.observation_recorded":
        if not isinstance(payload.get("source"), str) or not payload.get("source"):
            violations.append({"monitor": "M-PULSE-SOURCE-001", "reason": "Pulse observation must identify its source."})
        if not isinstance(payload.get("sequence"), int) or isinstance(payload.get("sequence"), bool) or payload.get("sequence") < 0:
            violations.append({"monitor": "M-PULSE-SEQUENCE-001", "reason": "Connected Pulse observation must have a non-negative integer provider sequence."})
        if not isinstance(payload.get("observations"), dict):
            violations.append({"monitor": "M-PULSE-OBSERVATION-001", "reason": "Pulse observations must be a structured object."})
        evidence = payload.get("clinical_state_evidence", [])
        if not isinstance(evidence, list):
            violations.append({"monitor": "M-PULSE-CLINICAL-EVIDENCE-001", "reason": "Clinical-state evidence must be a list."})
        elif any(not isinstance(item, dict) or not all(item.get(key) for key in ("patient_id", "state_id", "evidence_id", "polarity"))
                 or item.get("polarity") not in {"supports", "opposes"} for item in evidence):
            violations.append({"monitor": "M-PULSE-CLINICAL-EVIDENCE-002", "reason": "Clinical-state evidence requires patient, state, evidence and supports/opposes polarity."})

    elif event_type == "platform.guard.checked":
        if payload.get("decision") not in {"pass", "fail"}:
            violations.append({"monitor": "M-GUARD-STATE-001", "reason": "Checked guard events must be pass or fail."})

    elif event_type == "platform.guard.abstained":
        if payload.get("decision") != "abstain":
            violations.append({"monitor": "M-GUARD-STATE-002", "reason": "Abstained guard events must carry decision=abstain."})

    elif event_type == "platform.plugin.configured":
        config = payload.get("config")
        if not isinstance(config, dict):
            violations.append({"monitor": "M-SKIN-CONFIG-001", "reason": "Skin configuration must be an object."})
        elif FORBIDDEN_SKIN_KEYS.intersection(config):
            violations.append({"monitor": "M-SKIN-FACT-001", "reason": "Skins cannot own clinical facts, thresholds or executable rules."})

    elif event_type == "platform.mastery.signal_recorded":
        if payload.get("signal") not in {"demonstrated", "needs_reinforcement", "not_assessed"}:
            violations.append({"monitor": "M-MASTERY-SIGNAL-001", "reason": "Mastery signal is outside the formative signal vocabulary."})

    return violations
