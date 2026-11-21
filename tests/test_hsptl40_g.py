from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.argumentation import evaluate_decision
from backend.hsptl_core.hsp_tl40.embedded_smt import EmbeddedSMT, compile_proforma_to_cnf
from backend.hsptl_core.hsp_tl40.explain import derive, render_explanation
from backend.hsptl_core.hsp_tl40.guards import Guards
from backend.hsptl_core.hsp_tl40.kernel import EventKernel
from backend.hsptl_core.hsp_tl40.proforma import ProformaRuntime, validate_plan
from backend.hsptl_core.hsp_tl40.pulse import PulseBridge
from backend.hsptl_core.hsp_tl40.router import Router
from backend.hsptl_core.hsp_tl40.temporal_reasoning import RULESET_PATH, TemporalReasoner


@pytest.fixture
def core(tmp_path):
    engine = DeterministicIntelligenceEngine(tmp_path / "hsptl_g.sqlite3")
    return engine, EventKernel(engine)


def _cnf_satisfiable(clauses: list[list[int]], n: int) -> bool:
    for values in itertools.product([False, True], repeat=n):
        if all(any(values[abs(lit) - 1] if lit > 0 else not values[abs(lit) - 1]
                       for lit in clause) for clause in clauses):
            return True
    return False


def test_proforma_decision_uses_additive_weighted_arguments_and_keeps_options():
    task = {"id": "choose", "options": [
        {"id": "candidate-a", "label": "A", "arguments": [
            {"id": "a-for-1", "polarity": "for", "weight": 2.0, "when": True},
            {"id": "a-for-2", "polarity": "for", "weight": 1.0, "when": True},
            {"id": "a-against", "polarity": "against", "weight": 1.5, "when": True},
        ]},
        {"id": "candidate-b", "label": "B", "arguments": [
            {"id": "b-for", "polarity": "for", "weight": 2.0, "when": True},
        ]},
        {"id": "excluded", "when": False, "arguments": []},
    ]}
    result = evaluate_decision(task, {})
    assert result["state"] == "pass"
    assert [item["candidate_id"] for item in result["profiles"]] == ["candidate-b", "candidate-a"]
    candidate_a = next(item for item in result["profiles"] if item["candidate_id"] == "candidate-a")
    assert candidate_a["support_force"] == 3.0
    assert candidate_a["opposition_force"] == 1.5
    assert candidate_a["net_force"] == 1.5
    assert result["preferred_candidates"] == ["candidate-b"]
    assert result["automatic_selection"] is False
    assert all(item["conclusive"] is False for item in result["profiles"])


def test_proforma_runtime_persists_argument_profile_and_user_choice(core):
    _, kernel = core
    runtime = ProformaRuntime(kernel)
    plan = {"id": "weighted-decision", "type": "plan", "tasks": [
        {"id": "decision", "type": "decision", "options": [
            {"id": "a", "arguments": [
                {"id": "a-positive", "polarity": "for", "weight": 2, "when": True},
                {"id": "a-negative", "polarity": "against", "weight": 0.5, "when": True}]},
            {"id": "b", "arguments": [
                {"id": "b-positive", "polarity": "for", "weight": 1, "when": True}]},
        ]},
        {"id": "finish", "type": "action"},
    ]}
    started = runtime.enact(plan)
    available = started["availability"]["available_tasks"][0]
    assert [item["id"] for item in available["options"]] == ["a", "b"]
    assert available["argumentation"]["preferred_candidates"] == ["a"]
    stepped = runtime.step(started["state"]["enactment_id"], "decision", value="b")
    profile = stepped["state"]["decision_profiles"]["decision"]
    assert profile["selected_candidate"] == "b"
    assert profile["selection_is_user_confirmed"] is True
    assert kernel.replay()["verified"] is True


def test_plan_validator_rejects_malformed_argumentation():
    plan = {"id": "bad", "type": "plan", "tasks": [
        {"id": "d", "type": "decision", "options": [
            {"id": "x", "arguments": [{"id": "bad-weight", "polarity": "for", "weight": -2}]}
        ]}
    ]}
    assert validate_plan(plan)["valid"] is False


