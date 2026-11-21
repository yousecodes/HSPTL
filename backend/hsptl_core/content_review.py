"""Content-quality queue and source-staleness propagation to derived cards.

A card whose source is flagged must not silently keep appearing as trusted
revision material. Enqueueing uses its own transaction, so it is always called
outside an open write transaction to avoid SQLite write-lock contention.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

REVIEW_INTERVAL_DAYS = 730


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ContentReviewService:
    def __init__(self, store):
        self.store = store

    def enqueue(self, owner_kind: str, owner_id: str, reason: str,
                severity: str = "warning", due_days: int = 30) -> str:
        item_id = str(uuid.uuid4())
        with self.store.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO content_review_items (item_id,owner_kind,owner_id,"
                "reason,severity,status,due_date,created_at) VALUES(?,?,?,?,?,'open',?,?)",
                (item_id, owner_kind, owner_id, reason, severity,
                 (date.today() + timedelta(days=due_days)).isoformat(), _now()))
        return item_id

    def _flag_note(self, note_id: str) -> None:
        with self.store.transaction() as conn:
            conn.execute("UPDATE study_notes SET review_status='needs_review' WHERE id=?",
                         (note_id,))
            conn.execute("UPDATE revision_cards SET needs_source_review=1, "
                         "state='needs_source_review' WHERE origin_note_id=?", (note_id,))

    def scan_note(self, note_id: str, note: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if note.get("sections") and not note.get("supported_sections"):
            reasons.append("no_source_supported_sections")
        for reference in note.get("references", []):
            if str(reference.get("kind", "")).startswith("Open-access") and not reference.get("license"):
                reasons.append("article_licence_unverified")
                break
        if note.get("generated_mode") != "learner_reflection_unverified":
            if not note.get("jurisdiction") or note.get("jurisdiction") == "Not specified":
                reasons.append("jurisdiction_unspecified")
        for reason in reasons:
            self.enqueue("note", note_id, reason)
        if reasons:
            self._flag_note(note_id)
        return reasons

    def flag_stale_sources(self, today: date | None = None) -> int:
        cutoff = ((today or date.today()) - timedelta(days=REVIEW_INTERVAL_DAYS)).isoformat()
        with self.store.transaction() as conn:
            rows = conn.execute(
                "SELECT id FROM study_notes WHERE review_status='verified' "
                "AND (review_date='' OR review_date<?)", (cutoff,)).fetchall()
            for row in rows:
                conn.execute("UPDATE study_notes SET review_status='needs_review' WHERE id=?",
                             (row["id"],))
                conn.execute("UPDATE revision_cards SET needs_source_review=1, "
                             "state='needs_source_review' WHERE origin_note_id=?", (row["id"],))
        for row in rows:  # separate transactions, after the write above has committed
            self.enqueue("note", row["id"], "source_review_overdue")
        return len(rows)

    def queue(self, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM content_review_items WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, max(1, min(int(limit), 200)))).fetchall()
        return [dict(r) for r in rows]

    def resolve(self, item_id: str, *, status: str, reviewer: str,
                review_date: str | None = None) -> dict[str, Any]:
        if status not in {"verified", "retired", "in_review", "open"}:
            raise ValueError("Unsupported review status")
        today = review_date or date.today().isoformat()
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM content_review_items WHERE item_id=?",
                               (item_id,)).fetchone()
            if row is None:
                raise KeyError("Review item not found")
            conn.execute("UPDATE content_review_items SET status=?, reviewer=?, resolved_at=? "
                         "WHERE item_id=?", (status, reviewer[:120], _now(), item_id))
            if row["owner_kind"] == "note":
                note_status = ("verified" if status == "verified"
                               else "retired" if status == "retired" else "needs_review")
                conn.execute("UPDATE study_notes SET review_status=?, review_date=? WHERE id=?",
                             (note_status, today if status == "verified" else "", row["owner_id"]))
                remaining = conn.execute(
                    "SELECT COUNT(*) n FROM content_review_items WHERE owner_kind='note' "
                    "AND owner_id=? AND status IN ('open','in_review')",
                    (row["owner_id"],)).fetchone()["n"]
                if remaining == 0 and status == "verified":
                    conn.execute(
                        "UPDATE revision_cards SET needs_source_review=0, "
                        "state=CASE WHEN state='needs_source_review' THEN 'review' ELSE state END "
                        "WHERE origin_note_id=?", (row["owner_id"],))
                elif status == "retired":
                    conn.execute("UPDATE revision_cards SET state='retired', suspended=1 "
                                 "WHERE origin_note_id=?", (row["owner_id"],))
        return {"item_id": item_id, "status": status}
