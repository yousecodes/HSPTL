"""Learner post-use feedback for approved, delivered learning artefacts.

Learner reports are quality signals, not clinical approvals or source-rights
permissions. Only a configured reviewer can triage/resolve them.
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..runtime import PATHS, INSTITUTIONAL_AUTH
from ..hsptl_core.generation_distribution import GenerationDistribution

router = APIRouter(prefix="/api/published-learning", tags=["published-learning-feedback"])
ENGINE = GenerationDistribution(PATHS["database"])
DB_PATH = Path(PATHS["database"])

FEEDBACK_CATEGORIES = {
    "factual_accuracy", "outdated_information", "missing_context", "unclear_explanation",
    "citation_or_source_problem", "accessibility_or_format", "technical_problem", "no_issue", "other",
}
RESOLUTION_STATES = {"acknowledged", "source_review_required", "artifact_revision_required", "closed"}
VALIDATION_DOMAINS = {"educational", "clinical", "sources", "assessment"}
VALIDATION_WEIGHTS = {"educational": 25, "clinical": 35, "sources": 20, "assessment": 20}
# Only institution-assigned training levels from password-backed sessions influence
# the evidence weighting. These are modest multipliers, not claims of competence.
LEVEL_WEIGHTS = {"student": 0.70, "intern": 0.82, "resident": 0.95, "registrar": 1.05,
                 "fellow": 1.12, "specialist": 1.18, "consultant": 1.22,
                 "faculty": 1.18, "unspecified": 0.60}
VALIDATION_TARGET_CONTRIBUTORS = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def _init() -> None:
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS learner_artifact_uses (
            usage_id TEXT PRIMARY KEY,
            artifact_id TEXT NOT NULL REFERENCES generated_artifacts(id),
            learner_id TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            completed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_learner_artifact_uses_artifact
            ON learner_artifact_uses(artifact_id, opened_at DESC);
        CREATE TABLE IF NOT EXISTS learner_artifact_feedback (
            feedback_id TEXT PRIMARY KEY,
            usage_id TEXT NOT NULL UNIQUE REFERENCES learner_artifact_uses(usage_id),
            artifact_id TEXT NOT NULL REFERENCES generated_artifacts(id),
            learner_id TEXT NOT NULL,
            rating INTEGER,
            educational_rating INTEGER,
            clinical_rating INTEGER,
            source_rating INTEGER,
            assessment_rating INTEGER,
            learner_level TEXT NOT NULL DEFAULT 'unspecified',
            account_role TEXT NOT NULL DEFAULT 'guest',
            identity_verified INTEGER NOT NULL DEFAULT 0,
            institution_id TEXT NOT NULL DEFAULT 'local',
            content_hash TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'routine',
            categories_json TEXT NOT NULL,
            source_document_ids_json TEXT NOT NULL DEFAULT '[]',
            comment TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            reviewer TEXT NOT NULL DEFAULT '',
            resolution TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            resolved_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_learner_feedback_status
            ON learner_artifact_feedback(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS learner_artifact_signoffs (
            signoff_id TEXT PRIMARY KEY,
            artifact_id TEXT NOT NULL REFERENCES generated_artifacts(id),
            content_hash TEXT NOT NULL,
            domain TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewer_role TEXT NOT NULL,
            reviewer_level TEXT NOT NULL,
            institution_id TEXT NOT NULL DEFAULT 'local',
            decision TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_artifact_signoffs_current
            ON learner_artifact_signoffs(artifact_id,content_hash,domain,created_at DESC);
        CREATE TABLE IF NOT EXISTS learner_feedback_audit (
            audit_id TEXT PRIMARY KEY,
            feedback_id TEXT NOT NULL,
            action TEXT NOT NULL,
            reviewer TEXT NOT NULL DEFAULT '',
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        """)
        use_columns = {row[1] for row in conn.execute("PRAGMA table_info(learner_artifact_uses)")}
        for name, ddl in {
            "completed_at": "TEXT NOT NULL DEFAULT ''",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
            "learner_level": "TEXT NOT NULL DEFAULT 'unspecified'",
            "account_role": "TEXT NOT NULL DEFAULT 'guest'",
            "identity_verified": "INTEGER NOT NULL DEFAULT 0",
            "institution_id": "TEXT NOT NULL DEFAULT 'local'",
        }.items():
            if name not in use_columns:
                conn.execute(f"ALTER TABLE learner_artifact_uses ADD COLUMN {name} {ddl}")
        feedback_columns = {row[1] for row in conn.execute("PRAGMA table_info(learner_artifact_feedback)")}
        for name, ddl in {
            "educational_rating": "INTEGER",
            "clinical_rating": "INTEGER",
            "source_rating": "INTEGER",
            "assessment_rating": "INTEGER",
            "learner_level": "TEXT NOT NULL DEFAULT 'unspecified'",
            "account_role": "TEXT NOT NULL DEFAULT 'guest'",
            "identity_verified": "INTEGER NOT NULL DEFAULT 0",
            "institution_id": "TEXT NOT NULL DEFAULT 'local'",
            "content_hash": "TEXT NOT NULL DEFAULT ''",
            "severity": "TEXT NOT NULL DEFAULT 'routine'",
        }.items():
            if name not in feedback_columns:
                conn.execute(f"ALTER TABLE learner_artifact_feedback ADD COLUMN {name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_learner_feedback_validation "
                     "ON learner_artifact_feedback(artifact_id,content_hash,identity_verified,created_at DESC)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_learner_feedback_one_verified_vote "
                     "ON learner_artifact_feedback(artifact_id,learner_id,content_hash) WHERE identity_verified=1")