def test_unknown_argument_conditions_abstain_and_invoke_classified_smt(core):
    _, kernel = core
    runtime = ProformaRuntime(kernel)
    plan = {"id": "unknown", "type": "plan", "tasks": [
        {"id": "d", "type": "decision", "options": [
            {"id": "x", "arguments": [{"id": "unknown", "polarity": "for", "weight": 1,
                "when": {"op": "eq", "left": {"ref": "facts.missing"}, "right": True}}]}
        ]}
    ]}
    started = runtime.enact(plan)
    assert started["state"]["status"] == "abstain"
    assert started["availability"]["argumentation"]["state"] == "abstain"
    assert started["availability"]["argumentation"]["smt_consistency"]["state"] in {"pass", "abstain"}


def test_proforma_conditions_compile_to_cnf_and_detect_internal_contradiction_shape():
    contradictory = {"op": "and", "args": [
        {"op": "eq", "left": {"ref": "facts.x"}, "right": 1},
        {"op": "neq", "left": {"ref": "facts.x"}, "right": 1},
    ]}
    compiled = compile_proforma_to_cnf([("arg-contradiction", contradictory)], {})
    assert compiled["encoding"] == "Tseitin-CNF"
    assert compiled["source_language"] == "PROforma"
    assert compiled["variable_count"] >= 2
    assert _cnf_satisfiable(compiled["clauses"] + [[compiled["roots"][0]["literal"]]],
                           compiled["variable_count"]) is False


def test_embedded_smt_is_rule_gated_and_fails_closed_without_z3():
    smt = EmbeddedSMT()
    unauthorized = smt.check_argument_consistency([], {}, rule_id="PROFORMA-ROUTE-001")
    assert unauthorized["state"] == "abstain"
    if smt._new_z3() is None:
        result = smt.check_argument_consistency([{"id": "x", "when": True}], {})
        assert result["state"] == "abstain"
        differential = smt.enumerate_differentials([], [], {})
        assert differential["state"] == "abstain"
        counterfactual = smt.counterfactual_single_finding({"options": []}, {}, [])
        assert counterfactual["state"] == "abstain"


def test_router_reasoned_sequence_attaches_irt_fsrs_prerequisite_and_brier_arguments(core):
    engine, kernel = core
    router = Router(kernel, Guards(kernel, engine), engine)
    result = router.reasoned_sequence([
        {"object_id": "object-a", "title": "Review A", "irt_difficulty": 0.1,
         "fsrs_card": {"card_id": "a", "due_date": "2026-01-01"},
         "prerequisites": ["base"], "calibration_relevance": 1.0},
        {"object_id": "object-b", "title": "Review B", "irt_difficulty": 0.5,
         "fsrs_card": {"card_id": "b", "due_date": "2027-01-01"},
         "prerequisites": [], "calibration_relevance": 0.1},
    ], responses=[{"correct": True, "difficulty": 0.0}],
       completed_prerequisites=["base"],
       calibration_history=[{"probability": 0.9, "outcome": 0}], today="2026-11-19")
    assert result["state"] == "pass"
    assert len(result["proposals"]) == 2
    for profile in result["proposals"]:
        assert {argument["id"].split(":")[-1] for argument in profile["arguments"]} == {
            "irt", "fsrs", "prerequisites", "brier"}
    assert result["automatic_selection"] is False
    assert result["derivation"]["output_type"] == "learning.sequence"


def test_reasoned_sequence_shows_prerequisite_block_instead_of_routing(core):
    engine, kernel = core
    router = Router(kernel, Guards(kernel, engine), engine)
    result = router.reasoned_sequence([{"object_id": "locked", "prerequisites": ["missing"]}],
        completed_prerequisites=[], today="2026-11-19")
    assert result["state"] == "blocked"
    assert result["blocked_candidates"][0]["missing_prerequisites"] == ["missing"]
    assert result["blocked_candidates"][0]["routeable"] is False


