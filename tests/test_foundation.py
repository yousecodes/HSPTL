from __future__ import annotations

import json
import sqlite3
import sys

from fastapi.testclient import TestClient

from backend.hsptl_core.capabilities import capability_report
from backend.hsptl_core.exams import ExamRepository
from backend.hsptl_core.migrations import apply as apply_migrations
from backend.hsptl_core.store import StudyStore
from backend.main import app


def test_core_capabilities_do_not_require_optional_packages():
    report = capability_report()
    assert report["core"]["status"] == "available"
    assert "clinic" in report["core"]["features"]
    assert report["policy"]["optional_dependencies_imported_at_startup"] is False
    assert report["policy"]["ragas_in_normal_runtime"] is False
    assert report["policy"]["presidio_is_complete_deidentification"] is False
    assert "ragas" not in sys.modules


def test_note_save_is_idempotent_and_versions_changes(tmp_path):
    store = StudyStore(tmp_path / "hsptl.sqlite3")
    first = store.save_note("Pearl", "Asthma", "Initial note", "Source A")
    same = store.save_note("Pearl", "Asthma", "Initial note", "Source A")
    changed = store.save_note("Pearl", "Asthma", "Revised note", "Source B")

    assert first["created"] is True and first["version"] == 1
    assert same["id"] == first["id"] and same["updated"] is False
    assert changed["id"] == first["id"] and changed["version"] == 2
    with store.transaction() as conn:
        versions = conn.execute(
            "SELECT version, body FROM study_note_versions WHERE note_id=?", (first["id"],)
        ).fetchall()
    assert [(row["version"], row["body"]) for row in versions] == [(1, "Initial note")]
    assert store.notes()[0]["body"] == "Revised note"


def test_local_search_works_without_chroma(tmp_path):
    store = StudyStore(tmp_path / "search.sqlite3")
    store.save_note("Pearl", "Acute asthma", "Wheeze and reversible airflow obstruction", "Teaching source")
    results = store.search_notes("reversible airflow", limit=10)
    assert results
    assert results[0]["title"] == "Acute asthma"


def test_background_jobs_pause_resume_and_checkpoint(tmp_path):
    store = StudyStore(tmp_path / "jobs.sqlite3")
    job_id = store.create_job("model_indexing", {"collection": "pearls"})
    assert store.update_job(job_id, status="running", progress_done=20, progress_total=100,
                            checkpoint={"last_document_id": "doc-20"})
    assert store.update_job(job_id, status="paused")
    job = store.jobs()[0]
    assert job["status"] == "paused"
    assert job["progress_done"] == 20
    assert job["checkpoint"] == {"last_document_id": "doc-20"}
    assert store.update_job(job_id, status="queued")


def test_lifetime_stats_are_not_limited_by_recent_page(tmp_path):
    store = StudyStore(tmp_path / "progress.sqlite3")
    with store.transaction() as conn:
        rows = [
            (f"attempt-{i}", f"patient-{i}", 1, "answer", "{}", "2026-11-17T00:00:00+00:00", "2026-11-17T00:00:00+00:00")
            for i in range(1205)
        ]
        conn.executemany("""
            INSERT INTO stage_attempts(id, patient_key, stage_index, answer, rubric_json, created_at, updated_at)
            VALUES(?,?,?,?,?,?,?)
        """, rows)
    first_page = store.notes(limit=10, offset=0)
    assert first_page == []
    assert store.stats()["attempts"] == 1205


def test_backup_contains_committed_data(tmp_path):
    store = StudyStore(tmp_path / "source.sqlite3")
    store.save_note("Pearl", "Backup check", "Persisted")
    backup = store.backup_to(tmp_path / "backup.sqlite3")
    conn = sqlite3.connect(backup)
    try:
        row = conn.execute("SELECT title, body FROM study_notes").fetchone()
    finally:
        conn.close()
    assert row == ("Backup check", "Persisted")


