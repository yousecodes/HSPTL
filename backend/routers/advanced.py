"""Phase 4 routes. Every advanced capability is gated and default-off.

`/api/tutor/prompt` returns 403 in the default configuration by design: the
conversational-tutoring requirements are never auto-satisfied. Prompt assembly
that performs no generation already exists today via POST /api/pearls/generate
(tutor_prompt field).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..hsptl_core.advanced import (BranchValidationError, branch_choose, branch_start,
                                     export_bundle, get_tutor, graph_satisfied, import_dry_run)
from ..hsptl_core.policy import PolicyError, feature_report
from ..runtime import EPISODES, EXAMS, STORE

router = APIRouter(prefix="/api", tags=["advanced"])


class BranchGraph(BaseModel):
    reviewer: str = Field(default="", max_length=120)
    review_date: str = Field(default="", max_length=20)
    source_type: str = "curated_case"
    start_node: str = Field(default="", max_length=80)
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class BranchState(BaseModel):
    graph: BranchGraph
    path: list[str] = Field(min_length=1)
    option_id: str = Field(min_length=1, max_length=80)


class TutorRequest(BaseModel):
    case_context: str = Field(min_length=10, max_length=20_000)
    stage_name: str = Field(min_length=2, max_length=80)
    questions: list[str] = Field(default_factory=list, max_length=6)
    answer: str = Field(min_length=1, max_length=8000)
    ratings: dict[str, int] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)


@router.get("/features")
def features() -> list[dict[str, Any]]:
    return feature_report()


@router.get("/features/{key}")
def feature(key: str) -> dict[str, Any]:
    match = next((i for i in feature_report() if i["key"] == key), None)
    if match is None:
        raise HTTPException(404, "Unknown feature")
    return match


@router.post("/branching/start")
def branching_start(payload: BranchGraph) -> dict[str, Any]:
    graph = payload.model_dump()
    try:
        return branch_start(graph, satisfied=graph_satisfied(graph))
    except PolicyError as exc:
        raise HTTPException(403, str(exc)) from exc
    except BranchValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/branching/choose")
def branching_choose(payload: BranchState) -> dict[str, Any]:
    graph = payload.graph.model_dump()
    try:
        return branch_choose(graph, {"path": payload.path}, payload.option_id,
                             satisfied=graph_satisfied(graph))
    except PolicyError as exc:
        raise HTTPException(403, str(exc)) from exc
    except BranchValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/portability/export")
def export_portfolio() -> dict[str, Any]:
    return export_bundle(STORE, EPISODES, EXAMS)


@router.post("/portability/import/preview")
def import_preview(payload: dict[str, Any]) -> dict[str, Any]:
    return import_dry_run(payload)


@router.post("/tutor/prompt")
def tutor_prompt(payload: TutorRequest) -> dict[str, Any]:
    try:
        adapter = get_tutor()
    except PolicyError as exc:
        raise HTTPException(403, str(exc)) from exc
    return adapter.prepare(**payload.model_dump())
