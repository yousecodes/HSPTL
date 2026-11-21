"""UCKS API: additive endpoints for the unified clinical knowledge foundation."""
from __future__ import annotations

from typing import Any
import hmac
import os
from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
import requests
import time
from ..hsptl_core.ucks_feeds import parse_feed, validate_feed_url, MAX_FEED_BYTES

from ..runtime import STORE, SOURCE_REGISTRY
from ..hsptl_core.ucks_monitoring import governance_snapshot
from ..hsptl_core.ucks import UCKSRepository
from ..hsptl_core.external_source_automation import ExternalSourceAutomation
from ..hsptl_core.ucks_files import extract_text, MAX_FILE_BYTES
from ..hsptl_core.ucks_entities import propose_document_entities, list_proposals, review_proposal
from ..hsptl_core.ucks_relationships import (propose_document_relationships, list_relationship_proposals, review_relationship_proposal)
from ..hsptl_core.ucks_terminology import (import_catalogue, list_catalogue, review_catalogue_concept, propose_entity_mappings, list_mapping_candidates, review_mapping_candidate)
from ..hsptl_core.ucks_evidence import (save_appraisal, get_appraisal, list_appraisal_history, detect_assertion_disagreements, list_disagreements, review_disagreement)
from ..hsptl_core.ucks_rights import review_rights, list_rights_reviews
from ..hsptl_core.ucks_surveillance import (initialise_surveillance, detect_feed_change, list_change_events, review_change_event, scan_staleness, list_staleness_flags, review_staleness_flag)
from ..hsptl_core.ucks_connectors import (sync_connector, list_connector_runs, configure_connector_schedule, get_connector_schedule, run_due_connectors, get_connector_checkpoint, find_identifier_matches, list_document_identifiers)

router = APIRouter(prefix="/api/ucks", tags=["UCKS"])
REPO = UCKSRepository(STORE)
EXTERNAL_AUTOMATION = ExternalSourceAutomation(REPO, SOURCE_REGISTRY)
initialise_surveillance(STORE)


class SourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source_type: str
    locator: str = Field(default="", max_length=2000)
    licence: str = Field(default="", max_length=300)
    reuse_permitted: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class FeedScheduleUpdate(BaseModel):
    enabled: bool
    interval_minutes: int = Field(default=360, ge=15, le=10080)


class DocumentIngest(BaseModel):
    source_id: str
    title: str = Field(min_length=2, max_length=500)
    body: str = Field(min_length=1, max_length=2_000_000)
    content_type: str = "other"
    external_id: str = Field(default="", max_length=500)
    specialty: str = Field(default="", max_length=120)
    jurisdiction: str = Field(default="", max_length=120)
    publication_date: str = Field(default="", max_length=40)
    source_url: str = Field(default="", max_length=2000)
    licence: str = Field(default="", max_length=300)
    provenance: dict[str, Any] = Field(default_factory=dict)


@router.get("/automation/status")
def external_automation_status():
    return EXTERNAL_AUTOMATION.status()


@router.post("/automation/refresh")
def refresh_external_sources():
    return EXTERNAL_AUTOMATION.trigger_refresh()


