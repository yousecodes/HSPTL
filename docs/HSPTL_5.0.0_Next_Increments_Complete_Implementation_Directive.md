# HSPTL 5.0.0 — Complete Implementation Directive
## Rights-Aware Source Registry, Local Folder Sources, Daily Clinical Case Lottery, Clinical Knowledge Factory, and Seven-Engine Workspace Integration

**Target:** HSPTL 5.0.0 continuation / next implementation increments  
**Baseline reference:** User-uploaded `HSPTL-5.0.0.zip`  
**Authoritative implementation target:** The user's current local HSPTL working tree containing the reported implemented and verified Synthetic Data Factory changes  
**Architecture:** Local-first, model-free, deterministic where applicable, single FastAPI/SQLite + React modular monolith  
**Hardware target:** Windows 10/11, 8 GB RAM  
**Primary goal:** Extend existing UCKS, Content Factory, JobRunner, Kernel, Case Repository, tagging, rights and evidence infrastructure. Do not rebuild them.

---

# COPY THE IMPLEMENTATION PROMPT IN SECTION 1 INTO YOUR CODING AGENT

## 1. Master implementation prompt

Act as a senior software architect, Python/FastAPI engineer, React/TypeScript engineer, clinical knowledge systems engineer, content-rights engineer, clinical education designer, test engineer, and release engineer.

Implement the complete set of HSPTL 5.0.0 next increments directly in the existing repository. This is an implementation task, not a planning-only task. Preserve all existing features, local data, the verified Synthetic Data Factory, the clinical simulation, learning library, content factory, UCKS, institutional/governance functionality, and the current seven core engines.

The deliverables are:

1. Complete a rights-aware medical source registry by extending UCKS.
2. Implement a safe, read-only Local Folder Source Manager with scheduled rescanning using the existing job infrastructure.
3. Implement consistent four-label provenance: GENERATED CONTENT, IMPORTED CONTENT, SYNTHETIC CONTENT, and DERIVED CONTENT.
4. Implement the Daily Clinical Case Lottery as a shared learner feature, available from Ward Board and Clinic.
5. Integrate the seven shared core engines across all six existing workspace skins and their actual product areas.
6. Extend the Clinical Knowledge & Pearls Factory with deterministic, source-linked templates and the prioritized source catalogue.
7. Add the cross-workspace content lineage, source evidence, analytics, review and publication interfaces required to operate these features.
8. Produce documentation, migrations, tests, release notes and a final package.

Do not stop after architecture notes or scaffolding. Inspect the repository, implement the work, run one consolidated verification cycle after implementation, correct defects found, and report exact results. Do not claim completion for features that remain blocked or unverified.

### 1.1 Repository preflight — mandatory

Inspect the checked-out repository before editing. Do not assume that the uploaded ZIP and current working tree are identical.

The uploaded ZIP was inspected and contains:

- `backend/hsptl_core/ucks.py` and supporting UCKS modules for source/document storage, versioning, chunks and SQLite FTS5 retrieval.
- `backend/hsptl_core/ucks_connectors.py` with existing Europe PMC, PubMed, Crossref and ClinicalTrials.gov discovery/integration paths, connector schedules/checkpoints and identifier reconciliation.
- `backend/hsptl_core/ucks_rights.py` and rights-review API.
- Existing evidence appraisal, lifecycle revisions, knowledge graph, terminology mapping, source surveillance and governance monitoring.
- `backend/hsptl_core/ucks_files.py`, which currently extracts text from PDF, TXT, Markdown, CSV, TSV, JSON, JSONL and DOCX uploads, with a 20 MB single-file limit.
- `backend/routers/ucks.py`, `frontend/src/pages/DataToolsPage.tsx`, `frontend/src/pages/PearlsPage.tsx`, `frontend/src/pages/ContentFactoryPage.tsx`, and the existing UCKS/Content Factory frontend integration.
- `backend/hsptl_core/jobs.py`, `backend/runtime.py`, SQLite storage, the canonical Kernel and deterministic event engine.
- Six presentation-only skins in `frontend/src/hsptl40/skinRegistry.ts`: `clinic`, `rounds`, `lab`, `ward`, `exam`, `portfolio`.
- The seven core engines: Kernel, Reasoner, Logic (PROforma), Composer, Router, Guards and Explain.

The uploaded ZIP reports `APP_VERSION` and frontend package version 5.0.0, but its root `RELEASE_STATUS.md` still identifies a 3.0.0 release candidate. Reconcile this documentation mismatch before packaging.

**Synthetic Data Factory discrepancy:** The user's subsequent implementation report states that a full Synthetic Data Factory was implemented and verified in the working tree, with 9 release gates passing, 365 tests passing, 78 factory tests, and a regenerated manifest. However, the uploaded ZIP inspected as a baseline primarily shows MedNoteGen/Synthea ingestion and does not visibly contain the complete later factory implementation described in that report. Therefore:

- Treat the current local working tree containing the reported Synthetic Data Factory implementation as authoritative.
- Do not replace the working tree with the uploaded ZIP.
- Do not delete, rename, reimplement or downgrade the reported Synthetic Data Factory.
- Before coding, locate its actual modules, migrations, APIs, UI, tests and report. Record their paths in the implementation map.
- If the current checkout does not contain the reported Synthea factory implementation, stop feature implementation and report the baseline mismatch. Do not state that the Synthea factory is present merely because the user reported it.
- Preserve the user's previously reported one-time verification results as historical report data; run the requested new consolidated verification only after all new changes are complete.

### 1.2 Existing infrastructure to extend, not duplicate

Reuse these systems after inspecting their exact implementation:

- **UCKSRepository:** source records, documents, immutable document versions, text chunks, FTS5 retrieval, lifecycle, knowledge graph and workspace-aware retrieval.
- **UCKS connectors:** existing literature discovery connectors, connector checkpoints, scheduled sync, identifier reconciliation and run history.
- **UCKS rights and appraisal:** rights decisions, rights scope, reviewer, rationale, evidence appraisal and histories.
- **UCKS monitoring/surveillance:** source health, evidence aging and governance snapshots.
- **Existing file extraction:** extend it safely; do not introduce an unrelated upload service.
- **JobRunner/background_jobs:** use existing durable jobs, lease, heartbeat, checkpoints, retry/backoff and cancellation. Do not create a second job queue or scheduler.
- **SQLite/StudyStore and migrations:** persist metadata and indices locally. Keep large original documents and media as file-backed artifacts, not huge SQLite blobs.
- **Kernel/event ledger:** one canonical append-only event history. Add event types to all required registries/catalogues and test that catalogues do not drift.
- **Existing Content Factory and generated-artifact/review/distribution lifecycle:** add templates and outputs without rebuilding content generation or release systems.
- **CaseRepository/FHIR import and existing case/debrief/OSCE/assessment repositories:** reuse their data contracts and route boundaries.
- **Existing shared tag/competency system:** connect content to existing stable tag IDs; do not create a parallel taxonomy.
- **Existing six workspace skins:** presentation only. Do not put clinical facts, thresholds, evidence, executable predicates or routing rules in `skinRegistry.ts`.

Do not add microservices, external database servers, Redis, message brokers, vector databases, embedding models, LLMs, hosted AI, API-key requirements, or alternate executable rule engines. Keep deterministic lexical FTS5 retrieval and approved graph/terminology expansion. PROforma remains the only executable workflow/decision language.

### 1.3 Mandatory non-negotiable safety and data rules

