"""HSPTL 5.2.0 source and learning intelligence API: sources, local folders, labels, lottery, engines, pearls.

Design notes that matter for reviewing this file:

* Local folder management is an *administration* surface. No endpoint accepts a
  filesystem path for reading; a scan takes a ``root_id`` that was registered
  locally with a named administrator. ``GET /local-folders`` returns metadata
  only, never a directory listing of arbitrary paths.
* Reviewer decisions reuse the existing ``HSPTL_REVIEWER_TOKEN`` /
  ``HSPTL_REVIEWER_ID`` convention rather than inventing a second auth scheme.
* Read-only endpoints stay open so the learner UI works without configuration;
  every mutating governance action requires the reviewer token.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..runtime import (
    STORE, LABELS, SOURCE_REGISTRY, LOCAL_SOURCES, CASE_LOTTERY, PEARLS_FACTORY,
    ENGINE_INTEGRATION, UCKS_REPO, JOBS, LOCAL_SOURCE_JOB_KIND, LEARNING_INTELLIGENCE,
)
from ..hsptl_core.content_labels import (
    CONTENT_LABELS, LABEL_DERIVED, LABEL_GENERATED, LABEL_IMPORTED, LABEL_SYNTHETIC,
    LabelError, LabelledContent, LineageRef, content_hash, describe_labels,
)
from ..hsptl_core.source_registry import (
    RightsError, SourceRegistry, SourceRights,
)
from ..hsptl_core.local_sources import LocalSourceError
from ..hsptl_core.case_lottery import LotteryError, WORKSPACES as LOTTERY_WORKSPACES
from ..hsptl_core.engine_integration import IntegrationError, EngineIntegration, SKINS, WORKSPACES as PRODUCT_WORKSPACES
from ..hsptl_core.pearls_factory import PearlsFactory, TEMPLATES

router = APIRouter(prefix="/api/v5", tags=["HSPTL 5.0 next increments"])


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

def _reviewer(token: str | None) -> str:
    expected = os.environ.get("HSPTL_REVIEWER_TOKEN", "")
    reviewer = os.environ.get("HSPTL_REVIEWER_ID", "").strip()
    if len(expected) < 32 or not reviewer:
        raise HTTPException(
            status_code=503,
            detail=("Reviewer authentication is not configured. Set HSPTL_REVIEWER_TOKEN "
                    "(32+ characters) and HSPTL_REVIEWER_ID before enabling governance decisions."))
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Valid reviewer credentials are required")
    return reviewer[:160]


def _admin(token: str | None) -> str:
    expected = os.environ.get("HSPTL_ADMIN_TOKEN", "")
    administrator = os.environ.get("HSPTL_ADMIN_ID", "").strip()
    if len(expected) < 32 or not administrator:
        raise HTTPException(
            status_code=503,
            detail=("Local administration is not configured. Set HSPTL_ADMIN_TOKEN "
                    "(32+ characters) and HSPTL_ADMIN_ID to manage local source folders."))
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Valid administrator credentials are required")
    return administrator[:160]


# --------------------------------------------------------------------------- #
# Content labels
# --------------------------------------------------------------------------- #

class LabelBody(BaseModel):
    label: str
    title: str = Field(min_length=1, max_length=500)
    content_hash: str = Field(min_length=8, max_length=128)
    workspace: str = Field(default="", max_length=80)
    content_type: str = Field(default="", max_length=80)
    lineage: list[dict[str, Any]] = Field(default_factory=list)
    rights_status: str = "unknown"
    clinical_review_status: str = "unreviewed"
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/labels")
def label_catalogue() -> dict[str, Any]:
    """The four labels, their meanings, and the dimensions kept separate from them."""
    return describe_labels() | {"registry": LABELS.summary()}


@router.post("/labels", status_code=201)
def register_label(payload: LabelBody) -> dict[str, Any]:
    try:
        lineage = tuple(LineageRef(item_id=ref["item_id"], label=ref["label"],
                                   role=ref.get("role", "source"),
                                   content_hash=ref.get("content_hash", ""))
                        for ref in payload.lineage)
        record = LABELS.register(LabelledContent(
            label=payload.label, title=payload.title, content_hash=payload.content_hash,
            workspace=payload.workspace, content_type=payload.content_type,
            lineage=lineage, rights_status=payload.rights_status,
            clinical_review_status=payload.clinical_review_status,
            metadata=payload.metadata,
        ))
    except LabelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Lineage entry is missing {exc}") from exc
    return record


@router.get("/labels/items/{item_id}")
def get_label_item(item_id: str) -> dict[str, Any]:
    record = LABELS.get(item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown content label item")
    return record | {"lineage_chain": LABELS.lineage_chain(item_id)}


@router.get("/labels/items/{item_id}/lineage")
def label_lineage(item_id: str) -> dict[str, Any]:
    record = LABELS.get(item_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown content label item")
    return LABELS.lineage_chain(item_id) | {"children": LABELS.children(item_id)}


@router.get("/lineage/summary")
def lineage_summary() -> dict[str, Any]:
    return {"labels": LABELS.summary(), "note": (
        "Derived content must always resolve to at least one parent. "
        "A non-zero derived_without_lineage count is an integrity fault.")}


# --------------------------------------------------------------------------- #
# Source registry
# --------------------------------------------------------------------------- #

class SourceRegisterBody(BaseModel):
    source_id: str = Field(min_length=1, max_length=120)
    catalogue_key: str = Field(default="", max_length=80)
    family: str = Field(default="", max_length=80)
    priority: int | None = None


class SourceRightsBody(BaseModel):
    access: str = "unknown"
    reuse: str = "unknown"
    adaptation: str = "unknown"
    licence: str = Field(default="", max_length=300)
    licence_uri: str = Field(default="", max_length=2000)
    attribution: str = Field(default="", max_length=2000)
    jurisdiction: str = Field(default="global", max_length=120)
    rationale: str = Field(default="", max_length=4000)
    evidence_reference: str = Field(default="", max_length=2000)


@router.get("/sources/catalogue")
def source_catalogue() -> dict[str, Any]:
    """Prioritised source families with their typical rights posture."""
    return {
        "items": SourceRegistry.catalogue(),
        "count": len(SourceRegistry.catalogue()),
        "note": ("Catalogue defaults describe what is typical for a source family. They are a "
                 "prompt to review, never a rights decision. Priority is a curation hint and "
                 "says nothing about evidence quality."),
    }


@router.get("/sources/registry")
def list_registry(family: str = "", reviewed_only: bool = False) -> dict[str, Any]:
    items = SOURCE_REGISTRY.list_sources(family=family, only_reviewed=reviewed_only)
    return {"items": items, "count": len(items), "summary": SOURCE_REGISTRY.summary()}


@router.post("/sources/registry", status_code=201)
def register_source(payload: SourceRegisterBody,
                    x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    if not UCKS_REPO.get_source(payload.source_id):
        raise HTTPException(status_code=404, detail="Register the UCKS source before its rights record")
    try:
        record = SOURCE_REGISTRY.register(
            source_id=payload.source_id, catalogue_key=payload.catalogue_key,
            family=payload.family, priority=payload.priority,
            rights=SourceRights(reviewer=reviewer),
        )
    except RightsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return record


@router.put("/sources/registry/{source_id}/rights")
def record_source_rights(source_id: str, payload: SourceRightsBody,
                         x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    try:
        return SOURCE_REGISTRY.record_rights(source_id, SourceRights(
            access=payload.access, reuse=payload.reuse, adaptation=payload.adaptation,
            licence=payload.licence, licence_uri=payload.licence_uri,
            attribution=payload.attribution, jurisdiction=payload.jurisdiction,
            reviewer=reviewer, rationale=payload.rationale,
            evidence_reference=payload.evidence_reference,
        ))
    except RightsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sources/registry/{source_id}")
def get_registry_source(source_id: str) -> dict[str, Any]:
    record = SOURCE_REGISTRY.get(source_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown registered source")
    return record | {"history": SOURCE_REGISTRY.history(source_id)}


# --------------------------------------------------------------------------- #
# Local folder sources
# --------------------------------------------------------------------------- #

class LocalRootBody(BaseModel):
    path: str = Field(min_length=1, max_length=4000)
    label: str = Field(min_length=1, max_length=200)
    recursive: bool = True
    allow_archives: bool = False
    include_pattern: str = Field(default="", max_length=200)


class LocalScheduleBody(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=1440, ge=15, le=10080)


@router.get("/local-folders")
def list_local_folders() -> dict[str, Any]:
    """Metadata about configured roots. Never a directory listing."""
    return {
        "items": LOCAL_SOURCES.list_roots(),
        "summary": LOCAL_SOURCES.summary(),
        "safety": {
            "read_only": True,
            "arbitrary_paths_over_http": False,
            "follows_symlinks": False,
            "opens_active_content": False,
            "note": ("Folders are added through local administration only. No endpoint accepts "
                     "a path for reading, and scanning never modifies the folder."),
        },
    }


@router.post("/local-folders", status_code=201)
def add_local_folder(payload: LocalRootBody,
                     x_hsptl_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    administrator = _admin(x_hsptl_admin_token)
    try:
        return LOCAL_SOURCES.register_root(
            path=payload.path, label=payload.label, registered_by=administrator,
            recursive=payload.recursive, allow_archives=payload.allow_archives,
            include_pattern=payload.include_pattern,
        )
    except LocalSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/local-folders/{root_id}/scan")
def scan_local_folder(root_id: str,
                      x_hsptl_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    _admin(x_hsptl_admin_token)
    try:
        return LOCAL_SOURCES.scan(root_id, trigger="manual")
    except LocalSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/local-folders/{root_id}/schedule")
def schedule_local_folder(root_id: str, payload: LocalScheduleBody,
                          x_hsptl_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    _admin(x_hsptl_admin_token)
    try:
        return LOCAL_SOURCES.configure_schedule(root_id, enabled=payload.enabled,
                                                interval_minutes=payload.interval_minutes)
    except LocalSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/local-folders/{root_id}/enabled")
def set_local_folder_enabled(root_id: str, enabled: bool,
                             x_hsptl_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    _admin(x_hsptl_admin_token)
    try:
        return LOCAL_SOURCES.set_enabled(root_id, enabled)
    except LocalSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/local-folders/{root_id}")
def get_local_folder(root_id: str) -> dict[str, Any]:
    record = LOCAL_SOURCES.get_root(root_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown local source root")
    return record | {"latest_scan": LOCAL_SOURCES.latest_scan(root_id),
                     "files": LOCAL_SOURCES.files(root_id=root_id, limit=100)}


@router.get("/local-folders/files")
def local_folder_files(root_id: str = "", verdict: str = "", limit: int = 200) -> dict[str, Any]:
    items = LOCAL_SOURCES.files(root_id=root_id, verdict=verdict, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/local-folders/rescan-now")
def trigger_rescan(x_hsptl_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    """Queue the scheduled sweep on the existing durable job runner."""
    _admin(x_hsptl_admin_token)
    job_id = JOBS.store.create_job(LOCAL_SOURCE_JOB_KIND, {"trigger": "manual"})
    return {"job_id": job_id, "kind": LOCAL_SOURCE_JOB_KIND,
            "note": "Queued on the existing background job runner; a worker must be running."}


# --------------------------------------------------------------------------- #
# Daily case lottery
# --------------------------------------------------------------------------- #



class ClinicalEventBody(BaseModel):
    id: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(default="General", max_length=80)
    icon: str = Field(default="🏥", max_length=12)
    summary: str = Field(default="", max_length=1200)
    setting: str = Field(default="Clinical learning", max_length=160)
    learning_objectives: list[str] = Field(default_factory=list, max_length=20)
    case_signals: list[str] = Field(default_factory=list, max_length=30)
    workspaces: list[str] = Field(default_factory=lambda: ["clinic", "ward", "rounds"])
    selection_weight: int = Field(default=1, ge=1, le=100)
    active: bool = True
    cooldown_days: int = Field(default=2, ge=0, le=90)


class LotteryCaseBody(BaseModel):
    case_id: str = Field(default="", max_length=120)
    title: str = Field(min_length=2, max_length=300)
    stem: str = Field(min_length=1, max_length=8000)
    prompt: str = Field(min_length=1, max_length=2000)
    label: str
    specialty: str = Field(default="", max_length=120)
    difficulty: str = Field(default="Intermediate", max_length=40)
    presenting_complaint: str = Field(default="", max_length=2000)
    patient_age_value: int | None = Field(default=None, ge=0, le=125)
    patient_age_unit: str = Field(default="years", pattern="^(years|months|weeks|days)$")
    rights_status: str = "unknown"
    clinical_review_status: str = "unreviewed"
    publication_status: str = "unpublished"
    reveal: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class RevealBody(BaseModel):
    learner_id: str = Field(min_length=1, max_length=160)
    reason: str = "explicit_reveal"


@router.get("/lottery/summary")
def lottery_summary() -> dict[str, Any]:
    return CASE_LOTTERY.summary() | {"eligibility": CASE_LOTTERY.eligibility_report()}


@router.get("/lottery/daily")
def lottery_daily(workspace: str = "clinic", draw_date: str = "") -> dict[str, Any]:
    """The shared daily case. Both Ward Board and Clinic resolve to the same case."""
    try:
        return CASE_LOTTERY.draw(workspace=workspace, draw_date=draw_date or None)
    except LotteryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lottery/draws/{draw_id}/reveal")
def lottery_reveal(draw_id: str, payload: RevealBody) -> dict[str, Any]:
    try:
        return CASE_LOTTERY.reveal(draw_id=draw_id, learner_id=payload.learner_id,
                                   reason=payload.reason)
    except LotteryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/lottery/history")
def lottery_history(limit: int = 30) -> dict[str, Any]:
    items = CASE_LOTTERY.history(limit=limit)
    return {"items": items, "workspaces": list(LOTTERY_WORKSPACES), "count": len(items),
            "privacy": "Non-revealing archive projection; diagnosis and answer payloads are excluded."}


@router.get("/clinical-events")
def clinical_events() -> dict[str, Any]:
    items = CASE_LOTTERY.event_catalogue(active_only=True)
    return {"items": items, "count": len(items), "catalogue_version": "6.0", "note": "Educational themes only; not live alerts or care protocols."}


@router.put("/clinical-events/{event_id}")
def save_clinical_event(event_id: str, payload: ClinicalEventBody,
                        x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    _reviewer(x_hsptl_reviewer_token)
    if event_id != payload.id:
        raise HTTPException(status_code=400, detail="Path and body event IDs must match")
    try:
        return CASE_LOTTERY.upsert_event(payload.model_dump())
    except LotteryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lottery/cases", status_code=201)
def register_lottery_case(payload: LotteryCaseBody,
                          x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    _reviewer(x_hsptl_reviewer_token)
    try:
        return CASE_LOTTERY.register_case(
            case_id=payload.case_id, title=payload.title, stem=payload.stem,
            prompt=payload.prompt, label=payload.label, specialty=payload.specialty,
            difficulty=payload.difficulty, presenting_complaint=payload.presenting_complaint,
            patient_age_value=payload.patient_age_value, patient_age_unit=payload.patient_age_unit,
            rights_status=payload.rights_status,
            clinical_review_status=payload.clinical_review_status,
            publication_status=payload.publication_status, reveal=payload.reveal,
            source_refs=payload.source_refs,
        )
    except (LotteryError, LabelError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# Engine integration
# --------------------------------------------------------------------------- #

class InvokeBody(BaseModel):
    skin: str
    area: str
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/engines/matrix")
def engine_matrix() -> dict[str, Any]:
    return EngineIntegration.catalogue()


@router.get("/workspaces/contracts")
def workspace_engine_contracts() -> dict[str, Any]:
    """Canonical seven-workspace to shared-engine integration contract."""
    return ENGINE_INTEGRATION.workspace_catalogue()


@router.get("/workspaces/{workspace}/engines")
def workspace_engine_bindings(workspace: str) -> dict[str, Any]:
    try:
        bindings = ENGINE_INTEGRATION.bindings_for_workspace(workspace)
    except IntegrationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"workspace": workspace, "bindings": [item.to_dict() for item in bindings],
            "workspaces": list(PRODUCT_WORKSPACES)}


@router.get("/engines/skins/{skin}")
def engine_skin_bindings(skin: str, area: str = "") -> dict[str, Any]:
    try:
        bindings = ENGINE_INTEGRATION.bindings_for(skin, area)
    except IntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"skin": skin, "area": area, "bindings": [b.to_dict() for b in bindings],
            "skins": list(SKINS)}


@router.post("/engines/invoke")
def engine_invoke(payload: InvokeBody) -> dict[str, Any]:
    try:
        return ENGINE_INTEGRATION.invoke(skin=payload.skin, area=payload.area,
                                         operation=payload.operation, payload=payload.payload)
    except IntegrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing required field: {exc}") from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# Pearls factory
# --------------------------------------------------------------------------- #

class PearlComposeBody(BaseModel):
    topic: str = Field(min_length=2, max_length=140)
    template_id: str = "high_yield_pearl"
    seed: int = 0


class PearlReviewBody(BaseModel):
    decision: str


@router.get("/pearls-factory/templates")
def pearls_templates() -> dict[str, Any]:
    return {"templates": PearlsFactory.templates(), "summary": PEARLS_FACTORY.summary()}


@router.post("/pearls-factory/compose", status_code=201)
def pearls_compose(payload: PearlComposeBody) -> dict[str, Any]:
    try:
        return PEARLS_FACTORY.compose(topic=payload.topic, template_id=payload.template_id,
                                      seed=payload.seed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/pearls-factory/artifacts")
def pearls_artifacts(topic: str = "", limit: int = 50) -> dict[str, Any]:
    items = PEARLS_FACTORY.list_artifacts(topic=topic, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/pearls-factory/artifacts/{artifact_id}/review")
def pearls_review(artifact_id: str, payload: PearlReviewBody,
                  x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    try:
        return PEARLS_FACTORY.review(artifact_id, reviewer=reviewer, decision=payload.decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
# HSPTL 5.1 learning intelligence
# --------------------------------------------------------------------------- #

class SourceReliabilityBody(BaseModel):
    scores: dict[str, int]
    rationale: str = Field(min_length=12, max_length=4000)

class LearnerPreferencesBody(BaseModel):
    learner_id: str = Field(min_length=1, max_length=160)
    specialties: list[str] = Field(default_factory=list, max_length=30)
    difficulty: str = "Any"

class CaseAttemptBody(BaseModel):
    learner_id: str = Field(min_length=1, max_length=160)
    response: str = Field(min_length=20, max_length=12000)
    confidence: int | None = Field(default=None, ge=1, le=5)

@router.get("/sources/registry/{source_id}/reliability")
def source_reliability(source_id: str) -> dict[str, Any]:
    item = LEARNING_INTELLIGENCE.source_appraisal(source_id)
    return item or {"source_id": source_id, "state": "not_appraised",
                    "note": "Reliability appraisal is separate from reuse rights and evidence certainty."}

@router.put("/sources/registry/{source_id}/reliability")
def record_source_reliability(source_id: str, payload: SourceReliabilityBody,
                              x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    if SOURCE_REGISTRY.get(source_id) is None:
        raise HTTPException(status_code=404, detail="Unknown registered source")
    try:
        return LEARNING_INTELLIGENCE.appraise_source(source_id, payload.scores, reviewer, payload.rationale)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.put("/learning/preferences")
def set_learning_preferences(payload: LearnerPreferencesBody) -> dict[str, Any]:
    try:
        return LEARNING_INTELLIGENCE.set_preferences(payload.learner_id, payload.specialties, payload.difficulty)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/learning/recommendations/{learner_id}")
def learning_recommendations(learner_id: str, limit: int = 8) -> dict[str, Any]:
    return LEARNING_INTELLIGENCE.recommendations(learner_id, limit)

@router.post("/lottery/draws/{draw_id}/attempt", status_code=201)
def lottery_attempt(draw_id: str, payload: CaseAttemptBody) -> dict[str, Any]:
    try:
        return LEARNING_INTELLIGENCE.submit_case_attempt(payload.learner_id, draw_id,
                                                          payload.response, payload.confidence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

# --------------------------------------------------------------------------- #
# Cross-workspace operational overview
# --------------------------------------------------------------------------- #

@router.get("/overview")
def next_increments_overview() -> dict[str, Any]:
    """One read for the operations screen: lineage, rights, folders, lottery, engines."""
    lottery = CASE_LOTTERY.summary()
    return {
        "version": "5.2.0",
        "learning_intelligence": "personalized_practice_and_source_reliability_appraisal",
        "labels": LABELS.summary(),
        "source_registry": SOURCE_REGISTRY.summary(),
        "local_sources": LOCAL_SOURCES.summary(),
        "lottery": lottery,
        "engines": {"bindings": EngineIntegration.catalogue()["binding_count"],
                    "all_integrated": EngineIntegration.catalogue()["all_engines_integrated"]},
        "pearls": PEARLS_FACTORY.summary(),
        "labels_available": list(CONTENT_LABELS),
        "pearl_templates": list(TEMPLATES),
        "integrity_notes": [
            "Content labels are independent of rights, review and publication status.",
            "Derived content without lineage is an integrity fault and is counted.",
            "The lottery never draws an unreviewed or rights-restricted case.",
        ],
    }
