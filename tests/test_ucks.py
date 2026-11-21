from pathlib import Path

import pytest

from backend.hsptl_core.store import StudyStore
from backend.hsptl_core.ucks import UCKSRepository


def registered_api_paths(app) -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            paths.add(path)
        original = getattr(route, "original_router", None)
        for nested in getattr(original, "routes", []):
            nested_path = getattr(nested, "path", None)
            if isinstance(nested_path, str):
                paths.add(nested_path)
    return paths


def test_ucks_source_ingest_deduplicate_and_search(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks.sqlite3"))
    source = repo.register_source(
        name="Local test source", source_type="external_import",
        licence="CC-BY-4.0", reuse_permitted=True,
    )
    doc = repo.ingest_document(
        source_id=source["id"], title="Acute kidney injury",
        body="## Clinical presentation\n\nAcute kidney injury may present with oliguria.\n\n"
             "## Investigations\n\nMeasure serum creatinine and assess electrolytes.",
        content_type="reference_document", external_id="test-akI",
        provenance={"filename": "aki.txt", "import_method": "test"},
    )
    assert doc["chunk_count"] == 2
    assert repo.stats()["documents"] == 1
    assert repo.stats()["chunks"] == 2
    assert repo.search("serum creatinine")
    duplicate = repo.ingest_document(
        source_id=source["id"], title="Acute kidney injury",
        body="## Clinical presentation\n\nAcute kidney injury may present with oliguria.\n\n"
             "## Investigations\n\nMeasure serum creatinine and assess electrolytes.",
        content_type="reference_document", external_id="test-akI",
    )
    assert duplicate["id"] == doc["id"]
    assert repo.stats()["documents"] == 1


def test_ucks_rejects_self_validation(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks.sqlite3"))
    source = repo.register_source(name="Synthetic", source_type="synthea_mednotegen")
    with pytest.raises(ValueError, match="cannot be self-promoted"):
        repo.ingest_document(source_id=source["id"], title="Synthetic case",
                             body="Synthetic educational case.", content_type="synthetic_case",
                             review_status="validated")


def test_mednotegen_payload_is_imported_as_synthetic(tmp_path: Path):
    from backend.hsptl_core.ucks_ingestion import ingest_mednotegen_payload

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-mednote.sqlite3"))
    payload = {
        "clinic_cases": [{
            "case_code": "SYN-001", "clinical_narrative": "Synthetic patient narrative.",
            "encounter": {"date": "2026-01-01"},
            "observations": [{"display": "Haemoglobin", "value": {"value": 12, "unit": "g/dL"},
                              "provenance": {"resource_id": "Observation/1"}}],
        }],
        "pearl_seeds": [{"title": "Draft pearl", "learning_prompt": "Consider the differential.",
                         "content": "Synthetic source-derived seed."}],
    }
    result = ingest_mednotegen_payload(repo, payload)
    assert result == {"cases_seen": 1, "cases_added": 1, "pearls_seen": 1, "pearls_added": 1}
    found = repo.search("Haemoglobin")
    assert found and found[0]["content_type"] == "synthetic_case"
    assert found[0]["review_status"] == "harvested"


def test_specialty_harvest_jats_import_retains_rights_review(tmp_path: Path):
    import json
    from backend.hsptl_core.ucks_ingestion import ingest_specialty_harvest

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-harvest.sqlite3"))
    article_dir = tmp_path / "harvest" / "cardiology" / "PMC123"
    article_dir.mkdir(parents=True)
    (article_dir / "article.xml").write_text(
        '<article><front><article-meta><title-group><article-title>Rare cardiac presentation</article-title></title-group>'
        '<abstract><p>Abstract text.</p></abstract></article-meta></front>'
        '<body><sec><title>Case presentation</title><p>Patient presented with chest pain.</p></sec></body></article>',
        encoding="utf-8")
    (article_dir / "meta.json").write_text(json.dumps({"pmcid": "PMC123", "title": "Rare cardiac presentation",
        "year": "2024", "license_status": "unknown_requires_manual_review"}), encoding="utf-8")
    result = ingest_specialty_harvest(repo, tmp_path / "harvest")
    assert result == {"articles_seen": 1, "articles_added": 1, "articles_failed": 0}
    found = repo.search("chest pain")
    assert found and found[0]["review_status"] == "harvested"
    assert found[0]["specialty"] == "cardiology"


def test_external_file_extractors_support_csv_json_and_docx(tmp_path: Path):
    import io
    import zipfile
    from backend.hsptl_core.ucks_files import extract_text

    csv_text, csv_meta = extract_text("labs.csv", b"test,value\nHb,12\n")
    assert "Hb | 12" in csv_text and csv_meta["row_count"] == 2
    json_text, json_meta = extract_text("dataset.json", b'{"cohort": [{"age": 42}]}')
    assert '"age": 42' in json_text and json_meta["record_count"] == 1
    docx_buffer = io.BytesIO()
    document_xml = (b'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    b'<w:body><w:p><w:r><w:t>Clinical summary</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(docx_buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    docx_text, docx_meta = extract_text("summary.docx", docx_buffer.getvalue())
    assert docx_text == "Clinical summary" and docx_meta["format"] == "docx"


def test_external_file_extractor_rejects_unsupported_and_oversized_files():
    from backend.hsptl_core.ucks_files import extract_text, MAX_FILE_BYTES
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("macro.xlsm", b"not executable")
    with pytest.raises(ValueError, match="20 MB"):
        extract_text("large.txt", b"x" * (MAX_FILE_BYTES + 1))


def test_ucks_embedding_index_and_vector_search_with_provider_contract(tmp_path: Path):
    from backend.hsptl_core.ucks_embeddings import cosine

    class FakeProvider:
        name = "test-provider"
        model = "test-model"
        def embed(self, texts):
            return [[1.0, 0.0] if "renal" in text.lower() else [0.0, 1.0] for text in texts]

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-vectors.sqlite3"))
    source = repo.register_source(name="Vector test", source_type="external_import")
    repo.ingest_document(source_id=source["id"], title="Renal medicine", body="Renal function and creatinine.")
    repo.ingest_document(source_id=source["id"], title="Respiratory medicine", body="Airway and lung function.")
    provider = FakeProvider()
    assert repo.index_embeddings(provider, limit=10)["indexed"] == 2
    results = repo.vector_search("renal disease", provider)
    assert results[0]["title"] == "Renal medicine"
    assert repo.stats()["vector_status"] == "available"
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)


def test_workspace_retrieval_is_scoped_and_preserves_review_status(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-workspaces.sqlite3"))
    source = repo.register_source(name="Evidence source", source_type="external_import")
    clinic = repo.ingest_document(
        source_id=source["id"], title="Acute kidney injury case report",
        body="Acute kidney injury with oliguria and raised creatinine.",
        content_type="case_report", specialty="nephrology", jurisdiction="UK",
        review_status="reviewed", provenance={"pmid": "12345"})
    repo.ingest_document(
        source_id=source["id"], title="Renal guideline",
        body="Renal guideline for acute kidney injury and creatinine monitoring.",
        content_type="guideline", specialty="nephrology", review_status="rejected")
    lab_results = repo.workspace_retrieve("lab", "acute kidney injury creatinine", specialty="nephrology")
    assert lab_results
    assert all(item["content_type"] in repo.WORKSPACE_CONTENT_TYPES["lab"] for item in lab_results)
    assert all(item["review_status"] != "rejected" for item in lab_results)
    assert any(item["document_id"] == clinic["id"] and item["evidence_status"] == "reviewed"
               and item["jurisdiction"] == "UK" and item["provenance"].get("pmid") == "12345"
               for item in lab_results)
    assert repo.workspace_retrieve("lab", "acute kidney injury creatinine", jurisdiction="US") == []
    portfolio = repo.workspace_retrieve("portfolio", "acute kidney injury creatinine")
    assert any(item["review_status"] == "rejected" for item in portfolio)
    assert repo.workspace_retrieve("clinic", "acute kidney injury", review_status="validated") == []


def test_workspace_hybrid_retrieval_fuses_lexical_and_vector_results(tmp_path: Path):
    class FakeProvider:
        name = "test-provider"
        model = "test-model"
        def embed(self, texts):
            return [[1.0, 0.0] if "renal" in text.lower() else [0.0, 1.0] for text in texts]

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-hybrid.sqlite3"))
    source = repo.register_source(name="Hybrid source", source_type="external_import")
    repo.ingest_document(source_id=source["id"], title="Renal clinical case",
                         body="Renal presentation with a subtle clinical pattern.",
                         content_type="case_report")
    repo.ingest_document(source_id=source["id"], title="Respiratory case",
                         body="Airway and lung presentation.", content_type="case_report")
    provider = FakeProvider()
    repo.index_embeddings(provider)
    results = repo.workspace_retrieve("clinic", "renal presentation", provider=provider)
    assert results[0]["title"] == "Renal clinical case"
    assert set(results[0]["retrieval_methods"]) == {"full_text", "vector"}
    assert results[0]["is_validated"] is False


def test_workspace_retrieval_rejects_unknown_workspace(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-invalid-workspace.sqlite3"))
    with pytest.raises(ValueError, match="Unsupported UCKS workspace"):
        repo.workspace_retrieve("textbook", "clinical query")


def test_rejected_content_cannot_be_requested_in_learning_workspaces(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-rejected-filter.sqlite3"))
    source = repo.register_source(name="Review source", source_type="external_import")
    repo.ingest_document(source_id=source["id"], title="Rejected diagnostic case",
                         body="Diagnostic case with troponin and chest pain.",
                         content_type="case_report", review_status="rejected")
    assert repo.workspace_retrieve("clinic", "troponin chest pain", review_status="rejected") == []
    assert repo.workspace_retrieve("portfolio", "troponin chest pain", review_status="rejected")


def test_rss_atom_feed_parser_and_url_validation():
    from backend.hsptl_core.ucks_feeds import parse_feed, validate_feed_url
    import pytest
    payload = b'''<rss version="2.0"><channel><item><title>New guideline</title><link>https://example.org/guideline</link><guid>g-1</guid><pubDate>2026-11-01</pubDate><description>Guidance for acute care.</description></item></channel></rss>'''
    entries = parse_feed(payload)
    assert entries == [{"title": "New guideline", "body": "Guidance for acute care.",
                        "url": "https://example.org/guideline", "external_id": "g-1",
                        "publication_date": "2026-11-01", "category": ""}]
    assert validate_feed_url("https://example.org/feed") == "https://example.org/feed"
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        validate_feed_url("file:///etc/passwd")


def test_feed_state_persists_conditional_request_metadata(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-feed.sqlite3"))
    source = repo.register_source(name="Feed", source_type="online_feed", locator="https://example.org/rss")
    repo.update_feed_state(source["id"], etag='"v1"', last_modified="Wed, 19 Nov 2026 05:00:00 GMT", status="ok")
    state = repo.feed_state(source["id"])
    assert state["etag"] == '"v1"'
    assert state["last_status"] == "ok"
    assert repo.stats()["online_feeds"] == 1


def test_ucks_document_revision_and_retraction_lifecycle(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-lifecycle.sqlite3"))
    source = repo.register_source(name="Guideline feed", source_type="online_feed")
    doc = repo.ingest_document(source_id=source["id"], title="AKI guidance",
        body="Initial guidance discusses renal monitoring.", content_type="guideline",
        external_id="guideline-1")
    revised = repo.revise_document(doc["id"], title="AKI guidance updated",
        body="Updated guidance discusses renal monitoring and fluid balance.")
    assert revised["current_version"] == 2
    assert repo.stats()["versions"] == 2
    assert repo.search("fluid balance")
    repo.set_lifecycle_state(doc["id"], "retracted")
    assert repo.workspace_retrieve("ward", "fluid balance") == []
    assert repo.lifecycle_queue()[0]["lifecycle_state"] == "retracted"


def test_ucks_rejects_invalid_supersession(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-supersession.sqlite3"))
    source = repo.register_source(name="Feed", source_type="online_feed")
    doc = repo.ingest_document(source_id=source["id"], title="Guidance",
        body="Evidence text.", content_type="guideline")
    with pytest.raises(ValueError, match="Unsupported lifecycle state"):
        repo.set_lifecycle_state(doc["id"], "withdrawn")


def test_ucks_knowledge_graph_relationships_are_traceable(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-graph.sqlite3"))
    source = repo.register_source(name="Graph evidence", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Pneumonia case",
        body="Fever and cough investigated by chest radiography.", content_type="case_report")
    condition = repo.upsert_graph_node(label="Pneumonia", node_type="condition",
        terminology_system="SNOMED-CT", terminology_code="233604007")
    symptom = repo.upsert_graph_node(label="Fever", node_type="symptom")
    edge = repo.add_graph_edge(subject_id=condition["id"], predicate="presents_with",
        object_id=symptom["id"], document_id=doc["id"], evidence_note="Linked from an imported case; not independently validated")
    graph = repo.graph_neighbours(condition["id"], depth=1)
    assert edge["document_id"] == doc["id"]
    assert {n["label"] for n in graph["nodes"]} == {"Pneumonia", "Fever"}
    assert graph["edges"][0]["predicate"] == "presents_with"
    assert repo.stats()["knowledge_graph_edges"] == 1


def test_ucks_graph_rejects_untyped_or_unsupported_relationships(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-graph-validation.sqlite3"))
    a = repo.upsert_graph_node(label="Chest pain", node_type="symptom")
    b = repo.upsert_graph_node(label="ECG", node_type="investigation")
    with pytest.raises(ValueError, match="Unsupported relationship"):
        repo.add_graph_edge(subject_id=a["id"], predicate="proves", object_id=b["id"])
    with pytest.raises(ValueError, match="supported node_type"):
        repo.upsert_graph_node(label="Unknown", node_type="random")



def test_clinical_entity_extraction_creates_review_proposals_not_graph_nodes(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-entities.sqlite3"))
    source = repo.register_source(name="Entity source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="AKI case",
        body="The patient presented with fever and oliguria. Serum creatinine was elevated.",
        content_type="case_report")
    result = propose_document_entities(repo, doc["id"])
    assert result["mentions_seen"] >= 3
    proposals = list_proposals(repo, document_id=doc["id"])
    assert {p["normalized_label"] for p in proposals} >= {"fever", "oliguria", "serum creatinine"}
    with repo.store.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ucks_graph_nodes").fetchone()[0] == 0


def test_entity_proposal_review_accepts_node_without_inferred_edges(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals, review_proposal

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-entity-review.sqlite3"))
    source = repo.register_source(name="Review entity source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Chest pain assessment",
        body="Chest pain was reported. ECG was performed.", content_type="case_report")
    propose_document_entities(repo, doc["id"])
    proposal = list_proposals(repo, document_id=doc["id"])[0]
    accepted = review_proposal(repo, proposal["id"], "accept")
    assert accepted["status"] == "accepted" and accepted["graph_node_id"].startswith("node_")
    with repo.store.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ucks_graph_nodes").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ucks_graph_edges").fetchone()[0] == 0


def test_entity_extractor_marks_simple_negation_and_is_idempotent(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-entity-negation.sqlite3"))
    source = repo.register_source(name="Negation source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Review",
        body="No fever. Patient has cough.", content_type="clinical_note")
    first = propose_document_entities(repo, doc["id"])
    second = propose_document_entities(repo, doc["id"])
    proposals = list_proposals(repo, document_id=doc["id"])
    assert first["proposals_added"] == 2 and second["proposals_added"] == 0
    assert {p["normalized_label"]: p["polarity"] for p in proposals} == {"fever": "absent", "cough": "present"}


def test_explicit_relationship_extraction_requires_human_review_and_accepted_nodes(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals, review_proposal
    from backend.hsptl_core.ucks_relationships import (
        propose_document_relationships, list_relationship_proposals, review_relationship_proposal,
    )

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-relationships.sqlite3"))
    source = repo.register_source(name="Relationship source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="AKI presentation",
        body="Acute kidney injury presented with oliguria.", content_type="case_report")
    propose_document_entities(repo, doc["id"])
    result = propose_document_relationships(repo, doc["id"])
    assert result["relationships_seen"] == 1 and result["proposals_added"] == 1
    relation = list_relationship_proposals(repo, document_id=doc["id"])[0]
    assert relation["predicate"] == "presents_with"
    with pytest.raises(ValueError, match="Accept both linked entity"):
        review_relationship_proposal(repo, relation["id"], "accept")
    for proposal in list_proposals(repo, document_id=doc["id"]):
        review_proposal(repo, proposal["id"], "accept")
    accepted = review_relationship_proposal(repo, relation["id"], "accept")
    assert accepted["status"] == "accepted" and accepted["graph_edge_id"].startswith("ke_")
    with repo.store.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ucks_graph_edges").fetchone()[0] == 1


def test_relationship_extractor_marks_negated_and_uncertain_and_is_idempotent(tmp_path: Path):
    from backend.hsptl_core.ucks_relationships import (
        propose_document_relationships, list_relationship_proposals, review_relationship_proposal,
    )

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-rel-assertion.sqlite3"))
    source = repo.register_source(name="Assertion source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Relationship assertions",
        body=("Acute kidney injury is not associated with oliguria. "
              "Acute kidney injury may present with hypotension."), content_type="reference_document")
    first = propose_document_relationships(repo, doc["id"])
    second = propose_document_relationships(repo, doc["id"])
    proposals = list_relationship_proposals(repo, document_id=doc["id"])
    assert first["proposals_added"] == 2 and second["proposals_added"] == 0
    assert {p["assertion_status"] for p in proposals} == {"negated", "uncertain"}
    for proposal in proposals:
        with pytest.raises(ValueError, match="Only asserted"):
            review_relationship_proposal(repo, proposal["id"], "accept")
    with repo.store.transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ucks_graph_edges").fetchone()[0] == 0


def test_ucks_relationship_api_routes_are_registered():
    from backend.main import app
    paths = registered_api_paths(app)
    assert "/api/ucks/documents/{document_id}/relationships/extract" in paths
    assert "/api/ucks/relationships/proposals" in paths
    assert "/api/ucks/relationships/proposals/{proposal_id}/review" in paths


def test_ucks_terminology_catalogue_requires_provenance_and_two_stage_review(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals, review_proposal
    from backend.hsptl_core.ucks_terminology import (
        import_catalogue, list_catalogue, review_catalogue_concept,
        propose_entity_mappings, list_mapping_candidates, review_mapping_candidate,
    )

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-terminology.sqlite3"))
    source = repo.register_source(name="Terminology case", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Creatinine result",
        body="Serum creatinine was elevated.", content_type="clinical_note")
    propose_document_entities(repo, doc["id"])
    entity = next(p for p in list_proposals(repo, document_id=doc["id"]) if p["normalized_label"] == "serum creatinine")

    imported = import_catalogue(repo, [{
        "system": "LOINC", "code": "LOINC-EXAMPLE-001", "display": "Serum creatinine",
        "aliases": ["serum creatinine"], "version": "local-test-release", "publisher": "Test publisher",
        "source_url": "https://example.org/loinc", "licence": "Test-only licence",
        "reuse_permitted": True, "jurisdiction": "global",
    }], import_name="test terminology import", source_reference="test fixture")
    assert imported["records_added"] == 1
    concept = list_catalogue(repo, system="LOINC", status="unreviewed")[0]
    propose_entity_mappings(repo, document_id=doc["id"], system="LOINC")
    candidate = list_mapping_candidates(repo, document_id=doc["id"])[0]
    assert candidate["match_method"] == "exact_alias" and candidate["match_score"] == 1.0
    with pytest.raises(ValueError, match="Approve the terminology catalogue"):
        review_mapping_candidate(repo, candidate["id"], "accept")
    review_catalogue_concept(repo, concept["id"], "approve")
    review_proposal(repo, entity["id"], "accept")
    mapped = review_mapping_candidate(repo, candidate["id"], "accept")
    assert mapped["review_status"] == "accepted"
    with repo.store.transaction() as conn:
        node = conn.execute("SELECT terminology_system,terminology_code FROM ucks_graph_nodes WHERE label='serum creatinine'").fetchone()
        assert tuple(node) == ("LOINC", "LOINC-EXAMPLE-001")


def test_ucks_terminology_matching_is_exact_and_requires_supported_system(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities
    from backend.hsptl_core.ucks_terminology import import_catalogue, propose_entity_mappings

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-terminology-exact.sqlite3"))
    source = repo.register_source(name="Exact terminology case", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Clinical note",
        body="The patient had chest pain.", content_type="clinical_note")
    propose_document_entities(repo, doc["id"])
    with pytest.raises(ValueError, match="Unsupported terminology system"):
        import_catalogue(repo, [{"system": "MadeUp", "code": "1", "display": "Chest pain",
            "version": "v1", "publisher": "x", "licence": "x"}], import_name="bad")
    import_catalogue(repo, [{"system": "SNOMEDCT", "code": "TEST-CP", "display": "Thoracic discomfort",
        "aliases": ["thoracic discomfort"], "version": "v1", "publisher": "Test publisher",
        "licence": "Test-only licence"}], import_name="no exact alias")
    result = propose_entity_mappings(repo, document_id=doc["id"])
    assert result["candidates_added"] == 0


def test_ucks_terminology_routes_are_registered():
    from backend.main import app
    paths = registered_api_paths(app)
    assert "/api/ucks/terminology/catalogue/import" in paths
    assert "/api/ucks/terminology/catalogue/{concept_id}/review" in paths
    assert "/api/ucks/terminology/mappings/propose" in paths
    assert "/api/ucks/terminology/mappings/candidates/{candidate_id}/review" in paths


def test_ucks_terminology_release_records_are_immutable_and_reuse_gated(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities
    from backend.hsptl_core.ucks_terminology import import_catalogue, propose_entity_mappings

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-terminology-rights.sqlite3"))
    source = repo.register_source(name="Rights source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Fever note",
        body="The patient reported fever.", content_type="clinical_note")
    propose_document_entities(repo, doc["id"])
    record = {"system": "SNOMEDCT", "code": "TEST-FEVER", "display": "Fever",
        "aliases": ["fever"], "version": "release-1", "publisher": "Test publisher",
        "licence": "Restricted test licence", "reuse_permitted": False}
    import_catalogue(repo, [record], import_name="restricted fixture")
    assert propose_entity_mappings(repo, document_id=doc["id"])["candidates_added"] == 0
    changed = dict(record, display="Pyrexia")
    with pytest.raises(ValueError, match="immutable within a release"):
        import_catalogue(repo, [changed], import_name="mutated fixture")


def test_ucks_terminology_graph_expansion_retrieves_linked_evidence(tmp_path: Path):
    from backend.hsptl_core.ucks_entities import propose_document_entities, list_proposals, review_proposal
    from backend.hsptl_core.ucks_terminology import (
        import_catalogue, list_catalogue, review_catalogue_concept,
        propose_entity_mappings, list_mapping_candidates, review_mapping_candidate,
    )

    repo = UCKSRepository(StudyStore(tmp_path / "ucks-graph-retrieval.sqlite3"))
    source = repo.register_source(name="Terminology retrieval", source_type="external_import")
    seed = repo.ingest_document(source_id=source["id"], title="Creatinine case",
        body="Serum creatinine was elevated.", content_type="case_report", review_status="reviewed")
    linked = repo.ingest_document(source_id=source["id"], title="Renal monitoring case",
        body="Renal function monitoring was described.", content_type="case_report", review_status="reviewed")
    propose_document_entities(repo, seed["id"])
    entity = next(p for p in list_proposals(repo, document_id=seed["id"])
                  if p["normalized_label"] == "serum creatinine")
    import_catalogue(repo, [{"system": "LOINC", "code": "TEST-CREAT", "display": "Serum creatinine",
        "aliases": ["serum creatinine"], "version": "test-v1", "publisher": "Test publisher",
        "source_url": "https://example.org/catalogue", "licence": "Test licence",
        "reuse_permitted": True}], import_name="retrieval test")
    concept = list_catalogue(repo, system="LOINC", status="unreviewed")[0]
    propose_entity_mappings(repo, document_id=seed["id"], system="LOINC")
    candidate = list_mapping_candidates(repo, document_id=seed["id"])[0]
    review_catalogue_concept(repo, concept["id"], "approve")
    review_proposal(repo, entity["id"], "accept")
    review_mapping_candidate(repo, candidate["id"], "accept")

    mapped = repo.search_graph_nodes("serum creatinine")[0]
    renal = repo.upsert_graph_node(label="renal function", node_type="finding")
    repo.add_graph_edge(subject_id=mapped["id"], predicate="investigated_by",
        object_id=renal["id"], document_id=linked["id"], evidence_note="Explicitly linked in the imported source")

    expansion = repo.terminology_graph_expansion("creatinine", system="LOINC")
    assert "serum creatinine" in expansion["expanded_terms"]
    assert "renal function" in expansion["expanded_terms"]
    results = repo.workspace_retrieve("clinic", "creatinine", terminology_system="LOINC")
    assert any(item["document_id"] == linked["id"] for item in results)
    linked_result = next(item for item in results if item["document_id"] == linked["id"])
    assert linked_result["graph_evidence"][0]["evidence_note"] == "Explicitly linked in the imported source"
    assert repo.graph_search("creatinine")


def test_ucks_terminology_graph_expansion_excludes_unapproved_catalogue(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-graph-unapproved.sqlite3"))
    source = repo.register_source(name="Unapproved terminology", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Chest pain", body="Chest pain was reported.",
                               content_type="case_report")
    node = repo.upsert_graph_node(label="chest pain", node_type="symptom",
                                  terminology_system="SNOMEDCT", terminology_code="TEST-CP")
    from backend.hsptl_core.ucks_terminology import import_catalogue
    import_catalogue(repo, [{"system": "SNOMEDCT", "code": "TEST-CP", "display": "Chest pain",
        "version": "test-v1", "publisher": "Test publisher", "licence": "Test licence",
        "reuse_permitted": True}], import_name="unapproved test")
    assert repo.terminology_graph_expansion("chest pain")["expanded_terms"] == []


def test_ucks_terminology_retrieval_routes_are_registered():
    from backend.main import app
    paths = registered_api_paths(app)
    assert "/api/ucks/terminology/expand" in paths
    assert "/api/ucks/graph/search" in paths


def test_feed_scheduler_requires_explicit_opt_in_and_claims_due_sources(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-feed-scheduler.sqlite3"))
    manual = repo.register_source(name="Manual feed", source_type="online_feed",
                                  locator="https://example.org/feed.xml")
    automatic = repo.register_source(name="Scheduled feed", source_type="online_feed",
                                     locator="https://example.org/atom.xml",
                                     config={"auto_sync": True, "sync_interval_minutes": 30})
    assert repo.feed_schedule(manual["id"])["enabled"] == 0
    assert repo.feed_schedule(automatic["id"])["enabled"] == 1
    claimed = repo.claim_due_feeds()
    assert claimed == [automatic["id"]]
    assert repo.claim_due_feeds() == []  # lease prevents duplicate concurrent execution


def test_feed_scheduler_backoff_health_and_audit(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-feed-backoff.sqlite3"))
    source = repo.register_source(name="Scheduled feed", source_type="online_feed",
                                  locator="https://example.org/feed.xml",
                                  config={"auto_sync": True, "sync_interval_minutes": 15})
    claimed = repo.claim_due_feeds()
    assert claimed == [source["id"]]
    schedule = repo.complete_feed_schedule(source["id"], outcome="error",
                                           error="temporary upstream failure", duration_ms=123)
    assert schedule["consecutive_failures"] == 1
    assert schedule["lease_until"] == ""
    assert schedule["next_run"]
    audit = repo.feed_audit(source_id=source["id"])
    assert len(audit) == 1
    assert audit[0]["outcome"] == "error"
    assert audit[0]["error"] == "temporary upstream failure"
    health = repo.feed_health()
    assert health[0]["consecutive_failures"] == 1
    assert health[0]["schedule_enabled"] == 1


def test_feed_scheduler_configuration_bounds_interval_and_can_disable(tmp_path: Path):
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-feed-config.sqlite3"))
    source = repo.register_source(name="Feed", source_type="online_feed",
                                  locator="https://example.org/feed.xml")
    configured = repo.configure_feed_schedule(source["id"], enabled=True, interval_minutes=1)
    assert configured["interval_minutes"] == 15
    disabled = repo.configure_feed_schedule(source["id"], enabled=False, interval_minutes=60)
    assert disabled["enabled"] == 0
    assert disabled["next_run"] == ""
    assert repo.claim_due_feeds() == []


def test_ucks_structured_evidence_appraisal_keeps_domains_separate(tmp_path: Path):
    from backend.hsptl_core.ucks_evidence import save_appraisal, get_appraisal
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-evidence-appraisal.sqlite3"))
    source = repo.register_source(name="Evidence source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Trial report", body="Randomized trial report.", content_type="trial")
    saved = save_appraisal(repo, doc["id"], {"study_design": "randomized_trial", "sample_size": 240,
        "risk_of_bias": "some_concerns", "certainty": "not_assessed", "status": "reviewed"})
    assert saved["study_design"] == "randomized_trial"
    assert saved["sample_size"] == 240
    assert saved["risk_of_bias"] == "some_concerns"
    assert saved["certainty"] == "not_assessed"
    assert get_appraisal(repo, doc["id"])["status"] == "reviewed"


def test_ucks_potential_disagreement_requires_accepted_assertions_and_human_review(tmp_path: Path):
    from backend.hsptl_core.ucks_evidence import detect_assertion_disagreements, list_disagreements, review_disagreement
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-disagreement.sqlite3"))
    source = repo.register_source(name="Evidence source", source_type="external_import")
    a = repo.ingest_document(source_id=source["id"], title="Report A", body="Pneumonia present.", content_type="case_report")
    b = repo.ingest_document(source_id=source["id"], title="Report B", body="No pneumonia.", content_type="case_report")
    with repo.store.transaction() as conn:
        conn.execute("INSERT INTO ucks_entity_proposals (id,document_id,surface,normalized_label,entity_type,polarity,context,status,extraction_method,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("ea",a["id"],"pneumonia","pneumonia","condition","present","Pneumonia present.","accepted","test", "2026-01-01T00:00:00+00:00"))
        conn.execute("INSERT INTO ucks_entity_proposals (id,document_id,surface,normalized_label,entity_type,polarity,context,status,extraction_method,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("eb",b["id"],"pneumonia","pneumonia","condition","absent","No pneumonia.","accepted","test", "2026-01-01T00:00:00+00:00"))
    result = detect_assertion_disagreements(repo, a["id"])
    assert result["created"] == 1
    flag = list_disagreements(repo)[0]
    assert flag["status"] == "pending"
    assert "Potential assertion disagreement" in result["notice"]
    reviewed = review_disagreement(repo, flag["id"], "dismiss", reviewer="reviewer", note="Different populations")
    assert reviewed["status"] == "dismissed"


def test_ucks_evidence_routes_registered():
    from backend.main import app
    paths = registered_api_paths(app)
    assert "/api/ucks/documents/{document_id}/evidence-appraisal" in paths
    assert "/api/ucks/evidence-disagreements" in paths


def test_specialty_harvest_imports_metadata_abstract_records_without_full_text(tmp_path: Path):
    import json
    from backend.hsptl_core.ucks_ingestion import ingest_specialty_harvest
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-metadata-harvest.sqlite3"))
    record_dir = tmp_path / "harvest" / "cardiology" / "pmid_98765"
    record_dir.mkdir(parents=True)
    (record_dir / "meta.json").write_text(json.dumps({
        "pmid": "98765", "title": "Clinical cardiology guideline",
        "abstractText": "Abstract available; full text not acquired.", "year": "2025",
        "content_type": "guideline", "publication_type": "Guideline",
        "knowledge_profile": "guidelines", "full_text_available": False,
    }), encoding="utf-8")
    result = ingest_specialty_harvest(repo, tmp_path / "harvest")
    assert result == {"articles_seen": 1, "articles_added": 1, "articles_failed": 0}
    found = repo.search("Clinical cardiology guideline", limit=5)
    assert found
    assert found[0]["content_type"] == "guideline"


def test_ucks_rights_review_requires_reviewer_and_preserves_audit_history(tmp_path: Path):
    from backend.hsptl_core.ucks_rights import review_rights, list_rights_reviews
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-rights-review.sqlite3"))
    source = repo.register_source(name="Rights source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Open article", body="Article text", content_type="case_report")
    import pytest
    with pytest.raises(ValueError):
        review_rights(repo, doc["id"], {"decision": "permitted", "licence": "CC BY 4.0", "reviewer": ""})
    with pytest.raises(ValueError):
        review_rights(repo, doc["id"], {"decision": "permitted", "reviewer": "Reviewer"})
    first = review_rights(repo, doc["id"], {"decision": "permitted", "licence": "CC BY 4.0", "scope": "full_text_reuse", "reviewer": "Reviewer A", "attribution": "Author and source"})
    second = review_rights(repo, doc["id"], {"decision": "restricted", "scope": "metadata_only", "reviewer": "Reviewer B", "rationale": "Licence does not permit adaptation"})
    assert first["decision"] == "permitted" and second["decision"] == "restricted"
    assert len(list_rights_reviews(repo, doc["id"])) == 2


def test_ucks_appraisal_updates_preserve_previous_snapshot(tmp_path: Path):
    from backend.hsptl_core.ucks_evidence import save_appraisal, list_appraisal_history
    repo = UCKSRepository(StudyStore(tmp_path / "ucks-appraisal-history.sqlite3"))
    source = repo.register_source(name="Evidence source", source_type="external_import")
    doc = repo.ingest_document(source_id=source["id"], title="Trial", body="Trial text", content_type="trial")
    save_appraisal(repo, doc["id"], {"study_design": "randomized_trial", "risk_of_bias": "low"})
    save_appraisal(repo, doc["id"], {"study_design": "randomized_trial", "risk_of_bias": "some_concerns"})
    history = list_appraisal_history(repo, doc["id"])
    assert len(history) == 1
    assert history[0]["snapshot"]["risk_of_bias"] == "low"


def test_ucks_reviewer_identity_is_server_configured_and_token_authenticated(monkeypatch):
    from fastapi import HTTPException
    from backend.routers.ucks import _authenticated_reviewer
    import pytest
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "Clinical Governance Lead")
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "x" * 40)
    assert _authenticated_reviewer("x" * 40) == "Clinical Governance Lead"
    with pytest.raises(HTTPException) as denied:
        _authenticated_reviewer("incorrect")
    assert denied.value.status_code == 401
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "short")
    with pytest.raises(HTTPException) as unavailable:
        _authenticated_reviewer("short")
    assert unavailable.value.status_code == 503


def test_ucks_governance_write_routes_enforce_configured_reviewer(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.routers.ucks import REPO
    monkeypatch.setenv("HSPTL_REVIEWER_ID", "Authenticated Reviewer")
    monkeypatch.setenv("HSPTL_REVIEWER_TOKEN", "test-reviewer-token-01234567890123456789")
    source = REPO.register_source(name="API governance auth source", source_type="external_import")
    doc = REPO.ingest_document(source_id=source["id"], title="API governance auth test", body="A test document", content_type="reference_document")
    client = TestClient(app)
    denied = client.post(f"/api/ucks/documents/{doc['id']}/rights-reviews", json={"decision":"restricted"})
    assert denied.status_code == 401
    accepted = client.post(f"/api/ucks/documents/{doc['id']}/rights-reviews", headers={"X-HSPTL-Reviewer-Token":"test-reviewer-token-01234567890123456789"}, json={"decision":"restricted"})
    assert accepted.status_code == 201
    assert accepted.json()["reviewer"] == "Authenticated Reviewer"
    appraisal = client.put(f"/api/ucks/documents/{doc['id']}/evidence-appraisal", headers={"X-HSPTL-Reviewer-Token":"test-reviewer-token-01234567890123456789"}, json={"study_design":"cohort","status":"reviewed"})
    assert appraisal.status_code == 200
    assert appraisal.json()["reviewer"] == "Authenticated Reviewer"


def test_external_source_automation_provisions_api_key_free_profiles_idempotently(tmp_path: Path):
    from backend.hsptl_core.external_source_automation import (
        DEFAULT_EXTERNAL_PROFILES, ExternalSourceAutomation,
    )
    from backend.hsptl_core.source_registry import SourceRegistry

    store = StudyStore(tmp_path / "external-auto.sqlite3")
    repo = UCKSRepository(store)
    registry = SourceRegistry(store)
    automation = ExternalSourceAutomation(repo, registry)

    first = automation.ensure_default_sources()
    second = automation.ensure_default_sources()

    assert first["provisioned"] == len(DEFAULT_EXTERNAL_PROFILES)
    assert second["provisioned"] == 0
    assert first["api_key_required"] is False
    assert "Europe PMC only" in first["full_text_policy"]
    sources = [s for s in repo.list_sources() if s["config"].get("automation_profile")]
    assert len(sources) == len(DEFAULT_EXTERNAL_PROFILES)
    for source in sources:
        assert source["config"]["connector"] in {"europe_pmc", "pubmed", "crossref", "clinicaltrials_gov"}
        assert source["source_type"] == "external_import"
        schedule = automation.status()["profiles"]
        item = next(x for x in schedule if x["source_id"] == source["id"])
        assert item["schedule"]["enabled"] == 1
        expected_fulltext = 1 if source["config"]["connector"] == "europe_pmc" else 0
        assert item["schedule"]["include_full_text"] == expected_fulltext
        rights = registry.rights_for(source["id"])
        assert rights.reuse == "unknown"
        assert rights.adaptation == "unknown"


def test_external_source_query_templates_use_rolling_utc_dates():
    from datetime import datetime, timezone
    from backend.hsptl_core.external_source_automation import expand_query

    stamp = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
    query = expand_query("FIRST_PDATE:[{date_365d_ago} TO {today}] AND ({pubmed_365d_ago} {pubmed_today})", stamp)
    assert "FIRST_PDATE:[2025-11-21 TO 2026-11-21]" in query
    assert "2025/11/21 2026/11/21" in query


def test_external_source_automation_manual_refresh_only_queues_work(tmp_path: Path):
    from backend.hsptl_core.external_source_automation import ExternalSourceAutomation

    repo = UCKSRepository(StudyStore(tmp_path / "external-queue.sqlite3"))
    automation = ExternalSourceAutomation(repo)
    queued = automation.trigger_refresh()
    assert queued["status"] == "queued"
    assert queued["queued"] is True
    assert "without per-record approval" in queued["message"]
    assert "machine-screened" in queued["message"]


def test_external_source_automation_syncs_mocked_providers_without_per_record_approval(tmp_path: Path, monkeypatch):
    from backend.hsptl_core import ucks_connectors
    from backend.hsptl_core.external_source_automation import ExternalSourceAutomation

    repo = UCKSRepository(StudyStore(tmp_path / "external-sync.sqlite3"))
    automation = ExternalSourceAutomation(repo)
    automation.ensure_default_sources()

    def fake_fetcher(query, limit, session):
        provider = "mock:" + query[:20]
        return [{
            "external_id": provider,
            "title": provider,
            "body": "A mock external evidence record for integration testing.",
            "content_type": "other",
            "publication_date": "2026-11-21",
            "url": "https://example.invalid/record",
            "licence": "",
            "provenance": {"connector": "mock-provider"},
        }]

    for connector in tuple(ucks_connectors.CONNECTORS):
        monkeypatch.setitem(ucks_connectors._FETCHERS, connector, fake_fetcher)

    result = automation.run_once(force=True, trigger_source="test")
    assert result["status"] == "completed"
    assert result["claimed"] == 4
    assert len(result["results"]) == 4
    assert repo.stats()["documents"] == 4
    imported = repo.search("mock external evidence")
    assert len(imported) == 4
    assert all(item["review_status"] == "machine_screened" for item in imported)
    assert all(item["provenance_json"] for item in imported)
    state = automation.status()
    assert state["status"] == "completed"
    assert state["automatic_import_enabled"] is True
    assert state["human_approval_required_for_import"] is False
    assert state["clinical_validity_assessed_automatically"] is False
    assert state["reuse_rights_granted_automatically"] is False
    assert state["auto_approve"] is False
    assert state["auto_publish"] is True
    assert state["publication_status"] == "provisional"
