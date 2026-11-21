"""Phase 2/3 learning routes: episodes, feedback preview, revision scheduler,
faceted search, content-review queue, and manual job pump.

No route here collides with an existing main.py path:
  * existing GET  /api/search                     -> we add POST /api/search/faceted
  * existing GET  /api/revision                   -> we add /api/revision/analytics etc.
  * existing POST /api/revision/cards/{id}/grade  -> we add /api/revision/cards/{id}/review
  * existing GET/POST /api/jobs                   -> we add /api/jobs/run-once
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..hsptl_core.episodes import ConflictError, NotFoundError
from ..hsptl_core.reasoning_feedback import build_feedback
from ..hsptl_core.scheduling import GRADES, scheduler_catalogue
from ..runtime import EPISODES, JOBS, REVIEWS, SEARCH, STORE

router = APIRouter(prefix="/api", tags=["learning"])


class StartEpisode(BaseModel):
    source_type: Literal["fhir_encounter", "curated_case", "exam_attempt",
                         "pearl_review", "puzzle_run"]
    source_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(default="", max_length=80)
    learning_goal: str = Field(default="", max_length=200)
    specialty: str = Field(default="", max_length=80)
    jurisdiction: str = Field(default="", max_length=60)
    provenance_status: Literal["source_documented", "curated",
                               "learner_authored", "mixed"] = "source_documented"
    content_version_id: str = Field(default="", max_length=80)


class DraftUpdate(BaseModel):
    draft: dict[str, Any]
    expected_revision: int | None = None
    stage: int | None = Field(default=None, ge=1, le=5)


class ArtifactCreate(BaseModel):
    kind: str
    body: dict[str, Any]
    authored_by: Literal["learner", "curator", "system"] = "learner"
    verification_status: Literal["unverified", "needs_review", "verified"] = "unverified"
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class FacetedSearch(BaseModel):
    q: str = Field(default="", max_length=300)
    facets: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class SchedulerChoice(BaseModel):
    scheduler: Literal["simple", "fsrs"]


class ResolveReview(BaseModel):
    status: Literal["verified", "retired", "in_review", "open"]
    reviewer: str = Field(default="local learner", max_length=120)
    review_date: str | None = Field(default=None, max_length=20)


class FeedbackPreview(BaseModel):
    payload: dict[str, Any]
    available_facts: list[dict[str, Any]] = Field(default_factory=list)
    curated_rubric: dict[str, Any] | None = None


@router.post("/episodes")
def start_episode(payload: StartEpisode) -> dict[str, Any]:
    try:
        return EPISODES.start_or_resume(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/episodes")
def list_episodes(status: str | None = None, limit: int = 30, offset: int = 0) -> dict[str, Any]:
    return EPISODES.list(status=status, limit=limit, offset=offset)


@router.get("/episodes/next")
def next_action() -> dict[str, Any]:
    """One recommended next action, never a wall of competing destinations."""
    active = EPISODES.latest_active()
    stats = STORE.stats()
    if active:
        return {"action": "continue_case", "episode": active,
                "label": "Continue your reasoning episode",
                "reason": "You have an unfinished episode in this workspace."}
    if stats["due"]:
        return {"action": "review_due", "due": stats["due"],
                "label": f"Review {stats['due']} due item(s)",
                "reason": "Scheduled review is the highest-value action when no case is open.",
                "estimated_minutes": max(1, min(20, stats["due"]))}
    return {"action": "start_case", "label": "Start a focused case",
            "reason": "No open episode and nothing due."}


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: str) -> dict[str, Any]:
    try:
        return EPISODES.get(episode_id)
    except NotFoundError as exc:
        raise HTTPException(404, "Learning episode not found") from exc


@router.patch("/episodes/{episode_id}/draft")
def save_draft(episode_id: str, payload: DraftUpdate) -> dict[str, Any]:
    try:
        return EPISODES.save_draft(episode_id, payload.draft,
                                   expected_revision=payload.expected_revision, stage=payload.stage)
    except NotFoundError as exc:
        raise HTTPException(404, "Learning episode not found") from exc
    except ConflictError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/episodes/{episode_id}/complete")
def complete_episode(episode_id: str) -> dict[str, Any]:
    try:
        return EPISODES.set_status(episode_id, "completed")
    except NotFoundError as exc:
        raise HTTPException(404, "Learning episode not found") from exc


@router.post("/episodes/{episode_id}/artifacts")
def add_artifact(episode_id: str, payload: ArtifactCreate) -> dict[str, Any]:
    try:
        return EPISODES.add_artifact(episode_id, payload.kind, payload.body,
                                     authored_by=payload.authored_by,
                                     verification_status=payload.verification_status,
                                     source_refs=payload.source_refs)
    except NotFoundError as exc:
        raise HTTPException(404, "Learning episode not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/episodes/{episode_id}/lineage")
def lineage(episode_id: str) -> dict[str, Any]:
    try:
        return EPISODES.lineage(episode_id)
    except NotFoundError as exc:
        raise HTTPException(404, "Learning episode not found") from exc


@router.post("/learning/feedback-preview")
def feedback_preview(payload: FeedbackPreview) -> dict[str, Any]:
    """Process-level feedback layer. Diagnostic grading stays reserved for curated cases."""
    try:
        return build_feedback(payload.payload, available_facts=payload.available_facts,
                              curated_rubric=payload.curated_rubric)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/revision/analytics")
def revision_analytics() -> dict[str, Any]:
    return STORE.review_analytics()


@router.get("/revision/schedulers")
def schedulers() -> dict[str, Any]:
    return {"active": STORE.scheduler_name(), "available": scheduler_catalogue(),
            "note": "FSRS is an unvalidated preview. Switching does not imply better retention."}


@router.put("/revision/scheduler")
def set_scheduler(payload: SchedulerChoice) -> dict[str, Any]:
    return {"scheduler": STORE.set_scheduler(payload.scheduler)}


@router.post("/revision/cards/{card_id}/review")
def review_card(card_id: str, grade: str) -> dict[str, Any]:
    """Scheduler-aware grading. Coexists with the legacy /grade endpoint."""
    if grade not in GRADES:
        raise HTTPException(400, "Unsupported review grade")
    try:
        return STORE.grade_card(card_id, grade)
    except KeyError as exc:
        raise HTTPException(404, "Revision card not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/search/faceted")
def faceted_search(payload: FacetedSearch) -> dict[str, Any]:
    return SEARCH.search(payload.q, facets=payload.facets,
                         limit=payload.limit, offset=payload.offset)


@router.get("/content/review")
def review_queue(status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
    return REVIEWS.queue(status=status, limit=limit)


@router.post("/content/review/{item_id}/resolve")
def resolve_review(item_id: str, payload: ResolveReview) -> dict[str, Any]:
    try:
        return REVIEWS.resolve(item_id, status=payload.status, reviewer=payload.reviewer,
                               review_date=payload.review_date)
    except KeyError as exc:
        raise HTTPException(404, "Review item not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/content/rebuild")
def queue_content_rebuild() -> dict[str, str]:
    return {"id": STORE.create_job("content_rebuild", {}), "status": "queued"}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, bool]:
    if not JOBS.request_cancel(job_id):
        raise HTTPException(404, "Background job not found")
    return {"cancel_requested": True}


@router.post("/jobs/run-once")
def run_one_job() -> dict[str, bool]:
    """Manually pump the durable queue once. No background thread is started."""
    return {"ran": JOBS.run_once()}
