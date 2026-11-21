"""Question-bank governance and reproducible practice assessment.

Every attempt grades against an immutable snapshot of question versions, so
editing a question or answer key never changes a historical score. Timing is
practice timing: the server records its own start and clamps impossible client
durations. This is not a trusted formal-assessment boundary.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .migrations import apply as apply_migrations

MAX_IMPORT_ROWS = 20_000
MAX_IMPORT_BYTES = 8 * 1024 * 1024
MAX_QUESTIONS = 200
DURATION_GRACE_SECONDS = 120
DIFFICULTIES = {"Foundation", "Beginner", "Intermediate", "Advanced"}


class NotFoundError(KeyError):
    pass


class GovernanceError(RuntimeError):
    """Unreviewed content cannot enter an examination."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalise_answer(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def normalise_question_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Accept HSPTL rows and the MedMCQA opa/opb/opc/opd/cop schema.

    MedMCQA `cop` is a zero-based option index. Imported rows are never
    auto-approved; a human must review the answer key and source.
    """
    question = str(row.get("question") or "").strip()
    if not question:
        return None
    if "opa" in row:
        options = [str(row.get(k) or "").strip() for k in ("opa", "opb", "opc", "opd")]
        options = [o for o in options if o]
        try:
            index = int(row.get("cop", -1))
        except (TypeError, ValueError):
            index = -1
        answer = options[index] if 0 <= index < len(options) else ""
        explanation = str(row.get("exp") or "")
        specialty = str(row.get("subject_name") or "General medicine")
    else:
        raw_options = row.get("options") or []
        if isinstance(raw_options, str):
            raw_options = [o.strip() for o in raw_options.split("|")]
        options = [str(o).strip() for o in raw_options if str(o).strip()]
        answer = str(row.get("answer") or row.get("correct_answer") or "").strip()
        explanation = str(row.get("explanation") or "")
        specialty = str(row.get("specialty") or "General medicine")
    if not answer or (options and answer not in options):
        return None
    difficulty = str(row.get("difficulty") or "Intermediate")
    try:
        timer_seconds = max(0, min(int(row.get("timer_seconds") or 600), 3600))
    except (TypeError, ValueError):
        timer_seconds = 600
    return {
        "kind": str(row.get("kind") or ("MCQ" if options else "ShortAnswer")),
        "specialty": specialty[:80],
        "difficulty": difficulty if difficulty in DIFFICULTIES else "Intermediate",
        "question": question[:4000], "options": options[:8], "answer": answer[:500],
        "aliases": [str(a)[:200] for a in (row.get("aliases") or [])][:12],
        "explanation": explanation[:4000],
        "candidate_instructions": str(row.get("candidate_instructions") or "")[:4000],
        "checklist": [str(x)[:500] for x in (row.get("checklist") or [])][:30],
        "critical_errors": [str(x)[:500] for x in (row.get("critical_errors") or [])][:30],
        "timer_seconds": timer_seconds,
        "source_title": str(row.get("source_title") or "Unspecified source")[:300],
        "source_url": str(row.get("source_url") or "")[:600],
        "licence": str(row.get("licence") or row.get("license")
                       or "User-provided; verify permissions")[:200],
        "media_url": str(row.get("media_url") or "")[:600],
        "tags": [str(t)[:60] for t in (row.get("tags") or [])][:12],
    }


class ExamRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            apply_migrations(conn)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
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

    # -- bank ---------------------------------------------------------------
    def add_question(self, payload: dict[str, Any], *, reviewed: bool = False) -> dict[str, Any]:
        item = normalise_question_row(payload)
        if item is None:
            raise ValueError("A question, a resolvable answer and valid options are required")
        now, question_id, version_id = _now(), str(uuid.uuid4()), str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO exam_questions (question_id,kind,specialty,difficulty,reviewed,"
                "current_version,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)",
                (question_id, item["kind"], item["specialty"], item["difficulty"],
                 int(reviewed), now, now))
            conn.execute(
                "INSERT INTO exam_question_versions (version_id,question_id,version,"
                "payload_json,content_hash,created_at) VALUES(?,?,1,?,?,?)",
                (version_id, question_id, json.dumps(item, ensure_ascii=False), _hash(item), now))
        return {"id": question_id, "version_id": version_id, "version": 1,
                "reviewed": reviewed, **item}

    def revise_question(self, question_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new version. Editing invalidates prior approval."""
        item = normalise_question_row(payload)
        if item is None:
            raise ValueError("Invalid question payload")
        now, version_id = _now(), str(uuid.uuid4())
        with self.transaction() as conn:
            row = conn.execute("SELECT current_version FROM exam_questions WHERE question_id=?",
                               (question_id,)).fetchone()
            if row is None:
                raise NotFoundError("Question not found")
            version = int(row["current_version"]) + 1
            conn.execute(
                "INSERT INTO exam_question_versions (version_id,question_id,version,"
                "payload_json,content_hash,created_at) VALUES(?,?,?,?,?,?)",
                (version_id, question_id, version, json.dumps(item, ensure_ascii=False),
                 _hash(item), now))
            conn.execute(
                "UPDATE exam_questions SET current_version=?, reviewed=0, reviewer='', "
                "specialty=?, difficulty=?, kind=?, updated_at=? WHERE question_id=?",
                (version, item["specialty"], item["difficulty"], item["kind"], now, question_id))
        return {"id": question_id, "version_id": version_id, "version": version, "reviewed": False}

    def set_reviewed(self, question_id: str, reviewed: bool, reviewer: str = "local learner") -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE exam_questions SET reviewed=?, reviewer=?, updated_at=? WHERE question_id=?",
                (int(reviewed), reviewer[:120] if reviewed else "", _now(), question_id))
            return cursor.rowcount > 0

    def questions(self, *, kind: str | None = None, specialty: str | None = None,
                  reviewed: bool | None = None, limit: int = 100,
                  offset: int = 0) -> dict[str, Any]:
        limit, offset = max(1, min(int(limit), 500)), max(0, int(offset))
        where, params = [], []
        if kind:
            where.append("q.kind=?"); params.append(kind)
        if specialty and specialty not in {"Mixed", "All"}:
            where.append("q.specialty=?"); params.append(specialty)
        if reviewed is not None:
            where.append("q.reviewed=?"); params.append(int(reviewed))
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        with self.transaction() as conn:
            total = conn.execute(f"SELECT COUNT(*) n FROM exam_questions q{clause}",
                                 params).fetchone()["n"]
            reviewed_count = conn.execute(
                "SELECT COUNT(*) n FROM exam_questions WHERE reviewed=1").fetchone()["n"]
            rows = conn.execute(
                "SELECT q.*, v.payload_json, v.version_id FROM exam_questions q "
                "JOIN exam_question_versions v ON v.question_id=q.question_id "
                f"AND v.version=q.current_version{clause} "
                "ORDER BY q.updated_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
        items = [{"id": r["question_id"], "version_id": r["version_id"],
                  "version": r["current_version"], "reviewed": bool(r["reviewed"]),
                  **json.loads(r["payload_json"])} for r in rows]
        return {"count": int(total), "reviewed_count": int(reviewed_count),
                "limit": limit, "offset": offset, "questions": items}

    def import_questions(self, content: bytes, filename: str) -> dict[str, int]:
        if len(content) > MAX_IMPORT_BYTES:
            raise ValueError("Import file exceeds the 8 MB safety limit")
        text = content.decode("utf-8", errors="replace")
        name = (filename or "").lower()
        if name.endswith(".json"):
            parsed = json.loads(text)
            rows = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
            if not isinstance(rows, list):
                raise ValueError('JSON import must be an array or {"questions": [...]}')
        elif name.endswith((".jsonl", ".ndjson")):
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            delimiter = "\t" if name.endswith(".tsv") else ","
            rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
        truncated = max(0, len(rows) - MAX_IMPORT_ROWS)
        created = skipped = 0
        for row in rows[:MAX_IMPORT_ROWS]:
            if not isinstance(row, dict):
                skipped += 1
                continue
            try:
                self.add_question(row, reviewed=False)
                created += 1
            except ValueError:
                skipped += 1
        return {"created": created, "skipped": skipped, "truncated": truncated}

    # -- builder --------------------------------------------------------------
    def build_exam(self, *, title: str, specialty: str = "Mixed", difficulty: str = "Any",
                   question_count: int = 20, duration_minutes: int = 30,
                   kinds: list[str] | None = None) -> dict[str, Any]:
        count = max(1, min(int(question_count), MAX_QUESTIONS))
        where, params = ["q.reviewed=1"], []
        if specialty and specialty not in {"Mixed", "All"}:
            where.append("q.specialty=?"); params.append(specialty)
        if difficulty and difficulty != "Any":
            where.append("q.difficulty=?"); params.append(difficulty)
        if kinds:
            where.append("q.kind IN (%s)" % ",".join("?" * len(kinds)))
            params.extend(kinds)
        clause = " AND ".join(where)
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT v.version_id FROM exam_questions q JOIN exam_question_versions v "
                "ON v.question_id=q.question_id AND v.version=q.current_version "
                f"WHERE {clause} ORDER BY RANDOM() LIMIT ?", [*params, count]).fetchall()
            if not rows:
                raise GovernanceError(
                    "No reviewed questions match this blueprint. Review answer keys and "
                    "sources first; HSPTL will not fabricate questions to fill an examination.")
            exam_id, now = str(uuid.uuid4()), _now()
            blueprint = {"specialty": specialty, "difficulty": difficulty, "requested": count,
                         "selected": len(rows), "kinds": kinds or [],
                         "selection": "random_reviewed_only"}
            conn.execute(
                "INSERT INTO exams (exam_id,title,specialty,difficulty,duration_minutes,"
                "blueprint_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (exam_id, (title or "Untitled examination")[:200], specialty, difficulty,
                 max(0, min(int(duration_minutes), 600)), json.dumps(blueprint), now))
            for position, row in enumerate(rows):
                conn.execute("INSERT INTO exam_items(exam_id,position,question_version_id) "
                             "VALUES(?,?,?)", (exam_id, position, row["version_id"]))
        return self.exam(exam_id)

    def exams(self) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT e.*, (SELECT COUNT(*) FROM exam_items i WHERE i.exam_id=e.exam_id) "
                "question_count FROM exams e ORDER BY created_at DESC").fetchall()
        return [{"id": r["exam_id"], "title": r["title"], "specialty": r["specialty"],
                 "difficulty": r["difficulty"], "question_count": r["question_count"],
                 "duration_minutes": r["duration_minutes"], "created_at": r["created_at"]}
                for r in rows]

    def _snapshot(self, conn: sqlite3.Connection, exam_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT i.position, v.version_id, v.version, v.question_id, v.payload_json "
            "FROM exam_items i JOIN exam_question_versions v ON v.version_id=i.question_version_id "
            "WHERE i.exam_id=? ORDER BY i.position", (exam_id,)).fetchall()
        return [{"version_id": r["version_id"], "version": r["version"],
                 "question_id": r["question_id"], **json.loads(r["payload_json"])} for r in rows]

    def exam(self, exam_id: str) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM exams WHERE exam_id=?", (exam_id,)).fetchone()
            if row is None:
                raise NotFoundError("Examination not found")
            snapshot = self._snapshot(conn, exam_id)
        public = [{"id": q["question_id"],
                   **{k: v for k, v in q.items() if k not in {"answer", "aliases", "explanation"}}}
                  for q in snapshot]
        return {"id": row["exam_id"], "title": row["title"], "specialty": row["specialty"],
                "difficulty": row["difficulty"], "duration_minutes": row["duration_minutes"],
                "question_count": len(snapshot), "blueprint": json.loads(row["blueprint_json"]),
                "questions": public}

    # -- attempts ---------------------------------------------------------------
    def start_attempt(self, exam_id: str, episode_id: str = "") -> dict[str, Any]:
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM exams WHERE exam_id=?", (exam_id,)).fetchone() is None:
                raise NotFoundError("Examination not found")
            snapshot = self._snapshot(conn, exam_id)
            attempt_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO exam_attempts (attempt_id,exam_id,episode_id,snapshot_json,"
                "server_started_at,total,timing_source) VALUES(?,?,?,?,?,?,'practice')",
                (attempt_id, exam_id, episode_id, json.dumps(snapshot, ensure_ascii=False),
                 _now(), len(snapshot)))
        return {"attempt_id": attempt_id, "exam": self.exam(exam_id),
                "timing": "Practice timing only; not a trusted formal-assessment clock."}

    def open_attempt_for(self, exam_id: str) -> str | None:
        """Latest unsubmitted attempt. Submitted attempts are never reused."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT attempt_id FROM exam_attempts WHERE exam_id=? AND submitted_at IS NULL "
                "ORDER BY server_started_at DESC LIMIT 1", (exam_id,)).fetchone()
            return row["attempt_id"] if row else None

    def submit_attempt(self, attempt_id: str, responses: dict[str, str],
                       client_duration_seconds: int = 0) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM exam_attempts WHERE attempt_id=?",
                               (attempt_id,)).fetchone()
            if row is None:
                raise NotFoundError("Attempt not found")
            if row["submitted_at"]:
                return json.loads(row["responses_json"])["report"]
            snapshot = json.loads(row["snapshot_json"])
            started = datetime.fromisoformat(row["server_started_at"])
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
            claimed = max(0, int(client_duration_seconds))
            ceiling = elapsed + DURATION_GRACE_SECONDS
            duration, clamped = min(claimed, ceiling), int(claimed > ceiling)
            results, score = [], 0
            for index, question in enumerate(snapshot):
                given = str(responses.get(question["question_id"])
                            or responses.get(question["version_id"])
                            or responses.get(str(index)) or "")
                accepted = {normalise_answer(question["answer"]),
                            *[normalise_answer(a) for a in question.get("aliases", [])]}
                correct = bool(normalise_answer(given)) and normalise_answer(given) in accepted
                score += int(correct)
                results.append({
                    "question_id": question["question_id"],
                    "question_version_id": question["version_id"],
                    "question": question["question"], "response": given, "correct": correct,
                    "answer": question["answer"], "explanation": question.get("explanation", ""),
                    "specialty": question.get("specialty", ""), "match_method": "exact_or_alias"})
            total = len(snapshot) or 1
            report = {
                "attempt_id": attempt_id, "score": score, "total": len(snapshot),
                "percentage": round(score / total * 100, 1), "results": results,
                "duration_seconds": duration, "timing_clamped": bool(clamped),
                "timing_source": "practice",
                "limitations": [
                    "Marked against the answer key stored when this attempt started.",
                    "Exact/alias matching only; differently phrased free text may be marked wrong.",
                    "Practice timing; this is not a validated or invigilated assessment.",
                ]}
            conn.execute(
                "UPDATE exam_attempts SET responses_json=?, submitted_at=?, duration_seconds=?, "
                "client_duration_seconds=?, timing_clamped=?, score=?, percentage=? WHERE attempt_id=?",
                (json.dumps({"responses": responses, "report": report}, ensure_ascii=False),
                 _now(), duration, claimed, clamped, score, report["percentage"], attempt_id))
        return report

    def attempt_report(self, attempt_id: str) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute("SELECT responses_json, submitted_at FROM exam_attempts "
                               "WHERE attempt_id=?", (attempt_id,)).fetchone()
            if row is None:
                raise NotFoundError("Attempt not found")
            if not row["submitted_at"]:
                raise GovernanceError("This attempt has not been submitted")
            return json.loads(row["responses_json"])["report"]

    def stats(self) -> dict[str, Any]:
        with self.transaction() as conn:
            attempts = conn.execute("SELECT COUNT(*) n FROM exam_attempts "
                                    "WHERE submitted_at IS NOT NULL").fetchone()["n"]
            mean = conn.execute("SELECT AVG(percentage) m FROM exam_attempts "
                                "WHERE submitted_at IS NOT NULL").fetchone()["m"]
            rows = conn.execute("SELECT responses_json FROM exam_attempts "
                                "WHERE submitted_at IS NOT NULL").fetchall()
            osce_rows = conn.execute(
                "SELECT snapshot_json, correct FROM osce_attempts"
            ).fetchall()
        by_specialty: dict[str, dict[str, int]] = {}
        for row in rows:
            for item in json.loads(row["responses_json"])["report"]["results"]:
                bucket = by_specialty.setdefault(item["specialty"] or "General medicine",
                                                 {"correct": 0, "total": 0})
                bucket["total"] += 1
                bucket["correct"] += int(item["correct"])
        osce_by_kind: dict[str, dict[str, int]] = {}
        for row in osce_rows:
            try:
                snapshot = json.loads(row["snapshot_json"] or "{}")
            except (TypeError, ValueError):
                snapshot = {}
            kind = str(snapshot.get("kind") or "OSCE")
            bucket = osce_by_kind.setdefault(kind, {"correct": 0, "total": 0})
            bucket["total"] += 1
            bucket["correct"] += int(row["correct"])
        return {"exam_attempts": int(attempts),
                "mean_percentage": round(float(mean), 1) if mean is not None else None,
                "by_specialty": [{"specialty": k, "correct": v["correct"], "total": v["total"],
                                  "percentage": round(v["correct"] / v["total"] * 100, 1)}
                                 for k, v in sorted(by_specialty.items())],
                "osce_attempts": int(len(osce_rows)),
                "osce_by_kind": [{"kind": k, "correct": v["correct"], "total": v["total"],
                                  "percentage": round(v["correct"] / v["total"] * 100, 1)}
                                 for k, v in sorted(osce_by_kind.items())],
                "scope": "Question-bank performance only; not clinical competence."}
