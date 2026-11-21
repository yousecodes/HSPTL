"""Local institutional governance primitives for HSPTL.

Bounded, local-first governance: password-backed subjects, role-based sessions,
institution-scoped records, retention enforcement and clinical safety-case review.

This is deliberately not an enterprise identity provider, SSO/MFA, a hardened
multi-tenant service or an institutional clinical-approval system. Institution
scoping is a local data-isolation boundary inside one SQLite file, not a
production tenancy guarantee.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROLES = {"learner", "facilitator", "reviewer", "admin"}
ROLE_RANK = {"learner": 1, "facilitator": 2, "reviewer": 3, "admin": 4}
TRAINING_LEVELS = {"student", "intern", "resident", "registrar", "fellow", "specialist", "consultant", "faculty", "unspecified"}
SAFETY_DECISIONS = {"approved_with_residual_risk", "changes_requested", "rejected"}
FACILITATION_ACTIONS = {"start", "pause", "resume", "reveal", "clock_advance", "debrief", "close"}
CONSENT_STATES = {"not_required", "pending", "acknowledged", "revoked"}
DEFAULT_INSTITUTION = "local"


class InstitutionalError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def configured_institution() -> str:
    """Institution identity for shared-token deployments."""
    return (os.environ.get("HSPTL_INSTITUTION_ID", "").strip() or DEFAULT_INSTITUTION)[:100]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _highest(roles: set[str]) -> str:
    for role in sorted(roles, key=lambda item: ROLE_RANK.get(item, 0), reverse=True):
        return role
    raise InstitutionalError("Unknown HSPTL role.")


class InstitutionalAuth:
    # Access tables created by this class. Order matters only for readability.
    ACCESS_TABLES = ("hsptl_access_subjects", "hsptl_access_sessions", "hsptl_access_accounts")

    # Indexes that depend on institution_id, so they may only be created after
    # the column migration has succeeded on every access table.
    SESSION_INDEXES = (
        ("idx_hsptl_access_sessions_subject",
         "CREATE INDEX IF NOT EXISTS idx_hsptl_access_sessions_subject"
         " ON hsptl_access_sessions(subject_id, expires_at)"),
        ("idx_hsptl_access_sessions_institution",
         "CREATE INDEX IF NOT EXISTS idx_hsptl_access_sessions_institution"
         " ON hsptl_access_sessions(institution_id, expires_at)"),
    )

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            self._initialise_access_schema(conn)

    def _initialise_access_schema(self, conn: sqlite3.Connection) -> None:
        """Create tables, migrate legacy columns, then add the dependent indexes.

        A pre-5.0 database has these three tables without institution_id. The
        institution index references that column, so it cannot be created until
        the migration has run: doing both in one script fails with
        "no such column: institution_id" and leaves the schema half-migrated.

        The whole sequence runs in one transaction. ``executescript`` is
        deliberately not used because it commits any open transaction, which
        would defeat the rollback on failure. Rows are only ever added to
        (``ALTER TABLE ... ADD COLUMN``), never dropped or recreated.
        """
        statements = [
            """CREATE TABLE IF NOT EXISTS hsptl_access_subjects (
                subject_id TEXT PRIMARY KEY,
                institution_id TEXT NOT NULL DEFAULT 'local',
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                training_level TEXT NOT NULL DEFAULT 'unspecified',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS hsptl_access_sessions (
                session_id TEXT PRIMARY KEY,
                institution_id TEXT NOT NULL DEFAULT 'local',
                subject_id TEXT NOT NULL,
                role TEXT NOT NULL,
                training_level TEXT NOT NULL DEFAULT 'unspecified',
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS hsptl_access_accounts (
                subject_id TEXT PRIMARY KEY,
                institution_id TEXT NOT NULL DEFAULT 'local',
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                training_level TEXT NOT NULL DEFAULT 'unspecified',
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""",
        ]
        conn.execute("BEGIN IMMEDIATE")
        try:
            # 1. Tables first, with no indexes.
            for statement in statements:
                conn.execute(statement)
            # 2. Migrate every access table to carry institution_id. Existing
            #    rows take the DEFAULT, so pre-existing records are preserved.
            for table in self.ACCESS_TABLES:
                _ensure_column(conn, table, "institution_id", "TEXT NOT NULL DEFAULT 'local'")
                _ensure_column(conn, table, "training_level", "TEXT NOT NULL DEFAULT 'unspecified'")
            # 3. Only now may the indexes that reference institution_id be built.
            for _name, ddl in self.SESSION_INDEXES:
                conn.execute(ddl)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @staticmethod
    def utc_now() -> str:
        return utc_now()

    def configured(self) -> bool:
        return len(os.environ.get("HSPTL_ADMIN_TOKEN", "")) >= 32

    @staticmethod
    def _password_hash(password: str, salt: str) -> str:
        if len(password) < 12:
            raise InstitutionalError("Password must contain at least 12 characters.")
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                   salt.encode("ascii"), 240_000).hex()

    def create_account(self, subject_id: str, display_name: str, password: str,
                       role: str, institution_id: str = DEFAULT_INSTITUTION,
                       training_level: str = "student") -> dict[str, Any]:
        subject_id = subject_id.strip()[:160]
        display_name = display_name.strip()[:160]
        institution_id = (institution_id or DEFAULT_INSTITUTION).strip()[:100]
        if not subject_id or not display_name:
            raise InstitutionalError("subject_id and display_name are required.")
        if role not in ROLES:
            raise InstitutionalError("Unknown HSPTL role.")
        training_level = (training_level or "unspecified").strip().lower()
        if training_level not in TRAINING_LEVELS:
            raise InstitutionalError("Unknown training level.")
        if role == "admin":
            raise InstitutionalError(
                "Admin accounts must be created through the configured deployment administrator.")
        salt = secrets.token_hex(16)
        password_hash = self._password_hash(password, salt)
        now = utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM hsptl_access_accounts WHERE subject_id=?", (subject_id,)).fetchone()
            if existing:
                raise InstitutionalError("Subject account already exists.")
            conn.execute("""INSERT INTO hsptl_access_accounts
                (subject_id,institution_id,display_name,role,training_level,password_salt,password_hash,
                 active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (subject_id, institution_id, display_name, role, training_level, salt, password_hash, 1, now, now))
            conn.execute("""INSERT OR REPLACE INTO hsptl_access_subjects
                (subject_id,institution_id,display_name,role,training_level,active,created_at)
                VALUES(?,?,?,?,?,?,?)""",
                (subject_id, institution_id, display_name, role, training_level, 1, now))
        return {"subject_id": subject_id, "institution_id": institution_id,
                "display_name": display_name, "role": role, "training_level": training_level, "active": True,
                "password": "stored_as_pbkdf2_sha256"}

    def login(self, subject_id: str, password: str,
              institution_id: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            account = conn.execute(
                "SELECT * FROM hsptl_access_accounts WHERE subject_id=? AND active=1",
                (subject_id.strip(),)).fetchone()
        if account is None:
            raise InstitutionalError("Invalid subject or password.")
        supplied = self._password_hash(password, account["password_salt"])
        if not hmac.compare_digest(supplied, account["password_hash"]):
            raise InstitutionalError("Invalid subject or password.")
        if institution_id and institution_id.strip() != account["institution_id"]:
            raise InstitutionalError("Invalid subject or password.")
        session_id = "session_" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(hours=8)).replace(microsecond=0)
        with self._connect() as conn:
            conn.execute("INSERT INTO hsptl_access_sessions"
                         "(session_id,institution_id,subject_id,role,training_level,expires_at,created_at) "
                         "VALUES(?,?,?,?,?,?,?)",
                         (session_id, account["institution_id"], account["subject_id"],
                          account["role"], account["training_level"], expires.isoformat(timespec="seconds"),
                          now.isoformat(timespec="seconds")))
        return {"state": "authenticated", "subject_id": account["subject_id"],
                "institution_id": account["institution_id"],
                "display_name": account["display_name"], "role": account["role"],
                "training_level": account["training_level"],
                "session_id": session_id,
                "expires_at": expires.isoformat(timespec="seconds"),
                "scope": "local_rbac_session"}

    def validate_session(self, session_id: str, required_roles: set[str]) -> dict[str, Any]:
        if not session_id:
            raise InstitutionalError("A valid session is required.")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with self._connect() as conn:
            session = conn.execute(
                "SELECT * FROM hsptl_access_sessions WHERE session_id=?",
                (session_id.strip(),)).fetchone()
        if session is None:
            raise InstitutionalError("Invalid or expired session.")
        try:
            expires = datetime.fromisoformat(session["expires_at"])
        except ValueError:
            expires = datetime.now(timezone.utc) - timedelta(seconds=1)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            raise InstitutionalError("Invalid or expired session.")
        if session["role"] not in required_roles:
            raise PermissionError("The authenticated role cannot perform this operation.")
        return {"state": "authenticated", "session_id": session["session_id"],
                "subject_id": session["subject_id"], "role": session["role"],
                "training_level": session["training_level"],
                "institution_id": session["institution_id"],
                "scope": "local_rbac_session"}

    def logout(self, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("DELETE FROM hsptl_access_sessions WHERE session_id=?",
                         (session_id.strip(),))
        return {"state": "logged_out", "session_id": session_id}

    def verify(self, token: str | None, role: str, subject_id: str = "") -> dict[str, Any]:
        if role not in ROLES:
            raise InstitutionalError("Unknown HSPTL role.")
        expected = os.environ.get("HSPTL_ADMIN_TOKEN", "")
        if len(expected) < 32:
            return {"state": "not_configured", "authentication": "fail_closed",
                    "reason": "Set HSPTL_ADMIN_TOKEN to a 32+ character local deployment token."}
        if not token or not hmac.compare_digest(token, expected):
            return {"state": "unauthorized", "authentication": "fail_closed",
                    "reason": "Valid HSPTL_ADMIN_TOKEN authentication is required."}
        institution_id = configured_institution()
        resolved_subject = (subject_id.strip()[:160]
                            or os.environ.get("HSPTL_ADMIN_ID", "local-admin").strip()[:160])
        session_id = "session_" + uuid.uuid4().hex
        now = utc_now()
        training_level = os.environ.get("HSPTL_ADMIN_TRAINING_LEVEL", "unspecified").strip().lower()
        if training_level not in TRAINING_LEVELS:
            training_level = "unspecified"
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO hsptl_access_subjects"
                         "(subject_id,institution_id,display_name,role,training_level,active,created_at) "
                         "VALUES(?,?,?,?,?,?,?)",
                         (resolved_subject, institution_id, resolved_subject, role, training_level, 1, now))
            conn.execute("INSERT INTO hsptl_access_sessions"
                         "(session_id,institution_id,subject_id,role,training_level,expires_at,created_at) "
                         "VALUES(?,?,?,?,?,?,?)",
                         (session_id, institution_id, resolved_subject, role, training_level,
                          (datetime.now(timezone.utc) + timedelta(hours=8))
                          .replace(microsecond=0).isoformat(timespec="seconds"), now))
        return {"state": "authenticated", "subject_id": resolved_subject,
                "institution_id": institution_id, "role": role, "training_level": training_level,
                "session_id": session_id, "scope": "local_institutional_governance",
                "limitation": "This shared-token boundary is not SSO, MFA or an enterprise identity provider."}

    def require(self, token: str | None, role: str, subject_id: str = "") -> dict[str, Any]:
        result = self.verify(token, role, subject_id)
        if result["state"] != "authenticated":
            raise InstitutionalError(result["reason"])
        if role not in {"facilitator", "reviewer", "admin"}:
            raise InstitutionalError("The operation requires facilitator, reviewer or admin role.")
        return result

    def principal(self, *, admin_token: str | None, session_id: str | None,
                  roles: set[str]) -> dict[str, Any]:
        """Resolve one authenticated principal that satisfies ``roles``.

        Sessions take precedence so a browser login cannot be silently
        downgraded by an absent token. Both paths resolve an institution.
        """
        if session_id:
            return self.validate_session(session_id, roles)
        return self.require(admin_token, _highest(roles))


class CohortRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS hsptl_cohorts (
                    cohort_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    title TEXT NOT NULL,
                    specialty TEXT NOT NULL,
                    learner_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    privacy_notice TEXT NOT NULL,
                    retention_days INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hsptl_cohort_members (
                    cohort_id TEXT NOT NULL,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    subject_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    joined_at TEXT NOT NULL,
                    PRIMARY KEY(cohort_id,subject_id)
                );
                CREATE TABLE IF NOT EXISTS hsptl_facilitation_sessions (
                    session_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    cohort_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    scenario_version TEXT NOT NULL,
                    facilitator_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    clock_policy TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS hsptl_facilitation_events (
                    event_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    session_id TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hsptl_privacy_policies (
                    policy_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    data_scope TEXT NOT NULL,
                    retention_days INTEGER NOT NULL,
                    purge_strategy TEXT NOT NULL,
                    consent_status TEXT NOT NULL,
                    encryption_at_rest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hsptl_purge_audit (
                    purge_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    policy_id TEXT NOT NULL,
                    removed_records INTEGER NOT NULL,
                    scope TEXT NOT NULL,
                    cutoff_at TEXT NOT NULL,
                    performed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hsptl_safety_cases (
                    case_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    scenario_id TEXT NOT NULL,
                    scenario_version TEXT NOT NULL,
                    hazard TEXT NOT NULL,
                    safety_requirement TEXT NOT NULL,
                    control TEXT NOT NULL,
                    residual_risk TEXT NOT NULL,
                    evidence_status TEXT NOT NULL,
                    clinical_owner TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hsptl_safety_case_reviews (
                    review_id TEXT PRIMARY KEY,
                    institution_id TEXT NOT NULL DEFAULT 'local',
                    case_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    residual_risk_acceptance TEXT NOT NULL,
                    note TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                );
            """)
            for table in ("hsptl_cohorts", "hsptl_cohort_members", "hsptl_facilitation_sessions",
                          "hsptl_facilitation_events", "hsptl_privacy_policies",
                          "hsptl_purge_audit", "hsptl_safety_cases", "hsptl_safety_case_reviews"):
                _ensure_column(conn, table, "institution_id", "TEXT NOT NULL DEFAULT 'local'")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hsptl_cohorts_institution "
                         "ON hsptl_cohorts(institution_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hsptl_sessions_institution "
                         "ON hsptl_facilitation_sessions(institution_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hsptl_safety_institution "
                         "ON hsptl_safety_cases(institution_id, created_at)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    # -- cohorts ---------------------------------------------------------
    def create_cohort(self, payload: dict[str, Any],
                      institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        cohort_id = str(payload.get("cohort_id", "")).strip()
        if not cohort_id or len(cohort_id) > 100:
            cohort_id = "cohort_" + uuid.uuid4().hex
        title = str(payload.get("title", "")).strip()
        if not title:
            raise InstitutionalError("Cohort title is required.")
        retention = int(payload.get("retention_days", 365))
        if retention < 1 or retention > 3650:
            raise InstitutionalError("retention_days must be from 1 through 3650.")
        now = utc_now()
        row = {"cohort_id": cohort_id,
               "institution_id": (institution_id or DEFAULT_INSTITUTION)[:100],
               "title": title[:160],
               "specialty": str(payload.get("specialty", "General")).strip()[:100],
               "learner_level": str(payload.get("learner_level", "Mixed")).strip()[:100],
               "status": "active",
               "privacy_notice": str(payload.get(
                   "privacy_notice", "Local educational use; no patient identifiers."))[:3000],
               "retention_days": retention,
               "created_at": now, "updated_at": now}
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)
        with self._connect() as conn:
            conn.execute(f"INSERT OR REPLACE INTO hsptl_cohorts({columns}) VALUES({placeholders})",
                         tuple(row.values()))
        return dict(row)

    def list_cohorts(self, institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM hsptl_cohorts WHERE institution_id=? ORDER BY created_at DESC",
                (institution_id,))]

    def get_cohort(self, cohort_id: str,
                   institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM hsptl_cohorts WHERE cohort_id=? AND institution_id=?",
                (cohort_id, institution_id)).fetchone()
        if row is None:
            raise KeyError(cohort_id)
        return dict(row)

    def add_member(self, cohort_id: str, subject_id: str, role: str,
                   institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        if role not in {"learner", "facilitator", "reviewer"}:
            raise InstitutionalError("Member role must be learner, facilitator or reviewer.")
        if not subject_id.strip():
            raise InstitutionalError("subject_id is required.")
        now = utc_now()
        with self._connect() as conn:
            cohort = conn.execute(
                "SELECT cohort_id FROM hsptl_cohorts WHERE cohort_id=? AND institution_id=?",
                (cohort_id, institution_id)).fetchone()
            if cohort is None:
                raise InstitutionalError("Cohort not found.")
            conn.execute("INSERT OR REPLACE INTO hsptl_cohort_members"
                         "(cohort_id,institution_id,subject_id,role,active,joined_at) "
                         "VALUES(?,?,?,?,?,?)",
                         (cohort_id, institution_id, subject_id[:160], role, 1, now))
        return {"cohort_id": cohort_id, "institution_id": institution_id,
                "subject_id": subject_id[:160], "role": role, "active": True}

    def list_members(self, cohort_id: str,
                     institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM hsptl_cohort_members WHERE cohort_id=? AND institution_id=? "
                "ORDER BY joined_at", (cohort_id, institution_id))]

    # -- facilitation ----------------------------------------------------
    def create_session(self, payload: dict[str, Any],
                       institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        cohort_id = str(payload.get("cohort_id", "")).strip()
        scenario_id = str(payload.get("scenario_id", "")).strip()
        scenario_version = str(payload.get("scenario_version", "")).strip()
        facilitator_id = str(payload.get("facilitator_id", "")).strip()
        if not cohort_id or not scenario_id or not scenario_version or not facilitator_id:
            raise InstitutionalError(
                "cohort_id, scenario_id, scenario_version and facilitator_id are required.")
        now = utc_now()
        row = {"session_id": "fac_" + uuid.uuid4().hex,
               "institution_id": (institution_id or DEFAULT_INSTITUTION)[:100],
               "cohort_id": cohort_id,
               "scenario_id": scenario_id[:100], "scenario_version": scenario_version[:40],
               "facilitator_id": facilitator_id[:160], "status": "active",
               "clock_policy": "facilitator_explicit_integer_clock",
               "created_at": now, "closed_at": None}
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)
        with self._connect() as conn:
            cohort = conn.execute(
                "SELECT cohort_id FROM hsptl_cohorts WHERE cohort_id=? AND institution_id=?",
                (cohort_id, institution_id)).fetchone()
            if cohort is None:
                raise InstitutionalError("Cohort not found.")
            conn.execute(
                f"INSERT INTO hsptl_facilitation_sessions({columns}) VALUES({placeholders})",
                tuple(row.values()))
        return dict(row)

    def record_event(self, session_id: str, subject_id: str, action: str,
                     detail: dict[str, Any],
                     institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        if action not in FACILITATION_ACTIONS:
            raise InstitutionalError("Unsupported facilitation action.")
        event_id = "facle_" + uuid.uuid4().hex
        now = utc_now()
        with self._connect() as conn:
            session = conn.execute(
                "SELECT status FROM hsptl_facilitation_sessions "
                "WHERE session_id=? AND institution_id=?",
                (session_id, institution_id)).fetchone()
            if session is None:
                raise InstitutionalError("Facilitation session not found.")
            if session["status"] == "closed" and action != "close":
                raise InstitutionalError("A closed facilitation session is immutable.")
            conn.execute("INSERT INTO hsptl_facilitation_events"
                         "(event_id,institution_id,session_id,subject_id,action,detail_json,recorded_at) "
                         "VALUES(?,?,?,?,?,?,?)",
                         (event_id, institution_id, session_id, subject_id[:160], action,
                          json.dumps(detail, sort_keys=True, ensure_ascii=False), now))
            if action == "close":
                conn.execute("UPDATE hsptl_facilitation_sessions "
                             "SET status='closed',closed_at=? WHERE session_id=?",
                             (now, session_id))
        return {"event_id": event_id, "session_id": session_id, "subject_id": subject_id[:160],
                "action": action, "detail": detail, "recorded_at": now}

    def list_sessions(self, cohort_id: str = "",
                      institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if cohort_id:
                rows = conn.execute(
                    "SELECT * FROM hsptl_facilitation_sessions "
                    "WHERE cohort_id=? AND institution_id=? ORDER BY created_at DESC",
                    (cohort_id, institution_id))
            else:
                rows = conn.execute(
                    "SELECT * FROM hsptl_facilitation_sessions "
                    "WHERE institution_id=? ORDER BY created_at DESC", (institution_id,))
            return [dict(row) for row in rows]

    # -- privacy and retention -------------------------------------------
    def set_privacy_policy(self, data_scope: str, retention_days: int,
                           consent_status: str = "acknowledged",
                           encryption_at_rest: str = "deployment_managed",
                           institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        data_scope = data_scope.strip()[:160]
        if not data_scope:
            raise InstitutionalError("data_scope is required.")
        if retention_days < 1 or retention_days > 3650:
            raise InstitutionalError("retention_days must be from 1 through 3650.")
        if consent_status not in CONSENT_STATES:
            raise InstitutionalError("Unsupported consent status.")
        now = utc_now()
        policy_id = "privacy_" + hashlib.sha256(
            f"{institution_id}:{data_scope}".encode("utf-8")).hexdigest()[:16]
        row = {"policy_id": policy_id,
               "institution_id": (institution_id or DEFAULT_INSTITUTION)[:100],
               "data_scope": data_scope, "retention_days": retention_days,
               "purge_strategy": "delete_closed_records_after_retention",
               "consent_status": consent_status,
               "encryption_at_rest": encryption_at_rest[:160],
               "created_at": now, "updated_at": now}
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT created_at FROM hsptl_privacy_policies WHERE policy_id=?",
                (policy_id,)).fetchone()
            row["created_at"] = existing["created_at"] if existing else now
            columns = ",".join(row)
            placeholders = ",".join("?" for _ in row)
            conn.execute(
                f"INSERT OR REPLACE INTO hsptl_privacy_policies({columns}) VALUES({placeholders})",
                tuple(row.values()))
        return dict(row)

    def privacy_policies(self, institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM hsptl_privacy_policies WHERE institution_id=? "
                "ORDER BY updated_at DESC", (institution_id,))]

    def purge_expired_sessions(self,
                               institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        cutoff_text = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(
            timespec="seconds")
        with self._connect() as conn:
            removed = conn.execute(
                "SELECT COUNT(*) AS n FROM hsptl_access_sessions "
                "WHERE institution_id=? AND expires_at < ?",
                (institution_id, cutoff_text)).fetchone()["n"]
            conn.execute("DELETE FROM hsptl_access_sessions "
                         "WHERE institution_id=? AND expires_at < ?",
                         (institution_id, cutoff_text))
        purge_id = "purge_" + uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute("INSERT INTO hsptl_purge_audit"
                         "(purge_id,institution_id,policy_id,removed_records,scope,"
                         "cutoff_at,performed_at) VALUES(?,?,?,?,?,?,?)",
                         (purge_id, institution_id, "privacy_expired_auth_sessions", int(removed),
                          "hsptl_access_sessions", cutoff_text, utc_now()))
        return {"purge_id": purge_id, "institution_id": institution_id,
                "removed_records": int(removed),
                "scope": "expired_access_sessions", "cutoff_at": cutoff_text}

    def purge_expired_cohort_data(self,
                                  institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        """Delete closed facilitation data older than each cohort's retention window."""
        now = datetime.now(timezone.utc)
        removed_sessions = 0
        removed_events = 0
        with self._connect() as conn:
            cohorts = conn.execute(
                "SELECT cohort_id, retention_days FROM hsptl_cohorts WHERE institution_id=?",
                (institution_id,)).fetchall()
            for cohort in cohorts:
                cutoff = (now - timedelta(days=int(cohort["retention_days"]))).isoformat(
                    timespec="seconds")
                expired = [row["session_id"] for row in conn.execute(
                    "SELECT session_id FROM hsptl_facilitation_sessions "
                    "WHERE institution_id=? AND cohort_id=? AND status='closed' "
                    "AND closed_at IS NOT NULL AND closed_at < ?",
                    (institution_id, cohort["cohort_id"], cutoff))]
                for session_id in expired:
                    removed_events += conn.execute(
                        "DELETE FROM hsptl_facilitation_events "
                        "WHERE institution_id=? AND session_id=?",
                        (institution_id, session_id)).rowcount
                    removed_sessions += conn.execute(
                        "DELETE FROM hsptl_facilitation_sessions "
                        "WHERE institution_id=? AND session_id=?",
                        (institution_id, session_id)).rowcount
        purge_id = "purge_" + uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute("INSERT INTO hsptl_purge_audit"
                         "(purge_id,institution_id,policy_id,removed_records,scope,"
                         "cutoff_at,performed_at) VALUES(?,?,?,?,?,?,?)",
                         (purge_id, institution_id, "privacy_cohort_retention",
                          int(removed_sessions + removed_events),
                          "closed_facilitation_sessions_and_events",
                          now.isoformat(timespec="seconds"), utc_now()))
        return {"purge_id": purge_id, "institution_id": institution_id,
                "removed_sessions": int(removed_sessions),
                "removed_events": int(removed_events),
                "removed_records": int(removed_sessions + removed_events),
                "scope": "closed_cohort_data_past_retention"}

    def purge_audit(self, institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM hsptl_purge_audit WHERE institution_id=? "
                "ORDER BY performed_at DESC LIMIT 100", (institution_id,))]

    # -- clinical safety cases -------------------------------------------
    def create_safety_case(self, payload: dict[str, Any],
                           institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        required = ("scenario_id", "scenario_version", "hazard", "safety_requirement",
                    "control", "residual_risk", "clinical_owner")
        missing = [key for key in required if not str(payload.get(key, "")).strip()]
        if missing:
            raise InstitutionalError("Missing safety-case fields: " + ", ".join(missing))
        now = utc_now()
        row = {"case_id": "safety_" + uuid.uuid4().hex,
               "institution_id": (institution_id or DEFAULT_INSTITUTION)[:100],
               "scenario_id": str(payload["scenario_id"]).strip()[:100],
               "scenario_version": str(payload["scenario_version"]).strip()[:40],
               "hazard": str(payload["hazard"]).strip()[:3000],
               "safety_requirement": str(payload["safety_requirement"]).strip()[:3000],
               "control": str(payload["control"]).strip()[:3000],
               "residual_risk": str(payload["residual_risk"]).strip()[:3000],
               "evidence_status": str(payload.get("evidence_status", "pending")).strip()[:100],
               "clinical_owner": str(payload["clinical_owner"]).strip()[:160],
               "approval_status": "pending_external_clinical_review",
               "created_at": now, "updated_at": now}
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)
        with self._connect() as conn:
            conn.execute(f"INSERT INTO hsptl_safety_cases({columns}) VALUES({placeholders})",
                         tuple(row.values()))
        return dict(row)

    def list_safety_cases(self, scenario_id: str = "",
                          institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if scenario_id:
                rows = conn.execute(
                    "SELECT * FROM hsptl_safety_cases WHERE scenario_id=? AND institution_id=? "
                    "ORDER BY created_at DESC", (scenario_id, institution_id))
            else:
                rows = conn.execute(
                    "SELECT * FROM hsptl_safety_cases WHERE institution_id=? "
                    "ORDER BY created_at DESC", (institution_id,))
            return [dict(row) for row in rows]

    def review_safety_case(self, case_id: str, reviewer_id: str, decision: str,
                           residual_risk_acceptance: str, note: str = "",
                           institution_id: str = DEFAULT_INSTITUTION) -> dict[str, Any]:
        """Record a clinical-safety decision for one scenario hazard.

        This captures a local reviewer decision. It does not assert that the
        reviewer is institutionally qualified, and external clinical approval
        remains required before learner use.
        """
        if decision not in SAFETY_DECISIONS:
            raise InstitutionalError("Unsupported safety-case decision.")
        reviewer_id = reviewer_id.strip()[:160]
        if not reviewer_id:
            raise InstitutionalError("reviewer_id is required.")
        if decision == "approved_with_residual_risk" and not residual_risk_acceptance.strip():
            raise InstitutionalError(
                "Residual-risk acceptance text is required to approve a safety case.")
        now = utc_now()
        review_id = "safetyreview_" + uuid.uuid4().hex
        with self._connect() as conn:
            case = conn.execute(
                "SELECT case_id FROM hsptl_safety_cases WHERE case_id=? AND institution_id=?",
                (case_id, institution_id)).fetchone()
            if case is None:
                raise KeyError(case_id)
            conn.execute("INSERT INTO hsptl_safety_case_reviews"
                         "(review_id,institution_id,case_id,reviewer_id,decision,"
                         "residual_risk_acceptance,note,reviewed_at) VALUES(?,?,?,?,?,?,?,?)",
                         (review_id, institution_id, case_id, reviewer_id, decision,
                          residual_risk_acceptance.strip()[:3000], note.strip()[:3000], now))
            conn.execute("UPDATE hsptl_safety_cases SET approval_status=?,updated_at=? "
                         "WHERE case_id=? AND institution_id=?",
                         (decision, now, case_id, institution_id))
        return {"review_id": review_id, "case_id": case_id, "institution_id": institution_id,
                "reviewer_id": reviewer_id, "decision": decision,
                "residual_risk_acceptance": residual_risk_acceptance.strip()[:3000],
                "note": note.strip()[:3000], "reviewed_at": now,
                "approval_scope": "local_safety_record_review",
                "external_qualification_note":
                    "Reviewer qualification must be verified by the deploying institution."}

    def safety_case_reviews(self, case_id: str = "",
                            institution_id: str = DEFAULT_INSTITUTION) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if case_id:
                rows = conn.execute(
                    "SELECT * FROM hsptl_safety_case_reviews "
                    "WHERE case_id=? AND institution_id=? ORDER BY reviewed_at DESC",
                    (case_id, institution_id))
            else:
                rows = conn.execute(
                    "SELECT * FROM hsptl_safety_case_reviews WHERE institution_id=? "
                    "ORDER BY reviewed_at DESC", (institution_id,))
            return [dict(row) for row in rows]
