from __future__ import annotations

import hashlib

import pytest

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.composer import Composer
from backend.hsptl_core.hsp_tl40.guards import Guards
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.plugins import REGISTRY, PluginRegistry, WorkspaceModule, WorkspaceSkin
from backend.hsptl_core.hsp_tl40.proforma import ProformaRuntime, evaluate, validate_plan
from backend.hsptl_core.hsp_tl40.pulse import PulseBridge
from backend.hsptl_core.hsp_tl40.reasoner import Reasoner
from backend.hsptl_core.hsp_tl40.router import Router


@pytest.fixture
def kernel(tmp_path):
    engine = DeterministicIntelligenceEngine(tmp_path / "hsptl.sqlite3")
    return engine, EventKernel(engine)


def test_proforma_logic_uses_three_valued_fail_closed_semantics():
    assert evaluate({"op": "eq", "left": 1, "right": 1}, {}).state == "pass"
    assert evaluate({"op": "eq", "left": 1, "right": 2}, {}).state == "fail"
    unknown = evaluate({"op": "exists", "left": {"ref": "facts.missing"}}, {"facts": {}})
    assert unknown.state == "abstain"
    assert unknown.trace


def test_proforma_enactment_is_sequenced_and_event_backed(kernel):
    engine, event_kernel = kernel
    runtime = ProformaRuntime(event_kernel)
    plan = {"id": "p1", "type": "plan", "tasks": [
        {"id": "q1", "type": "inquiry", "response_key": "objective", "prompt": "Objective?"},
        {"id": "a1", "type": "action", "preconditions": {"op": "exists", "left": {"ref": "answers.objective"}}},
    ]}
    assert validate_plan(plan)["valid"]
    started = runtime.enact(plan)
    enactment_id = started["state"]["enactment_id"]
    assert started["state"]["available"][0]["task"]["id"] == "q1"
    first = runtime.step(enactment_id, "q1", value="Learn the workflow")
    assert first["state"]["available"][0]["task"]["id"] == "a1"
    completed = runtime.step(enactment_id, "a1")
    assert completed["state"]["status"] == "completed"
    assert runtime.get(enactment_id)["state"]["status"] == "completed"
    assert len(event_kernel.platform_events()) == 3
    assert event_kernel.replay()["verified"] is True


def test_unsupported_proforma_construct_abstains(kernel):
    engine, event_kernel = kernel
    guards = Guards(event_kernel, engine)
    result = guards.decide("G-TEST", {"op": "some_unknown_operator", "left": 1}, {})
    assert result.decision == "abstain"
    assert result.audit_event["event_type"] == "platform.guard.abstained"


def test_reasoner_returns_named_subclass_proof(kernel):
    engine, event_kernel = kernel
    engine.register_entity("c1", "Condition", "Condition")
    result = Reasoner(engine).entails_type("c1", "ClinicalEntity")
    assert result["entailed"] is True
    assert [step["class"] for step in result["proof"]] == ["Condition", "ClinicalEntity"]
    assert result["derivation"]["replayable"] is True


def test_composer_requires_evidence_appraisal_rights_and_source_event(kernel):
    engine, event_kernel = kernel
    guards = Guards(event_kernel, engine)
    text = "Reviewed source statement about a clinical finding."
    digest = hashlib.sha256(text.encode()).hexdigest()
    engine.register_entity("ev-entity", "Guideline", "Reviewed guideline")
    engine.register_evidence("ev-1", "ev-entity", "source-1", digest, "permitted", "educational-quotation", "1.0")
    engine.register_source_span("span-1", "ev-1", digest, text, 0, len(text))
    engine.record_appraisal("app-1", "ev-1", "pass", derivation={"reviewer": "reviewer-1", "method": "test"})
    composer = Composer(engine, event_kernel, guards)
    result = composer.compose("learning-1", "rounds", "evidence-linked-assertion@1.0.0", {
        "assertion": {"text": "A reviewed assertion.", "evidence_id": "ev-1", "appraisal_id": "app-1", "source_span_id": "span-1"},
        "evidence_context": {"evidence_id": "ev-1"},
        "limitations": {"text": "Reviewed limitations retained."},
    })
    assert result["state"] == "pass"
    kinds = [item["kind"] for item in result["object"]["assertion_lineage"]]
    assert kinds == ["assertion", "evidence_entity", "appraisal", "source_event", "source_span"]
    assert result["derivation"]["source_events"]


