"""API for the shared, cross-workspace HSPTL tag index."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..hsptl_core.tagging import TagRepository
from ..runtime import STORE

router = APIRouter(prefix="/api/tagging", tags=["shared clinical tags"])
TAGS = TagRepository(STORE)


class TaggedContentCreate(BaseModel):
    content_type: Literal["case", "case_report", "debrief", "pearl", "lecture", "topic", "viva", "osce", "exam_question", "simulation", "harvested_case", "synthea_note"]
    content_id: str = Field(min_length=1, max_length=180)
    title: str = Field(min_length=1, max_length=240)
    workspace: Literal["clinic", "rounds", "lab", "exam", "on_call", "conference", "data_tools"]
    summary: str = Field(default="", max_length=1200)
    source_status: Literal["approved", "reviewed", "unreviewed", "synthetic", "draft"] = "unreviewed"
    content_url: str = Field(default="", max_length=1600)
    tags: list[str] = Field(min_length=1, max_length=12)
    assigned_by: str = Field(default="learner", max_length=80)


class TagEventCreate(BaseModel):
    action: Literal["opened", "attempted", "completed", "reviewed", "revisited"]
    score: float | None = Field(default=None, ge=0, le=1000)
    max_score: float | None = Field(default=None, gt=0, le=1000)
    confidence: Literal["low", "medium", "high", ""] = ""


@router.get("/catalogue")
def tag_catalogue(facet: str | None = None) -> dict:
    try:
        tags = TAGS.catalogue(facet)
    except Exception as exc:
        raise HTTPException(500, "Could not load the tag catalogue") from exc
    grouped: dict[str, list[dict]] = {}
    for item in tags:
        grouped.setdefault(item["facet"], []).append(item)
    return {"count": len(tags), "facets": grouped, "tags": tags}


@router.post("/content")
def register_tagged_content(payload: TaggedContentCreate) -> dict:
    try:
        return TAGS.register_content(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/content")
def find_tagged_content(
    tag_id: list[str] = Query(default=[]),
    workspace: str | None = None,
    q: str = "",
    limit: int = Query(default=100, ge=1, le=250),
) -> dict:
    try:
        items = TAGS.search_content(tag_ids=tag_id, workspace=workspace, query=q, limit=limit)
    except Exception as exc:
        raise HTTPException(500, "Could not search tagged content") from exc
    return {"count": len(items), "items": items}


@router.post("/content/{item_id}/events")
def record_tag_event(item_id: str, payload: TagEventCreate) -> dict:
    try:
        return TAGS.record_event(item_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(404, "Tagged content item not found") from exc


@router.get("/analytics")
def tag_analytics() -> dict:
    try:
        items = TAGS.analytics()
    except Exception as exc:
        raise HTTPException(500, "Could not calculate tag analytics") from exc
    return {"items": items, "note": "Activity summaries are formative signals, not validated measures of clinical competence."}
