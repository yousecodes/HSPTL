"""Additive SQLite schema for the synthetic data factory.

All statements are ``CREATE ... IF NOT EXISTS`` and column additions are
guarded, so applying this to an existing 4.0.2 database is a no-op for learner
data and idempotent across restarts. Nothing here drops or rewrites a table.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS synthetic_recipes (
    recipe_id TEXT NOT NULL,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    owner TEXT NOT NULL DEFAULT 'local',
    builtin INTEGER NOT NULL DEFAULT 0,
    body_json TEXT NOT NULL,
    content_digest TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (recipe_id, version)
);

CREATE TABLE IF NOT EXISTS synthetic_dataset_runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT NOT NULL DEFAULT 'queued',
    stage_index INTEGER NOT NULL DEFAULT 0,
    attempt INTEGER NOT NULL DEFAULT 0,
    dataset_id TEXT NOT NULL DEFAULT '',
    staging_path TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    diagnostic TEXT NOT NULL DEFAULT '',
    counts_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_synthetic_run_idempotency
    ON synthetic_dataset_runs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_synthetic_run_job ON synthetic_dataset_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_synthetic_run_status ON synthetic_dataset_runs(status, updated_at);

CREATE TABLE IF NOT EXISTS synthetic_datasets (
    dataset_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'accepted',
    cohort_status TEXT NOT NULL DEFAULT 'complete',
    seed TEXT NOT NULL DEFAULT '',
    synthea_version TEXT NOT NULL DEFAULT '',
    fhir_version TEXT NOT NULL DEFAULT '4.0.1',
    manifest_digest TEXT NOT NULL DEFAULT '',
    content_digest TEXT NOT NULL DEFAULT '',
    generated_patients INTEGER NOT NULL DEFAULT 0,
    matched_patients INTEGER NOT NULL DEFAULT 0,
    accepted_patients INTEGER NOT NULL DEFAULT 0,
    quarantined_patients INTEGER NOT NULL DEFAULT 0,
    imported_patients INTEGER NOT NULL DEFAULT 0,
    validation_status TEXT NOT NULL DEFAULT 'pending',
    strict_conformance INTEGER NOT NULL DEFAULT 0,
    terminology_status TEXT NOT NULL DEFAULT 'pending',
    storage_bytes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synthetic_dataset_status ON synthetic_datasets(status, created_at);

CREATE TABLE IF NOT EXISTS synthetic_dataset_artifacts (
    artifact_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    kind TEXT NOT NULL,
    byte_size INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    immutable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synthetic_artifact_dataset ON synthetic_dataset_artifacts(dataset_id, kind);

CREATE TABLE IF NOT EXISTS synthetic_quality_findings (
    finding_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    patient_key TEXT NOT NULL DEFAULT '',
    dimension TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_version TEXT NOT NULL DEFAULT '1',
    severity TEXT NOT NULL,
    resource_type TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synthetic_finding_dataset ON synthetic_quality_findings(dataset_id, dimension, severity);

CREATE TABLE IF NOT EXISTS synthetic_quarantine_items (
    item_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    patient_key TEXT NOT NULL,
    bundle_path TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL,
    rule_ids_json TEXT NOT NULL DEFAULT '[]',
    severity TEXT NOT NULL DEFAULT 'quarantine',
    status TEXT NOT NULL DEFAULT 'open',
    reviewer TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synthetic_quarantine_status ON synthetic_quarantine_items(dataset_id, status);

CREATE TABLE IF NOT EXISTS synthetic_schedules (
    schedule_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    recipe_version TEXT NOT NULL,
    population INTEGER NOT NULL DEFAULT 5,
    accepted_target INTEGER NOT NULL DEFAULT 0,
    frequency TEXT NOT NULL DEFAULT 'weekly',
    enabled INTEGER NOT NULL DEFAULT 0,
    last_run_at TEXT NOT NULL DEFAULT '',
    next_run_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS synthetic_review_actions (
    action_id TEXT PRIMARY KEY,
    item_kind TEXT NOT NULL,
    item_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL DEFAULT '',
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synthetic_review_item ON synthetic_review_actions(item_kind, item_id);

CREATE TABLE IF NOT EXISTS synthetic_factory_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def apply(conn: sqlite3.Connection) -> None:
    """Create factory tables. Safe to call on every startup."""
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
        (1000 + SCHEMA_VERSION, _now()),
    )
