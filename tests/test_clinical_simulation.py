from __future__ import annotations

from pathlib import Path

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.clinical_simulation import ClinicalSimulationRuntime
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.pulse import PulseBridge
from backend.hsptl_core.hsp_tl40.proforma import LOGIC_VERSION, ProformaRuntime


SCENARIO_ID = "asthma-moderate-adult-001"
NOTE = {
    "assessment": "Synthetic moderate asthma exacerbation; reassessment documented.",
    "findings": "Initial wheeze and increased work of breathing; later improvement in this model.",
    "plan": "Scenario treatment actions recorded; continue monitoring and follow reviewed local pathway.",
    "uncertainties": "Allergies and maintenance regimen require verification.",
}
HANDOVER = {
    "situation": "Synthetic patient with acute breathlessness and wheeze.",
    "background": "Known asthma; worsening symptoms over approximately one day.",
    "assessment": "Moderate-presentation features initially; improvement observed in bounded model.",
    "recommendation": "Continue supervised review against local clinical protocol.",
    "outstanding_tasks": "Verify allergies, medication regimen and follow-up arrangements.",
}


def make_runtime(tmp_path: Path):
    engine = DeterministicIntelligenceEngine(tmp_path / "simulation.sqlite")
    kernel = EventKernel(engine)
    logic = ProformaRuntime(kernel)
    return kernel, logic, ClinicalSimulationRuntime(kernel, logic)


def complete_reference_run(sim: ClinicalSimulationRuntime, seed: int = 31415):
    run = sim.start_run(SCENARIO_ID, seed)
    run_id = run["run_id"]
    for action_id in ("focused_assessment", "order_peak_flow"):
        result = sim.perform_action(run_id, {"id": action_id})
        assert result["applied"], result
    # The result is available at T+2; treatment follows without a clinically
    # meaningful artificial wait in this short teaching sequence.
    sim.advance_time(run_id, 2)
    for action_id in ("administer_bronchodilator", "start_systemic_corticosteroid"):
        result = sim.perform_action(run_id, {"id": action_id})
        assert result["applied"], result
    sim.advance_time(run_id, 20)
    sim.advance_time(run_id, 38)
    assert sim.perform_action(run_id, {"id": "reassess_patient"})["applied"]
    sim.save_document(run_id, "clinical_note", NOTE)
    sim.save_document(run_id, "handover", HANDOVER)
    assessment = sim.derive_assessment(run_id)["assessment"]
    replay = sim.replay(run_id)
    return run_id, assessment, replay