_init()



def _session_principal(session_id: str, *, required_roles: set[str] | None = None) -> dict[str, Any] | None:
    if not session_id:
        return None
    roles = required_roles or {"learner", "facilitator", "reviewer", "admin"}
    try:
        return INSTITUTIONAL_AUTH.validate_session(session_id, roles)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(401, "A valid institutional sign-in is required for this validation action") from exc


def _validation_summary(artifact_id: str, content_hash: str) -> dict[str, Any]:
    with _connect() as conn:
        votes = conn.execute(
            """SELECT * FROM learner_artifact_feedback
               WHERE artifact_id=? AND content_hash=? AND identity_verified=1
                 AND educational_rating IS NOT NULL AND clinical_rating IS NOT NULL
                 AND source_rating IS NOT NULL AND assessment_rating IS NOT NULL
               ORDER BY created_at""", (artifact_id, content_hash),
        ).fetchall()
        signoff_rows = conn.execute(
            """SELECT * FROM learner_artifact_signoffs WHERE artifact_id=? AND content_hash=?
               ORDER BY created_at DESC, rowid DESC""", (artifact_id, content_hash),
        ).fetchall()
        critical_open = conn.execute(
            """SELECT COUNT(*) FROM learner_artifact_feedback
               WHERE artifact_id=? AND content_hash=? AND severity='critical' AND status!='closed'""",
            (artifact_id, content_hash),
        ).fetchone()[0]

    unique_voters: dict[str, dict[str, Any]] = {}
    dimension_scores: dict[str, float | None] = {}
    for domain in VALIDATION_DOMAINS:
        field = f"{domain}_rating" if domain != "sources" else "source_rating"
        applicable = [row for row in votes if row[field] is not None]
        if not applicable:
            dimension_scores[domain] = None
            continue
        weighted_total = 0.0
        total_weight = 0.0
        for vote in applicable:
            level = vote["learner_level"] or "unspecified"
            weight = LEVEL_WEIGHTS.get(level, LEVEL_WEIGHTS["unspecified"])
            score = (int(vote[field]) - 1) * 25.0
            weighted_total += score * weight
            total_weight += weight
            unique_voters[vote["learner_id"]] = {
                "learner_level": level,
                "account_role": vote["account_role"],
            }
        dimension_scores[domain] = round(weighted_total / total_weight, 1) if total_weight else None

    dimension_coverage = sum(value is not None for value in dimension_scores.values())
    quality_score = sum(
        (dimension_scores[domain] or 0.0) * VALIDATION_WEIGHTS[domain]
        for domain in VALIDATION_DOMAINS
    ) / 100.0
    contributor_count = len(unique_voters)
    evidence_coverage = min(1.0, contributor_count / VALIDATION_TARGET_CONTRIBUTORS)
    level_counts: dict[str, int] = {}
    for item in unique_voters.values():
        level_counts[item["learner_level"]] = level_counts.get(item["learner_level"], 0) + 1

    latest_signoffs: dict[str, dict[str, Any]] = {}
    for row in signoff_rows:
        domain = row["domain"]
        if domain not in latest_signoffs:
            latest_signoffs[domain] = {
                "decision": row["decision"], "reviewer_id": row["reviewer_id"],
                "reviewer_level": row["reviewer_level"], "reviewer_role": row["reviewer_role"],
                "note": row["note"], "created_at": row["created_at"],
            }
    approvals = {
        domain: latest_signoffs.get(domain, {"decision": "pending", "reviewer_id": "", "note": ""})
        for domain in sorted(VALIDATION_DOMAINS)
    }
    affirmed_domains = sum(approvals[domain]["decision"] == "affirmed" for domain in VALIDATION_DOMAINS)
    approval_coverage = affirmed_domains / len(VALIDATION_DOMAINS)
    all_signed = affirmed_domains == len(VALIDATION_DOMAINS)
    distinct_levels = len([k for k, v in level_counts.items() if k != "unspecified" and v])
    role_diversity_coverage = min(1.0, distinct_levels / 2.0)
    approval_factor = 0.70 + 0.30 * approval_coverage
    diversity_factor = 0.90 + 0.10 * role_diversity_coverage
    validation_percent = round(quality_score * evidence_coverage * approval_factor * diversity_factor)
    if critical_open:
        validation_percent = min(validation_percent, 49)
    revision_required = any(approvals[domain]["decision"] in {"revision_required", "rejected"}
                            for domain in VALIDATION_DOMAINS)
    if critical_open:
        state = "critical_review_pending"
    elif contributor_count == 0:
        state = "awaiting_post_use_evidence"
    elif revision_required:
        state = "revision_required"
    elif contributor_count < VALIDATION_TARGET_CONTRIBUTORS:
        state = "collecting_learner_evidence"
    elif not all_signed:
        state = "expert_signoff_pending"
    elif validation_percent < 90 or distinct_levels < 2:
        state = "validation_improvement_required"
    else:
        state = "validated"

    return {
        "validation_percent": validation_percent,
        "quality_score": round(quality_score, 1),
        "contributor_count": contributor_count,
        "target_contributors": VALIDATION_TARGET_CONTRIBUTORS,
        "evidence_coverage_percent": round(evidence_coverage * 100),
        "expert_signoff_coverage_percent": round(approval_coverage * 100),
        "role_diversity_coverage_percent": round(role_diversity_coverage * 100),
        "affirmed_domains": affirmed_domains,
        "dimension_coverage": dimension_coverage,
        "dimension_scores": dimension_scores,
        "training_level_counts": level_counts,
        "approvals": approvals,
        "all_domains_signed_off": all_signed,
        "open_critical_issues": int(critical_open),
        "state": state,
        "content_hash": content_hash,
        "method": "weighted quality × verified learner coverage × expert sign-off factor × learner-level diversity factor; unresolved critical issues cap the result at 49%",
        "weights": VALIDATION_WEIGHTS,
        "rating_scale": "1=0, 2=25, 3=50, 4=75, 5=100",
    }


