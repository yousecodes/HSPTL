# HSPTL 5.0.0 — Source Registry, Daily Case Lottery & Seven-Engine Integration
## Repository Implementation Directive for a Coding Agent

**Target release:** HSPTL 5.0.0  
**Baseline archive:** User-uploaded `HSPTL-5.0.0.zip`  
**Architecture:** Local-first FastAPI/React/SQLite modular monolith  
**Runtime policy:** Deterministic, model-free, no required API keys, no new deployable services  
**Primary goal:** Extend the existing UCKS, generation/distribution, case, tagging, job and HSPTL 4.0 engine infrastructure. Do not build duplicate systems.

---

# COPY THE IMPLEMENTATION DIRECTIVE BELOW INTO YOUR CODING AGENT

## 0. Role and objective

Act as a senior software architect, Python/FastAPI engineer, React/TypeScript engineer, clinical knowledge engineer, source-rights and provenance engineer, educational assessment designer, test engineer and release engineer.

Your task is to **implement**, not merely plan, the seven implementation increments described in this directive in the supplied HSPTL repository:

1. Rights-aware source registry expansion.
2. Local Folder Source Manager.
3. Shared provenance/content-origin schema and labels.
4. Daily Clinical Case Lottery.
5. Seven-core-engine integration across all HSPTL workspaces.
6. Clinical Knowledge & Pearls Factory expansion using the selected source collections and reusable open sources.
7. Cross-workspace learning analytics and learner feedback.

Inspect the actual repository before changing it. Implement in the existing application. Preserve existing data, APIs, functionality, event semantics, review lifecycles and current user settings. Do not stop after producing a plan or scaffolding.

### 0.1 Critical baseline identity check

The user-uploaded archive filename is `HSPTL-5.0.0.zip`, but its internal `RELEASE_STATUS.md` currently identifies the package as an `HSPTL 3.0.0` release candidate. Other internal documents refer to HSPTL 4.0/4.0.2. This is a release-identity inconsistency.

Before implementation:

- Inspect `RELEASE_STATUS.md`, `RELEASE_CHECKLIST.md`, `CHANGELOG.md`, `README.md`, `backend/hsptl_core/config.py`, `frontend/package.json`, `frontend/package-lock.json`, `scripts/release_identity.py`, package scripts and release metadata.
- Determine the actual code baseline from its code and migrations, not from the ZIP filename.
- Treat 5.0.0 as the requested target release, but reconcile every product/version reference consistently.
- Do not claim that the archive is already a verified 5.0.0 release.
- Preserve earlier release notes as historical records; add a new 5.0.0 release entry and exact verification results.

## 1. Repository inventory: existing capabilities to reuse

The uploaded archive already contains substantial infrastructure. Extend it instead of rebuilding it.

### 1.1 Backend and storage

Known components include:

- FastAPI backend in `backend/main.py` and `backend/routers/`.
- React/TypeScript/Vite frontend in `frontend/src/`.
- SQLite authoritative store and additive migrations in `backend/hsptl_core/store.py` and `migrations.py`.
- Durable `JobRunner` with leases, heartbeat, retry and cancellation intent in `backend/hsptl_core/jobs.py`.
- Runtime singleton wiring in `backend/runtime.py`.
- Existing canonical HSPTL event Kernel and event catalogue under `backend/hsptl_core/hsp_tl40/` and `docs/hsptl40/`.
- Existing shared tagging and tagged-content index.
- Existing profile and local single-user deployment boundaries. Do not infer a verified identity from a display name.

### 1.2 UCKS — Unified Clinical Knowledge System

Reuse `backend/hsptl_core/ucks.py`, its submodules, `backend/routers/ucks.py`, `docs/UCKS.md` and the current Data Tools UI.

The current UCKS already provides:

- `ucks_sources`, `ucks_documents`, immutable `ucks_document_versions`, heading-aware `ucks_chunks`, SQLite FTS5, and ingestion audit records.
- Source registration, external document ingestion, document retrieval and workspace-aware lexical search.
- File upload/extraction for PDF, DOCX, CSV, TSV, JSON, JSONL, Markdown and TXT, with a 20 MB bound. Unsupported active/macro formats are not supported. Scanned PDFs without an extractable text layer are rejected; OCR is not implemented.
- RSS/Atom feed registration and opt-in scheduling with leases, conditional requests and audit history.
- Metadata connectors for Europe PMC, PubMed, Crossref and ClinicalTrials.gov, including checkpoints and pagination.
- Specialty Harvester adapters for Europe PMC, PubMed, PMC OA, Crossref, DOAJ, journal catalogue and exam-curated sources.
- Article-level rights metadata, rights-review history and evidence-appraisal history.
- Document revision and lifecycle states including current, superseded, corrected and retracted.
- Source-change and staleness queues.
- Review-first clinical entity and relationship proposals.
- Local terminology catalogue and separately reviewed mappings for SNOMED CT, LOINC, ICD-10-CM and RxNorm.
- Provenance-linked knowledge graph with controlled node and edge vocabularies.
- Workspace-aware FTS5 retrieval and terminology-aware query expansion.
- A local-first, model-free retrieval boundary. Vector/embedding modes are disabled at the product HTTP boundary.

Important current limitations documented in `docs/UCKS.md`:

- Lexical retrieval rank is not evidence strength or clinical validity.
- Entity/relationship extraction is a small deterministic lexical proof-of-function, not comprehensive clinical NLP.
- Terminology mapping is exact-alias based and requires review.
- Online provider discovery does not establish reuse permission.
- Current connectors do not cover all requested content sites.
- Automatic publisher correction/retraction matching is conservative and incomplete.
- The application remains local/single-user; reviewer token workflows are not institutional identity management.

### 1.3 Existing generation and distribution layer

Reuse `backend/hsptl_core/generation_distribution.py`, `backend/hsptl_core/workspace_distribution.py`, `backend/routers/generation_distribution.py` and the existing Data Tools / Content Factory UI.

Current capabilities include:

- Six workspace scripts: Clinic, Rounds, Lab, Ward, Exam Hall and Portfolio.
- Workspace-specific generation/output contracts.
- Model-free, extractive retrieval-cache generation from eligible UCKS chunks.
- Exact source sentence/character offsets, source document/chunk IDs and source URLs.
- Versioned generated-artifact drafts and content hashes.
- Reviewer-gated approval.
- Internal distribution routes into the existing workspace/tagged-content index.
- Workspace mapping: Clinic → conference; Rounds → rounds; Lab → lab; Ward → on_call; Exam Hall → exam; Portfolio → data_tools.
- No free-form clinical synthesis and no automatic clinical publication.