1. Preserve existing patient records, user data, review history, generated artifacts and Synthea run history.
2. Raw imported source files and raw Synthea exports remain immutable.
3. Every transformed or extracted item is a separate derived artifact with lineage to its raw source.
4. Never treat free-to-read as permission to copy, adapt, redistribute or make derivative works.
5. Rights status, clinical review status, source validity, evidence certainty and publication status are independent dimensions.
6. Never fabricate missing patient findings, laboratory results, diagnoses, medication instructions, dates or clinical facts.
7. Do not turn extracted prose into a clinical recommendation unless the claim is explicitly supported and meets the review gate for its risk.
8. Do not treat source reputation or automated score as proof that an individual claim is correct.
9. Do not equate abnormal measurements with data errors. Preserve clinically meaningful abnormal values.
10. Imported, generated, synthetic and derived content must retain distinct labels and full multi-source lineage.
11. Link-only sources must remain link-only. Do not copy their protected content into a local case or use it to generate derivative content without permission.
12. The lottery may only select cases meeting the eligibility, rights and publication rules below. If no case qualifies, it must return an explicit no-eligible-case state; never invent one.
13. Prevent answer leakage before the learner submits or explicitly reveals an answer.
14. For local content, reject or quarantine suspected direct identifiers and protected health information unless an approved institutional basis and de-identification workflow exists.
15. Do not expose arbitrary filesystem browsing through an HTTP endpoint. Use a configured set of allowlisted local source roots and restrict folder selection to the local administration workflow.
16. Protect against path traversal, symlink/reparse-point escapes, Windows junctions, hardlink surprises, filename collisions, malicious archives, oversized files, decompression bombs and active content.
17. Never execute macros, embedded scripts, HTML scripts or document attachments.
18. Keep the application bound to loopback by default unless the existing authenticated institutional deployment explicitly permits otherwise.
19. Maintain the no-LLM/no-AI-API requirement. All content assembly must be deterministic, template-based and evidence-linked.
20. Keep the platform educational. It must not be represented as live-patient clinical decision support or a substitute for institutional clinical governance.

---

# 2. Target architecture and deliverables

## 2.1 The three production factories

Keep three separate production domains, sharing registries, provenance, quality, review, publication and core engines.

### A. Clinical Knowledge & Pearls Factory — independent of Synthea

Purpose: discover and organize clinical teaching knowledge from permitted online references and approved local files; produce structured educational derivatives.

Initial outputs:

- Clinical pearls.
- ECG interpretation pearls.
- Laboratory interpretation pearls.
- Radiology spotters and explanations.
- Physical examination pearls.
- Spot-diagnosis exercises.
- Medication information/medication-safety pearls.
- Clinical reasoning exercises.
- Procedure and skills teaching notes.
- Lecture/teaching summaries, flashcards, viva prompts and question sets.

The Clinical Knowledge Factory must not use Synthea records as its general knowledge source.

### B. Synthetic Data Factory — Synthea only for synthetic patient generation

Preserve the already implemented factory reported by the user. It remains responsible for synthetic population generation, FHIR/CSV export, technical and plausibility validation, immutable artifacts, run provenance, quarantine, accepted fixture registration and reports.

Do not move general clinical pearls, medical reference extraction or educational article ingestion into this factory.

### C. Clinical Case & Simulation Factory — patient-context production

Purpose: create case packages from one or more permitted case inputs:

- Synthea synthetic patient records.
- Authorized external clinical case reports and educational cases.
- Authorized local case files.
- HSPTL-generated case structures based on referenced clinical knowledge.
- Multi-origin derived case packages.

It must retain the distinction between a source case reproduced under a licence, a generated case structure, a synthetic patient case, and a hybrid derived case.

## 2.2 Shared services

The three factories share:

- UCKS Source Registry.
- Rights & Licensing Review.
- Immutable Document and Document Version Registry.
- Claim/Fact/Evidence Registry.
- Source and Claim Appraisal.
- Terminology and Competency Graph.
- Four-label Provenance and Lineage.
- Content Quality and Deduplication.
- Review/Approval/Publication Lifecycle.
- Shared tags and specialty classification.
- Daily Case Lottery.
- Seven core engines.
- Existing JobRunner and Kernel.

No parallel registries for the same concept should be created.

---

# 3. Increment 1 — Rights-aware UCKS Source Registry

## 3.1 Extend the existing UCKS source model

Inspect current schemas before migrating. Add only missing fields through additive migrations. Preserve current source IDs and historical records.

Each source record should support:

- `source_id` (stable internal ID).
- `display_name` and `provider_name`.
- `source_family` (open_education, medical_reference, case_report, image_repository, drug_label, local_folder, institutional_upload, synthetic_generator, research_index, other).
- `source_type` (online_api, rss_atom_feed, manual_link, local_folder, local_file, licensed_import, public_domain_repository, synthetic_dataset).
- `canonical_home_url`.
- `official_api_url` / `feed_url` when one exists.
- `publisher_or_owner`.
- `authors_or_contributors` where available.
- `source_license`, `license_uri`, `license_version`, `license_evidence_uri`.
- `rights_status`: unknown, pending_review, public_domain_verified, cc0_verified, cc_by_verified, cc_by_sa_verified, noncommercial_only, no_derivatives, permission_required, link_only, restricted, expired_or_revoked.
- `reuse_scope`: metadata_only, abstract_only, full_text_reuse, image_reuse, adaptation, redistribution, internal_local_use.
- `commercial_use_allowed` (true/false/unknown).
- `derivatives_allowed` (true/false/unknown).
- `attribution_text` and `sharealike_obligations`.
- `machine_access_policy` and `rate_limit_policy`.
- `jurisdictions` and specialties.
- `last_checked_at`, `last_success_at`, `last_error_at`.
- `source_active`, `connector_status`, `review_required`.
- Source reliability appraisal profile, last appraisal version and reviewer.

Rights must be resolved at the smallest relevant asset/document unit. Source-level defaults are not enough when a page contains differently licensed figures, images, tables or third-party excerpts.

## 3.2 Keep independent governance dimensions

Do not overload the existing `review_status` or UCKS lifecycle. Expose separate axes:

- Ingestion status: discovered, metadata_imported, downloaded, extracted, failed.
- Rights status: unknown, pending, permitted, restricted, link_only, needs_clarification.
- Clinical review status: unreviewed, in_review, reviewed, approved_for_education, rejected.
- Evidence status: unassessed, appraised, supported, limited, conflicting, unsupported.
- Document lifecycle: current, superseded, corrected, retracted.
- Publication status: draft, staged, published, withdrawn.

A technically successful import must not mark rights as permitted or clinical content as approved.

## 3.3 Source-specific initial collection

Register the following provider records. Do not assume each source has an API or permission for full-text ingestion.

### User-prioritized clinical teaching providers

1. LITFL — link-first by default; source-specific API/feed only if officially documented; request permission before adapting protected content.
2. AHRQ PSNet / WebM&M — historical patient-safety case discovery; metadata and links by default; require explicit permission for reproduction/derivatives.
3. ARUP Consult — laboratory interpretation; metadata/link-first unless documented reuse permission exists.
4. Radiopaedia — imaging and radiology spot diagnosis; asset-by-asset licence checks; link-first by default.
5. DailyMed — official SPL/drug label structured data integration; retain label source, SetID, version, update dates and label section references; do not imply US labels are Egyptian registrations.
6. Manual of Medicine — spot diagnosis and clinical pearls; link-first absent explicit permissions/API.
7. Pathognomonic/Pathognomics — do not guess the provider URL. Register as `needs_configuration` until the user-verified exact URL and publisher identity are recorded.
8. Morning Reports — treat as a content format/source collection, not a single assumed website. Support local folder/import and publisher-specific providers.
9. Clinical Problem Solvers — clinical reasoning and case teaching; link-first unless an official export or licence supports more.
10. SGIM — case vignettes and teaching cases; article-level rights, author permissions and patient privacy checks.
11. EMCrit/IBCC — critical care pearls; link-first unless authorized reuse is documented.
12. Medscape — clinical pearls/educational resources; link-first unless a licence or partner API authorizes ingestion.

