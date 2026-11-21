"""Idempotent additive Phase 2-4 schema migrations. No destructive statements."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 13

DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_refs (
    ref_id TEXT PRIMARY KEY, kind TEXT NOT NULL, locator TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '', citation TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT NOT NULL DEFAULT '', jurisdiction TEXT NOT NULL DEFAULT '',
    license TEXT NOT NULL DEFAULT '', review_date TEXT NOT NULL DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0, snapshot_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, UNIQUE(kind, locator, snapshot_hash));
CREATE TABLE IF NOT EXISTS content_sources (
    owner_kind TEXT NOT NULL, owner_id TEXT NOT NULL,
    ref_id TEXT NOT NULL REFERENCES source_refs(ref_id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(owner_kind, owner_id, ref_id));
CREATE INDEX IF NOT EXISTS idx_content_sources_ref ON content_sources(ref_id);
CREATE TABLE IF NOT EXISTS learning_episodes (
    episode_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL DEFAULT 'local',
    source_type TEXT NOT NULL, source_id TEXT NOT NULL,
    content_version_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active',
    learning_goal TEXT NOT NULL DEFAULT '', specialty TEXT NOT NULL DEFAULT '',
    jurisdiction TEXT NOT NULL DEFAULT '',
    provenance_status TEXT NOT NULL DEFAULT 'source_documented',
    stage INTEGER NOT NULL DEFAULT 1, draft_json TEXT NOT NULL DEFAULT '{}',
    draft_revision INTEGER NOT NULL DEFAULT 0, idempotency_key TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_identity
    ON learning_episodes(profile_id, source_type, source_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_episode_resume
    ON learning_episodes(profile_id, status, updated_at DESC);
CREATE TABLE IF NOT EXISTS learning_artifacts (
    artifact_id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL REFERENCES learning_episodes(episode_id) ON DELETE CASCADE,
    kind TEXT NOT NULL, body_json TEXT NOT NULL DEFAULT '{}',
    authored_by TEXT NOT NULL DEFAULT 'learner',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    version INTEGER NOT NULL DEFAULT 1, content_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifact_idempotent
    ON learning_artifacts(episode_id, kind, content_hash);
CREATE TABLE IF NOT EXISTS artifact_links (
    parent_kind TEXT NOT NULL, parent_id TEXT NOT NULL,
    child_kind TEXT NOT NULL, child_id TEXT NOT NULL,
    relation TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(parent_kind, parent_id, child_kind, child_id, relation));
CREATE TABLE IF NOT EXISTS exam_questions (
    question_id TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'MCQ',
    specialty TEXT NOT NULL DEFAULT 'General medicine',
    difficulty TEXT NOT NULL DEFAULT 'Intermediate',
    reviewed INTEGER NOT NULL DEFAULT 0, reviewer TEXT NOT NULL DEFAULT '',
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exam_question_versions (
    version_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES exam_questions(question_id) ON DELETE CASCADE,
    version INTEGER NOT NULL, payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(question_id, version));
CREATE TABLE IF NOT EXISTS exams (
    exam_id TEXT PRIMARY KEY, title TEXT NOT NULL,
    specialty TEXT NOT NULL DEFAULT 'Mixed', difficulty TEXT NOT NULL DEFAULT 'Any',
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    blueprint_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exam_items (
    exam_id TEXT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    question_version_id TEXT NOT NULL REFERENCES exam_question_versions(version_id),
    PRIMARY KEY(exam_id, position));
CREATE TABLE IF NOT EXISTS exam_attempts (
    attempt_id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    episode_id TEXT NOT NULL DEFAULT '', snapshot_json TEXT NOT NULL,
    responses_json TEXT NOT NULL DEFAULT '{}', server_started_at TEXT NOT NULL,
    submitted_at TEXT, duration_seconds INTEGER NOT NULL DEFAULT 0,
    client_duration_seconds INTEGER NOT NULL DEFAULT 0,
    timing_source TEXT NOT NULL DEFAULT 'practice',
    timing_clamped INTEGER NOT NULL DEFAULT 0,
    score INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
    percentage REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS card_reviews (
    review_id TEXT PRIMARY KEY, card_id TEXT NOT NULL, grade TEXT NOT NULL,
    scheduler TEXT NOT NULL, state_before TEXT NOT NULL DEFAULT 'new',
    state_after TEXT NOT NULL DEFAULT 'learning',
    elapsed_days INTEGER NOT NULL DEFAULT 0, scheduled_days INTEGER NOT NULL DEFAULT 0,
    stability REAL NOT NULL DEFAULT 0, difficulty REAL NOT NULL DEFAULT 0,
    reviewed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_card_reviews_card ON card_reviews(card_id, reviewed_at);
CREATE TABLE IF NOT EXISTS osce_attempts (
    attempt_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    version_id TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL DEFAULT '',
    correct INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    submitted_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_osce_attempts_question
    ON osce_attempts(question_id, submitted_at);
CREATE TABLE IF NOT EXISTS external_sources (
    cache_key TEXT PRIMARY KEY, url TEXT NOT NULL, query TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'article', open_access INTEGER NOT NULL DEFAULT 0,
    license TEXT NOT NULL DEFAULT '', license_url TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}', payload_hash TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ok');
CREATE TABLE IF NOT EXISTS content_review_items (
    item_id TEXT PRIMARY KEY, owner_kind TEXT NOT NULL, owner_id TEXT NOT NULL,
    reason TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'warning',
    status TEXT NOT NULL DEFAULT 'open', reviewer TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, resolved_at TEXT,
    UNIQUE(owner_kind, owner_id, reason));
CREATE INDEX IF NOT EXISTS idx_review_queue_status ON content_review_items(status, created_at);
CREATE TABLE IF NOT EXISTS learning_tags (
    tag_id TEXT PRIMARY KEY,
    facet TEXT NOT NULL,
    label TEXT NOT NULL,
    parent_tag_id TEXT REFERENCES learning_tags(tag_id),
    aliases_json TEXT NOT NULL DEFAULT '[]',
    vocabulary TEXT NOT NULL DEFAULT 'hsptl_local',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(facet, label));
CREATE INDEX IF NOT EXISTS idx_learning_tags_facet ON learning_tags(facet, label);
CREATE TABLE IF NOT EXISTS tagged_content_items (
    item_id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    title TEXT NOT NULL,
    workspace TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source_status TEXT NOT NULL DEFAULT 'unreviewed',
    content_url TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    UNIQUE(content_type, content_id));
CREATE INDEX IF NOT EXISTS idx_tagged_content_workspace ON tagged_content_items(workspace, updated_at DESC);
CREATE TABLE IF NOT EXISTS content_tag_links (
    item_id TEXT NOT NULL REFERENCES tagged_content_items(item_id) ON DELETE CASCADE,
    tag_id TEXT NOT NULL REFERENCES learning_tags(tag_id),
    assigned_by TEXT NOT NULL DEFAULT 'system',
    assigned_at TEXT NOT NULL,
    PRIMARY KEY(item_id, tag_id));
CREATE INDEX IF NOT EXISTS idx_content_tag_links_tag ON content_tag_links(tag_id, item_id);
CREATE TABLE IF NOT EXISTS tag_learning_events (
    event_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES tagged_content_items(item_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    score REAL,
    max_score REAL,
    confidence TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tag_learning_events_item ON tag_learning_events(item_id, occurred_at DESC);
"""