def test_legacy_exam_tables_are_preserved_when_current_schema_is_created(tmp_path):
    database = tmp_path / "legacy-exams.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE question_bank (id TEXT PRIMARY KEY);
        INSERT INTO question_bank (id) VALUES ('q-1');
        CREATE TABLE exams (
            id TEXT PRIMARY KEY, title TEXT NOT NULL,
            specialty TEXT NOT NULL DEFAULT 'Mixed',
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            source_description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE exam_items (
            exam_id TEXT NOT NULL, question_id TEXT NOT NULL, position INTEGER NOT NULL,
            PRIMARY KEY(exam_id, position),
            FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY(question_id) REFERENCES question_bank(id)
        );
        CREATE TABLE exam_attempts (
            id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, score INTEGER NOT NULL,
            total INTEGER NOT NULL, responses_json TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0, completed_at TEXT NOT NULL,
            FOREIGN KEY(exam_id) REFERENCES exams(id)
        );
        INSERT INTO exams (id, title, created_at) VALUES ('e-1', 'Legacy exam', '2025-01-01');
        INSERT INTO exam_items (exam_id, question_id, position) VALUES ('e-1', 'q-1', 0);
        INSERT INTO exam_attempts (id, exam_id, score, total, responses_json, completed_at)
            VALUES ('a-1', 'e-1', 1, 1, '{}', '2025-01-01');
    """)
    try:
        apply_migrations(conn)
        current_columns = {row[1] for row in conn.execute("PRAGMA table_info(exams)")}
        assert "exam_id" in current_columns
        assert conn.execute("SELECT id FROM legacy_exams_v1").fetchone()[0] == "e-1"
        assert conn.execute("SELECT question_id FROM legacy_exam_items_v1").fetchone()[0] == "q-1"
        assert conn.execute("SELECT id FROM legacy_exam_attempts_v1").fetchone()[0] == "a-1"
    finally:
        conn.close()

    assert ExamRepository(database).exams() == []


def test_api_exposes_capabilities_progress_search_and_resumable_jobs():
    with TestClient(app) as client:
        capabilities = client.get("/api/system/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["core"]["status"] == "available"

        progress = client.get("/api/progress")
        assert progress.status_code == 200
        assert progress.json()["scope"] == "all_saved_activity"
        assert "lifetime" in progress.json()

        created = client.post("/api/jobs", json={"kind": "model_indexing", "payload": {"collection": "test"}})
        assert created.status_code == 200
        job_id = created.json()["id"]
        assert client.post(f"/api/jobs/{job_id}/pause").status_code == 200
        assert client.post(f"/api/jobs/{job_id}/resume").status_code == 200


def test_reference_upload_is_streamed_and_validated(tmp_path, monkeypatch):
    import io
    from pypdf import PdfWriter
    from backend.main import PATHS

    monkeypatch.setitem(PATHS, "references", tmp_path)
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(pdf)

    with TestClient(app) as client:
        valid = client.post("/api/pearls/references", files={"file": ("tiny.pdf", pdf.getvalue(), "application/pdf")})
        assert valid.status_code == 200, valid.text
        assert valid.json()["saved"] is True

        invalid = client.post("/api/pearls/references", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
        assert invalid.status_code == 400
        malformed = client.post("/api/pearls/references", files={"file": ("malformed.pdf", b"%PDF-1.4\nnot a valid PDF", "application/pdf")})
        assert malformed.status_code == 400
        wrong_mime = client.post("/api/pearls/references", files={"file": ("tiny.pdf", pdf.getvalue(), "application/octet-stream")})
        assert wrong_mime.status_code == 415


def test_clinical_fact_requires_provenance_for_documented_and_derived_values():
    from backend.hsptl_core.provenance import ClinicalFact, FactStatus, unavailable_fact

    documented = ClinicalFact("heart_rate", 88, FactStatus.DOCUMENTED,
                              source_type="Observation", source_id="obs-1")
    derived = ClinicalFact("age_at_encounter", 9, FactStatus.DERIVED,
                          derivation="Encounter date minus documented birth date")
    unavailable = unavailable_fact("oxygen_saturation")
    assert documented.to_dict()["status"] == "documented"
    assert derived.to_dict()["derivation"]
    assert unavailable.value is None

    import pytest
    with pytest.raises(ValueError):
        ClinicalFact("diagnosis", "asthma", FactStatus.DOCUMENTED)
    with pytest.raises(ValueError):
        ClinicalFact("age", 9, FactStatus.DERIVED)


def test_egyptian_medication_mapping_never_guesses_rxnorm_code():
    from backend.hsptl_core.terminology import resolve_medication

    mappings = [{
        "aliases": ["verified local brand"], "code": "12345", "display": "Example ingredient",
        "source": "Reviewed Egyptian formulary mapping", "jurisdiction": "Egypt",
    }]
    matched = resolve_medication("Verified Local Brand", mappings, "Egypt")
    unmatched = resolve_medication("Unmapped Egyptian trade name", mappings, "Egypt")
    wrong_region = resolve_medication("Verified Local Brand", mappings, "UK")
    assert matched["status"] == "matched" and matched["code"] == "12345"
    assert unmatched["status"] == "unmatched" and unmatched["code"] is None
    assert wrong_region["status"] == "unmatched" and wrong_region["code"] is None


def test_umls_export_is_blocked_without_licence_or_source_permission():
    from backend.hsptl_core.terminology import umls_export_allowed

    allowed, _ = umls_export_allowed(licence_active=False, requested_sources=["SNOMEDCT_US"],
                                     export_permitted_sources={"SNOMEDCT_US"})
    assert allowed is False
    allowed, _ = umls_export_allowed(licence_active=True, requested_sources=["SNOMEDCT_US", "Other"],
                                     export_permitted_sources={"SNOMEDCT_US"})
    assert allowed is False
    allowed, _ = umls_export_allowed(licence_active=True, requested_sources=["LOINC"],
                                     export_permitted_sources={"LOINC"})
    assert allowed is True


def test_fts_search_falls_back_to_like_when_fts5_is_disabled(tmp_path):
    store = StudyStore(tmp_path / "fallback.sqlite3")
    store.save_note("Pearl", "Pneumonia", "Consolidation and fever")
    store.fts_available = False
    assert store.search_notes("Consolidation")


def test_deterministic_fhir_folder_load_does_not_require_llamaindex(tmp_path, monkeypatch):
    from backend.main import PATHS

    monkeypatch.setitem(PATHS, "imports", tmp_path)
    patient = {
        "resourceType": "Patient", "id": "p-001", "gender": "female",
        "birthDate": "2000-01-01", "name": [{"given": ["Test"], "family": "Patient"}],
    }
    encounter = {
        "resourceType": "Encounter", "id": "e-001", "subject": {"reference": "Patient/p-001"},
        "period": {"start": "2026-01-01T10:00:00Z"}, "status": "finished",
    }
    (tmp_path / "patient.json").write_text(json.dumps(patient), encoding="utf-8")
    (tmp_path / "encounter.json").write_text(json.dumps(encounter), encoding="utf-8")
    with TestClient(app) as client:
        response = client.post("/api/data/connect", json={"path": str(tmp_path)})
    assert response.status_code == 200, response.text
    assert response.json()["patients"] == 1
    assert "llama_index" not in sys.modules


def test_api_search_uses_sqlite_when_chroma_is_not_installed():
    with TestClient(app) as client:
        generated = client.post("/api/pearls/generate", json={
            "topic": "heart failure", "note_type": "Condition", "level": "Clinical years",
            "jurisdiction": "Egypt", "use_local_pdfs": False, "use_open_access": False,
        })
        assert generated.status_code == 200
        saved = client.post("/api/pearls/save", json={"note": generated.json()["note"]})
        assert saved.status_code == 200
        saved_again = client.post("/api/pearls/save", json={"note": generated.json()["note"]})
        assert saved_again.json()["id"] == saved.json()["id"]
        result = client.get("/api/search", params={"q": "heart failure"})
        assert result.status_code == 200
        assert result.json()["engine"] in {"sqlite_fts5", "sqlite_like_fallback"}


def test_dataset_discovery_recognises_fhir_patient_bundles(tmp_path):
    from backend.hsptl_core.config import discover_dataset_dirs

    bundle = {
        "resourceType": "Bundle", "type": "collection",
        "entry": [{"resource": {"resourceType": "Patient", "id": "p-fhir-1"}}],
    }
    (tmp_path / "patient-bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    found = discover_dataset_dirs({"dataset_dirs": [str(tmp_path)]})
    assert tmp_path.resolve() in found
