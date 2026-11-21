from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from backend.hsptl_core.hsp_tl40.dataset_imports import (
    FixtureImportError, cass_jsonld_to_reference_graph,
    medbiquitous_xml_to_reference_graph, phekb_phenotype_to_proforma,
)
from backend.hsptl_core.hsp_tl40.debugger import debug_proforma
from backend.hsptl_core.hsp_tl40.event_contracts import event_catalogue
from backend.hsptl_core.hsp_tl40.golden import replay_diff, run_replay_diff
from backend.hsptl_core.hsp_tl40.guard_matrix import guard_catalogue
from backend.hsptl_core.hsp_tl40.guards import Guards
from backend.hsptl_core.hsp_tl40.kernel import EventKernel, WritePrevented
from backend.hsptl_core.hsp_tl40.model_library import model_catalogue, load_model
from backend.hsptl_core.hsp_tl40.plugins import REGISTRY
from backend.hsptl_core.hsp_tl40.proforma import validate_plan
from backend.hsptl_core.hsp_tl40.provability import Z3DecisionAdapter, classify_rule
from backend.hsptl_core.hsp_tl40.terminology_port import TerminologyPort


@pytest.fixture
def core(tmp_path):
    engine = DeterministicIntelligenceEngine(tmp_path / "hsptl.sqlite3")
    return engine, EventKernel(engine)


def test_event_catalogue_has_versioned_prevented_write_event():
    catalogue = event_catalogue()
    assert catalogue["schema"] == "hsptl.event/1.0"
    assert "platform.write.prevented" in catalogue["events"]
    assert "payload_digest" in catalogue["events"]["platform.write.prevented"]["required"]


def test_write_boundary_blocks_unknown_event_and_logs_prevention(core):
    _, kernel = core
    with pytest.raises(WritePrevented) as caught:
        kernel.append("platform.not_a_real_event", {"hello": "world"})
    assert caught.value.audit_event["event_type"] == "platform.write.prevented"
    assert caught.value.audit_event["payload"]["layer"] == "write_boundary"
    events = kernel.platform_events()
    assert len(events) == 1 and events[0]["event_type"] == "platform.write.prevented"
    assert kernel.replay()["verified"] is True


def test_write_boundary_requires_payload_schema(core):
    _, kernel = core
    with pytest.raises(WritePrevented):
        kernel.append("platform.route.decided", {"object_id": "x", "workspace": "ward"})
    assert kernel.platform_events()[-1]["event_type"] == "platform.write.prevented"


def test_runtime_monitor_blocks_inconsistent_abstaining_pathway(core):
    _, kernel = core
    with pytest.raises(WritePrevented) as caught:
        kernel.append("platform.pathway.stepped", {
            "enactment_id": "e1", "task_id": "t1",
            "state": {"enactment_id": "e1", "status": "abstain"},
        })
    assert caught.value.audit_event["payload"]["layer"] == "runtime_event_monitor"
    assert caught.value.audit_event["payload"]["monitor"] == "M-PROFORMA-ABSTAIN-001"


def test_runtime_monitor_blocks_route_without_proven_eligibility(core):
    _, kernel = core
    with pytest.raises(WritePrevented) as caught:
        kernel.append("platform.route.decided", {"object_id": "x", "workspace": "ward", "eligibility": "abstain"})
    assert caught.value.audit_event["payload"]["monitor"] == "M-ROUTE-ELIGIBILITY-001"


def test_per_rule_provability_calls_solver_only_for_z3_required_rules(core):
    engine, kernel = core

    class SpySolver:
        def __init__(self): self.calls = 0
        def decide(self, expression, context):
            self.calls += 1
            return {"decision": "pass", "reason": "spy proof", "trace": [{"solver": "spy"}]}

    solver = SpySolver()
    guards = Guards(kernel, engine, z3_adapter=solver)
    ordinary = guards.decide("G-ORDINARY", True, {}, rule_id="PROFORMA-GUARD-001")
    assert ordinary.decision == "pass" and solver.calls == 0
    unclassified = guards.decide("G-UNKNOWN", True, {}, rule_id="UNREGISTERED-RULE")
    assert unclassified.decision == "abstain" and solver.calls == 0
    symbolic = guards.decide("G-SMT", True, {}, rule_id="SMT-SAFETY-001")
    assert symbolic.decision == "pass" and solver.calls == 1
    assert classify_rule("SMT-SAFETY-001")["classification"] == "z3_required"



