import json
from fastapi.testclient import TestClient
from backend.main import app


def test_features_default_off_and_formal_hard_blocked(monkeypatch):
    monkeypatch.delenv("HSPTL_FEATURES", raising=False)
    with TestClient(app) as client:
        report = client.get("/api/features").json()
    keys = {f["key"] for f in report}
    assert keys == {"branching_simulation", "conversational_tutoring",
                    "ai_generated_content", "multi_user_sync", "formal_assessment"}
    for f in report:
        if f["key"] == "formal_assessment":
            assert f["hard_blocked"] is True
        assert f["enabled"] is False


def test_episode_lifecycle_and_lineage():
    with TestClient(app) as client:
        ep = client.post("/api/episodes",
                         json={"source_type": "curated_case", "source_id": "case-x"}).json()
        episode_id = ep["episode_id"]
        assert episode_id
        draft = client.patch(f"/api/episodes/{episode_id}/draft",
                             json={"draft": {"representation": "d"}, "expected_revision": 0}).json()
        assert draft["draft_revision"] == 1
        art = client.post(f"/api/episodes/{episode_id}/artifacts",
                          json={"kind": "reflection", "body": {"text": "note"},
                                "authored_by": "learner"}).json()
        assert art["created"] is True
        lineage = client.get(f"/api/episodes/{episode_id}/lineage").json()
        assert lineage["artifacts"][0]["artifact_id"] == art["artifact_id"]


def test_exam_governance_and_reproducible_submit():
    payload = {"questions": [{
        "kind": "MCQ", "specialty": "Cardiology", "difficulty": "Intermediate",
        "question": "Best answer?", "options": ["A", "B"], "answer": "A",
        "explanation": "E", "source_title": "T"}]}
    with TestClient(app) as client:
        listed = client.get("/api/exams")
        assert listed.status_code == 200, listed.text
        imported = client.post("/api/exams/import",
                               files={"file": ("q.json", json.dumps(payload), "application/json")}).json()
        assert imported["created"] == 1
        question = client.get("/api/exams/questions").json()["questions"][0]
        assert question["reviewed"] is False
        blocked = client.post("/api/exams/build",
                              json={"title": "Test Exam", "specialty": "Cardiology",
                                    "question_count": 1, "duration_minutes": 5, "difficulty": "Any"})
        assert blocked.status_code == 409  # no reviewed questions yet
        client.post(f"/api/questions/{question['id']}/review", json={"reviewed": True})
        built = client.post("/api/exams/build",
                            json={"title": "Test Exam", "specialty": "Cardiology",
                                  "question_count": 1, "duration_minutes": 5,
                                  "difficulty": "Any"}).json()
        detail = client.get(f"/api/exams/{built['id']}").json()
        assert "answer" not in detail["questions"][0]
        result = client.post(f"/api/exams/{built['id']}/submit",
                             json={"responses": {question["id"]: "A"},
                                   "duration_seconds": 5}).json()
        assert result["percentage"] == 100.0


def test_osce_metadata_and_attempt_persistence():
    from backend.runtime import EXAMS
    created = EXAMS.add_question({
        "kind": "Clinical examination",
        "specialty": "Cardiology",
        "difficulty": "Intermediate",
        "question": "Demonstrate assessment of a raised jugular venous pressure.",
        "options": ["Inspect the neck", "Palpate the abdomen"],
        "answer": "Inspect the neck",
        "explanation": "Correct inspection technique.",
        "candidate_instructions": "You have 10 minutes.",
        "checklist": ["Introduces self", "Positions patient"],
        "critical_errors": ["Fails to explain the procedure"],
        "timer_seconds": 600,
    })
    EXAMS.set_reviewed(created["id"], True)
    with TestClient(app) as client:
        result = client.post("/api/osce/attempt", json={
            "question_id": created["id"],
            "response": "Inspect the neck",
            "duration_seconds": 42,
        })
        assert result.status_code == 200
        assert result.json()["correct"] is True
        progress = client.get("/api/progress").json()
    assert progress["exam"]["osce_attempts"] >= 1
    assert progress["exam"]["osce_by_kind"]


def test_simple_scheduler_matches_legacy_first_good():
    from datetime import date
    from backend.hsptl_core.scheduling import CardState, SimpleScheduler
    result = SimpleScheduler().next_review(CardState(card_id="c", state="new"),
                                           "Good", date(2026, 1, 1))
    assert result.interval_days == 1
    assert result.scheduler == "simple"


def test_faceted_search_and_progress_dimensions():
    from backend.runtime import SEARCH, STORE
    STORE.save_note("TestCat", "Asthma note", "body about asthma",
                    note_type="Condition", provenance_status="curated", has_sources=True)
    out = SEARCH.search("asthma", facets={"note_type": "Condition"})
    assert out["engine"] in {"sqlite_fts5", "sqlite_like_fallback"}
    with TestClient(app) as client:
        progress = client.get("/api/progress").json()
    assert progress["scope"] == "all_saved_activity"
    assert "lifetime" in progress
    assert set(progress["dimensions"]) >= {"practice", "reasoning_process", "retention", "transfer"}


def test_portability_export_checksum_roundtrip():
    with TestClient(app) as client:
        bundle = client.get("/api/portability/export").json()
        assert "checksum" in bundle
        preview = client.post("/api/portability/import/preview", json=bundle).json()
        assert preview["valid"] is True
        tampered = dict(bundle)
        tampered["bundle_version"] = 999
        assert client.post("/api/portability/import/preview", json=tampered).json()["valid"] is False


def test_phase5_event_catalogue_endpoint_and_reviewer_edit(monkeypatch):
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "r" * 40)
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "reviewer-test")
    payload = {
        "id": "api-event-test", "title": "API Event Test", "category": "Education",
        "icon": "🎓", "summary": "Reviewer-managed test theme", "setting": "Teaching room",
        "learning_objectives": ["clinical reasoning"], "case_signals": ["test presentation"],
        "workspaces": ["clinic", "rounds"], "selection_weight": 2, "cooldown_days": 3,
        "active": True,
    }
    with TestClient(app) as client:
        before = client.get("/api/v5/clinical-events")
        assert before.status_code == 200 and before.json()["count"] >= 20
        saved = client.put("/api/v5/clinical-events/api-event-test", json=payload,
                           headers={"X-HSPTL-Reviewer-Token": "r" * 40})
        assert saved.status_code == 200, saved.text
        assert saved.json()["id"] == "api-event-test"
        assert saved.json()["catalogue_version"] == 1
        catalogue = client.get("/api/clinical-catalogue/events").json()
        assert any(item["id"] == "api-event-test" for item in catalogue["items"])
