from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.clinical_simulation import ScenarioCatalog
from backend.hsptl_core.hsp_tl40.event_contracts import EVENT_SCHEMAS, validate_event_payload
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.scenario_authoring import ScenarioAuthoring, ScenarioAuthoringError
from backend.hsptl_core.hsp_tl40.proforma import evaluate


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "fixtures" / "scenarios" / "asthma-moderate-adult-001" / "scenario.json"


def test_402_event_contracts_cover_learning_curriculum_and_scenario_lifecycle():
    assert {
        "platform.curriculum.draft_created", "platform.curriculum.activated",
        "platform.learning.unit_opened", "platform.learning.quiz_submitted",
        "platform.scenario.draft_saved", "platform.scenario.published",
    }.issubset(EVENT_SCHEMAS)
    valid_quiz = {
        "attempt_id": "quiz_1", "idempotency_key": "attempt-key-0001", "learner_id": "local-default",
        "curriculum_id": "", "curriculum_version": 0, "unit_id": "acute-asthma-01",
        "pack_id": "acute-care-foundations", "pack_version": "1.0.0", "score": 2, "maximum": 3,
        "responses": [{"index": 0}, {"index": 1}, {"index": 2}], "objective_results": [],
        "submitted_at": "2026-11-20T00:00:00+00:00",
    }
    assert validate_event_payload("platform.learning.quiz_submitted", valid_quiz) == (True, "")
    invalid = {**valid_quiz, "score": 4}
    assert validate_event_payload("platform.learning.quiz_submitted", invalid)[0] is False


def test_402_kernel_appends_new_learning_events_to_existing_ledger(tmp_path):
    engine = DeterministicIntelligenceEngine(tmp_path / "events.sqlite3")
    kernel = EventKernel(engine)
    opened = kernel.append("platform.learning.unit_opened", {
        "learner_id": "local-default", "curriculum_id": "", "curriculum_version": 0,
        "unit_id": "acute-asthma-01", "pack_id": "acute-care-foundations", "pack_version": "1.0.0",
    })
    assert opened["event_type"] == "platform.learning.unit_opened"
    assert kernel.platform_events()[-1]["event_id"] == opened["event_id"]
    assert kernel.replay()["verified"] is True


def test_402_curriculum_unlock_predicate_uses_proforma_three_valued_logic():
    predicate = {"op": "set_includes", "left": {"ref": "learner.completed_units"}, "right": ["unit-a"]}
    assert evaluate(predicate, {"learner": {"completed_units": ["unit-a"]}}).state == "pass"
    assert evaluate(predicate, {"learner": {"completed_units": []}}).state == "fail"
    assert evaluate(predicate, {}).state == "abstain"


def test_402_scenario_drafts_are_immutable_and_publish_to_catalog(tmp_path, monkeypatch):
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    scenario["scenario_id"] = "educator-scenario-test"
    scenario["title"] = "Educator scenario test"
    authoring = ScenarioAuthoring(tmp_path / "user-data")
    validation = authoring.validate(scenario)
    assert validation["valid"] is True
    saved = authoring.save_draft(scenario)
    assert saved["clinical_review_status"] == "draft_pending_clinical_review"
    assert saved["scenario_digest"]
    assert authoring.save_draft(scenario)["reused"] is True

    changed = json.loads(json.dumps(scenario))
    changed["title"] = "Changed without a version increment"
    with pytest.raises(ScenarioAuthoringError, match="immutable"):
        authoring.save_draft(changed)

    monkeypatch.setenv("HSPTL_CLINICAL_REVIEWER_TOKEN", "x" * 40)
    monkeypatch.setenv("HSPTL_CLINICAL_REVIEWER_ID", "qualified-reviewer-id")
    published = authoring.publish("educator-scenario-test", "x" * 40)
    assert published["published"] is True
    catalog = ScenarioCatalog(root=tmp_path / "empty-package-catalog", additional_roots=[authoring.published])
    assert catalog.load("educator-scenario-test")["clinical_review_status"] == "approved"


def test_402_scenario_authoring_rejects_missing_proforma_model(tmp_path):
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    scenario["scenario_id"] = "educator-invalid-test"
    scenario["action_catalogue"]["focused_assessment"]["model_path"] = "simulation/not-a-real-model.json"
    result = ScenarioAuthoring(tmp_path / "user-data").validate(scenario)
    assert result["valid"] is False
    assert any("invalid PROforma model" in item for item in result["errors"])


def test_402_learning_attempts_and_reviewer_activated_curriculum_are_end_to_end(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "reviewer-token-" + "r" * 40)
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "curriculum-reviewer")
    with TestClient(app) as client:
        catalog = client.get("/api/content-factory/catalog").json()
        unit_ids = [item["unit_id"] for item in catalog["units"][:2]]
        composed = client.post("/api/content-factory/curricula/compose", json={
            "title": "4.0.2 pathway integration fixture", "unit_ids": unit_ids,
            "prerequisites": {unit_ids[0]: [], unit_ids[1]: [unit_ids[0]]},
        })
        assert composed.status_code == 201, composed.text
        curriculum_id = composed.json()["curriculum"]["curriculum_id"]
        activated = client.post(f"/api/content-factory/curricula/{curriculum_id}/activate",
                                headers={"X-HSPTL-Reviewer-Token": "reviewer-token-" + "r" * 40})
        assert activated.status_code == 200, activated.text

        projection = client.get("/api/content-factory/curricula").json()
        assert projection["active"]["curriculum_id"] == curriculum_id
        assert projection["eligible_unit_ids"] == [unit_ids[0]]
        version = projection["active"]["version"]
        locked = client.post(f"/api/content-factory/units/{unit_ids[1]}/opened",
                             params={"curriculum_id": curriculum_id, "curriculum_version": version})
        assert locked.status_code == 409

        detail_response = client.get(f"/api/content-factory/units/{unit_ids[0]}",
                                     params={"curriculum_id": curriculum_id, "curriculum_version": version})
        assert detail_response.status_code == 200, detail_response.text
        detail = detail_response.json()
        answers = {str(index): question["correct_index"] for index, question in enumerate(detail["quiz"])}
        request = {"answers": answers, "idempotency_key": "pathway-test-attempt-0001",
                   "curriculum_id": curriculum_id, "curriculum_version": version}
        submitted = client.post(f"/api/content-factory/units/{unit_ids[0]}/attempts", json=request)
        assert submitted.status_code == 201, submitted.text
        assert submitted.json()["attempt"]["score"] == len(detail["quiz"])
        retry = client.post(f"/api/content-factory/units/{unit_ids[0]}/attempts", json=request)
        assert retry.status_code == 201
        assert retry.json()["reused"] is True
        assert retry.json()["event_id"] == submitted.json()["event_id"]

        refreshed = client.get("/api/content-factory/curricula").json()
        assert set(refreshed["eligible_unit_ids"]) == set(unit_ids)
        progress = client.get("/api/content-factory/progress").json()
        first = next(item for item in progress["units"] if item["unit_id"] == unit_ids[0])
        assert first["attempt_count"] >= 1
        assert first["latest_percent"] == 100.0
