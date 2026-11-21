"""Versioned HSPTL 4.0 event schemas and deterministic write-boundary checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


EVENT_SCHEMA_VERSION = "hsptl.event/1.0"


@dataclass(frozen=True)
class EventSchema:
    required: tuple[str, ...]
    description: str


EVENT_SCHEMAS: dict[str, EventSchema] = {
    "platform.pathway.enacted": EventSchema(("enactment_id", "state"), "PROforma plan started"),
    "platform.pathway.stepped": EventSchema(("enactment_id", "state", "task_id"), "PROforma task advanced"),
    "platform.pathway.abstained": EventSchema(("enactment_id", "state", "reason"), "PROforma execution abstained"),
    "platform.learning_object.composed": EventSchema(("object",), "Template composition emitted"),
    "platform.route.decided": EventSchema(("object_id", "workspace", "eligibility"), "Workspace routing decision"),
    "platform.guard.checked": EventSchema(("guard_id", "decision", "reason"), "Guard evaluated as pass or fail"),
    "platform.guard.abstained": EventSchema(("guard_id", "decision", "reason"), "Guard cannot decide"),
    "platform.pulse.action_requested": EventSchema(("action", "decision"), "Pulse action request"),
    "platform.pulse.observation_recorded": EventSchema(("source", "sequence", "observations"), "Pulse physiological observation snapshot recorded"),
    "platform.plugin.configured": EventSchema(("workspace", "config"), "Workspace presentation configuration changed"),
    "platform.mastery.signal_recorded": EventSchema(("competency_id", "learner_id", "signal", "evidence_ref", "reviewer"), "Formative signal recorded"),
    "platform.write.prevented": EventSchema(("attempted_event_type", "reason", "payload_digest", "layer"), "A prohibited or malformed write was blocked and audited"),
    "platform.terminology.imported": EventSchema(("edition", "effective_time", "concept_count", "description_count", "file_hashes"), "Licensed SNOMED CT RF2 terminology index imported"),
    "platform.curriculum.draft_created": EventSchema(("curriculum_id", "version", "title", "description", "unit_ids", "stages", "prerequisites", "source_packs", "ordering_derivation", "unlock_logic_version", "content_digest", "status"), "A versioned curriculum pathway draft was composed"),
    "platform.curriculum.activated": EventSchema(("curriculum_id", "version", "content_digest", "reviewer", "reviewed_at"), "A reviewed curriculum version was activated"),
    "platform.learning.unit_opened": EventSchema(("learner_id", "curriculum_id", "curriculum_version", "unit_id", "pack_id", "pack_version"), "A learner opened a curriculum unit"),
    "platform.learning.quiz_submitted": EventSchema(("attempt_id", "idempotency_key", "learner_id", "curriculum_id", "curriculum_version", "unit_id", "pack_id", "pack_version", "score", "maximum", "responses", "objective_results", "submitted_at"), "A formative learning-unit quiz attempt was recorded"),
    "platform.scenario.draft_saved": EventSchema(("scenario_id", "version", "scenario_digest", "author", "review_status"), "A versioned synthetic scenario draft was saved"),
    "platform.scenario.published": EventSchema(("scenario_id", "version", "scenario_digest", "reviewer", "reviewed_at"), "A synthetic scenario version was published after configured clinical review"),
    "platform.facilitation.session_created": EventSchema(("session_id", "cohort_id", "scenario_id", "scenario_version", "facilitator_id", "status"), "A governed facilitation session was created"),
    "platform.facilitation.event_recorded": EventSchema(("session_id", "subject_id", "action", "detail"), "A facilitator control event was recorded"),
    "platform.safety.case_reviewed": EventSchema(("case_id", "reviewer_id", "decision"), "A local clinical-safety case decision was recorded; external approval remains required"),
    "platform.synthetic_data.recipe_created": EventSchema(("recipe_id", "version", "status", "owner"), "A declarative synthetic data generation recipe draft was created"),
    "platform.synthetic_data.recipe_activated": EventSchema(("recipe_id", "version", "content_digest", "reviewer", "reviewed_at"), "A synthetic data recipe passed technical and clinical review and was activated"),
    "platform.synthetic_data.job_queued": EventSchema(("job_id", "recipe_id", "recipe_version", "idempotency_key"), "A synthetic data generation job was queued"),
    "platform.synthetic_data.stage_changed": EventSchema(("job_id", "stage", "stage_version", "status", "counts"), "A synthetic data factory pipeline stage changed state"),
    "platform.synthetic_data.generation_completed": EventSchema(("job_id", "generated_patients", "matched_patients", "selected_patients", "cohort_status"), "Synthea population generation finished with cohort selection metrics"),
    "platform.synthetic_data.validation_completed": EventSchema(("job_id", "dataset_id", "validator_id", "validator_version", "strict_conformance", "finding_counts", "dimension_results"), "Layered synthetic dataset validation completed"),
    "platform.synthetic_data.dataset_registered": EventSchema(("dataset_id", "job_id", "recipe_id", "recipe_version", "manifest_digest", "artifact_count", "accepted_patients"), "A synthetic dataset was registered with an immutable provenance manifest"),
    "platform.synthetic_data.records_quarantined": EventSchema(("job_id", "dataset_id", "quarantined_patients", "rule_ids", "severity_counts"), "Synthetic patient bundles were quarantined with diagnostic findings"),
    "platform.synthetic_data.dataset_imported": EventSchema(("dataset_id", "job_id", "imported_patients", "imported_facts", "idempotency_key", "import_status"), "An accepted synthetic dataset was imported into the local clinical fixture registry"),
    "platform.synthetic_data.review_recorded": EventSchema(("item_id", "dataset_id", "reviewer_id", "decision", "rationale"), "A synthetic data quarantine or recipe review decision was recorded"),
    "platform.synthetic_data.job_cancelled": EventSchema(("job_id", "stage", "reason"), "A synthetic data factory job was cancelled"),
    "simulation.run.started": EventSchema(("run_id", "scenario_id", "scenario_version", "scenario_digest", "simulation_model_digest", "engine_version", "transition_model_id", "transition_model_version", "seed", "seed_algorithm", "simulation_time_min", "initial_state"), "A deterministic synthetic clinical simulation run started"),
    "simulation.event.scheduled": EventSchema(("run_id", "scheduled_event_id", "due_at_minute", "priority", "kind", "condition"), "A deterministic event was scheduled on the simulation clock"),
    "simulation.action.requested": EventSchema(("run_id", "action_id", "simulation_time_min", "payload"), "A learner requested a typed scenario action"),
    "simulation.action.accepted": EventSchema(("run_id", "action_id", "simulation_time_min", "proforma_plan_id", "proforma_task_id", "proforma_logic_version", "proforma_derivation_hash", "proforma_proof_trace", "rationale"), "A scenario action passed PROforma and was accepted"),
    "simulation.action.rejected": EventSchema(("run_id", "action_id", "simulation_time_min", "reason", "guard"), "A scenario action was withheld and audited"),
    "simulation.clock.advanced": EventSchema(("run_id", "from_minute", "to_minute", "requested_advance_min", "clock_policy"), "The integer simulation clock advanced explicitly"),
    "simulation.event.fired": EventSchema(("run_id", "scheduled_event_id", "kind", "due_at_minute", "processed_at_minute", "priority", "explanation"), "A scheduled synthetic patient-state event fired"),
    "simulation.event.skipped": EventSchema(("run_id", "scheduled_event_id", "simulation_time_min", "reason"), "A scheduled event was deterministically skipped"),
    "simulation.state.transitioned": EventSchema(("run_id", "simulation_time_min", "transition_model_id", "transition_model_version", "triggered_by", "explanation", "state_after", "state_digest"), "The bounded synthetic patient state transitioned"),
    "simulation.observation.released": EventSchema(("run_id", "stage", "simulation_time_min", "observations", "observation_digest"), "A learner-facing observation projection was released"),
    "simulation.result.available": EventSchema(("run_id", "result_id", "result_type", "simulation_time_min", "value", "unit", "interpretation"), "A delayed investigation result became available"),
    "simulation.document.saved": EventSchema(("run_id", "document_id", "document_type", "document_version", "simulation_time_min", "content", "content_digest", "author", "state"), "A learner clinical note or handover version was saved"),
    "simulation.order.entered": EventSchema(("run_id", "document_id", "document_type", "document_version", "simulation_time_min", "content", "content_digest", "author", "state"), "A bounded educational order version was entered"),
    "simulation.handover.submitted": EventSchema(("run_id", "document_id", "document_type", "document_version", "simulation_time_min", "content", "content_digest", "author", "state"), "A structured handover version was submitted"),
    "simulation.assessment.derived": EventSchema(("run_id", "rubric_id", "rubric_version", "trace_digest", "assessment_digest", "score", "maximum", "percentage", "criteria", "critical_flags", "derivation", "status", "competence_claimed"), "A formative assessment was derived from the canonical run trace"),
    "simulation.debrief.completed": EventSchema(("run_id", "simulation_time_min", "responses", "response_digest", "completed", "total"), "A structured simulation debrief was completed"),
    "simulation.run.completed": EventSchema(("run_id", "simulation_time_min", "trace_digest", "assessment_digest"), "A simulation run was completed and sealed"),
    "simulation.run.abandoned": EventSchema(("run_id", "simulation_time_min", "reason"), "A simulation run was abandoned"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def payload_digest(payload: Any) -> str:
    try:
        raw = canonical_json(payload).encode("utf-8")
    except (TypeError, ValueError):
        raw = f"non-json:{type(payload).__module__}.{type(payload).__qualname__}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_event_payload(event_type: str, payload: Any) -> tuple[bool, str]:
    schema = EVENT_SCHEMAS.get(event_type)
    if schema is None:
        return False, "Event type is not in the HSPTL 4.0 event catalogue."
    if not isinstance(payload, dict):
        return False, "Event payload must be a JSON object."
    try:
        canonical_json(payload)
    except (TypeError, ValueError) as exc:
        return False, f"Event payload is not canonical JSON: {exc}"
    missing = [key for key in schema.required if key not in payload]
    if missing:
        return False, f"Event payload is missing required fields: {', '.join(missing)}."
    if len(canonical_json(payload).encode("utf-8")) > 1_000_000:
        return False, "Event payload exceeds the 1 MB write-boundary limit."
    if event_type in {"platform.guard.checked", "platform.guard.abstained"}:
        allowed = {"pass", "fail"} if event_type.endswith("checked") else {"abstain"}
        if payload.get("decision") not in allowed:
            return False, f"{event_type} accepts only decisions {sorted(allowed)}."
    if event_type == "platform.pathway.stepped" and not isinstance(payload.get("task_id"), str):
        return False, "Stepped pathway event requires a task_id string."
    if event_type == "platform.plugin.configured" and not isinstance(payload.get("config"), dict):
        return False, "Plugin configuration must be a JSON object."
    if event_type == "platform.terminology.imported":
        if not isinstance(payload.get("file_hashes"), dict) or not payload["file_hashes"]:
            return False, "Terminology import must include source file hashes."
        if not isinstance(payload.get("concept_count"), int) or payload["concept_count"] < 0:
            return False, "Terminology concept_count must be a non-negative integer."
    if event_type == "platform.learning.quiz_submitted":
        score, maximum = payload.get("score"), payload.get("maximum")
        if (not isinstance(score, int) or not isinstance(maximum, int)
                or maximum < 1 or score < 0 or score > maximum):
            return False, "Quiz score must be an integer within the declared maximum."
        if not isinstance(payload.get("responses"), list) or len(payload["responses"]) != maximum:
            return False, "Quiz submissions must include one result per question."
        if not payload.get("idempotency_key") or not payload.get("attempt_id"):
            return False, "Quiz submissions require attempt and idempotency identifiers."
    if event_type == "platform.curriculum.draft_created":
        if not isinstance(payload.get("unit_ids"), list) or not payload["unit_ids"]:
            return False, "Curriculum drafts require at least one unit."
        if not isinstance(payload.get("stages"), list) or len(payload["stages"]) != len(payload["unit_ids"]):
            return False, "Curriculum stages must match the ordered unit list."
    if event_type == "platform.curriculum.activated" and not payload.get("reviewer"):
        return False, "Curriculum activation requires an authenticated reviewer."
    if event_type.startswith("platform.synthetic_data."):
        forbidden = {"bundle", "bundles", "resource", "resources", "entry", "patient_bundle",
                     "fhir", "observations", "clinical_facts", "name", "address", "birth_date",
                     "birthdate", "payload_bundle"}
        leaked = sorted(forbidden.intersection(payload))
        if leaked:
            return False, ("Synthetic data audit events must not carry patient resource payloads; "
                           f"remove: {', '.join(leaked)}.")
        if event_type == "platform.synthetic_data.recipe_activated" and not payload.get("reviewer"):
            return False, "Recipe activation requires an authenticated reviewer."
        if event_type == "platform.synthetic_data.review_recorded" and not payload.get("reviewer_id"):
            return False, "Review decisions require a reviewer identifier."
        if event_type == "platform.synthetic_data.stage_changed":
            if not isinstance(payload.get("counts"), dict):
                return False, "Stage change events must carry a counts object."
            if payload.get("status") not in {"running", "completed", "failed", "skipped", "quarantined"}:
                return False, "Stage status is outside the pipeline vocabulary."
        if event_type == "platform.synthetic_data.validation_completed":
            if not isinstance(payload.get("finding_counts"), dict):
                return False, "Validation events must carry finding counts by severity."
            if not isinstance(payload.get("strict_conformance"), bool):
                return False, "Validation events must state whether strict conformance was checked."
        if event_type == "platform.synthetic_data.generation_completed":
            if payload.get("cohort_status") not in {"complete", "partial_cohort", "not_applicable"}:
                return False, "Cohort status is outside the declared vocabulary."
            for key in ("generated_patients", "matched_patients", "selected_patients"):
                value = payload.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return False, f"{key} must be a non-negative integer."
    if event_type.startswith("simulation."):
        if not isinstance(payload.get("run_id"), str) or not payload["run_id"].startswith("simrun_"):
            return False, "Simulation events require a valid simrun_ identifier."
        if event_type == "simulation.clock.advanced":
            if not all(isinstance(payload.get(key), int) for key in ("from_minute", "to_minute", "requested_advance_min")):
                return False, "Simulation clock values must be integers."
            if payload["to_minute"] <= payload["from_minute"]:
                return False, "Simulation clock must advance monotonically."
        if event_type in {"simulation.document.saved", "simulation.order.entered", "simulation.handover.submitted"} and not isinstance(payload.get("content"), dict):
            return False, "Simulation document content must be a structured object."
        if event_type == "simulation.assessment.derived":
            if payload.get("competence_claimed") is not False:
                return False, "The first simulation assessment must not claim clinical competence."
            if not isinstance(payload.get("score"), int) or not isinstance(payload.get("maximum"), int):
                return False, "Simulation assessment scores must be integers."
    return True, ""


def event_catalogue() -> dict[str, Any]:
    return {
        "schema": EVENT_SCHEMA_VERSION,
        "events": {
            event_type: {"required": list(schema.required), "description": schema.description}
            for event_type, schema in sorted(EVENT_SCHEMAS.items())
        },
        "policy": "append-only; malformed writes are rejected and audited as platform.write.prevented",
    }
