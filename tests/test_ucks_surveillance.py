from datetime import datetime, timezone, timedelta

from backend.hsptl_core.store import StudyStore
from backend.hsptl_core.ucks import UCKSRepository
from backend.hsptl_core.ucks_surveillance import (
    initialise_surveillance, detect_feed_change, list_change_events,
    review_change_event, scan_staleness, list_staleness_flags, review_staleness_flag,
)


def setup(tmp_path):
    store = StudyStore(tmp_path / "surveillance.sqlite3")
    repo = UCKSRepository(store)
    initialise_surveillance(store)
    source = repo.register_source(name="Publisher", source_type="online_feed", locator="https://example.org/feed")
    return store, repo, source


def test_retraction_signal_is_proposed_not_automatically_applied(tmp_path):
    store, repo, source = setup(tmp_path)
    doc = repo.ingest_document(source_id=source["id"], title="Trial report", body="Trial findings.",
                               external_id="trial-1", content_type="trial")
    event = detect_feed_change(store, source["id"], {"title": "Retraction notice", "body": "This article is retracted.",
        "external_id": "trial-1", "url": "https://example.org/trial-1"})
    assert event and event["event_type"] == "retraction"
    assert repo.get_document(doc["id"])["lifecycle_state"] == "current"
    reviewed = review_change_event(store, repo, event["id"], "confirm_retraction", "Publisher notice verified")
    assert reviewed["status"] == "confirm_retraction"
    assert repo.get_document(doc["id"])["lifecycle_state"] == "retracted"


def test_change_signals_deduplicate_and_ignore_unrelated_entries(tmp_path):
    store, repo, source = setup(tmp_path)
    assert detect_feed_change(store, source["id"], {"title": "Routine issue", "body": "New research", "external_id": "x"}) is None
    entry = {"title": "Correction notice", "body": "Erratum", "external_id": "x"}
    first = detect_feed_change(store, source["id"], entry)
    second = detect_feed_change(store, source["id"], entry)
    assert first["created"] is True and second["created"] is False
    assert len(list_change_events(store)) == 1


def test_staleness_is_a_review_flag_not_a_lifecycle_change(tmp_path):
    store, repo, source = setup(tmp_path)
    old_date = (datetime.now(timezone.utc).date() - timedelta(days=1500)).isoformat()
    doc = repo.ingest_document(source_id=source["id"], title="Older guideline", body="Guideline text.",
                               content_type="guideline", publication_date=old_date)
    result = scan_staleness(store, max_age_days=1095)
    flags = list_staleness_flags(store)
    assert result["flags_created"] == 1 and flags[0]["document_id"] == doc["id"]
    assert repo.get_document(doc["id"])["lifecycle_state"] == "current"
    review_staleness_flag(store, flags[0]["id"], "needs_update", "Check publisher for newer edition")
    assert list_staleness_flags(store) == []
