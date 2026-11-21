"""Shared tag catalogue and cross-workspace content index for HSPTL."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .store import StudyStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Stable IDs are persisted; display labels may be localised without breaking links.
DEFAULT_TAGS: list[dict[str, Any]] = []


def _add(facet: str, labels: list[str], aliases: dict[str, list[str]] | None = None) -> None:
    aliases = aliases or {}
    for label in labels:
        slug = "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in label).split())
        DEFAULT_TAGS.append({
            "tag_id": f"{facet}.{slug}", "facet": facet, "label": label,
            "aliases": aliases.get(label, []),
        })


_add("specialty", [
    "General Medicine", "Cardiology", "Respiratory", "Neurology", "Gastroenterology",
    "Nephrology", "Endocrinology", "Haematology", "Infectious Diseases", "Rheumatology",
    "Dermatology", "Ophthalmology", "ENT", "Orthopaedics", "Paediatrics",
    "Obstetrics and Gynaecology", "Psychiatry", "Emergency Medicine", "Radiology", "Pathology",
])
_add("system", [
    "Cardiovascular", "Respiratory", "Neurological", "Gastrointestinal", "Renal",
    "Endocrine", "Haematological", "Musculoskeletal", "Integumentary", "Reproductive",
    "Infectious", "Multisystem",
])
_add("presentation", [
    "Chest Pain", "Dyspnoea", "Syncope", "Fever", "Abdominal Pain", "Headache", "Weakness",
    "Rash", "Joint Pain", "Altered Mental Status", "Bleeding", "Oedema",
], {"Dyspnoea": ["Dyspnea", "Shortness of breath"], "Oedema": ["Edema"]})
_add("task", [
    "Diagnosis", "Differential Diagnosis", "Investigation", "Management", "Interpretation",
    "Communication", "Procedure", "Prevention", "Clinical Reasoning",
])
_add("modality", [
    "Clinical Photo", "ECG", "X-ray", "CT and MRI", "Ultrasound", "Histopathology",
    "Laboratory Results", "Fundoscopy", "Spirometry", "Clinical Examination",
])
_add("setting", ["Emergency", "Outpatient", "Inpatient", "Critical Care", "Primary Care"])
_add("competency", [
    "Clinical Reasoning", "Data Interpretation", "Communication", "Procedural Skills",
    "Patient Safety", "Evidence Appraisal", "Prioritisation",
])
_add("difficulty", ["Foundational", "Intermediate", "Advanced"])
_add("level", ["Preclinical", "Clinical Years", "Postgraduate"])


class TagRepository:
    def __init__(self, store: StudyStore):
        self.store = store

    def seed(self) -> None:
        now = _now()
        with self.store.transaction() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO learning_tags
                   (tag_id, facet, label, aliases_json, vocabulary, active, created_at)
                   VALUES (?, ?, ?, ?, 'hsptl_local', 1, ?)""",
                [(x["tag_id"], x["facet"], x["label"], json.dumps(x["aliases"]), now)
                 for x in DEFAULT_TAGS],
            )

    def catalogue(self, facet: str | None = None) -> list[dict[str, Any]]:
        self.seed()
        with self.store.transaction() as conn:
            if facet:
                rows = conn.execute(
                    "SELECT * FROM learning_tags WHERE active=1 AND facet=? ORDER BY label", (facet,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM learning_tags WHERE active=1 ORDER BY facet, label"
                ).fetchall()
        return [{**dict(row), "aliases": json.loads(row["aliases_json"])} for row in rows]

    def register_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.seed()
        tag_ids = list(dict.fromkeys(payload["tags"]))
        if not 1 <= len(tag_ids) <= 12:
            raise ValueError("Provide between 1 and 12 tags for each content item.")
        item_id = ""
        now = _now()
        with self.store.transaction() as conn:
            marks = ",".join("?" for _ in tag_ids)
            known = {row[0] for row in conn.execute(
                f"SELECT tag_id FROM learning_tags WHERE active=1 AND tag_id IN ({marks})", tag_ids
            ).fetchall()}
            unknown = sorted(set(tag_ids) - known)
            if unknown:
                raise ValueError("Unknown tag IDs: " + ", ".join(unknown))
            row = conn.execute(
                "SELECT item_id FROM tagged_content_items WHERE content_type=? AND content_id=?",
                (payload["content_type"], payload["content_id"]),
            ).fetchone()
            item_id = row[0] if row else str(uuid.uuid4())
            conn.execute(
                """INSERT INTO tagged_content_items
                   (item_id, content_type, content_id, title, workspace, summary, source_status, content_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(content_type, content_id) DO UPDATE SET
                     title=excluded.title, workspace=excluded.workspace, summary=excluded.summary,
                     source_status=excluded.source_status, content_url=excluded.content_url,
                     updated_at=excluded.updated_at""",
                (item_id, payload["content_type"], payload["content_id"], payload["title"],
                 payload["workspace"], payload.get("summary", ""), payload.get("source_status", "unreviewed"),
                 payload.get("content_url", ""), now),
            )
            conn.execute("DELETE FROM content_tag_links WHERE item_id=?", (item_id,))
            conn.executemany(
                "INSERT INTO content_tag_links(item_id, tag_id, assigned_by, assigned_at) VALUES (?, ?, ?, ?)",
                [(item_id, tag_id, payload.get("assigned_by", "learner"), now) for tag_id in tag_ids],
            )
        return self.content_item(item_id)

    def content_item(self, item_id: str) -> dict[str, Any]:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM tagged_content_items WHERE item_id=?", (item_id,)).fetchone()
            if not row:
                raise KeyError(item_id)
            tags = conn.execute(
                """SELECT t.tag_id, t.facet, t.label FROM content_tag_links l
                   JOIN learning_tags t ON t.tag_id=l.tag_id WHERE l.item_id=? ORDER BY t.facet, t.label""",
                (item_id,),
            ).fetchall()
        return {**dict(row), "tags": [dict(tag) for tag in tags]}

    def search_content(self, *, tag_ids: list[str] | None = None, workspace: str | None = None,
                       query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        self.seed()
        clauses: list[str] = []
        params: list[Any] = []
        if workspace:
            clauses.append("c.workspace=?"); params.append(workspace)
        if query.strip():
            clauses.append("(c.title LIKE ? OR c.summary LIKE ?)")
            params.extend([f"%{query.strip()}%", f"%{query.strip()}%"])
        tag_ids = list(dict.fromkeys(tag_ids or []))
        if tag_ids:
            marks = ",".join("?" for _ in tag_ids)
            clauses.append(f"c.item_id IN (SELECT item_id FROM content_tag_links WHERE tag_id IN ({marks}) GROUP BY item_id HAVING COUNT(DISTINCT tag_id)=?)")
            params.extend(tag_ids); params.append(len(tag_ids))
        sql = "SELECT c.item_id FROM tagged_content_items c"
        if clauses: sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY c.updated_at DESC LIMIT ?"; params.append(max(1, min(int(limit), 250)))
        with self.store.transaction() as conn:
            ids = [row[0] for row in conn.execute(sql, params).fetchall()]
        return [self.content_item(item_id) for item_id in ids]

    def record_event(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self.store.transaction() as conn:
            if not conn.execute("SELECT 1 FROM tagged_content_items WHERE item_id=?", (item_id,)).fetchone():
                raise KeyError(item_id)
            event_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO tag_learning_events
                   (event_id, item_id, action, score, max_score, confidence, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (event_id, item_id, payload["action"], payload.get("score"), payload.get("max_score"),
                 payload.get("confidence", ""), now),
            )
        return {"event_id": event_id, "item_id": item_id, "action": payload["action"], "occurred_at": now}

    def analytics(self) -> list[dict[str, Any]]:
        self.seed()
        with self.store.transaction() as conn:
            rows = conn.execute(
                """SELECT t.tag_id, t.facet, t.label, COUNT(DISTINCT c.item_id) AS content_count,
                          COUNT(e.event_id) AS event_count, AVG(CASE WHEN e.max_score>0
                             THEN 100.0*e.score/e.max_score END) AS mean_score,
                          MAX(e.occurred_at) AS last_practised
                   FROM learning_tags t
                   LEFT JOIN content_tag_links l ON l.tag_id=t.tag_id
                   LEFT JOIN tagged_content_items c ON c.item_id=l.item_id
                   LEFT JOIN tag_learning_events e ON e.item_id=c.item_id
                   WHERE t.active=1 GROUP BY t.tag_id ORDER BY t.facet, t.label"""
            ).fetchall()
        return [dict(row) for row in rows]
