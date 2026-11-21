from __future__ import annotations

import json

import pytest

from backend.hsptl_core.ucks_connectors import _crossref, sync_connector


class Response:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.headers = {}
    def raise_for_status(self):
        return None
    def iter_content(self, chunk_size):
        yield json.dumps(self.payload).encode()


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.payload)


def test_europe_pmc_open_access_flag_treats_provider_n_as_false():
    from backend.hsptl_core.ucks_connectors import _normalise_europe_pmc

    records = _normalise_europe_pmc({"resultList": {"result": [
        {"pmcid": "PMC123", "title": "Closed record", "isOpenAccess": "N", "license": "CC BY"},
        {"pmcid": "PMC124", "title": "Open record", "isOpenAccess": "Y", "license": "CC BY"},
    ]}})
    assert records[0]["provenance"]["is_open_access"] is False
    assert records[1]["provenance"]["is_open_access"] is True


def test_crossref_metadata_normalisation():
    session = Session({"message": {"items": [{
        "DOI": "10.1000/example", "title": ["A clinical study"],
        "author": [{"family": "Smith", "given": "A"}],
        "published": {"date-parts": [[2024, 2, 3]]}, "type": "journal-article",
        "URL": "https://api.crossref.org/works/10.1000/example", "license": []
    }]}})
    records = _crossref("clinical study", 10, session)
    assert len(records) == 1
    assert records[0]["external_id"] == "DOI:10.1000/example"
    assert records[0]["publication_date"] == "2024-02-03"
    assert "abstract not supplied" in records[0]["body"]
    assert records[0]["provenance"]["rights_review_required"] is True


def test_connector_sync_keeps_records_harvested_and_deduplicates(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "connectors.sqlite3"))
    source = repo.register_source(name="Test Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [{
        "external_id": "DOI:10.1/test", "title": "Test paper", "body": "# Test paper\n\nMetadata record",
        "content_type": "other", "publication_date": "2024", "url": "https://doi.org/10.1/test",
        "licence": "", "provenance": {"connector": "Crossref"}
    }])
    first = sync_connector(repo, source["id"], "test")
    second = sync_connector(repo, source["id"], "test")
    assert first["records_added"] == 1
    assert second["records_added"] == 0
    docs = repo.search("Test paper", limit=10)
    assert docs[0]["review_status"] == "harvested"
    assert docs[0]["provenance_json"] and docs[0]["source_url"] == "https://doi.org/10.1/test"


def test_connector_requires_explicit_supported_source(tmp_path):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    repo = UCKSRepository(StudyStore(tmp_path / "invalid.sqlite3"))
    source = repo.register_source(name="Feed", source_type="online_feed", locator="https://example.org")
    with pytest.raises(ValueError, match="supported connector"):
        sync_connector(repo, source["id"], "heart failure")


def test_europe_pmc_fulltext_requires_allowlisted_open_access_licence():
    from backend.hsptl_core.ucks_connectors import _europe_pmc_fulltext
    record = {"title": "Test", "licence": "CC BY-NC 4.0", "provenance": {
        "pmcid": "PMC123", "is_open_access": True}}
    body, metadata = _europe_pmc_fulltext(record, Session({}))
    assert body == ""
    assert metadata["full_text_status"] == "not_fetched_rights_or_identifier"


def test_europe_pmc_fulltext_extracts_jats_body():
    from backend.hsptl_core.ucks_connectors import _europe_pmc_fulltext
    class XMLResponse:
        status_code = 200
        headers = {}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size):
            yield (b"<article><body><sec><title>Methods</title><p>" + b"Clinical methods text " * 30 + b"</p></sec></body></article>")
    class XMLSession:
        def get(self, url, **kwargs):
            assert "PMC123" in url
            return XMLResponse()
    record = {"title": "Test article", "licence": "CC BY 4.0", "provenance": {
        "pmcid": "PMC123", "is_open_access": True}}
    body, metadata = _europe_pmc_fulltext(record, XMLSession())
    assert "## Methods" in body
    assert metadata["full_text_status"] == "fetched"


