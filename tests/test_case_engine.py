import json
from pathlib import Path

import pytest

from backend.hsptl_core.case_engine import CaseRepository


def _bundle(patient_id="p-1"):
    return {
        "resourceType": "Bundle", "type": "collection", "entry": [
            {"fullUrl": f"urn:uuid:{patient_id}", "resource": {
                "resourceType": "Patient", "id": patient_id, "gender": "female", "birthDate": "1990-04-03",
                "name": [{"given": ["Synthetic"], "family": "Patient"}] }},
            {"fullUrl": "urn:uuid:e-1", "resource": {
                "resourceType": "Encounter", "id": "e-1", "status": "finished",
                "subject": {"reference": f"urn:uuid:{patient_id}"}, "period": {"start": "2025-01-01T09:00:00Z"},
                "type": [{"text": "Outpatient visit"}] }},
            {"resource": {
                "resourceType": "Observation", "id": "o-1", "subject": {"reference": f"urn:uuid:{patient_id}"},
                "encounter": {"reference": "urn:uuid:e-1"}, "status": "final",
                "code": {"text": "Haemoglobin"}, "valueQuantity": {"value": 12.4, "unit": "g/dL"},
                "effectiveDateTime": "2025-01-01T09:10:00Z" }},
            {"resource": {
                "resourceType": "Condition", "id": "c-1", "subject": {"reference": f"Patient/{patient_id}"},
                "code": {"text": "Source coded condition"}, "recordedDate": "2025-01-01" }},
        ]
    }