### Additional open/reuse candidates

Register these as candidate sources with exact item-level permissions:

- Open RN (CC BY 4.0 materials; retain attribution and source/version metadata).
- MedEdPORTAL (per-publication CC BY, CC BY-NC or CC0; inspect publication licence and files).
- WikEM (CC BY-SA 3.0 where the specific page/asset is covered; preserve ShareAlike and attribution; verify media exceptions).
- PLOS (generally CC BY 4.0 articles; inspect individual article and third-party figure rights).
- PubMed Central Open Access Subset (article-level licence; prioritize CC BY/CC0 for adaptation; respect OA Subset retrieval terms).
- Europe PMC (discovery and full-text acquisition only where article rights permit).
- Cureus (article-specific published content, generally CC BY; verify the article licence and content rights).
- CDC Public Health Image Library (verify per-image public-domain or other rights status).
- NCI Visuals Online (verify image-level copyright/credit and third-party rights).
- Wellcome Collection (item-level rights; use official API where permitted).
- MedlinePlus (use only clearly identified public-domain/NLM-owned material; third-party components excluded).
- Open Textbook Library (book- and component-level licence; exclude ND from adaptation; respect NC/SA terms).
- OpenStax (verify exact book and component licence; do not assume all material is commercially reusable).

The source catalogue should support `enabled_for_discovery`, `enabled_for_metadata`, `enabled_for_full_text`, `enabled_for_adaptation`, and `enabled_for_lottery` independently.

## 3.4 Connector policy

- Reuse existing Europe PMC, PubMed, Crossref, ClinicalTrials.gov and current supported connectors.
- Add only official/documented APIs, OAI-PMH, RSS/Atom feeds, official export files or user-provided imports.
- Use source-specific adapters, not a generic website scraper.
- Do not bypass robots, paywalls, login walls, CAPTCHAs, rate limits or publisher terms.
- No mandatory API keys. Optional keys may be configured only where a source requires them; the baseline platform must remain usable without them.
- Respect ETags/Last-Modified, cursor checkpoints, backoff, bounded downloads and existing connector schedules.
- For sources without a reliable machine-readable interface, provide metadata-only/manual-link registration.
- Record connector version, query, fetch date, HTTP status, source identifier, provider identifier and raw response hash.
- Store source metadata even when full text cannot be retained.

---

# 4. Increment 2 — Local Folder Source Manager

## 4.1 User experience

Add a Local Sources section in Data Tools with:

- Add source root (native local-folder picker where supported, plus a typed path fallback).
- Display configured folder roots and their status.
- Choose an optional collection name and default provenance label.
- Configure allowed extensions, recursion depth and maximum file sizes.
- Scan now, pause, resume, rescan changes, disable source, remove registration (without deleting originals).
- Show discovered files, new/changed/unchanged/removed candidates, extraction results, duplicates and quarantined files.
- Schedule scans using existing JobRunner; provide an explicit opt-in and visible last/next scan.
- Never silently move, rename, modify or delete files in the user's source folders.

## 4.2 Security boundary

- Store explicitly allowlisted canonical roots in local settings/DB.
- Resolve all candidate paths and verify they remain under an allowlisted root.
- Do not follow symlinks, Windows junctions, reparse points or paths escaping the root.
- Reject UNC/network shares by default unless an administrator explicitly enables them.
- Protect against path traversal, hardlink/symlink tricks, filename collisions and case-insensitive path collisions.
- Use read-only access. Do not execute files, macros, HTML scripts, JavaScript, OLE objects or attachments.
- Enforce per-file and per-scan total size limits and maximum recursion depth.
- Validate archive entries before processing OOXML containers. Reject path traversal inside ZIP/OOXML entries and decompression bombs.
- Do not automatically OCR scanned PDFs in this increment. Mark them `needs_ocr` and quarantine/exclude from text-based extraction; a later OCR feature can be separately approved.
- Do not automatically use image recognition or OCR models. Images can be registered as media assets with metadata/hash and a manual rights/clinical caption workflow.
- Flag likely direct identifiers/PHI for quarantine. Use conservative local pattern detection and a review queue; do not claim that regex screening is complete de-identification.

## 4.3 Supported file formats

Preserve existing safe formats:

- PDF text layer.
- TXT, Markdown, HTML (sanitized text only; scripts/styles/active content stripped).
- CSV, TSV.
- JSON, JSONL.
- DOCX.

Add safe extraction/registration for:

- PPTX (read-only OOXML slide/notes text; reject PPTM and macros).
- PNG, JPG/JPEG, WebP (register immutable media file and metadata; no automatic content claims).

Do not add DOCM, PPTM, XLSM, executable formats or arbitrary ZIP imports. Validate MIME and magic bytes; never trust filename extensions alone.

## 4.4 File identity and change detection

For each file, record:

- `local_source_id`, `relative_path`, `canonical_path_hash` (avoid exposing full path to learners),
- `sha256`, byte size, extension, detected MIME, modified time, extraction version,
- original filename, import time, scan ID, extraction status, provenance label,
- rights declaration and reviewer state.

Use content hash for duplicate detection. If a file changes, create a new immutable UCKS document version; do not overwrite the original version. Removed files should be marked `missing_from_source` or `source_removed`, not deleted from the audit history.

## 4.5 Folder scan API and job lifecycle

Extend the current UCKS routes and JobRunner using the repository's conventions. Suggested APIs (adapt naming to existing patterns):

- `GET /api/ucks/local-sources`
- `POST /api/ucks/local-sources`
- `GET /api/ucks/local-sources/{id}`
- `PUT /api/ucks/local-sources/{id}`
- `POST /api/ucks/local-sources/{id}/scan`
- `POST /api/ucks/local-sources/{id}/pause`
- `GET /api/ucks/local-sources/{id}/scans`
- `GET /api/ucks/local-scans/{scan_id}`
- `POST /api/ucks/local-files/{document_id}/rights-declaration`

All local scanning jobs must be durable, cancellable, resumable with checkpoints, bounded, idempotent and visible in the Data Tools job queue.

---

# 5. Increment 3 — Four-label provenance and content lineage

## 5.1 Canonical visible labels

Use exactly these user-facing labels (case and spelling consistent across all workspaces):

1. `GENERATED CONTENT` — HSPTL assembled original educational content from approved source claims, templates, rules and/or authored content.
2. `IMPORTED CONTENT` — externally authored material or user-supplied material retained/imported under the relevant rights, or metadata/link records imported from a provider. The interface must distinguish full-text reproduction from metadata/link-only records.
3. `SYNTHETIC CONTENT` — synthetic patient records or patient histories produced by Synthea or another explicitly identified synthetic generator.
4. `DERIVED CONTENT` — a new item that combines two or more origins or transforms/imports material into a new educational artifact, such as an HSPTL case built around a synthetic patient and an authorized teaching template.

These labels are provenance categories, not quality or approval badges.

