from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from backend.main import app
from backend.hsptl_core.config import resolve_dev_port


def test_health_and_bootstrap():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["name"] == "HSPTL"
        bootstrap = client.get("/api/bootstrap")
        assert bootstrap.status_code == 200
        assert bootstrap.json()["note_types"]


def test_health_returns_unavailable_when_database_is_read_only(monkeypatch):
    original_connect = sqlite3.connect

    def readonly_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connection.execute("PRAGMA query_only = ON")
        return connection

    with TestClient(app) as client:
        monkeypatch.setattr(sqlite3, "connect", readonly_connect)
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "ok": False,
        "name": "HSPTL",
        "code": "database_not_writable",
    }


def test_clinic_puzzle_flow():
    with TestClient(app) as client:
        puzzles = client.get("/api/clinic/puzzles")
        assert puzzles.status_code == 200
        asthma = next(item for item in puzzles.json() if item["id"] == "asthma-001")
        started = client.post("/api/clinic/start", json={"puzzle_id": asthma["id"]})
        assert started.status_code == 200
        run = started.json()
        assert run["revealed"] == 1
        guessed = client.post("/api/clinic/guess", json={"run_id": run["run_id"], "guess": "asthma"})
        assert guessed.status_code == 200
        assert guessed.json()["result"] == "correct"
        assert guessed.json()["finished"] is True
        assert guessed.json()["answer"] == "Asthma"


def test_specialties_and_topic_detail():
    with TestClient(app) as client:
        response = client.get("/api/specialties")
        assert response.status_code == 200
        assert len(response.json()) >= 5
        cardiology = client.get("/api/specialties/cardiology")
        assert cardiology.status_code == 200
        assert cardiology.json()["topics"]
        assert cardiology.json()["topics"][0]["questions"]


def test_note_generation_save_and_recall_cards():
    with TestClient(app) as client:
        generated = client.post("/api/pearls/generate", json={
            "topic": "heart failure",
            "note_type": "Condition",
            "level": "Clinical years",
            "jurisdiction": "Egypt",
            "use_local_pdfs": False,
            "use_open_access": False,
        })
        assert generated.status_code == 200
        payload = generated.json()
        assert payload["note"]["curated_pack"]
        assert payload["note"]["sections"]
        saved = client.post("/api/pearls/save", json={"note": payload["note"]})
        assert saved.status_code == 200
        assert saved.json()["saved"] is True
        cards = client.post("/api/pearls/cards", json={"note": payload["note"]})
        assert cards.status_code == 200
        assert cards.json()["created"] >= 1


def test_theme_setting():
    with TestClient(app) as client:
        response = client.put("/api/settings/theme", json={"theme": "dark"})
        assert response.status_code == 200
        assert client.get("/api/settings").json()["theme"] == "dark"
        invalid = client.put("/api/settings/theme", json={"theme": "sepia"})
        assert invalid.status_code == 400


def test_connect_local_synthea_csv_folder(tmp_path, monkeypatch):
    from backend.main import PATHS

    monkeypatch.setitem(PATHS, "imports", tmp_path)
    patient_csv = tmp_path / "Patient.csv"
    patient_csv.write_text(
        'id,gender,birthDate,name\n'
        'patient-001,male,2010-02-03,"[{\\"given\\":[\\"Test\\"],\\"family\\":\\"Learner\\"}]"\n',
        encoding="utf-8",
    )
    with TestClient(app) as client:
        connected = client.post("/api/data/connect", json={"path": str(tmp_path)})
        assert connected.status_code == 200, connected.text
        assert connected.json()["connected"] is True
        assert connected.json()["patients"] == 1
        bootstrap = client.get("/api/bootstrap").json()
        assert bootstrap["data_ready"] is True
        assert bootstrap["patient_count"] >= 1


