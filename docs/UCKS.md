# UCKS — Unified Clinical Knowledge System

## Status
External file ingestion, lexical FTS5 retrieval, online-feed scheduling and review-first knowledge graph proposals are implemented in the existing UCKS foundation. In HSPTL 4.0 the application is strictly model-free: embedding indexing and vector retrieval are disabled at the HTTP boundary. Historical embedding schema/data are retained for non-destructive compatibility and are not queried by the product runtime.

## Architecture
UCKS is additive and local-first. Existing HSPTL tables remain authoritative for their current workflows. UCKS adds:
- `ucks_sources`: registered source systems and reuse permissions.
- `ucks_documents`: canonical document metadata, source provenance and review state.
- `ucks_document_versions`: immutable body snapshots.
- `ucks_chunks`: heading-aware, bounded text chunks.
- `ucks_chunks_fts`: SQLite FTS5 lexical retrieval.
- `ucks_embeddings`: legacy vector payload schema retained for compatibility only; HSPTL 4.0 ignores these rows.
- `ucks_ingestion_jobs`: ingestion execution audit records.

External user-supplied PDF, DOCX, CSV, TSV, JSON, JSONL, Markdown and TXT files can be uploaded through a registered source. Text extraction is bounded to 20 MB per file; scanned PDFs without a text layer require OCR and are rejected when no text can be extracted. Macro-enabled/active formats are not supported. Extracted data is stored as source-linked reference documents, not silently transformed into validated datasets.

Existing MedNoteGen and Specialty Harvester jobs now automatically pass their outputs into UCKS. MedNoteGen cases are stored as `synthetic_case` and retain synthetic provenance. Pearl seeds remain draft learning seeds. Harvested JATS articles retain source metadata and article-level rights fields; all remain unreviewed, and the adapter deliberately does not assume that open access grants redistribution rights.

## API
- `GET /api/ucks/status`
- `GET /api/ucks/stats`
- `GET /api/ucks/sources`
- `POST /api/ucks/sources`
- `POST /api/ucks/documents`
- `GET /api/ucks/documents/{document_id}`
- `GET /api/ucks/search?q=...&limit=...&mode=full_text` (other modes return an explicit model-free abstention)
- `POST /api/ucks/sources/{source_id}/files` (multipart file upload)
- `POST /api/ucks/embeddings/index` (compatibility endpoint; returns an explicit model-free abstention)

Imported records default to `harvested`. The ingestion API explicitly prevents imported content from self-promoting to `validated`. Validation remains a separate review action.

## Source types
The registry accepts `clinical_harvester`, `synthea_mednotegen`, `external_import`, and `online_feed`. The MedNoteGen and Specialty Harvester source types have working adapters invoked by their existing background jobs. External file ingestion is available for the supported text-bearing formats above. Structured CSV/TSV and JSON content is retained as extracted text with row/record counts in provenance; it is not yet normalised into typed clinical tables. Online-feed scheduling remains a subsequent increment.

## Model-free retrieval in HSPTL 4.0

HSPTL 4.0 uses deterministic SQLite FTS5 lexical retrieval and workspace-aware filters. It does not import, load or call Sentence Transformers, neural embedding models, LLMs or other AI/ML inference components. `mode=vector`, `mode=hybrid` and the embedding-index endpoint are closed with an explicit abstention response. The `ucks_embeddings` table and low-level compatibility helpers remain so an upgraded 3.0 database can be opened without destructive migration; stored rows are not used by the product HTTP/UI. The repository retains an explicit provider-injection seam for migration tests and trusted external code, but the application never configures one. The local Sentence Transformers provider class is a disabled sentinel and always raises an explicit model-free runtime error.


## Safety and governance
- Record licence and reuse permissions; free-to-read is not equivalent to permission to redistribute.
- Keep synthetic content explicitly labelled and traceable to its synthetic source.
- Preserve original source IDs, URLs, licence, and provenance.
- Keep harvested, reviewed, validated, and rejected states distinct.
- Do not treat retrieval rank as evidence quality or clinical recommendation.
- Do not ingest identifiable patient data without an approved governance basis.

## Remaining work
- Publisher correction/retraction detection and reconciliation against existing records.
- Typed clinical dataset normalisation and OCR for scanned documents.
- Broader clinical NLP, terminology reconciliation and graph quality review.
- Frontend governance and retrieval interfaces across the six workspaces.
- Full Windows release verification and frontend build before production release.