## 5.2 Structured provenance contract

Every content item must include:

- `provenance_label` (one of the four labels).
- `provenance_components[]` with component label, source/document ID, version, exact asset/section locator, rights scope and hash.
- `generation_method` (manual, deterministic_template, transformed_import, synthetic_generator, composite).
- `generator_name`, `generator_version`, `template_id`, `template_version`, `seed` where applicable.
- `source_document_ids[]`, `source_claim_ids[]`, `source_dataset_id` and `synthea_patient_id` where applicable.
- `transformation_manifest` with ordered steps, code/version, settings and output hash.
- `attribution_text` and required licence notices.
- `clinical_review_status`, `rights_status`, `evidence_status`, `publication_status` as independent fields.
- `created_at`, `updated_at`, `content_hash`, `lineage_hash`.

A derived item must preserve every contributing origin. Do not replace lineage with a single simplified parent ID.

## 5.3 UI presentation

- Show the provenance badge on cards, detail pages, case headers, question details and exports.
- Selecting the badge opens a provenance panel with source records, rights scope, transformations and source versions.
- `GENERATED CONTENT` is not synonymous with clinically approved.
- `IMPORTED CONTENT` is not synonymous with permission to redistribute.
- `SYNTHETIC CONTENT` must clearly say the patient is simulated, not a real patient.
- `DERIVED CONTENT` shows all source components, not just its final generator.

## 5.4 Migration/backfill

- Additive migration only.
- Preserve historical content labels already assigned by the application.
- Backfill only when source lineage provides sufficient evidence.
- Unknown provenance must remain `unknown/pending_classification` internally and must not be guessed into one of the four labels. UI may show `PROVENANCE UNVERIFIED` until classified.
- Add tests proving all newly produced records receive a valid label and lineage.

---

# 6. Increment 4 — Daily Clinical Case Lottery

## 6.1 Product behavior

Add **Daily Case Lottery** as a shared learning feature:

- Prominent card on Ward Board / Overview.
- Dedicated page or route under Clinic.
- Optional directory entry under the hospital identity/navigation system.
- Admin configuration and source-pool monitoring in Data Tools.

The tagline may be: **One case. One clinical challenge. Every day.**

It must select from all four provenance labels, multiple online source collections and configured local folders.

## 6.2 Candidate eligibility

A candidate may enter the lottery only if:

- It is a valid case or a valid external-link challenge.
- It has a stable ID and immutable content/version hash.
- Its provenance is classified and lineage is preserved.
- It has a source record and source locator.
- Rights permit the exact in-app use. If only a link is allowed, the lottery must open the publisher's original page and must not copy the protected content into HSPTL.
- Its review/publication status meets the configured challenge policy.
- It has no unresolved privacy/PHI flags.
- It is not superseded/retracted/withdrawn or otherwise ineligible.
- It has an adequate case manifest: specialty/topic, task type, learner level, difficulty or an explicit `unknown` value.

For a link-only challenge, HSPTL may show permissible metadata and a user-authored HSPTL question only if that question is independently sourced and not a derivative of protected expression. Otherwise show a source link only.

## 6.3 Selection policy

Implement a deterministic weighted lottery using the existing Router, not an unrelated random-selection framework.

Required configuration:

- local timezone (default system/user timezone; do not hardcode UTC or Egypt).
- eligible specialties and topics.
- difficulty bands and learner level.
- four provenance label weights.
- source weights or source diversity cap.
- recency window.
- case-repeat cooldown.
- source-repeat cooldown.
- per-day reroll count (default 1, configurable).
- whether external link-only challenges are eligible.

Default policy:

- Equal initial weight across available provenance labels, then renormalize among labels with at least one eligible candidate.
- Avoid domination by a large source collection by using staged selection: first choose provenance group, then source collection, then case.
- Prefer cases not completed by the learner recently, while retaining a controlled exploration path if the candidate pool is small.
- Avoid drawing the exact same case for the same learner during the cooldown window unless explicitly allowed.
- Use source diversity to avoid repeatedly drawing from one provider.
- Do not claim balanced coverage when the candidate pool does not support it; show actual eligible pool counts.

Deterministic draw identity:

`learner_or_local_profile_id + local_date + policy_version + lottery_scope`.

Persist the selected case and pool snapshot. Same learner + local date + policy version must return the same saved draw after refresh/restart. An optional reroll creates a new recorded selection and consumes the configured reroll allowance. Do not redraw automatically because the source pool changes later that day.

If no case is eligible, show an honest empty state with reasons and the next available action. Never generate a fictional case to fill the slot.

## 6.4 Progressive case-solving workflow

Use the existing PROforma runtime to implement the learner flow. Suggested stages:

1. Case teaser / presenting complaint.
2. Initial history and context.
3. Additional history, examination or clues (revealed in controlled stages).
4. Investigations / images / observations.
5. Problem representation.
6. Differential diagnosis.
7. Most likely diagnosis or requested clinical interpretation.
8. Reasoning justification and next-step question, if appropriate.
9. Debrief, pearls, source references and related learning activities.

The learner may submit a staged answer. Do not reveal hidden case data or answer keys before the corresponding stage is completed or explicitly revealed.

Support multiple defensible answers where the case and assessment design permit them. Do not impose a single answer solely because the source's original author selected one.

## 6.5 Daily lottery events

Register event types in both the deterministic engine `EVENT_CATALOG` and HSPTL event contracts/catalogue, using matching names and semantics. Suggested events:

- `learning.daily_case.pool_snapshotted`
- `learning.daily_case.drawn`
- `learning.daily_case.rerolled`
- `learning.daily_case.opened`
- `learning.daily_case.stage_revealed`
- `learning.daily_case.answer_submitted`
- `learning.daily_case.completed`
- `learning.daily_case.debrief_opened`
- `learning.daily_case.draw_abstained`

Event payloads contain IDs, hashes, versions, selection reason codes, timestamps, state transitions and counts—not full patient FHIR Bundles or full documents.

Use idempotency keys for draw/open/submission operations. Add event-catalog drift regression tests.

## 6.6 Daily lottery APIs

Adapt to existing router style, but provide equivalent behavior:

- `GET /api/daily-case/status`
- `POST /api/daily-case/draw`
- `POST /api/daily-case/reroll`
- `GET /api/daily-case/today`
- `GET /api/daily-case/{draw_id}`
- `POST /api/daily-case/{draw_id}/open`
- `POST /api/daily-case/{draw_id}/reveal`
- `POST /api/daily-case/{draw_id}/answer`
- `POST /api/daily-case/{draw_id}/complete`
- `GET /api/daily-case/history`
- `GET /api/daily-case/admin/pool-stats`
- `PUT /api/daily-case/admin/policy`

Use the current institutional/user identity model where available. Do not assume a global single-user ID if the updated checkout has user identities. Do not claim real production multi-tenancy; enforce existing local authorization boundaries and report remaining deployment limitations honestly.

## 6.7 Frontend requirements

Ward Board:
- Daily Case Lottery feature card.
- Drawn case, specialty, difficulty, time estimate and provenance label.
- Status (not started, in progress, completed).
- Draw/continue action.

Clinic:
- Dedicated progressive challenge experience.
- Current case stage and answer form.
- Source and provenance panel.
- Reveal controls with clear consequences.
- Debrief and related pearls/cases links.

Data Tools:
- Eligible pool counts by provenance label, source and specialty.
- Ineligible/quarantined candidate reasons.
- Lottery policy editor.
- Draw audit and selection reason viewer.