def test_composer_abstains_on_non_pass_appraisal(kernel):
    engine, event_kernel = kernel
    guards = Guards(event_kernel, engine)
    text = "A source statement."
    digest = hashlib.sha256(text.encode()).hexdigest()
    engine.register_entity("ev-entity", "Guideline", "Guideline")
    engine.register_evidence("ev-1", "ev-entity", "source-1", digest, "permitted", "education", "1.0")
    engine.register_source_span("span-1", "ev-1", digest, text, 0, len(text))
    engine.record_appraisal("app-1", "ev-1", "abstain", derivation={"reviewer": "reviewer-1"})
    result = Composer(engine, event_kernel, guards).compose("learning-1", "rounds", "evidence-linked-assertion@1.0.0", {
        "assertion": {"text": "Claim", "evidence_id": "ev-1", "appraisal_id": "app-1", "source_span_id": "span-1"},
        "evidence_context": {"evidence_id": "ev-1"}, "limitations": {"text": "Limit"},
    })
    assert result["state"] == "abstain"
    assert not any(event["event_type"] == "platform.learning_object.composed" for event in event_kernel.platform_events())


def test_router_gaps_topology_irt_fsrs_and_mastery_fold(kernel):
    engine, event_kernel = kernel
    guards = Guards(event_kernel, engine)
    router = Router(event_kernel, guards, engine)
    assert router.coverage_gaps(["a", "b"], ["b", "x"])["missing"] == ["a"]
    assert router.topological_order({"b": ["a"], "a": []})["order"] == ["a", "b"]
    assert router.topological_order({"a": ["b"], "b": ["a"]})["state"] == "fail"
    estimate = router.estimate_irt([{"correct": True, "difficulty": 0}, {"correct": False, "difficulty": 0}])
    assert estimate["state"] == "pass" and estimate["responses"] == 2
    review = router.fsrs_next_review({"card_id": "c1"}, "Good", today="2026-01-01")
    assert review["state"] == "pass" and review["due_date"]
    router.record_mastery_signal("comp-1", "learner-1", "demonstrated", "evidence-1", "reviewer-1")
    router.record_mastery_signal("comp-1", "learner-1", "needs_reinforcement", "evidence-2", "reviewer-1")
    fold = router.mastery_fold("learner-1")
    assert fold["items"][0]["signal"] == "needs_reinforcement"
    assert fold["items"][0]["attempts"] == 2


def test_pulse_bridge_never_fabricates_and_audits_unavailable_action(kernel):
    engine, event_kernel = kernel
    bridge = PulseBridge(event_kernel)
    assert bridge.getState()["connected"] is False
    assert bridge.getState()["observations"] == {}
    result = bridge.applyAction({"id": "test-action"})
    assert result["applied"] is False
    assert result["event"]["event_type"] == "platform.pulse.action_requested"


def test_six_skin_registry_and_presentation_only_config():
    manifest = REGISTRY.manifest()
    assert set(manifest["skins"]) == {"clinic", "rounds", "lab", "ward", "exam", "portfolio"}
    with pytest.raises(ValueError):
        REGISTRY.configure("clinic", {"clinical_facts": {"diagnosis": "x"}})
    registry = PluginRegistry()
    registry.register_module(WorkspaceModule("m", "lab", ("vitals",)))
    registry.register_skin(WorkspaceSkin("lab", "Lab", {}, ("m",), "lab"))
    assert registry.configure("lab", {"display_units": "SI"})["display_units"] == "SI"


def test_replay_includes_v4_platform_events(kernel):
    engine, event_kernel = kernel
    event_kernel.append("platform.plugin.configured", {"workspace": "lab", "config": {"display_units": "SI"}})
    projection = event_kernel.replay()["projection"]
    assert projection["platform_events"][0]["event_type"] == "platform.plugin.configured"
    assert event_kernel.status()["projection_fresh"] is True


def test_proforma_decision_only_exposes_proven_eligible_options(kernel):
    _, event_kernel = kernel
    runtime = ProformaRuntime(event_kernel)
    plan = {"id": "decision-plan", "type": "plan", "tasks": [
        {"id": "choice", "type": "decision", "options": [
            {"id": "eligible", "label": "Eligible", "when": {"op": "eq", "left": {"ref": "facts.ready"}, "right": True}},
            {"id": "not-eligible", "label": "Not eligible", "when": False},
        ]},
        {"id": "finish", "type": "action"},
    ]}
    enacted = runtime.enact(plan, facts={"ready": True})
    state = enacted["state"]
    assert state["available"][0]["task"]["id"] == "choice"
    assert [option["id"] for option in state["available"][0]["options"]] == ["eligible"]
    advanced = runtime.step(state["enactment_id"], "choice", value="eligible")
    assert advanced["state"]["answers"]["decision:choice"] == "eligible"
    assert advanced["state"]["available"][0]["task"]["id"] == "finish"


