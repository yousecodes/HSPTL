"""Conservative, review-first clinical entity proposal extraction for UCKS.

This deterministic starter recognises a deliberately small terminology lexicon.
It proposes mentions; it does not diagnose, infer relationships, or validate evidence.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any

LEXICON = [
    ("acute kidney injury", "condition", "SNOMED CT", ""),
    ("chronic kidney disease", "condition", "SNOMED CT", ""),
    ("myocardial infarction", "condition", "SNOMED CT", ""),
    ("heart failure", "condition", "SNOMED CT", ""),
    ("pneumonia", "condition", "SNOMED CT", ""),
    ("pulmonary embolism", "condition", "SNOMED CT", ""),
    ("diabetes mellitus", "condition", "SNOMED CT", ""),
    ("hypertension", "condition", "SNOMED CT", ""),
    ("sepsis", "condition", "SNOMED CT", ""),
    ("chest pain", "symptom", "SNOMED CT", ""),
    ("shortness of breath", "symptom", "SNOMED CT", ""),
    ("dyspnoea", "symptom", "SNOMED CT", ""),
    ("dyspnea", "symptom", "SNOMED CT", ""),
    ("fever", "symptom", "SNOMED CT", ""),
    ("cough", "symptom", "SNOMED CT", ""),
    ("oliguria", "clinical_finding", "SNOMED CT", ""),
    ("hypotension", "clinical_finding", "SNOMED CT", ""),
    ("tachycardia", "clinical_finding", "SNOMED CT", ""),
    ("creatinine", "investigation", "LOINC", ""),
    ("serum creatinine", "investigation", "LOINC", ""),
    ("troponin", "investigation", "LOINC", ""),
    ("electrocardiogram", "investigation", "LOINC", ""),
    ("ecg", "investigation", "LOINC", ""),
    ("chest x-ray", "investigation", "LOINC", ""),
    ("blood culture", "investigation", "LOINC", ""),
    ("metformin", "medication", "RxNorm", ""),
    ("furosemide", "medication", "RxNorm", ""),
    ("aspirin", "medication", "RxNorm", ""),
    ("antibiotics", "treatment", "SNOMED CT", ""),
    ("oxygen therapy", "treatment", "SNOMED CT", ""),
    ("acute respiratory failure", "condition", "SNOMED CT", ""),
]
# Prefer longest terms first to avoid nested duplicate matches.
LEXICON.sort(key=lambda x: len(x[0]), reverse=True)

def extract_mentions(text: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return []
    matches = []
    occupied: list[tuple[int, int]] = []
    for term, entity_type, system, code in LEXICON:
        for match in re.finditer(r"(?<![\\w-])" + re.escape(term) + r"(?![\\w-])", text, re.I):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            occupied.append((match.start(), match.end()))
            start, end = max(0, match.start()-100), min(len(text), match.end()+100)
            context = re.sub(r"\\s+", " ", text[start:end]).strip()
            left = text[max(0, match.start()-45):match.start()].lower()
            left = re.split(r"[.!?;\n]", left)[-1]
            polarity = "absent" if re.search(r"\b(no|not|without|denies|negative for|absence of)\s*$", left) else "present"
            matches.append({"surface": match.group(0), "normalized_label": term,
                            "entity_type": entity_type, "terminology_system": system,
                            "terminology_code": code, "polarity": polarity, "context": context})
    matches.sort(key=lambda x: text.lower().find(x["surface"].lower()))
    return matches

def propose_document_entities(repo, document_id: str) -> dict[str, int]:
    with repo.store.transaction() as conn:
        doc = conn.execute("SELECT id,current_version FROM ucks_documents WHERE id=?", (document_id,)).fetchone()
        if not doc:
            raise ValueError("Unknown UCKS document")
        version = conn.execute("SELECT body FROM ucks_document_versions WHERE document_id=? AND version=?",
                               (document_id, doc["current_version"])).fetchone()
        body = version["body"] if version else ""
        mentions = extract_mentions(body)
        added = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for item in mentions:
            chunk = conn.execute("""SELECT id FROM ucks_chunks WHERE document_id=? AND version=?
                AND instr(lower(body), lower(?)) > 0 ORDER BY ordinal LIMIT 1""",
                (document_id, doc["current_version"], item["surface"])).fetchone()
            cur = conn.execute("""INSERT OR IGNORE INTO ucks_entity_proposals
                (id,document_id,chunk_id,surface,normalized_label,entity_type,terminology_system,
                 terminology_code,polarity,context,status,extraction_method,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'pending','curated_lexicon_v1',?)""",
                ("entp_" + __import__("uuid").uuid4().hex, document_id,
                 chunk["id"] if chunk else None, item["surface"], item["normalized_label"],
                 item["entity_type"], item["terminology_system"], item["terminology_code"],
                 item["polarity"], item["context"], now))
            added += cur.rowcount
        return {"document_id": document_id, "mentions_seen": len(mentions), "proposals_added": added}

def list_proposals(repo, *, status: str = "pending", document_id: str = "", limit: int = 100):
    if status not in {"pending", "accepted", "rejected", "all"}:
        raise ValueError("Unsupported proposal status")
    limit = max(1, min(int(limit), 500))
    sql = "SELECT * FROM ucks_entity_proposals"
    params = []
    clauses = []
    if status != "all":
        clauses.append("status=?"); params.append(status)
    if document_id:
        clauses.append("document_id=?"); params.append(document_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"; params.append(limit)
    with repo.store.transaction() as conn:
        return [dict(row) for row in conn.execute(sql, params)]

def review_proposal(repo, proposal_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"accept", "reject"}:
        raise ValueError("Decision must be accept or reject")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT * FROM ucks_entity_proposals WHERE id=?", (proposal_id,)).fetchone()
        if not row:
            raise ValueError("Unknown entity proposal")
        if row["status"] != "pending":
            raise ValueError("Entity proposal has already been reviewed")
        status = "accepted" if decision == "accept" else "rejected"
        conn.execute("UPDATE ucks_entity_proposals SET status=?, reviewed_at=? WHERE id=?",
                     (status, now, proposal_id))
        node_id = ""
        if decision == "accept":
            # Accepted concepts enter the graph as nodes only. No relationships are inferred.
            graph_type = {"clinical_finding": "finding", "medication": "drug"}.get(row["entity_type"], row["entity_type"])
            existing = conn.execute("""SELECT id FROM ucks_graph_nodes WHERE node_type=?
                AND terminology_system=? AND terminology_code=? AND label=?""",
                (graph_type, row["terminology_system"], row["terminology_code"],
                 row["normalized_label"])).fetchone()
            if existing:
                node_id = existing["id"]
            else:
                node_id = "node_" + __import__("uuid").uuid4().hex
                conn.execute("""INSERT INTO ucks_graph_nodes
                    (id,label,node_type,terminology_system,terminology_code,metadata_json,created_at)
                    VALUES(?,?,?,?,?,'{}',?)""",
                    (node_id, row["normalized_label"], graph_type,
                     row["terminology_system"], row["terminology_code"], now))
        result = dict(row); result["status"] = status; result["graph_node_id"] = node_id
        return result