@router.get("/status")
def status():
    return {"system": "UCKS", "version": 1, "status": "foundation_available",
            "ai_models_enabled": False, "embedding_inference_enabled": False,
            "retrieval_default": "sqlite_fts5_lexical", "legacy_vector_rows_used_by_product": False,
            "capabilities": ["source_registry", "document_versioning", "clinical_chunking",
                             "provenance", "full_text_search", "lexical_workspace_retrieval",
                             "mednotegen_auto_ingestion", "specialty_harvest_auto_ingestion", "external_file_ingestion_pdf_docx_csv_json_text", "six_workspace_retrieval_profiles", "registered_rss_atom_feed_sync", "review_first_clinical_entity_proposals", "explicit_pattern_relationship_proposals", "provenance_bearing_terminology_catalogue", "exact_alias_mapping_candidates", "human_reviewed_terminology_mapping", "scheduled_feed_orchestration", "feed_retry_backoff", "feed_health_and_audit", "structured_evidence_appraisal", "potential_assertion_disagreement_review", "publisher_change_surveillance_proposals", "guideline_age_surveillance", "europe_pmc_connector", "pubmed_connector", "crossref_metadata_connector", "clinicaltrials_gov_connector", "licence_gated_europe_pmc_full_text", "immutable_connector_document_revisions", "scheduled_metadata_connector_sync", "connector_job_leases_and_retry_backoff", "cross_provider_clinical_identifier_index", "non_destructive_pmid_pmcid_doi_nct_reconciliation",
                             "clinical_knowledge_harvester_profiles", "provider_health_monitoring", "ucks_governance_monitoring",
                             "built_in_api_key_free_external_source_profiles", "local_background_external_source_scheduler",
                             "startup_and_manual_external_source_refresh", "external_source_automation_status_and_audit"],
            "limitations": ["model_based_embeddings_and_vector_retrieval_disabled_in_model_free_4_0", "managed_sources_walk_up_to_10_pages_per_scheduled_run_and_resume_provider_cursors_until_the_query_is_exhausted", "provider_pagination_does_not_guarantee_a_stable_snapshot_while_the_remote_corpus_is_changing", "provider_updated_date_watermarks_and_full_corpus_reconciliation_are_not_yet_implemented", "administrator_can_disable_managed_source_or_pause_its_schedule",
                            "ocr_for_scanned_pdfs_not_configured", 
                            "entity_extraction_is_curated_lexicon_proposal_only_not_clinical_nlp",
                            "terminology_catalogue_is_empty_until_licensed_source_data_is_imported",
                            "terminology_matching_is_exact_alias_only_and_requires_two_stage_human_review",
                            "no_live_terminology_server_connection_or_automatic_code_lookup_is_configured",
                            "terminology_expansion_requires_approved_reusable_catalogue_concepts_and_reviewed_graph_mappings",
                            "relationship_extraction_is_narrow_explicit_pattern_matching_not_clinical_nlp",
                            "negated_or_uncertain_relationships_are_not_promoted_to_graph_edges", "evidence_appraisal_does_not_generate_a_quality_score_or_grade_certainty", "assertion_disagreement_detection_is_not_contradiction_detection", "explicit_pubmed_and_europe_pmc_retraction_designations_are_auto_quarantined_but_other_publisher_change_signals_require_confirmation", "age_flags_do_not_prove_guideline_is_outdated", "managed_external_connector_records_are_machine_screened_not_clinically_validated_and_rights_remain_separate", "full_text_acquisition_is_opt_in_and_restricted_to_allow_listed_cc_licences", "connector_updates_create_immutable_revisions_and_remain_harvested", "broad_harvester_profiles_initially_use_europe_pmc", "provider_health_probes_measure_reachability_not_data_completeness"]}


@router.get("/stats")
def stats():
    result = REPO.stats()
    # Preserve historical row counts, but never describe vector search as a
    # supported product capability in the model-free 4.0 HTTP application.
    result["legacy_embedding_rows"] = result.pop("embeddings", 0)
    result["vector_status"] = "disabled_model_free"
    result["retrieval_modes"] = ["full_text"]
    result["embedding_inference_enabled"] = False
    return result


@router.get("/sources")
def sources():
    return {"items": REPO.list_sources()}


