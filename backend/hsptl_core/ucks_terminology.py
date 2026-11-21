"""Review-first terminology catalogue and exact-match mapping for UCKS.

The catalogue is populated only from explicitly supplied, provenance-bearing
records. This module does not call public terminology servers, invent codes,
or treat lexical similarity as clinical equivalence.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

SUPPORTED_SYSTEMS = {"SNOMEDCT", "LOINC", "ICD10CM", "RxNorm"}
MAX_RECORDS = 50_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.+/-]", " ", str(value or "").casefold())).strip()


def _validate_record(item: dict[str, Any]) -> dict[str, Any]:
    system = str(item.get("system", "")).strip()
    code = str(item.get("code", "")).strip()
    display = str(item.get("display", "")).strip()
    version = str(item.get("version", "")).strip()
    publisher = str(item.get("publisher", "")).strip()
    source_url = str(item.get("source_url", "")).strip()
    licence = str(item.get("licence", "")).strip()
    if system not in SUPPORTED_SYSTEMS:
        raise ValueError(f"Unsupported terminology system: {system or '(blank)'}")
    if not code or len(code) > 128 or not display or len(display) > 500:
        raise ValueError("Each concept requires a code (max 128) and display (max 500)")
    if not version or len(version) > 80:
        raise ValueError("Each concept requires a terminology release/version")
    if not publisher or not licence:
        raise ValueError("Publisher and licence metadata are required")
    if source_url and not source_url.lower().startswith("https://"):
        raise ValueError("Terminology source_url must use HTTPS")
    aliases = item.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, list) or len(aliases) > 100:
        raise ValueError("aliases must be a list containing at most 100 strings")
    aliases = sorted({_normalise(str(alias)) for alias in aliases if _normalise(str(alias))})
    aliases = [a for a in aliases if len(a) <= 500]
    return {
        "system": system, "code": code, "display": display, "version": version,
        "publisher": publisher, "source_url": source_url, "licence": licence,
        "reuse_permitted": bool(item.get("reuse_permitted", False)),
        "redistribution_permitted": bool(item.get("redistribution_permitted", False)),
        "jurisdiction": str(item.get("jurisdiction", "global")).strip()[:120] or "global",
        "aliases": aliases,
    }


def import_catalogue(repo, records: Iterable[dict[str, Any]], *, import_name: str,
                     source_reference: str = "") -> dict[str, Any]:
    rows = list(records)
    if not rows or len(rows) > MAX_RECORDS:
        raise ValueError(f"Import must contain between 1 and {MAX_RECORDS} concepts")
    if not import_name.strip() or len(import_name) > 160:
        raise ValueError("import_name is required (max 160)")
    validated = [_validate_record(row) for row in rows]
    now = _now()
    added = updated = 0
    with repo.store.transaction() as conn:
        for row in validated:
            concept_id = "tc_" + uuid.uuid4().hex
            aliases_json = json.dumps(row["aliases"], ensure_ascii=False)
            existing = conn.execute(
                "SELECT id FROM ucks_terminology_concepts WHERE system=? AND code=? AND version=?",
                (row["system"], row["code"], row["version"]),
            ).fetchone()
            if existing:
                prior = conn.execute("SELECT * FROM ucks_terminology_concepts WHERE id=?", (existing["id"],)).fetchone()
                unchanged = (
                    prior["display"] == row["display"] and prior["publisher"] == row["publisher"]
                    and prior["source_url"] == row["source_url"] and prior["licence"] == row["licence"]
                    and bool(prior["reuse_permitted"]) == row["reuse_permitted"]
                    and bool(prior["redistribution_permitted"]) == row["redistribution_permitted"]
                    and prior["jurisdiction"] == row["jurisdiction"]
                    and prior["aliases_json"] == aliases_json
                )
                if not unchanged:
                    raise ValueError("Terminology concepts are immutable within a release; import changed content under a new version")
                updated += 1
            else:
                conn.execute("""INSERT INTO ucks_terminology_concepts
                    (id,system,code,display,version,publisher,source_url,licence,reuse_permitted,
                     redistribution_permitted,jurisdiction,aliases_json,review_status,import_name,
                     source_reference,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'unreviewed',?,?,?,?)""",
                    (concept_id, row["system"], row["code"], row["display"], row["version"],
                     row["publisher"], row["source_url"], row["licence"], int(row["reuse_permitted"]),
                     int(row["redistribution_permitted"]), row["jurisdiction"], aliases_json,
                     import_name, source_reference, now, now))
                added += 1
    return {"import_name": import_name, "records_seen": len(validated), "records_added": added,
            "records_updated": updated, "review_status": "unreviewed"}


def list_catalogue(repo, *, system: str = "", status: str = "all", limit: int = 100) -> list[dict[str, Any]]:
    if status not in {"all", "unreviewed", "approved", "rejected"}:
        raise ValueError("Unsupported terminology catalogue status")
    if system and system not in SUPPORTED_SYSTEMS:
        raise ValueError("Unsupported terminology system")
    limit = max(1, min(int(limit), 500))
    clauses, params = [], []
    if system:
        clauses.append("system=?"); params.append(system)
    if status != "all":
        clauses.append("review_status=?"); params.append(status)
    sql = "SELECT * FROM ucks_terminology_concepts"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY system,display LIMIT ?"; params.append(limit)
    with repo.store.transaction() as conn:
        result = []
        for row in conn.execute(sql, params):
            item = dict(row)
            item["aliases"] = json.loads(item.pop("aliases_json"))
            result.append(item)
        return result


def review_catalogue_concept(repo, concept_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject")
    now = _now()
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT * FROM ucks_terminology_concepts WHERE id=?", (concept_id,)).fetchone()
        if not row:
            raise ValueError("Unknown terminology concept")
        if row["review_status"] != "unreviewed":
            raise ValueError("Terminology concept has already been reviewed")
        status = "approved" if decision == "approve" else "rejected"
        conn.execute("UPDATE ucks_terminology_concepts SET review_status=?,reviewed_at=?,updated_at=? WHERE id=?",
                     (status, now, now, concept_id))
        result = dict(row); result.update(review_status=status, reviewed_at=now)
        return result


def propose_entity_mappings(repo, *, document_id: str = "", system: str = "") -> dict[str, int]:
    if system and system not in SUPPORTED_SYSTEMS:
        raise ValueError("Unsupported terminology system")
    clauses, params = ["ep.status IN ('pending','accepted')"], []
    if document_id:
        clauses.append("ep.document_id=?"); params.append(document_id)
    if system:
        clauses.append("tc.system=?"); params.append(system)
    sql = """SELECT ep.*,tc.id AS concept_id,tc.system AS concept_system,tc.code AS concept_code,
        tc.display AS concept_display,tc.version AS concept_version,tc.jurisdiction AS concept_jurisdiction,
        tc.review_status AS concept_status,tc.aliases_json FROM ucks_entity_proposals ep
        JOIN ucks_terminology_concepts tc ON tc.review_status IN ('unreviewed','approved')
            AND tc.reuse_permitted=1
        WHERE """ + " AND ".join(clauses)
    added = 0
    now = _now()
    with repo.store.transaction() as conn:
        entities = conn.execute(sql, params).fetchall()
        for entity in entities:
            entity_terms = {_normalise(entity["surface"]), _normalise(entity["normalized_label"])}
            concept_aliases = {_normalise(entity["concept_display"])}
            concept_aliases.update(json.loads(entity["aliases_json"]))
            if not entity_terms.intersection(concept_aliases):
                continue
            # Jurisdiction mismatch is not silently ignored; global concepts are portable only
            # as a terminology concept, not as a claim of local clinical guidance.
            candidate_id = "tmc_" + uuid.uuid4().hex
            cur = conn.execute("""INSERT OR IGNORE INTO ucks_terminology_candidates
                (id,entity_proposal_id,concept_id,match_method,match_score,review_status,
                 concept_review_status,created_at)
                VALUES(?,?,?,'exact_alias',1.0,'pending',?,?)""",
                (candidate_id, entity["id"], entity["concept_id"], entity["concept_status"], now))
            added += cur.rowcount
    with repo.store.transaction() as conn:
        total = conn.execute("SELECT COUNT(*) FROM ucks_terminology_candidates WHERE review_status='pending'").fetchone()[0]
    return {"candidates_added": added, "pending_candidates": int(total)}


def list_mapping_candidates(repo, *, status: str = "pending", document_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
    if status not in {"pending", "accepted", "rejected", "all"}:
        raise ValueError("Unsupported mapping candidate status")
    limit = max(1, min(int(limit), 500))
    clauses, params = [], []
    if status != "all":
        clauses.append("mc.review_status=?"); params.append(status)
    if document_id:
        clauses.append("ep.document_id=?"); params.append(document_id)
    sql = """SELECT mc.*,ep.document_id,ep.surface,ep.normalized_label,ep.entity_type,
        tc.system,tc.code,tc.display,tc.version,tc.publisher,tc.source_url,tc.licence,
        tc.reuse_permitted,tc.redistribution_permitted,tc.jurisdiction,tc.review_status AS concept_status
        FROM ucks_terminology_candidates mc
        JOIN ucks_entity_proposals ep ON ep.id=mc.entity_proposal_id
        JOIN ucks_terminology_concepts tc ON tc.id=mc.concept_id"""
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY mc.created_at DESC LIMIT ?"; params.append(limit)
    with repo.store.transaction() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def review_mapping_candidate(repo, candidate_id: str, decision: str) -> dict[str, Any]:
    if decision not in {"accept", "reject"}:
        raise ValueError("Decision must be accept or reject")
    now = _now()
    with repo.store.transaction() as conn:
        row = conn.execute("""SELECT mc.*,ep.status AS entity_status,tc.system,tc.code,tc.display,
            tc.review_status AS concept_status FROM ucks_terminology_candidates mc
            JOIN ucks_entity_proposals ep ON ep.id=mc.entity_proposal_id
            JOIN ucks_terminology_concepts tc ON tc.id=mc.concept_id WHERE mc.id=?""",
            (candidate_id,)).fetchone()
        if not row:
            raise ValueError("Unknown terminology mapping candidate")
        if row["review_status"] != "pending":
            raise ValueError("Terminology mapping candidate has already been reviewed")
        if decision == "accept" and row["concept_status"] != "approved":
            raise ValueError("Approve the terminology catalogue concept before accepting its mapping")
        if decision == "accept" and row["entity_status"] not in {"pending", "accepted"}:
            raise ValueError("Rejected entity proposals cannot receive terminology mappings")
        if decision == "accept":
            current = conn.execute("SELECT terminology_system,terminology_code FROM ucks_entity_proposals WHERE id=?",
                                   (row["entity_proposal_id"],)).fetchone()
            if current["terminology_code"] and (current["terminology_system"], current["terminology_code"]) != (row["system"], row["code"]):
                raise ValueError("This entity already has a terminology mapping; resolve the existing mapping before adding another")
        status = "accepted" if decision == "accept" else "rejected"
        conn.execute("UPDATE ucks_terminology_candidates SET review_status=?,reviewed_at=? WHERE id=?",
                     (status, now, candidate_id))
        if decision == "accept":
            conn.execute("""UPDATE ucks_entity_proposals SET terminology_system=?,terminology_code=?
                WHERE id=?""", (row["system"], row["code"], row["entity_proposal_id"]))
            # If the entity was already accepted, attach the reviewed code to its graph node.
            if row["entity_status"] == "accepted":
                entity = conn.execute("SELECT normalized_label,entity_type FROM ucks_entity_proposals WHERE id=?",
                                      (row["entity_proposal_id"],)).fetchone()
                graph_type = {"clinical_finding": "finding", "medication": "drug"}.get(entity["entity_type"], entity["entity_type"])
                conn.execute("""UPDATE ucks_graph_nodes SET terminology_system=?,terminology_code=?
                    WHERE node_type=? AND label=? AND terminology_code=''""",
                    (row["system"], row["code"], graph_type, entity["normalized_label"]))
        result = dict(row); result.update(review_status=status, reviewed_at=now)
        return result
