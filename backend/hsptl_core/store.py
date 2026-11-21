"""SQLite-backed local learning portfolio.

All learning data are stored locally. There is no telemetry or cloud sync.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


class StudyStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_available = False
        self._initialise()
        from .migrations import apply as _apply_phase_migrations
        with self.transaction() as conn:
            _apply_phase_migrations(conn)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self.transaction() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stage_attempts (
                    id TEXT PRIMARY KEY,
                    patient_key TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    answer TEXT NOT NULL DEFAULT '',
                    rubric_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(patient_key, stage_index)
                );
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id TEXT PRIMARY KEY,
                    patient_key TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    responses_json TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS revision_cards (
                    id TEXT PRIMARY KEY,
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    last_grade TEXT NOT NULL DEFAULT 'New',
                    last_reviewed TEXT,
                    suspended INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_revision_due ON revision_cards(due_date, suspended);
                CREATE TABLE IF NOT EXISTS illness_scripts (
                    id TEXT PRIMARY KEY,
                    condition TEXT NOT NULL,
                    fields_json TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS study_notes (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    content_hash TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS study_note_versions (
                    id TEXT PRIMARY KEY,
                    note_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(note_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_note_versions_note ON study_note_versions(note_id, version);
                CREATE TABLE IF NOT EXISTS background_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    progress_done INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    checkpoint_json TEXT NOT NULL DEFAULT '{}',
                    error_code TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status, updated_at);
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulation_debriefs (
                    id TEXT PRIMARY KEY,
                    patient_key TEXT NOT NULL,
                    stage_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(patient_key, stage_index)
                );
                CREATE INDEX IF NOT EXISTS idx_debrief_patient ON simulation_debriefs(patient_key, stage_index);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
            """)
            # Additive migrations keep existing learner data intact.
            note_columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_notes)")}
            if "version" not in note_columns:
                conn.execute("ALTER TABLE study_notes ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            if "content_hash" not in note_columns:
                conn.execute("ALTER TABLE study_notes ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(1, ?)", (self._now(),))
            try:
                fts_preexisting = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='study_notes_fts'"
                ).fetchone() is not None
                conn.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS study_notes_fts USING fts5(
                        title, body, source, content='study_notes', content_rowid='rowid'
                    );
                    CREATE TRIGGER IF NOT EXISTS study_notes_ai AFTER INSERT ON study_notes BEGIN
                        INSERT INTO study_notes_fts(rowid, title, body, source)
                        VALUES(new.rowid, new.title, new.body, new.source);
                    END;
                    CREATE TRIGGER IF NOT EXISTS study_notes_ad AFTER DELETE ON study_notes BEGIN
                        INSERT INTO study_notes_fts(study_notes_fts, rowid, title, body, source)
                        VALUES('delete', old.rowid, old.title, old.body, old.source);
                    END;
                    CREATE TRIGGER IF NOT EXISTS study_notes_au AFTER UPDATE ON study_notes BEGIN
                        INSERT INTO study_notes_fts(study_notes_fts, rowid, title, body, source)
                        VALUES('delete', old.rowid, old.title, old.body, old.source);
                        INSERT INTO study_notes_fts(rowid, title, body, source)
                        VALUES(new.rowid, new.title, new.body, new.source);
                    END;
                """)
                if not fts_preexisting:
                    conn.execute("INSERT INTO study_notes_fts(study_notes_fts) VALUES('rebuild')")
                self.fts_available = True
            except sqlite3.OperationalError:
                # SQLite builds without FTS5 still get a deterministic LIKE search.
                self.fts_available = False

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="microseconds")

    def save_stage_attempt(self, patient_key: str, stage_index: int, answer: str,
                           rubric: dict[str, Any] | None = None) -> None:
        now = self._now()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO stage_attempts(id, patient_key, stage_index, answer, rubric_json, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(patient_key, stage_index) DO UPDATE SET
                    answer=excluded.answer, rubric_json=excluded.rubric_json, updated_at=excluded.updated_at
            """, (str(uuid.uuid4()), patient_key, int(stage_index), answer,
                  json.dumps(rubric or {}, ensure_ascii=False), now, now))

    def stage_attempts(self, patient_key: str) -> dict[int, dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM stage_attempts WHERE patient_key=?", (patient_key,)).fetchall()
        result: dict[int, dict[str, Any]] = {}
        for row in rows:
            result[int(row["stage_index"])] = {
                "answer": row["answer"],
                "rubric": self._json_load(row["rubric_json"], {}),
                "updated_at": row["updated_at"],
            }
        return result

    def save_quiz_attempt(self, patient_key: str, stage_index: int, score: int,
                          total: int, responses: list[Any]) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO quiz_attempts(id, patient_key, stage_index, score, total, responses_json, completed_at)
                VALUES(?,?,?,?,?,?,?)
            """, (str(uuid.uuid4()), patient_key, int(stage_index), int(score), int(total),
                  json.dumps(responses, ensure_ascii=False), self._now()))

    def quiz_average(self) -> tuple[float | None, int]:
        """Return mean percentage across each patient's latest quiz per stage."""
        with self.transaction() as conn:
            row = conn.execute("""
                SELECT AVG(100.0 * q.score / NULLIF(q.total, 0)) AS mean_score, COUNT(*) AS n
                FROM quiz_attempts q
                WHERE q.completed_at = (
                    SELECT MAX(q2.completed_at) FROM quiz_attempts q2
                    WHERE q2.patient_key=q.patient_key AND q2.stage_index=q.stage_index
                )
            """).fetchone()
        mean = row["mean_score"] if row else None
        return (float(mean) if mean is not None else None, int(row["n"] if row else 0))

    def latest_quiz_attempts(self, patient_key: str) -> dict[int, dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("""
                SELECT q.* FROM quiz_attempts q
                JOIN (SELECT stage_index, MAX(completed_at) AS latest
                      FROM quiz_attempts WHERE patient_key=? GROUP BY stage_index) m
                ON q.stage_index=m.stage_index AND q.completed_at=m.latest
                WHERE q.patient_key=?
            """, (patient_key, patient_key)).fetchall()
        return {int(r["stage_index"]): {
            "score": int(r["score"]), "total": int(r["total"]),
            "responses": self._json_load(r["responses_json"], []),
            "completed_at": r["completed_at"],
        } for r in rows}

    def save_debrief(self, patient_key: str, stage_index: int, payload: dict[str, str]) -> None:
        """Persist one structured guided debrief per patient and stage."""
        now = self._now()
        safe_payload = {str(k): str(v or "")[:5000] for k, v in payload.items()}
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO simulation_debriefs(id, patient_key, stage_index, payload_json, created_at, updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(patient_key, stage_index) DO UPDATE SET
                     payload_json=excluded.payload_json, updated_at=excluded.updated_at""",
                (str(uuid.uuid4()), patient_key, int(stage_index),
                 json.dumps(safe_payload, ensure_ascii=False), now, now),
            )

    def debriefs(self, patient_key: str) -> dict[int, dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM simulation_debriefs WHERE patient_key=? ORDER BY stage_index",
                (patient_key,),
            ).fetchall()
        return {
            int(row["stage_index"]): {
                **self._json_load(row["payload_json"], {}),
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def add_card(self, front: str, back: str, source: str = "", tags: str = "", *,
                 origin_note_id: str = "", origin_episode_id: str = "",
                 origin_artifact_id: str = "", source_ref_id: str = "") -> bool:
        front, back = front.strip(), back.strip()
        if not front or not back:
            return False
        normal = " ".join(front.casefold().split())
        with self.transaction() as conn:
            existing = conn.execute("SELECT front FROM revision_cards").fetchall()
            if any(" ".join(str(row["front"]).casefold().split()) == normal for row in existing):
                return False
            today = date.today().isoformat()
            conn.execute(
                "INSERT INTO revision_cards(id, front, back, source, tags, created_at, due_date, "
                "origin_note_id, origin_episode_id, origin_artifact_id, source_ref_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), front, back, source, tags, self._now(), today,
                 origin_note_id[:80], origin_episode_id[:80], origin_artifact_id[:80],
                 source_ref_id[:64]),
            )
        return True
    def cards(self, due_only: bool = False, include_suspended: bool = False,
              limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        conditions, params = [], []
        if due_only:
            conditions.append("due_date<=?")
            params.append(date.today().isoformat())
        if not include_suspended:
            conditions.append("suspended=0")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = "SELECT * FROM revision_cards" + where + " ORDER BY due_date, created_at"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([max(1, min(int(limit), 500)), max(0, int(offset))])
        with self.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def card_count(self, due_only: bool = False, include_suspended: bool = False) -> int:
        conditions, params = [], []
        if due_only:
            conditions.append("due_date<=?")
            params.append(date.today().isoformat())
        if not include_suspended:
            conditions.append("suspended=0")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        with self.transaction() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM revision_cards" + where, params).fetchone()
        return int(row["n"] if row else 0)

    def scheduler_name(self) -> str:
        with self.transaction() as conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key='scheduler'").fetchone()
        try:
            return str(json.loads(row["value_json"])) if row else "simple"
        except (TypeError, ValueError):
            return "simple"

    def set_scheduler(self, name: str) -> str:
        from .scheduling import SCHEDULERS
        if name not in SCHEDULERS:
            raise ValueError("Unknown scheduler")
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings(key,value_json) VALUES('scheduler',?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json",
                (json.dumps(name),),
            )
        return name

    def review_analytics(self) -> dict[str, Any]:
        with self.transaction() as conn:
            states = {r["state"]: r["n"] for r in conn.execute(
                "SELECT COALESCE(NULLIF(state,''),'new') state, COUNT(*) n "
                "FROM revision_cards GROUP BY state")}
            grades = {r["grade"]: r["n"] for r in conn.execute(
                "SELECT grade, COUNT(*) n FROM card_reviews GROUP BY grade")}
            forecast = [{"days": d, "due": conn.execute(
                "SELECT COUNT(*) n FROM revision_cards WHERE suspended=0 AND needs_source_review=0 "
                "AND due_date<=?", ((date.today() + timedelta(days=d)).isoformat(),)).fetchone()["n"]}
                for d in (1, 7, 30)]
            flagged = conn.execute("SELECT COUNT(*) n FROM revision_cards "
                                   "WHERE needs_source_review=1").fetchone()["n"]
        total_reviews = sum(grades.values())
        again = grades.get("Again", 0)
        return {
            "states": states, "grades": grades, "forecast": forecast,
            "reviews_recorded": total_reviews,
            "again_rate_percent": round(again / total_reviews * 100, 1) if total_reviews else None,
            "cards_needing_source_review": int(flagged),
            "scheduler": self.scheduler_name(),
            "scope": "Card recall only; this is not a measure of clinical performance.",
        }

    def grade_card(self, card_id: str, grade: str, *, scheduler: str | None = None) -> dict[str, Any]:
        from .scheduling import CardState, GRADES, get_scheduler
        if grade not in GRADES:
            raise ValueError(f"Unsupported review grade: {grade}")
        today = date.today()
        engine = get_scheduler(scheduler or self.scheduler_name())
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM revision_cards WHERE id=?", (card_id,)).fetchone()
            if row is None:
                raise KeyError("Revision card not found")
            if row["needs_source_review"]:
                raise ValueError("This card's source is flagged for review; verify the source before revising")
            before = CardState(
                card_id=card_id, state=row["state"] or "new",
                interval_days=int(row["interval_days"]), repetitions=int(row["repetitions"]),
                lapses=int(row["lapses"] or 0), stability=float(row["stability"] or 0),
                difficulty=float(row["difficulty"] or 0), due_date=row["due_date"],
                last_reviewed=row["last_reviewed"] or "",
            )
            result = engine.next_review(before, grade, today)
            elapsed = 0
            if before.last_reviewed:
                try:
                    elapsed = max(0, (today - date.fromisoformat(before.last_reviewed[:10])).days)
                except ValueError:
                    elapsed = 0
            conn.execute(
                "UPDATE revision_cards SET interval_days=?, repetitions=?, last_grade=?, due_date=?, "
                "last_reviewed=?, state=?, stability=?, difficulty=?, lapses=?, scheduler=? WHERE id=?",
                (result.interval_days, result.repetitions, grade, result.due_date, today.isoformat(),
                 result.state, result.stability, result.difficulty, result.lapses, result.scheduler, card_id),
            )
            conn.execute(
                "INSERT INTO card_reviews (review_id,card_id,grade,scheduler,state_before,state_after,"
                "elapsed_days,scheduled_days,stability,difficulty,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), card_id, grade, result.scheduler, before.state, result.state,
                 elapsed, result.interval_days, result.stability, result.difficulty, self._now()),
            )
        return {"due_date": result.due_date, "interval_days": result.interval_days,
                "state": result.state, "scheduler": result.scheduler}
    def delete_card(self, card_id: str) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM revision_cards WHERE id=?", (card_id,))

    def add_illness_script(self, condition: str, fields: dict[str, str], reference: str = "") -> None:
        now = self._now()
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO illness_scripts(id, condition, fields_json, reference, created_at, updated_at)
                VALUES(?,?,?,?,?,?)
            """, (str(uuid.uuid4()), condition.strip(), json.dumps(fields, ensure_ascii=False), reference.strip(), now, now))

    def illness_scripts(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM illness_scripts ORDER BY condition COLLATE NOCASE").fetchall()
        return [{**dict(r), "fields": self._json_load(r["fields_json"], {})} for r in rows]

    def save_note(self, category: str, title: str, body: str, source: str = "", *,
                  note_type: str = "", specialty: str = "", jurisdiction: str = "",
                  provenance_status: str = "learner_authored", review_status: str = "unreviewed",
                  review_date: str = "", origin_episode_id: str = "", origin_artifact_id: str = "",
                  has_sources: bool = False) -> dict[str, Any]:
        """Idempotently save a note; retain the previous version when content changes."""
        now = self._now()
        content_hash = hashlib.sha256((body + chr(0) + source).encode("utf-8")).hexdigest()
        meta = (note_type[:80], specialty[:80], jurisdiction[:60], provenance_status[:40],
                review_status[:40], review_date[:20], origin_episode_id[:80],
                origin_artifact_id[:80], int(bool(has_sources)))
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM study_notes WHERE category=? AND title=? ORDER BY updated_at DESC LIMIT 1",
                (category, title),
            ).fetchone()
            if existing is None:
                note_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO study_notes(id, category, title, body, source, created_at, "
                    "updated_at, version, content_hash, note_type, specialty, jurisdiction, "
                    "provenance_status, review_status, review_date, origin_episode_id, "
                    "origin_artifact_id, has_sources) "
                    "VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,?)",
                    (note_id, category, title, body, source, now, now, content_hash, *meta),
                )
                return {"id": note_id, "version": 1, "created": True, "updated": False}
            note_id = str(existing["id"])
            version = int(existing["version"] or 1)
            if existing["content_hash"] == content_hash:
                conn.execute(
                    "UPDATE study_notes SET note_type=?, specialty=?, jurisdiction=?, "
                    "provenance_status=?, review_status=?, review_date=?, origin_episode_id=?, "
                    "origin_artifact_id=?, has_sources=? WHERE id=?", (*meta, note_id),
                )
                return {"id": note_id, "version": version, "created": False, "updated": False}
            conn.execute(
                "INSERT OR IGNORE INTO study_note_versions "
                "(id, note_id, version, title, body, source, content_hash, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), note_id, version, existing["title"], existing["body"],
                 existing["source"], existing["content_hash"], existing["updated_at"]),
            )
            version += 1
            conn.execute(
                "UPDATE study_notes SET body=?, source=?, updated_at=?, version=?, content_hash=?, "
                "note_type=?, specialty=?, jurisdiction=?, provenance_status=?, review_status=?, "
                "review_date=?, origin_episode_id=?, origin_artifact_id=?, has_sources=? WHERE id=?",
                (body, source, now, version, content_hash, *meta, note_id),
            )
            return {"id": note_id, "version": version, "created": False, "updated": True}
    def notes(self, category: str | None = None, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 500)) if limit is not None else None
        safe_offset = max(0, int(offset))
        sql = "SELECT * FROM study_notes"
        params: list[Any] = []
        if category:
            sql += " WHERE category=?"
            params.append(category)
        sql += " ORDER BY updated_at DESC"
        if safe_limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([safe_limit, safe_offset])
        with self.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def search_notes(self, query: str, limit: int = 30) -> list[dict[str, Any]]:
        query = " ".join(str(query or "").split())[:300]
        if not query:
            return []
        limit = max(1, min(int(limit), 100))
        with self.transaction() as conn:
            if self.fts_available:
                # Convert plain words to a safe AND query; no raw FTS operators are accepted.
                terms = [part.replace('"', '""') for part in query.split() if part]
                match = " AND ".join(f'"{term}"*' for term in terms)
                rows = conn.execute("""
                    SELECT n.*, bm25(study_notes_fts) AS rank
                    FROM study_notes_fts f JOIN study_notes n ON n.rowid=f.rowid
                    WHERE study_notes_fts MATCH ? ORDER BY rank LIMIT ?
                """, (match, limit)).fetchall()
            else:
                like = f"%{query}%"
                rows = conn.execute("""
                    SELECT * FROM study_notes WHERE title LIKE ? OR body LIKE ? OR source LIKE ?
                    ORDER BY updated_at DESC LIMIT ?
                """, (like, like, like, limit)).fetchall()
        return [dict(row) for row in rows]

    def create_job(self, kind: str, payload: dict[str, Any] | None = None) -> str:
        now = self._now()
        job_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO background_jobs(id, kind, status, payload_json, created_at, updated_at)
                VALUES(?, ?, 'queued', ?, ?, ?)
            """, (job_id, kind, json.dumps(payload or {}, ensure_ascii=False), now, now))
        return job_id

    def update_job(self, job_id: str, *, status: str | None = None,
                   progress_done: int | None = None, progress_total: int | None = None,
                   checkpoint: dict[str, Any] | None = None, error_code: str | None = None) -> bool:
        allowed = {"queued", "running", "paused", "failed", "completed", "cancelled"}
        if status is not None and status not in allowed:
            raise ValueError("Unsupported background job status")
        fields: list[str] = ["updated_at=?"]
        values: list[Any] = [self._now()]
        for column, value in (("status", status), ("progress_done", progress_done), ("progress_total", progress_total), ("error_code", error_code)):
            if value is not None:
                fields.append(f"{column}=?")
                values.append(max(0, int(value)) if column.startswith("progress_") else value)
        if checkpoint is not None:
            fields.append("checkpoint_json=?")
            values.append(json.dumps(checkpoint, ensure_ascii=False))
        values.append(job_id)
        with self.transaction() as conn:
            cursor = conn.execute(f"UPDATE background_jobs SET {', '.join(fields)} WHERE id=?", values)
            return cursor.rowcount > 0

    def jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM background_jobs ORDER BY updated_at DESC LIMIT ?", (max(1, min(int(limit), 200)),)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = self._json_load(item.pop("payload_json"), {})
            item["checkpoint"] = self._json_load(item.pop("checkpoint_json"), {})
            item["result"] = self._json_load(item.pop("result_json", "{}"), {})
            result.append(item)
        return result

    def backup_to(self, destination: Path) -> Path:
        """Create a consistent SQLite backup, including committed WAL content."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_suffix(destination.suffix + ".tmp")
        temp.unlink(missing_ok=True)
        source_conn = self.connect()
        target_conn = sqlite3.connect(temp)
        try:
            source_conn.backup(target_conn)
            target_conn.commit()
        finally:
            target_conn.close()
            source_conn.close()
        temp.replace(destination)
        return destination

    def stats(self) -> dict[str, int]:
        with self.transaction() as conn:
            cards = conn.execute("SELECT COUNT(*) AS n FROM revision_cards WHERE suspended=0").fetchone()["n"]
            due = conn.execute("SELECT COUNT(*) AS n FROM revision_cards WHERE suspended=0 AND due_date<=?", (date.today().isoformat(),)).fetchone()["n"]
            attempts = conn.execute("SELECT COUNT(*) AS n FROM stage_attempts WHERE length(trim(answer))>0").fetchone()["n"]
            scripts = conn.execute("SELECT COUNT(*) AS n FROM illness_scripts").fetchone()["n"]
            quizzes = conn.execute("SELECT COUNT(*) AS n FROM quiz_attempts").fetchone()["n"]
            debriefs = conn.execute("SELECT COUNT(*) AS n FROM simulation_debriefs").fetchone()["n"]
        return {"cards": int(cards), "due": int(due), "attempts": int(attempts), "scripts": int(scripts), "quizzes": int(quizzes), "debriefs": int(debriefs)}

    @staticmethod
    def _json_load(raw: str, default: Any) -> Any:
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return default
