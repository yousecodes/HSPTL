from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import hashlib, hmac, json, os, uuid, threading
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..runtime import PATHS
from ..hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from ..hsptl_core.hsp_tl40.kernel import EventKernel
from ..hsptl_core.hsp_tl40.router import Router as LearningRouter
from ..hsptl_core.hsp_tl40.guards import Guards
from ..hsptl_core.hsp_tl40.proforma import evaluate as evaluate_proforma
from ..hsptl_core.content_factory import ContentFactory, ContentPackError, DEFAULT_OUTPUT_TYPES
from ..hsptl_core.generation_distribution import GenerationDistribution
from ..hsptl_core.unified_content import UnifiedContentPipeline

router = APIRouter(prefix="/api/content-factory", tags=["content-factory"])
FACTORY = ContentFactory()
ENGINE = GenerationDistribution(PATHS["database"])
_EVENT_ENGINE = DeterministicIntelligenceEngine(PATHS["database"])
KERNEL = EventKernel(_EVENT_ENGINE)
_ROUTER = LearningRouter(KERNEL, Guards(KERNEL, _EVENT_ENGINE), _EVENT_ENGINE)
LOCAL_LEARNER_ID = "local-default"
_QUIZ_SUBMISSION_LOCK = threading.Lock()
_CONTENT_REFRESH_LOCK = threading.RLock()


def _events(event_type: str | None = None) -> list[dict[str, Any]]:
    return [event for event in KERNEL.platform_events(limit=10000)
            if event_type is None or event["event_type"] == event_type]


def _reviewer(token: str | None) -> str:
    expected = os.environ.get("HSPTL_REVIEWER_TOKEN", "")
    reviewer = os.environ.get("HSPTL_REVIEWER_ID", "").strip()
    if len(expected) < 32 or not reviewer:
        raise HTTPException(503, "Reviewer authentication is not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Valid reviewer credentials are required")
    return reviewer[:160]


def _completed_unit_ids() -> list[str]:
    completed = set()
    for event in _events("platform.learning.quiz_submitted"):
        payload = event["payload"]
        if payload.get("learner_id") == LOCAL_LEARNER_ID:
            completed.add(payload.get("unit_id"))
    return sorted(item for item in completed if item)


def _active_curriculum_eligibility(unit_id: str, curriculum_id: str, curriculum_version: int, *, audit: bool = True) -> dict[str, Any]:
    active = _curriculum_projection().get("active")
    if not active:
        return {"decision": "pass", "reason": "No active curriculum imposes a prerequisite gate."}
    if curriculum_id != active["curriculum_id"] or curriculum_version != active["version"]:
        return {"decision": "fail", "reason": "The learner action does not reference the active curriculum version."}
    stage = next((item for item in active["stages"] if item["unit_id"] == unit_id), None)
    if stage is None:
        return {"decision": "fail", "reason": "This unit is not part of the active curriculum."}
    context = {"learner": {"completed_units": _completed_unit_ids()}}
    if audit:
        result = _ROUTER.eligibility(stage["unlock_predicate"], context)
        decision = result["decision"]
        derivation = result.get("derivation")
    else:
        result = evaluate_proforma(stage["unlock_predicate"], context)
        decision = result.state
        derivation = {"proof_trace": result.trace, "logic_language": "HSPTL-PROforma-Subset/1.1"}
    return {"decision": decision, "reason": "PROforma curriculum prerequisite evaluation.",
            "derivation": derivation, "completed_units": context["learner"]["completed_units"]}


def _curriculum_projection() -> dict[str, Any]:
    drafts: dict[str, dict[str, Any]] = {}
    active: dict[str, Any] | None = None
    for event in _events():
        payload = event["payload"]
        if event["event_type"] == "platform.curriculum.draft_created":
            drafts[payload["curriculum_id"]] = {**payload, "created_event": event["event_id"], "created_seq": event["seq"]}
        elif event["event_type"] == "platform.curriculum.activated":
            draft = drafts.get(payload["curriculum_id"])
            if draft and draft["version"] == payload["version"] and draft["content_digest"] == payload["content_digest"]:
                draft["status"] = "active"
                active = {**draft, "status": "active", "activation": payload,
                          "activation_event": event["event_id"], "activation_seq": event["seq"]}
    return {"active": active, "drafts": sorted(drafts.values(), key=lambda x: x["created_seq"], reverse=True),
            "projection": "derived from canonical HSPTL 4.0 event log"}