Accessibility:
- Keyboard navigation, visible focus, semantic headings, readable disclosure controls, responsive layout and honest empty/error/loading states.

---

# 7. Increment 5 — Clinical Knowledge & Pearls Factory

## 7.1 Source priorities

Create source profiles and connector capability records for the user's priorities. The order is important:

### Core clinical pearls and teaching sources

- LITFL — ECG, emergency medicine, critical care, toxicology, ultrasound, procedures; link-first or permission-aware reuse.
- EMCrit / IBCC — critical care and emergency physiology/pearls; link-first unless reuse permission is confirmed.
- Medscape — clinical pearls and education; link-first/licensed integration only unless rights permit more.
- Manual of Medicine — spot diagnosis and concise clinical teaching; link-first until reuse is documented.
- Pathognomonic/Pathognomics — do not infer URL; await verified provider identity/URL.

### Specialist sources

- ARUP Consult — laboratory testing and interpretation; apply its stated reuse terms.
- Radiopaedia — radiology and imaging spotters; per-image/page rights, default link-first.
- DailyMed — structured drug labels and safety data; retain SetID/version/section/update information and distinguish US labels from local regulatory registration.
- AHRQ PSNet / WebM&M — historical safety cases; link/metadata by default until explicit rights permit reproduction.
- Morning Reports — treat as a case format or local/provider-specific source, not as one assumed publisher.
- Clinical Problem Solvers — reasoning frameworks and cases; use officially authorized material.
- SGIM — clinical vignettes; article-level rights and privacy checks.

### Open/reuse collections

- Open RN.
- MedEdPORTAL (publication-level licence).
- WikEM (CC BY-SA unless an item says otherwise).
- PLOS (article-level CC BY, with third-party media checks).
- PMC Open Access Subset (article-level licence; prioritize CC BY/CC0 for adaptation).
- Europe PMC.
- Cureus (article-level licence).
- CDC PHIL (asset-level rights).
- NCI Visuals Online (asset-level rights).
- Wellcome Collection (item-level licence/API).
- MedlinePlus (NLM-owned/public-domain portions only).
- Open Textbook Library (book/component licence).
- OpenStax (exact book/component licence; verify NC restrictions).

Do not treat this list as an instruction to scrape. Register provider profiles and implement adapters only where officially documented and permitted. Other sources are metadata/link-only connectors.

## 7.2 Clinical pearl templates

Create versioned JSON schemas and deterministic composers for these types:

1. `diagnostic_clue_pearl` — clue, interpretation, implications, differential, limitations, citations.
2. `physical_exam_pearl` — technique, normal finding, abnormal finding, significance, pitfalls, limits.
3. `interpretation_pearl` — ECG/lab/ABG/imaging, steps, pattern, caveat, clinical context.
4. `differential_pearl` — presentation, candidate diagnoses, supporting/opposing findings, discriminators.
5. `medication_safety_pearl` — medicine, label section, adverse effects, interactions, contraindications, monitoring; never invent dose instructions.
6. `emergency_recognition_pearl` — recognition cues, red flags, deterioration concern, escalation context, source.
7. `procedure_pearl` — indication, setup, steps, safety, complications and references; high-risk procedure material requires review.
8. `clinical_pitfall_pearl` — common misconception, why it occurs, correction, supporting source and limitations.
9. `clinical_reasoning_pearl` — problem representation, discriminating clues, alternatives, reasoning trap and takeaway.
10. `spot_diagnosis_item` — permitted image/media asset, clinical prompt, answer, key features, differential, teaching explanation and image rights.
11. `lab_interpretation_item` — test, specimen, unit, reference interval where supplied by source/lab, pattern, limitations and clinical context.
12. `radiology_spotter` — image, modality, view/sequence, visible features, likely interpretation, alternatives, limitations and image rights.
13. `drug_label_fact` — structured SPL section and exact label locator; not a treatment recommendation.

All generated items must include target learner level, specialty, task type, competency/learning objective tags, provenance, source claims, rights scope, version, review status and content hash.

## 7.3 Source extraction and claim registry

Use existing UCKS document versions and chunks. Add an explicit claim/fact layer if missing:

- claim ID, normalized statement, claim type, subject/predicate/object or typed fields,
- source document/version ID, exact locator (page, heading, paragraph, table, figure, SPL section),
- original excerpt/hash where legally retained,
- supporting and contradicting references,
- author/date/jurisdiction/population where known,
- appraisal method and evidence certainty,
- status: proposed, corroborated, conflicting, unsupported, withdrawn,
- reviewer and rationale.

Do not copy large protected text extracts. Store short permitted quotations or source locators and links as appropriate to the licence. Generated paraphrases must be independently composed and must not substitute for permission to create derivatives.

## 7.4 No unsupported composition

- Composer assembles only approved claims, authored templates and permitted excerpts.
- If a required field lacks support, output `not established` or leave it explicitly missing.
- Do not fabricate a clinical fact to complete a template.
- Use `abstain` when a source claim is contradictory, unlicensed for the intended transformation, outdated or not sufficiently supported.
- New treatment advice, doses, contraindications, emergency management, procedure steps and high-risk interpretation require qualified review before publication.

## 7.5 Source and claim validity metrics

Implement two distinct HSPTL operational scores. These are governance indicators, not validated medical scales.

### Source Reliability Score (SRS), proposed 0–100

- Author qualifications/subject expertise: 15.
- Editorial/peer-review governance: 20.
- References and evidence transparency: 20.
- Currency and update transparency: 15.
- Specialty and learner-context relevance: 15.
- Conflict-of-interest transparency: 10.
- Independent corroboration: 5.

Visible bands: 85–100 strong, 70–84 moderate, 50–69 weak, below 50 unverified. Missing fields must not receive invented points. An unverified score remains provisional.

### Claim Support Score (CSS), proposed 0–100

- Direct support of the specific claim: 30.
- Underlying evidence quality/appraisal: 25.
- Independent corroboration: 20.
- Applicability to target population/jurisdiction/context: 15.
- Currency of supporting content: 10.

Visible bands: 90–100 strong support, 75–89 moderate, 50–74 weak, below 50 unsupported/unverified.

These numbers must be validated and calibrated against qualified independent appraisals before being described as validated measures. Preserve the component vector, missing-data flags, appraisal method and reviewer. Do not display a numerical score if required dimensions are missing; show `provisional/unrated`.

Use appropriate established appraisal tools by material type where relevant (e.g. source appraisal, study risk-of-bias method, educational design appraisal). Do not combine GRADE, AGREE II, AMSTAR 2, RoB 2 or other distinct instruments into one arithmetic score. Do not treat PRISMA or RIGHT reporting checklists as evidence-quality scores.

No clinical-practice-guideline source ingestion is in scope for this Clinical Pearls Factory increment. The focus is practical clinical teaching sources, educational resources, drug-label facts, clinical cases and research/educational material. Do not add a guidelines harvester.

---

# 8. Increment 6 — Content and template integration

Extend the existing deterministic Content Factory and generated-artifact store.

Outputs should include:

- clinical pearl cards.
- topic/skill summaries.
- spot-diagnosis exercises.
- ECG/lab/radiology interpretation exercises.
- medication-label learning items.
- SBA/MCQ sets with answer rationales.
- flashcards.
- viva prompts.
- OSCE stations/checklists.
- case reports and debriefs.
- related content collections and learning sequences.

The existing six outputs (`case_report`, `case_debrief`, `question_set`, `topic_summary`, `viva_set`, `osce_station`) must remain intact. New templates are additive and versioned.