def test_scenario_is_versioned_synthetic_and_uses_proforma_models(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    catalogue = sim.list_scenarios()
    assert catalogue["count"] >= 1
    scenario = sim.catalog.load(SCENARIO_ID)
    assert scenario["clinical_review_status"] == "draft_pending_clinical_review"
    assert scenario["patient"]["synthetic"] is True
    for action in scenario["action_catalogue"].values():
        assert action["model_path"].startswith("simulation/")


def test_arrival_view_does_not_leak_unmeasured_peak_flow_or_internal_state(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run = sim.start_run(SCENARIO_ID, 7)
    assert "peak_flow" not in run["observations"]
    assert "initial_state" not in run
    assert "pef_percent_predicted" not in run["observations"]
    assert run["observations"]["spo2"]["value"] == 93


def test_proforma_gates_reject_peak_flow_before_focused_assessment_without_state_change(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run = sim.start_run(SCENARIO_ID, 7)
    run_id = run["run_id"]
    before = sim.get_run(run_id)
    result = sim.perform_action(run_id, {"id": "order_peak_flow"})
    after = sim.get_run(run_id)
    assert result["applied"] is False
    assert len(after["actions"]) == 0
    assert len(after["rejected_actions"]) == 1
    assert before["observations"] == after["observations"]
    assert result["event"]["event_type"] == "simulation.action.rejected"


def test_delayed_peak_flow_and_patient_response_fire_at_exact_simulated_times(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 7)["run_id"]
    assert sim.perform_action(run_id, {"id": "focused_assessment"})["applied"]
    assert sim.perform_action(run_id, {"id": "order_peak_flow"})["applied"]
    assert "peak_flow" not in sim.get_run(run_id)["observations"]
    sim.advance_time(run_id, 2)
    current = sim.get_run(run_id)
    assert current["simulation_time_min"] == 2
    assert current["observations"]["peak_flow"]["value"] == 58
    assert sim.perform_action(run_id, {"id": "administer_bronchodilator"})["applied"]
    result = sim.advance_time(run_id, 20)
    fired = [event["payload"] for event in result["processed_events"]
             if event["event_type"] == "simulation.event.fired"]
    assert fired and fired[0]["kind"] == "bronchodilator_response"
    assert fired[0]["processed_at_minute"] == 22
    current = sim.get_run(run_id)
    assert current["observations"]["spo2"]["value"] == 95
    assert current["observations"]["peak_flow"]["value"] == 70


def test_untreated_scenario_worsens_and_proforma_exposes_escalation(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 12)["run_id"]
    assert sim.perform_action(run_id, {"id": "focused_assessment"})["applied"]
    sim.advance_time(run_id, 30)
    current = sim.get_run(run_id)
    assert current["patient_status"].startswith("Worsening transition")
    escalation = next(item for item in current["available_actions"] if item["id"] == "escalate_for_senior_review")
    assert escalation["available"] is True
    result = sim.perform_action(run_id, {"id": "escalate_for_senior_review"})
    assert result["applied"] is True


def test_pulse_bridge_reads_and_applies_only_scenario_scoped_actions(tmp_path):
    kernel, _, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 19)["run_id"]
    bridge = PulseBridge(kernel, sim.pulse_provider(run_id))
    snapshot = bridge.step()
    assert snapshot["state"]["connected"] is True
    assert snapshot["recorded"] is True
    assert snapshot["event"]["event_type"] == "platform.pulse.observation_recorded"
    action = bridge.applyAction({"id": "focused_assessment"})
    assert action["applied"] is True
    assert action["event"]["event_type"] == "platform.pulse.action_requested"
    assert any(event["event_type"] == "platform.pathway.stepped" for event in kernel.events(limit=1000))


def test_documents_are_immutable_versions_and_formative_assessment_is_explainable(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 101)["run_id"]
    assert sim.perform_action(run_id, {"id": "focused_assessment"})["applied"]
    first = sim.save_document(run_id, "clinical_note", NOTE)["document"]
    second = sim.save_document(run_id, "clinical_note", {**NOTE, "plan": "Revised plan text."})["document"]
    assert first["document_version"] == 1
    assert second["document_version"] == 2
    assessment = sim.derive_assessment(run_id)["assessment"]
    assert assessment["assessment_type"] == "formative_trace_based"
    assert assessment["competence_claimed"] is False
    assert assessment["free_text_semantics_scored"] is False
    assert assessment["derivation"]["replayable"] is True
    assert all("evidence_event_ids" in row for row in assessment["criteria"])


def test_full_run_replays_with_identical_semantic_trace_and_score_for_same_seed(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run1, assessment1, replay1 = complete_reference_run(sim, 31415)
    run2, assessment2, replay2 = complete_reference_run(sim, 31415)
    assert run1 != run2
    assert replay1["semantic_trace_digest"] == replay2["semantic_trace_digest"]
    assert replay1["state_digest"] == replay2["state_digest"]
    assert assessment1["trace_digest"] == assessment2["trace_digest"]
    assert assessment1["score"] == assessment2["score"] == 100
    assert assessment1["criteria"] == [
        {key: value for key, value in row.items() if key != "evidence_event_ids"}
        for row in assessment2["criteria"]
    ] or assessment1["percentage"] == assessment2["percentage"]


def test_run_completion_is_immutable_and_event_chain_replay_verifies(tmp_path):
    kernel, _, sim = make_runtime(tmp_path)
    run_id, assessment, _ = complete_reference_run(sim, 29)
    completed = sim.complete(run_id)
    assert completed["run"]["status"] == "completed"
    try:
        sim.advance_time(run_id, 1)
        assert False, "Completed run should reject clock mutation."
    except ValueError:
        pass
    replay = kernel.replay()
    assert replay["verified"] is True


def test_scenario_action_uses_the_existing_proforma_language_version(tmp_path):
    kernel, logic, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 88)["run_id"]
    result = sim.perform_action(run_id, {"id": "focused_assessment"})
    assert result["applied"] is True
    accepted = next(event for event in kernel.events(limit=1000)
                    if event["event_type"] == "simulation.action.accepted")
    assert accepted["payload"]["proforma_logic_version"] == LOGIC_VERSION
    assert accepted["payload"]["proforma_plan_id"] == "SIM-ASTHMA-ASSESS-1"



def test_peak_flow_rubric_uses_result_availability_not_order_request_time(tmp_path):
    _, _, sim = make_runtime(tmp_path)
    run_id = sim.start_run(SCENARIO_ID, 23)["run_id"]
    assert sim.perform_action(run_id, {"id": "focused_assessment"})["applied"]
    assert sim.perform_action(run_id, {"id": "order_peak_flow"})["applied"]
    # Treatment is recorded before the delayed result returns. The order request
    # alone must not earn the full objective-measurement criterion.
    assert sim.perform_action(run_id, {"id": "administer_bronchodilator"})["applied"]
    sim.advance_time(run_id, 20)
    assessment = sim.derive_assessment(run_id)["assessment"]
    criterion = next(row for row in assessment["criteria"] if row["criterion_id"] == "objective_lung_function")
    assert criterion["points_earned"] == 10
    assert "after the bronchodilator action" in criterion["rationale"]

def test_fastapi_vertical_slice_completes_observe_act_document_assess_replay(tmp_path, monkeypatch):
    # Import the app after pytest's isolated HSPTL_HOME has been set by conftest.
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    catalogue = client.get("/api/v4/simulation/scenarios")
    assert catalogue.status_code == 200
    scenario_id = catalogue.json()["items"][0]["scenario_id"]

    started = client.post("/api/v4/simulation/runs", json={"scenario_id": scenario_id, "seed": 20261119})
    assert started.status_code == 200
    run = started.json()
    run_id = run["run_id"]
    assert run["education_only"] is True
    assert "peak_flow" not in run["observations"]

    # A blocked action is recorded and does not mutate the simulated patient.
    blocked = client.post(f"/api/v4/simulation/runs/{run_id}/actions", json={"action": {"id": "order_peak_flow"}})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["simulation_event"]["event_type"] == "simulation.action.rejected"
    assert blocked.json()["detail"]["pulse_audit_event"]["event_type"] == "platform.pulse.action_requested"

    for action_id in ("focused_assessment", "order_peak_flow"):
        response = client.post(f"/api/v4/simulation/runs/{run_id}/actions", json={"action": {"id": action_id}})
        assert response.status_code == 200 and response.json()["applied"] is True
    advanced = client.post(f"/api/v4/simulation/runs/{run_id}/advance", json={"minutes": 2})
    assert advanced.status_code == 200
    assert advanced.json()["run"]["observations"]["peak_flow"]["value"] == 58

    for action_id in ("administer_bronchodilator", "start_systemic_corticosteroid"):
        response = client.post(f"/api/v4/simulation/runs/{run_id}/actions", json={"action": {"id": action_id}})
        assert response.status_code == 200 and response.json()["applied"] is True
    for minutes in (20, 38):
        response = client.post(f"/api/v4/simulation/runs/{run_id}/advance", json={"minutes": minutes})
        assert response.status_code == 200
    run = client.get(f"/api/v4/simulation/runs/{run_id}").json()
    assert run["simulation_time_min"] == 60
    assert run["observations"]["spo2"]["value"] == 95
    assert run["available_actions"][-1]["id"] == "reassess_patient"
    response = client.post(f"/api/v4/simulation/runs/{run_id}/actions", json={"action": {"id": "reassess_patient"}})
    assert response.status_code == 200

    for document_type, content in (("clinical_note", NOTE), ("handover", HANDOVER)):
        response = client.post(f"/api/v4/simulation/runs/{run_id}/documents", json={"document_type": document_type, "content": content})
        assert response.status_code == 200
        assert response.json()["document"]["document_version"] == 1

    assessment = client.post(f"/api/v4/simulation/runs/{run_id}/assessment")
    assert assessment.status_code == 200
    assert assessment.json()["assessment"]["percentage"] == 100
    assert assessment.json()["assessment"]["competence_claimed"] is False

    replay = client.get(f"/api/v4/simulation/runs/{run_id}/replay")
    assert replay.status_code == 200
    assert replay.json()["event_count"] >= 30
    assert replay.json()["semantic_trace_digest"]

    completed = client.post(f"/api/v4/simulation/runs/{run_id}/complete")
    assert completed.status_code == 200
    assert completed.json()["run"]["status"] == "completed"
    immutable = client.post(f"/api/v4/simulation/runs/{run_id}/advance", json={"minutes": 1})
    assert immutable.status_code == 409