## Workspace-aware retrieval (Increment 4)

UCKS exposes retrieval profiles for Clinic, Rounds, Lab, Ward, Exam Hall and
Portfolio. `GET /api/ucks/retrieve/{workspace}?q=...` applies workspace-specific
content-type filters, optional specialty/jurisdiction/review-state filters and
workspace-filtered lexical FTS5 results. Vector rank fusion is disabled in
HSPTL 4.0 because the runtime does not execute embedding models.

Learning workspaces exclude rejected records even if a caller requests that
review state. Portfolio is the governance surface and can inspect rejected
records. Returned items preserve their original review state and include
`evidence_status` and `is_validated`; retrieval never changes review state.
The lexical retrieval score is a relevance-ranking aid only, not a measure of evidence
quality, clinical validity, or patient-specific applicability. Consumers must
show source, publication date, licence and review state, and must not present
harvested content as validated guidance.

Workspace profiles are discoverable at `GET /api/ucks/workspaces`.

## Registered online feeds

UCKS supports manual synchronisation and opt-in scheduled synchronisation of
registered RSS/Atom feeds. Register a source with `source_type=online_feed` and
an absolute HTTP(S) feed locator. Scheduling can be enabled in source config or
through `PUT /api/ucks/sources/{source_id}/schedule`. The periodic runner uses
database leases, ETag and Last-Modified conditional requests, a 2 MB payload
limit, source enablement checks, exponential retry backoff and an append-only
run audit. A trusted local periodic trigger is required; see the Increment 12
section below. Entries remain `harvested`. Feed entries are not clinical
recommendations; licences and redistribution rights require independent review.
Publisher correction/retraction detection is not yet implemented.


## Evidence lifecycle and document revisions

UCKS stores document lifecycle independently from clinical review status.
`current`, `superseded`, `corrected`, and `retracted` are lifecycle states;
they do not imply clinical validation. Revised content is stored as a new
immutable document version, with new chunks and full-text entries. Existing
versions remain available for audit. Workspace retrieval excludes superseded
and retracted records; Portfolio can inspect them through the lifecycle queue.

API:
- `POST /api/ucks/documents/{id}/revise` with `title`, `body`, optional `provenance`.
- `POST /api/ucks/documents/{id}/lifecycle` with `state` and optional
  `superseding_document_id`.
- `GET /api/ucks/lifecycle` for non-current records.

Lifecycle changes require an authorised administrative workflow in production.
This increment supplies the API and repository safeguards; authentication and
role enforcement must be verified against the deployment's existing security
configuration before enabling remote administrative access. Feed sync currently
does not automatically infer corrections or retractions from publisher notices.

## Clinical knowledge graph (Increment 7)

UCKS now provides an explicit, provenance-linked graph registry. Nodes use a
controlled type vocabulary (conditions, symptoms, findings, investigations,
treatments, drugs, procedures, complications, specialties, anatomy, organisms,
cases and evidence). Edges use a controlled predicate vocabulary such as
`presents_with`, `investigated_by`, `treated_with`, `complicated_by`,
`differential_for` and `supported_by`. Each edge may cite a UCKS document and
carry an explanatory evidence note. The graph does not infer relationships
from text automatically and does not treat a graph edge as validated merely
because it exists; automated entity extraction, terminology reconciliation
and clinical review are subsequent work.

API:
- `POST /api/ucks/graph/nodes` to create or update a typed node.
- `GET /api/ucks/graph/nodes?q=...` to search labels.
- `POST /api/ucks/graph/edges` to add a controlled, optionally evidence-linked relation.
- `GET /api/ucks/graph/nodes/{id}/neighbours?depth=1&limit=100` to inspect a bounded neighbourhood (maximum depth 3).

Graph counts are included in UCKS statistics. Terminology identifiers are
stored as supplied; the system does not claim that codes have been externally
validated or that terminology mappings are complete.


## Clinical entity extraction (Increment 8)

UCKS now includes a conservative, deterministic starter extractor in
`backend/hsptl_core/ucks_entities.py`. It recognises a small curated set of
conditions, symptoms, findings, investigations and treatments, then stores
mentions in `ucks_entity_proposals` with source document/chunk, context,
simple present/absent polarity, terminology-system placeholder and extraction
method. Terminology codes are intentionally blank unless explicitly curated;
the extractor does not claim authoritative SNOMED CT, LOINC or RxNorm mapping.