def test_brier_score_is_explicit_and_bounds_checked(core):
    engine, kernel = core
    router = Router(kernel, Guards(kernel, engine), engine)
    assert router.brier_score([{"probability": 0.9, "outcome": 1}])["brier_score"] == pytest.approx(0.01)
    assert router.brier_score([{"probability": 1.4, "outcome": 1}])["state"] == "abstain"


def test_one_derivation_renders_clinical_pedagogical_and_negative_views():
    source = derive(output_type="proforma.decision", output={"candidate": "a"},
        rules=["PROFORMA-ARGUMENTATION-001"],
        inputs=[{"evidence": [{"evidence_id": "ev-1"}]}],
        steps=[{"kind": "argument", "node": "argument:a1", "candidate_id": "a",
                "polarity": "for", "weight": 2, "evidence": [{"evidence_id": "ev-1"}],
                "source_events": [{"event_id": "event-1"}], "result": "unknown"}])
    rendered = [render_explanation(source, audience) for audience in ("clinical", "pedagogical", "negative")]
    assert {item["derivation_hash"] for item in rendered} == {source["derivation_hash"]}
    assert all(item["same_trace"] for item in rendered)
    assert rendered[0]["sections"][0]["items"][0]["evidence"][0]["evidence_id"] == "ev-1"
    assert rendered[2]["sections"][0]["items"]


def test_temporal_asp_bundle_is_versioned_and_pulse_state_facts_are_subject_scoped():
    assert RULESET_PATH.is_file()
    program = RULESET_PATH.read_text(encoding="utf-8")
    assert "temporal_missing" in program and "clinical_state_conflict" in program
    events = [{"event_type": "platform.pulse.observation_recorded", "seq": 5,
               "payload": {"clinical_state_evidence": [
                   {"patient_id": "p1", "state_id": "s1", "evidence_id": "ev1", "polarity": "supports"},
                   {"patient_id": "p2", "state_id": "s2", "evidence_id": "ev2", "polarity": "supports"}]}}]
    facts = TemporalReasoner._event_facts(events, "enactment-1", subject_id="p1")
    assert any('"p1","s1","ev1",supports' in item for item in facts)
    assert not any('"p2"' in item for item in facts)


def test_temporal_reasoner_abstains_when_clingo_library_is_unavailable():
    reasoner = TemporalReasoner()
    if reasoner.analyze([], {"id": "p", "type": "plan", "tasks": []}, "e")["reason"].startswith("Clingo library unavailable"):
        result = reasoner.analyze([], {"id": "p", "type": "plan", "tasks": []}, "e")
        assert result["state"] == "abstain"


def test_pulse_observation_snapshot_enters_canonical_event_log(core):
    _, kernel = core

    class Provider:
        def step(self):
            return {"connected": True, "source": "test-pulse", "sequence": 3,
                    "observations": {"heart_rate": {"value": 72, "unit": "bpm"}},
                    "clinical_state_evidence": [{"patient_id": "p1", "state_id": "reviewed-state",
                        "evidence_id": "ev-1", "polarity": "supports"}]}
        def get_state(self):
            return self.step()
        def apply_action(self, action):
            return {"applied": True}

    bridge = PulseBridge(kernel, Provider())
    result = bridge.step()
    assert result["recorded"] is True
    event = kernel.platform_events()[-1]
    assert event["event_type"] == "platform.pulse.observation_recorded"
    assert event["payload"]["observations"]["heart_rate"]["value"] == 72
    assert kernel.replay()["verified"] is True


def test_reasoned_choice_model_is_part_of_the_single_proforma_library():
    from backend.hsptl_core.hsp_tl40.model_library import load_model
    model = load_model("pathways/reasoned_choice.json")
    decision = model["tasks"][0]
    assert decision["type"] == "decision"
    assert all(option.get("arguments") for option in decision["options"])
    assert all(argument["polarity"] in {"for", "against"}
               for option in decision["options"] for argument in option["arguments"])