def test_connector_changed_body_revises_existing_document(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "revision.sqlite3"))
    source = repo.register_source(name="Test Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    record = {"external_id": "DOI:10.1/revision", "title": "Revision paper",
        "body": "# Revision paper\n\nFirst abstract version", "content_type": "other",
        "publication_date": "2024", "url": "https://doi.org/10.1/revision", "licence": "",
        "provenance": {"connector": "Crossref"}}
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [record])
    sync_connector(repo, source["id"], "revision")
    doc = repo.search("Revision paper", limit=1)[0]
    document_id = doc["document_id"]
    record["body"] = "# Revision paper\n\nCorrected abstract version"
    sync_connector(repo, source["id"], "revision")
    updated = repo.get_document(document_id)
    assert updated["current_version"] == 2
    assert updated["review_status"] == "harvested"


def test_connector_revision_does_not_reactivate_retracted_document(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "retracted.sqlite3"))
    source = repo.register_source(name="Test Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    record = {"external_id": "DOI:10.1/retracted", "title": "Retracted paper",
        "body": "# Retracted paper\n\nOriginal abstract", "content_type": "other",
        "publication_date": "2024", "url": "https://doi.org/10.1/retracted", "licence": "",
        "provenance": {"connector": "Crossref"}}
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [record])
    sync_connector(repo, source["id"], "retracted")
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT id FROM ucks_documents WHERE external_id=?", (record["external_id"],)).fetchone()
    repo.set_lifecycle_state(row["id"], "retracted")
    record["body"] = "# Retracted paper\n\nPublisher metadata updated"
    sync_connector(repo, source["id"], "retracted")
    assert repo.get_document(row["id"])["lifecycle_state"] == "retracted"



def test_connector_schedule_is_opt_in_and_persists_query(tmp_path):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    from backend.hsptl_core.ucks_connectors import configure_connector_schedule, get_connector_schedule
    repo = UCKSRepository(StudyStore(tmp_path / "schedule.sqlite3"))
    source = repo.register_source(name="Scheduled Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    assert get_connector_schedule(repo) == []
    saved = configure_connector_schedule(repo, source["id"], enabled=True,
        query="heart failure", interval_minutes=60, result_limit=40)
    assert saved["enabled"] == 1
    assert saved["query_text"] == "heart failure"
    assert saved["result_limit"] == 40
    disabled = configure_connector_schedule(repo, source["id"], enabled=False,
        query="heart failure")
    assert disabled["next_run"] == ""


def test_due_connector_run_completes_and_records_harvested_results(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    from backend.hsptl_core.ucks_connectors import configure_connector_schedule, run_due_connectors
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "due.sqlite3"))
    source = repo.register_source(name="Due Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    configure_connector_schedule(repo, source["id"], enabled=True, query="test query")
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [{
        "external_id": "DOI:10.1/scheduled", "title": "Scheduled paper",
        "body": "# Scheduled paper\\n\\nAbstract metadata", "content_type": "other",
        "publication_date": "2025", "url": "https://doi.org/10.1/scheduled",
        "licence": "", "provenance": {"connector": "Crossref"}}])
    result = run_due_connectors(repo)
    assert result["claimed"] == 1
    assert result["results"][0]["status"] == "succeeded"
    assert repo.search("Scheduled paper", limit=1)[0]["review_status"] == "harvested"
    schedule = connectors.get_connector_schedule(repo, source["id"])
    assert schedule["consecutive_failures"] == 0
    assert schedule["lease_until"] == ""


def test_connector_checkpoint_tracks_successful_runs_and_is_query_scoped(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    from backend.hsptl_core.ucks_connectors import sync_connector, get_connector_checkpoint
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "checkpoint.sqlite3"))
    source = repo.register_source(name="Checkpoint Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    record = {"external_id": "DOI:10.1/checkpoint", "title": "Checkpoint paper",
        "body": "# Checkpoint paper\\n\\nMetadata", "content_type": "other", "publication_date": "2025",
        "url": "https://doi.org/10.1/checkpoint", "licence": "", "provenance": {"connector": "Crossref"}}
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [record])
    first = sync_connector(repo, source["id"], "checkpoint query")
    second = sync_connector(repo, source["id"], "checkpoint query")
    checkpoint = get_connector_checkpoint(repo, source["id"], "checkpoint query")
    assert first["checkpoint"]["sync_runs_completed"] == 1
    assert second["checkpoint"]["sync_runs_completed"] == 2
    assert checkpoint["records_seen"] == 2
    assert checkpoint["records_added"] == 1
    assert checkpoint["last_external_id"] == "DOI:10.1/checkpoint"
    assert get_connector_checkpoint(repo, source["id"], "different query") is None