Endpoints:
- `POST /api/ucks/documents/{document_id}/entities/extract`
- `GET /api/ucks/entities/proposals?status=pending&document_id=...`
- `POST /api/ucks/entities/proposals/{proposal_id}/review` with `accept` or `reject`

Only an explicit reviewer acceptance creates a graph node. Acceptance does not
create graph edges, infer causality, validate the source document, or change its
review status. Rejected and pending proposals remain auditable. Re-running
extraction is idempotent for the same document, mention and context.

This is a lexical proof-of-function, not a clinical NLP system. Negation handling
is intentionally simple and does not resolve temporality, experiencer, family
history, uncertainty, section context, dosage, or complex linguistic scope.
It must not be used for autonomous diagnosis, treatment selection or patient
record coding. Terminology server integration, comprehensive concept mapping,
human review UI and richer NLP remain future work.

## Explicit clinical relationship proposals (Increment 9)

A second review-first layer can propose a limited set of relationships when an
explicit phrase connects two recognised lexicon mentions in the same sentence:
`presents_with`, `treated_with`, `investigated_by`, and `complicated_by`.
Each proposal retains its document, chunk when matched, sentence context,
extraction method, and assertion status (`asserted`, `negated`, or `uncertain`).
This is deterministic phrase matching, not dependency parsing or clinical NLP;
no relation is proposed merely because two concepts co-occur in a document.

Endpoints:
- `POST /api/ucks/documents/{document_id}/relationships/extract`
- `GET /api/ucks/relationships/proposals?status=pending&document_id=...`
- `POST /api/ucks/relationships/proposals/{proposal_id}/review` with `accept` or `reject`

A reviewer can accept an asserted relationship only after both linked entity
proposals have independently been accepted into the graph. Negated and uncertain
proposals cannot be promoted to graph edges by this workflow. The evidence
sentence is retained on the edge. These safeguards do not establish clinical
truth: human review remains mandatory, and the source document's review status
is not changed. Pattern coverage and assertion-scope detection are limited;
complex negation, temporality, experiencer, cross-sentence relations, and
causality are not resolved.

## Terminology catalogue and reviewed mappings (Increment 10)

UCKS now provides a local terminology catalogue for SNOMED CT (`SNOMEDCT`),
LOINC, ICD-10-CM (`ICD10CM`) and RxNorm. It is deliberately empty until an
operator imports source records with a release/version, publisher, licence,
source reference and jurisdiction. No codes or terminology records are seeded
from guesses. Import does not establish that the source licence permits onward
redistribution; that permission is recorded separately.

Mapping candidates are generated only from exact normalised display/alias
matches. The numeric score `1.0` denotes exact lexical equality only; it is not
clinical confidence, equivalence, or evidence quality. Candidates remain
pending. A terminology concept must first be explicitly approved, then its
entity mapping must separately be accepted. Accepted mappings update the
reviewed entity proposal and, if its graph node already exists, attach the
terminology identifier to that node. Rejected entity proposals cannot be mapped.

Endpoints:
- `POST /api/ucks/terminology/catalogue/import` imports provenance-bearing
  records (`import_name`, optional `source_reference`, and `records`).
- `GET /api/ucks/terminology/catalogue?system=LOINC&status=unreviewed`
- `POST /api/ucks/terminology/catalogue/{concept_id}/review` with `approve` or `reject`.
- `POST /api/ucks/terminology/mappings/propose?document_id=...&system=...`
- `GET /api/ucks/terminology/mappings/candidates?status=pending&document_id=...`
- `POST /api/ucks/terminology/mappings/candidates/{candidate_id}/review` with
  `accept` or `reject`.

The current implementation is a local catalogue/import adapter and exact-alias
matcher. It does not connect to live SNOMED CT, LOINC, ICD-10-CM or RxNorm
servers, download terminology releases, perform fuzzy mapping, or guarantee
licence compliance. Operators must obtain and import data under the applicable
publisher terms. Human review remains required before a code is attached to a
graph concept. Authentication/role enforcement for these review endpoints
must be verified before deployment in a multi-user environment.

### Terminology-aware retrieval (Increment 11)

