"""Synthetic data factory API.

Reviewer-authenticated operations reuse the existing ``HSPTL_REVIEWER_TOKEN`` /
``HSPTL_REVIEWER_ID`` convention. When they are unset, review endpoints answer
503 rather than silently permitting an unauthenticated approval.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..runtime import SYNTHETIC_FACTORY as FACTORY
from ..hsptl_core.synthetic_data.paths import UnsafePath
from ..hsptl_core.synthetic_data.recipes import LIFECYCLE

router = APIRouter(prefix="/api/synthetic", tags=["synthetic-data"])


def _reviewer(token: str | None) -> str:
    expected = os.environ.get("HSPTL_REVIEWER_TOKEN", "")
    reviewer = os.environ.get("HSPTL_REVIEWER_ID", "").strip()
    if len(expected) < 32 or not reviewer:
        raise HTTPException(503, "Reviewer authentication is not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Valid reviewer credentials are required")
    return reviewer[:160]


def _bad_request(message: str) -> HTTPException:
    return HTTPException(400, message)


# --------------------------------------------------------------------------- #
# Status and settings
# --------------------------------------------------------------------------- #

class SettingsUpdate(BaseModel):
    synthea_jar: str | None = Field(default=None, max_length=1000)
    synthea_version: str | None = Field(default=None, max_length=120)
    synthea_sha256: str | None = Field(default=None, max_length=64)
    java_path: str | None = Field(default=None, max_length=1000)
    module_dir: str | None = Field(default=None, max_length=1000)
    config_file: str | None = Field(default=None, max_length=1000)
    validator_jar: str | None = Field(default=None, max_length=1000)
    validator_sha256: str | None = Field(default=None, max_length=64)
    validator_version: str | None = Field(default=None, max_length=120)
    package_cache: str | None = Field(default=None, max_length=1000)
    max_heap_mb: int | None = Field(default=None, ge=256, le=4096)
    min_free_disk_mb: int | None = Field(default=None, ge=256, le=51200)
    strict_fhir_required: bool | None = None


@router.get("/status")
def status() -> dict[str, Any]:
    return FACTORY.status()


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    settings = FACTORY.settings().to_dict()
    # The checksum values are not secrets, but echoing full paths is unnecessary.
    settings.pop("package_cache", None)
    return settings


@router.put("/settings")
def put_settings(payload: SettingsUpdate) -> dict[str, Any]:
    changes = {key: value for key, value in payload.model_dump(exclude_none=True).items()}
    for path_field in ("synthea_jar", "module_dir", "config_file", "validator_jar"):
        if path_field in changes and changes[path_field]:
            candidate = Path(changes[path_field]).expanduser()
            if not candidate.is_absolute():
                raise _bad_request(f"{path_field} must be an absolute local path")
    for hash_field in ("synthea_sha256", "validator_sha256"):
        if hash_field in changes and changes[hash_field]:
            value = str(changes[hash_field]).strip().casefold()
            if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise _bad_request(f"{hash_field} must be a 64-character hex SHA-256")
            changes[hash_field] = value
    settings = FACTORY.update_settings(changes)
    return settings.to_dict()


# --------------------------------------------------------------------------- #
# Recipes
# --------------------------------------------------------------------------- #

class RecipeBody(BaseModel):
    body: dict[str, Any]


class RecipeTransition(BaseModel):
    status: str
    rationale: str = Field(default="", max_length=2000)


@router.get("/recipes")
def list_recipes() -> dict[str, Any]:
    return {"items": FACTORY.recipes.list(), "lifecycle": list(LIFECYCLE)}


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: str, version: str | None = None) -> dict[str, Any]:
    recipe = FACTORY.recipes.get(recipe_id, version)
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    return recipe


@router.post("/recipes", status_code=201)
def create_recipe(payload: RecipeBody, x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    try:
        recipe = FACTORY.recipes.create(payload.body, owner=reviewer)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    FACTORY._emit("platform.synthetic_data.recipe_created", {
        "recipe_id": recipe["recipe_id"], "version": recipe["version"],
        "status": recipe["status"], "owner": reviewer,
    })
    return recipe


@router.post("/recipes/{recipe_id}/transition")
def transition_recipe(recipe_id: str, payload: RecipeTransition, version: str | None = None,
                      x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    if payload.status not in LIFECYCLE:
        raise _bad_request(f"Unknown recipe status: {payload.status}")
    try:
        recipe = FACTORY.recipes.transition(recipe_id, version or "", payload.status,
                                            reviewer=reviewer)
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    if payload.status == "active":
        FACTORY._emit("platform.synthetic_data.recipe_activated", {
            "recipe_id": recipe["recipe_id"], "version": recipe["version"],
            "content_digest": recipe["content_digest"], "reviewer": reviewer,
            "reviewed_at": recipe["reviewed_at"],
        })
    return recipe


# --------------------------------------------------------------------------- #
# Preflight and jobs
# --------------------------------------------------------------------------- #

class PreflightRequest(BaseModel):
    recipe_id: str = Field(min_length=1, max_length=120)
    population: int = Field(ge=1, le=5000)
    fhir: bool = True
    csv: bool = True
    version: str | None = Field(default=None, max_length=40)


@router.post("/preflight")
def preflight_preview(payload: PreflightRequest) -> dict[str, Any]:
    try:
        return FACTORY.preflight_preview(payload.recipe_id, population=payload.population,
                                         fhir=payload.fhir, csv=payload.csv,
                                         version=payload.version)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


class JobRequest(BaseModel):
    recipe_id: str = Field(min_length=1, max_length=120)
    population: int = Field(ge=1, le=5000)
    accepted_target: int = Field(default=0, ge=0, le=5000)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    fhir: bool = True
    csv: bool = True
    years_of_history: int | None = Field(default=None, ge=0, le=120)
    version: str | None = Field(default=None, max_length=40)


@router.post("/jobs", status_code=202)
def queue_job(payload: JobRequest) -> dict[str, Any]:
    try:
        result = FACTORY.queue_job(
            recipe_id=payload.recipe_id, population=payload.population,
            accepted_target=payload.accepted_target, seed=payload.seed,
            fhir=payload.fhir, csv=payload.csv,
            years_of_history=payload.years_of_history, version=payload.version,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return result


@router.get("/jobs")
def list_jobs(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return {"items": FACTORY.store.list_runs(limit=limit, offset=offset),
            "counts": FACTORY.status()["runs"]}


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    detail = FACTORY.job_detail(job_id)
    if detail is None:
        raise HTTPException(404, "Job not found")
    return detail


@router.post("/jobs/{job_id}/run")
def run_job_now(job_id: str) -> dict[str, Any]:
    """Execute a queued job synchronously. Useful on machines without a worker."""
    from ..runtime import JOBS
    try:
        ran = JOBS.run_once(job_id)
    except Exception as exc:  # noqa: BLE001 - surface a controlled error to the UI
        raise HTTPException(500, f"Job execution failed: {exc}") from exc
    return {"ran": ran, "job": FACTORY.job_detail(job_id)}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    result = FACTORY.cancel_job(job_id)
    if not result["cancelled"]:
        raise HTTPException(404, "Job not found")
    return result


# --------------------------------------------------------------------------- #
# Datasets
# --------------------------------------------------------------------------- #

@router.get("/datasets")
def list_datasets(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return {"items": FACTORY.store.list_datasets(limit=limit, offset=offset),
            "counts": FACTORY.store.dataset_counts()}


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str) -> dict[str, Any]:
    try:
        detail = FACTORY.dataset_detail(dataset_id)
    except UnsafePath as exc:
        raise _bad_request(str(exc)) from exc
    if detail is None:
        raise HTTPException(404, "Dataset not found")
    return detail


@router.get("/datasets/{dataset_id}/quality")
def dataset_quality(dataset_id: str) -> dict[str, Any]:
    report = FACTORY.quality_report(dataset_id)
    if report is None:
        raise HTTPException(404, "Dataset not found")
    return report


@router.get("/datasets/{dataset_id}/manifest")
def dataset_manifest(dataset_id: str) -> dict[str, Any]:
    from ..hsptl_core.synthetic_data.manifest import verify_manifest
    dataset = FACTORY.store.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    path = FACTORY.storage_root / "datasets" / dataset_id / "manifests" / "dataset-manifest.json"
    if not path.is_file():
        raise HTTPException(404, "Manifest not found")
    import json
    verified, detail = verify_manifest(path)
    return {"dataset_id": dataset_id, "verified": verified, "verification": detail,
            "manifest": json.loads(path.read_text(encoding="utf-8"))}


# --------------------------------------------------------------------------- #
# Quarantine review
# --------------------------------------------------------------------------- #

@router.get("/quarantine")
def list_quarantine(dataset_id: str = "", status: str = "", severity: str = "",
                    rule_id: str = "", limit: int = 100, offset: int = 0) -> dict[str, Any]:
    items = FACTORY.store.list_quarantine(dataset_id=dataset_id, status=status,
                                          severity=severity, rule_id=rule_id,
                                          limit=limit, offset=offset)
    return {"items": items, "count": len(items)}


class QuarantineReview(BaseModel):
    decision: str
    rationale: str = Field(default="", max_length=2000)


@router.post("/quarantine/{item_id}/review")
def review_quarantine(item_id: str, payload: QuarantineReview,
                      x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    if payload.decision not in {"accepted", "rejected", "remediated", "open"}:
        raise _bad_request("Decision must be accepted, rejected, remediated or open")
    item = FACTORY.store.get_quarantine_item(item_id)
    if item is None:
        raise HTTPException(404, "Quarantine item not found")
    FACTORY.store.review_quarantine_item(item_id, reviewer=reviewer,
                                         decision=payload.decision,
                                         rationale=payload.rationale)
    FACTORY.store.record_review(item_kind="quarantine", item_id=item_id,
                                dataset_id=item["dataset_id"], reviewer=reviewer,
                                decision=payload.decision, rationale=payload.rationale)
    FACTORY._emit("platform.synthetic_data.review_recorded", {
        "item_id": item_id, "dataset_id": item["dataset_id"],
        "reviewer_id": reviewer, "decision": payload.decision,
        "rationale": payload.rationale[:500],
    })
    return FACTORY.store.get_quarantine_item(item_id) or {}


@router.get("/quarantine/{item_id}")
def get_quarantine(item_id: str) -> dict[str, Any]:
    detail = FACTORY.quarantine_detail(item_id)
    if detail is None:
        raise HTTPException(404, "Quarantine item not found")
    return detail


# --------------------------------------------------------------------------- #
# Schedules
# --------------------------------------------------------------------------- #

class ScheduleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    recipe_id: str = Field(min_length=1, max_length=120)
    population: int = Field(ge=1, le=5000)
    accepted_target: int = Field(default=0, ge=0, le=5000)
    frequency: str = "weekly"
    enabled: bool = False
    version: str | None = Field(default=None, max_length=40)


@router.get("/schedules")
def list_schedules() -> dict[str, Any]:
    return {"items": FACTORY.store.list_schedules()}


@router.post("/schedules", status_code=201)
def create_schedule(payload: ScheduleRequest) -> dict[str, Any]:
    try:
        return FACTORY.create_schedule(
            name=payload.name, recipe_id=payload.recipe_id, population=payload.population,
            accepted_target=payload.accepted_target, frequency=payload.frequency,
            enabled=payload.enabled, version=payload.version,
        )
    except ValueError as exc:
        raise _bad_request(str(exc)) from exc


class ScheduleUpdate(BaseModel):
    enabled: bool | None = None
    frequency: str | None = None
    population: int | None = Field(default=None, ge=1, le=5000)


@router.patch("/schedules/{schedule_id}")
def update_schedule(schedule_id: str, payload: ScheduleUpdate) -> dict[str, Any]:
    changes = {key: value for key, value in payload.model_dump(exclude_none=True).items()}
    if "frequency" in changes and changes["frequency"] not in {"daily", "weekly", "monthly"}:
        raise _bad_request("Frequency must be daily, weekly or monthly")
    record = FACTORY.store.update_schedule(schedule_id, **changes)
    if record is None:
        raise HTTPException(404, "Schedule not found")
    return record


@router.post("/schedules/run-due")
def run_due_schedules() -> dict[str, Any]:
    return {"queued": FACTORY.run_due_schedules()}


@router.get("/events")
def factory_events(limit: int = 50) -> dict[str, Any]:
    if FACTORY.kernel is None:
        return {"items": []}
    events = FACTORY.kernel.events(limit=limit)
    return {"items": [event for event in events
                      if str(event.get("event_type", "")).startswith("platform.synthetic_data.")]}
