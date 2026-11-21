"""Read-only UCKS governance and ingestion monitoring snapshot."""
from __future__ import annotations
from typing import Any

TABLES = {
    "ucks_documents", "ucks_sources", "ucks_entity_proposals", "ucks_relationship_proposals",
    "ucks_terminology_candidates", "ucks_terminology_concepts", "ucks_evidence_appraisals",
    "ucks_conflict_flags", "ucks_source_change_events", "ucks_staleness_flags",
    "ucks_connector_runs", "ucks_connector_schedule", "ucks_connector_checkpoints",
    "ucks_feed_audit", "ucks_feed_schedule", "ucks_feed_state", "ucks_embeddings",
}

def governance_snapshot(store, repo, *, limit: int = 20) -> dict[str, Any]:
    limit=max(1,min(int(limit),100))
    with store.transaction() as conn:
        existing={r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def columns(table):
            return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")} if table in existing else set()
        def count(table, where="1=1", params=()):
            if table not in existing: return 0
            return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}",params).fetchone()[0])
        def grouped(table, column):
            if table not in existing or column not in columns(table): return {}
            return {str(r[0] or "unknown"):int(r[1]) for r in conn.execute(f"SELECT {column},COUNT(*) FROM {table} GROUP BY {column}")}
        doc_review=grouped("ucks_documents","review_status")
        lifecycle=grouped("ucks_documents","lifecycle_state")
        content_types=grouped("ucks_documents","content_type")
        source_types=grouped("ucks_sources","source_type")
        rights={"reuse_permitted_sources":count("ucks_sources","reuse_permitted=1"),
                "sources_without_declared_licence":count("ucks_sources","COALESCE(licence,'')=''"),
                "documents_without_declared_licence":count("ucks_documents","COALESCE(licence,'')=''")}
        queues={}
        queue_previews={}
        for table in ("ucks_entity_proposals","ucks_relationship_proposals","ucks_terminology_candidates","ucks_source_change_events","ucks_staleness_flags","ucks_conflict_flags"):
            cols=columns(table)
            status_col="status" if "status" in cols else ("review_status" if "review_status" in cols else "")
            queues[table]={"total":count(table),"by_status":grouped(table,status_col) if status_col else {}}
            if table in existing:
                order_col="created_at" if "created_at" in cols else ("detected_at" if "detected_at" in cols else "rowid")
                queue_previews[table]=[dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY {order_col} ASC LIMIT ?",(min(limit,10),))]
        latest_runs=[]
        if "ucks_connector_runs" in existing:
            cols=columns("ucks_connector_runs")
            order="started_at" if "started_at" in cols else "rowid"
            latest_runs=[dict(r) for r in conn.execute(f"SELECT * FROM ucks_connector_runs ORDER BY {order} DESC LIMIT ?",(limit,))]
        schedules=[]
        if "ucks_connector_schedule" in existing:
            schedules=[dict(r) for r in conn.execute("SELECT * FROM ucks_connector_schedule ORDER BY source_id LIMIT ?",(limit,))]
        feed_audit=[]
        if "ucks_feed_audit" in existing:
            cols=columns("ucks_feed_audit"); order="created_at" if "created_at" in cols else "rowid"
            feed_audit=[dict(r) for r in conn.execute(f"SELECT * FROM ucks_feed_audit ORDER BY {order} DESC LIMIT ?",(limit,))]
        evidence_appraisals={"total":count("ucks_evidence_appraisals"),
                             "by_status":grouped("ucks_evidence_appraisals","status"),
                             "by_study_design":grouped("ucks_evidence_appraisals","study_design"),
                             "historical_snapshots":count("ucks_evidence_appraisal_history")}
        rights_reviews={"total":count("ucks_rights_reviews"),"by_decision":grouped("ucks_rights_reviews","decision")}
        review_backlog=[]
        if "ucks_documents" in existing:
            review_backlog=[dict(r) for r in conn.execute("""SELECT d.id,d.title,d.content_type,d.specialty,d.publication_date,
                d.created_at,d.review_status,d.licence,s.name AS source_name
                FROM ucks_documents d LEFT JOIN ucks_sources s ON s.id=d.source_id
                WHERE d.review_status IN ('harvested','reviewed')
                ORDER BY d.created_at ASC LIMIT ?""",(limit,))]
        rights_review_count=0
        if "ucks_documents" in existing and "ucks_sources" in existing:
            rights_review_count=int(conn.execute("""SELECT COUNT(*) FROM ucks_documents d
                LEFT JOIN ucks_sources s ON s.id=d.source_id
                WHERE (COALESCE(d.licence,'')='' AND COALESCE(s.licence,'')='')
                   OR d.provenance_json LIKE '%provider_metadata_requires_verification%'
                   OR d.provenance_json LIKE '%unknown_requires_manual_review%'
                   OR d.provenance_json LIKE '%blocked_unverified_rights%'
                   OR d.provenance_json LIKE '%allowlisted_full_text_pending_human_review%'""").fetchone()[0])
        rights_review_queue=[]
        if "ucks_documents" in existing:
            rights_review_queue=[dict(r) for r in conn.execute("""SELECT d.id,d.title,d.content_type,d.created_at,d.licence,
                d.review_status,s.name AS source_name,s.licence AS source_licence,s.reuse_permitted
                FROM ucks_documents d LEFT JOIN ucks_sources s ON s.id=d.source_id
                WHERE (COALESCE(d.licence,'')='' AND COALESCE(s.licence,'')='')
                   OR d.provenance_json LIKE '%provider_metadata_requires_verification%'
                   OR d.provenance_json LIKE '%unknown_requires_manual_review%'
                   OR d.provenance_json LIKE '%blocked_unverified_rights%'
                   OR d.provenance_json LIKE '%allowlisted_full_text_pending_human_review%'
                ORDER BY d.created_at ASC LIMIT ?""",(limit,))]
        source_document_summary=[]
        if "ucks_documents" in existing:
            source_document_summary=[dict(r) for r in conn.execute("""SELECT s.id AS source_id,s.name,
                COUNT(d.id) AS documents,
                SUM(CASE WHEN d.review_status='harvested' THEN 1 ELSE 0 END) AS harvested,
                SUM(CASE WHEN d.review_status='machine_screened' THEN 1 ELSE 0 END) AS machine_screened,
                SUM(CASE WHEN d.review_status='reviewed' THEN 1 ELSE 0 END) AS reviewed,
                SUM(CASE WHEN d.review_status='validated' THEN 1 ELSE 0 END) AS validated,
                SUM(CASE WHEN d.review_status='rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN COALESCE(d.licence,'')='' THEN 1 ELSE 0 END) AS missing_document_licence
                FROM ucks_sources s LEFT JOIN ucks_documents d ON d.source_id=s.id
                GROUP BY s.id,s.name ORDER BY documents DESC LIMIT ?""",(limit,))]
    sources=repo.list_sources()
    source_summary=[]
    for source in sources:
        source_summary.append({"id":source["id"],"name":source["name"],"source_type":source["source_type"],
            "enabled":source.get("enabled",True),"reuse_permitted":source.get("reuse_permitted",False),
            "licence_declared":bool(source.get("licence")),"locator":source.get("locator","")})
    return {"documents":{"total":sum(doc_review.values()),"review_status":doc_review,
                          "lifecycle_state":lifecycle,"content_types":content_types},
            "sources":{"total":len(sources),"by_type":source_types,"items":source_summary},
            "rights_and_provenance":rights,
            "rights_reviews":rights_reviews,
            "governance_queues":queues,
            "governance_queue_previews":queue_previews,
            "rights_review_queue":{"count":rights_review_count,"unresolved_oldest_first":rights_review_queue},
            "evidence_appraisals":evidence_appraisals,
            "review_backlog":{"count":len(review_backlog),"oldest_first":review_backlog},
            "source_document_summary":source_document_summary,
            "connectors":{"scheduled":schedules,"recent_runs":latest_runs,
                           "failed_runs":sum(1 for x in latest_runs if str(x.get("status","")).lower() in {"failed","error"})},
            "feed_sync":{"recent_audit":feed_audit},
            "retrieval":{"chunks":repo.stats().get("chunks",0),
                         "legacy_embedding_rows":repo.stats().get("embeddings",0),
                         "embedding_inference_enabled":False,
                         "vector_status":"disabled_model_free"},
            "policy":{"imported_content_default":"harvested","automatic_validation":False,
                      "rejected_content_excluded_from_learning_workspaces":True,
                      "retrieval_relevance_is_not_evidence_quality":True}}