Keep those properties. Do not misrepresent the current extractive composer as a generative AI or a validated medical author.

### 1.4 Existing patient/case and synthetic-data infrastructure

Reuse:

- `backend/hsptl_core/case_engine.py` and `CaseRepository` for FHIR JSON Bundle, standalone FHIR resource and NDJSON/JSONL imports.
- Stable patient/encounter identity, source-linked facts, raw resource retention and bounded batch imports.
- `backend/hsptl_core/case_quality.py` for structural sparsity/linkage/chronology flags. These are not clinical-validity certification.
- Existing MedNoteGen and Specialty Harvester tools in `backend/hsptl_tools/` and `backend/routers/data_tools.py`.
- Existing case archive, Clinic and simulation workflows.

Synthea-derived content must remain clearly synthetic. Do not reclassify a `synthetic_case` as ordinary imported or generated content.

### 1.5 Existing workspaces and seven core engines

The six presentation skins defined in `frontend/src/hsptl40/skinRegistry.ts` are:

- `clinic`
- `rounds`
- `lab`
- `ward`
- `exam`
- `portfolio`

The product navigation includes Overview/Ward Board, Learning Library, Clinic, Simulation Lab, Lab/OSCE, Exam Hall, Case Debriefs, Progress Board, Content Factory, Question Review, Rounds, Ward/On-Call, High-Yield Pearls, Lectures, Case Archives, Procedure Theatre, Handover Desk, Consult Room, Case Conference, Clinical Progression, Topic Summaries, Data Tools and Portfolio/Profile.

The seven core engines are shared platform services, not seven new engines to create:

1. Kernel
2. Reasoner
3. Logic (PROforma)
4. Composer
5. Router
6. Guards
7. Explain

Preserve the existing presentation-only skin rule. Clinical facts, evidence, routing predicates and executable medical logic must not be stored in skin configurations.

## 2. Non-negotiable architecture and safety constraints

1. Keep one FastAPI/React/SQLite modular monolith. No microservices, second database server, message broker, model server or cloud AI dependency.
2. Reuse UCKS as the canonical source/document/chunk/rights/review/lifecycle registry. Do not create another source registry.
3. Reuse `JobRunner` and `background_jobs` for long-running folder scans, provider sync, import, index, lottery pool preparation and analytics. Do not create another job framework or resident thread at import time.
4. Reuse the canonical HSPTL event Kernel. Do not create a second event log.
5. Keep FTS5 lexical retrieval as the default model-free retrieval mechanism. Do not enable embeddings, vector search or neural reranking.
6. No generative AI, LLM, external inference endpoint or API key is required. Deterministic extraction and template composition only.
7. Preserve original source bytes and original UCKS versions. Any transformation is a separate derived record with full lineage.
8. Do not scrape arbitrary websites. Use documented public APIs, official feeds, authorized bulk downloads, openly licensed datasets or manually registered metadata/links. Use link-only for sources without explicit reuse permission.
9. Free-to-read is not the same as permission to copy, adapt, redistribute or commercially use.
10. Never fabricate missing clinical facts, observations, patient findings, diagnoses, answers, citations, licences or image attributions.
11. Do not use abnormal values as automatic data-quality failures. Clinical outliers may be intentional teaching cases.
12. Do not equate source prestige, lexical rank, author status, publication venue or a numeric internal score with evidence certainty or clinical validity.
13. Do not use source reliability scores to auto-approve clinical content. New high-risk claims, OSCE critical items, clinical actions and simulation pathways require qualified review.
14. Local folder scanning is read-only and must be constrained to explicitly configured allowlisted roots. Never accept arbitrary paths from learner-facing API requests.
15. Reject path traversal, UNC/network shares unless explicitly approved, symlink/junction escapes, executable files, macro-enabled files and oversized inputs. Never execute embedded scripts/macros.
16. Quarantine unknown rights, unresolved ownership, suspected identifiable patient information, unparseable content and ambiguous provenance.
17. The current app is local/single-user. Use its local learner profile or a stable local learner key; do not pretend that a profile display name is authenticated identity. Do not enable cohorts or remote access as part of this increment.
18. Keep clinical case content and patient-derived records separate from general teaching knowledge. Synthea is a source for synthetic patient histories and synthetic cases only, not the primary source of clinical pearls.
19. Retain the four provenance labels exactly as user-facing terms: `GENERATED CONTENT`, `IMPORTED CONTENT`, `SYNTHETIC CONTENT`, `DERIVED CONTENT`.
20. A provenance label is not a review status, rights status, evidence grade, safety status or content type. Store and display those independently.

## 3. Increment 1 — rights-aware source registry expansion

### Objective

Extend UCKS's existing source registry, connector adapters and rights audit so HSPTL can register the user's preferred medical education sources and additional open/reusable repositories, while respecting source-specific acquisition and licence conditions.

### 3.1 Existing UCKS entities to extend

Inspect and reuse:

- `ucks_sources`
- `ucks_documents`
- `ucks_document_versions`
- `ucks_chunks` / `ucks_chunks_fts`
- `ucks_ingestion_jobs`
- existing rights review tables and APIs in `ucks_rights.py`
- source lifecycle and evidence appraisal tables
- provider and feed connector run/checkpoint tables

Add only additive schema migrations. Preserve all existing data and backward-compatible APIs.

### 3.2 Source catalogue: seed these source families

Create a versioned source catalogue/registry seed. Do not assume all sources allow full-text reuse. Every source record must declare acquisition mode, supported content types, known licence policy, API/feed availability, terms URL, source homepage, jurisdiction where known, and whether full-text ingestion is enabled.

**User-prioritized sources — preserve their priority and intended purpose:**

| Source | Primary purpose | Default acquisition policy |
|---|---|---|
| LITFL / Life in the Fast Lane | ECG, emergency, critical care, toxicology, ultrasound and practical pearls | Link/metadata by default; enable specific resources only under explicit documented permission or item licence |
| AHRQ PSNet / WebM&M | Historical patient-safety cases and lessons | Link/metadata; full-text republication only with permission |
| ARUP Consult | Laboratory medicine and test interpretation | Link/metadata by default; reuse only under source's applicable noncommercial/permission terms |
| Radiopaedia | Radiology cases, signs and visual interpretation | Link/metadata by default; each image/article asset must pass item-level licence checks |
| DailyMed | Drug labels, warnings, contraindications and adverse reactions | Official API/label retrieval; preserve SPL source/version and distinguish US label from local Egyptian authorization |
| Manual of Medicine | Spot diagnosis and quick clinical teaching | Link/metadata unless permission is established |
| Morning Reports | Long-form case discussion format | User-registered/local or licensed material; no generic scraping |
| Clinical Problem Solvers | Clinical reasoning, illness scripts and differential diagnosis | Link/metadata unless explicit licence/permission is recorded |
| SGIM clinical vignettes | Internal medicine educational case discovery | Link/metadata or licensed item; preserve author/source attribution |
| EMCrit / IBCC | Critical care teaching and physiology pearls | Link/metadata by default; no automated republication without permission |
| Medscape | Clinical pearls and educational materials | Link/metadata by default; no automated copying/scraping without permission |
| Manual/Pathognomonic visual resources | Spot diagnosis and diagnostic signs | Verify the exact intended canonical source and each asset's rights before enabling ingestion |