Every generated artifact must record:

- content ID, content type, workspace destination;
- provenance label and full lineage;
- source/claim IDs and exact locators;
- rights/attribution text;
- template/version and composer version;
- deterministic seed only where variation is explicitly permitted;
- content hash, creation time and review status;
- evidence and source appraisal states;
- target learner level, specialty, tags and learning objectives.

Do not change clinical statement meaning or invent variation through randomization. Seeded randomization may change the order of distractor options only if the answer mapping is stable and regression-tested.

All newly generated content remains draft/reviewable by default. Do not automatically publish clinical teaching content simply because its source has a high SRS or CSS.

---

# 9. Increment 7 — Seven-engine integration across all workspaces

The seven engines are shared platform services, not seven separate implementations per workspace. Preserve the six presentation-only skins: Clinic, Rounds, Lab, Ward, Exam and Portfolio.

## 9.1 Core engine responsibilities

### Kernel
Canonical event history, audit, version references, source lineage, draw history, learner activity, job events, replay. Large files and patient bundles remain file-backed; events store IDs, hashes, counts and transitions only.

### Reasoner
Clinical concept graph, tags, terminology mapping, relationships between signs/tests/conditions, competency links and supported derivations. Unknown or unlinked concepts remain unresolved; do not force-match.

### Logic
PROforma remains the only executable workflow language. Use it for progressive case solving, OSCE flows, reviews, publishing gates, assessment lifecycles and daily case challenge states.

### Composer
Deterministic template and projection assembly. Build pearls, cards, cases, questions, debriefs, case challenge stages and dashboards from validated facts and approved templates.

### Router
Eligibility and selection, specialty/topic/difficulty matching, prerequisites, learning path sequencing, item scheduling and Daily Case Lottery. Provide stable reason codes and deterministic outcomes when the policy/seed/pool snapshot is unchanged.

### Guards
Rights, provenance, privacy, publication, review state, answer-leak protection, source currency flags, structural validity and permitted workflow actions. Fail closed or abstain on unresolved high-risk constraints.

### Explain
Claim/source support, content lineage, why-this-case selection, answer rationales, learner feedback, rubric points and simulation replay explanations.

## 9.2 Workspace mapping

### Ward Board / Overview (Portfolio skin)
- Kernel: activity, completion, review and daily draw history.
- Reasoner: knowledge gaps and competency relationships.
- Logic: learning path and challenge lifecycle.
- Composer: cards, activity summaries and learner view projections.
- Router: next pearl, case, review or Daily Case Lottery recommendation.
- Guards: prevent unsupported mastery claims and exclude ineligible activities.
- Explain: explain why each recommendation appears.

### Clinic
- Kernel: case opening, stage reveal, answer and completion events.
- Reasoner: signs, symptoms, findings, differential and diagnostic concept graph.
- Logic: progressive case workflow and answer gating.
- Composer: case narrative, timeline, clue and debrief assembly.
- Router: case selection and related-case recommendations.
- Guards: hide answer keys, verify rights and exclude unapproved/PHI cases.
- Explain: decisive findings, differential rationale and sources.

### Rounds
- Kernel: pearl/lecture/viva activity.
- Reasoner: specialty concepts and supporting claims.
- Logic: viva and structured teaching flow.
- Composer: pearls, lecture outlines, teaching summaries and revision packs.
- Router: topic and spaced-review selection.
- Guards: source rights, currency and clinical review requirements.
- Explain: claim-level citations and rationale.

### Diagnostics Lab
- Kernel: image views, spotter answers, OSCE attempts.
- Reasoner: visual signs, anatomy, investigations and competency links.
- Logic: station stages, timing and reveal control.
- Composer: spotters, media captions, station instructions and rubrics.
- Router: next visual/skill station.
- Guards: asset rights, privacy and critical checklist constraints.
- Explain: image feature and answer rationale.

### Ward workflows (On-Call, Handover, Consult, Clinical Progression)
- Kernel: tasks, actions, handovers and transitions.
- Reasoner: related clinical problems and constraints.
- Logic: PROforma-controlled workflows.
- Composer: handover, consultation, task plan and learning reflection.
- Router: valid next task and workflow sequencing.
- Guards: reject unsupported transitions and unsafe workflow actions.
- Explain: why a task is due, blocked or escalated.

### Exam Hall
- Kernel: exam sessions, attempts, timing and submission.
- Reasoner: item-to-concept and competency mapping.
- Logic: assessment workflow and submission rules.
- Composer: blueprint-balanced exam forms and question sets.
- Router: item selection by blueprint, difficulty and available calibrated data.
- Guards: answer-key security and session integrity.
- Explain: item rationale, source support and rubric calculation.

### Data Tools / Content Studio (Portfolio skin)
- Kernel: source ingestion, file scans, connector runs, rights reviews, generation and publication history.
- Reasoner: claim graph, terminology and competency mappings.
- Logic: ingestion, appraisal, approval and publishing lifecycles.
- Composer: all three factory outputs.
- Router: destination and review queue routing.
- Guards: local file safety, rights, privacy, quality and provenance.
- Explain: transformation history, exact source lineage and scoring components.

## 9.3 Shared contracts and engine observability

Implement common typed service interfaces and use runtime wiring from existing `backend/runtime.py` or its actual current successor. Do not create duplicate engine singletons.

For every engine-mediated operation, record:

- engine name/version;
- workspace and operation;
- input IDs/version hashes;
- output ID/hash;
- policy/model/template version;
- decision/reason code;
- abstention/guard reason if applicable;
- event references.

Expose a read-only engine health/contract dashboard in Data Tools. Do not expose raw internal state or secrets. Add contract tests to verify that each workspace uses shared engine interfaces and that skins remain presentation-only.

---

# 10. Increment 8 — Cross-workspace analytics and feedback

Build on existing tag-level activity and progress projections. Do not create new claims of psychometric validity.

Required views:

- Daily Case Lottery draws, completion, rerolls and provenance distribution.
- Cases by specialty, source, difficulty and content label.
- Clinical pearls viewed/recalled and related question performance.
- Spot-diagnosis and OSCE attempts by competency.
- Content source coverage, licence coverage and review backlog.
- Claim support/source reliability distribution with provisional/unknown values visible.
- Outdated, corrected, retracted and superseded material.
- Factory job throughput, acceptance, quarantine and error rates.

Analytics are descriptive/formative until validated. Do not infer clinical competence from views, clicks or completion alone.

---

# 11. Suggested database and API boundaries

Before adding tables, inspect current UCKS and repository schemas. Extend existing tables where appropriate; avoid duplicate source, rights, document, lifecycle or tag records.

Potential additive domain entities (names are suggestions, not a mandate if equivalent tables already exist):

- `ucks_source_capabilities`
- `ucks_local_source_roots`
- `ucks_local_source_scans`
- `ucks_local_file_manifest`
- `ucks_claims`
- `ucks_claim_evidence_links`
- `ucks_appraisal_snapshots` (reuse existing appraisal history if present)
- `content_provenance_components`
- `daily_case_policies`
- `daily_case_pool_snapshots`
- `daily_case_draws`
- `daily_case_attempts`

Every migration must be additive, reversible where possible, and safe with existing local databases.

All list endpoints require bounded pagination/limits. All mutating operations require idempotency where retries can create duplicates. Use stable resource IDs and explicit versioning.

---

# 12. Security, privacy and operational requirements