def test_fhir_case_engine_api_import_and_retrieval(tmp_path, monkeypatch):
    import json
    from backend.main import PATHS

    monkeypatch.setitem(PATHS, "imports", tmp_path)
    source = tmp_path / "synthea-fhir"
    source.mkdir()
    bundle = {
        "resourceType": "Bundle", "entry": [
            {"fullUrl": "urn:uuid:api-p1", "resource": {"resourceType": "Patient", "id": "api-p1", "gender": "male", "birthDate": "1988-02-01"}},
            {"resource": {"resourceType": "Encounter", "id": "api-e1", "subject": {"reference": "Patient/api-p1"}, "status": "finished", "period": {"start": "2024-02-01"}}},
            {"resource": {"resourceType": "Observation", "id": "api-o1", "subject": {"reference": "Patient/api-p1"}, "encounter": {"reference": "Encounter/api-e1"}, "code": {"text": "Pulse"}, "valueQuantity": {"value": 72, "unit": "beats/min"}}},
        ]
    }
    (source / "patient.json").write_text(json.dumps(bundle), encoding="utf-8")
    with TestClient(app) as client:
        imported = client.post("/api/clinical/fhir/import", json={"path": str(source), "batch_size": 25})
        assert imported.status_code == 200, imported.text
        assert imported.json()["patients"] == 1
        patients = client.get("/api/clinical/patients").json()
        patient = next(item for item in patients["items"] if item["source_patient_id"] == "api-p1")
        assert "raw_json" not in patient
        case = client.get(f"/api/clinical/patients/{patient['patient_key']}")
        assert case.status_code == 200
        assert case.json()["facts"][0]["code_text"] == "Pulse"
        assert "raw_json" not in case.json()["facts"][0]
        assert case.json()["quality"]["diagnostic_puzzle_eligible"] is False
        encounter_key = case.json()["encounters"][0]["encounter_key"]
        encounter_case = client.get(f"/api/clinical/patients/{patient['patient_key']}", params={"encounter_key": encounter_key})
        assert encounter_case.status_code == 200
        assert encounter_case.json()["scope"] == "encounter_linked_only"


def test_fhir_import_api_rejects_missing_directory():
    with TestClient(app) as client:
        response = client.post("/api/clinical/fhir/import", json={"path": "Z:/not-a-real-fhir-directory"})
        assert response.status_code == 400