Workspace retrieval can now expand a query through terminology mappings only when
both the terminology catalogue concept is approved and reusable and the graph node
has that reviewed system/code mapping. Expansion follows one-hop, source-linked
graph relationships; it does not treat co-occurrence as a relationship. The
retrieval response labels expanded terms and returns graph evidence attached to
the retrieved document. This supplements, rather than replaces, lexical/vector
retrieval and does not change document review or validation status.

`GET /api/ucks/retrieve/{workspace}` accepts optional `terminology_system`.
`GET /api/ucks/terminology/expand?q=...` previews approved mapped concept and
graph expansion. `GET /api/ucks/graph/search?q=...` returns terminology-linked
graph context. Graph associations are retrieval context, not proof of causality,
clinical validity or patient-specific advice. Expansion is limited to one graph
hop and the supported local catalogue; no live terminology server is configured.

## Scheduled online-feed orchestration (Increment 12)

RSS/Atom sources remain manual by default. Scheduling is opt-in per source:

- Register an `online_feed` source with `config.auto_sync=true` and optional
  `config.sync_interval_minutes` (15–10,080; default 360), or configure it later
  through `PUT /api/ucks/sources/{source_id}/schedule`.
- `POST /api/ucks/scheduler/run-due` claims due sources using a database lease,
  then synchronises them. A source disabled in the source registry is skipped.
- Failed synchronisations use exponential retry delay, capped at 24 hours.
  Successful and not-modified runs return to the configured interval.
- `GET /api/ucks/scheduler/health` reports source state; `GET
  /api/ucks/scheduler/audit` returns the append-only run audit.
- `scripts/run_ucks_scheduler.py` runs one scheduler cycle against the local API.
  Configure Windows Task Scheduler or cron to invoke it periodically. The helper
  is restricted to loopback HTTP; keep the API bound to localhost unless a
  separately secured deployment is configured.

The application does not silently start a network-polling background worker.
This is deliberate: the installed deployment must explicitly configure a trusted
periodic trigger. Imported documents remain `harvested`; scheduling does not
validate evidence, grant reuse rights, or detect publisher retractions. Publisher
correction/retraction reconciliation remains a separate implementation task.

## Increment 13 — evidence appraisal and disagreement review

UCKS stores structured evidence appraisal domains per document: study design,
sample size, population, setting, intervention/comparator/outcomes, risk-of-bias
domains, limitations, funding, guideline issuer, recommendation text/strength,
certainty, jurisdiction and reviewer metadata. Missing or unassessed fields stay
explicitly unassessed. The system does not calculate an evidence-quality score,
GRADE certainty, or recommendation strength from study design.

Accepted entity assertions with opposite present/absent polarity across documents
can generate a **potential assertion disagreement**. These are review leads, not
confirmed contradictions: population, timepoint, measurement, context and
methodological differences require expert assessment. Only accepted entity
proposals are considered, and retracted/superseded documents are excluded.
Reviewers can confirm or dismiss each flag with a note.

Endpoints:
- `PUT/GET /api/ucks/documents/{id}/evidence-appraisal`
- `POST /api/ucks/documents/{id}/evidence-disagreements/detect`
- `GET /api/ucks/evidence-disagreements`
- `POST /api/ucks/evidence-disagreements/{flag_id}/review`

This increment does not implement automated guideline retraction monitoring,
formal GRADE/Cochrane appraisal instruments, or reviewer authentication/role
enforcement. It does not alter document review status or workspace eligibility.

## Publisher-change and evidence-age surveillance

UCKS now creates review proposals from explicit publisher-feed signals for retractions, corrections/errata, expressions of concern, and guideline updates. Signals are linked to an existing document only when the feed item's external identifier or source URL matches. These signals never change a document lifecycle state automatically. Reviewers can dismiss a signal, confirm a retraction, mark a document corrected, or supersede it with a replacement document. The source-change queue is available at `GET /api/ucks/surveillance/source-changes`; review actions use `POST /api/ucks/surveillance/source-changes/{event_id}/review`.

A separate age scan can flag current guidelines older than a configurable threshold (default 1,095 days) using `POST /api/ucks/surveillance/staleness/scan`. Age flags are prompts to verify the publisher's current version, not evidence that a guideline is obsolete. Review them through `GET /api/ucks/surveillance/staleness` and `POST /api/ucks/surveillance/staleness/{flag_id}/review`. Neither scan changes lifecycle state or clinical retrieval eligibility without an explicit lifecycle review. Publisher signal matching is conservative keyword detection, not a comprehensive Crossref/PubMed/publisher retraction API integration. Authentication and reviewer-role enforcement must be verified before multi-user deployment.

