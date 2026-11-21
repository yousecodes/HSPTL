"""LearningEpisode: the audit spine linking a case attempt to its artifacts.

Additive. Existing tables are untouched; the episode connects them.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .migrations import apply as apply_migrations
from .source_refs import SourceRef, normalise_refs

SOURCE_TYPES = {"fhir_encounter", "curated_case", "exam_attempt", "pearl_review", "puzzle_run"}
ARTIFACT_KINDS = {"representation", "plan", "differential", "reflection", "feedback",
                  "pearl", "card", "debrief", "exam_response"}
PROVENANCE_STATES = {"source_documented", "curated", "learner_authored", "mixed"}


class NotFoundError(KeyError):
    pass


class ConflictError(RuntimeError):
    """Optimistic-concurrency conflict; the client must reload before saving."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class EpisodeRepository:
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

    @staticmethod
    def _episode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["draft"] = json.loads(item.pop("draft_json") or "{}")
        except (TypeError, ValueError):
            item["draft"] = {}
        return item

    @staticmethod
    def _artifact(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        try:
            item["body"] = json.loads(item.pop("body_json") or "{}")
        except (TypeError, ValueError):
            item["body"] = {}
        return item

    def start_or_resume(self, *, source_type: str, source_id: str, profile_id: str = "local",
                        idempotency_key: str = "", learning_goal: str = "", specialty: str = "",
                        jurisdiction: str = "", provenance_status: str = "source_documented",
                        content_version_id: str = "") -> dict[str, Any]:
        if source_type not in SOURCE_TYPES:
            raise ValueError("Unsupported episode source type")
        if provenance_status not in PROVENANCE_STATES:
            raise ValueError("Unsupported provenance status")
        if not str(source_id).strip():
            raise ValueError("An episode requires a source id")
        now = _now()
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM learning_episodes WHERE profile_id=? AND source_type=? "
                "AND source_id=? AND idempotency_key=?",
                (profile_id, source_type, source_id, idempotency_key)).fetchone()
            if existing:
                conn.execute("UPDATE learning_episodes SET updated_at=? WHERE episode_id=?",
                             (now, existing["episode_id"]))
                return {**self._episode(existing), "resumed": True}
            episode_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO learning_episodes (episode_id,profile_id,source_type,source_id,"
                "content_version_id,status,learning_goal,specialty,jurisdiction,"
                "provenance_status,idempotency_key,started_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (episode_id, profile_id, source_type, source_id, content_version_id, "active",
                 learning_goal[:200], specialty[:80], jurisdiction[:60], provenance_status,
                 idempotency_key[:80], now, now))
            row = conn.execute("SELECT * FROM learning_episodes WHERE episode_id=?",
                               (episode_id,)).fetchone()
            return {**self._episode(row), "resumed": False}

    def get(self, episode_id: str) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM learning_episodes WHERE episode_id=?",
                               (episode_id,)).fetchone()
            if row is None:
                raise NotFoundError("Learning episode not found")
            return self._episode(row)

    def list(self, *, status: str | None = None, limit: int = 30, offset: int = 0,
             profile_id: str = "local") -> dict[str, Any]:
        limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
        where, params = ["profile_id=?"], [profile_id]
        if status:
            where.append("status=?")
            params.append(status)
        clause = " AND ".join(where)
        with self.transaction() as conn:
            total = conn.execute(f"SELECT COUNT(*) n FROM learning_episodes WHERE {clause}",
                                 params).fetchone()["n"]
            rows = conn.execute(
                f"SELECT * FROM learning_episodes WHERE {clause} "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
            return {"total": int(total), "limit": limit, "offset": offset,
                    "items": [self._episode(r) for r in rows]}

    def latest_active(self, profile_id: str = "local") -> dict[str, Any] | None:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM learning_episodes WHERE profile_id=? AND status='active' "
                "ORDER BY updated_at DESC LIMIT 1", (profile_id,)).fetchone()
            return self._episode(row) if row else None

    def save_draft(self, episode_id: str, draft: dict[str, Any], *,
                   expected_revision: int | None = None,
                   stage: int | None = None) -> dict[str, Any]:
        """Autosave drafts only. Final attempts and cards are never autosaved."""
        body = json.dumps(draft, ensure_ascii=False)[:200_000]
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT draft_revision, status FROM learning_episodes WHERE episode_id=?",
                (episode_id,)).fetchone()
            if row is None:
                raise NotFoundError("Learning episode not found")
            if row["status"] != "active":
                raise ConflictError("This episode is closed; start a new episode to continue")
            if expected_revision is not None and int(row["draft_revision"]) != int(expected_revision):
                raise ConflictError("The draft changed in another view; reload before saving")
            revision = int(row["draft_revision"]) + 1
            conn.execute(
                "UPDATE learning_episodes SET draft_json=?, draft_revision=?, "
                "stage=COALESCE(?, stage), updated_at=? WHERE episode_id=?",
                (body, revision, stage, _now(), episode_id))
            return {"episode_id": episode_id, "draft_revision": revision, "saved": True}

    def set_status(self, episode_id: str, status: str) -> dict[str, Any]:
        if status not in {"active", "completed", "abandoned"}:
            raise ValueError("Unsupported episode status")
        now = _now()
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE learning_episodes SET status=?, updated_at=?, completed_at=? "
                "WHERE episode_id=?",
                (status, now, now if status == "completed" else None, episode_id))
            if cursor.rowcount == 0:
                raise NotFoundError("Learning episode not found")
        return self.get(episode_id)

    def add_artifact(self, episode_id: str, kind: str, body: dict[str, Any], *,
                     authored_by: str = "learner", verification_status: str = "unverified",
                     source_refs: Iterable[Any] | None = None) -> dict[str, Any]:
        if kind not in ARTIFACT_KINDS:
            raise ValueError("Unsupported artifact kind")
        if authored_by not in {"learner", "curator", "system"}:
            raise ValueError("Unsupported artifact author")
        if authored_by == "learner" and verification_status == "verified":
            raise ValueError("Learner-authored artifacts cannot be marked verified")
        digest, refs, now = _hash(body), normalise_refs(source_refs), _now()
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM learning_episodes WHERE episode_id=?",
                            (episode_id,)).fetchone() is None:
                raise NotFoundError("Learning episode not found")
            existing = conn.execute(
                "SELECT * FROM learning_artifacts WHERE episode_id=? AND kind=? AND content_hash=?",
                (episode_id, kind, digest)).fetchone()
            if existing:
                self._write_sources(conn, "artifact", existing["artifact_id"], refs)
                return {**self._artifact(existing), "created": False}
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version),0) v FROM learning_artifacts "
                "WHERE episode_id=? AND kind=?", (episode_id, kind)).fetchone()["v"]) + 1
            artifact_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO learning_artifacts (artifact_id,episode_id,kind,body_json,"
                "authored_by,verification_status,version,content_hash,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (artifact_id, episode_id, kind, json.dumps(body, ensure_ascii=False),
                 authored_by, verification_status, version, digest, now))
            self._write_sources(conn, "artifact", artifact_id, refs)
            conn.execute("UPDATE learning_episodes SET updated_at=? WHERE episode_id=?",
                         (now, episode_id))
            row = conn.execute("SELECT * FROM learning_artifacts WHERE artifact_id=?",
                               (artifact_id,)).fetchone()
            return {**self._artifact(row), "created": True}

    def artifacts(self, episode_id: str) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM learning_artifacts WHERE episode_id=? "
                                "ORDER BY created_at", (episode_id,)).fetchall()
            return [self._artifact(r) for r in rows]

    def _write_sources(self, conn: sqlite3.Connection, owner_kind: str, owner_id: str,
                       refs: list[SourceRef]) -> None:
        for position, ref in enumerate(refs):
            conn.execute(
                "INSERT INTO source_refs (ref_id,kind,locator,title,citation,retrieved_at,"
                "jurisdiction,license,review_date,verified,snapshot_hash,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(ref_id) DO UPDATE SET "
                "title=excluded.title, citation=excluded.citation, license=excluded.license, "
                "review_date=excluded.review_date, verified=excluded.verified",
                (ref.ref_id, ref.kind.value, ref.locator, ref.title, ref.citation,
                 ref.retrieved_at, ref.jurisdiction, ref.license, ref.review_date,
                 int(ref.verified), ref.snapshot_hash, _now()))
            conn.execute(
                "INSERT OR IGNORE INTO content_sources(owner_kind,owner_id,ref_id,position) "
                "VALUES(?,?,?,?)", (owner_kind, owner_id, ref.ref_id, position))

    def attach_sources(self, owner_kind: str, owner_id: str,
                       refs: Iterable[Any]) -> list[dict[str, Any]]:
        normalised = normalise_refs(refs)
        with self.transaction() as conn:
            self._write_sources(conn, owner_kind, owner_id, normalised)
        return [r.to_dict() for r in normalised]

    def sources_for(self, owner_kind: str, owner_id: str) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT s.* FROM source_refs s JOIN content_sources c ON c.ref_id=s.ref_id "
                "WHERE c.owner_kind=? AND c.owner_id=? ORDER BY c.position",
                (owner_kind, owner_id)).fetchall()
        return [SourceRef(kind=r["kind"], locator=r["locator"], title=r["title"],
                          citation=r["citation"], retrieved_at=r["retrieved_at"],
                          jurisdiction=r["jurisdiction"], license=r["license"],
                          verified=bool(r["verified"]), review_date=r["review_date"],
                          snapshot_hash=r["snapshot_hash"]).to_dict() for r in rows]

    def link(self, parent_kind: str, parent_id: str, child_kind: str, child_id: str,
             relation: str = "derived_from") -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO artifact_links "
                "(parent_kind,parent_id,child_kind,child_id,relation,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (parent_kind, parent_id, child_kind, child_id, relation, _now()))

    def children(self, parent_kind: str, parent_id: str) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM artifact_links WHERE parent_kind=? "
                                "AND parent_id=? ORDER BY created_at",
                                (parent_kind, parent_id)).fetchall()
            return [dict(r) for r in rows]

    def lineage(self, episode_id: str) -> dict[str, Any]:
        artifacts = self.artifacts(episode_id)
        for artifact in artifacts:
            artifact["sources"] = self.sources_for("artifact", artifact["artifact_id"])
            artifact["children"] = self.children("artifact", artifact["artifact_id"])
        return {"episode": self.get(episode_id), "artifacts": artifacts}
