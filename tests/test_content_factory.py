from __future__ import annotations

from backend.hsptl_core.content_factory import ContentFactory
from backend.hsptl_core.generation_distribution import GenerationDistribution


def test_pack_is_populated_valid_and_model_free():
    factory = ContentFactory()
    catalog = factory.catalog()
    assert catalog["unit_count"] == 8
    assert catalog["question_count"] == 24
    assert catalog["generation_policy"]["model_required"] is False
    assert catalog["content_status"] == "provisional_educational_use"


def test_all_output_types_build_for_every_unit():
    factory = ContentFactory()
    kinds = ["case_report", "case_debrief", "question_set", "topic_summary", "viva_set", "osce_station", "on_call_scenario", "handover_template", "simulation_brief"]
    for unit in factory.catalog()["units"]:
        for kind in kinds:
            spec = factory.build(unit["unit_id"], kind, seed=17)
            assert spec["body"]["validation"]["valid"] is True
            assert spec["body"]["content_status"] == "provisional_educational_use"
            assert spec["workspace"]
            if kind == "question_set":
                assert len(spec["body"]["assessment_items"]) == 3
                for item in spec["body"]["assessment_items"]:
                    assert item["answer"] in item["options"]


def test_question_variation_is_seeded_and_preserves_answer(tmp_path):
    factory = ContentFactory()
    unit_id = "acute-chest-pain-01"
    first = factory.build(unit_id, "question_set", seed=77)
    same = factory.build(unit_id, "question_set", seed=77)
    assert first["body"] == same["body"]
    for item in first["body"]["assessment_items"]:
        assert item["answer"] in item["options"]


def test_structured_draft_uses_existing_review_and_distribution_lifecycle(tmp_path):
    factory = ContentFactory()
    spec = factory.build("acute-chest-pain-01", "question_set", seed=10)
    engine = GenerationDistribution(tmp_path / "generation.db")
    artifact = engine.create_structured_draft(
        workspace=spec["workspace"], kind=spec["kind"], title=spec["title"],
        body=spec["body"], source_refs=spec["source_refs"],
        template_version=spec["template_version"],
    )
    assert artifact["status"] == "provisional"
    assert artifact["body"]["generation_mode"] == "deterministic_template_composer"
    duplicate = engine.create_structured_draft(
        workspace=spec["workspace"], kind=spec["kind"], title=spec["title"],
        body=spec["body"], source_refs=spec["source_refs"],
        template_version=spec["template_version"],
    )
    assert duplicate["id"] == artifact["id"]
    with engine.connect() as conn:
        row = conn.execute("SELECT event FROM generation_audit WHERE artifact_id=? ORDER BY created_at DESC LIMIT 1", (artifact["id"],)).fetchone()
    assert row["event"] == "generation_deduplicated"


def test_content_factory_api_catalog_generate_and_batch():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        catalog = client.get("/api/content-factory/catalog")
        assert catalog.status_code == 200
        assert catalog.json()["unit_count"] == 8
        detail = client.get("/api/content-factory/units/acute-chest-pain-01")
        assert detail.status_code == 200
        generated = client.post("/api/content-factory/generate", json={
            "unit_id": "acute-chest-pain-01", "kind": "question_set", "seed": 8,
        })
        assert generated.status_code == 201
        assert generated.json()["status"] == "provisional"
        batch = client.post("/api/content-factory/batch", json={
            "unit_ids": ["acute-chest-pain-01", "acute-asthma-01"],
            "kinds": ["topic_summary", "viva_set"], "seed": 8,
        })
        assert batch.status_code == 201
        assert batch.json()["requested"] == 4
        assert batch.json()["auto_approved"] is False

        # The full nine-format bundle is supported by both the factory and API.
        all_formats = client.post("/api/content-factory/batch", json={
            "unit_ids": ["acute-chest-pain-01"],
            "kinds": ["case_report", "case_debrief", "question_set", "topic_summary", "viva_set", "osce_station", "on_call_scenario", "handover_template", "simulation_brief"],
            "seed": 8,
        })
        assert all_formats.status_code == 201
        assert all_formats.json()["requested"] == 9


def test_factory_discovers_multiple_versioned_packs_without_new_routes(tmp_path):
    import json
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / "backend" / "content_packs" / "acute_care_foundations_v1.json"
    original = json.loads(source.read_text(encoding="utf-8"))
    first = dict(original)
    first["pack_id"] = "acute-care-foundations-test-a"
    second = json.loads(json.dumps(original))
    second["pack_id"] = "acute-care-foundations-test-b"
    second["title"] = "Second test pack"
    for unit in second["units"]:
        unit["unit_id"] = f"second-{unit['unit_id']}"
    (tmp_path / "first_v1.json").write_text(json.dumps(first), encoding="utf-8")
    (tmp_path / "second_v1.json").write_text(json.dumps(second), encoding="utf-8")

    factory = ContentFactory(tmp_path)
    catalog = factory.catalog()
    assert catalog["pack_count"] == 2
    assert catalog["unit_count"] == 16
    generated = factory.build("second-acute-asthma-01", "topic_summary", seed=7)
    assert generated["body"]["content_pack_id"] == "acute-care-foundations-test-b"
    assert generated["body"]["content_pack_version"] == "1.0.0"


def test_content_pack_validation_rejects_incomplete_osce(tmp_path):
    import json
    from pathlib import Path
    import pytest
    from backend.hsptl_core.content_factory import ContentPackError
    source = Path(__file__).resolve().parents[1] / "backend" / "content_packs" / "acute_care_foundations_v1.json"
    pack = json.loads(source.read_text(encoding="utf-8"))
    pack["units"][0]["osce"]["time_seconds"] = 20
    path = tmp_path / "invalid_v1.json"
    path.write_text(json.dumps(pack), encoding="utf-8")
    with pytest.raises(ContentPackError, match="OSCE station"):
        ContentFactory(path)


def test_startup_prepares_all_workspace_drafts_and_refresh_is_idempotent():
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        status = client.get("/api/content-factory/status")
        assert status.status_code == 200
        assert {"simulation_brief", "on_call_scenario", "handover_template"}.issubset(set(status.json()["output_types"]))

        refreshed = client.post("/api/content-factory/refresh")
        assert refreshed.status_code == 200
        payload = refreshed.json()
        assert payload["status"] == "ready"
        assert payload["unit_count"] == 8
        assert payload["draft_count"] == 8 * 9
        assert set(payload["workspace_counts"]) == {"clinic", "exam_hall", "rounds", "lab", "ward", "simulation"}
        assert payload["review_required"] is False
        assert payload["auto_approved"] is False
        assert payload["auto_published"] is True
        assert payload["created_count"] == 0
        assert payload["reused_count"] == payload["draft_count"]
        assert payload["published_count"] == payload["draft_count"]
