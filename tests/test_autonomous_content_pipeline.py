from pathlib import Path

from backend.hsptl_core.external_source_automation import ExternalSourceAutomation
from backend.hsptl_core.store import StudyStore
from backend.hsptl_core.ucks import UCKSRepository


def test_new_machine_screened_cc_by_guideline_generates_and_publishes_provisionally(tmp_path: Path):
    store = StudyStore(tmp_path / "autonomous.sqlite3")
    repo = UCKSRepository(store)
    source = repo.register_source(
        name="Automated test source", source_type="external_import",
        licence="Provider terms; item-level licence controls reuse",
        config={"automation_profile": "test-profile", "connector": "europe_pmc"},
    )
    document = repo.ingest_document(
        source_id=source["id"], title="Acute asthma guideline",
        body=("## Assessment\n\n" +
              "A structured clinical assessment should document symptom severity and response. " * 5 +
              "\n\n## Follow-up\n\n" +
              "The source recommends reassessment and clear escalation criteria. " * 5),
        content_type="guideline", external_id="guideline-1",
        source_url="https://example.org/guideline", licence="CC-BY-4.0",
        review_status="machine_screened",
        provenance={"automated_screening": {"passed": True}},
    )
    automation = ExternalSourceAutomation(repo)

    result = automation._generate_and_publish_new_records({
        "results": [{"source_id": source["id"], "status": "succeeded", "records_added": 1}]
    })

    assert result["generated"] == 1
    assert result["published"] == 1
    assert result["items"][0]["status"] == "provisional"
    with store.transaction() as conn:
        artifact = conn.execute(
            "SELECT status,source_refs_json FROM generated_artifacts"
        ).fetchone()
        indexed = conn.execute(
            "SELECT source_status FROM tagged_content_items"
        ).fetchone()
    assert artifact["status"] == "provisional"
    assert document["id"] in artifact["source_refs_json"]
    assert indexed["source_status"] == "unreviewed"


def test_automatic_generation_skips_unknown_rights_without_blocking_import(tmp_path: Path):
    store = StudyStore(tmp_path / "rights.sqlite3")
    repo = UCKSRepository(store)
    source = repo.register_source(name="Restricted source", source_type="external_import")
    repo.ingest_document(
        source_id=source["id"], title="Restricted guideline",
        body="Clinical guidance text that must not be reused without permission. " * 8,
        content_type="guideline", external_id="restricted-1",
        source_url="https://example.org/restricted", licence="All rights reserved",
        review_status="machine_screened",
    )
    automation = ExternalSourceAutomation(repo)
    result = automation._generate_and_publish_new_records({
        "results": [{"source_id": source["id"], "status": "succeeded", "records_added": 1}]
    })
    assert result["generated"] == 0
    assert result["skipped"] == 1
    assert "reuse" in result["items"][0]["reason"].lower() or "rights" in result["items"][0]["reason"].lower()
    assert repo.stats()["documents"] == 1


def test_source_revision_creates_a_new_provisional_learning_version(tmp_path: Path):
    store = StudyStore(tmp_path / "revision.sqlite3")
    repo = UCKSRepository(store)
    source = repo.register_source(name="Revision source", source_type="external_import")
    first = repo.ingest_document(
        source_id=source["id"], title="Updated respiratory guideline",
        body="## Evidence\n\n" + "The first version recommends structured assessment. " * 8,
        content_type="guideline", external_id="resp-guideline",
        source_url="https://example.org/resp", licence="CC-BY-4.0",
        review_status="machine_screened",
    )
    automation = ExternalSourceAutomation(repo)
    run = {"results": [{"source_id": source["id"], "status": "succeeded", "records_added": 1}]}
    first_result = automation._generate_and_publish_new_records(run)
    assert first_result["generated"] == 1

    repo.revise_document(
        first["id"], title="Updated respiratory guideline",
        body="## Evidence\n\n" + "The revised version recommends reassessment and escalation. " * 8,
    )
    second_result = automation._generate_and_publish_new_records(run)
    assert second_result["generated"] == 1
    with store.transaction() as conn:
        versions = conn.execute("SELECT COUNT(*) FROM generated_artifacts").fetchone()[0]
    assert versions == 2


def test_source_revision_and_retraction_quarantine_downstream_learning_artifacts(tmp_path: Path):
    store = StudyStore(tmp_path / "source-lifecycle.sqlite3")
    repo = UCKSRepository(store)
    source = repo.register_source(name="Lifecycle source", source_type="external_import")
    document = repo.ingest_document(
        source_id=source["id"], title="Evidence guideline",
        body="## Evidence\n\n" + "The original guideline recommends a structured assessment. " * 8,
        content_type="guideline", external_id="lifecycle-guideline",
        source_url="https://example.org/lifecycle", licence="CC-BY-4.0",
        review_status="machine_screened",
    )
    automation = ExternalSourceAutomation(repo)
    run = {"results": [{"source_id": source["id"], "status": "succeeded", "records_added": 1}]}
    generated = automation._generate_and_publish_new_records(run)
    assert generated["published"] == 1
    with store.transaction() as conn:
        old_artifact_id = conn.execute("SELECT id FROM generated_artifacts").fetchone()["id"]

    repo.revise_document(
        document["id"], title="Evidence guideline",
        body="## Evidence\n\n" + "The revised guideline updates the assessment and follow-up advice. " * 8,
    )
    revised = automation._reconcile_downstream_artifacts()
    assert revised["refresh_required"] == 1
    with store.transaction() as conn:
        old = conn.execute("SELECT status FROM generated_artifacts WHERE id=?", (old_artifact_id,)).fetchone()
        indexed = conn.execute("SELECT source_status FROM tagged_content_items WHERE content_id=?", (old_artifact_id,)).fetchone()
    assert old["status"] == "source_update_required"
    assert indexed["source_status"] == "source_update_required"

    repo.set_lifecycle_state(document["id"], "retracted")
    withdrawn = automation._reconcile_downstream_artifacts()
    assert withdrawn["withdrawn"] == 1
    with store.transaction() as conn:
        old = conn.execute("SELECT status FROM generated_artifacts WHERE id=?", (old_artifact_id,)).fetchone()
        route = conn.execute("SELECT status FROM distribution_routes WHERE artifact_id=?", (old_artifact_id,)).fetchone()
    assert old["status"] == "withdrawn"
    assert route["status"] == "withdrawn"