def test_temporal_rules_check_prerequisites_at_the_next_canonical_event_position():
    program = RULESET_PATH.read_text(encoding="utf-8")
    assert "current_sequence(E, S)" in program
    assert "not earlier_prerequisite_completed(E, P, S)" in program
    assert "temporal_missing(E, T, P)" in program
    # Future tasks may have pending prerequisites; the active task gets its own
    # readiness decision rather than failing the entire plan pre-emptively.
    assert 'state = "fail" if deviations else "pass"' in Path(
        "backend/hsptl_core/hsp_tl40/temporal_reasoning.py").read_text(encoding="utf-8")


def test_decision_task_preconditions_are_checked_and_unknown_requires_symbolic_proof(core):
    _, kernel = core
    blocked = ProformaRuntime(kernel).enact({"id": "decision-precondition-false", "type": "plan", "tasks": [
        {"id": "d", "type": "decision", "preconditions": False,
         "options": [{"id": "x", "arguments": []}]}
    ]})
    assert blocked["state"]["status"] == "blocked"

    unknown = ProformaRuntime(kernel).enact({"id": "decision-precondition-unknown", "type": "plan", "tasks": [
        {"id": "d", "type": "decision", "preconditions": {"op": "eq",
         "left": {"ref": "facts.unobserved"}, "right": True},
         "options": [{"id": "x", "arguments": [{"id": "a", "polarity": "for", "weight": 1}]}]}
    ]})
    assert unknown["state"]["status"] == "abstain"
    assert unknown["availability"]["precondition_solver"]["state"] == "abstain"


def test_asp_pathway_deviation_becomes_a_negative_proforma_argument(core):
    _, kernel = core

    class FakeTemporal:
        def analyze(self, events, plan, enactment_id, subject_id=None):
            return {"state": "fail", "recognized_states": [],
                    "deviations": ['pathway_deviation("e","choose","12","evt-step")'],
                    "deviation_sources": [{"event_id": "evt-step", "seq": 12,
                        "task_id": "choose", "event_type": "platform.pathway.stepped"}],
                    "prerequisite_ready": {}}

    runtime = ProformaRuntime(kernel, temporal_reasoner=FakeTemporal())
    started = runtime.enact({"id": "deviation-argument", "type": "plan",
        "metadata": {"asp_deviation_argument_weight": 2.5},
        "tasks": [{"id": "choose", "type": "decision", "options": [
            {"id": "candidate-a", "arguments": [{"id": "base", "polarity": "for", "weight": 1}]},
            {"id": "candidate-b", "arguments": [{"id": "base-b", "polarity": "for", "weight": 1}]}
        ]}]})
    assert started["state"]["status"] == "active"
    for profile in started["availability"]["argumentation"]["profiles"]:
        deviation = next(item for item in profile["arguments"] if item["id"] == "asp-deviation:evt-step")
        assert deviation["polarity"] == "against"
        assert deviation["weight"] == 2.5
        assert deviation["source_events"][0]["event_id"] == "evt-step"


def test_temporal_event_projection_retains_step_source_identity():
    events = [{"event_type": "platform.pathway.stepped", "event_id": "evt-step", "seq": 12,
               "payload": {"enactment_id": "enact-1", "task_id": "choose"}}]
    facts = TemporalReasoner._event_facts(events, "enact-1")
    assert 'pathway_step_source("enact-1","choose",12,"evt-step").' in facts


def test_connected_pulse_snapshot_requires_provider_sequence_and_audits_prevention(core):
    _, kernel = core

    class Provider:
        def step(self):
            return {"connected": True, "source": "pulse-test", "sequence": None, "observations": {"heart_rate": {"value": 70}}}
        def get_state(self):
            return self.step()
        def apply_action(self, action):
            return {"applied": False}

    from backend.hsptl_core.hsp_tl40.kernel import WritePrevented
    with pytest.raises(WritePrevented):
        PulseBridge(kernel, Provider()).step()
    assert kernel.platform_events()[-1]["event_type"] == "platform.write.prevented"