def _refresh_installed_content(*, reload_packs: bool) -> dict[str, Any]:
    """Prepare drafts through the shared idempotent pipeline used at startup and on demand."""
    global FACTORY
    with _CONTENT_REFRESH_LOCK:
        if reload_packs:
            # Construct first. A malformed pack must not replace the last valid factory.
            refreshed_factory = ContentFactory()
            FACTORY = refreshed_factory
        return UnifiedContentPipeline(FACTORY, ENGINE).refresh()


def ensure_startup_content() -> dict[str, Any]:
    """Run during FastAPI lifespan; safe to call on every application start."""
    return _refresh_installed_content(reload_packs=True)


class GenerateRequest(BaseModel):
    unit_id: str = Field(min_length=3, max_length=100)
    kind: str = Field(min_length=3, max_length=60)
    seed: int = Field(default=0, ge=0, le=2_147_483_647)


class BatchRequest(BaseModel):
    unit_ids: list[str] = Field(min_length=1, max_length=12)
    kinds: list[str] = Field(min_length=1, max_length=len(DEFAULT_OUTPUT_TYPES))
    seed: int = Field(default=0, ge=0, le=2_147_483_647)


class QuizAttemptRequest(BaseModel):
    answers: dict[str, int]
    idempotency_key: str = Field(min_length=8, max_length=120)
    curriculum_id: str = Field(default="", max_length=120)
    curriculum_version: int = Field(default=0, ge=0)


class CurriculumComposeRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    unit_ids: list[str] = Field(min_length=1, max_length=12)
    prerequisites: dict[str, list[str]] = Field(default_factory=dict)
    description: str = Field(default="", max_length=1000)


@router.get("/catalog")
def content_catalog() -> dict[str, Any]:
    return FACTORY.catalog()


@router.get("/units/{unit_id}")
def content_unit(unit_id: str, curriculum_id: str = "", curriculum_version: int = 0) -> dict[str, Any]:
    item = FACTORY.get_unit(unit_id)
    if item is None:
        raise HTTPException(404, "Learning unit not found")
    eligibility = _active_curriculum_eligibility(unit_id, curriculum_id, curriculum_version, audit=False)
    if eligibility["decision"] != "pass":
        raise HTTPException(409, {"state": eligibility["decision"], "reason": eligibility["reason"],
                                  "derivation": eligibility.get("derivation")})
    return item


@router.get("/status")
def factory_status() -> dict[str, Any]:
    catalog = FACTORY.catalog()
    return {
        "mode": "deterministic_template_composer",
        "model_required": False,
        "api_key_required": False,
        "pack_count": catalog.get("pack_count", 1),
        "unit_count": catalog["unit_count"],
        "retrieval_question_count": catalog["question_count"],
        "output_types": list(DEFAULT_OUTPUT_TYPES),
        "review_required": True,
        "auto_publish": False,
        "version": "1.0.0",
    }




@router.post("/refresh")
def refresh_all_content() -> dict[str, Any]:
    """Refresh deterministic drafts across all learning workspaces from installed packs."""
    try:
        return _refresh_installed_content(reload_packs=True)
    except ContentPackError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(422, "Installed content could not be refreshed. Check the versioned content packs.") from exc


@router.post("/generate", status_code=201)
def generate_content(payload: GenerateRequest) -> dict[str, Any]:
    try:
        spec = FACTORY.build(payload.unit_id, payload.kind, payload.seed)
        return ENGINE.create_structured_draft(
            workspace=spec["workspace"], kind=spec["kind"], title=spec["title"],
            body=spec["body"], source_refs=spec["source_refs"],
            template_version=spec["template_version"], audit_event="generated_by_content_factory",
        )
    except ContentPackError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/batch", status_code=201)