### Public research connectors (Increment 15)

UCKS supports explicit, query-driven metadata synchronisation from Europe PMC,
NCBI PubMed E-utilities, Crossref REST API and ClinicalTrials.gov API v2. Create
a source with `source_type: external_import` and `config.connector` set to one of
`europe_pmc`, `pubmed`, `crossref` or `clinicaltrials_gov`, then call
`POST /api/ucks/sources/{source_id}/connectors/sync` with a query and a result
limit (maximum 100). Run history is available at `GET /api/ucks/connectors/runs`.

These adapters are metadata-first. Europe PMC and PubMed may supply abstracts;
Crossref generally supplies bibliographic metadata; ClinicalTrials.gov supplies
registry descriptions and status fields. They do not download publisher full
text. Imported records remain `harvested`; rights and clinical review are
required before any validation. A source's licence and reuse flags are not
inferred from API accessibility. Requests use HTTPS, bounded response size,
finite timeouts and do not follow redirects. Synchronisation is explicitly
invoked and is not automatically scheduled by these connectors. Run history is
recorded with per-query checkpoints. Provider-native page continuation is
implemented in Increment 19; publisher retraction reconciliation remains a
separate, review-first workflow.

### Europe PMC full-text acquisition and connector revisions

The multi-source connector sync endpoint accepts `include_full_text` (default
`false`). When enabled for a Europe PMC source, UCKS requests PMC JATS XML only
when the record has a PMCID, Europe PMC marks it open access, and the supplied
licence normalises to the conservative CC0, CC-BY or CC-BY-SA allow-list. NC,
ND, unknown and missing licences remain metadata/abstract-only. A failed or
insufficient XML extraction does not replace the existing abstract record.

Repeated connector imports with the same source and external identifier are
reconciled against the existing document. Changed content creates an immutable
new document version and re-indexed chunks instead of a second document. The
existing review and lifecycle states are preserved; connector refreshes never
promote harvested content or reactivate retracted/superseded records.


## Connector orchestration (Increment 17)

Metadata connectors (Europe PMC, PubMed, Crossref and ClinicalTrials.gov) can
be scheduled independently of RSS/Atom feeds. Scheduling is disabled by
default and requires an explicit source-level configuration:

- `PUT /api/ucks/sources/{source_id}/connectors/schedule` configures the
  query, interval (15 minutes to 7 days), result limit and optional Europe PMC
  full-text request.
- `GET /api/ucks/connectors/schedules` reports configured schedules.
- `POST /api/ucks/connectors/run-due` claims and executes due jobs.
- `POST /api/ucks/sources/{source_id}/connectors/sync` remains available for
  manual execution.
- `GET /api/ucks/connectors/runs` reports connector execution history.

Connector schedules use database-backed leases, bounded job batches and
exponential retry backoff (capped at 24 hours). A failed job records the
exception class, releases its lease and is rescheduled. The periodic helper
`scripts/run_ucks_scheduler.py` now triggers both feed and connector queues;
configure it in Windows Task Scheduler or cron. It does not create a resident
background process.

Connector APIs use bounded pages (maximum 100) and stable external identifiers
for idempotent reconciliation. Increment 19 adds provider-native page
continuation: Europe PMC `cursorMark`, PubMed E-utilities `retstart` offsets,
Crossref `offset`, and ClinicalTrials.gov API v2 `nextPageToken`. The opaque or
numeric continuation value is persisted in the source/query checkpoint only
after a successful page import. Repeated scheduler runs resume from that value;
completed page sequences are marked complete and a later scheduled cycle starts
a fresh query sequence. Checkpoints also report provider total count, page count,
page size, cumulative records seen/added and last-page time.

This is resumable query pagination, not guaranteed exhaustive historical
backfill: provider result sets can change while paging, some APIs impose
provider-side limits, and schedules do not yet apply provider-specific
updated-date watermarks or stable snapshot semantics. Cross-provider identity
reconciliation (PMID/PMCID/DOI) is not yet a canonical merge operation.
Connector changes create immutable document revisions while preserving review
and lifecycle states. Imports remain `harvested`; rights and clinical review
are still required. Full-text retrieval remains subject to the Europe PMC
licence allow-list.


