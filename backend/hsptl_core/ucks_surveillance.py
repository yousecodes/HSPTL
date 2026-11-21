"""Conservative publisher-change and evidence-age surveillance proposals.

Signals are never applied automatically: reviewers decide document lifecycle changes.
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone, timedelta


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id():
    return "chg_" + uuid.uuid4().hex

CHANGE_PATTERNS = {
    "retraction": re.compile(r"\b(retract(?:ed|ion)?|withdrawn|withdrawal of publication)\b", re.I),
    "correction": re.compile(r"\b(correct(?:ed|ion|ion notice)?|erratum|corrigendum)\b", re.I),
    "expression_of_concern": re.compile(r"\b(expression of concern)\b", re.I),
    "guideline_update": re.compile(r"\b(updated guideline|guideline update|new version of guideline)\b", re.I),
}


def initialise_surveillance(store):
    with store.transaction() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ucks_source_change_events (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL, document_id TEXT NOT NULL DEFAULT '',
            external_id TEXT NOT NULL DEFAULT '', event_type TEXT NOT NULL,
            signal_text TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending', reviewer_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_ucks_change_queue ON ucks_source_change_events(status,created_at);
        CREATE TABLE IF NOT EXISTS ucks_staleness_flags (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL, age_days INTEGER NOT NULL,
            threshold_days INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '', reviewer_note TEXT NOT NULL DEFAULT '',
            UNIQUE(document_id,threshold_days)
        );
        CREATE INDEX IF NOT EXISTS idx_ucks_stale_queue ON ucks_staleness_flags(status,age_days);
        """)
        conn.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(25,?)", (_now(),))


def detect_feed_change(store, source_id: str, entry: dict) -> dict | None:
    text = " ".join(str(entry.get(k, "")) for k in ("title", "body", "category"))
    event_type = next((kind for kind, pattern in CHANGE_PATTERNS.items() if pattern.search(text)), None)
    if not event_type:
        return None
    external_id = str(entry.get("external_id", ""))
    url = str(entry.get("url", ""))
    with store.transaction() as conn:
        doc = conn.execute("""SELECT id FROM ucks_documents WHERE source_id=? AND
            (external_id=? OR (source_url=? AND ?!='')) ORDER BY updated_at DESC LIMIT 1""",
            (source_id, external_id, url, url)).fetchone()
        document_id = doc["id"] if doc else ""
        existing = conn.execute("""SELECT id FROM ucks_source_change_events WHERE source_id=?
            AND external_id=? AND event_type=? AND status='pending'""",
            (source_id, external_id, event_type)).fetchone()
        if existing:
            return {"id": existing["id"], "event_type": event_type, "document_id": document_id, "created": False}
        event_id = _id()
        conn.execute("""INSERT INTO ucks_source_change_events
            (id,source_id,document_id,external_id,event_type,signal_text,source_url,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", (event_id,source_id,document_id,external_id,event_type,
                text[:2000],url,_now()))
    return {"id": event_id, "event_type": event_type, "document_id": document_id, "created": True}


def list_change_events(store, status="pending", limit=100):
    with store.transaction() as conn:
        rows=conn.execute("""SELECT e.*,d.title AS document_title FROM ucks_source_change_events e
            LEFT JOIN ucks_documents d ON d.id=e.document_id
            WHERE (?='all' OR e.status=?) ORDER BY e.created_at DESC LIMIT ?""",
            (status,status,max(1,min(int(limit),500)))).fetchall()
    return [dict(r) for r in rows]


def review_change_event(store, repo, event_id: str, decision: str, note: str="", replacement_document_id: str=""):
    if decision not in {"confirm_retraction","confirm_superseded","confirm_correction","dismiss"}:
        raise ValueError("Unsupported source-change decision")
    with store.transaction() as conn:
        row=conn.execute("SELECT * FROM ucks_source_change_events WHERE id=?",(event_id,)).fetchone()
        if not row: raise ValueError("Unknown source-change event")
        if row["status"] != "pending": raise ValueError("Source-change event has already been reviewed")
        if decision != "dismiss" and not row["document_id"]:
            raise ValueError("No matching document; link the publisher event to a document before confirming")
        if decision == "confirm_superseded" and not replacement_document_id:
            raise ValueError("A replacement document ID is required")
        if replacement_document_id:
            replacement=repo.get_document(replacement_document_id)
            if not replacement: raise ValueError("Replacement document not found")
            if row["document_id"] and replacement_document_id == row["document_id"]:
                raise ValueError("A document cannot supersede itself")
        conn.execute("UPDATE ucks_source_change_events SET status=?,reviewer_note=?,reviewed_at=? WHERE id=?",
            (decision,note[:2000],_now(),event_id))
    if decision == "confirm_retraction":
        repo.set_lifecycle_state(row["document_id"],"retracted")
    elif decision == "confirm_superseded":
        repo.set_lifecycle_state(row["document_id"],"superseded",superseding_document_id=replacement_document_id)
    elif decision == "confirm_correction":
        repo.set_lifecycle_state(row["document_id"],"corrected")
    return {"id":event_id,"status":decision,"document_id":row["document_id"]}


def scan_staleness(store, max_age_days: int=1095, content_type: str="guideline"):
    threshold=max(30,min(int(max_age_days),3650))
    cutoff=(datetime.now(timezone.utc)-timedelta(days=threshold)).date().isoformat()
    with store.transaction() as conn:
        rows=conn.execute("""SELECT id,publication_date FROM ucks_documents WHERE content_type=?
            AND lifecycle_state='current' AND publication_date!='' AND substr(publication_date,1,10)<?""",
            (content_type,cutoff)).fetchall()
        created=[]
        for row in rows:
            try: age=(datetime.now(timezone.utc).date()-datetime.fromisoformat(row['publication_date'][:10]).date()).days
            except ValueError: continue
            flag_id="stl_"+uuid.uuid4().hex
            cur=conn.execute("""INSERT OR IGNORE INTO ucks_staleness_flags
                (id,document_id,age_days,threshold_days,created_at) VALUES(?,?,?,?,?)""",
                (flag_id,row['id'],age,threshold,_now()))
            if cur.rowcount: created.append(flag_id)
    return {"scanned":len(rows),"flags_created":len(created),"threshold_days":threshold,"content_type":content_type}


def list_staleness_flags(store,status="pending",limit=100):
    with store.transaction() as conn:
        rows=conn.execute("""SELECT f.*,d.title,d.publication_date,d.jurisdiction FROM ucks_staleness_flags f
            JOIN ucks_documents d ON d.id=f.document_id WHERE (?='all' OR f.status=?)
            ORDER BY f.age_days DESC LIMIT ?""",(status,status,max(1,min(int(limit),500)))).fetchall()
    return [dict(r) for r in rows]


def review_staleness_flag(store, flag_id, decision, note=""):
    if decision not in {"reviewed_current","needs_update","dismiss"}: raise ValueError("Unsupported staleness decision")
    with store.transaction() as conn:
        row=conn.execute("SELECT id,status FROM ucks_staleness_flags WHERE id=?",(flag_id,)).fetchone()
        if not row: raise ValueError("Unknown staleness flag")
        if row['status']!='pending': raise ValueError("Staleness flag has already been reviewed")
        conn.execute("UPDATE ucks_staleness_flags SET status=?,reviewer_note=?,reviewed_at=? WHERE id=?",
            (decision,note[:2000],_now(),flag_id))
    return {"id":flag_id,"status":decision}