**Additional open/reusable sources to implement as rights-aware connectors or curated catalogues:**

| Source | Purpose | Rights behavior |
|---|---|---|
| Open RN / Open RN Virtual Simulations | Nursing skills, case studies, handover and virtual simulations | CC BY 4.0 where stated; persist item-level attribution and licence |
| MedEdPORTAL | Simulation packages, standardized patients, OSCE/assessment materials | Check each publication's author-selected CC BY, CC BY-NC or CC0 licence |
| WikEM | Emergency medicine reference and pearls | CC BY-SA 3.0 default subject to item exceptions; preserve attribution, changes and ShareAlike obligations |
| PLOS | Open research, case reports and figures | CC BY 4.0 for eligible articles; check third-party figure rights |
| PMC Open Access Subset | Research articles and case reports | Article-level licence; only ingest full text when licence permits the intended reuse |
| Europe PMC | Literature metadata and open full-text discovery | Use official APIs; confirm article-specific reuse rights |
| Cureus | Open-access case reports | Article licence and third-party assets must be checked |
| Journal of Medical Cases | Open-access medical case reports | CC BY 4.0 for eligible 2026 onward material; older material may be CC BY-NC; check per article |
| CDC Public Health Image Library | Infectious disease, organisms and public-health visual spotters | Inspect each image's copyright/credit; public-domain items can be reused subject to their metadata |
| NCI Visuals Online | Oncology, anatomy, pathology and clinical visuals | Item-level copyright and credit checks |
| Wikimedia Commons | Medical images and diagrams | File-by-file licence, attribution and derivative rules |
| Wellcome Collection | Medical history, anatomy and health images | API/catalogue discovery; item-level rights |
| MedlinePlus | Patient-friendly medical explanations and test information | Reuse only the specific public-domain/allowed sections; exclude third-party encyclopedia/drug content where restricted |
| Open Textbook Library | Foundational medical/biology/health-science textbooks | Book/chapter-level CC/GNU licence; no blanket assumption |

Do not hard-code unverified assumptions about a provider API. For each provider, record whether there is a documented API, RSS/Atom feed, bulk download, public metadata page or only link-out. If no documented acquisition method exists, implement a curated source catalogue and link-only connector rather than an HTML scraper.

### 3.3 Connector implementation requirements

- Reuse existing connectors in `ucks_connectors.py`, Specialty Harvester adapters and shared HTTP/cache utilities.
- Add provider adapters only for documented, stable APIs or feeds. Prefer no-key public APIs.
- Add DailyMed's documented web services/SPL interface as a dedicated connector. Store label set ID, SPL version/date, section identifiers, application/product identifiers where available and source URL. Never infer Egyptian registration from an FDA label.
- Extend Europe PMC / PMC OA handling only where the actual article-level licence and article identifiers are available.
- Where MedEdPORTAL, Open RN, WikEM, PLOS, Cureus or other providers expose supported metadata/API/feed routes, use those routes with bounded requests and provider-specific parsing. Otherwise register catalogue metadata and allow manual approved document import.
- Never crawl LITFL, Medscape, EMCrit, Radiopaedia, ARUP, Manual of Medicine, AHRQ or SGIM indiscriminately.
- Store provider terms URL and a `last_rights_checked_at` review date.
- Respect robots/terms, rate limits, conditional requests, ETag/Last-Modified where available, bounded payload sizes, timeouts and no-follow redirects where existing transport policy requires it.
- Preserve provider identifiers (DOI, PMID, PMCID, NCT, SPL Set ID, provider item ID, image ID) without merging records merely because identifiers appear similar.

### 3.4 Rights and licensing model

Extend the existing append-only rights decision model. Do not make a new rights database.

Each document and each embedded image/media asset must have its own rights record where the rights differ. Fields should include:

- `license_id` / SPDX identifier or normalized licence key when possible;
- `license_uri` and exact source licence text/reference;
- `rights_holder` / creator / publisher;
- attribution text and required citation;
- `reuse_scope`: metadata_only, abstract_only, display_link, full_text_reuse, adaptation, redistribution, image_display, image_adaptation;
- `commercial_use_allowed` (true/false/unknown);
- `derivatives_allowed` (true/false/unknown);
- `share_alike_required` and compatible licence requirement;
- `noncommercial_restriction`, `no_derivatives_restriction`;
- third-party asset exceptions;
- permission evidence URL/file and reviewer rationale;
- reviewer ID from the existing authenticated reviewer workflow;
- decision (`permitted`, `restricted`, `needs_clarification`);
- review timestamp and recheck date.

Support at minimum:

- Public domain / CC0
- CC BY
- CC BY-SA
- CC BY-NC
- CC BY-NC-SA
- CC BY-ND / CC BY-NC-ND
- custom publisher terms
- permission required
- link-only
- unknown/unverified

**Rights behavior:**

- A site-level policy is only a default; item-level terms override it.
- If rights are unknown, retain metadata and link only; do not store reusable full text or redistribute assets.
- CC BY-SA derivatives must preserve compatible ShareAlike terms and attribution.
- NC items must remain excluded from any incompatible commercial or institutional distribution mode.
- ND items may be linked/displayed only within the exact permitted scope; do not paraphrase/adapt under the ND licence without separate permission.
- Public-domain status must be evidenced; do not assume all government or medical-site content is public domain.
- `permitted` decisions require licence/scope/evidence fields, not simply a user checkbox.
- Rights review must remain distinct from clinical review and evidence appraisal.

## 4. Increment 2 — Local Folder Source Manager

### Objective

Allow the user to register one or more local folders as read-only source collections. Use these local documents in UCKS, the Clinical Knowledge Factory and Daily Case Lottery after rights/privacy screening.

### 4.1 User workflow

Add a Data Tools → Source Manager screen with:

1. Add Local Folder.
2. Browse/select a directory using the supported local UI/runtime mechanism.
3. Name the source collection (e.g. Morning Reports, Local OSCEs, Spot Diagnosis Images).
4. Declare owner/source, intended use and rights basis.
5. Preview folders/files and file counts.
6. Configure recursive depth, allowed file types, max file size and include/exclude rules.
7. Run Scan.
8. Review scan report and duplicates.
9. Ingest eligible documents into UCKS.
10. View file path, hash, extraction status, source ID, provenance label and rights status.

### 4.2 Supported file types

Reuse the existing UCKS upload parsers for PDF, DOCX, CSV, TSV, JSON, JSONL, Markdown and TXT. Add PPTX and HTML only if safe extractors already exist or can be added without macro/script execution. Images (PNG, JPG/JPEG, WebP) should be registered as media assets with metadata and hashes; do not pretend OCR or visual interpretation exists when it does not.

- No macros, executables, scripts, archives or password-protected files in the initial increment.
- Scanned PDFs with no text layer stay `needs_ocr` / quarantined; do not silently run OCR or fabricate extracted text.
- Maximum file size and total scan limits must be configurable and safely bounded.
- Skip symlinks/junctions by default. If explicitly supported, resolve the final path and prove it remains under the registered root.

### 4.3 Path and filesystem security

- Only source roots registered by an authorized local administrator are eligible.
- Resolve paths canonically and reject path traversal, device paths, UNC paths and unapproved network shares.
- Prevent symlink/junction escapes and time-of-check/time-of-use path replacement as far as the platform allows.
- Never accept an arbitrary `path` parameter from a learner-facing endpoint.
- Open files read-only; never modify, move, rename or delete originals.
- Store relative paths in learner-facing provenance where useful; reveal absolute paths only in local administration/source detail.
- Do not follow links inside imported HTML or documents.
- Do not execute embedded content.

### 4.4 File reconciliation

- Calculate SHA-256 streaming hashes.
- Identical root + relative path + hash: skip unchanged file.
- Same hash at another path: surface as possible duplicate; do not merge away the original source identity automatically.
- Same path with changed hash: create a new immutable source-document version and retain the previous version.
- Preserve filename, relative path, media type, byte size, modified timestamp, hash, extractor/version and import job ID.
- Store extracted text/chunks as UCKS document versions; original binary file is an immutable referenced artifact within the configured source root or a managed source-copy if the existing storage design requires it. Document the retention rule.

### 4.5 Job model

Use the existing durable `JobRunner` and `background_jobs` table for scan/ingestion tasks. Add job kinds such as `ucks_local_folder_scan` and `ucks_local_folder_ingest` only if they fit the current job registration contract. Include progress checkpoints, cancellation, restart recovery, bounded batches and an audit record. Never start a worker thread on module import.

## 5. Increment 3 — Shared content-origin and provenance model

### Objective

Make the four user-facing labels consistent across UCKS, generated artifacts, case records, question bank, visual media, workspace libraries and the Daily Case Lottery.

### 5.1 Exact provenance labels

Persist a normalized enum:

- `generated` → UI badge **GENERATED CONTENT**
- `imported` → UI badge **IMPORTED CONTENT**
- `synthetic` → UI badge **SYNTHETIC CONTENT**
- `derived` → UI badge **DERIVED CONTENT**

Map existing values conservatively. For example, current `synthetic_case` content should display as `SYNTHETIC CONTENT`; do not rewrite its historical record or remove its detailed provenance.

### 5.2 Keep independent dimensions independent

A content item must have separate fields for:

- `origin_label` (one of the four labels);
- `content_type` (case, pearl, question, image spotter, OSCE, note, etc.);
- `review_status` (draft, harvested, under_review, reviewed, validated, approved, rejected, as appropriate to the existing workflow);
- `lifecycle_state` (current, superseded, corrected, retracted);
- `rights_status` and allowed reuse scope;
- `clinical_review_status`;
- `evidence_status` / appraisal metadata;
- `publication_status` / workspace distribution status.

Do not conflate any of these. A `GENERATED CONTENT` item may be a draft or approved; an `IMPORTED CONTENT` item may be reviewed but not licensed for redistribution; a `SYNTHETIC CONTENT` record is not automatically a clinical teaching case.

### 5.3 Provenance lineage

Create or extend a common content identity/lineage adapter using existing UCKS, generated-artifact, CaseRepository, tagged-content and provenance stores. Avoid a parallel master document database.

Record:

- stable `content_item_id`;
- origin label;
- parent content IDs (0, 1 or many);
- source document/version/chunk IDs;
- external source/provider IDs and canonical URL;
- local source ID, relative file path and SHA-256;
- Synthea version/seed/module/config manifest when applicable;
- generator/recipe/template version;
- transformation names and versions;
- content hash;
- rights decision and attribution references;
- reviewer/review state and timestamps;
- creation/import/derivation timestamps.

`DERIVED CONTENT` must have at least two explicitly recorded contributing origins or an explicit derivation from a parent. Do not mark an item derived simply because it has a citation. A generated extractive teaching artifact from one imported document remains `GENERATED CONTENT` with imported parent lineage; a case that combines a Synthea patient with an imported or generated teaching structure becomes `DERIVED CONTENT`.

Add migration/backfill reports. Do not silently infer missing provenance. Items whose origin cannot be established should have `origin_label=unknown` internally and display an `ORIGIN UNVERIFIED` warning, not be falsely assigned one of the four labels.

### 5.4 UI label rules

Every card/list/detail view in Clinic, Rounds, Lab, Ward, Exam Hall, Portfolio/Data Tools and Daily Case Lottery should display:

- origin badge;
- review status;
- rights/reuse badge where relevant;
- source and publication date;
- evidence/support rating when available;
- clinical review state for high-risk content.

Use text labels and accessible colour/icon distinctions; do not rely on colour alone.

## 6. Increment 4 — Daily Clinical Case Lottery

### Objective

Build a shared daily case challenge from eligible cases across all four origin labels and all registered source pools, including approved local folders. It should be visible on Ward Board and open its case-solving experience in Clinic.

### 6.1 Core UX

Ward Board card:

- Title: `Daily Case Lottery`.
- Subtitle: `One case. One clinical challenge. Every day.`
- Draw/current challenge state.
- Specialty, difficulty, estimated time and origin label.
- Source badge and review status.
- Continue/Open button.
- Completion state and next debrief availability.

Clinic case flow:

