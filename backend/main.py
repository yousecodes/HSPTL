from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import uuid
from contextlib import asynccontextmanager, closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import requests
from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .hsptl_core.capabilities import capability_report
from .hsptl_core.case_engine import CaseRepository
from .hsptl_core.clinical_narrative import build_encounter_narrative
from .hsptl_core.config import (
    APP_NAME,
    APP_VERSION,
    discover_dataset_dirs,
    ensure_user_dirs,
    load_settings,
    resolve_dev_port,
    save_settings,
)
from .hsptl_core.data import DatasetCatalog, load_catalog, patient_summaries, measurements_for_case
from .hsptl_core.integrations import (
    article_url,
    commons_search_images,
    europe_pmc_fulltext_xml,
    europe_pmc_search,
    is_open_access,
    parse_jats_article,
)
from .hsptl_core.learning import QUESTION_PACKS
from .hsptl_core.note_engine import (
    NOTE_TYPES,
    article_license_allows_excerpt,
    article_source_excerpts,
    find_curated_pack,
    generate_study_note,
    note_to_markdown,
    pdf_source_excerpts,
    build_external_tutor_prompt,
)
from .hsptl_core.puzzle_engine import select_daily_puzzle, load_approved_puzzles
from .hsptl_core.puzzles import PUZZLES, answer_matches, apply_guess
from .hsptl_core.reporting import build_case_report, report_to_markdown
from .hsptl_core.store import StudyStore
from .hsptl_core.simulation import PEARLS_DEBRIEF, clean_debrief_payload, debrief_completion

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
from .runtime import PATHS, SETTINGS, STORE, CASE_STORE, EPISODES, EXAMS, SEARCH, REVIEWS, CACHE, JOBS
CATALOG: DatasetCatalog | None = None
CATALOG_DIRS: tuple[str, ...] = ()