def _add(conn: sqlite3.Connection, table: str, additions: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if not existing:
        return  # owning repository has not created its base table yet
    for column, definition in additions.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _migrate_legacy_exam_tables(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(exams)")}
    if not columns or "exam_id" in columns or "id" not in columns:
        return

    legacy_tables = (
        ("exam_attempts", "legacy_exam_attempts_v1"),
        ("exam_items", "legacy_exam_items_v1"),
        ("exams", "legacy_exams_v1"),
    )
    for table, legacy_table in legacy_tables:
        if not _table_exists(conn, table):
            continue
        if _table_exists(conn, legacy_table):
            raise sqlite3.OperationalError(
                f"Cannot migrate legacy exam schema: {legacy_table} already exists"
            )
        conn.execute(f"ALTER TABLE {table} RENAME TO {legacy_table}")


def apply(conn: sqlite3.Connection) -> None:
    _migrate_legacy_exam_tables(conn)
    conn.executescript(DDL)
    _add(conn, "study_notes", {
        "note_type": "TEXT NOT NULL DEFAULT ''",
        "specialty": "TEXT NOT NULL DEFAULT ''",
        "jurisdiction": "TEXT NOT NULL DEFAULT ''",
        "provenance_status": "TEXT NOT NULL DEFAULT 'learner_authored'",
        "review_status": "TEXT NOT NULL DEFAULT 'unreviewed'",
        "review_date": "TEXT NOT NULL DEFAULT ''",
        "origin_episode_id": "TEXT NOT NULL DEFAULT ''",
        "origin_artifact_id": "TEXT NOT NULL DEFAULT ''",
        "has_sources": "INTEGER NOT NULL DEFAULT 0"})
    _add(conn, "revision_cards", {
        "state": "TEXT NOT NULL DEFAULT 'new'",
        "stability": "REAL NOT NULL DEFAULT 0",
        "difficulty": "REAL NOT NULL DEFAULT 0",
        "lapses": "INTEGER NOT NULL DEFAULT 0",
        "scheduler": "TEXT NOT NULL DEFAULT 'simple'",
        "origin_note_id": "TEXT NOT NULL DEFAULT ''",
        "origin_episode_id": "TEXT NOT NULL DEFAULT ''",
        "origin_artifact_id": "TEXT NOT NULL DEFAULT ''",
        "source_ref_id": "TEXT NOT NULL DEFAULT ''",
        "needs_source_review": "INTEGER NOT NULL DEFAULT 0"})
    _add(conn, "clinical_learning_attempts", {
        "episode_id": "TEXT NOT NULL DEFAULT ''",
        "expected_missing": "TEXT NOT NULL DEFAULT ''",
        "next_discriminating_question": "TEXT NOT NULL DEFAULT ''",
        "cited_fact_keys_json": "TEXT NOT NULL DEFAULT '[]'",
        "prioritisation_rationale": "TEXT NOT NULL DEFAULT ''"})
    _add(conn, "background_jobs", {
        "lease_owner": "TEXT NOT NULL DEFAULT ''",
        "lease_expires_at": "TEXT NOT NULL DEFAULT ''",
        "heartbeat_at": "TEXT NOT NULL DEFAULT ''",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 5",
        "next_attempt_at": "TEXT NOT NULL DEFAULT ''",
        "cancel_requested": "INTEGER NOT NULL DEFAULT 0",
        "result_json": "TEXT NOT NULL DEFAULT '{}'"})
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for version in range(7, SCHEMA_VERSION + 1):
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            (version, now))