def test_z3_adapter_accepts_proforma_reference_shape_and_abstains_when_solver_unavailable():
    import importlib.util
    result = Z3DecisionAdapter().decide(
        {"op": "gte", "left": {"ref": "facts.minimum"}, "right": 5},
        {"variables": {"facts.minimum": {"type": "int", "min": 5}}},
    )
    assert result["decision"] in {"pass", "abstain"}
    if importlib.util.find_spec("z3") is None:
        assert result["decision"] == "abstain"
        assert "Z3 unavailable" in result["reason"]
    else:
        assert result["decision"] == "pass"


def test_legacy_solver_entrypoints_cannot_bypass_per_rule_provability_registry(core, monkeypatch):
    from backend.hsptl_core.deterministic_intelligence.engine import Abstention
    from backend.hsptl_core.hsp_tl40 import provability as provability_module
    from backend.hsptl_core.hsp_tl40 import reasoner as reasoner_module
    from backend.hsptl_core.hsp_tl40.reasoner import Reasoner

    engine, _ = core
    monkeypatch.setattr(provability_module, "classify_rule", lambda rule_id: {
        "rule_id": rule_id, "classification": "unclassified", "solver": "none",
        "rationale": "test policy denies symbolic solving",
    })
    with pytest.raises(Abstention, match="not permitted by the registered provability policy"):
        engine.verify_safety_properties()
    with pytest.raises(Abstention, match="not permitted by the registered provability policy"):
        engine.detect_conflict("c1", "p", "s", "e1", "e2", "positive", "negative")

    monkeypatch.setattr(reasoner_module, "classify_rule", lambda rule_id: {
        "rule_id": rule_id, "classification": "unclassified", "solver": "none",
        "rationale": "test policy denies symbolic solving",
    })
    result = Reasoner(engine).detect_conflict("p", "s", "e1", "e2", "positive", "negative")
    assert result["state"] == "abstain"
    assert result["provability"]["classification"] == "unclassified"

def test_grade_proforma_model_keeps_human_domain_review_and_no_assessed_abstains():
    model = load_model("appraisal/grade_domain_appraisal.json")
    debug = debug_proforma(model)
    assert debug["state"] == "active"
    assert debug["next_task"] == "risk-of-bias"
    action = model["tasks"][-1]
    assert any(item.get("op") == "neq" and item.get("right") == "not_assessed"
               for item in action["preconditions"]["args"])
    assert model["metadata"]["aggregate_certainty"] is False


def test_proforma_debugger_uses_same_logic_without_writes():
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures/phekb_cases/phekb_style_case_001.json"
    phenotype = json.loads(fixture_path.read_text())
    plan = phekb_phenotype_to_proforma(phenotype)
    pass_case = debug_proforma(plan, {"dataset_ready": True, "dictionary_reviewed": True})
    unknown_case = debug_proforma(plan, {})
    assert pass_case["state"] == "active"
    assert pass_case["next_task"] == "criterion-dataset-present"
    assert unknown_case["state"] == "abstain"
    assert unknown_case["writes"] == 0



def _phekb_t2d_facts(**overrides):
    facts = {
        "age_at_latest_assessment_years": 55,
        "type1_diabetes_any_time": False,
        "t2d_icd_diagnosis_count": 0,
        "any_diabetes_medication": False,
        "outpatient_insulin_record": False,
        "non_insulin_medication_before_insulin": False,
        "non_insulin_diabetes_medication": False,
        "self_reported_t2d": False,
        "in_person_provider_visit_count": 1,
        "glucose_measurement_count": 1,
        "fasting_glucose_mg_dl_available": True,
        "fasting_glucose_mg_dl": 90,
        "fasting_glucose_mmol_l_available": False,
        "fasting_glucose_mmol_l": None,
        "hba1c_percent_available": True,
        "hba1c_percent": 5.4,
        "hba1c_mmol_mol_available": False,
        "hba1c_mmol_mol": None,
        "random_glucose_mg_dl_available": False,
        "random_glucose_mg_dl": None,
        "random_glucose_mmol_l_available": False,
        "random_glucose_mmol_l": None,
        "any_diabetes_diagnosis_or_related_condition_any_time": False,
        "self_reported_diabetes_any": False,
    }
    facts.update(overrides)
    return facts