logger = logging.getLogger("hsptl")
if not logger.handlers:
    PATHS["logs"].mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(PATHS["logs"] / "hsptl_api.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _init_api_tables() -> None:
    with STORE.transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hsptl_puzzle_runs (
                id TEXT PRIMARY KEY,
                puzzle_id TEXT NOT NULL,
                day_key TEXT NOT NULL,
                is_daily INTEGER NOT NULL DEFAULT 0,
                guesses_json TEXT NOT NULL DEFAULT '[]',
                revealed INTEGER NOT NULL DEFAULT 1,
                finished INTEGER NOT NULL DEFAULT 0,
                solved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hsptl_puzzle_day ON hsptl_puzzle_runs(day_key, is_daily)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _init_api_tables()
    from .runtime import JOBS as _JOBS, SYNTHETIC_FACTORY as _FACTORY, CASE_LOTTERY as _CASE_LOTTERY
    # The lottery is the single source of truth for the Clinic and Ward daily case.
    # Seed the already-published HSPTL-authored teaching bank without duplicating
    # cases or overwriting locally maintained lottery records.
    lottery_seed = _CASE_LOTTERY.seed_curated_cases()
    logger.info("Daily case lottery curriculum seed: %s new, %s already present",
                lottery_seed["created"], lottery_seed["already_present"])
    from .hsptl_core.jobs import start_worker_thread, stop_worker_thread
    from .hsptl_core.synthetic_data.scheduler import SyntheticScheduler
    worker = start_worker_thread(_JOBS)
    scheduler = SyntheticScheduler(_FACTORY)
    scheduler.start()
    from .routers import ucks as ucks_routes
    if os.environ.get("HSPTL_DISABLE_EXTERNAL_AUTOMATION") != "1":
        ucks_routes.EXTERNAL_AUTOMATION.start()
    try:
        try:
            startup_content = content_factory_routes.ensure_startup_content()
            logger.info(
                "Starter learning content ready: %s topics, %s outputs (%s new, %s already current)",
                startup_content["unit_count"], startup_content["draft_count"],
                startup_content["created_count"], startup_content["reused_count"],
            )
        except Exception:
            # Content preparation is recoverable through the Update content button;
            # do not prevent the local learning app from starting.
            logger.exception("Automatic starter content preparation failed; use Update content to retry")
        yield
    finally:
        if os.environ.get("HSPTL_DISABLE_EXTERNAL_AUTOMATION") != "1":
            ucks_routes.EXTERNAL_AUTOMATION.stop()
        scheduler.stop()
        stop_worker_thread(_JOBS, timeout=2)


app = FastAPI(
    title="HSPTL API",
    version=APP_VERSION,
    description="Local-first clinical learning API. Educational use only.",
    lifespan=lifespan,
)


@app.exception_handler(sqlite3.Error)
async def sqlite_error_handler(request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.exception("Unhandled SQLite error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Database operation failed", "code": "database_error"},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred", "code": "internal_error"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://127.0.0.1:{resolve_dev_port()}",
        f"http://localhost:{resolve_dev_port()}",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-HSPTL-Reviewer-Token", "X-HSPTL-Session"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; connect-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


from .routers import learning as learning_routes, assessment as assessment_routes, advanced as advanced_routes, data_tools as data_tool_routes, tagging as tagging_routes, ucks as ucks_routes, generation_distribution as generation_distribution_routes, deterministic_intelligence as deterministic_intelligence_routes, hsp_tl40 as hsp_tl40_routes, content_factory as content_factory_routes, synthetic_data as synthetic_data_routes, next_increments as next_increments_routes, published_learning as published_learning_routes
app.include_router(learning_routes.router)
app.include_router(assessment_routes.router)
app.include_router(advanced_routes.router)
app.include_router(data_tool_routes.router)
app.include_router(tagging_routes.router)
app.include_router(ucks_routes.router)
app.include_router(generation_distribution_routes.router)
app.include_router(deterministic_intelligence_routes.router)
app.include_router(hsp_tl40_routes.router)
app.include_router(content_factory_routes.router)
app.include_router(synthetic_data_routes.router)
app.include_router(next_increments_routes.router)
app.include_router(published_learning_routes.router)


class DatasetConnectRequest(BaseModel):
    path: str = Field(min_length=3, max_length=1000)


class GuessRequest(BaseModel):
    run_id: str = Field(min_length=8, max_length=80)
    guess: str = Field(min_length=1, max_length=120)


class StartPuzzleRequest(BaseModel):
    puzzle_id: str | None = Field(default=None, max_length=120)


class NoteRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=140)
    note_type: str = "Condition"
    level: str = "Clinical years"
    jurisdiction: str = "Egypt"
    use_local_pdfs: bool = True
    use_open_access: bool = False
    pmcid: str | None = Field(default=None, max_length=20)


class SaveNoteRequest(BaseModel):
    note: dict[str, Any]


class CardRequest(BaseModel):
    front: str = Field(min_length=3, max_length=1000)
    back: str = Field(min_length=3, max_length=3000)
    source: str = Field(default="", max_length=1000)
    tags: str = Field(default="", max_length=300)


class GradeRequest(BaseModel):
    grade: str = Field(pattern="^(Again|Hard|Good|Easy)$")


class SpecialtySearchRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=140)


class BackgroundJobRequest(BaseModel):
    kind: str = Field(min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


class LearningPearlRequest(BaseModel):
    focus: str = Field(min_length=3, max_length=100)
    reflection: str = Field(min_length=10, max_length=2000)


class ClinicalDebriefRequest(BaseModel):
    responses: dict[str, str] = Field(default_factory=dict)


class FHIRImportRequest(BaseModel):
    path: str = Field(min_length=3, max_length=1000)
    batch_size: int = Field(default=250, ge=25, le=1000)


class ClinicalLearningAttemptRequest(BaseModel):
    patient_key: str = Field(min_length=16, max_length=128)
    encounter_key: str = Field(min_length=16, max_length=128)
    case_code: str = Field(min_length=4, max_length=40)
    problem_representation: str = Field(default="", max_length=3000)
    differentials: list[str] = Field(default_factory=list, max_length=8)
    evidence_for: str = Field(default="", max_length=3000)
    evidence_against: str = Field(default="", max_length=3000)
    investigation_plan: str = Field(default="", max_length=3000)
    working_diagnosis: str = Field(default="", max_length=500)
    management_plan: str = Field(default="", max_length=3000)
    safety_net: str = Field(default="", max_length=2000)
    communication_plan: str = Field(default="", max_length=2000)
    stage_completed: int = Field(default=1, ge=1, le=5)
    confidence: int = Field(ge=1, le=5)
    history_plan: list[str] = Field(default_factory=list, max_length=20)
    examination_plan: list[str] = Field(default_factory=list, max_length=20)
    investigation_selection: list[str] = Field(default_factory=list, max_length=20)
    specialty_pathway: str = Field(default="Emergency", min_length=2, max_length=60)
    cited_fact_keys: list[str] = Field(default_factory=list, max_length=40)
    prioritisation_rationale: str = Field(default="", max_length=2000)


class ExternalServiceError(RuntimeError):
    """A remote service failed while assembling optional learning content."""


def get_catalog(force: bool = False) -> DatasetCatalog | None:
    global CATALOG, CATALOG_DIRS, SETTINGS
    dirs = discover_dataset_dirs(SETTINGS)
    key = tuple(str(p.resolve()) for p in dirs)
    if not dirs:
        CATALOG = None
        CATALOG_DIRS = ()
        return None
    if force or CATALOG is None or key != CATALOG_DIRS:
        CATALOG = load_catalog(dirs)
        CATALOG_DIRS = key
    return CATALOG


def _resolve_allowed_data_directory(path: str) -> Path:
    try:
        candidate = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail="The selected folder does not exist") from exc
    if not candidate.is_dir():
        raise HTTPException(status_code=400, detail="The selected path must be a directory")

    allowed_dirs = [PATHS["imports"], *discover_dataset_dirs(SETTINGS)]
    for allowed_dir in allowed_dirs:
        try:
            candidate.relative_to(allowed_dir.resolve(strict=True))
            return candidate
        except (OSError, RuntimeError, ValueError):
            continue
    raise HTTPException(status_code=400, detail="The selected folder is outside approved data directories")


def _pool() -> list[dict[str, Any]]:
    combined = [*PUZZLES, *load_approved_puzzles(STORE)]
    unique: dict[str, dict[str, Any]] = {}
    for puzzle in combined:
        if isinstance(puzzle, dict) and puzzle.get("id") and puzzle.get("answer") and puzzle.get("clues"):
            unique.setdefault(str(puzzle["id"]), puzzle)
    return list(unique.values())


def _puzzle_by_id(puzzle_id: str) -> dict[str, Any] | None:
    return next((p for p in _pool() if str(p.get("id")) == puzzle_id), None)


def _normalised_puzzle_run(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "puzzle_id": str(row["puzzle_id"]),
        "day_key": str(row["day_key"]),
        "is_daily": bool(row["is_daily"]),
        "guesses": json.loads(row["guesses_json"] or "[]"),
        "revealed": int(row["revealed"]),
        "finished": bool(row["finished"]),
        "solved": bool(row["solved"]),
    }


def _case_meta(puzzle: dict[str, Any]) -> dict[str, str | None]:
    clues = puzzle.get("clues") or []
    first = str(clues[0]) if clues else ""
    age_match = re.search(r"\b(\d{1,3})[- ]year[- ]old\b", first, flags=re.I)
    gender_match = re.search(r"\b(man|woman|male|female|boy|girl|person)\b", first, flags=re.I)
    return {
        "age": age_match.group(1) if age_match else None,
        "gender": gender_match.group(1).title() if gender_match else None,
        "chief_complaint": first[:220] if first else "Not stated",
    }


def _safe_puzzle_payload(puzzle: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    clues = [str(x) for x in puzzle.get("clues", [])]
    revealed = min(max(1, run["revealed"]), max(1, len(clues)))
    payload: dict[str, Any] = {
        "run_id": run["id"],
        "id": puzzle["id"],
        "title": str(puzzle.get("title") or puzzle.get("question") or "Clinical case"),
        "specialty": str(puzzle.get("specialty") or "General medicine"),
        "difficulty": str(puzzle.get("difficulty") or "Intermediate"),
        "question": str(puzzle.get("question") or "What is the most likely diagnosis?"),
        "case_type": str(puzzle.get("source_type") or "Curated educational vignette"),
        "case_meta": _case_meta(puzzle),
        "clues": clues[:revealed],
        "clue_count": len(clues),
        "revealed": revealed,
        "guesses": run["guesses"],
        "guess_count": len(run["guesses"]),
        "max_guesses": min(6, max(1, len(clues))),
        "finished": run["finished"],
        "solved": run["solved"],
        "source_title": str(puzzle.get("source_title") or "HSPTL curated educational case"),
        "source_url": str(puzzle.get("source_url") or ""),
    }
    if run["finished"]:
        payload["answer"] = str(puzzle.get("answer") or "Not available")
        payload["explanation"] = str(puzzle.get("explanation") or "No explanation was supplied.")
        payload["takeaways"] = [str(x) for x in puzzle.get("takeaways", [])[:8]]
        payload["all_clues"] = clues
    return payload


def _get_run(run_id: str) -> dict[str, Any] | None:
    with STORE.transaction() as conn:
        row = conn.execute("SELECT * FROM hsptl_puzzle_runs WHERE id=?", (run_id,)).fetchone()
    return _normalised_puzzle_run(row) if row else None


def _save_run(run: dict[str, Any]) -> None:
    with STORE.transaction() as conn:
        conn.execute("""
            UPDATE hsptl_puzzle_runs
            SET guesses_json=?, revealed=?, finished=?, solved=?, updated_at=?
            WHERE id=?
        """, (
            json.dumps(run["guesses"], ensure_ascii=False),
            int(run["revealed"]), int(run["finished"]), int(run["solved"]),
            datetime.now(timezone.utc).isoformat(), run["id"],
        ))


def _new_run(puzzle_id: str, daily: bool = False) -> dict[str, Any]:
    puzzle = _puzzle_by_id(puzzle_id)
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    run = {
        "id": str(uuid.uuid4()), "puzzle_id": puzzle_id,
        "day_key": date.today().isoformat(), "is_daily": daily,
        "guesses": [], "revealed": 1, "finished": False, "solved": False,
    }
    now = datetime.now(timezone.utc).isoformat()
    with STORE.transaction() as conn:
        conn.execute("""
            INSERT INTO hsptl_puzzle_runs
            (id,puzzle_id,day_key,is_daily,guesses_json,revealed,finished,solved,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            run["id"], run["puzzle_id"], run["day_key"], int(run["is_daily"]),
            "[]", 1, 0, 0, now, now,
        ))
    return run


def _daily_run() -> dict[str, Any]:
    today = date.today().isoformat()
    with STORE.transaction() as conn:
        row = conn.execute(
            "SELECT * FROM hsptl_puzzle_runs WHERE day_key=? AND is_daily=1 ORDER BY created_at DESC LIMIT 1",
            (today,),
        ).fetchone()
    if row:
        return _normalised_puzzle_run(row)
    pool = _pool()
    if not pool:
        raise HTTPException(status_code=503, detail="No clinical puzzles are available")
    with STORE.transaction() as conn:
        history_rows = conn.execute(
            "SELECT puzzle_id, day_key, is_daily FROM hsptl_puzzle_runs WHERE day_key>=? ORDER BY created_at DESC LIMIT 100",
            ((date.today() - timedelta(days=30)).isoformat(),),
        ).fetchall()
    history = [{"body": json.dumps({"date": r["day_key"], "puzzle_id": r["puzzle_id"]})} for r in history_rows]
    index = select_daily_puzzle(pool, today, history)
    return _new_run(str(pool[index]["id"]), daily=True)


def _specialty_groups() -> list[dict[str, Any]]:
    """Return the broad service catalogue enriched with installed question packs."""
    from .hsptl_core.clinical_catalogues import specialty_catalogue

    curated_pack_map: dict[str, list[str]] = {
        "cardiology": ["heart_failure", "hypertension"],
        "respiratory-medicine": ["asthma", "copd", "pneumonia"],
        "endocrinology-diabetes": ["type_2_diabetes"],
        "nephrology": ["chronic_kidney_disease"],
        "haematology": ["iron_deficiency_anaemia"],
        "dentistry-oral-health": ["oral_health"],
        "paediatrics": ["otitis_media"],
        "infectious-diseases": ["sore_throat", "pneumonia", "otitis_media"],
        "general-medicine": ["record_literacy"],
    }
    output: list[dict[str, Any]] = []
    for group in specialty_catalogue():
        topics = list(group["topics"])
        for pack_id in curated_pack_map.get(group["slug"], []):
            pack = QUESTION_PACKS.get(pack_id)
            if pack:
                topics.insert(0, {"id": pack_id, **pack})
        for topic in topics:
            topic.setdefault("question_count", len(topic.get("questions") or []))
        group["topics"] = topics
        group["topic_count"] = len(topics)
        group["curated_pack_count"] = sum(1 for topic in topics if topic["id"] in QUESTION_PACKS)
        group["discovery_theme_count"] = len(topics) - group["curated_pack_count"]
        output.append(group)
    return output


@app.get("/api/health")
def health(response: Response) -> dict[str, Any]:
    try:
        with closing(sqlite3.connect(STORE.db_path, timeout=1.0)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            probe_table = f"hsptl_health_probe_{uuid.uuid4().hex}"
            connection.execute(f'CREATE TABLE "{probe_table}" (id INTEGER)')
            connection.rollback()
    except sqlite3.Error:
        logger.exception("Database write health check failed")
        response.status_code = 503
        return {"ok": False, "name": APP_NAME, "code": "database_not_writable"}
    return {"ok": True, "name": APP_NAME, "version": APP_VERSION, "api": "FastAPI",
            "core_ready": True, "optional_models_loaded": False}


@app.get("/api/system/capabilities")
def system_capabilities() -> dict[str, Any]:
    return capability_report(STORE.fts_available)


@app.post("/api/system/backup")
def create_database_backup() -> FileResponse:
    backup_dir = PATHS["root"] / "backups"
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    destination = backup_dir / f"hsptl-{stamp}.sqlite3"
    try:
        STORE.backup_to(destination)
        backups = sorted(backup_dir.glob("hsptl-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in backups[10:]:
            stale.unlink(missing_ok=True)
    except (OSError, sqlite3.Error) as exc:
        logger.exception("SQLite backup failed")
        raise HTTPException(status_code=500, detail="Could not create a database backup") from exc
    return FileResponse(destination, media_type="application/vnd.sqlite3", filename=destination.name)


@app.get("/api/search")
def search_knowledge(q: str = "", limit: int = 30) -> dict[str, Any]:
    query = q.strip()
    if len(query) > 300:
        raise HTTPException(status_code=400, detail="Search query is too long")
    results = STORE.search_notes(query, limit=limit)
    return {"query": query, "engine": "sqlite_fts5" if STORE.fts_available else "sqlite_like_fallback",
            "results": [{"id": row["id"], "category": row["category"], "title": row["title"],
                         "source": row["source"], "updated_at": row["updated_at"],
                         "version": row.get("version", 1), "excerpt": row["body"][:500]} for row in results]}


@app.post("/api/clinical/fhir/import")
def import_fhir_cases(payload: FHIRImportRequest) -> dict[str, Any]:
    """Import a local FHIR directory into the provenance-aware case store."""
    source = _resolve_allowed_data_directory(payload.path)
    try:
        result = CASE_STORE.import_directory(source, batch_size=payload.batch_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        logger.exception("FHIR import failed")
        raise HTTPException(status_code=500, detail="FHIR import could not access the selected source") from exc
    return result


@app.get("/api/clinical/patients")
def clinical_patients(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return CASE_STORE.list_patients(limit=limit, offset=offset)


@app.get("/api/clinical/patients/{patient_key}")
def clinical_patient_case(patient_key: str, encounter_key: str | None = None) -> dict[str, Any]:
    result = CASE_STORE.patient_case(patient_key, encounter_key=encounter_key)
    if result is None:
        raise HTTPException(status_code=404, detail="Patient or encounter was not found")
    return result


@app.get("/api/clinical/patients/{patient_key}/encounters/{encounter_key}/narrative")
def clinical_encounter_narrative(patient_key: str, encounter_key: str) -> dict[str, Any]:
    result = CASE_STORE.patient_case(patient_key, encounter_key=encounter_key)
    if result is None:
        raise HTTPException(status_code=404, detail="Patient or encounter was not found")
    try:
        return build_encounter_narrative(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/clinical/learning-attempts")
def list_clinical_learning_attempts(limit: int = 100) -> dict[str, Any]:
    items = CASE_STORE.list_learning_attempts(limit)
    for item in items:
        saved = STORE.debriefs(f"attempt:{item['attempt_id']}").get(1, {})
        responses = {section["key"]: str(saved.get(section["key"], "")) for section in PEARLS_DEBRIEF}
        completed, total = debrief_completion(responses)
        item["debrief_completed"] = completed
        item["debrief_total"] = total
    return {"count": len(items), "items": items}


@app.get("/api/clinical/learning-attempts/{attempt_id}")
def get_clinical_learning_attempt(attempt_id: str) -> dict[str, Any]:
    attempt = CASE_STORE.get_learning_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Learning attempt was not found")
    # Keep internal synthetic patient/encounter keys out of the general debrief response.
    attempt.pop("patient_key", None)
    attempt.pop("encounter_key", None)
    return attempt


@app.post("/api/clinical/learning-attempts")
def save_clinical_learning_attempt(payload: ClinicalLearningAttemptRequest) -> dict[str, Any]:
    try:
        return CASE_STORE.save_learning_attempt(
            patient_key=payload.patient_key,
            encounter_key=payload.encounter_key,
            payload=payload.model_dump(exclude={"patient_key", "encounter_key"}),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/clinical/learning-attempts/{attempt_id}/debrief")
def get_clinical_attempt_debrief(attempt_id: str) -> dict[str, Any]:
    if CASE_STORE.get_learning_attempt(attempt_id) is None:
        raise HTTPException(status_code=404, detail="Learning attempt was not found")
    saved = STORE.debriefs(f"attempt:{attempt_id}").get(1, {})
    responses = {item["key"]: str(saved.get(item["key"], "")) for item in PEARLS_DEBRIEF}
    completed, total = debrief_completion(responses)
    return {"responses": responses, "completed": completed, "total": total, "sections": PEARLS_DEBRIEF}


@app.put("/api/clinical/learning-attempts/{attempt_id}/debrief")
def save_clinical_attempt_debrief(attempt_id: str, payload: ClinicalDebriefRequest) -> dict[str, Any]:
    if CASE_STORE.get_learning_attempt(attempt_id) is None:
        raise HTTPException(status_code=404, detail="Learning attempt was not found")
    responses = clean_debrief_payload(payload.responses)
    STORE.save_debrief(f"attempt:{attempt_id}", 1, responses)
    completed, total = debrief_completion(responses)
    return {"saved": True, "responses": responses, "completed": completed, "total": total}


@app.post("/api/clinical/learning-attempts/{attempt_id}/pearl")
def create_learning_reflection_pearl(attempt_id: str, payload: LearningPearlRequest) -> dict[str, Any]:
    """Save a learner-authored reflection in Pearls without presenting it as verified guidance."""
    attempt = CASE_STORE.get_learning_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Learning attempt was not found")

    focus = payload.focus.strip()
    reflection = payload.reflection.strip()
    title = f"Learning reflection: {focus[:70]} · {attempt.get('case_code', attempt_id[:8])}"
    learner_sections = [
        ("Problem representation", attempt.get("problem_representation", "")),
        ("Differential diagnoses", "\n".join(attempt.get("differentials", []))),
        ("Evidence supporting", attempt.get("evidence_for", "")),
        ("Evidence against / uncertainty", attempt.get("evidence_against", "")),
        ("Investigation strategy", attempt.get("investigation_plan", "")),
        ("Management and safety", "\n\n".join(filter(None, [attempt.get("management_plan", ""), attempt.get("safety_net", "")]))),
        ("Communication", attempt.get("communication_plan", "")),
    ]
    sections = [{
        "title": "Learner reflection",
        "objective": "A personal learning action written by the learner; not clinical evidence or a verified recommendation.",
        "evidence": [{
            "text": reflection,
            "citation": "Learner-authored reflection",
            "kind": "learner_reflection",
        }],
        "status": "learner_authored_unverified",
    }]
    markdown_lines = [f"# {title}", "", f"**Focus:** {focus}", "", "## Learner reflection", "", reflection, "",
                     "> This is a learner-authored reflection, not independently verified clinical guidance. Check current local guidance and appropriate references before applying clinical information.", ""]
    for heading, content in learner_sections:
        content = str(content or "").strip()
        if not content:
            continue
        sections.append({
            "title": heading,
            "objective": "Learner-entered content from the saved clinical reasoning attempt; not independently verified.",
            "evidence": [{
                "text": content,
                "citation": "Learner-authored clinical learning attempt",
                "kind": "learner_reflection",
            }],
            "status": "learner_authored_unverified",
        })
        markdown_lines.extend([f"## {heading}", "", content, ""])
    note = {
        "title": title,
        "topic": focus,
        "note_type": "Clinical reflection",
        "level": "Clinical years",
        "jurisdiction": "Not specified",
        "description": "A learner-authored reflection generated from a saved HSPTL reasoning attempt.",
        "level_lens": "Reflect on reasoning process; verify clinical claims independently.",
        "jurisdiction_lens": "No jurisdiction-specific recommendation is supplied.",
        "sections": sections,
        "curated_pack": None,
        "references": [],
        "recall_prompts": [],
        "evidence_count": 0,
        "supported_sections": 0,
        "total_sections": len(sections),
        "generated_mode": "learner_reflection_unverified",
        "provenance": {"kind": "learner_authored", "attempt_id": attempt_id, "verified": False},
    }
    markdown = "\n".join(markdown_lines).strip() + "\n"
    body = json.dumps({"note": note, "markdown": markdown}, ensure_ascii=False)
    saved = STORE.save_note("HSPTLPearlNote", title, body, "Learner-authored reflection; not independently verified")
    return {"saved": True, "id": saved["id"], "title": title, "version": saved["version"], "created": saved["created"]}


@app.get("/api/jobs")
def background_jobs() -> list[dict[str, Any]]:
    return STORE.jobs()


@app.post("/api/jobs")
def create_background_job(payload: BackgroundJobRequest) -> dict[str, str]:
    allowed = {"model_indexing", "document_import", "fhir_import", "content_rebuild", "mednotegen_generate", "specialty_harvest"}
    if payload.kind not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported background job kind")
    job_id = STORE.create_job(payload.kind, payload.payload)
    return {"id": job_id, "status": "queued"}


@app.post("/api/jobs/{job_id}/pause")
def pause_background_job(job_id: str) -> dict[str, bool]:
    jobs = {job["id"]: job for job in STORE.jobs(200)}
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found")
    if job["status"] not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Only queued or running jobs can be paused")
    return {"saved": STORE.update_job(job_id, status="paused")}


@app.post("/api/jobs/{job_id}/resume")
def resume_background_job(job_id: str) -> dict[str, bool]:
    jobs = {job["id"]: job for job in STORE.jobs(200)}
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Background job not found")
    if job["status"] not in {"paused", "failed"}:
        raise HTTPException(status_code=409, detail="Only paused or failed jobs can be resumed")
    return {"saved": STORE.update_job(job_id, status="queued", error_code="")}


@app.get("/api/progress")
def progress_summary() -> dict[str, Any]:
    from .hsptl_core.progress import progress_dimensions
    quiz_average, quiz_groups = STORE.quiz_average()
    dimensions = progress_dimensions(STORE, CASE_STORE, EPISODES, EXAMS)
    return {"lifetime": STORE.stats(), "quiz_average_percent": quiz_average,
            "quiz_groups": quiz_groups,
            "dimensions": dimensions,
            **dimensions,
            "scope": "all_saved_activity"}
@app.get("/api/bootstrap")
def bootstrap() -> dict[str, Any]:
    catalog = get_catalog()
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "data_ready": catalog is not None,
        "cohorts": catalog.source_names if catalog else [],
        "patient_count": len(catalog.patient_keys) if catalog else 0,
        "stats": STORE.stats(),
        "capabilities": capability_report(STORE.fts_available),
        "note_types": list(NOTE_TYPES.keys()),
        "levels": ["Preclinical", "Clinical years", "Final-year / exam revision", "OSCE / practical"],
        "jurisdictions": ["Egypt", "UK", "WHO / global", "International"],
        "default_dataset_path": str(discover_dataset_dirs(SETTINGS)[0]) if discover_dataset_dirs(SETTINGS) else "",
    }


@app.post("/api/data/connect")
def connect_dataset(payload: DatasetConnectRequest) -> dict[str, Any]:
    global SETTINGS
    candidate = _resolve_allowed_data_directory(payload.path)
    try:
        loaded = load_catalog([candidate])
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Could not load that dataset. Check the directory and its data files.",
        ) from exc
    folder = str(candidate.resolve())
    dirs = list(SETTINGS.get("dataset_dirs", []))
    if folder not in dirs:
        dirs.append(folder)
    SETTINGS["dataset_dirs"] = dirs
    try:
        save_settings(SETTINGS, PATHS["settings"])
        get_catalog(force=True)
    except (OSError, ValueError) as exc:
        logger.exception("Dataset settings update failed")
        raise HTTPException(status_code=500, detail="Could not save or refresh the selected dataset") from exc
    return {"connected": True, "patients": len(loaded.patient_keys), "cohorts": loaded.source_names}


@app.get("/api/clinic/daily")
def clinic_daily() -> dict[str, Any]:
    run = _daily_run()
    puzzle = _puzzle_by_id(run["puzzle_id"])
    if not puzzle:
        raise HTTPException(status_code=404, detail="Daily puzzle is no longer in the puzzle pool")
    return _safe_puzzle_payload(puzzle, run)


@app.get("/api/clinic/puzzles")
def clinic_puzzles(specialty: str | None = None) -> list[dict[str, Any]]:
    items = _pool()
    if specialty:
        items = [p for p in items if str(p.get("specialty", "General medicine")).casefold() == specialty.casefold()]
    return [{
        "id": p["id"], "title": str(p.get("title") or p.get("question") or p["id"]),
        "specialty": str(p.get("specialty") or "General medicine"),
        "difficulty": str(p.get("difficulty") or "Intermediate"),
        "clue_count": len(p.get("clues", [])),
        "source_title": str(p.get("source_title") or "HSPTL curated teaching vignette"),
    } for p in items]


@app.post("/api/clinic/start")
def clinic_start(payload: StartPuzzleRequest) -> dict[str, Any]:
    pool = _pool()
    if not pool:
        raise HTTPException(status_code=503, detail="No puzzles are available")
    if payload.puzzle_id:
        puzzle_id = payload.puzzle_id
    else:
        # Select a fresh run without reusing the daily session.
        existing = set()
        for row in STORE.notes("HSPTLPuzzleHistory"):
            try:
                previous = json.loads(row.get("body") or "{}")
                if previous.get("puzzle_id"):
                    existing.add(str(previous["puzzle_id"]))
            except (TypeError, ValueError) as exc:
                logger.warning("Skipped invalid puzzle history entry: %s", type(exc).__name__)
                continue
        available = [p for p in pool if p["id"] not in existing]
        if not available:
            available = pool
        puzzle_id = str(available[0]["id"])
    run = _new_run(puzzle_id, daily=False)
    puzzle = _puzzle_by_id(puzzle_id)
    return _safe_puzzle_payload(puzzle, run)


@app.get("/api/clinic/run/{run_id}")
def clinic_run(run_id: str) -> dict[str, Any]:
    run = _get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Puzzle session not found")
    puzzle = _puzzle_by_id(run["puzzle_id"])
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    return _safe_puzzle_payload(puzzle, run)


@app.post("/api/clinic/guess")
def clinic_guess(payload: GuessRequest) -> dict[str, Any]:
    run = _get_run(payload.run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Puzzle session not found")
    puzzle = _puzzle_by_id(run["puzzle_id"])
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    game = {"guesses": run["guesses"], "revealed": run["revealed"], "finished": run["finished"], "solved": run["solved"]}
    result = apply_guess(game, puzzle, payload.guess)
    if result == "empty":
        raise HTTPException(status_code=400, detail="Enter a diagnosis before submitting")
    run.update(game)
    _save_run(run)
    if result in {"correct", "exhausted"}:
        history = {"date": run["day_key"], "puzzle_id": run["puzzle_id"], "specialty": puzzle.get("specialty", "General medicine"), "difficulty": puzzle.get("difficulty", "Intermediate"), "result": result, "guess_count": len(run["guesses"])}
        STORE.save_note("HSPTLPuzzleHistory", str(puzzle.get("title") or puzzle["id"]), json.dumps(history), str(puzzle.get("source_url") or ""))
    return {"result": result, **_safe_puzzle_payload(puzzle, run)}


@app.post("/api/clinic/reveal/{run_id}")
def clinic_reveal(run_id: str) -> dict[str, Any]:
    run = _get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Puzzle session not found")
    puzzle = _puzzle_by_id(run["puzzle_id"])
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    if not run["finished"]:
        run["revealed"] = min(run["revealed"] + 1, len(puzzle.get("clues", [])))
        _save_run(run)
    return _safe_puzzle_payload(puzzle, run)


@app.get("/api/clinical-catalogue/events")
def clinical_events_catalogue() -> dict[str, Any]:
    from .runtime import CASE_LOTTERY
    items = CASE_LOTTERY.event_catalogue(active_only=True)
    return {"items": items, "count": len(items), "note": "Educational scenario themes only; not live alerts, protocols or patient-specific advice."}


@app.get("/api/clinical-catalogue/summary")
def clinical_catalogue_summary() -> dict[str, Any]:
    from .hsptl_core.clinical_catalogues import catalogue_summary
    from .hsptl_core.source_registry import PRIORITY_SOURCE_CATALOGUE
    summary = catalogue_summary()
    summary["source_count"] = len(PRIORITY_SOURCE_CATALOGUE)
    summary["source_families"] = len({str(item.get("family", "other")) for item in PRIORITY_SOURCE_CATALOGUE})
    return summary


@app.get("/api/specialties")
def specialties() -> list[dict[str, Any]]:
    return _specialty_groups()


@app.get("/api/specialties/{slug}")
def specialty_detail(slug: str) -> dict[str, Any]:
    group = next((item for item in _specialty_groups() if item["slug"] == slug), None)
    if not group:
        raise HTTPException(status_code=404, detail="Specialty not found")
    return group


@app.get("/api/specialties/{slug}/articles")
def specialty_articles(slug: str, q: str, limit: int = 6) -> list[dict[str, Any]]:
    group = next((item for item in _specialty_groups() if item["slug"] == slug), None)
    if not group:
        raise HTTPException(status_code=404, detail="Specialty not found")
    if not q.strip():
        raise HTTPException(status_code=400, detail="Enter a topic to search")
    try:
        rows = europe_pmc_search(q, limit=max(1, min(limit, 10)), case_reports_only=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        logger.exception("Europe PMC article search failed")
        raise HTTPException(status_code=502, detail="Europe PMC search is temporarily unavailable") from exc
    output = []
    for row in rows:
        output.append({"title": row.get("title") or "Untitled article", "authors": row.get("authorString") or "", "journal": row.get("journalTitle") or "", "year": row.get("pubYear") or "", "pmcid": row.get("pmcid") or "", "open_access": is_open_access(row), "url": article_url(row), "abstract": (row.get("abstractText") or "")[:900]})
    return output


@app.get("/api/specialties/{slug}/images")
def specialty_images(slug: str, q: str, limit: int = 6) -> list[dict[str, str]]:
    group = next((item for item in _specialty_groups() if item["slug"] == slug), None)
    if not group:
        raise HTTPException(status_code=404, detail="Specialty not found")
    try:
        return commons_search_images(q, limit=max(1, min(limit, 8)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        logger.exception("Wikimedia Commons image search failed")
        raise HTTPException(status_code=502, detail="Wikimedia Commons search is temporarily unavailable") from exc


def _reference_pdf_paths() -> list[Path]:
    candidates = [PATHS["references"], PATHS["imports"]]
    candidates.extend(Path(str(p)).expanduser() for p in SETTINGS.get("reference_dirs", []) if str(p).strip())
    found: list[Path] = []
    seen: set[str] = set()
    for folder in candidates:
        if folder.is_dir():
            for path in sorted(folder.rglob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
                key = str(path.resolve()).casefold()
                if key not in seen:
                    found.append(path)
                    seen.add(key)
                if len(found) >= 40:
                    return found
    return found


@app.get("/api/pearls/options")
def pearls_options() -> dict[str, Any]:
    return {"note_types": list(NOTE_TYPES.keys()), "levels": ["Preclinical", "Clinical years", "Final-year / exam revision", "OSCE / practical"], "jurisdictions": ["Egypt", "UK", "WHO / global", "International"], "packs": [{"id": key, "title": value.get("title"), "tagline": value.get("tagline"), "source_title": value.get("source_title"), "source_url": value.get("source_url")} for key, value in QUESTION_PACKS.items()]}


@app.get("/api/pearls/references")
def pearls_references() -> list[dict[str, Any]]:
    result = []
    for path in _reference_pdf_paths():
        try:
            result.append({"name": path.name, "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="minutes"), "size_bytes": path.stat().st_size})
        except OSError as exc:
            logger.warning("Skipped inaccessible reference file %s: %s", path.name, type(exc).__name__)
            continue
    return result


@app.post("/api/pearls/references")
async def upload_reference(file: UploadFile = File(...)) -> dict[str, Any]:
    """Stream PDF uploads to a temporary file and atomically publish when valid."""
    filename = Path(file.filename or "reference.pdf").name
    target_dir = PATHS["references"]
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Reference upload directory preparation failed")
        raise HTTPException(status_code=500, detail="Could not prepare reference storage") from exc
    temp = target_dir / f".upload-{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    total = 0
    prefix = bytearray()
    maximum = 35 * 1024 * 1024
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=415, detail="The uploaded file must have MIME type application/pdf")
        with temp.open("wb") as stream:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise HTTPException(status_code=413, detail="PDF exceeds the 35 MB import limit")
                if len(prefix) < 5:
                    prefix.extend(chunk[:5 - len(prefix)])
                digest.update(chunk)
                stream.write(chunk)
        if not bytes(prefix).startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file does not appear to be a PDF")
        try:
            reader = PdfReader(temp, strict=True)
            if reader.is_encrypted or not reader.pages:
                raise PdfReadError("PDF must be unencrypted and contain at least one page")
        except (OSError, PdfReadError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid, unencrypted PDF") from exc
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._-") or "reference"
        target = target_dir / f"{stem}_{digest.hexdigest()[:10]}.pdf"
        temp.replace(target)
        return {"saved": True, "name": target.name, "size_bytes": total}
    except HTTPException:
        temp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temp.unlink(missing_ok=True)
        logger.exception("Reference upload failed")
        raise HTTPException(status_code=500, detail="Could not save the reference file") from exc
    finally:
        temp.unlink(missing_ok=True)
        await file.close()


def _local_pdf_excerpts(topic: str) -> list[dict[str, str]]:
    excerpts: list[dict[str, str]] = []
    for path in _reference_pdf_paths()[:8]:
        try:
            excerpts.extend(pdf_source_excerpts(path, topic, limit=2))
        except (OSError, PdfReadError, ValueError, RuntimeError) as exc:
            logger.warning("Skipped local PDF reference %s: %s", path.name, type(exc).__name__)
    return excerpts[:12]


def _article_excerpts(topic: str, pmcid: str | None = None) -> list[dict[str, str]]:
    from .hsptl_core.note_engine import article_source_excerpts
    articles: list[dict[str, Any]] = []
    if pmcid:
        articles = [{"pmcid": pmcid.strip().upper(), "isOpenAccess": "Y"}]
    else:
        try:
            rows = europe_pmc_search(topic, limit=8, case_reports_only=False)
        except requests.RequestException as exc:
            raise ExternalServiceError("Europe PMC search is temporarily unavailable") from exc
        articles = [row for row in rows if is_open_access(row) and row.get("pmcid")][:4]
    excerpts: list[dict[str, str]] = []
    for meta in articles[:4]:
        if not is_open_access(meta) or not meta.get("pmcid"):
            continue
        try:
            xml_text = europe_pmc_fulltext_xml(str(meta["pmcid"]))
        except requests.RequestException as exc:
            raise ExternalServiceError("Europe PMC full text is temporarily unavailable") from exc
        if not xml_text:
            continue
        try:
            parsed = parse_jats_article(xml_text)
        except (ET.ParseError, ValueError) as exc:
            logger.warning(
                "Skipped malformed JATS article %s: %s",
                meta.get("pmcid"),
                type(exc).__name__,
                exc_info=True,
            )
            continue
        license_text = parsed.get("license_text", "")
        license_url = parsed.get("license_url", "")
        if not article_license_allows_excerpt(license_url, license_text):
            continue
        parsed.update({"url": article_url(meta), "license_text": license_text, "license_url": license_url})
        if not parsed.get("title"):
            parsed["title"] = meta.get("title") or meta["pmcid"]
        excerpts.extend(article_source_excerpts(parsed, topic, limit=2))
    return excerpts[:8]


@app.post("/api/pearls/generate")
def generate_pearls(payload: NoteRequest) -> dict[str, Any]:
    try:
        pack = find_curated_pack(payload.topic, QUESTION_PACKS)
        excerpts: list[dict[str, str]] = []
        if payload.use_local_pdfs:
            excerpts.extend(_local_pdf_excerpts(payload.topic))
        if payload.use_open_access:
            excerpts.extend(_article_excerpts(payload.topic, payload.pmcid))
        note = generate_study_note(
            topic=payload.topic,
            note_type=payload.note_type,
            level=payload.level,
            jurisdiction=payload.jurisdiction,
            excerpts=excerpts,
            curated_pack=pack,
        )
        markdown = note_to_markdown(note)
        tutor_prompt = build_external_tutor_prompt(note, markdown)
        return {"note": note, "markdown": markdown, "tutor_prompt": tutor_prompt, "local_reference_count": len(excerpts), "matched_curated_pack": bool(pack)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ExternalServiceError as exc:
        logger.exception("Pearls note generation could not reach Europe PMC")
        raise HTTPException(status_code=502, detail="Could not assemble the note from the selected sources") from exc
    except OSError as exc:
        logger.exception("Pearls note generation could not read local references")
        raise HTTPException(status_code=500, detail="Could not read the selected local references") from exc


@app.post("/api/pearls/save")
def save_pearl(payload: SaveNoteRequest) -> dict[str, Any]:
    note = payload.note
    if not isinstance(note, dict) or not note.get("topic") or not note.get("sections"):
        raise HTTPException(status_code=400, detail="The generated note is incomplete")
    markdown = note_to_markdown(note)
    body = json.dumps({"note": note, "markdown": markdown}, ensure_ascii=False)
    title = str(note.get("title") or note.get("topic"))
    saved = STORE.save_note("HSPTLPearlNote", title, body, "; ".join(r.get("citation", "") for r in note.get("references", [])[:8]))
    return {"saved": True, "id": saved["id"], "title": title,
            "version": saved["version"], "created": saved["created"], "updated": saved["updated"]}


@app.get("/api/pearls/saved")
def saved_pearls(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    items = []
    for row in STORE.notes("HSPTLPearlNote", limit=limit, offset=offset):
        try:
            content = json.loads(row.get("body") or "{}")
            note = content.get("note", {})
            items.append({"id": row["id"], "title": row["title"], "topic": note.get("topic", row["title"]), "note_type": note.get("note_type", "Condition"), "saved_at": row.get("created_at"), "supported_sections": note.get("supported_sections", 0), "total_sections": note.get("total_sections", 0)})
        except (ValueError, TypeError, AttributeError) as exc:
            logger.warning("Skipped unreadable saved Pearl %s: %s", row.get("id"), type(exc).__name__)
            continue
    return items


@app.get("/api/pearls/saved/{note_id}")
def saved_pearl_detail(note_id: str) -> dict[str, Any]:
    row = next((item for item in STORE.notes("HSPTLPearlNote") if item.get("id") == note_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="Saved note not found")
    try:
        return json.loads(row.get("body") or "{}")
    except ValueError as exc:
        logger.exception("Saved Pearl JSON is invalid for note %s", note_id)
        raise HTTPException(status_code=500, detail="Saved note cannot be read") from exc


@app.post("/api/pearls/cards")
def create_pearl_cards(payload: SaveNoteRequest) -> dict[str, int]:
    note = payload.note
    created = 0
    for prompt in note.get("recall_prompts", [])[:10]:
        if STORE.add_card(
            str(prompt.get("question", "")), str(prompt.get("answer", "")),
            source=str(prompt.get("source", "HSPTL study note")), tags=f"Pearls,{note.get('topic', '')}",
        ):
            created += 1
    curated = note.get("curated_pack") or {}
    for question in curated.get("questions", [])[:8]:
        options = question.get("options", [])
        answer_index = question.get("answer")
        correct = options[answer_index] if isinstance(answer_index, int) and 0 <= answer_index < len(options) else "See source explanation"
        back = f"{correct}\n\n{question.get('explanation', '')}\n\n{question.get('takeaway', '')}"
        if STORE.add_card(str(question.get("question", "")), back, source=str(curated.get("source_title", "Curated pack")), tags=f"Pearls,{note.get('topic', '')}"):
            created += 1
    return {"created": created}


@app.get("/api/revision")
def revision_summary(recent_limit: int = 30, recent_offset: int = 0) -> dict[str, Any]:
    safe_limit = max(1, min(recent_limit, 200))
    safe_offset = max(0, recent_offset)
    return {"stats": STORE.stats(), "due_cards": STORE.cards(due_only=True, limit=100),
            "recent_cards": STORE.cards(due_only=False, limit=safe_limit, offset=safe_offset),
            "recent_total": STORE.card_count(), "recent_limit": safe_limit, "recent_offset": safe_offset}


@app.post("/api/revision/cards")
def add_revision_card(payload: CardRequest) -> dict[str, Any]:
    created = STORE.add_card(payload.front, payload.back, payload.source, payload.tags)
    return {"created": created}


@app.post("/api/revision/cards/{card_id}/grade")
def grade_revision_card(card_id: str, payload: GradeRequest) -> dict[str, bool]:
    card = next((x for x in STORE.cards() if x.get("id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Revision card not found")
    STORE.grade_card(card_id, payload.grade)
    return {"saved": True}


@app.get("/api/settings")
def get_app_settings() -> dict[str, Any]:
    return {"theme": SETTINGS.get("theme", "light"), "dataset_dirs": SETTINGS.get("dataset_dirs", []), "reference_dirs": SETTINGS.get("reference_dirs", []), "user_data_dir": str(PATHS["root"])}


@app.put("/api/settings/theme")
def set_theme(payload: dict[str, str]) -> dict[str, str]:
    theme = payload.get("theme", "light")
    if theme not in {"light", "dark"}:
        raise HTTPException(status_code=400, detail="Theme must be light or dark")
    SETTINGS["theme"] = theme
    save_settings(SETTINGS, PATHS["settings"])
    return {"theme": theme}


if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_fallback(full_path: str):
    # The API is registered above; this catch-all serves the compiled React SPA.
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="HSPTL frontend has not been built. Run npm install and npm run build in frontend/.")
    candidate = (FRONTEND_DIST / full_path).resolve() if full_path else index.resolve()
    try:
        candidate.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(index)
