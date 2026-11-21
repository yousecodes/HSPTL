from backend.hsptl_core.content_factory import ContentFactory
from backend.hsptl_core.generation_distribution import GenerationDistribution
from backend.hsptl_core.unified_content import UnifiedContentPipeline


def test_unified_pipeline_creates_reviewable_drafts_and_is_idempotent(tmp_path):
    factory = ContentFactory()
    distribution = GenerationDistribution(tmp_path / "pipeline.sqlite3")
    pipeline = UnifiedContentPipeline(factory, distribution)

    first = pipeline.refresh()
    second = pipeline.refresh()

    assert first["status"] == "ready"
    assert first["created_count"] > 0
    assert first["auto_approved"] is False
    assert first["auto_published"] is False
    assert first["pipeline"] == "unified_deterministic_content_v1"
    assert second["created_count"] == 0
    assert second["reused_count"] == first["draft_count"]
    for workspace in first["workspace_counts"]:
        assert distribution.list_artifacts(workspace=workspace, limit=100)["items"]