def generate_batch(payload: BatchRequest) -> dict[str, Any]:
    try:
        specs = FACTORY.build_batch(payload.unit_ids, payload.kinds, payload.seed)
        items = []
        for spec in specs:
            artifact = ENGINE.create_structured_draft(
                workspace=spec["workspace"], kind=spec["kind"], title=spec["title"],
                body=spec["body"], source_refs=spec["source_refs"],
                template_version=spec["template_version"], audit_event="generated_by_content_factory_batch",
            )
            items.append({"id": artifact["id"], "title": artifact["title"], "kind": artifact["kind"],
                          "workspace": artifact["workspace"], "status": artifact["status"],
                          "unit_id": artifact["body"].get("unit_id"), "content_hash": artifact["content_hash"]})
        unique_ids = {item["id"] for item in items}
        return {"requested": len(specs), "draft_count": len(unique_ids), "items": items,
                "status": "drafts_created_or_reused", "auto_approved": False,
                "message": "All outputs are drafts. Expert review is required before distribution."}
    except ContentPackError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/units/{unit_id}/opened", status_code=201)
def record_unit_opened(unit_id: str, curriculum_id: str = "", curriculum_version: int = 0) -> dict[str, Any]:
    unit = FACTORY.get_unit(unit_id)
    if unit is None:
        raise HTTPException(404, "Learning unit not found")
    eligibility = _active_curriculum_eligibility(unit_id, curriculum_id, curriculum_version)
    if eligibility["decision"] != "pass":
        raise HTTPException(409, {"state": eligibility["decision"], "reason": eligibility["reason"],
                                  "derivation": eligibility.get("derivation")})
    payload = {"learner_id": LOCAL_LEARNER_ID, "curriculum_id": curriculum_id,
               "curriculum_version": curriculum_version, "unit_id": unit_id,
               "pack_id": unit["pack"]["pack_id"], "pack_version": unit["pack"]["version"]}
    event = KERNEL.append("platform.learning.unit_opened", payload)
    return {"opened": True, "event_id": event["event_id"], "unit_id": unit_id}


@router.post("/units/{unit_id}/attempts", status_code=201)
def submit_unit_quiz(unit_id: str, payload: QuizAttemptRequest) -> dict[str, Any]:
    with _QUIZ_SUBMISSION_LOCK:
        return _submit_unit_quiz_locked(unit_id, payload)