1. Presenting complaint / opening prompt.
2. Progressive history disclosure.
3. Examination findings (only if present in the source/approved case package).
4. Investigation/image/result reveal.
5. Problem representation.
6. Differential diagnosis.
7. Working diagnosis and justification.
8. Next-step/management reasoning only where an approved case-specific educational rubric exists.
9. Commit final answer.
10. Debrief with clinical pearls, explanations, references and related material.

Never reveal hidden answer keys, unreleased clues or examiner-only notes before the learner commits. External link-only challenges may open at the publisher and must not reproduce protected text/images in HSPTL.

### 6.2 Candidate eligibility

A candidate must:

- be explicitly classified as a case/challenge/spotter type supported by the lottery;
- have a valid provenance origin or be held out as origin-unverified;
- be in an eligible published/review state for its content type;
- not be rejected, retracted or superseded;
- have a rights scope that permits the selected delivery mode (internal display, adaptation or link-only);
- pass required structural and privacy checks;
- have a valid difficulty/specialty/estimated-time profile or receive an explicit `not_assigned` state;
- have answer/debrief access properly separated from learner content;
- have source attribution and lineage available.

Do not require every imported educational case to be clinically validated as a guideline. Use appropriate case-level educational/clinical review statuses. A link-only source can be a `Read/Discuss` challenge, but not a copied full-text case.

### 6.3 Four-label balancing

- If all four labels have eligible candidates, assign equal initial weight to each available label.
- Within a label, balance source collection/provider, specialty and difficulty so one very large source does not dominate.
- If a label has no eligible items, redistribute its probability only among labels that do have eligible candidates; report pool unavailability.
- Exclude recently completed items where alternatives exist. Relax the exclusion gradually when the candidate pool is small, with a reason code.
- Avoid repeated same-provider/source streaks when there are viable alternatives.
- Allow learner filters for specialty, difficulty, case length and origin labels; defaults include all four labels.

### 6.4 Deterministic draw and daily persistence

- Use application-configured timezone; default to the operating-system/local configured timezone (support `Africa/Cairo`, but do not hard-code Cairo for every installation).
- Build a candidate-pool snapshot with stable sorted candidate IDs and eligibility metadata hash.
- Derive a deterministic seed from local date, local learner key, policy version and pool snapshot hash, using a cryptographic hash rather than Python's process-randomized `hash()`.
- Persist the draw transactionally. Enforce a unique key for `(learner_key, local_date, challenge_slot)`.
- Reopening HSPTL must return the same draw even if the source pool later changes.
- Save pool snapshot hash, policy version, seed digest, chosen item ID, origin label, source IDs and reason codes.
- Reroll is optional, max one per day by default, only before first answer/clue reveal. It must retain the prior draw and record a `rerolled` event; no silent replacement.
- In the current local single-user installation, use the stable local learner key. Do not use display name as identity. Future multi-user behavior is out of scope until authenticated identity and privacy controls are implemented.

### 6.5 Kernel events

Use the existing canonical Kernel and add event contracts/catalogue entries for the relevant lifecycle, such as:

- `learning.daily_case.pool_built`
- `learning.daily_case.drawn`
- `learning.daily_case.rerolled`
- `learning.daily_case.opened`
- `learning.daily_case.clue_revealed`
- `learning.daily_case.answer_committed`
- `learning.daily_case.completed`
- `learning.daily_case.debrief_opened`

Event payloads contain IDs, version references, hashes, counts, timestamps, policy version and state transitions. Do not store full PDFs, images, FHIR bundles or entire case documents in events.

### 6.6 Daily-case analytics

Record open, clue reveal, answer commit, completion, debrief, time spent, confidence if explicitly collected, score if a validated rubric exists and related-tag activity. A correct answer rate is formative performance, not proof of clinical competence.

## 7. Increment 5 — integrate the seven core engines across workspaces

### Objective

Make the seven existing engines available through consistent application-service boundaries and use-case adapters. Do not duplicate engine logic in each React page or put medical rules in skin configuration.

### 7.1 Engine responsibilities

**Kernel**
- canonical event append, audit, replay and provenance;
- source/rights decisions, local scans, generation, lottery, attempts, reviews and distribution events;
- immutable event payloads with references/hashes, not full document bodies.

**Reasoner**
- use existing UCKS graph and reviewed terminology mappings;
- connect concepts, findings, investigations, specialties, competencies, tags, cases and pearls;
- only expose reviewed graph links as trusted relationships;
- keep lexical co-occurrence and unreviewed proposals visibly separate from accepted knowledge.

**Logic**
- PROforma only for executable workflows;
- daily case staged-reveal and answer-commit lifecycle;
- review/rights approval workflow orchestration;
- OSCE and assessment state transitions;
- no new parallel rule language or hidden clinical decision logic.

**Composer**
- use existing workspace scripts/templates and extractive source-chunk composer;
- build learner presentation, case brief, pearl, spotter, question packet, debrief and workspace delivery artifact;
- retain source spans/character offsets for every extractive assertion;
- do not synthesize unsupported medical facts or create ungrounded answer keys.

**Router**
- use existing workspace-aware retrieval and routing profiles;
- content eligibility and distribution routing;
- Daily Case Lottery candidate balancing and draw;
- recommendation of related pearls, questions and cases using reviewed tags, due review and recorded learner activity;
- every decision must have stable reason codes and deterministic replay inputs.

**Guards**
- validate rights scope for the intended use;
- block rejected/retracted/superseded/unlicensed content from inappropriate distribution;
- enforce local folder path restrictions and privacy scans;
- validate provenance completeness, review state and hidden-answer access;
- fail closed/abstain/quarantine for missing or uncertain prerequisites;
- do not automatically change clinical meaning.

**Explain**
- source and claim lineage;
- daily draw explanation (eligible pools, chosen label/source, reason codes);
- case answer rationales and evidence support;
- assessment item and rubric derivation;
- workspace recommendations and source changes;
- replayable derivation trace.

### 7.2 Workspace integration requirements

Six skins remain presentation-only: Clinic, Rounds, Lab, Ward, Exam and Portfolio. Extend page use cases and workspace APIs, not skin configuration with clinical logic.

**Ward Board / Overview (Portfolio skin)**
- Daily Case Lottery card, continue case, due reviews, recent activity, next recommendation.
- Kernel activity projection; Reasoner learning-gap links; Router next activity; Explain recommendation reasons.
- Do not invent dashboard metrics or claim mastery from sparse formative data.

**Clinic**
- daily case solving, case archives, conference and simulation entry points.
- progressive evidence disclosure and diagnostic reasoning capture.
- Reasoner concept links; Logic case state; Composer case presentation/debrief; Guards hidden answers and case eligibility.

