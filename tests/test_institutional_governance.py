from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.hsptl_core.config import APP_VERSION
from backend.hsptl_core.institutional import CohortRepository, InstitutionalAuth
from backend.main import app

ADMIN_TOKEN = "test-admin-token-" + "x" * 32
PASSWORD = "correct-horse-battery"


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setenv("HSPTL_ADMIN_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("HSPTL_INSTITUTION_ID", "institution-a")
    return {"X-HSPTL-Admin-Token": ADMIN_TOKEN}


@pytest.fixture
def second_institution(monkeypatch):
    monkeypatch.setenv("HSPTL_INSTITUTION_ID", "institution-b")
    return {"X-HSPTL-Admin-Token": ADMIN_TOKEN}


def _login(client: TestClient, subject_id: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/v4/institution/login",
                           json={"subject_id": subject_id, "password": password})
    assert response.status_code == 200, response.text
    return {"X-HSPTL-Session": response.json()["session_id"]}


def _create_account(client: TestClient, headers: dict[str, str], subject_id: str,
                    role: str) -> None:
    response = client.post("/api/v4/institution/accounts", headers=headers,
                           json={"subject_id": subject_id, "display_name": subject_id,
                                 "password": PASSWORD, "role": role})
    assert response.status_code == 200, response.text


def test_version_metadata_reports_current_release_across_endpoints():
    project_root = Path(__file__).resolve().parents[1]
    package = json.loads((project_root / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((project_root / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert package["version"] == APP_VERSION
    assert lock["version"] == APP_VERSION
    assert lock["packages"][""]["version"] == APP_VERSION
    with TestClient(app) as client:
        assert client.get("/api/health").json()["version"] == APP_VERSION
        assert client.get("/api/bootstrap").json()["version"] == APP_VERSION
        assert client.get("/api/v4/architecture").json()["version"] == APP_VERSION
        assert client.get("/api/v4/status").json()["version"] == APP_VERSION


def test_governance_routes_are_unauthenticated_fail_closed(monkeypatch):
    monkeypatch.delenv("HSPTL_ADMIN_TOKEN", raising=False)
    with TestClient(app) as client:
        for method, path in (
            ("get", "/api/v4/institution/cohorts"),
            ("get", "/api/v4/institution/privacy/policies"),
            ("get", "/api/v4/institution/recovery/backups"),
            ("get", "/api/v4/institution/calibration/export"),
            ("get", "/api/v4/institution/safety-cases"),
            ("get", "/api/v4/institution/privacy/purge-audit"),
        ):
            response = getattr(client, method)(path)
            assert response.status_code == 401, f"{path} leaked data without authentication"


def test_learner_session_is_forbidden_from_governance_operations(admin):
    with TestClient(app) as client:
        _create_account(client, admin, "learner-1", "learner")
        session = _login(client, "learner-1")
        assert client.get("/api/v4/institution/session",
                          headers=session).json()["role"] == "learner"
        for path in ("/api/v4/institution/cohorts",
                     "/api/v4/institution/privacy/policies",
                     "/api/v4/institution/recovery/backups",
                     "/api/v4/institution/calibration/export",
                     "/api/v4/institution/safety-cases"):
            assert client.get(path, headers=session).status_code == 403, path
        assert client.post("/api/v4/institution/cohorts", headers=session,
                           json={"title": "Denied"}).status_code == 403


def test_facilitator_can_manage_cohorts_but_not_privacy_policy(admin):
    with TestClient(app) as client:
        _create_account(client, admin, "facilitator-1", "facilitator")
        session = _login(client, "facilitator-1")
        created = client.post("/api/v4/institution/cohorts", headers=session,
                              json={"title": "Ward round cohort"})
        assert created.status_code == 403
        assert client.get("/api/v4/institution/cohorts",
                          headers=session).status_code == 200
        assert client.post("/api/v4/institution/privacy/policy", headers=session,
                           json={"data_scope": "cohort_records"}).status_code == 403


def test_accounts_cannot_self_register_as_admin(admin):
    with TestClient(app) as client:
        response = client.post("/api/v4/institution/accounts", headers=admin,
                               json={"subject_id": "sneaky", "display_name": "Sneaky",
                                     "password": PASSWORD, "role": "admin"})
        assert response.status_code == 422
        assert "administrator" in str(response.json()["detail"]).lower()


def test_cohort_records_are_isolated_between_institutions(monkeypatch):
    monkeypatch.setenv("HSPTL_ADMIN_TOKEN", ADMIN_TOKEN)
    with TestClient(app) as client:
        monkeypatch.setenv("HSPTL_INSTITUTION_ID", "institution-a")
        created = client.post("/api/v4/institution/cohorts",
                              headers={"X-HSPTL-Admin-Token": ADMIN_TOKEN},
                              json={"title": "Tenant A cohort", "retention_days": 30})
        assert created.status_code == 200
        cohort_id = created.json()["cohort_id"]

        monkeypatch.setenv("HSPTL_INSTITUTION_ID", "institution-b")
        other = {"X-HSPTL-Admin-Token": ADMIN_TOKEN}
        titles = [item["title"] for item in
                  client.get("/api/v4/institution/cohorts", headers=other).json()["items"]]
        assert "Tenant A cohort" not in titles
        # Cross-tenant identifiers must not be addressable.
        assert client.get(f"/api/v4/institution/cohorts/{cohort_id}/members",
                          headers=other).status_code == 404


def test_safety_case_review_requires_residual_risk_acceptance(admin):
    with TestClient(app) as client:
        created = client.post("/api/v4/institution/safety-cases", headers=admin, json={
            "scenario_id": "asthma", "scenario_version": "1.0.0",
            "hazard": "Delayed escalation in worsening asthma",
            "safety_requirement": "Escalate within the authored window",
            "control": "Senior review prompt and blocked completion",
            "residual_risk": "Learner may still delay escalation",
            "clinical_owner": "Dr Owner",
        })
        assert created.status_code == 200
        case = created.json()
        assert case["approval_status"] == "pending_external_clinical_review"
        case_id = case["case_id"]

        rejected = client.post(f"/api/v4/institution/safety-cases/{case_id}/review",
                               headers=admin,
                               json={"reviewer_id": "Dr Reviewer",
                                     "decision": "approved_with_residual_risk"})
        assert rejected.status_code == 422

        approved = client.post(f"/api/v4/institution/safety-cases/{case_id}/review",
                               headers=admin,
                               json={"reviewer_id": "Dr Reviewer",
                                     "decision": "approved_with_residual_risk",
                                     "residual_risk_acceptance":
                                         "Accepted for local formative use only."})
        assert approved.status_code == 200
        assert approved.json()["approval_scope"] == "local_safety_record_review"

        listed = client.get("/api/v4/institution/safety-cases", headers=admin).json()
        assert listed["items"][0]["approval_status"] == "approved_with_residual_risk"
        reviews = client.get("/api/v4/institution/safety-cases/reviews",
                             headers=admin).json()["items"]
        assert len(reviews) == 1 and reviews[0]["reviewer_id"] == "Dr Reviewer"


def test_safety_case_review_of_unknown_case_is_not_found(admin):
    with TestClient(app) as client:
        response = client.post("/api/v4/institution/safety-cases/safety_missing/review",
                               headers=admin,
                               json={"reviewer_id": "Dr Reviewer",
                                     "decision": "rejected"})
        assert response.status_code == 404


def test_facilitation_session_is_immutable_once_closed(admin):
    with TestClient(app) as client:
        cohort = client.post("/api/v4/institution/cohorts", headers=admin,
                             json={"title": "Debrief cohort"}).json()
        session = client.post("/api/v4/institution/sessions", headers=admin, json={
            "cohort_id": cohort["cohort_id"], "scenario_id": "asthma",
            "scenario_version": "1.0.0", "facilitator_id": "facilitator-1"}).json()
        session_id = session["session_id"]
        assert client.post(f"/api/v4/institution/sessions/{session_id}/events", headers=admin,
                           json={"subject_id": "learner-1", "action": "start"}).status_code == 200
        assert client.post(f"/api/v4/institution/sessions/{session_id}/events", headers=admin,
                           json={"subject_id": "learner-1", "action": "close"}).status_code == 200
        late = client.post(f"/api/v4/institution/sessions/{session_id}/events", headers=admin,
                           json={"subject_id": "learner-1", "action": "reveal"})
        assert late.status_code == 422


def test_retention_purge_keeps_recent_closed_data_and_audits(admin):
    with TestClient(app) as client:
        cohort = client.post("/api/v4/institution/cohorts", headers=admin,
                             json={"title": "Active cohort", "retention_days": 30}).json()
        session = client.post("/api/v4/institution/sessions", headers=admin, json={
            "cohort_id": cohort["cohort_id"], "scenario_id": "asthma",
            "scenario_version": "1.0.0", "facilitator_id": "facilitator-1"}).json()
        client.post(f"/api/v4/institution/sessions/{session['session_id']}/events",
                    headers=admin, json={"subject_id": "learner-1", "action": "close"})
        purge = client.post("/api/v4/institution/privacy/purge-retention", headers=admin)
        assert purge.status_code == 200
        assert purge.json()["scope"] == "closed_cohort_data_past_retention"
        assert purge.json()["removed_sessions"] == 0
        audit = client.get("/api/v4/institution/privacy/purge-audit", headers=admin).json()
        assert audit["items"], "purge must be auditable"
        kept = client.get("/api/v4/institution/sessions", headers=admin,
                          params={"cohort_id": cohort["cohort_id"]}).json()["items"]
        assert len(kept) == 1


def test_retention_purge_deletes_only_data_past_the_cohort_window(tmp_path: Path):
    repo = CohortRepository(tmp_path / "retention.sqlite3")
    expired = repo.create_cohort({"title": "Expired", "retention_days": 1}, "institution-a")
    fresh = repo.create_cohort({"title": "Fresh", "retention_days": 365}, "institution-a")
    old_session = repo.create_session({
        "cohort_id": expired["cohort_id"], "scenario_id": "asthma",
        "scenario_version": "1.0.0", "facilitator_id": "facilitator-1"}, "institution-a")
    new_session = repo.create_session({
        "cohort_id": fresh["cohort_id"], "scenario_id": "asthma",
        "scenario_version": "1.0.0", "facilitator_id": "facilitator-1"}, "institution-a")
    repo.record_event(old_session["session_id"], "learner-1", "close", {}, "institution-a")
    repo.record_event(new_session["session_id"], "learner-1", "close", {}, "institution-a")
    with sqlite3.connect(repo.db_path) as conn:
        conn.execute("UPDATE hsptl_facilitation_sessions SET closed_at=? WHERE session_id=?",
                     ("2020-01-01T00:00:00+00:00", old_session["session_id"]))
    result = repo.purge_expired_cohort_data("institution-a")
    assert result["removed_sessions"] == 1
    remaining = [row["session_id"] for row in repo.list_sessions(institution_id="institution-a")]
    assert remaining == [new_session["session_id"]]


def test_backup_endpoint_writes_versioned_recovery_artifact(admin):
    with TestClient(app) as client:
        response = client.post("/api/v4/institution/recovery/backup", headers=admin)
        assert response.status_code == 200
        payload = response.json()
        assert APP_VERSION in Path(payload["backup"]).name
        assert len(payload["sha256"]) == 64
        listed = client.get("/api/v4/institution/recovery/backups", headers=admin).json()
        assert listed["count"] >= 1


def test_governance_readiness_states_the_enterprise_boundaries():
    with TestClient(app) as client:
        readiness = client.get("/api/v4/institution/governance/readiness").json()
    assert readiness["enterprise_sso_mfa"] == "not_implemented"
    assert readiness["production_multi_tenancy"] == "not_implemented"
    assert readiness["clinical_approval"] == "external_not_completed"
    assert readiness["formal_assessment"] == "blocked"
    assert readiness["rbac_session_roles"] == ["admin", "facilitator", "learner", "reviewer"]


def test_institutional_auth_migrates_legacy_tables_without_data_loss(tmp_path: Path):
    """An existing 5.0 database predates institution_id; rows must be preserved."""
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE hsptl_cohorts (
            cohort_id TEXT PRIMARY KEY, title TEXT NOT NULL, specialty TEXT NOT NULL,
            learner_level TEXT NOT NULL, status TEXT NOT NULL, privacy_notice TEXT NOT NULL,
            retention_days INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute("INSERT INTO hsptl_cohorts VALUES('legacy-1','Legacy cohort','General',"
                     "'Mixed','active','local only',365,'2026-01-01','2026-01-01')")
    InstitutionalAuth(db_path)
    repo = CohortRepository(db_path)
    rows = repo.list_cohorts("local")
    assert [row["cohort_id"] for row in rows] == ["legacy-1"]
    assert rows[0]["institution_id"] == "local"
    assert repo.list_cohorts("another-institution") == []


def test_safety_case_tenant_isolation(tmp_path: Path):
    repo = CohortRepository(tmp_path / "tenancy.sqlite3")
    case = repo.create_safety_case({
        "scenario_id": "asthma", "scenario_version": "1.0.0", "hazard": "hazard text",
        "safety_requirement": "requirement", "control": "control",
        "residual_risk": "residual", "clinical_owner": "Dr Owner",
    }, "institution-a")
    assert repo.list_safety_cases(institution_id="institution-b") == []
    assert [item["case_id"] for item in repo.list_safety_cases(
        institution_id="institution-a")] == [case["case_id"]]


# --------------------------------------------------------------------------- #
# Legacy access-table migration (regression for the 5.0.0 startup failure)
#
# A pre-5.0 database has hsptl_access_subjects, hsptl_access_sessions and
# hsptl_access_accounts without an institution_id column. The institution index
# references that column, so creating it before the migration fails with
# "no such column: institution_id" and leaves the schema half-migrated.
# --------------------------------------------------------------------------- #

LEGACY_ACCESS_SCHEMA = """
CREATE TABLE hsptl_access_subjects (
    subject_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE hsptl_access_sessions (
    session_id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, role TEXT NOT NULL,
    expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE hsptl_access_accounts (
    subject_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,
    password_salt TEXT NOT NULL, password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
"""

SESSION_INDEXES = {"idx_hsptl_access_sessions_subject",
                   "idx_hsptl_access_sessions_institution"}
ACCESS_TABLES = ("hsptl_access_subjects", "hsptl_access_sessions", "hsptl_access_accounts")


def _legacy_access_db(tmp_path: Path) -> Path:
    """Build a pre-5.0 database with live rows in all three access tables."""
    db_path = tmp_path / "legacy_access.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(LEGACY_ACCESS_SCHEMA)
        conn.execute("INSERT INTO hsptl_access_subjects VALUES"
                     "('legacy-1','Dr Legacy','reviewer',1,'2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO hsptl_access_sessions VALUES"
                     "('sess-legacy','legacy-1','reviewer','2030-01-01T00:00:00+00:00',"
                     "'2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO hsptl_access_accounts VALUES"
                     "('legacy-1','Dr Legacy','reviewer','salt','hash',1,"
                     "'2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')")
    return db_path


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _index_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")}


def test_institutional_auth_starts_against_legacy_access_tables(tmp_path: Path):
    """The 5.0.0 startup failure: init must not raise on a legacy database."""
    InstitutionalAuth(_legacy_access_db(tmp_path))


def test_legacy_access_tables_gain_institution_id(tmp_path: Path):
    db_path = _legacy_access_db(tmp_path)
    InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        for table in ACCESS_TABLES:
            assert "institution_id" in _columns(conn, table)


def test_legacy_access_rows_are_preserved_and_defaulted(tmp_path: Path):
    """Existing records must survive and be assigned the default institution."""
    db_path = _legacy_access_db(tmp_path)
    InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        subject = conn.execute(
            "SELECT subject_id, institution_id, display_name, role FROM hsptl_access_subjects"
        ).fetchone()
        session = conn.execute(
            "SELECT session_id, institution_id, subject_id, expires_at FROM hsptl_access_sessions"
        ).fetchone()
        account = conn.execute(
            "SELECT subject_id, institution_id, password_hash FROM hsptl_access_accounts"
        ).fetchone()
    assert (subject["subject_id"], subject["institution_id"]) == ("legacy-1", "local")
    assert (subject["display_name"], subject["role"]) == ("Dr Legacy", "reviewer")
    assert (session["session_id"], session["institution_id"]) == ("sess-legacy", "local")
    assert session["expires_at"] == "2030-01-01T00:00:00+00:00"
    assert (account["subject_id"], account["institution_id"]) == ("legacy-1", "local")
    assert account["password_hash"] == "hash"


def test_both_session_indexes_exist_after_migration(tmp_path: Path):
    db_path = _legacy_access_db(tmp_path)
    InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        assert _index_names(conn) >= SESSION_INDEXES


def test_institution_index_covers_institution_and_expiry(tmp_path: Path):
    db_path = _legacy_access_db(tmp_path)
    InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        indexed = [row[2] for row in conn.execute(
            "PRAGMA index_info(idx_hsptl_access_sessions_institution)")]
    assert indexed == ["institution_id", "expires_at"]


def test_institutional_auth_is_idempotent_across_repeated_init(tmp_path: Path):
    db_path = _legacy_access_db(tmp_path)
    for _ in range(5):
        InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        assert _index_names(conn) == SESSION_INDEXES
        for table in ACCESS_TABLES:
            assert _columns(conn, table).count("institution_id") == 1
        assert conn.execute("SELECT COUNT(*) FROM hsptl_access_subjects").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM hsptl_access_sessions").fetchone()[0] == 1


def test_init_repairs_a_half_migrated_schema(tmp_path: Path):
    """The old code left the subject index but no column; init must recover."""
    db_path = tmp_path / "half.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(LEGACY_ACCESS_SCHEMA)
        conn.execute("CREATE INDEX idx_hsptl_access_sessions_subject"
                     " ON hsptl_access_sessions(subject_id, expires_at)")
        conn.execute("INSERT INTO hsptl_access_sessions VALUES"
                     "('s1','u1','learner','2030-01-01','2026-01-01')")
    InstitutionalAuth(db_path)
    with sqlite3.connect(db_path) as conn:
        assert _index_names(conn) == SESSION_INDEXES
        assert "institution_id" in _columns(conn, "hsptl_access_sessions")
        assert conn.execute(
            "SELECT institution_id FROM hsptl_access_sessions WHERE session_id='s1'"
        ).fetchone()[0] == "local"


def test_failed_migration_rolls_back_and_preserves_data(tmp_path: Path, monkeypatch):
    """A mid-migration failure must leave the database exactly as it was."""
    db_path = tmp_path / "atomic.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(LEGACY_ACCESS_SCHEMA)
        conn.execute("INSERT INTO hsptl_access_subjects VALUES"
                     "('keep','Dr Keep','learner',1,'2026-01-01')")

    monkeypatch.setattr(InstitutionalAuth, "SESSION_INDEXES",
                        (("bad_index", "CREATE INDEX bad_index ON missing_table(x)"),))
    with pytest.raises(sqlite3.OperationalError):
        InstitutionalAuth(db_path)

    with sqlite3.connect(db_path) as conn:
        # No column was added to any table, no index was created, and the
        # pre-existing row is untouched.
        for table in ACCESS_TABLES:
            assert "institution_id" not in _columns(conn, table)
        assert _index_names(conn) == set()
        assert conn.execute("SELECT COUNT(*) FROM hsptl_access_subjects").fetchone()[0] == 1


def test_migrated_database_supports_login_and_sessions(tmp_path: Path, monkeypatch):
    """End to end: a legacy row is reachable through the normal API after migration."""
    db_path = _legacy_access_db(tmp_path)
    auth = InstitutionalAuth(db_path)
    created = auth.create_account("new-user", "New User", PASSWORD, "learner")
    assert created["institution_id"] == "local"
    session = auth.login("new-user", PASSWORD)
    assert session["subject_id"] == "new-user"
    assert auth.validate_session(session["session_id"], {"learner"})["subject_id"] == "new-user"


def test_application_startup_path_initialises_legacy_database(tmp_path: Path, monkeypatch):
    """The startup path that failed in 5.0.0: runtime imports and boots."""
    db_path = _legacy_access_db(tmp_path)
    monkeypatch.setenv("HSPTL_HOME", str(tmp_path))
    InstitutionalAuth(db_path)
    from backend.runtime import INSTITUTIONAL_AUTH
    assert INSTITUTIONAL_AUTH.db_path.exists()
    with sqlite3.connect(INSTITUTIONAL_AUTH.db_path) as conn:
        assert _index_names(conn) >= SESSION_INDEXES


def test_app_serves_governance_after_legacy_migration(tmp_path: Path, monkeypatch):
    db_path = _legacy_access_db(tmp_path)
    InstitutionalAuth(db_path)
    monkeypatch.setenv("HSPTL_ADMIN_TOKEN", ADMIN_TOKEN)
    with TestClient(app) as client:
        response = client.get("/api/v4/institution/governance/readiness",
                              headers={"X-HSPTL-Admin-Token": ADMIN_TOKEN})
    assert response.status_code == 200
    assert response.json()["rbac_session_roles"] == ["admin", "facilitator", "learner", "reviewer"]


def test_training_level_is_institution_assigned_and_persisted_in_login_session(admin):
    with TestClient(app) as client:
        response = client.post("/api/v4/institution/accounts", headers=admin, json={
            "subject_id": "resident-reviewer", "display_name": "Resident Reviewer",
            "password": PASSWORD, "role": "reviewer", "training_level": "resident",
        })
        assert response.status_code == 200, response.text
        assert response.json()["training_level"] == "resident"
        login = client.post("/api/v4/institution/login", json={
            "subject_id": "resident-reviewer", "password": PASSWORD,
        })
        assert login.status_code == 200, login.text
        assert login.json()["training_level"] == "resident"
        session = {"X-HSPTL-Session": login.json()["session_id"]}
        assert client.get("/api/v4/institution/session", headers=session).json()["training_level"] == "resident"
