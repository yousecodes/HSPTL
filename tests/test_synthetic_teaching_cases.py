import json

from backend.hsptl_core.case_lottery import CaseLottery
from backend.hsptl_core.store import StudyStore
from backend.hsptl_core.synthetic_data.teaching_cases import author_cases_from_accepted_fhir


def _bundle():
    return {
        "resourceType": "Bundle", "type": "collection", "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-private-123", "name": [{"text": "Synthetic Person"}], "birthDate": "1980-04-03"}},
            {"resource": {"resourceType": "Encounter", "id": "enc-1", "status": "finished",
                          "class": {"code": "AMB"}, "period": {"start": "2020-01-01T09:00:00Z"}}},
            {"resource": {"resourceType": "Condition", "id": "cond-1",
                          "clinicalStatus": {"coding": [{"display": "Active"}]},
                          "verificationStatus": {"coding": [{"display": "Confirmed"}]},
                          "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006", "display": "Diabetes mellitus type 2"}]}}},
            {"resource": {"resourceType": "Observation", "id": "obs-1", "status": "final",
                          "code": {"coding": [{"display": "Body weight"}]},
                          "valueQuantity": {"value": 82, "unit": "kg"}}},
        ]
    }


def test_accepted_synthea_bundle_becomes_privacy_minimised_provisional_lottery_case(tmp_path):
    source = tmp_path / "accepted"
    source.mkdir()
    (source / "bundle-1.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    lottery = CaseLottery(StudyStore(tmp_path / "study.sqlite3"))

    result = author_cases_from_accepted_fhir(source, lottery, dataset_id="dataset-1", recipe_id="recipe-1")
    assert result["created"] == 1
    cases = lottery.list_cases()
    assert len(cases) == 1
    case = cases[0]
    assert case["label"] == "SYNTHETIC CONTENT"
    assert case["clinical_review_status"] == "synthetic_qa_passed"
    assert case["patient_age_value"] == 39
    assert case["rights_status"] == "permitted"
    assert "Synthetic Person" not in case["stem"]
    assert "patient-private-123" not in case["case_id"]
    assert "Diabetes mellitus type 2" in case["reveal"]["diagnosis"]
    assert "not clinically validated" in case["reveal"]["educational_status"].lower()
    draw = lottery.draw(workspace="clinic", draw_date="2026-11-21")
    assert draw["state"] == "selected"
    assert draw["case"]["clinical_validation_status"] == "not_assessed_synthetic_qa_only"
    assert draw["case"]["publication_label"] == "Provisional educational use"

    repeated = author_cases_from_accepted_fhir(source, lottery, dataset_id="dataset-1", recipe_id="recipe-1")
    assert repeated["created"] == 0
    assert repeated["already_present"] == 1


def test_synthea_case_authoring_skips_records_without_required_clinical_context(tmp_path):
    source = tmp_path / "accepted"
    source.mkdir()
    bundle = _bundle()
    bundle["entry"] = [entry for entry in bundle["entry"] if entry["resource"].get("resourceType") != "Observation"]
    (source / "bundle-1.json").write_text(json.dumps(bundle), encoding="utf-8")
    lottery = CaseLottery(StudyStore(tmp_path / "study.sqlite3"))
    result = author_cases_from_accepted_fhir(source, lottery, dataset_id="dataset-1", recipe_id="recipe-1")
    assert result["created"] == 0
    assert result["skip_reasons"]["requires_observations"] == 1