**Rounds**
- clinical pearls, topic teaching, case reports, viva and lectures.
- UCKS source-backed retrieval; Composer structured pearls/teaching packets; Explain claim-level references; Guards rights/currentness/review state.

**Diagnostics Lab**
- ECG, radiology, pathology, laboratory, bedside examination and OSCE.
- image/media source rights checked per asset; Reasoner finding-concept links; Composer spotter and interpretation templates; Router competency-linked practice.

**Ward workflows**
- On-Call, Handover, Consult and Clinical Progression.
- PROforma workflow state; Kernel events; Guards prevent unsupported actions; Explain transitions and consequences.

**Exam Hall**
- questions, mock exams and assessment packs.
- Composer assessment assembly; Router blueprint/difficulty selection; Guards answer security and eligibility; Explain item rationales and provenance.
- Do not claim IRT calibration or psychometric validity without representative response data.

**Data Tools / Content Studio / Portfolio governance**
- source manager, local folders, UCKS, rights, provenance, evidence appraisal, generator, Daily Case Lottery pool manager, quality queue, review and distribution.
- Keep administrative functions away from learner views unless the user has a supported role. The current single-user environment is not an institutional RBAC system.

### 7.3 Shared engine contract

For each engine, expose a typed in-process service/use-case interface to backend services. Frontend pages must call workspace/application APIs rather than instantiate engines directly. Every use-case should declare inputs, outputs, event(s), failure/abstention states and provenance requirements. Add contract tests to ensure workspace skins cannot hold clinical facts, evidence, thresholds or executable predicates.

## 8. Increment 6 — expand the Clinical Knowledge & Pearls Factory

### Objective

Expand model-free, rights-aware educational content production using non-guideline clinical teaching sources. Keep the user's earlier preference: this increment focuses on clinical pearls, bedside practice, spot diagnosis, cases, clinical skills and teaching material; do not turn it into a general clinical-practice guideline harvester.

Legacy guideline documents and code may remain backward-compatible, but guideline ingestion must not be added to the default Clinical Pearls source profile or Daily Case Lottery source profile.

### 8.1 Source families and use profiles

Create curated source profiles:

- `emergency_critical_care`: LITFL, EMCrit/IBCC, WikEM (rights-aware).
- `clinical_pearls`: LITFL, Medscape, Manual of Medicine, Clinical Problem Solvers (restricted sources link-only unless permitted).
- `historical_safety_cases`: AHRQ PSNet/WebM&M (link-only by default; use permissioned local copies if obtained).
- `laboratory_interpretation`: ARUP Consult (link/metadata by default; reuse only within permitted terms).
- `radiology_spotters`: Radiopaedia (item-specific licence) plus public-domain/CC visual repositories.
- `medication_reference`: DailyMed SPL/API; keep US label jurisdiction explicit and distinguish from Egyptian registration.
- `spot_diagnosis`: Manual of Medicine, Pathognomonic (verify exact canonical provider), CDC PHIL, NCI, Wikimedia Commons and Wellcome item-level rights.
- `clinical_cases`: Morning Reports, Clinical Problem Solvers, SGIM vignettes, MedEdPORTAL, PLOS, eligible PMC, Cureus and Journal of Medical Cases.
- `skills_osce`: Open RN, MedEdPORTAL, WikEM and locally licensed institutional templates.

Use these source modes:

1. `api_ingest` only where an official supported API is documented.
2. `feed_ingest` only for published RSS/Atom feeds and within source terms.
3. `licensed_bulk` for explicitly authorized bulk files.
4. `manual_file_import` for the user's rights-cleared local content.
5. `metadata_link_only` for free-to-read or restricted sources without reuse permission.

Do not scrape restricted sites or bypass paywalls, login controls or rate limits.

### 8.2 Standard deterministic pearl/content templates

Implement versioned JSON schemas and renderers for at least:

1. `clinical_pearl`: title, one-sentence insight, why it matters, context, common pitfall, limitation, related tags, source claims, citations.
2. `diagnostic_clue`: finding, what it suggests, differential, discriminating clues, exceptions, claim references.
3. `bedside_exam`: purpose, technique, normal finding, abnormal finding, interpretation, limitations, safety, source.
4. `ecg_interpretation`: rate, rhythm, axis, intervals, morphology, pattern, differential, limitations, linked ECG asset.
5. `laboratory_interpretation`: test, specimen/context, result/unit/reference interval (source-specific), interpretation, pitfalls, next learning question.
6. `radiology_spotter`: modality, image asset, prompt, visible features, differential, answer, caveats, asset rights record.
7. `medication_safety_pearl`: drug/product identifier, jurisdiction, source label/version, warning/adverse effect/interaction, evidence text, limitations. Do not turn a US SPL into an Egyptian prescribing rule.
8. `clinical_case`: case narrative, timeline, source facts, learner prompts, differential, answer/debrief, origin lineage and case-review metadata.
9. `osce_station`: station aim, candidate instructions, examiner instructions, patient brief, equipment, time, checklist, critical safety items, global rating, model answer, references.
10. `viva_set`: progressive question, examiner probes, model answer, marking domains, references and difficulty.
11. `patient_safety_case`: event summary, timeline, contributing factors, systems learning, reflection questions, source/permission details.
12. `question_set`: question stem, lead-in, options if authored, keyed answer, distractor rationales, learning objective, source claims, review state.

Use the existing generation/output schema and versioning system; do not add another template registry. Add schema migration and tests for new output kinds.

### 8.3 Generation boundaries

- Reuse existing extractive/BM25-lite source retrieval and exact source span offsets.
- The deterministic composer may assemble approved snippets, structured facts and author-created templates.
- Do not paraphrase copyrighted material unless the licence/permission allows adaptation.
- Do not generate novel clinical facts, treatment claims, drug doses, image findings or answer keys without explicit approved source material and expert review.
- Imported questions remain imported; HSPTL-created questions are generated; cases combining a Synthea patient and external teaching framework are derived.
- Clinical pearls can be generated from permitted source claims, but must carry exact supporting source spans or a clear `expert_opinion/teaching_insight` declaration.
- Every artifact starts as draft/harvested as appropriate. Preserve existing reviewer-gated approval and distribution.

## 9. Increment 7 — analytics and learner feedback

### Objective

Use existing Kernel events and shared tags to produce useful formative feedback across all workspaces. This is not a psychometric calibration project or a competency-certification feature.

### 9.1 Event capture

Standardize events for:

- content_opened;
- content_completed;
- question_attempted;
- answer_committed;
- answer_feedback_opened;
- pearl_reviewed;
- spotter_attempted;
- osce_attempted;
- viva_attempted;
- case_started;
- case_completed;
- daily_case_drawn;
- daily_case_completed;
- debrief_opened;
- spaced_review_scheduled/completed.