1. Run local source scans only under configured roots.
2. Ensure no endpoint accepts an arbitrary path and causes server-side scanning outside the allowlist.
3. Use file hashes and secure temporary files; no original overwrite.
4. Enforce safe archive extraction and MIME/magic-byte detection.
5. Apply bounded concurrency: one folder scan/large ingest at a time on 8 GB RAM unless configuration explicitly permits more.
6. Reuse current JobRunner with progress checkpoints, cancellation and restart recovery.
7. Ensure worker lifecycle is explicit; a queued job must not remain silently unprocessed. Respect existing worker opt-in/settings and document how to enable/disable it.
8. Keep external connector network access limited to registered source domains and official API endpoints. Protect against SSRF, redirects to private/internal IPs, DNS rebinding and oversized responses.
9. Apply source-specific rate limits and backoff.
10. Never fetch or render remote active content directly in the trusted application origin. External links open safely.
11. Enforce current authentication/roles and reviewer credentials where available, but do not overstate production RBAC/tenancy if remaining limitations exist.
12. Do not store source credentials in code or event payloads. Keep secrets out of logs and manifests.
13. Separate local-only path data from learner-facing exports.
14. Keep retention and backup controls consistent with the current institutional/privacy controls.

---

# 13. Testing and acceptance criteria

Add focused tests first, then one consolidated release verification after implementation is complete.

## 13.1 Source registry and rights

- Create/list/update sources without duplicating existing provider records.
- Source capability flags are independent.
- Public-domain/CC0/CC BY/CC BY-SA/NC/ND/unknown cases map correctly.
- Unknown rights never permit full-text or adaptation.
- A source-level licence does not override a conflicting per-asset licence.
- Rights-review and clinical-review states remain independent.
- Restricted providers are registered link-only and are not scraped.
- Revisions and retractions preserve historic versions and flags.

## 13.2 Local folder manager

- Scan an allowed directory and create a file manifest.
- Unchanged file hashes are idempotent.
- Changed files create immutable versions.
- Removed local files do not delete historical records.
- Reject path traversal, symlinks, junctions/reparse points and outside-root paths.
- Reject macro-enabled and unsupported file types.
- Reject oversized files, malicious OOXML entries, ZIP path traversal and decompression bombs.
- Ensure source root is never changed by ingestion.
- Ensure local path is not leaked into learner exports.
- Quarantine potential PHI rather than silently accepting it.
- Verify PDF, DOCX, PPTX, TXT, Markdown, JSON, CSV and image handling.

## 13.3 Provenance and lineage

- Every new generated/imported/synthetic/derived item receives a correct label.
- A multi-origin derived case stores every source component.
- A Synthea patient is visibly synthetic.
- An HSPTL-generated pearl is not labelled imported.
- An imported source is not presented as HSPTL-authored.
- Unknown provenance is not guessed.
- Source badge opens the full permitted lineage record.

## 13.4 Daily Case Lottery

- Selection filters out unlicensed, unreviewed, retracted, PHI-flagged and invalid candidates according to policy.
- Same learner/date/policy returns the same stored draw after refresh and restart.
- Candidate pool changes after draw do not silently replace today's case.
- Balanced source/label selection works and handles absent categories.
- No-case pool returns explicit abstention/empty state.
- Reroll limit and event history work.
- Learner cannot access hidden answer or later-stage data before reveal.
- Multiple defensible answers are handled by rubric configuration.
- External link-only candidate never copies protected text/images into HSPTL.
- Daily draw, stage reveal, response and debrief are event-backed and idempotent.
- Local timezone/date boundary is tested.

## 13.5 Factory and engine integration

- Existing six Content Factory outputs remain unchanged.
- New pearl/spotter/drug/visual templates validate against versioned schemas.
- No generated clinical claim lacks source/claim linkage or explicit authored-framework declaration.
- Unsupported claims abstain or remain draft with explicit reasons.
- All seven engines are shared and wired once.
- All six skins remain presentation-only; no clinical facts or rules in skin configuration.
- Workspace reason codes and explain traces are available.
- Both event catalogues stay synchronized.
- No duplicate event store, scheduler, job runner or source repository is introduced.

## 13.6 Regression and release verification

Preserve all existing Synthetic Data Factory tests and features. Add tests for the previously fixed defects:

- recipe transition targets resolved versions;
- engine event catalogue includes all event types;
- quarantine filenames cannot escape the quarantine directory;
- artifact filenames are validated, not trusted via `Path.name`;
- empty Synthea output fails closed;
- deterministic replay and idempotency.

Run:

1. Python environment and identity checks.
2. Python compile.
3. Content-pack/template validation.
4. All backend tests.
5. Frontend strict typecheck.
6. Frontend production build.
7. Launcher contract checks.
8. Local backend boot/health test.
9. Release manifest generation and self-verification.
10. ZIP integrity test and package verification.

Report test count, pass/fail, warning, skipped gates and environment limitations exactly. Do not claim all gates passed if any gate was skipped.

---

# 14. Implementation sequence — do not reorder foundational controls

### Phase 0 — Baseline and safety checkpoint

- Inspect current working tree, git status, existing database schema and release scripts.
- Confirm the reported Synthea factory files and tests exist.
- Make a recoverable local backup or documented checkpoint before editing.
- Record current version and feature inventory.
- Reconcile stale release documentation.
- Do not modify user data or reset SQLite.

### Phase 1 — UCKS Source Registry and rights capabilities

- Extend source metadata and capability fields.
- Add provider profiles for priority sources and open-access candidates.
- Build a source catalogue UI with connector/rights states.
- Add rights and licence details at document/asset level.
- Preserve current Europe PMC/PubMed/Crossref/ClinicalTrials integrations and existing UCKS records.

### Phase 2 — Local Folder Source Manager

- Add allowlisted local roots and scan manifests.
- Extend safe extraction and image/media registration.
- Reuse JobRunner and ingestion audit.
- Add Data Tools UI and security tests.

### Phase 3 — Four provenance labels and claim lineage

- Add canonical provenance contract and migrations.
- Backfill only when evidence exists.
- Update cards, content detail, case detail, document exports and factory outputs.
- Add multi-origin lineage display.

### Phase 4 — Daily Clinical Case Lottery

- Build eligible candidate view and deterministic Router selection policy.
- Persist pool snapshots/draws/attempts using existing SQLite and Kernel.
- Use PROforma for progressive case stages.
- Add Ward Board card, Clinic challenge flow and Data Tools controls.
- Add source/label fairness, exclusion and no-case abstention tests.

### Phase 5 — Clinical Knowledge & Pearls Factory

- Add templates and schemas for the pearl categories.
- Add official, licence-aware source adapters where possible.
- Link claims to UCKS docs and evidence records.
- Add visual spotter/media handling, lab/radiology/drug label structures.
- Connect outputs to Rounds, Lab and Exam Hall.

### Phase 6 — Seven-engine workspace integration

- Add shared contracts and orchestration facade if required by current architecture.
- Map the engines to Ward Board, Clinic, Rounds, Lab, Ward workflows, Exam Hall and Data Tools.
- Keep skins presentation-only.
- Add engine trace/health view and contract tests.

### Phase 7 — Cross-workspace analytics, docs and release

- Add lottery/source/content coverage analytics.
- Add operational runbooks and source onboarding policy.
- Run final consolidated verification once.
- Fix failures and re-run only affected focused tests as needed; do not conceal failed gates.
- Update release status, changelog, README, API docs, schemas, architecture diagrams and limitations.
- Package final release with manifest and ZIP integrity validation.

---