## Connector checkpoint observability (Increment 18)

Successful connector sync cycles now maintain a durable checkpoint keyed by
source and a SHA-256 digest of the exact configured query. The checkpoint
records connector identity, completed sync-cycle count, cumulative records
seen/added, the last external identifier and last successful timestamp.
`GET /api/ucks/connectors/checkpoint?source_id=...&query=...` exposes the
checkpoint for monitoring and recovery diagnostics. Failed syncs do not advance
the checkpoint. Increment 19 extends this record with the provider continuation token/offset,
total result count, completed page count, page size, pagination completion
state and last-page timestamp. It now functions as a resumable page checkpoint
for the four registered metadata providers. It does not guarantee a stable
snapshot or exhaustive historical backfill when upstream result sets change.

## Cross-provider identifier reconciliation (Increment 20)

Connector-imported documents now receive a non-destructive identifier index
for DOI, PMID, PMCID and ClinicalTrials.gov NCT identifiers. DOI URL/prefix
forms are normalised to a lower-case DOI; PMID and NCT values are validated;
PMCID values are canonicalised to the `PMC` prefix. The index is additive and
retains the source/document association for every identifier occurrence.

- `GET /api/ucks/identifiers/lookup?identifier_type=doi&identifier_value=...`
  returns all matching document records across sources.
- `GET /api/ucks/documents/{document_id}/identifiers` lists identifiers indexed
  for one document.

A matching DOI/PMID/PMCID is an identity-reconciliation signal, not proof that
two source records are interchangeable. UCKS deliberately does not merge or
delete documents, collapse provenance, or transfer review/lifecycle status.
Multiple source documents can therefore appear for one identifier and require
human reconciliation. ClinicalTrials.gov NCT identifiers are indexed separately
from publication identifiers; no trial-publication relationship is inferred.
The identifier index is populated during subsequent connector syncs and does
not backfill old documents until those records are re-imported.

## Increments 28–32: rights, appraisal history and surveillance operations

- Document rights reviews are recorded as append-only decisions (`permitted`, `restricted`, `needs_clarification`) with reviewer, licence, licence URI, attribution, reuse scope, evidence reference and rationale. A permitted decision requires an explicit licence. These records are audit evidence, not legal advice and do not automatically alter document review status or grant reuse permission to other documents.
- Evidence appraisal updates preserve the prior structured appraisal as an immutable JSON snapshot. `GET /api/ucks/documents/{id}/evidence-appraisal/history` exposes bounded history. Appraisal domains remain separate; no automatic GRADE or quality score is generated.
- The loopback scheduler now performs bounded provider reachability probes after due feed and connector cycles. Provider checks use the existing fixed HTTPS allow-list, short timeouts and disabled redirects. Reachability does not establish data completeness or source reliability.
- End-to-end regression coverage exercises rights decision validation, audit history and appraisal revision history. External provider integration remains opt-in and is not exercised by offline tests.
- This remains a single-user local-first application. Reviewer identity is recorded as an asserted local reviewer label; this increment does not introduce authenticated multi-user identity or role-based access control. Do not treat a reviewer string as proof of identity.

## Authenticated governance decisions

Rights decisions and evidence-appraisal writes require a backend-configured reviewer identity and bearer token. The API derives the reviewer label from `HSPTL_REVIEWER_ID`; the client cannot submit or override that identity. The token is compared in constant time and is never returned by the status endpoint. If the token is absent/short or the reviewer ID is unset, governance writes fail closed with HTTP 503; invalid credentials return HTTP 401. Read-only governance history remains available.

For a local Windows installation, configure the variables in the same user environment that launches HSPTL (PowerShell example):

```powershell
$bytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$token = [Convert]::ToBase64String($bytes)
[Environment]::SetEnvironmentVariable('HSPTL_REVIEWER_TOKEN', $token, 'User')
[Environment]::SetEnvironmentVariable('HSPTL_REVIEWER_ID', 'Clinical Governance Reviewer', 'User')
```