Include content ID/version, content origin, source lineage reference, workspace, specialty, task, modality, difficulty, tag IDs, timestamp, duration where available and outcome when valid. Do not duplicate whole content payloads in events.

### 9.2 Tag-level learning signals

Reuse the existing shared tag registry/index. Aggregate only transparent signals:

- attempts and completions;
- latest/recent performance where an answer key and rubric exist;
- confidence when explicitly collected;
- time since last practice;
- due FSRS review state;
- unfinished activities;
- repeated errors by tag/task.

Unknown or missing signals stay unknown. Do not infer mastery or clinical competence from a few attempts, reading events or synthetic patient volume.

### 9.3 Router recommendations

Use the existing Router/learning-route contracts and existing FSRS/IRT boundary. Produce explainable suggestions such as:

- “Review this ECG pearl: recent errors tagged Cardiology + ECG interpretation.”
- “Try a radiology spotter: this modality has not been practised recently.”
- “Complete the debrief for yesterday's case before another advanced case.”

Each suggestion has reason codes, input event references, rule/profile version and an expiry/recompute policy. Do not call recommendation ranks evidence quality or proof of learning.

### 9.4 Learner feedback UI

Ward Board should show:

- Daily Case Lottery card and completion state;
- recent clinical practice;
- due review queue;
- specialty/task coverage;
- transparent strengths and topics to revisit;
- next recommended activity with an explanation.

Rounds, Lab, Clinic and Exam Hall should show context-specific follow-up recommendations. Portfolio should provide aggregate history and source/provenance information. Avoid gamified, unsupported mastery claims.

## 10. Daily Case Lottery detailed API and data contracts

Implement a typed lottery service and routes, following repository conventions. Suggested endpoints (adjust names to avoid route conflicts):

- `GET /api/daily-case/status`
- `GET /api/daily-case/pool/summary`
- `POST /api/daily-case/draw`
- `GET /api/daily-case/today`
- `POST /api/daily-case/reroll`
- `POST /api/daily-case/{draw_id}/open`
- `POST /api/daily-case/{draw_id}/reveal`
- `POST /api/daily-case/{draw_id}/answer`
- `POST /api/daily-case/{draw_id}/complete`
- `GET /api/daily-case/{draw_id}/debrief`
- `GET /api/daily-case/history`
- `GET/PUT /api/daily-case/preferences`
- `GET/POST /api/daily-case/sources` (or reuse existing source APIs and expose pool membership)

Persist draw, learner key, local date, timezone, policy version, candidate pool snapshot/hash, seed digest, selected item ID, origin label, source IDs, reason codes, state, reroll relation, answer/debrief references and timestamps. Add a uniqueness constraint to prevent duplicate first draws per learner/day/slot.

Keep case answers/examiner material separate from the learner projection. Enforce authorization at the service boundary even in local mode; future remote use requires a stronger identity model.

## 11. UI and navigation integration

Extend existing pages/components; do not build a second SPA or generic admin portal.

### Ward Board
- Add Daily Case Lottery hero card.
- Show today’s case metadata and origin badge.
- Show completed/available state and history.
- Add recommendations driven by actual tagged events.

### Clinic
- Add progressive case challenge route/state.
- Preserve current case archive, FHIR patient explorer and simulation flows.
- Distinguish external link-only challenges from cases rendered locally.

### Rounds
- Add Clinical Pearls source collections and generated/imported label badges.
- Add source/citation panel and related-case links.

### Diagnostics Lab
- Add visual asset catalogue with per-asset rights, attribution and modality metadata.
- Add spotter challenge entry from Daily Case Lottery.

### Exam Hall
- Link question/OSCE/viva practice to shared tags and source lineage.
- Preserve reviewed-question requirements and answer-key protection.

### Ward
- Link relevant case challenge debriefs to on-call, handover, consult and progression learning tasks; use existing PROforma workflows.

### Data Tools / Content Studio / Portfolio
- Add Source Manager tab, Local Folders tab, Rights & Licence review, Provenance browser, Daily Lottery Pool Manager, Clinical Knowledge Factory templates, source changes and generation/review/distribution dashboards.
- Expose local absolute paths only in local administrative source details.

Use the existing six skin definitions. Do not put clinical knowledge, provenance truth, eligibility predicates or medical rules into `skinRegistry.ts`.

## 12. Quality, evidence and validation model

Reuse the existing structured evidence appraisal and rights-review infrastructure. Add separate, clearly named dimensions where missing:

- source identity/authenticity;
- source editorial/transparency attributes;
- source licence/reuse status;
- claim-to-source support strength;
- underlying evidence certainty/appraisal;
- content clinical review status;
- content educational review status;
- freshness/lifecycle status;
- attribution completeness.

Do not collapse these into one score. If implementing provisional internal Source Reliability Index (SRI) or Claim Support Index (CSI), label them as HSPTL heuristic indices, version the rubric, store component-level values and calibrate against expert review before using them as automatic gates. GRADE, AGREE II, AMSTAR 2, RoB 2, ROBINS-I and QUADAS-2 are method-specific appraisal frameworks; do not invent a universal numeric conversion or treat checklists as evidence certainty.

Lexical retrieval rank is relevance, not evidence quality. Connector health is reachability, not source validity. Licence permission is reuse rights, not clinical accuracy. Editorial review is not clinical approval.

## 13. Rights, privacy and source integrity

- Keep the original source URL, publisher, author, date, licence and attribution.
- Store licence per document and per embedded figure/image where different.
- Keep the raw original immutable and version extracted content.
- Retain corrections, retractions and superseded versions.
- Treat patient-related documents as potentially sensitive. Detect obvious identifiers and quarantine for review; do not claim complete de-identification from a simple regex scan.
- Never publish local absolute paths, private files or patient identifiers into shared exports.
- Link-only resources should not be copied into generated artifacts; only permitted metadata, bibliographic facts and link-out UI may be used.
- Images need asset-level rights metadata and source linkage, not only parent article licence.
- A local folder declaration does not prove ownership or rights; require a recorded rights basis.

## 14. Testing and acceptance criteria

Implement deterministic tests with network calls mocked. Do not depend on a live external publisher during automated test runs.

### 14.1 Source registry and rights

- Existing UCKS sources and documents migrate without loss.
- Known source profiles seed idempotently.
- Restricted source defaults to metadata/link-only.
- Item-level licence overrides provider default.
- NC/ND/SA conditions are preserved.
- Unknown rights cannot be used for full-text generation or copied lottery content.
- Rights decision history is append-only and authenticated by existing reviewer token flow.
- Each image/figure asset can have separate rights metadata.

