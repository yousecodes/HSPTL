"""Review-first extraction of narrowly defined, explicit clinical relations.

Only direct lexical patterns are proposed. Co-occurrence, causality, and
unobserved relations are never inferred. Every proposal retains source context.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .ucks_entities import extract_mentions

# Explicit relation phrases and graph predicates. Direction is left mention -> right mention.
RELATION_PATTERNS = (
    (re.compile(r"\b(?:presents?\s+with|presented\s+with|associated\s+with)\b", re.I), "presents_with"),
    (re.compile(r"\btreated\s+with\b", re.I), "treated_with"),
    (re.compile(r"\binvestigated\s+by\b", re.I), "investigated_by"),
    (re.compile(r"\bcomplicated\s+by\b", re.I), "complicated_by"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sentences(body: str):
    # Retain bounded sentence fragments; this is intentionally not a full parser.
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", body):
        value = match.group(0).strip()
        if value:
            yield match.start(), match.end(), value


def extract_relationships(body: str) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for start, end, sentence in _sentences(body):
        mentions = extract_mentions(sentence)
        if len(mentions) < 2:
            continue
        # Resolve exact mention offsets within the sentence; longest-term entity extraction
        # already suppresses overlapping surface forms.
        located = []
        cursor = 0
        for mention in mentions:
            pos = sentence.lower().find(mention["surface"].lower(), cursor)
            if pos < 0:
                pos = sentence.lower().find(mention["surface"].lower())
            if pos >= 0:
                located.append((pos, pos + len(mention["surface"]), mention))
                cursor = pos + len(mention["surface"])
        located.sort(key=lambda item: item[0])
        for left, right in zip(located, located[1:]):
            between = sentence[left[1]:right[0]]
            for pattern, predicate in RELATION_PATTERNS:
                if pattern.search(between):
                    # Avoid encoding explicitly negated relationships as positive edges.
                    prefix = sentence[:left[0]].lower()
                    relation_prefix = between[:pattern.search(between).start()].lower()
                    negated = bool(re.search(r"\b(no|not|without|denies|negative for|absence of)\s*$", prefix)) or bool(re.search(r"\b(not|never|without)\s*$", relation_prefix))
                    uncertain = bool(re.search(r"\b(may|might|could|possibly|possible|suspected|疑似)\b", sentence, re.I))
                    proposals.append({
                        "subject_label": left[2]["normalized_label"],
                        "subject_type": left[2]["entity_type"],
                        "predicate": predicate,
                        "object_label": right[2]["normalized_label"],
                        "object_type": right[2]["entity_type"],
                        "context": sentence[:1000],
                        "assertion_status": "negated" if negated else ("uncertain" if uncertain else "asserted"),
                    })
                    break
    return proposals


def propose_document_relationships(repo, document_id: str) -> dict[str, int]:
    with repo.store.transaction() as conn:
        doc = conn.execute("SELECT id,current_version FROM ucks_documents WHERE id=?", (document_id,)).fetchone()
        if not doc:
            raise ValueError("Unknown UCKS document")
        version = conn.execute(
            "SELECT body FROM ucks_document_versions WHERE document_id=? AND version=?",
            (document_id, doc["current_version"]),
        ).fetchone()
        body = version["body"] if version else ""
        proposals = extract_relationships(body)
        added = 0
        now = _now()
        for item in proposals:
            chunk = conn.execute(
                "SELECT id FROM ucks_chunks WHERE document_id=? AND version=? AND instr(lower(body),lower(?))>0 ORDER BY ordinal LIMIT 1",
                (document_id, doc["current_version"], item["context"][:80]),
            ).fetchone()
            cur = conn.execute("""INSERT OR IGNORE INTO ucks_relationship_proposals
                (id,document_id,chunk_id,subject_label,subject_type,predicate,object_label,object_type,
                 context,assertion_status,status,extraction_method,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'pending','explicit_pattern_v1',?)""",
                ("relp_" + uuid.uuid4().hex, document_id, chunk["id"] if chunk else None,
                 item["subject_label"], item["subject_type"], item["predicate"],
                 item["object_label"], item["object_type"], item["context"],
                 item["assertion_status"], now))
            added += cur.rowcount
        return {"document_id": document_id, "relationships_seen": len(proposals), "proposals_added": added}


def list_relationship_proposals(repo, *, status: str = "pending", document_id: str = "", limit: int = 100):
    if status not in {"pending", "accepted", "rejected", "all"}:
        raise ValueError("Unsupported proposal status")
    limit = max(1, min(int(limit), 500))
    clauses, params = [], []
    if status != "all":
        clauses.append("status=?"); params.append(status)
    if document_id:
        clauses.append("document_id=?"); params.append(document_id)
    sql = "SELECT * FROM ucks_relationship_proposals"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
    with repo.store.transaction() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def review_relationship_proposal(repo, proposal_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"accept", "reject"}:
        raise ValueError("Decision must be accept or reject")
    now = _now()
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT * FROM ucks_relationship_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise ValueError("Unknown relationship proposal")
        if row["status"] != "pending":
            raise ValueError("Relationship proposal has already been reviewed")
        edge_id = ""
        if decision == "accept":
            if row["assertion_status"] != "asserted":
                raise ValueError("Only asserted relationship proposals can be accepted as graph edges")
            # A reviewer must first accept both source-linked concepts.
            subject = conn.execute("""SELECT id FROM ucks_graph_nodes WHERE label=? AND node_type=?
                ORDER BY created_at LIMIT 1""", (row["subject_label"], _graph_type(row["subject_type"]))).fetchone()
            obj = conn.execute("""SELECT id FROM ucks_graph_nodes WHERE label=? AND node_type=?
                ORDER BY created_at LIMIT 1""", (row["object_label"], _graph_type(row["object_type"]))).fetchone()
            if not subject or not obj:
                raise ValueError("Accept both linked entity proposals before accepting this relationship")
            edge_id = "ke_" + uuid.uuid4().hex
            conn.execute("""INSERT OR IGNORE INTO ucks_graph_edges
                (id,subject_id,predicate,object_id,document_id,evidence_note,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (edge_id, subject["id"], row["predicate"], obj["id"], row["document_id"], row["context"][:1000], now))
            edge = conn.execute("""SELECT id FROM ucks_graph_edges WHERE subject_id=? AND predicate=?
                AND object_id=? AND document_id=?""",
                (subject["id"], row["predicate"], obj["id"], row["document_id"])).fetchone()
            edge_id = edge["id"] if edge else edge_id
        status = "accepted" if decision == "accept" else "rejected"
        conn.execute("UPDATE ucks_relationship_proposals SET status=?,reviewed_at=?,graph_edge_id=? WHERE id=?",
                     (status, now, edge_id, proposal_id))
        result = dict(row); result.update(status=status, graph_edge_id=edge_id)
        return result


def _graph_type(entity_type: str) -> str:
    return {
        "clinical_finding": "finding", "medication": "drug",
        "condition": "condition", "symptom": "symptom",
        "investigation": "investigation", "treatment": "treatment",
    }.get(entity_type, entity_type)