def test_source_attributed_phekb_t2d_ehr_plus_fixture_executes_case_and_control_paths():
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures/phekb_cases"
    plan = json.loads((fixture_root / "phekb_type2_diabetes_ehr_plus.proforma.json").read_text())
    source = json.loads((fixture_root / "phekb_type2_diabetes_source.json").read_text())
    assert validate_plan(plan)["valid"] is True
    assert plan["metadata"]["source_ref"] == source["source_url"]
    assert plan["metadata"]["fixture_only"] is True

    case_facts = _phekb_t2d_facts(
        t2d_icd_diagnosis_count=1, any_diabetes_medication=True,
        any_diabetes_diagnosis_or_related_condition_any_time=True,
    )
    case = debug_proforma(plan, case_facts)
    assert case["state"] == "active"
    assert case["steps"][-1]["eligible_options"] == ["case"]

    control_facts = _phekb_t2d_facts()
    control = debug_proforma(plan, control_facts)
    assert control["state"] == "active"
    assert control["steps"][-1]["eligible_options"] == ["control"]


def test_phekb_t2d_insulin_exception_uses_two_independent_diagnoses_or_prior_noninsulin_medication():
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures/phekb_cases"
    plan = json.loads((fixture_root / "phekb_type2_diabetes_ehr_plus.proforma.json").read_text())
    one_diagnosis = _phekb_t2d_facts(
        t2d_icd_diagnosis_count=1, any_diabetes_medication=True,
        outpatient_insulin_record=True, non_insulin_medication_before_insulin=False,
        any_diabetes_diagnosis_or_related_condition_any_time=True,
    )
    two_diagnoses = dict(one_diagnosis, t2d_icd_diagnosis_count=2)
    assert debug_proforma(plan, one_diagnosis)["steps"][-1]["eligible_options"] == ["neither"]
    assert debug_proforma(plan, two_diagnoses)["steps"][-1]["eligible_options"] == ["case"]



def test_phekb_t2d_golden_vectors_match_proforma_debugger():
    root = Path(__file__).resolve().parents[1]
    plan = json.loads((root / "fixtures/phekb_cases/phekb_type2_diabetes_ehr_plus.proforma.json").read_text())
    corpus = json.loads((root / "fixtures/golden_corpus/golden_logic_cases.json").read_text())
    cases = [item for item in corpus["cases"] if item["model"] == "phekb_type2_diabetes_ehr_plus"]
    assert len(cases) == 4
    for item in cases:
        result = debug_proforma(plan, item["facts"])
        assert result["state"] == item["expected_debug_state"], item["id"]
        actual = result.get("steps", [{}])[-1].get("eligible_options", [])
        assert actual == item["expected_eligible_options"], item["id"]

def test_phekb_t2d_missing_required_fact_abstains_instead_of_defaulting():
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures/phekb_cases"
    plan = json.loads((fixture_root / "phekb_type2_diabetes_ehr_plus.proforma.json").read_text())
    facts = _phekb_t2d_facts()
    facts.pop("age_at_latest_assessment_years")
    result = debug_proforma(plan, facts)
    assert result["state"] == "abstain"
    assert result["writes"] == 0

def test_phekb_adapter_rejects_code_as_criterion():
    with pytest.raises(FixtureImportError):
        phekb_phenotype_to_proforma({"phenotype_id": "bad", "criteria": [{"id": "x", "expression": "eval('x')"}]})


def test_cass_jsonld_and_medbiquitous_xml_import_to_reference_graphs():
    fixture_root = Path(__file__).resolve().parents[1] / "fixtures/competency_graphs"
    cass = json.loads((fixture_root / "cass_synthetic_input.jsonld").read_text())
    cass_graph = cass_jsonld_to_reference_graph(cass)
    assert cass_graph["fixture_only"] is True
    assert len(cass_graph["nodes"]) == 3
    assert any(edge["predicate"] == "has_child" for edge in cass_graph["edges"])

    xml = (fixture_root / "medbiquitous_synthetic_input.xml").read_text()
    med_graph = medbiquitous_xml_to_reference_graph(xml)
    assert med_graph["fixture_only"] is True
    assert len(med_graph["nodes"]) == 3
    assert med_graph["warnings"]


