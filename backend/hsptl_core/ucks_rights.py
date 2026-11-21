"""Auditable human rights/reuse review; technical licence screening is not legal advice."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone

DECISIONS = {"permitted", "restricted", "needs_clarification"}

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _id(): return "rights_" + uuid.uuid4().hex

def initialise(repo):
    with repo.store.transaction() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ucks_rights_reviews (
          id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
          decision TEXT NOT NULL, licence TEXT NOT NULL DEFAULT '', licence_uri TEXT NOT NULL DEFAULT '',
          attribution TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT 'metadata_only',
          evidence_reference TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL,
          rationale TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ucks_rights_document ON ucks_rights_reviews(document_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_ucks_rights_decision ON ucks_rights_reviews(decision,created_at);
        """)

def review_rights(repo, document_id: str, data: dict):
    initialise(repo)
    if not repo.get_document(document_id): raise ValueError("Unknown UCKS document")
    decision=data.get("decision")
    if decision not in DECISIONS: raise ValueError("decision must be permitted, restricted or needs_clarification")
    reviewer=str(data.get("reviewer", "")).strip()
    if not reviewer: raise ValueError("A named reviewer is required")
    scope=data.get("scope", "metadata_only")
    if scope not in {"metadata_only","abstract_only","full_text_reuse","adaptation"}: raise ValueError("Unsupported rights scope")
    if decision == "permitted" and not str(data.get("licence", "")).strip():
        raise ValueError("A licence must be recorded for permitted reuse")
    rid=_id(); now=_now()
    with repo.store.transaction() as conn:
        conn.execute("INSERT INTO ucks_rights_reviews(id,document_id,decision,licence,licence_uri,attribution,scope,evidence_reference,reviewer,rationale,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (rid,document_id,decision,str(data.get("licence",""))[:300],str(data.get("licence_uri",""))[:2000],str(data.get("attribution",""))[:2000],scope,str(data.get("evidence_reference",""))[:2000],reviewer[:160],str(data.get("rationale",""))[:4000],now))
        row=conn.execute("SELECT * FROM ucks_rights_reviews WHERE id=?",(rid,)).fetchone()
    return dict(row)

def list_rights_reviews(repo, document_id: str):
    initialise(repo)
    with repo.store.transaction() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM ucks_rights_reviews WHERE document_id=? ORDER BY created_at DESC",(document_id,))]