# 15. Required final deliverables

1. Updated HSPTL source repository preserving the user's verified Synthetic Data Factory.
2. Additive SQLite migrations.
3. UCKS source/provider registry enhancements.
4. Local Folder Source Manager and tests.
5. Four-label provenance and full content lineage.
6. Daily Case Lottery backend, UI, event contracts and tests.
7. Clinical Knowledge & Pearls templates, schemas and deterministic composers.
8. Seven-engine workspace integration and engine trace/health UI.
9. Source catalogue and rights onboarding documentation.
10. Daily Case Lottery user/administrator documentation.
11. Updated architecture, changelog and release status.
12. Complete consolidated verification report.
13. Final release ZIP and `MANIFEST.sha256`.

## 16. Explicit non-goals and known limitations

Do not claim or attempt to solve these through this feature increment:

- Clinical safety certification or institutional approval.
- Production SSO/MFA, enterprise identity or complete multi-tenant isolation unless separately implemented and independently assessed.
- Psychometric calibration without representative learner data.
- Live patient clinical decision support.
- Automatic permission to reproduce content from a website because it is publicly accessible.
- Clinical guideline ingestion (explicitly out of scope for this Clinical Pearls increment).
- OCR of scanned documents in the initial local-folder implementation.
- AI/LLM generation, neural embeddings or cloud AI API calls.
- Universal clinical NLP or automatic extraction of treatment rules.
- Automatic approval of new clinical protocols or high-risk assessment content.

The goal is a reliable local-first educational content system with automated discovery, safe ingestion, deterministic composition, source traceability, a useful daily case challenge and shared engine behavior—not an autonomous clinician.

---

# 17. READY-TO-PASTE RUN PROMPT

Use the following prompt in your coding agent after opening the **current HSPTL working repository** (the checkout containing the reported implemented Synthetic Data Factory). Attach or provide this directive file to the agent.

```text
Act as the senior implementation engineer for HSPTL 5.0.0.

Read the attached complete implementation directive in full and implement every included increment directly in the current repository. Do not return only a plan, architecture proposal, or scaffold.

FIRST: inspect the current checkout, git status, source tree, migrations, release scripts and existing tests. The current working tree is authoritative. Preserve the already implemented and reported verified Synthetic Data Factory, including its recipe lifecycle fix, event-catalog synchronization, quarantine filename hardening, safe artifact naming, fail-closed empty-output behavior, deterministic replay, scheduled jobs and all regression tests. Do not replace the working tree with an older ZIP.

The uploaded HSPTL-5.0.0.zip is an architecture/reference baseline. It includes a substantial UCKS implementation. Reuse and extend its UCKSRepository, UCKS connectors, rights reviews, evidence appraisal, document lifecycle, FTS5, knowledge graph, terminology, surveillance, Data Tools UI, Content Factory, CaseRepository, JobRunner, SQLite store, Kernel and seven engines. Do not duplicate these systems.

Implement the full sequence:
1. Rights-aware UCKS provider/source registry and priority/open-source provider catalogue.
2. Safe local folder source manager with allowlisted roots, immutable file manifests, file hashes, bounded extraction, scheduled rescans and PHI quarantine.
3. Four provenance labels: GENERATED CONTENT, IMPORTED CONTENT, SYNTHETIC CONTENT and DERIVED CONTENT, preserving full multi-source lineage.
4. Daily Clinical Case Lottery across eligible content from all four labels, online providers and configured local folders. Use deterministic Router selection, saved daily draws, pool snapshots, reroll limits, PROforma progressive case stages and Kernel events.
5. Clinical Knowledge & Pearls Factory with versioned deterministic templates for diagnostic clues, physical examination, ECG/lab/ABG/radiology interpretation, differential diagnosis, medication safety, emergency recognition, procedures, clinical pitfalls, clinical reasoning, spot diagnosis, lab interpretation and radiology spotters.
6. Shared seven-engine contracts and workspace integration across the six presentation-only skins and the actual areas: Ward Board, Clinic, Rounds, Diagnostics Lab, Ward workflows, Exam Hall and Data Tools.
7. Cross-workspace analytics, explanations, source/claim references, documentation, tests and release packaging.

Keep three factories distinct: Clinical Knowledge & Pearls Factory (not based on Synthea), Synthetic Data Factory (Synthea patient generation only), and Clinical Case & Simulation Factory (uses authorized cases and/or synthetic patients plus supported knowledge). Keep the seven shared engines: Kernel, Reasoner, Logic/PROforma, Composer, Router, Guards and Explain.

Keep HSPTL local-first, one modular monolith, one React app, one SQLite data layer, one canonical event ledger and one JobRunner. No microservices, external database, Redis, message broker, vector database, embeddings, LLMs, hosted AI or mandatory API keys. Use official/documented APIs, feeds, OAI-PMH or link-only provider profiles. Never scrape around paywalls, logins, rate limits, robots or source terms. Respect item-level licences and third-party asset rights.

No clinical-practice-guideline harvester is in scope for this increment. Focus on practical clinical teaching, clinical pearls, educational cases, laboratory and radiology interpretation, medication label facts, simulation and skills resources.

No imported item becomes approved merely because ingestion succeeded. No generated item becomes clinically approved because an automated score is high. Preserve the four labels and independent rights, clinical review, evidence, lifecycle and publication states. High-risk clinical content requires qualified review. If source support, rights, patient privacy or eligibility cannot be established, abstain, link-only or quarantine as defined in the directive.

Do not fabricate clinical findings or answers. Do not let the Daily Case Lottery select retracted, unlicensed, unreviewed, PHI-flagged or otherwise ineligible material. The lottery must return an explicit no-eligible-case result rather than fabricate a case. Same learner/date/policy must return the same persisted case. Hide answers until their stage is completed or revealed.

Add migrations and event definitions to all required event registries/catalogues. Add regression tests ensuring they cannot drift. Keep large content and FHIR artifacts file-backed and keep event payloads to IDs, hashes, versions, counts and state changes.

Before implementation, verify that the Synthetic Data Factory described above actually exists in this checkout. If it is absent, stop and report the mismatch; do not claim to preserve an unlocated implementation or reconstruct it from the stale ZIP. Do not overwrite local user data.

After implementation, run one consolidated verification including Python environment, identity scan, compile, content/schema validation, all backend tests, frontend typecheck, frontend production build, launcher checks, local API boot, event catalogue consistency, migration checks, manifest self-verification and ZIP integrity. Preserve exact gate results. Correct failures and execute focused regression tests as appropriate. Update README, changelog, architecture, API docs, source rights documentation and release status. Produce the final HSPTL 5.0.0 package and checksum manifest.

Implement now. Do not stop after planning. At completion, report what was implemented, what was reused, tests/build results, known limitations, exact package path, checksum, and installation instructions.
```

---

# 18. Operator run instructions

1. Open the current local HSPTL working tree containing the reported verified Synthetic Data Factory. Do not start from the older ZIP if it would replace newer uncommitted work.
2. Make a full recoverable copy of the working directory and current user-data directory. Do not delete or reset the SQLite database.
3. Open the repository in the coding agent.
4. Attach this Markdown directive.
5. Paste Section 17 as the execution prompt.
6. Let the agent inspect the repository and confirm that the current Synthetic Data Factory implementation is present before editing.
7. Require implementation of all seven phases, not just a subset.
8. Require one consolidated final verification and final package.
9. Review the final report. Do not use the product with real patient data or represent it as clinically validated/production-ready unless the separate governance and validation requirements are met.

