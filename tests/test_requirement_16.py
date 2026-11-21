from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from backend.hsptl_core.capabilities import capability_report
from backend.hsptl_core.case_events import evaluate_case_events
from backend.hsptl_core.clinical_narrative import build_encounter_narrative
from backend.hsptl_core.note_engine import generate_study_note
from backend.hsptl_core.reasoning_feedback import build_feedback
from backend.main import CASE_STORE, app


def test_16_1_progress_is_contextualized_as_saved_activity():
    with TestClient(app) as client:
        response = client.get("/api/progress")

    assert response.status_code == 200
    progress = response.json()
    assert progress["scope"] == "all_saved_activity"
    assert {"cards", "attempts", "quizzes"} <= progress["lifetime"].keys()


def test_16_2_case_events_are_deterministic_and_reflection_only():
    payload = {
        "specialty_pathway": "Emergency",
        "confidence": 5,
        "differentials": ["A", "B", "C", "D"],
    }

    events = evaluate_case_events(payload)
    assert [event["id"] for event in events] == [
        "high-confidence-emergency-review",
        "broad-differential-review",
    ]
    assert events == evaluate_case_events(payload)
    uncertain_events = evaluate_case_events({
        "confidence": 2,
        "problem_representation": "Learner notes mention syncope.",
    })
    assert [event["id"] for event in uncertain_events] == ["uncertain-time-sensitive-term"]
    assert "not triage advice" in uncertain_events[0]["message"]


def test_16_3_missing_history_and_examination_are_not_normalized():
    narrative = build_encounter_narrative({
        "selected_encounter": {
            "encounter_key": "encounter-1",
            "encounter_type": "Visit",
            "status": "finished",
        },
        "patient": {},
        "facts": [],
    })
    sections = {section["title"]: section for section in narrative["sections"]}

    assert sections["Presenting history"]["availability"] == "unavailable"
    assert sections["Examination"]["availability"] == "unavailable"
    assert "Do not interpret this as a normal examination." in sections["Examination"]["note"]


def test_16_4_learning_actions_adapt_to_documented_process_gaps():
    sparse = build_feedback({})
    complete = build_feedback({
        "differentials": ["Option A", "Option B"],
        "prioritisation_rationale": "Compare likelihood and consequence.",
        "evidence_against": "Name contradictory findings.",
        "expected_missing": "History is not available in the source.",
        "next_discriminating_question": "What additional history would change the ranking?",
        "investigation_plan": "Describe what each test would answer.",
        "safety_net": "Review local escalation guidance with a supervisor.",
        "cited_fact_keys": ["fact-1"],
    }, available_facts=[{"fact_key": "fact-1", "effective_at": "2025-01-01"}])

    assert sparse["learning_actions"]
    assert any(action["id"] == "cite-evidence" for action in sparse["learning_actions"])
    assert complete["learning_actions"] == []


def test_16_5_learning_attempt_flows_into_unverified_pearl():
    patient_key = uuid.uuid4().hex * 2
    encounter_key = uuid.uuid4().hex * 2
    with CASE_STORE.transaction() as conn:
        conn.execute(
            "INSERT INTO clinical_patients "
            "(patient_key,source_key,source_patient_id,raw_json,updated_at) VALUES(?,?,?,?,?)",
            (patient_key, "req16", patient_key, "{}", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO clinical_encounters "
            "(encounter_key,patient_key,source_encounter_id,raw_json,source_file,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (encounter_key, patient_key, encounter_key, "{}", "req16.json", "2026-01-01T00:00:00+00:00"),
        )

    with TestClient(app) as client:
        saved = client.post("/api/clinical/learning-attempts", json={
            "patient_key": patient_key,
            "encounter_key": encounter_key,
            "case_code": "SYN-REQ16",
            "specialty_pathway": "Emergency",
            "problem_representation": "Learner-authored summary",
            "confidence": 5,
            "differentials": ["Option A", "Option B"],
        })
        assert saved.status_code == 200, saved.text
        assert saved.json()["case_events"][0]["id"] == "high-confidence-emergency-review"

        pearl = client.post(
            f"/api/clinical/learning-attempts/{saved.json()['attempt_id']}/pearl",
            json={"focus": "Uncertainty", "reflection": "I will review how I communicate uncertainty."},
        )
        assert pearl.status_code == 200, pearl.text
        detail = client.get(f"/api/pearls/saved/{pearl.json()['id']}")

    assert detail.status_code == 200
    assert detail.json()["note"]["provenance"]["verified"] is False
    assert detail.json()["note"]["references"] == []


def test_16_6_feedback_links_sources_without_claiming_diagnostic_correctness():
    feedback = build_feedback(
        {"cited_fact_keys": ["fact-1"]},
        available_facts=[{"fact_key": "fact-1", "effective_at": "2025-01-01"}],
    )

    assert feedback["evidence_coverage"]["linked"] is True
    assert feedback["scope"] == "process_only"
    assert "diagnosis_correct" not in feedback
    assert "not that it is clinically sound" in feedback["process"]["limitations"][0]
    assert "No diagnosis is ranked" in feedback["process"]["limitations"][1]


def test_16_7_study_note_discloses_template_only_generation():
    note = generate_study_note(
        topic="Respiratory approach",
        note_type="Condition",
        level="Clinical years",
        jurisdiction="International",
    )

    assert note["generated_mode"] == "Evidence-linked template assembly; no generative AI was used."
    assert note["evidence_count"] == 0
    assert all(section["status"] == "needs source review" for section in note["sections"])


def test_16_8_core_capabilities_degrade_without_optional_search_support():
    report = capability_report(fts5_available=False)

    assert report["core"]["status"] == "available"
    assert report["core"]["search_engine"] == "sqlite_like_fallback"
    assert "clinic" in report["core"]["features"]
    assert report["policy"]["optional_dependencies_imported_at_startup"] is False