def test_v4_api_smoke_and_model_free_ucks_boundary():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        architecture = client.get("/api/v4/architecture")
        assert architecture.status_code == 200
        assert architecture.json()["ai_models"] == 0
        assert architecture.json()["services_added"] == 0

        status = client.get("/api/v4/status")
        assert status.status_code == 200
        assert status.json()["ai_models"] == 0

        skins = client.get("/api/v4/workspaces/skins")
        assert skins.status_code == 200
        assert len(skins.json()["skins"]) == 6

        pulse = client.get("/api/v4/pulse/state")
        assert pulse.status_code == 200
        assert pulse.json()["connected"] is False
        assert pulse.json()["observations"] == {}

        ports = client.get("/api/v4/ports")
        assert ports.status_code == 200
        assert ports.json()["default_transport_services"] == 0

        ucks_status = client.get("/api/ucks/status")
        assert ucks_status.status_code == 200
        assert ucks_status.json()["ai_models_enabled"] is False
        assert ucks_status.json()["embedding_inference_enabled"] is False
        ucks_stats = client.get("/api/ucks/stats")
        assert ucks_stats.status_code == 200
        assert ucks_stats.json()["vector_status"] == "disabled_model_free"

        vector_search = client.get("/api/ucks/search", params={"q": "cardiology", "mode": "vector"})
        assert vector_search.status_code == 409
        assert vector_search.json()["detail"]["state"] == "abstain"

        embedding_index = client.post("/api/ucks/embeddings/index")
        assert embedding_index.status_code == 409
        assert embedding_index.json()["detail"]["state"] == "abstain"

        hybrid = client.get("/api/ucks/retrieve/clinic", params={"q": "cardiology", "mode": "hybrid"})
        assert hybrid.status_code == 409

        capabilities = client.get("/api/system/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["policy"]["ai_models_enabled"] is False



def test_unknown_rights_and_unknown_ontology_target_abstain(kernel):
    from backend.hsptl_core.deterministic_intelligence.engine import Abstention

    engine, _ = kernel
    reasoner = Reasoner(engine)
    unknown_target = reasoner.entails_type("not-registered", "UnsupportedClinicalClass")
    assert unknown_target["state"] == "abstain"

    engine.register_entity("unknown-rights-entity", "Guideline", "Guideline")
    text = "Source text with unresolved rights."
    digest = hashlib.sha256(text.encode()).hexdigest()
    with pytest.raises(Abstention):
        engine.register_evidence("unknown-rights-evidence", "unknown-rights-entity", "source-unknown",
                                 digest, "unknown", "unspecified", "1.0")


def test_undecidable_plan_precondition_is_audited_and_visible(kernel):
    _, event_kernel = kernel
    runtime = ProformaRuntime(event_kernel)
    plan = {"id": "unknown-plan", "type": "plan",
            "preconditions": {"op": "exists", "left": {"ref": "facts.pulse.connected"}},
            "tasks": [{"id": "review", "type": "action"}]}
    result = runtime.enact(plan, facts={})
    assert result["state"]["status"] == "abstain"
    assert result["state"]["abstention_reason"] == "Plan preconditions are undecidable."
    assert result["event"]["event_type"] == "platform.pathway.abstained"
    assert runtime.get(result["state"]["enactment_id"])["state"]["status"] == "abstain"


def test_conflict_result_is_read_only_and_abstains_without_z3(kernel):
    from backend.hsptl_core.deterministic_intelligence.engine import Abstention

    engine, event_kernel = kernel
    text_a = "First source assertion."
    text_b = "Second source assertion."
    engine.register_entity("conflict-a", "Guideline", "Guideline A")
    engine.register_entity("conflict-b", "Guideline", "Guideline B")
    engine.register_evidence("evidence-a", "conflict-a", "source-a",
                             hashlib.sha256(text_a.encode()).hexdigest(), "permitted", "education", "1")
    engine.register_evidence("evidence-b", "conflict-b", "source-b",
                             hashlib.sha256(text_b.encode()).hexdigest(), "permitted", "education", "1")
    head_before = event_kernel.head()["seq"]
    try:
        import z3  # noqa: F401
        has_z3 = True
    except ImportError:
        has_z3 = False
    result = Reasoner(engine).detect_conflict("benefit", "adult-population", "evidence-a", "evidence-b",
                                              "positive", "negative")
    if not has_z3:
        assert result["state"] == "abstain"
        assert result["conflict"] is None
    assert event_kernel.head()["seq"] == head_before
    assert result["derivation"]["replayable"] is True