Restart HSPTL after setting the variables. Keep the token private; the backend launcher binds to loopback (`127.0.0.1`). The Data Tools governance panel supports rights decisions, structured appraisal updates, and review-history inspection. A `permitted` rights decision records the licence and scope but does not silently promote clinical content to validated guidance. Appraisal `reviewed` is an appraisal workflow state, not independent clinical validation or a GRADE certainty determination.

## Continuous scheduler operation

The scheduler supports both a single-cycle invocation (for Windows Task Scheduler/cron) and an optional resident loop. On Windows, `run_ucks_scheduler.bat` starts the loop at 15-minute intervals; stop it with Ctrl+C. The Python CLI also accepts `--loop --interval-minutes N` (5–1440). Each cycle processes due feeds, due connectors and bounded provider reachability probes. Failed cycles use bounded exponential backoff. The scheduler requires the HSPTL API to be running on loopback and does not claim provider data completeness or licence validity from a successful reachability probe.

## Unified generation and distribution layer

UCKS is the ingestion and retrieval foundation; generation and distribution are
separate governed services layered above it. `backend/hsptl_core/generation_distribution.py`
provides six distinct workspace scripts (Clinic, Rounds, Lab, Ward, Exam Hall,
Portfolio), workspace-specific output contracts, persistent customization,
source-linked artifact drafts, review state, and distribution routes.

The current generator creates structured authoring packets from selected UCKS
documents. It records document IDs, titles, source URLs, licences, provenance,
review state and a content hash. It intentionally does not claim to perform
free-form clinical synthesis or generate new evidence. A future model-backed
generator must consume these packets, cite source spans, preserve uncertainty,
and remain subject to review. Rejected, retracted and superseded sources are
blocked at generation time.

Generated artifacts begin as `draft`. Only a reviewer authenticated through
`HSPTL_REVIEWER_TOKEN` and `HSPTL_REVIEWER_ID` can approve, reject or request
revision. Distribution routes can be created only for `approved` artifacts.
Routes currently represent delivery into an HSPTL workspace/section; they do
not publish to external channels. The API is under `/api/generation`,
`/api/distribution`, and `/api/workspaces`.

Workspace scripts are intentionally distinct: Clinic structures diagnosis;
Rounds structures viva and procedural examination; Lab structures result/image
interpretation and OSCE; Ward structures triage, management and continuity;
Exam Hall structures high-yield learning and assessment; Portfolio structures
governance, competency mapping and reflection. Display names, focus, tab labels,
and permitted workflow sequence overrides are stored per workspace.

## Retrieval/cache-augmented generation and workspace delivery

The Content Studio generator is fully local and deterministic; it does not call an AI model, external inference endpoint or embedding model. It retrieves eligible current UCKS chunks using a BM25-lite lexical relevance ranker, then builds output sections from verbatim source sentences. Every claim is checked against the original chunk and receives exact character offsets, document/chunk IDs and source URL. This is extractive assembly, not paraphrasing, clinical synthesis or newly generated evidence.

A persistent SQLite generation cache is keyed by workspace, output kind, title, template version and hashes of the ranked source chunks. Source corrections or changed chunk text produce a new key and naturally invalidate stale cache entries. Cache hits create a separate draft and audit event rather than reusing an earlier review decision. Rights and lifecycle eligibility are checked before retrieval; full-text reuse still requires an allowed licence or an explicit rights review. The provider status endpoint reports `retrieval_cache_extractive`, requires no API key and does not report a model.

Assessment items use source-derived recall prompts and verbatim answers; they are not clinically authored MCQs or examiner-calibrated cases. The output-specific schema and citation validation still apply. Human clinical review remains mandatory before distribution.
Distribution remains reviewer-gated. Approved artifacts are registered through the workspace distribution adapter in HSPTL's native tagged-content index, which is the shared content catalogue used by the workspace libraries. Mapping is Clinic→conference, Rounds→rounds, Lab→lab, Ward→on_call, Exam Hall→exam and Portfolio→data_tools. Delivery is internal to HSPTL; no external publication is implied. A destination-specific content type and broad workflow tag are assigned; these tags are navigation metadata, not clinical assertions. Structured `question_set`, `viva_set` and `osce_station` assessment items are additionally inserted into the native examination question bank as unreviewed items; question-bank review remains a separate human step. The tagged-content index retains the source artifact URL as the canonical citation/provenance record. Revisions require a new draft and review. Cross-workspace delivery is intentionally rejected; generate against the intended workspace.