def test_fhir_import_links_encounter_and_preserves_missing_data(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    result = repo.import_directory(source, batch_size=25)
    assert result["status"] == "completed"
    assert result["patients"] == 1
    assert result["encounters"] == 1
    assert result["facts"] == 2
    patient = repo.list_patients()["items"][0]
    case = repo.patient_case(patient["patient_key"])
    observation = next(item for item in case["facts"] if item["resource_type"] == "Observation")
    assert observation["code_text"] == "Haemoglobin"
    assert observation["value_text"] == "12.4"
    assert observation["unit"] == "g/dL"
    assert observation["provenance"] == "Documented"
    assert case["unlinked_facts"] == 1  # Condition has no explicit Encounter reference.
    assert any("not treated as negative" in item for item in case["limitations"])


def test_fhir_import_is_idempotent_and_skips_unchanged_file(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    first = repo.import_directory(source)
    second = repo.import_directory(source)
    assert first["patients"] == 1
    assert second["skipped_unchanged"] == 1
    assert repo.list_patients()["total"] == 1
    patient = repo.list_patients()["items"][0]
    assert len(repo.patient_case(patient["patient_key"])["facts"]) == 2


def test_malformed_file_does_not_prevent_other_files_import(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "a-bad.json").write_text("{broken", encoding="utf-8")
    (source / "b-good.json").write_text(json.dumps(_bundle("p-2")), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    result = repo.import_directory(source)
    assert result["errors"] == 1
    assert result["patients"] == 1
    assert result["status"] == "completed_with_errors"


def test_oversized_json_rejected_without_loading(tmp_path, monkeypatch):
    import backend.hsptl_core.case_engine as module
    source = tmp_path / "fhir"
    source.mkdir()
    file = source / "large.json"
    file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "MAX_JSON_FILE_BYTES", 1)
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    result = repo.import_directory(source)
    assert result["errors"] == 1
    assert result["patients"] == 0


def test_encounter_link_resolves_when_encounter_is_in_later_batch(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    bundle = _bundle()
    entries = bundle["entry"]
    patient = entries[0]
    observation = entries[2]
    encounter = entries[1]
    fillers = [{"resource": {"resourceType": "Condition", "id": f"orphan-{i}", "code": {"text": "Not linked"}}} for i in range(23)]
    # The first batch contains Patient + Observation + 23 resources; Encounter is in batch 2.
    bundle["entry"] = [patient, observation, *fillers, encounter]
    (source / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    result = repo.import_directory(source, batch_size=25)
    patient_row = repo.list_patients()["items"][0]
    case = repo.patient_case(patient_row["patient_key"])
    observation_row = next(item for item in case["facts"] if item["resource_type"] == "Observation")
    assert result["facts"] == 1
    assert observation_row["encounter_key"] == case["encounters"][0]["encounter_key"]


def test_changed_source_file_prunes_removed_facts_after_success(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    path = source / "bundle.json"
    path.write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    repo.import_directory(source)
    changed = _bundle()
    changed["entry"] = [entry for entry in changed["entry"] if entry.get("resource", {}).get("resourceType") != "Condition"]
    path.write_text(json.dumps(changed), encoding="utf-8")
    repo.import_directory(source)
    patient = repo.list_patients()["items"][0]
    assert {fact["resource_type"] for fact in repo.patient_case(patient["patient_key"])["facts"]} == {"Observation"}


def test_resource_without_patient_reference_is_not_guessed(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    bundle = _bundle()
    bundle["entry"].append({"resource": {"resourceType": "Observation", "id": "no-subject", "code": {"text": "Orphan"}}})
    (source / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    result = repo.import_directory(source)
    assert result["unlinked"] == 1
    patient = repo.list_patients()["items"][0]
    assert len(repo.patient_case(patient["patient_key"])["facts"]) == 2


def test_raw_fhir_record_is_never_automatically_diagnostic_puzzle_eligible(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    repo.import_directory(source)
    patient = repo.list_patients()["items"][0]
    case = repo.patient_case(patient["patient_key"])
    assert case["quality"]["ready_for_human_review"] is True
    assert case["quality"]["diagnostic_puzzle_eligible"] is False
    assert case["quality"]["record_status"] == "review_candidate"


def test_empty_patient_record_is_not_marked_review_ready(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "empty-patient"}}]}
    (source / "patient.json").write_text(json.dumps(bundle), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    repo.import_directory(source)
    patient = repo.list_patients()["items"][0]
    case = repo.patient_case(patient["patient_key"])
    assert case["quality"]["ready_for_human_review"] is False
    assert case["quality"]["diagnostic_puzzle_eligible"] is False


def test_case_engine_schema_migration_is_recorded(tmp_path):
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    with repo.transaction() as conn:
        versions = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    assert 2 in versions
    assert 3 in versions


def test_encounter_narrative_is_source_faithful_and_separates_condition(tmp_path):
    from backend.hsptl_core.clinical_narrative import build_encounter_narrative
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    repo.import_directory(source)
    patient = repo.list_patients()["items"][0]
    encounter = repo.patient_case(patient["patient_key"])["encounters"][0]
    case = repo.patient_case(patient["patient_key"], encounter_key=encounter["encounter_key"])
    narrative = build_encounter_narrative(case)
    sections = {item["title"]: item for item in narrative["sections"]}
    assert sections["Presenting history"]["availability"] == "unavailable"
    assert sections["Examination"]["availability"] == "unavailable"
    assert narrative["patient_context"]["age"] == 34
    assert narrative["patient_context"]["age_provenance"].startswith("Derived from documented")
    assert sections["Encounter context"]["availability"] == "documented"
    assert sections["Observations and measurements"]["items"][0]["value"] == "12.4 g/dL"
    # The source Condition has no encounter reference and must not be pulled into this visit.
    assert sections["Coded conditions"]["items"] == []
    assert narrative["diagnostic_puzzle_eligible"] is False
    assert "not automatically treated as the answer" in sections["Coded conditions"]["note"]


def test_learning_attempt_requires_encounter_belonging_to_patient(tmp_path):
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps(_bundle()), encoding="utf-8")
    repo = CaseRepository(tmp_path / "hsptl.sqlite3")
    repo.import_directory(source)
    patient = repo.list_patients()["items"][0]
    encounter = repo.patient_case(patient["patient_key"])["encounters"][0]
    result = repo.save_learning_attempt(patient_key=patient["patient_key"], encounter_key=encounter["encounter_key"], payload={
        "case_code": "SYN-TEST", "problem_representation": "A learner draft", "differentials": ["A", "B"],
        "evidence_for": "Documented observation", "evidence_against": "Missing history", "investigation_plan": "Targeted test", "confidence": 3,
        "working_diagnosis": "Learner impression", "management_plan": "Learning plan", "safety_net": "Escalation triggers",
        "communication_plan": "Explain uncertainty", "stage_completed": 5,
        "cited_fact_keys": ["fact-1"], "prioritisation_rationale": "Relevant documented evidence",
    })
    assert result["saved"] is True
    assert result["attempt_id"]
    with repo.transaction() as conn:
        saved = conn.execute(
            "SELECT working_diagnosis,management_plan,safety_net,communication_plan,stage_completed,"
            "expected_missing,next_discriminating_question,cited_fact_keys_json,prioritisation_rationale "
            "FROM clinical_learning_attempts WHERE attempt_id=?",
            (result["attempt_id"],),
        ).fetchone()
    assert tuple(saved) == (
        "Learner impression", "Learning plan", "Escalation triggers", "Explain uncertainty", 5,
        "", "", '["fact-1"]', "Relevant documented evidence",
    )
    with pytest.raises(ValueError):
        repo.save_learning_attempt(patient_key="wrong-patient-key-000000", encounter_key=encounter["encounter_key"], payload={
            "case_code": "SYN-TEST", "confidence": 3,
        })


def test_reasoning_feedback_is_completeness_only_and_not_diagnostic_scoring():
    from backend.hsptl_core.reasoning_feedback import assess_reasoning_completeness
    result = assess_reasoning_completeness({
        "problem_representation": "A concise summary",
        "differentials": ["A", "B"],
        "evidence_for": "Finding supports A",
        "evidence_against": "Important uncertainty",
        "investigation_plan": "Test to answer a defined question",
        "working_diagnosis": "Working impression",
        "management_plan": "Learning plan",
        "safety_net": "Escalation plan",
        "communication_plan": "Discuss uncertainty",
        "confidence": 4,
    })
    assert result["completed"] == 9
    assert result["coverage_percent"] == 100
    assert result["type"] == "completeness_only"
    assert "not a measure of diagnostic accuracy" in result["limitations"][0]


def test_reasoning_feedback_flags_missing_components_without_scoring_correctness():
    from backend.hsptl_core.reasoning_feedback import assess_reasoning_completeness
    result = assess_reasoning_completeness({"confidence": 2, "differentials": []})
    assert result["completed"] == 0
    assert all(not item["documented"] for item in result["dimensions"])
    assert all(item["suggestion"] for item in result["dimensions"])