def _submit_unit_quiz_locked(unit_id: str, payload: QuizAttemptRequest) -> dict[str, Any]:
    unit = FACTORY.get_unit(unit_id)
    if unit is None:
        raise HTTPException(404, "Learning unit not found")
    existing = next((event for event in _events("platform.learning.quiz_submitted")
                     if event["payload"].get("learner_id") == LOCAL_LEARNER_ID
                     and event["payload"].get("idempotency_key") == payload.idempotency_key), None)
    if existing:
        previous = existing["payload"]
        if previous.get("unit_id") != unit_id:
            raise HTTPException(409, "Idempotency key was already used for another learning unit")
        return {"attempt": previous, "event_id": existing["event_id"], "reused": True,
                "message": "This submission was already recorded; the original result is returned."}
    eligibility = _active_curriculum_eligibility(unit_id, payload.curriculum_id, payload.curriculum_version)
    if eligibility["decision"] != "pass":
        raise HTTPException(409, {"state": eligibility["decision"], "reason": eligibility["reason"],
                                  "derivation": eligibility.get("derivation")})
    if len(payload.answers) != len(unit["quiz"]):
        raise HTTPException(422, "Submit one answer for every question")
    results = []
    score = 0
    objective_counts: dict[str, dict[str, int]] = {}
    for index, question in enumerate(unit["quiz"]):
        key = str(index)
        if key not in payload.answers:
            raise HTTPException(422, f"Missing answer for question {index + 1}")
        selected = payload.answers[key]
        if type(selected) is not int or not 0 <= selected < len(question["options"]):
            raise HTTPException(422, f"Invalid answer for question {index + 1}")
        correct = selected == question["correct_index"]
        score += int(correct)
        objective = question.get("objective_id") or unit["objectives"][index % len(unit["objectives"])]
        bucket = objective_counts.setdefault(objective, {"correct": 0, "total": 0})
        bucket["correct"] += int(correct); bucket["total"] += 1
        results.append({"index": index, "selected_index": selected, "correct_index": question["correct_index"],
                        "correct": correct, "rationale": question["rationale"], "objective": objective})
    objective_results = [{"objective": objective, **counts,
                          "percent": round(counts["correct"] / counts["total"] * 100, 1)}
                         for objective, counts in sorted(objective_counts.items())]
    attempt = {"attempt_id": "quiz_" + uuid.uuid4().hex, "idempotency_key": payload.idempotency_key,
               "learner_id": LOCAL_LEARNER_ID, "curriculum_id": payload.curriculum_id,
               "curriculum_version": payload.curriculum_version, "unit_id": unit_id,
               "pack_id": unit["pack"]["pack_id"], "pack_version": unit["pack"]["version"],
               "score": score, "maximum": len(unit["quiz"]), "percentage": round(score / len(unit["quiz"]) * 100, 1),
               "responses": results, "objective_results": objective_results,
               "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "assessment_scope": "formative retrieval practice; not clinical competence"}
    event = KERNEL.append("platform.learning.quiz_submitted", attempt)
    return {"attempt": attempt, "event_id": event["event_id"], "reused": False,
            "message": "Formative attempt saved to the canonical event history."}


@router.get("/curricula")
def list_curricula() -> dict[str, Any]:
    projection = _curriculum_projection()
    active = projection.get("active")
    eligibility = []
    if active:
        context = {"learner": {"completed_units": _completed_unit_ids()}}
        for stage in active["stages"]:
            result = evaluate_proforma(stage["unlock_predicate"], context)
            eligibility.append({"unit_id": stage["unit_id"], "decision": result.state,
                                "proof_trace": result.trace})
    projection["eligibility"] = eligibility
    projection["eligible_unit_ids"] = [item["unit_id"] for item in eligibility if item["decision"] == "pass"]
    projection["completed_unit_ids"] = _completed_unit_ids()
    return projection


@router.post("/curricula/compose", status_code=201)
def compose_curriculum(payload: CurriculumComposeRequest) -> dict[str, Any]:
    catalog = FACTORY.catalog()
    units = {item["unit_id"]: item for item in catalog["units"]}
    if len(set(payload.unit_ids)) != len(payload.unit_ids):
        raise HTTPException(422, "Curriculum unit ids must be unique")
    missing = sorted(set(payload.unit_ids) - set(units))
    if missing:
        raise HTTPException(422, f"Unknown curriculum units: {', '.join(missing)}")
    extra_graph_keys = sorted(set(payload.prerequisites) - set(payload.unit_ids))
    if extra_graph_keys:
        raise HTTPException(422, f"Prerequisite graph contains unknown unit keys: {', '.join(extra_graph_keys)}")
    graph = {unit_id: list(payload.prerequisites.get(unit_id, [])) for unit_id in payload.unit_ids}
    for unit_id, prereqs in graph.items():
        if len(prereqs) != len(set(prereqs)):
            raise HTTPException(422, f"Prerequisites for {unit_id} must be unique")
        unknown = sorted(set(prereqs) - set(payload.unit_ids))
        if unknown:
            raise HTTPException(422, f"Unknown prerequisites for {unit_id}: {', '.join(unknown)}")
    ordered = _ROUTER.topological_order(graph)
    if ordered["state"] != "pass":
        raise HTTPException(422, ordered["reason"])
    stages = []
    for position, unit_id in enumerate(ordered["order"], start=1):
        item = units[unit_id]
        prereqs = graph[unit_id]
        unlock = {"op": "set_includes", "left": {"ref": "learner.completed_units"}, "right": prereqs} if prereqs else True
        stages.append({"position": position, "unit_id": unit_id, "title": item["title"],
                       "objectives": item["objectives"], "assessment_count": item["quiz_count"],
                       "pack_id": item["pack_id"], "pack_version": item["pack_version"],
                       "prerequisites": prereqs, "unlock_predicate": unlock,
                       "logic_language": "HSPTL-PROforma-Subset/1.1"})
    manifest = {"curriculum_id": "curr_" + uuid.uuid4().hex, "version": 1, "title": payload.title,
                "description": payload.description, "unit_ids": ordered["order"], "stages": stages,
                "prerequisites": graph, "unlock_logic_version": "HSPTL-PROforma-Subset/1.1",
                "source_packs": sorted({(units[key]["pack_id"], units[key]["pack_version"]) for key in payload.unit_ids}),
                "status": "draft", "ordering_derivation": ordered["derivation"]}
    manifest["source_packs"] = [{"pack_id": pack, "version": version} for pack, version in manifest["source_packs"]]
    digest_payload = {key: value for key, value in manifest.items() if key != "curriculum_id"}
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest["content_digest"] = digest
    event_payload = {key: manifest[key] for key in ("curriculum_id", "version", "title", "description", "unit_ids", "stages", "prerequisites", "source_packs", "ordering_derivation", "unlock_logic_version", "content_digest", "status")}
    event = KERNEL.append("platform.curriculum.draft_created", event_payload)
    return {"curriculum": manifest, "event_id": event["event_id"], "status": "draft",
            "message": "Curriculum composed. It is not available to learners until reviewer activation."}


@router.post("/curricula/{curriculum_id}/activate")
def activate_curriculum(curriculum_id: str, x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    projection = _curriculum_projection()
    draft = next((item for item in projection["drafts"] if item["curriculum_id"] == curriculum_id), None)
    if not draft:
        raise HTTPException(404, "Curriculum draft not found")
    if draft["status"] != "draft":
        raise HTTPException(409, "Only draft curricula can be activated")
    activated = {"curriculum_id": curriculum_id, "version": draft["version"],
                 "content_digest": draft["content_digest"], "reviewer": reviewer,
                 "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    event = KERNEL.append("platform.curriculum.activated", activated)
    return {"activated": True, "curriculum_id": curriculum_id, "version": draft["version"],
            "reviewer": reviewer, "event_id": event["event_id"]}


@router.get("/progress")
def learning_unit_progress() -> dict[str, Any]:
    opened: dict[str, int] = {}
    attempts: dict[str, list[dict[str, Any]]] = {}
    for event in _events():
        payload = event["payload"]
        if payload.get("learner_id") != LOCAL_LEARNER_ID:
            continue
        if event["event_type"] == "platform.learning.unit_opened":
            opened[payload["unit_id"]] = opened.get(payload["unit_id"], 0) + 1
        elif event["event_type"] == "platform.learning.quiz_submitted":
            attempts.setdefault(payload["unit_id"], []).append({**payload, "event_id": event["event_id"], "seq": event["seq"]})
    units = []
    for unit in FACTORY.catalog()["units"]:
        history = attempts.get(unit["unit_id"], [])
        latest = history[-1] if history else None
        units.append({"unit_id": unit["unit_id"], "title": unit["title"], "opened_count": opened.get(unit["unit_id"], 0),
                      "attempt_count": len(history), "latest_score": latest["score"] if latest else None,
                      "latest_maximum": latest["maximum"] if latest else None,
                      "latest_percent": latest["percentage"] if latest else None,
                      "objective_results": latest["objective_results"] if latest else [],
                      "last_attempt_at": latest["submitted_at"] if latest else None})
    latest_percentages = [item["latest_percent"] for item in units if item["latest_percent"] is not None]
    return {"units": units, "total_attempts": sum(len(value) for value in attempts.values()),
            "completed_units": sum(1 for value in attempts.values() if value),
            "latest_average_percent": round(sum(latest_percentages) / len(latest_percentages), 1) if latest_percentages else None,
            "latest_average_units": len(latest_percentages),
            "projection": "event fold; no computed progress value is stored"}
