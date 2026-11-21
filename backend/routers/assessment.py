"""Phase 2 assessment routes. Shapes match ExamCentrePage.tsx and OSCEPage.tsx.

Ordering matters: literal GET paths (/exams/datasets, /exams/questions) and
literal POST paths (/exams/build, /exams/import, /osce/import) are registered
BEFORE the parameterized GET /exams/{exam_id}, so FastAPI does not capture
"questions"/"datasets" as an {exam_id}.

Unreviewed questions cannot enter an exam and cannot be attempted in the OSCE;
that is a governance rule, not a bug.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..hsptl_core.content import DATASET_CATALOGUE
from ..hsptl_core.exams import GovernanceError, NotFoundError, normalise_answer
from ..hsptl_core.source_refs import SourceKind, SourceRef
from ..runtime import EPISODES, EXAMS

router = APIRouter(prefix="/api", tags=["assessment"])


class BuildExam(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    specialty: str = "Mixed"
    difficulty: str = "Any"
    question_count: int = Field(default=20, ge=1, le=200)
    duration_minutes: int = Field(default=30, ge=0, le=600)
    kinds: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    reviewed: bool
    reviewer: str = Field(default="local learner", max_length=120)


class SubmitAttempt(BaseModel):
    responses: dict[str, str] = Field(default_factory=dict)
    duration_seconds: int = Field(default=0, ge=0, le=86_400)


class AuthorQuestion(BaseModel):
    kind: str = "MCQ"
    specialty: str = "General medicine"
    difficulty: str = "Intermediate"
    question: str = Field(min_length=5, max_length=4000)
    options: list[str] = Field(default_factory=list, max_length=8)
    answer: str = Field(min_length=1, max_length=500)
    explanation: str = Field(default="", max_length=4000)
    source_title: str = Field(default="Unspecified source", max_length=300)
    source_url: str = Field(default="", max_length=600)
    licence: str = Field(default="User-provided; verify permissions", max_length=200)
    media_url: str = Field(default="", max_length=600)
    tags: list[str] = Field(default_factory=list)


class OsceAttempt(BaseModel):
    question_id: str = Field(min_length=1, max_length=80)
    response: str = Field(min_length=1, max_length=2000)
    duration_seconds: int = Field(default=0, ge=0, le=3600)


# --- datasets / bank / builder (literal paths, registered FIRST) -------------
@router.get("/exams/datasets")
def datasets() -> list[dict[str, Any]]:
    return [{"id": d["name"], "name": d["name"], "description": d["purpose"], "url": d["url"],
             "licence": d["access"], "format": "JSON / JSONL / CSV / TSV",
             "priority": d["priority"]} for d in DATASET_CATALOGUE]


@router.get("/exams/questions")
def questions(kind: str | None = None, specialty: str | None = None,
              limit: int = 100, offset: int = 0) -> dict[str, Any]:
    return EXAMS.questions(kind=kind, specialty=specialty, limit=limit, offset=offset)


@router.post("/exams/questions")
def author_question(payload: AuthorQuestion) -> dict[str, Any]:
    try:
        created = EXAMS.add_question(payload.model_dump(), reviewed=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    EPISODES.attach_sources("question", created["id"], [SourceRef(
        kind=SourceKind.EXTERNAL_LINK if payload.source_url else SourceKind.LEARNER_AUTHORED,
        locator=payload.source_url or "learner:authored", title=payload.source_title,
        citation=payload.source_title, license=payload.licence)])
    return created


@router.post("/exams/build")
def build_exam(payload: BuildExam) -> dict[str, Any]:
    try:
        return EXAMS.build_exam(**payload.model_dump())
    except GovernanceError as exc:
        raise HTTPException(409, str(exc)) from exc


async def _import(file: UploadFile) -> dict[str, int]:
    try:
        content = await file.read(9 * 1024 * 1024)
        return EXAMS.import_questions(content, file.filename or "import.json")
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await file.close()


@router.post("/exams/import")
async def import_exam_questions(file: UploadFile = File(...)) -> dict[str, int]:
    return await _import(file)


@router.post("/osce/import")
async def import_osce(file: UploadFile = File(...)) -> dict[str, int]:
    return await _import(file)


@router.get("/exams")
def exams() -> list[dict[str, Any]]:
    return EXAMS.exams()


@router.post("/questions/{question_id}/review")
def review_question(question_id: str, payload: ReviewRequest) -> dict[str, bool]:
    if not EXAMS.set_reviewed(question_id, payload.reviewed, payload.reviewer):
        raise HTTPException(404, "Question not found")
    return {"saved": True, "reviewed": payload.reviewed}


# --- parameterized exam paths (registered AFTER the literal routes) ----------
@router.get("/exams/{exam_id}")
def exam_detail(exam_id: str) -> dict[str, Any]:
    """Wrapped shape {exam, questions} expected by ExamCentrePage.tsx."""
    try:
        data = EXAMS.exam(exam_id)
    except NotFoundError as exc:
        raise HTTPException(404, "Examination not found") from exc
    header = {k: data[k] for k in ("id", "title", "specialty", "difficulty",
                                   "duration_minutes", "question_count")}
    return {"exam": header, "questions": data["questions"], "blueprint": data["blueprint"]}


@router.post("/exams/{exam_id}/attempts")
def start_attempt(exam_id: str) -> dict[str, Any]:
    try:
        episode = EPISODES.start_or_resume(source_type="exam_attempt", source_id=exam_id,
                                           provenance_status="curated")
        return EXAMS.start_attempt(exam_id, episode_id=episode["episode_id"])
    except NotFoundError as exc:
        raise HTTPException(404, "Examination not found") from exc


def _record(attempt_id: str, report: dict[str, Any]) -> None:
    with EXAMS.transaction() as conn:
        row = conn.execute("SELECT episode_id FROM exam_attempts WHERE attempt_id=?",
                           (attempt_id,)).fetchone()
    if row and row["episode_id"]:
        EPISODES.add_artifact(row["episode_id"], "exam_response", report,
                              authored_by="system", verification_status="unverified")
        EPISODES.set_status(row["episode_id"], "completed")


@router.post("/exams/{exam_id}/submit")
def submit_latest(exam_id: str, payload: SubmitAttempt) -> dict[str, Any]:
    """Convenience path used by ExamCentrePage: reuses an open attempt or opens one."""
    attempt_id = EXAMS.open_attempt_for(exam_id)
    if attempt_id is None:
        try:
            episode = EPISODES.start_or_resume(source_type="exam_attempt", source_id=exam_id,
                                               provenance_status="curated")
            attempt_id = EXAMS.start_attempt(exam_id, episode_id=episode["episode_id"])["attempt_id"]
        except NotFoundError as exc:
            raise HTTPException(404, "Examination not found") from exc
    report = EXAMS.submit_attempt(attempt_id, payload.responses, payload.duration_seconds)
    _record(attempt_id, report)
    return report


@router.post("/exam-attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, payload: SubmitAttempt) -> dict[str, Any]:
    try:
        report = EXAMS.submit_attempt(attempt_id, payload.responses, payload.duration_seconds)
    except NotFoundError as exc:
        raise HTTPException(404, "Attempt not found") from exc
    _record(attempt_id, report)
    return report


@router.get("/exam-attempts/{attempt_id}")
def attempt_report(attempt_id: str) -> dict[str, Any]:
    try:
        return EXAMS.attempt_report(attempt_id)
    except (NotFoundError, GovernanceError) as exc:
        raise HTTPException(404, "Attempt report not available") from exc


# --- OSCE ---------------------------------------------------------------------
@router.get("/osce/challenges")
def osce_challenges(kind: str | None = None) -> list[dict[str, Any]]:
    return EXAMS.questions(kind=kind, reviewed=True, limit=500)["questions"]


@router.post("/osce/attempt")
def osce_attempt(payload: OsceAttempt) -> dict[str, Any]:
    with EXAMS.transaction() as conn:
        row = conn.execute(
            "SELECT v.version_id, v.payload_json FROM exam_questions q JOIN exam_question_versions v "
            "ON v.question_id=q.question_id AND v.version=q.current_version "
            "WHERE q.question_id=? AND q.reviewed=1", (payload.question_id,)).fetchone()
    if row is None:
        raise HTTPException(409, "Question is not reviewed; approve source and answer before use")
    question = json.loads(row["payload_json"])
    given = normalise_answer(payload.response)
    accepted = {normalise_answer(question["answer"]),
                *[normalise_answer(a) for a in question.get("aliases", [])]}
    correct = bool(given) and given in accepted
    snapshot = json.dumps({"kind": question.get("kind", ""), "specialty": question.get("specialty", "")},
                          ensure_ascii=False)
    with EXAMS.transaction() as conn:
        conn.execute(
            "INSERT INTO osce_attempts "
            "(attempt_id,question_id,version_id,response,correct,points,duration_seconds,"
            "snapshot_json,submitted_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, payload.question_id, row["version_id"], payload.response,
             int(correct), int(correct), payload.duration_seconds, snapshot,
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return {"question_id": payload.question_id, "response": payload.response, "correct": correct,
            "answer": question["answer"], "explanation": question.get("explanation", ""),
            "source_title": question.get("source_title", ""),
            "source_url": question.get("source_url", ""), "points": int(correct),
            "scope": "Single-station practice; not a validated OSCE."}