### 14.2 Local folder manager

- Reads only configured allowlisted roots.
- Blocks path traversal, UNC/network paths by default, symlinks and junction escapes.
- Does not follow HTML external links or execute macros.
- Enforces file size/type and scan limits.
- Detects unchanged hashes and creates revisions for changed files.
- Originals are not modified.
- Scanned PDF without text layer is quarantined/needs OCR.
- Resume/cancel/retry behavior works through the existing durable JobRunner.

### 14.3 Provenance

- All four labels serialize and render exactly.
- Existing `synthetic_case` maps to SYNTHETIC CONTENT in UI without destroying old provenance.
- Generated from one imported source remains GENERATED CONTENT with imported parent lineage.
- Mixed-origin case is DERIVED CONTENT and retains all parent links.
- Unknown origin never silently maps to a known label.
- Review status and rights status remain independent from origin.

### 14.4 Daily Case Lottery

- Same learner/date/policy/pool snapshot returns the same draw after restart.
- Exactly one initial draw per learner/date/slot.
- Four-label balancing works when all labels are present.
- Missing label probability redistributes correctly.
- Ineligible/rejected/retracted/unlicensed candidates are excluded from in-app copying.
- Link-only cases open externally without reproducing protected content.
- No completed/recent repeats where eligible alternatives exist; relaxation reason recorded when necessary.
- Reroll limit and cutoff behavior enforced.
- Answer and examiner material remain hidden until commit.
- Draw, reveal, answer, completion and debrief events replay correctly.
- Pool snapshot hash and candidate IDs make selection explainable.

### 14.5 Engine/workspace integration

- Each workspace uses shared engine services via backend contracts.
- No React page contains independent clinical rules or direct database writes.
- PROforma remains the only executable workflow language.
- Skin configs remain presentation-only.
- Every Router recommendation/draw has reason codes.
- Every Explain output resolves source and event references.
- Kernel remains the single canonical event history.

### 14.6 Knowledge factory and analytics

- New content templates validate against versioned schemas.
- Every generated assertion/section retains source spans or an explicit authored/educator origin.
- Rights/lifecycle filters apply before generation.
- No unreviewed or source-invalid content is silently auto-published.
- Analytics aggregate only valid recorded learner events.
- No mastery/competence claim is inferred without a validated assessment basis.

### 14.7 Release verification

- Add/extend backend tests, API tests, frontend contract tests and UI component tests where test harness exists.
- Test Windows paths and Unicode file names where possible.
- Test offline behavior and graceful provider unavailability.
- Run targeted tests during development, then one consolidated backend/frontend/release verification after all changes are complete.
- Update exact test counts and limitations in release status. Do not claim a build/test passed if it was not run.

## 15. Documentation and deliverables

Update or add:

- `docs/UCKS.md` — new source adapters, local folder manager, rights behavior and remaining gaps.
- `docs/CLINICAL_KNOWLEDGE_HARVESTER.md` — source profile catalogue and acquisition modes.
- `docs/DAILY_CASE_LOTTERY.md` — selection, eligibility, event lifecycle and learner flow.
- `docs/CONTENT_PROVENANCE_AND_LABELS.md` — four labels, lineage, status separation and UI behavior.
- `docs/SEVEN_ENGINE_WORKSPACE_INTEGRATION.md` — engine contracts and workspace responsibilities.
- `docs/OPEN_SOURCE_RIGHTS_CATALOGUE.md` — seed sources, canonical terms, licences, supported ingestion mode and last verification date.
- `docs/ARCHITECTURE.md` and `README.md` — updated system map and install/run instructions.
- `CHANGELOG.md`, `RELEASE_STATUS.md`, `RELEASE_CHECKLIST.md` — 5.0.0 changes and truthful verification status.
- Tests and source catalogue seed data.

Final release package should include source code, documentation, migrations, tests, required local assets, `MANIFEST.sha256`, install scripts and Windows instructions. Exclude caches, `.venv`, `node_modules`, personal local source documents, API tokens and generated patient datasets unless the user explicitly asks to package a small fixture corpus.

## 16. Out of scope and explicit limitations

- No LLM or AI model, paid API, API key or hosted inference is required.
- No unrestricted website scraping or automated circumvention of publisher rights.
- No automatic publication of new clinical advice or treatment protocols.
- No real patient data ingestion without approved privacy/legal governance.
- No institutional multi-user RBAC/cohort rollout in this increment.
- No assertion that open access means reusable.
- No assertion that automated extraction proves clinical correctness.
- No assertion that a daily case score proves competence.
- No psychometric calibration without representative response data.
- No conversion of the seven engines into separate microservices or duplicated per-workspace implementations.

## 17. Required completion report

When implementation is finished, provide:

1. Repository inventory and baseline identity reconciliation.
2. Files added/changed, grouped by increment.
3. Database migrations and backward-compatibility result.
4. New/extended API routes.
5. Source catalogue and provider acquisition modes.
6. Rights policy and four-label provenance behavior.
7. Local folder security controls.
8. Daily Case Lottery selection/replay demonstration using fixtures.
9. Seven-engine workspace integration map.
10. UI routes/screens delivered.
11. Tests/build/release verification with exact results.
12. Known limitations and any publisher integrations that remain link-only or require permission.
13. Final ZIP package path and SHA-256 checksum.
14. Windows installation and configuration instructions.

Do not mark the task complete if only APIs or backend scaffolding exist. The learner-visible Daily Case Lottery, Source Manager, provenance labels, workspace integration and Data Tools governance UI must all work end-to-end.

---

# End of implementation directive

## Suggested execution order for the coding agent

1. Inspect and reconcile baseline/version metadata.
2. Confirm existing UCKS, generation, case, job, Kernel, Router, Guards, Explain and workspace contracts.
3. Add migrations and rights-aware provider catalogue.
4. Implement Local Folder Source Manager using the existing JobRunner.
5. Add shared origin/provenance adapters and UI labels.
6. Implement Daily Case Lottery service, events, APIs and Clinic/Ward Board UI.
7. Integrate seven engines through shared backend use cases and workspace contracts.
8. Expand clinical pearls and open-resource templates/connectors.
9. Add learning analytics and explainable recommendations.
10. Run consolidated verification, update docs and package release.

**Implementation rule:** Reuse first, extend second, create new modules only for genuinely missing capabilities. Preserve the current HSPTL product and data; do not replace working UCKS, content generation, FHIR case import, tagging, workspace distribution or simulation functionality.