def test_medbiquitous_import_rejects_dtd_and_entities():
    with pytest.raises(FixtureImportError):
        medbiquitous_xml_to_reference_graph('<!DOCTYPE x [<!ENTITY e "bad">]><x>&e;</x>')


def test_snomed_rf2_import_requires_license_and_indexes_exact_terms(core, tmp_path):
    engine, kernel = core
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    concept_file = snapshot / "sct2_Concept_Snapshot_TEST.txt"
    description_file = snapshot / "sct2_Description_Snapshot_TEST.txt"
    concept_columns = ["id", "effectiveTime", "active", "moduleId", "definitionStatusId"]
    description_columns = ["id", "effectiveTime", "active", "moduleId", "conceptId", "languageCode", "typeId", "term", "caseSignificanceId"]
    with concept_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=concept_columns, delimiter="\t")
        writer.writeheader(); writer.writerow({"id": "100001", "effectiveTime": "20260131", "active": "1", "moduleId": "900000000000207008", "definitionStatusId": "900000000000074008"})
    with description_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=description_columns, delimiter="\t")
        writer.writeheader(); writer.writerow({"id": "200001", "effectiveTime": "20260131", "active": "1", "moduleId": "900000000000207008", "conceptId": "100001", "languageCode": "en", "typeId": "900000000000003001", "term": "Synthetic fixture concept (concept)", "caseSignificanceId": "900000000000448009"})

    port = TerminologyPort(db_path=engine.db_path, kernel=kernel)
    with pytest.raises(PermissionError):
        port.import_snomed_rf2(snapshot, edition="test", effective_time="20260131")
    result = port.import_snomed_rf2(snapshot, edition="test", effective_time="20260131", licensed_use_confirmed=True)
    assert result["concept_count"] == 1
    assert port.lookup("100001")["state"] == "pass"
    assert port.lookup("Synthetic fixture concept (concept)")["concept"]["code"] == "100001"
    assert kernel.platform_events()[-1]["event_type"] == "platform.terminology.imported"


def test_skin_registry_enforces_per_skin_schema_and_fact_boundary():
    assert REGISTRY.configure("lab", {"display_units": "SI"})["display_units"] == "SI"
    with pytest.raises(ValueError):
        REGISTRY.configure("lab", {"clinical_thresholds": {"spo2": 92}})
    with pytest.raises(ValueError):
        REGISTRY.configure("lab", {"focus": "unsupported in this module"})
    with pytest.raises(ValueError):
        REGISTRY.configure("exam", {"exam_presentation": "clinical-auto"})


def test_guard_catalogue_declares_all_four_layers_and_z3_policy():
    catalogue = guard_catalogue()
    assert [item["number"] for item in catalogue["layers"]] == [1, 2, 3, 4]
    rules = {item["rule_id"]: item for item in catalogue["provability"]["rules"]}
    assert rules["SMT-CONFLICT-001"]["classification"] == "z3_required"
    assert rules["PROFORMA-ROUTE-001"]["classification"] == "proforma"


def test_golden_replay_diff_is_stable(core):
    _, kernel = core
    kernel.append("platform.plugin.configured", {"workspace": "lab", "config": {"display_units": "SI"}})
    result = run_replay_diff(kernel)
    assert result["verified"] is True
    assert result["diff"]["equal"] is True


def test_model_catalogue_contains_valid_models():
    catalogue = model_catalogue()
    assert catalogue["executable_languages"] == ["PROforma"]
    assert catalogue["model_count"] >= 5
    assert all(item["valid"] for item in catalogue["models"]), catalogue["models"]


def test_v4_api_exposes_d_to_f_contracts():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        assert client.get("/api/v4/event-catalogue").json()["schema"] == "hsptl.event/1.0"
        guard_catalogue_result = client.get("/api/v4/guards/catalogue").json()
        assert len(guard_catalogue_result["layers"]) == 4
        assert client.get("/api/v4/logic/models").json()["model_count"] >= 5
        model = load_model("pathways/case_review.json")
        debug = client.post("/api/v4/logic/debug", json={"plan": model, "facts": {}})
        assert debug.status_code == 200 and debug.json()["writes"] == 0