@router.post("/sources", status_code=201)
def create_source(payload: SourceCreate):
    try:
        return REPO.register_source(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents", status_code=201)
def ingest_document(payload: DocumentIngest):
    try:
        return REPO.ingest_document(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/search")
def search(q: str = "", limit: int = 10, mode: str = "full_text"):
    if mode != "full_text":
        raise HTTPException(status_code=409, detail={
            "state": "abstain", "reason": "HSPTL 4.0 is model-free; vector retrieval is disabled.",
            "supported_mode": "full_text"})
    return {"mode": "full_text", "items": REPO.search(q, limit)}


@router.post("/embeddings/index")
def index_embeddings():
    raise HTTPException(status_code=409, detail={
        "state": "abstain", "reason": "HSPTL 4.0 does not load or execute embedding models.",
        "alternative": "Use deterministic SQLite FTS5 lexical retrieval."})


@router.post("/sources/{source_id}/files", status_code=201)
async def ingest_file(source_id: str, file: UploadFile = File(...)):
    source = REPO.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="UCKS source not found")
    content = await file.read(MAX_FILE_BYTES + 1)
    try:
        body, extraction = extract_text(file.filename or "upload", content)
        if not body:
            raise ValueError("No extractable text was found; scanned PDFs require OCR before import")
        title = (file.filename or "Imported document").rsplit(".", 1)[0][:500]
        result = REPO.ingest_document(
            source_id=source_id, title=title, body=body, content_type="reference_document",
            external_id=f"upload:{file.filename or 'unnamed'}:{__import__('hashlib').sha256(content).hexdigest()}",
            licence=source.get("licence", ""),
            provenance={"filename": file.filename or "", "media_type": file.content_type or "",
                        "file_size_bytes": len(content), "extraction": extraction,
                        "reuse_permission": "inherited_from_source; verify_before_redistribution"},
            review_status="harvested")
        return {"document": result, "extraction": extraction, "text_characters": len(body)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()


@router.get("/workspaces")
def workspace_profiles():
    return {"items": {
        "clinic": "Diagnostic cases and evidence",
        "rounds": "Case-based examination and report retrieval",
        "lab": "Diagnostic and investigation evidence",
        "ward": "Management and longitudinal care evidence",
        "exam_hall": "Evidence for high-yield learning and assessment",
        "portfolio": "All content, including rejected records, for governance review",
    }}


@router.get("/retrieve/{workspace}")
def retrieve_workspace(workspace: str, q: str, limit: int = 10, specialty: str = "",
                       jurisdiction: str = "", review_status: str = "",
                       mode: str = "full_text", terminology_system: str = ""):
    if mode != "full_text":
        raise HTTPException(status_code=409, detail={
            "state": "abstain", "reason": "HSPTL 4.0 supports deterministic lexical retrieval only.",
            "supported_mode": "full_text"})
    try:
        items = REPO.workspace_retrieve(workspace, q, limit=limit, specialty=specialty,
                                        jurisdiction=jurisdiction, review_status=review_status,
                                        provider=None, terminology_system=terminology_system)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"workspace": workspace, "requested_mode": "full_text", "actual_mode": "full_text",
            "items": items,
            "clinical_notice": "Search relevance is not evidence quality, clinical validity, or a patient-specific recommendation. Check source, review status, jurisdiction, date and context."}



def _perform_feed_sync(source_id: str) -> dict[str, Any]:
    source = REPO.get_source(source_id)
    if source is None:
        raise ValueError("UCKS source not found")
    if source.get("source_type") != "online_feed":
        raise ValueError("Only online_feed sources can be synchronised")
    url = validate_feed_url(source.get("locator", ""))
    state = REPO.feed_state(source_id)
    headers = {"User-Agent": "HSPTL-UCKS/1.0 (clinical knowledge feed importer)"}
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    if state.get("last_modified"):
        headers["If-Modified-Since"] = state["last_modified"]
    response = requests.get(url, headers=headers, timeout=(5, 20), stream=True,
                            allow_redirects=False)
    if response.status_code == 304:
        REPO.update_feed_state(source_id, etag=state.get("etag", ""),
                               last_modified=state.get("last_modified", ""), status="not_modified")
        return {"source_id": source_id, "status": "not_modified", "seen": 0, "added": 0}
    response.raise_for_status()
    chunks, size = [], 0
    for part in response.iter_content(65536):
        size += len(part)
        if size > MAX_FEED_BYTES:
            raise ValueError("Feed exceeds the 2 MB import limit")
        chunks.append(part)
    entries = parse_feed(b"".join(chunks))
    added = 0
    change_signals = 0
    for entry in entries:
        change_event = detect_feed_change(STORE, source_id, entry)
        change_signals += int(bool(change_event))
        if change_event:
            # Publisher notices are governance signals, not teaching documents.
            continue
        result = REPO.ingest_document(
            source_id=source_id, title=entry["title"], body=entry["body"],
            content_type="other", external_id=entry["external_id"],
            publication_date=entry["publication_date"], source_url=entry["url"],
            licence=source.get("licence", ""),
            provenance={"feed_url": url, "feed_category": entry["category"],
                        "ingestion_method": "rss_atom", "reuse_permission": "verify_before_redistribution"},
            review_status="harvested")
        added += int(bool(result.get("created")))
    REPO.update_feed_state(source_id, etag=response.headers.get("ETag", ""),
                           last_modified=response.headers.get("Last-Modified", ""), status="ok")
    return {"source_id": source_id, "status": "ok", "seen": len(entries), "added": added, "change_signals": change_signals}


@router.post("/sources/{source_id}/sync", status_code=200)
def sync_online_feed(source_id: str):
    started = time.monotonic()
    try:
        result = _perform_feed_sync(source_id)
        schedule = REPO.feed_schedule(source_id)
        if schedule.get("enabled"):
            REPO.complete_feed_schedule(source_id, outcome=result["status"],
                records_seen=result["seen"], records_added=result["added"],
                duration_ms=int((time.monotonic()-started)*1000))
        return result
    except (ValueError, requests.RequestException) as exc:
        REPO.update_feed_state(source_id, status="error", error=str(exc))
        schedule = REPO.feed_schedule(source_id)
        if schedule.get("enabled"):
            REPO.complete_feed_schedule(source_id, outcome="error", error=str(exc),
                duration_ms=int((time.monotonic()-started)*1000))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/sources/{source_id}/schedule")
def update_feed_schedule(source_id: str, payload: FeedScheduleUpdate):
    try:
        return REPO.configure_feed_schedule(source_id, enabled=payload.enabled,
                                             interval_minutes=payload.interval_minutes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scheduler/health")
def feed_scheduler_health(limit: int = 100):
    return {"items": REPO.feed_health(limit=limit), "audit": REPO.feed_audit(limit=20),
            "scheduler_mode": "externally_triggered_opt_in",
            "notice": "Feeds run only when explicitly enabled and this endpoint is triggered by a trusted local scheduler."}


@router.get("/scheduler/audit")
def feed_scheduler_audit(source_id: str = "", limit: int = 100):
    return {"items": REPO.feed_audit(source_id=source_id, limit=limit)}


@router.post("/scheduler/run-due")
def run_due_feed_sync(limit: int = 20):
    claimed = REPO.claim_due_feeds(limit=limit)
    results = []
    for source_id in claimed:
        started = time.monotonic()
        try:
            result = _perform_feed_sync(source_id)
            REPO.complete_feed_schedule(source_id, outcome=result["status"],
                records_seen=result["seen"], records_added=result["added"],
                duration_ms=int((time.monotonic()-started)*1000))
            results.append(result)
        except (ValueError, requests.RequestException) as exc:
            REPO.update_feed_state(source_id, status="error", error=str(exc))
            REPO.complete_feed_schedule(source_id, outcome="error", error=str(exc),
                duration_ms=int((time.monotonic()-started)*1000))
            results.append({"source_id": source_id, "status": "error", "error": str(exc)[:500]})
    return {"claimed": len(claimed), "results": results,
            "notice": "Imported records remain harvested; this job does not validate clinical content or reuse rights."}



@router.post("/documents/{document_id}/revise")
def revise_document(document_id: str, payload: dict):
    try:
        result = REPO.revise_document(document_id, title=str(payload.get("title", "")),
                                      body=str(payload.get("body", "")),
                                      provenance=payload.get("provenance"))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/{document_id}/lifecycle")
def update_document_lifecycle(document_id: str, payload: dict):
    try:
        return REPO.set_lifecycle_state(document_id, str(payload.get("state", "")),
                                        superseding_document_id=str(payload.get("superseding_document_id", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/lifecycle")
def lifecycle_queue(limit: int = 100):
    return {"items": REPO.lifecycle_queue(limit=limit)}
@router.get("/documents/{document_id}")
def document(document_id: str):
    result = REPO.get_document(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="UCKS document not found")
    return result


class GraphNodeCreate(BaseModel):
    label: str = Field(min_length=1, max_length=300)
    node_type: str
    terminology_system: str = ""
    terminology_code: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeCreate(BaseModel):
    subject_id: str
    predicate: str
    object_id: str
    document_id: str = ""
    evidence_note: str = Field(default="", max_length=1000)


@router.post("/graph/nodes", status_code=201)
def create_graph_node(payload: GraphNodeCreate):
    try:
        return REPO.upsert_graph_node(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/graph/nodes")
def search_graph_nodes(q: str, limit: int = 20):
    return {"items": REPO.search_graph_nodes(q, limit=limit)}


@router.post("/graph/edges", status_code=201)
def create_graph_edge(payload: GraphEdgeCreate):
    try:
        return REPO.add_graph_edge(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/graph/nodes/{node_id}/neighbours")
def graph_neighbours(node_id: str, depth: int = 1, limit: int = 100):
    try:
        return REPO.graph_neighbours(node_id, depth=depth, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class EntityReview(BaseModel):
    decision: str


@router.post("/documents/{document_id}/entities/extract")
def extract_document_entities(document_id: str):
    try:
        return propose_document_entities(REPO, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/entities/proposals")
def entity_proposals(status: str = "pending", document_id: str = "", limit: int = 100):
    try:
        return {"items": list_proposals(REPO, status=status, document_id=document_id, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/entities/proposals/{proposal_id}/review")
def review_entity_proposal(proposal_id: str, payload: EntityReview):
    try:
        return review_proposal(REPO, proposal_id, payload.decision)
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/documents/{document_id}/relationships/extract")
def extract_document_relationships(document_id: str):
    try:
        return propose_document_relationships(REPO, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/relationships/proposals")
def relationship_proposals(status: str = "pending", document_id: str = "", limit: int = 100):
    try:
        return {"items": list_relationship_proposals(REPO, status=status, document_id=document_id, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/relationships/proposals/{proposal_id}/review")
def review_relationship(proposal_id: str, payload: EntityReview):
    try:
        return review_relationship_proposal(REPO, proposal_id, payload.decision)
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


class TerminologyCatalogueImport(BaseModel):
    import_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(default="", max_length=1000)
    records: list[dict[str, Any]] = Field(min_length=1, max_length=50000)


@router.get("/terminology/expand")
def expand_terminology_query(q: str, system: str = ""):
    try:
        return REPO.terminology_graph_expansion(q, system=system)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/graph/search")
def search_terminology_graph(q: str, limit: int = 20):
    return {"items": REPO.graph_search(q, limit=limit),
            "notice": "Graph associations are source-linked knowledge records, not proof of causality or patient-specific guidance."}


@router.post("/terminology/catalogue/import", status_code=201)
def import_terminology_catalogue(payload: TerminologyCatalogueImport):
    try:
        return import_catalogue(REPO, payload.records, import_name=payload.import_name,
                                source_reference=payload.source_reference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/terminology/catalogue")
def terminology_catalogue(system: str = "", status: str = "all", limit: int = 100):
    try:
        return {"items": list_catalogue(REPO, system=system, status=status, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/terminology/catalogue/{concept_id}/review")
def review_terminology_concept(concept_id: str, payload: EntityReview):
    try:
        return review_catalogue_concept(REPO, concept_id, payload.decision)
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.post("/terminology/mappings/propose")
def propose_terminology_mappings(document_id: str = "", system: str = ""):
    try:
        return propose_entity_mappings(REPO, document_id=document_id, system=system)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/terminology/mappings/candidates")
def terminology_mapping_candidates(status: str = "pending", document_id: str = "", limit: int = 100):
    try:
        return {"items": list_mapping_candidates(REPO, status=status, document_id=document_id, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/terminology/mappings/candidates/{candidate_id}/review")
def review_terminology_mapping(candidate_id: str, payload: EntityReview):
    try:
        return review_mapping_candidate(REPO, candidate_id, payload.decision)
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


class EvidenceAppraisal(BaseModel):
    study_design: str = "not_reported"
    sample_size: int | None = Field(default=None, ge=0)
    population: str = ""
    setting: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: str = ""
    risk_of_bias: str = "not_assessed"
    imprecision: str = "not_assessed"
    inconsistency: str = "not_assessed"
    indirectness: str = "not_assessed"
    publication_bias: str = "not_assessed"
    limitations: str = ""
    funding: str = ""
    guideline_issuer: str = ""
    recommendation_text: str = ""
    recommendation_strength: str = "not_reported"
    certainty: str = "not_assessed"
    jurisdiction: str = ""
    publication_date: str = ""
    reviewer: str = ""
    status: str = "draft"


@router.put("/documents/{document_id}/evidence-appraisal")
def put_evidence_appraisal(document_id: str, payload: EvidenceAppraisal, x_hsptl_reviewer_token: str | None = Header(default=None)):
    reviewer = _authenticated_reviewer(x_hsptl_reviewer_token)
    try:
        return save_appraisal(REPO, document_id, {**payload.model_dump(), "reviewer": reviewer})
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/documents/{document_id}/evidence-appraisal")
def read_evidence_appraisal(document_id: str):
    if REPO.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="UCKS document not found")
    return get_appraisal(REPO, document_id)


@router.post("/documents/{document_id}/evidence-disagreements/detect")
def detect_document_disagreements(document_id: str):
    try:
        return detect_assertion_disagreements(REPO, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evidence-disagreements")
def evidence_disagreements(status: str = "pending", limit: int = 100):
    try:
        return {"items": list_disagreements(REPO, status=status, limit=limit)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class DisagreementReview(BaseModel):
    decision: str
    reviewer: str = ""
    note: str = ""


@router.post("/evidence-disagreements/{flag_id}/review")
def review_evidence_disagreement(flag_id: str, payload: DisagreementReview):
    try:
        return review_disagreement(REPO, flag_id, payload.decision, payload.reviewer, payload.note)
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/surveillance/source-changes")
def source_change_queue(status: str = "pending", limit: int = 100):
    return {"items": list_change_events(STORE, status=status, limit=limit)}


@router.post("/surveillance/source-changes/{event_id}/review")
def source_change_review(event_id: str, payload: dict):
    try:
        return review_change_event(STORE, REPO, event_id, str(payload.get("decision", "")),
                                   str(payload.get("note", "")), str(payload.get("replacement_document_id", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/surveillance/staleness/scan")
def run_staleness_scan(payload: dict):
    return scan_staleness(STORE, int(payload.get("max_age_days", 1095)),
                          str(payload.get("content_type", "guideline")))


@router.get("/surveillance/staleness")
def staleness_queue(status: str = "pending", limit: int = 100):
    return {"items": list_staleness_flags(STORE, status=status, limit=limit)}


@router.post("/surveillance/staleness/{flag_id}/review")
def staleness_review(flag_id: str, payload: dict):
    try:
        return review_staleness_flag(STORE, flag_id, str(payload.get("decision", "")), str(payload.get("note", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class ConnectorSyncRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=25, ge=1, le=100)
    include_full_text: bool = False


@router.post("/sources/{source_id}/connectors/sync")
def connector_sync(source_id: str, payload: ConnectorSyncRequest):
    try:
        return sync_connector(REPO, source_id, payload.query, payload.limit, include_full_text=payload.include_full_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"External source request failed: {type(exc).__name__}") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=502, detail="External source returned an invalid response") from exc


@router.get("/connectors/runs")
def connector_runs(source_id: str = "", limit: int = 50):
    return {"items": list_connector_runs(REPO, source_id=source_id, limit=limit)}


class ConnectorScheduleUpdate(BaseModel):
    enabled: bool
    query: str = Field(min_length=1, max_length=500)
    interval_minutes: int = Field(default=360, ge=15, le=10080)
    limit: int = Field(default=25, ge=1, le=100)
    include_full_text: bool = False


@router.put("/sources/{source_id}/connectors/schedule")
def connector_schedule_update(source_id: str, payload: ConnectorScheduleUpdate):
    try:
        return configure_connector_schedule(REPO, source_id, enabled=payload.enabled,
            query=payload.query, interval_minutes=payload.interval_minutes,
            result_limit=payload.limit, include_full_text=payload.include_full_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/connectors/schedules")
def connector_schedules(source_id: str = ""):
    return {"items": get_connector_schedule(REPO, source_id) if source_id else get_connector_schedule(REPO)}


@router.post("/connectors/run-due")
def connector_run_due(limit: int = 20):
    return run_due_connectors(REPO, limit=limit)


@router.get("/connectors/checkpoint")
def connector_checkpoint(source_id: str, query: str):
    try:
        return {"checkpoint": get_connector_checkpoint(REPO, source_id, query)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/identifiers/lookup")
def connector_identifier_lookup(identifier_type: str, identifier_value: str):
    try:
        return {"identifier_type": identifier_type, "identifier_value": identifier_value,
                "matches": find_identifier_matches(REPO, identifier_type, identifier_value)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents/{document_id}/identifiers")
def connector_document_identifiers(document_id: str):
    if not REPO.get_document(document_id):
        raise HTTPException(status_code=404, detail="UCKS document not found")
    return {"document_id": document_id, "identifiers": list_document_identifiers(REPO, document_id)}


@router.get("/governance/monitoring")
def governance_monitoring(limit: int = 20):
    return governance_snapshot(STORE, REPO, limit=limit)


class RightsReview(BaseModel):
    decision: str
    licence: str = Field(default="", max_length=300)
    licence_uri: str = Field(default="", max_length=2000)
    attribution: str = Field(default="", max_length=2000)
    scope: str = "metadata_only"
    evidence_reference: str = Field(default="", max_length=2000)
    rationale: str = Field(default="", max_length=4000)


def _authenticated_reviewer(token: str | None) -> str:
    expected = os.environ.get("HSPTL_REVIEWER_TOKEN", "")
    reviewer = os.environ.get("HSPTL_REVIEWER_ID", "").strip()
    if len(expected) < 32 or not reviewer:
        raise HTTPException(status_code=503, detail="Reviewer authentication is not configured. Set HSPTL_REVIEWER_TOKEN (32+ characters) and HSPTL_REVIEWER_ID before enabling governance decisions.")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Valid reviewer credentials are required")
    return reviewer[:160]


@router.get("/reviewer/status")
def reviewer_status():
    configured = len(os.environ.get("HSPTL_REVIEWER_TOKEN", "")) >= 32 and bool(os.environ.get("HSPTL_REVIEWER_ID", "").strip())
    return {"configured": configured, "reviewer_id": os.environ.get("HSPTL_REVIEWER_ID", "").strip() if configured else "", "authentication": "bearer-token"}


@router.post("/documents/{document_id}/rights-reviews", status_code=201)
def create_rights_review(document_id: str, payload: RightsReview, x_hsptl_reviewer_token: str | None = Header(default=None)):
    reviewer = _authenticated_reviewer(x_hsptl_reviewer_token)
    try:
        return review_rights(REPO, document_id, {**payload.model_dump(), "reviewer": reviewer})
    except ValueError as exc:
        code = 404 if str(exc).startswith("Unknown") else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc


@router.get("/documents/{document_id}/rights-reviews")
def read_rights_reviews(document_id: str):
    if REPO.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="UCKS document not found")
    return {"items": list_rights_reviews(REPO, document_id)}


@router.get("/documents/{document_id}/evidence-appraisal/history")
def evidence_appraisal_history(document_id: str, limit: int = 50):
    if REPO.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail="UCKS document not found")
    return {"items": list_appraisal_history(REPO, document_id, limit)}
