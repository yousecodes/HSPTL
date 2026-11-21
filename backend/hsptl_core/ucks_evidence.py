"""Structured evidence appraisal and potential-disagreement review.

This module deliberately stores appraisal domains separately; it does not
calculate a GRADE certainty rating or infer that discordant assertions are
scientific contradictions.
"""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone


def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _id(prefix): return f"{prefix}_{uuid.uuid4().hex}"

STUDY_DESIGNS = {"guideline", "systematic_review", "meta_analysis", "randomized_trial", "nonrandomized_trial", "cohort", "case_control", "cross_sectional", "diagnostic_accuracy", "case_series", "case_report", "qualitative", "dataset", "other", "not_reported"}
APPRAISAL_STATES = {"draft", "reviewed"}


def initialise(repo):
    with repo.store.transaction() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ucks_evidence_appraisals (
          id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
          study_design TEXT NOT NULL, sample_size INTEGER, population TEXT NOT NULL DEFAULT '',
          setting TEXT NOT NULL DEFAULT '', intervention TEXT NOT NULL DEFAULT '',
          comparator TEXT NOT NULL DEFAULT '', outcomes TEXT NOT NULL DEFAULT '',
          risk_of_bias TEXT NOT NULL DEFAULT 'not_assessed',
          imprecision TEXT NOT NULL DEFAULT 'not_assessed',
          inconsistency TEXT NOT NULL DEFAULT 'not_assessed',
          indirectness TEXT NOT NULL DEFAULT 'not_assessed',
          publication_bias TEXT NOT NULL DEFAULT 'not_assessed',
          limitations TEXT NOT NULL DEFAULT '', funding TEXT NOT NULL DEFAULT '',
          guideline_issuer TEXT NOT NULL DEFAULT '', recommendation_text TEXT NOT NULL DEFAULT '',
          recommendation_strength TEXT NOT NULL DEFAULT 'not_reported',
          certainty TEXT NOT NULL DEFAULT 'not_assessed', jurisdiction TEXT NOT NULL DEFAULT '',
          publication_date TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          UNIQUE(document_id)
        );
        CREATE TABLE IF NOT EXISTS ucks_conflict_flags (
          id TEXT PRIMARY KEY, concept TEXT NOT NULL, entity_type TEXT NOT NULL,
          document_a TEXT NOT NULL REFERENCES ucks_documents(id),
          document_b TEXT NOT NULL REFERENCES ucks_documents(id),
          assertion_a TEXT NOT NULL, assertion_b TEXT NOT NULL,
          context_a TEXT NOT NULL, context_b TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', reviewer TEXT NOT NULL DEFAULT '',
          review_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '',
          UNIQUE(concept, document_a, document_b, assertion_a, assertion_b)
        );
        CREATE INDEX IF NOT EXISTS idx_ucks_conflict_review ON ucks_conflict_flags(status,created_at);
        CREATE TABLE IF NOT EXISTS ucks_evidence_appraisal_history (
          id TEXT PRIMARY KEY, appraisal_id TEXT NOT NULL, document_id TEXT NOT NULL,
          snapshot_json TEXT NOT NULL, changed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ucks_appraisal_history ON ucks_evidence_appraisal_history(document_id,changed_at DESC);
        """)
        conn.execute("INSERT OR IGNORE INTO schema_migrations(version,applied_at) VALUES(25,?)", (_now(),))


def save_appraisal(repo, document_id: str, data: dict):
    initialise(repo)
    if not repo.get_document(document_id): raise ValueError("Unknown UCKS document")
    design = data.get("study_design", "not_reported")
    if design not in STUDY_DESIGNS: raise ValueError("Unsupported study design")
    status = data.get("status", "draft")
    if status not in APPRAISAL_STATES: raise ValueError("Appraisal status must be draft or reviewed")
    sample = data.get("sample_size")
    if sample is not None and (not isinstance(sample, int) or sample < 0): raise ValueError("sample_size must be a non-negative integer")
    fields = ["population","setting","intervention","comparator","outcomes","risk_of_bias","imprecision","inconsistency","indirectness","publication_bias","limitations","funding","guideline_issuer","recommendation_text","recommendation_strength","certainty","jurisdiction","publication_date","reviewer"]
    values = {k: str(data.get(k, ""))[:4000] for k in fields}
    now = _now()
    with repo.store.transaction() as conn:
        old = conn.execute("SELECT * FROM ucks_evidence_appraisals WHERE document_id=?", (document_id,)).fetchone()
        appraisal_id = old["id"] if old else _id("app")
        if old:
            conn.execute("INSERT INTO ucks_evidence_appraisal_history(id,appraisal_id,document_id,snapshot_json,changed_at) VALUES(?,?,?,?,?)",
                         (_id("apphist"), appraisal_id, document_id, json.dumps(dict(old), ensure_ascii=False), now))
        conn.execute("""INSERT INTO ucks_evidence_appraisals
          (id,document_id,study_design,sample_size,population,setting,intervention,comparator,outcomes,
           risk_of_bias,imprecision,inconsistency,indirectness,publication_bias,limitations,funding,
           guideline_issuer,recommendation_text,recommendation_strength,certainty,jurisdiction,publication_date,
           reviewer,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(document_id) DO UPDATE SET study_design=excluded.study_design,sample_size=excluded.sample_size,
           population=excluded.population,setting=excluded.setting,intervention=excluded.intervention,
           comparator=excluded.comparator,outcomes=excluded.outcomes,risk_of_bias=excluded.risk_of_bias,
           imprecision=excluded.imprecision,inconsistency=excluded.inconsistency,indirectness=excluded.indirectness,
           publication_bias=excluded.publication_bias,limitations=excluded.limitations,funding=excluded.funding,
           guideline_issuer=excluded.guideline_issuer,recommendation_text=excluded.recommendation_text,
           recommendation_strength=excluded.recommendation_strength,certainty=excluded.certainty,
           jurisdiction=excluded.jurisdiction,publication_date=excluded.publication_date,
           reviewer=excluded.reviewer,status=excluded.status,updated_at=excluded.updated_at""",
          (appraisal_id,document_id,design,sample,*[values[k] for k in fields],status,now,now))
        row=conn.execute("SELECT * FROM ucks_evidence_appraisals WHERE document_id=?",(document_id,)).fetchone()
    return dict(row)


def get_appraisal(repo, document_id):
    initialise(repo)
    with repo.store.transaction() as conn: row=conn.execute("SELECT * FROM ucks_evidence_appraisals WHERE document_id=?",(document_id,)).fetchone()
    return dict(row) if row else None


def detect_assertion_disagreements(repo, document_id: str):
    initialise(repo)
    if not repo.get_document(document_id): raise ValueError("Unknown UCKS document")
    created=[]
    with repo.store.transaction() as conn:
        proposals=conn.execute("""SELECT normalized_label,entity_type,polarity,context FROM ucks_entity_proposals
          WHERE document_id=? AND status='accepted' AND polarity IN ('present','absent')""",(document_id,)).fetchall()
        for p in proposals:
            opposite="absent" if p["polarity"]=="present" else "present"
            rows=conn.execute("""SELECT DISTINCT e.document_id,e.context FROM ucks_entity_proposals e
              JOIN ucks_documents d ON d.id=e.document_id
              WHERE e.normalized_label=? AND e.entity_type=? AND e.polarity=? AND e.status='accepted'
              AND e.document_id!=? AND d.lifecycle_state NOT IN ('retracted','superseded')""",
              (p["normalized_label"],p["entity_type"],opposite,document_id)).fetchall()
            for other in rows:
                a,b=sorted([document_id,other["document_id"]])
                pa,pb=(p["polarity"],opposite) if a==document_id else (opposite,p["polarity"])
                ca,cb=(p["context"],other["context"]) if a==document_id else (other["context"],p["context"])
                flag_id=_id("cf")
                cur=conn.execute("""INSERT OR IGNORE INTO ucks_conflict_flags
                  (id,concept,entity_type,document_a,document_b,assertion_a,assertion_b,context_a,context_b,created_at)
                  VALUES(?,?,?,?,?,?,?,?,?,?)""",(flag_id,p["normalized_label"],p["entity_type"],a,b,pa,pb,ca,cb,_now()))
                if cur.rowcount: created.append(flag_id)
    return {"created":len(created),"flag_ids":created,"notice":"Potential assertion disagreement only; context, population, timing and measurement differences require expert review."}


def list_disagreements(repo, status="pending", limit=100):
    initialise(repo)
    if status not in {"pending","confirmed","dismissed","all"}: raise ValueError("Unsupported disagreement status")
    with repo.store.transaction() as conn:
        sql="SELECT * FROM ucks_conflict_flags"; args=[]
        if status!="all": sql+=" WHERE status=?"; args.append(status)
        sql+=" ORDER BY created_at DESC LIMIT ?"; args.append(max(1,min(limit,200)))
        return [dict(r) for r in conn.execute(sql,args).fetchall()]


def review_disagreement(repo, flag_id, decision, reviewer="", note=""):
    initialise(repo)
    if decision not in {"confirm_disagreement","dismiss"}: raise ValueError("Decision must be confirm_disagreement or dismiss")
    with repo.store.transaction() as conn:
        row=conn.execute("SELECT id FROM ucks_conflict_flags WHERE id=?",(flag_id,)).fetchone()
        if not row: raise ValueError("Unknown disagreement flag")
        status="confirmed" if decision=="confirm_disagreement" else "dismissed"
        conn.execute("UPDATE ucks_conflict_flags SET status=?,reviewer=?,review_note=?,reviewed_at=? WHERE id=?",(status,reviewer[:160],note[:2000],_now(),flag_id))
        result=conn.execute("SELECT * FROM ucks_conflict_flags WHERE id=?",(flag_id,)).fetchone()
    return dict(result)


def list_appraisal_history(repo, document_id: str, limit: int = 50):
    initialise(repo)
    limit=max(1,min(int(limit),200))
    with repo.store.transaction() as conn:
        rows=conn.execute("SELECT * FROM ucks_evidence_appraisal_history WHERE document_id=? ORDER BY changed_at DESC LIMIT ?",(document_id,limit)).fetchall()
    return [{**dict(r), "snapshot": json.loads(r["snapshot_json"])} for r in rows]