def _signoff_authorisation(principal: dict[str, Any], domain: str) -> None:
    role = principal.get("role", "")
    level = principal.get("training_level", "unspecified")
    if domain == "clinical":
        if role not in {"reviewer", "admin"} or level not in {"specialist", "consultant"}:
            raise HTTPException(403, "Clinical sign-off requires an authenticated reviewer/admin with an institution-assigned specialist or consultant level")
    elif domain == "sources":
        if role not in {"reviewer", "admin"}:
            raise HTTPException(403, "Source sign-off requires an authenticated reviewer or administrator")
    elif domain in {"educational", "assessment"}:
        if role not in {"facilitator", "reviewer", "admin"} or level != "faculty":
            raise HTTPException(403, "Educational and assessment sign-off requires an authenticated faculty facilitator/reviewer")


def _published_artifact(artifact_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        routes = conn.execute(
            """SELECT r.id AS route_id,r.workspace,r.section,r.status AS route_status,
                      r.created_at AS distributed_at
               FROM distribution_routes r JOIN generated_artifacts a ON a.id=r.artifact_id
               WHERE r.artifact_id=? AND r.status='delivered' AND a.status='approved'
               ORDER BY r.created_at DESC""", (artifact_id,),
        ).fetchall()
    artifact = ENGINE.get_artifact(artifact_id)
    if not artifact or artifact.get("status") != "approved" or not routes:
        return None
    artifact["published_routes"] = [dict(row) for row in routes]
    artifact["validation"] = _validation_summary(artifact_id, str(artifact.get("content_hash") or ""))
    return artifact


class UseRequest(BaseModel):
    learner_id: str = Field(default="local-default", min_length=1, max_length=120)
    session_id: str = Field(default="", max_length=240)


class CompleteUseRequest(BaseModel):
    learner_id: str = Field(default="local-default", min_length=1, max_length=120)
    session_id: str = Field(default="", max_length=240)


class FeedbackRequest(BaseModel):
    usage_id: str = Field(min_length=8, max_length=120)
    learner_id: str = Field(default="local-default", min_length=1, max_length=120)
    session_id: str = Field(default="", max_length=240)
    rating: int | None = Field(default=None, ge=1, le=5)
    educational_rating: int | None = Field(default=None, ge=1, le=5)
    clinical_rating: int | None = Field(default=None, ge=1, le=5)
    source_rating: int | None = Field(default=None, ge=1, le=5)
    assessment_rating: int | None = Field(default=None, ge=1, le=5)
    severity: str = Field(default="routine", pattern="^(routine|major|critical)$")
    categories: list[str] = Field(min_length=1, max_length=8)
    source_document_ids: list[str] = Field(default_factory=list, max_length=20)
    comment: str = Field(default="", max_length=4000)


class SignoffRequest(BaseModel):
    domain: str
    decision: str
    note: str = Field(min_length=8, max_length=3000)


class ResolveRequest(BaseModel):
    status: str
    resolution: str = Field(min_length=3, max_length=2000)


def _reviewer(token: str | None) -> str:
    expected = os.environ.get("HSPTL_REVIEWER_TOKEN", "")
    reviewer = os.environ.get("HSPTL_REVIEWER_ID", "").strip()
    if len(expected) < 32 or not reviewer:
        raise HTTPException(503, "Reviewer authentication is not configured")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Valid reviewer credentials are required")
    return reviewer[:160]


@router.get("/artifacts")
def published_artifacts(workspace: str = "", limit: int = 100) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        rows = conn.execute(
            """SELECT DISTINCT a.id FROM generated_artifacts a
               JOIN distribution_routes r ON r.artifact_id=a.id
               WHERE a.status='approved' AND r.status='delivered'
                 AND (?='' OR r.workspace=? OR a.workspace=?)
               ORDER BY a.updated_at DESC LIMIT ?""",
            (workspace, workspace, workspace, safe_limit),
        ).fetchall()
    items = [item for row in rows if (item := _published_artifact(row["id"]))]
    return {"items": items, "count": len(items),
            "publication_rule": "approved artifact plus at least one delivered workspace route"}


@router.post("/artifacts/{artifact_id}/use", status_code=201)
def record_artifact_use(artifact_id: str, payload: UseRequest) -> dict[str, Any]:
    artifact = _published_artifact(artifact_id)
    if not artifact:
        raise HTTPException(404, "Published learning artefact not found")
    principal = _session_principal(payload.session_id)
    learner_id = str(principal["subject_id"]) if principal else payload.learner_id.strip()
    training_level = str(principal.get("training_level", "unspecified")) if principal else "unspecified"
    account_role = str(principal.get("role", "guest")) if principal else "guest"
    institution_id = str(principal.get("institution_id", "local")) if principal else "local"
    usage_id = "use_" + uuid.uuid4().hex
    with _connect() as conn:
        conn.execute(
            """INSERT INTO learner_artifact_uses
               (usage_id,artifact_id,learner_id,opened_at,content_hash,learner_level,
                account_role,identity_verified,institution_id)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (usage_id, artifact_id, learner_id, _now(), str(artifact.get("content_hash") or ""),
             training_level, account_role, 1 if principal else 0, institution_id),
        )
    return {"usage_id": usage_id, "artifact_id": artifact_id, "recorded": True,
            "identity_verified": bool(principal), "learner_level": training_level,
            "validation_contribution": bool(principal)}


@router.post("/artifacts/{artifact_id}/use/{usage_id}/complete")
def complete_artifact_use(artifact_id: str, usage_id: str, payload: CompleteUseRequest) -> dict[str, Any]:
    artifact = _published_artifact(artifact_id)
    if not artifact:
        raise HTTPException(404, "Published learning artefact not found")
    principal = _session_principal(payload.session_id)
    learner_id = str(principal["subject_id"]) if principal else payload.learner_id.strip()
    with _connect() as conn:
        usage = conn.execute(
            "SELECT * FROM learner_artifact_uses WHERE usage_id=? AND artifact_id=?",
            (usage_id, artifact_id),
        ).fetchone()
        if usage is None:
            raise HTTPException(404, "Learning use session not found")
        if usage["learner_id"] != learner_id:
            raise HTTPException(403, "The use record belongs to a different learner session")
        if usage["identity_verified"] and not principal:
            raise HTTPException(401, "Sign in with the learner account used to open this artefact")
        if usage["content_hash"] != str(artifact.get("content_hash") or ""):
            raise HTTPException(409, "This artefact has changed since it was opened. Reopen the current version before completing it.")
        completed_at = usage["completed_at"] or _now()
        conn.execute("UPDATE learner_artifact_uses SET completed_at=? WHERE usage_id=?", (completed_at, usage_id))
    return {"usage_id": usage_id, "artifact_id": artifact_id, "completed": True,
            "completed_at": completed_at, "identity_verified": bool(usage["identity_verified"])}


@router.post("/artifacts/{artifact_id}/feedback", status_code=201)
def submit_artifact_feedback(artifact_id: str, payload: FeedbackRequest) -> dict[str, Any]:
    artifact = _published_artifact(artifact_id)
    if not artifact:
        raise HTTPException(404, "Published learning artefact not found")
    categories = list(dict.fromkeys(payload.categories))
    if not categories or any(category not in FEEDBACK_CATEGORIES for category in categories):
        raise HTTPException(400, "Select one or more supported feedback categories")
    dimension_values = [payload.educational_rating, payload.clinical_rating,
                        payload.source_rating, payload.assessment_rating]
    if any(value is not None for value in dimension_values) and not all(value is not None for value in dimension_values):
        raise HTTPException(400, "Complete all four validation dimensions, or submit an issue-only report")
    if not payload.comment.strip() and payload.rating is None and not any(v is not None for v in dimension_values):
        raise HTTPException(400, "Add a rating or a short comment so the report is useful")
    if payload.severity in {"major", "critical"} and len(payload.comment.strip()) < 20:
        raise HTTPException(400, "Major or critical reports require at least 20 characters explaining the concern")
    allowed_documents = {str(item.get("document_id", "")) for item in artifact.get("source_refs", [])}
    source_ids = list(dict.fromkeys(payload.source_document_ids))
    if any(item not in allowed_documents for item in source_ids):
        raise HTTPException(400, "Feedback can only reference source records linked to this artefact")

    principal = _session_principal(payload.session_id)
    with _connect() as conn:
        usage = conn.execute(
            "SELECT * FROM learner_artifact_uses WHERE usage_id=? AND artifact_id=?",
            (payload.usage_id, artifact_id),
        ).fetchone()
        if usage is None:
            raise HTTPException(409, "Open and use the published artefact before sending feedback")
        if not usage["completed_at"]:
            raise HTTPException(409, "Mark the learning activity complete before sending post-use feedback")
        if usage["content_hash"] != str(artifact.get("content_hash") or ""):
            raise HTTPException(409, "This artefact changed after your use session. Reopen the current version before validating it.")
        if usage["identity_verified"] and not principal:
            raise HTTPException(401, "Sign in with the learner account used to open this artefact")
        learner_id = str(principal["subject_id"]) if principal else payload.learner_id.strip()
        if usage["learner_id"] != learner_id:
            raise HTTPException(403, "The use record belongs to a different learner session")
        if principal and usage["identity_verified"] and usage["institution_id"] != principal.get("institution_id"):
            raise HTTPException(403, "The use session belongs to a different institution")
        existing = conn.execute(
            "SELECT feedback_id FROM learner_artifact_feedback WHERE usage_id=?",
            (payload.usage_id,),
        ).fetchone()
        if existing:
            raise HTTPException(409, "Feedback has already been submitted for this use session")
        feedback_id = "lfeedback_" + uuid.uuid4().hex
        verified = bool(principal and usage["identity_verified"])
        training_level = str(principal.get("training_level", usage["learner_level"] or "unspecified")) if verified else "unspecified"
        account_role = str(principal.get("role", "guest")) if verified else "guest"
        institution_id = str(principal.get("institution_id", "local")) if verified else "local"
        try:
            conn.execute(
                """INSERT INTO learner_artifact_feedback
                   (feedback_id,usage_id,artifact_id,learner_id,rating,educational_rating,
                    clinical_rating,source_rating,assessment_rating,learner_level,account_role,
                    identity_verified,institution_id,content_hash,severity,categories_json,
                    source_document_ids_json,comment,status,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)""",
                (feedback_id, payload.usage_id, artifact_id, learner_id, payload.rating,
                 payload.educational_rating, payload.clinical_rating, payload.source_rating,
                 payload.assessment_rating, training_level, account_role, 1 if verified else 0,
                 institution_id, str(artifact.get("content_hash") or ""), payload.severity,
                 json.dumps(categories), json.dumps(source_ids), payload.comment.strip(), _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "You have already contributed a validation vote for this artefact version") from exc
    summary = _validation_summary(artifact_id, str(artifact.get("content_hash") or ""))
    message = ("Your post-use validation was recorded and contributes to this version's validation score."
               if verified and all(v is not None for v in dimension_values)
               else "Your post-use report was recorded. Sign in with an institution-assigned account and complete all four dimensions for it to count toward the validation score.")
    return {"feedback_id": feedback_id, "status": "pending", "received": True,
            "identity_verified": verified, "validation_contribution": bool(verified and all(v is not None for v in dimension_values)),
            "validation": summary, "message": message}


@router.post("/artifacts/{artifact_id}/validation/signoffs")
def signoff_artifact_validation(artifact_id: str, payload: SignoffRequest,
                                x_hsptl_session: str | None = Header(default=None)) -> dict[str, Any]:
    if payload.domain not in VALIDATION_DOMAINS:
        raise HTTPException(400, "Unknown validation domain")
    if payload.decision not in {"affirmed", "revision_required", "rejected"}:
        raise HTTPException(400, "Decision must be affirmed, revision_required or rejected")
    principal = _session_principal(x_hsptl_session, required_roles={"facilitator", "reviewer", "admin"})
    if not principal:
        raise HTTPException(401, "An authenticated institutional reviewer session is required")
    _signoff_authorisation(principal, payload.domain)
    artifact = _published_artifact(artifact_id)
    if not artifact:
        raise HTTPException(404, "Published learning artefact not found")
    now = _now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO learner_artifact_signoffs
               (signoff_id,artifact_id,content_hash,domain,reviewer_id,reviewer_role,
                reviewer_level,institution_id,decision,note,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            ("lsignoff_" + uuid.uuid4().hex, artifact_id, str(artifact.get("content_hash") or ""),
             payload.domain, str(principal["subject_id"]), str(principal["role"]),
             str(principal.get("training_level", "unspecified")), str(principal.get("institution_id", "local")),
             payload.decision, payload.note.strip(), now),
        )
    summary = _validation_summary(artifact_id, str(artifact.get("content_hash") or ""))
    return {"artifact_id": artifact_id, "domain": payload.domain, "decision": payload.decision,
            "reviewer_id": principal["subject_id"], "validation": summary,
            "artifact_status_changed": False,
            "note": "The version-specific validation sign-off is recorded. It does not itself change publication or clinical release status."}


@router.get("/feedback/queue")
def learner_feedback_queue(status: str = "pending", limit: int = 100,
                           x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    _reviewer(x_hsptl_reviewer_token)
    safe_limit = max(1, min(int(limit), 200))
    with _connect() as conn:
        rows = conn.execute(
            """SELECT f.*,a.title AS artifact_title,a.workspace,a.kind
               FROM learner_artifact_feedback f JOIN generated_artifacts a ON a.id=f.artifact_id
               WHERE (?='all' OR f.status=?) ORDER BY f.created_at DESC LIMIT ?""",
            (status, status, safe_limit),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["categories"] = json.loads(item.pop("categories_json"))
        item["source_document_ids"] = json.loads(item.pop("source_document_ids_json"))
        items.append(item)
    return {"items": items, "count": len(items)}


@router.post("/feedback/{feedback_id}/resolve")
def resolve_learner_feedback(feedback_id: str, payload: ResolveRequest,
                             x_hsptl_reviewer_token: str | None = Header(default=None)) -> dict[str, Any]:
    reviewer = _reviewer(x_hsptl_reviewer_token)
    if payload.status not in RESOLUTION_STATES:
        raise HTTPException(400, "Unsupported feedback resolution state")
    now = _now()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM learner_artifact_feedback WHERE feedback_id=?", (feedback_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Learner feedback report not found")
        conn.execute(
            "UPDATE learner_artifact_feedback SET status=?,reviewer=?,resolution=?,resolved_at=? WHERE feedback_id=?",
            (payload.status, reviewer, payload.resolution.strip(), now, feedback_id),
        )
        conn.execute(
            "INSERT INTO learner_feedback_audit(audit_id,feedback_id,action,reviewer,detail_json,created_at) VALUES(?,?,?,?,?,?)",
            ("lfaudit_" + uuid.uuid4().hex, feedback_id, payload.status, reviewer,
             json.dumps({"resolution": payload.resolution.strip(), "artifact_id": row["artifact_id"],
                         "source_document_ids": json.loads(row["source_document_ids_json"])}), now),
        )
    return {"feedback_id": feedback_id, "status": payload.status, "reviewer": reviewer,
            "source_or_artifact_status_changed": False,
            "note": "Triage is recorded. A reviewer must separately perform any source or artefact change."}