def test_native_connector_pagination_persists_and_resumes_cursor(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "pagination.sqlite3"))
    source = repo.register_source(name="Paged Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    def record(doi):
        return {"external_id": f"DOI:{doi}", "title": doi, "body": f"# {doi}\\n\\nMetadata",
            "content_type": "other", "publication_date": "2025", "url": f"https://doi.org/{doi}",
            "licence": "", "provenance": {"connector": "Crossref"}}
    cursors = []
    pages = [
        {"records": [record("10.1/page1")], "next_cursor": "1", "total_records": 2, "complete": False},
        {"records": [record("10.1/page2")], "next_cursor": "", "total_records": 2, "complete": True},
    ]
    def fetch(query, limit, session, cursor=""):
        cursors.append(cursor)
        return pages[len(cursors)-1]
    monkeypatch.setitem(connectors._PAGE_FETCHERS, "crossref", fetch)
    first = connectors.sync_connector(repo, source["id"], "paged query")
    assert first["pagination"]["complete"] is False
    assert first["checkpoint"]["cursor"] == "1"
    second = connectors.sync_connector(repo, source["id"], "paged query")
    assert second["pagination"]["complete"] is True
    assert cursors == ["", "1"]
    checkpoint = connectors.get_connector_checkpoint(repo, source["id"], "paged query")
    assert checkpoint["pages_completed"] == 2
    assert checkpoint["total_records"] == 2
    assert checkpoint["pagination_complete"] == 1
    assert checkpoint["records_added"] == 2


def test_crossref_page_uses_offset_and_total_results():
    from backend.hsptl_core.ucks_connectors import _crossref_page
    class RecordingSession(Session):
        pass
    session = RecordingSession({"message": {"total-results": 3, "items": [{
        "DOI": "10.1/a", "title": ["A"]}]}})
    page = _crossref_page("test", 1, session, "1")
    params = session.calls[0][1]["params"]
    assert params["offset"] == 1
    assert page["total_records"] == 3
    assert page["next_cursor"] == "2"
    assert page["complete"] is False


def test_clinicaltrials_page_uses_next_page_token():
    from backend.hsptl_core.ucks_connectors import _clinicaltrials_page
    session = Session({"totalCount": 12, "nextPageToken": "opaque-token", "studies": []})
    page = _clinicaltrials_page("diabetes", 5, session)
    params = session.calls[0][1]["params"]
    assert params["countTotal"] == "true"
    assert page["next_cursor"] == "opaque-token"
    assert page["complete"] is False
    next_session = Session({"totalCount": 12, "studies": []})
    _clinicaltrials_page("diabetes", 5, next_session, "opaque-token")
    assert next_session.calls[0][1]["params"]["pageToken"] == "opaque-token"


def test_cross_provider_identifier_index_links_without_merging_documents(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors
    repo = UCKSRepository(StudyStore(tmp_path / "identifier-crosswalk.sqlite3"))
    pubmed = repo.register_source(name="PubMed IDs", source_type="external_import",
        locator="https://eutils.ncbi.nlm.nih.gov", config={"connector": "pubmed"})
    crossref = repo.register_source(name="Crossref IDs", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    monkeypatch.setitem(connectors._FETCHERS, "pubmed", lambda q, n, session: [{
        "external_id": "PMID:123456", "title": "Indexed from PubMed", "body": "PubMed abstract text",
        "content_type": "other", "publication_date": "2024", "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
        "licence": "", "provenance": {"connector": "PubMed", "pmid": "123456", "doi": "10.1000/Shared.DOI"}}])
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: [{
        "external_id": "DOI:10.1000/shared.doi", "title": "Indexed from Crossref", "body": "Crossref metadata text",
        "content_type": "other", "publication_date": "2024", "url": "https://doi.org/10.1000/shared.doi",
        "licence": "", "provenance": {"connector": "Crossref", "doi": "https://doi.org/10.1000/SHARED.DOI"}}])
    first = connectors.sync_connector(repo, pubmed["id"], "identifier test")
    second = connectors.sync_connector(repo, crossref["id"], "identifier test")
    assert first["records_added"] == second["records_added"] == 1
    matches = connectors.find_identifier_matches(repo, "doi", "https://doi.org/10.1000/Shared.DOI")
    assert len(matches) == 2
    assert {m["source_id"] for m in matches} == {pubmed["id"], crossref["id"]}
    pmid_matches = connectors.find_identifier_matches(repo, "pmid", "PMID:123456")
    assert len(pmid_matches) == 1
    assert len({m["document_id"] for m in matches}) == 2  # no silent cross-source merge


def test_identifier_normalisation_rejects_invalid_identifiers():
    from backend.hsptl_core.ucks_connectors import _normalise_identifier
    assert _normalise_identifier("doi", "https://doi.org/10.1000/ABC") == ("doi", "10.1000/abc")
    assert _normalise_identifier("pmcid", "PMC123") == ("pmcid", "PMC123")
    assert _normalise_identifier("nct", "nct01234567") == ("nct", "NCT01234567")
    assert _normalise_identifier("pmid", "not-a-pmid") is None


def test_managed_sync_walks_multiple_provider_pages_per_automation_tick(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors

    repo = UCKSRepository(StudyStore(tmp_path / "multi-page.sqlite3"))
    source = repo.register_source(name="Paged Crossref", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref", "automation_profile": "test"})

    def record(identifier):
        return {"external_id": f"DOI:{identifier}", "title": identifier,
            "body": f"# {identifier}\n\nMetadata", "content_type": "other",
            "publication_date": "2025", "url": f"https://doi.org/{identifier}",
            "licence": "", "provenance": {"connector": "Crossref"}}

    pages = [
        {"records": [record("10.1/a")], "next_cursor": "cursor-1", "total_records": 3, "complete": False},
        {"records": [record("10.1/b")], "next_cursor": "cursor-2", "total_records": 3, "complete": False},
        {"records": [record("10.1/c")], "next_cursor": "", "total_records": 3, "complete": True},
    ]
    cursors = []

    def fetch(query, limit, session, cursor=""):
        cursors.append(cursor)
        return pages[len(cursors) - 1]

    monkeypatch.setitem(connectors._PAGE_FETCHERS, "crossref", fetch)
    result = connectors.sync_connector(repo, source["id"], "historical query", max_pages_per_run=10)
    checkpoint = connectors.get_connector_checkpoint(repo, source["id"], "historical query")

    assert result["records_seen"] == 3
    assert result["records_added"] == 3
    assert result["pagination"]["pages_completed_this_run"] == 3
    assert result["pagination"]["complete"] is True
    assert cursors == ["", "cursor-1", "cursor-2"]
    assert checkpoint["pages_completed"] == 3
    assert checkpoint["pagination_complete"] == 1


def test_explicit_pubmed_retraction_signal_quarantines_imported_record(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors

    repo = UCKSRepository(StudyStore(tmp_path / "provider-retraction.sqlite3"))
    source = repo.register_source(name="Managed PubMed", source_type="external_import",
        locator="https://eutils.ncbi.nlm.nih.gov", config={"connector": "pubmed", "automation_profile": "test"})
    record = {"external_id": "PMID:999", "title": "Retracted paper", "body": "# Retracted paper\n\nAbstract",
        "content_type": "other", "publication_date": "2025", "url": "https://pubmed.ncbi.nlm.nih.gov/999/",
        "licence": "", "provenance": {"connector": "NCBI PubMed E-utilities",
            "publisher_lifecycle_signal": "retracted", "publication_types": ["Retracted Publication"]}}
    monkeypatch.setitem(connectors._PAGE_FETCHERS, "pubmed", lambda q, n, session, cursor="": {
        "records": [record], "next_cursor": "", "total_records": 1, "complete": True})

    connectors.sync_connector(repo, source["id"], "retraction query")
    document = repo.search("Retracted paper", limit=1)[0]
    stored = repo.get_document(document["document_id"])
    assert stored["lifecycle_state"] == "retracted"


def test_crossref_explicit_retraction_relation_marks_related_doi_retracted(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors

    repo = UCKSRepository(StudyStore(tmp_path / "crossref-relations.sqlite3"))
    source = repo.register_source(name="Crossref relations", source_type="external_import",
        locator="https://api.crossref.org", config={"connector": "crossref"})
    records = [
        {"external_id": "DOI:10.1000/original", "title": "Original paper",
         "body": "# Original paper\n\nOriginal abstract", "content_type": "other",
         "publication_date": "2024", "url": "https://doi.org/10.1000/original", "licence": "",
         "provenance": {"connector": "Crossref", "doi": "10.1000/original", "relation_metadata": {}}},
        {"external_id": "DOI:10.1000/retraction", "title": "Retraction notice",
         "body": "# Retraction notice\n\nNotice metadata", "content_type": "other",
         "publication_date": "2026", "url": "https://doi.org/10.1000/retraction", "licence": "",
         "provenance": {"connector": "Crossref", "doi": "10.1000/retraction",
             "relation_metadata": {"is-retraction-of": [{"id-type": "doi", "id": "10.1000/original"}]}}},
    ]
    monkeypatch.setitem(connectors._FETCHERS, "crossref", lambda q, n, session: records)
    connectors.sync_connector(repo, source["id"], "relation test")
    original = repo.search("Original paper", limit=1)[0]
    assert repo.get_document(original["document_id"])["lifecycle_state"] == "retracted"


def test_crossref_update_watermark_uses_updated_filter_and_sort():
    from backend.hsptl_core.ucks_connectors import _crossref_page

    session = Session({"message": {"items": [], "total-results": 0}})
    page = _crossref_page(
        "clinical medicine from-update-date:2026-10-22 until-update-date:2026-11-21",
        20, session,
    )
    params = session.calls[0][1]["params"]
    assert params["sort"] == "updated"
    assert "from-update-date:2026-10-22" in params["filter"]
    assert "until-update-date:2026-11-21" in params["filter"]
    assert page["complete"] is True


def test_clinicaltrials_connector_preserves_true_last_update_watermark():
    from backend.hsptl_core.ucks_connectors import _clinicaltrials_page

    payload = {"studies": [{"protocolSection": {
        "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Updated trial"},
        "descriptionModule": {"briefSummary": "A synthetic summary", "detailedDescription": ""},
        "statusModule": {"overallStatus": "RECRUITING", "studyFirstSubmitDate": "2020-01-01",
                         "studyLastUpdatePostDateStruct": {"date": "2026-11-20"},
                         "studyLastUpdateSubmitDate": "2026-11-18"},
        "designModule": {},
    }}], "totalCount": 1}
    page = _clinicaltrials_page("updated", 20, Session(payload))
    record = page["records"][0]
    assert record["provenance"]["last_update_posted"] == "2026-11-20"
    assert record["provenance"]["last_update_submitted"] == "2026-11-18"
    assert "2026-11-20" in record["body"]


def test_pubmed_explicit_retraction_relationship_marks_referenced_pmid(tmp_path, monkeypatch):
    from backend.hsptl_core.ucks import UCKSRepository
    from backend.hsptl_core.store import StudyStore
    import backend.hsptl_core.ucks_connectors as connectors

    repo = UCKSRepository(StudyStore(tmp_path / "pubmed-relations.sqlite3"))
    source = repo.register_source(name="PubMed relation feed", source_type="external_import",
        locator="https://eutils.ncbi.nlm.nih.gov", config={"connector": "pubmed"})
    records = [
        {"external_id": "PMID:1001", "title": "Original article", "body": "# Original article\n\nAbstract",
         "content_type": "other", "publication_date": "2023", "url": "https://pubmed.ncbi.nlm.nih.gov/1001/",
         "licence": "", "provenance": {"connector": "PubMed", "pmid": "1001"}},
        {"external_id": "PMID:1002", "title": "Retraction notice", "body": "# Retraction notice\n\nNotice",
         "content_type": "other", "publication_date": "2026", "url": "https://pubmed.ncbi.nlm.nih.gov/1002/",
         "licence": "", "provenance": {"connector": "PubMed", "pmid": "1002",
             "publication_relations": [{"type": "RetractionOf", "pmid": "1001"}]}},
    ]
    monkeypatch.setitem(connectors._PAGE_FETCHERS, "pubmed", lambda q, n, session, cursor="": {
        "records": records, "next_cursor": "", "total_records": 2, "complete": True})
    connectors.sync_connector(repo, source["id"], "pubmed relation test")
    original = repo.search("Original article", limit=1)[0]
    assert repo.get_document(original["document_id"])["lifecycle_state"] == "retracted"