def test_fhir_encounter_narrative_and_reasoning_attempt_api(tmp_path, monkeypatch):
    import json
    from backend.main import PATHS

    monkeypatch.setitem(PATHS, "imports", tmp_path)
    source = tmp_path / "narrative-fhir"
    source.mkdir()
    bundle = {
        "resourceType": "Bundle", "entry": [
            {"fullUrl": "urn:uuid:n-p1", "resource": {"resourceType": "Patient", "id": "n-p1", "gender": "female"}},
            {"resource": {"resourceType": "Encounter", "id": "n-e1", "subject": {"reference": "Patient/n-p1"}, "status": "finished", "period": {"start": "2025-03-01"}}},
            {"resource": {"resourceType": "Observation", "id": "n-o1", "subject": {"reference": "Patient/n-p1"}, "encounter": {"reference": "Encounter/n-e1"}, "code": {"text": "Heart rate"}, "valueQuantity": {"value": 88, "unit": "beats/min"}}},
            {"resource": {"resourceType": "Condition", "id": "n-c1", "subject": {"reference": "Patient/n-p1"}, "code": {"text": "Source condition"}}},
        ]
    }
    (source / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    with TestClient(app) as client:
        imported = client.post("/api/clinical/fhir/import", json={"path": str(source), "batch_size": 25})
        assert imported.status_code == 200
        patients = client.get("/api/clinical/patients").json()["items"]
        patient = next(item for item in patients if item["source_patient_id"] == "n-p1")
        encounter = client.get(f"/api/clinical/patients/{patient['patient_key']}").json()["encounters"][0]
        narrative = client.get(f"/api/clinical/patients/{patient['patient_key']}/encounters/{encounter['encounter_key']}/narrative")
        assert narrative.status_code == 200
        body = narrative.json()
        assert body["diagnostic_puzzle_eligible"] is False
        sections = {section["title"]: section for section in body["sections"]}
        assert sections["Presenting history"]["availability"] == "unavailable"
        assert sections["Examination"]["availability"] == "unavailable"
        assert sections["Observations and measurements"]["items"][0]["value"] == "88 beats/min"
        assert sections["Coded conditions"]["items"] == []
        saved = client.post("/api/clinical/learning-attempts", json={
            "patient_key": patient["patient_key"], "encounter_key": encounter["encounter_key"],
            "case_code": body["case_code"], "problem_representation": "Learner-authored summary",
            "differentials": ["Option A", "Option B"], "evidence_for": "Heart rate recorded",
            "evidence_against": "History unavailable", "investigation_plan": "Select targeted tests",
            "confidence": 3,
            "history_plan": ["Chest pain characteristics and radiation"],
            "examination_plan": ["Pulse, rhythm and peripheral perfusion"],
            "investigation_selection": ["ECG / physiological testing"],
            "specialty_pathway": "Cardiology",
        })
        assert saved.status_code == 200, saved.text
        assert saved.json()["saved"] is True
        from backend.main import CASE_STORE
        with CASE_STORE.connect() as conn:
            stored_attempt = conn.execute(
                "SELECT history_plan_json, examination_plan_json, investigation_selection_json, specialty_pathway FROM clinical_learning_attempts WHERE attempt_id=?",
                (saved.json()["attempt_id"],),
            ).fetchone()
        assert json.loads(stored_attempt["history_plan_json"]) == ["Chest pain characteristics and radiation"]
        assert json.loads(stored_attempt["examination_plan_json"]) == ["Pulse, rhythm and peripheral perfusion"]
        assert json.loads(stored_attempt["investigation_selection_json"]) == ["ECG / physiological testing"]
        assert stored_attempt["specialty_pathway"] == "Cardiology"
        assert saved.json()["feedback"]["type"] == "completeness_only"
        assert saved.json()["feedback"]["completed"] == 5
        invalid_confidence = client.post("/api/clinical/learning-attempts", json={
            "patient_key": patient["patient_key"], "encounter_key": encounter["encounter_key"],
            "case_code": body["case_code"], "confidence": 7,
        })
        assert invalid_confidence.status_code == 422


def test_data_path_endpoints_reject_directories_outside_approved_roots(tmp_path, monkeypatch):
    from backend.main import PATHS

    approved = tmp_path / "approved"
    outside = tmp_path / "outside"
    approved.mkdir()
    outside.mkdir()
    monkeypatch.setitem(PATHS, "imports", approved)

    with TestClient(app) as client:
        connected = client.post("/api/data/connect", json={"path": str(outside)})
        imported = client.post("/api/clinical/fhir/import", json={"path": str(outside)})

    assert connected.status_code == 400
    assert imported.status_code == 400


def test_security_headers_and_cors_origins():
    with TestClient(app) as client:
        for path in ("/api/health", "/api/not-a-route"):
            response = client.get(path)
            assert response.headers["content-security-policy"]
            assert response.headers["x-content-type-options"] == "nosniff"

        for origin in (f"http://127.0.0.1:{resolve_dev_port()}", f"http://localhost:{resolve_dev_port()}"):
            response = client.options(
                "/api/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin

        disallowed = client.options(
            "/api/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in disallowed.headers


def test_learning_attempt_can_be_converted_to_unverified_pearl():
    from backend.main import CASE_STORE

    with TestClient(app) as client:
        patient_key = "a" * 64
        encounter_key = "b" * 64
        with CASE_STORE.transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO clinical_patients (patient_key,source_key,source_patient_id,raw_json,updated_at) VALUES(?,?,?,?,?)",
                         (patient_key, "test-source", "test-patient", "{}", "2026-01-01T00:00:00+00:00"))
            conn.execute("INSERT OR IGNORE INTO clinical_encounters (encounter_key,patient_key,source_encounter_id,raw_json,source_file,updated_at) VALUES(?,?,?,?,?,?)",
                         (encounter_key, patient_key, "test-encounter", "{}", "test.json", "2026-01-01T00:00:00+00:00"))
        saved = client.post("/api/clinical/learning-attempts", json={
            "patient_key": patient_key, "encounter_key": encounter_key, "case_code": "SYN-TEST",
            "problem_representation": "Learner summary of documented facts", "differentials": ["Option A", "Option B"],
            "evidence_for": "Documented finding", "evidence_against": "Missing data acknowledged",
            "investigation_plan": "Consider what question a test would answer", "working_diagnosis": "",
            "management_plan": "", "safety_net": "", "communication_plan": "",
            "stage_completed": 3, "confidence": 3, "history_plan": [], "examination_plan": [],
            "investigation_selection": [], "specialty_pathway": "Emergency",
        })
        assert saved.status_code == 200
        attempt_id = saved.json()["attempt_id"]
        listed_attempts = client.get("/api/clinical/learning-attempts?limit=25")
        assert listed_attempts.status_code == 200
        assert any(item["attempt_id"] == attempt_id for item in listed_attempts.json()["items"])
        listed_record = next(item for item in listed_attempts.json()["items"] if item["attempt_id"] == attempt_id)
        assert listed_record["debrief_completed"] == 0
        saved_detail = client.get(f"/api/clinical/learning-attempts/{attempt_id}")
        assert saved_detail.status_code == 200
        assert saved_detail.json()["working_diagnosis"] == ""
        assert "patient_key" not in saved_detail.json()
        assert "encounter_key" not in saved_detail.json()
        pearl = client.post(f"/api/clinical/learning-attempts/{saved.json()['attempt_id']}/pearl", json={
            "focus": "Investigation strategy", "reflection": "I will practise linking each test to a clinical question."
        })
        assert pearl.status_code == 200
        detail = client.get(f"/api/pearls/saved/{pearl.json()['id']}")
        assert detail.status_code == 200
        note = detail.json()["note"]
        assert note["generated_mode"] == "learner_reflection_unverified"
        assert note["references"] == []
        assert note["provenance"]["verified"] is False
        assert any(section["title"] == "Learner reflection" for section in note["sections"])
        assert all(e["kind"] == "learner_reflection" for section in note["sections"] for e in section["evidence"])
        attempt_id = saved.json()["attempt_id"]
        initial_debrief = client.get(f"/api/clinical/learning-attempts/{attempt_id}/debrief")
        assert initial_debrief.status_code == 200
        assert initial_debrief.json()["completed"] == 0
        responses = {
            "setting": "Private learning exercise.",
            "reactions": "I was uncertain about missing history.",
            "description": "The record documented one observation; history was unavailable.",
            "analysis": "I should explain what each investigation would answer.",
            "summary": "I will practise a concise problem representation.",
        }
        stored_debrief = client.put(f"/api/clinical/learning-attempts/{attempt_id}/debrief", json={"responses": responses})
        assert stored_debrief.status_code == 200
        assert stored_debrief.json()["completed"] == 5
        reloaded = client.get(f"/api/clinical/learning-attempts/{attempt_id}/debrief")
        assert reloaded.json()["responses"] == responses
        assert client.get("/api/clinical/learning-attempts/not-real/debrief").status_code == 404


def test_learning_pearl_requires_reflection_and_valid_attempt():
    with TestClient(app) as client:
        missing = client.post("/api/clinical/learning-attempts/not-real/pearl", json={
            "focus": "Uncertainty", "reflection": "A sufficiently long reflection."
        })
        assert missing.status_code == 404
        invalid = client.post("/api/clinical/learning-attempts/not-real/pearl", json={
            "focus": "Uncertainty", "reflection": "short"
        })
        assert invalid.status_code == 422
