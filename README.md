<<<<<<< HEAD
# HSPTL — Clinical Learning Hospital

HSPTL is a local-first clinical learning environment built around **structured study, case reasoning, simulation, skills practice, assessment and debrief**. The learner experience opens with a learning dashboard and a populated starter library; the original Clinic, Rounds, Lab, Ward, Exam Hall and Portfolio capabilities remain available as in-process modules and routes. HSPTL is an educational product, not a healthcare provider or clinical decision-support system.

## HSPTL 5.2.0

This release simplifies the learner entry points, keeps specialist routes available in the All modules directory, and prepares local educational drafts automatically at startup. The global **Update content** action checks installed versioned packs from any workspace. Drafts are deterministic and remain subject to educator review; the refresh process never auto-approves or publishes clinical material. New output types cover on-call scenarios, handover templates and simulation briefs. See `CHANGELOG.md` and `RELEASE_STATUS_5.2.0.md`.

## HSPTL 5.1.0

The 5.0 release adds local password-backed institutional accounts, four-role RBAC sessions,
institution-scoped cohort and facilitation records, privacy/retention policies with audited purges,
SQLite backup and recovery manifests, bounded standards adapters, scenario trace/fault matrices and
clinical safety-case review records. Every governance route resolves an authenticated principal and
fails closed without one.

These controls improve deployment governance. They do **not** establish SSO/MFA, enterprise
encryption at rest, production multi-tenant isolation, validated clinical safety or independent
clinical approval. Read [Release Status](RELEASE_STATUS.md) before any institutional deployment.

Set `HSPTL_ADMIN_TOKEN` (32+ characters) and `HSPTL_INSTITUTION_ID` to enable governance routes.

### Synthetic data factory

Open **Synthetic data factory** to generate synthetic patient populations locally. The factory runs a
16-stage, resumable pipeline: preflight, population generation, export, inventory, six validation
dimensions, canonical normalisation, quarantine partitioning, idempotent import and provenance
registration.

It never downloads anything. Point it at a local Synthea artifact and pin the SHA-256 in the workspace
settings; generation fails closed without a pinned artifact, an exact version, a working Java runtime
and adequate free disk. The child process is started with an argument list and `shell=False`, so no
recipe value can become a shell command.

Validation keeps structural, reference, chronology, terminology, plausibility and completeness
findings separate. Plausibility rules check internal consistency and recordable ranges, never clinical
normality: an abnormal value is preserved unchanged, and the engine abstains when it has no reviewed
reference bound. Only failing patient bundles are quarantined; accepted patients still register.

Every dataset gets an immutable provenance manifest with a whole-document digest and a reproducibility
content digest. Identical inputs produce a byte-identical content digest. A cohort shortfall is
reported as `partial_cohort` and never padded.

Built-in recipes ship as drafts. Activating one requires `HSPTL_REVIEWER_TOKEN` and `HSPTL_REVIEWER_ID`
and records the reviewer and timestamp in the canonical event history. Strict FHIR conformance is
claimed only when a pinned HL7 validator runs.

Generation is automated. Clinical approval is not. Generated populations are synthetic, do not
represent any real population and must not inform clinical decisions.

Queued jobs run automatically when `HSPTL_ENABLE_WORKER=1`; otherwise use **Run now** in the workspace.

## HSPTL 4.0.2 architecture

HSPTL 4.0 retains the 3.0 application and six workspaces while adding deterministic intelligence as in-process modules in one modular monolith. It uses a bounded PROforma runtime as the only 4.0 executable logic language, a shared append-only event ledger, entailment and proof traces, fail-closed guards, derivation explanations, and closed-form routing/adaptivity. The D–F increment adds four-layer error-proofing and eight minimal implementation artifacts, with datasets kept as fixture/reference inputs rather than separate runtime infrastructure. The G increment enriches PROforma decisions with additive argumentation, adds rule-gated in-process SMT and versioned ASP temporal reasoning, renders clinical/pedagogical/negative explanations from one derivation trace, and makes IRT/FSRS/prerequisite/Brier adaptivity a reasoned router choice. No AI/ML or embedding models are loaded or called. See [HSPTL 4.0 Architecture](docs/HSPTL_4.0_ARCHITECTURE.md), [D–G deliverables](docs/hsptl40/DELIVERABLES.md) and [4.0 Release Status](RELEASE_STATUS_4.0.0.md) for boundaries and verification. The code-grounded plan for evolving HSPTL into an interactive, deterministic clinical learning simulation is in [HSPTL Clinical Learning Simulation Blueprint](docs/HSPTL_CLINICAL_LEARNING_SIMULATION_BLUEPRINT.md). The first runnable, event-backed vertical slice is the synthetic [adult moderate-asthma simulation](docs/HSPTL_CLINICAL_SIMULATION_VERTICAL_SLICE.md), available in Simulation Lab. The 4.0.1 learner experience adds the [Learning Library and Content Factory](docs/LEARNING_EXPERIENCE_4.0.1.md); 4.0.2 adds event-backed quiz history, objective-level progress, PROforma-gated curriculum composition and reviewer-gated scenario package authoring. See [4.0.2 implementation notes](docs/LEARNING_EXPERIENCE_4.0.2.md) and the [blueprint completion audit](docs/BLUEPRINT_IMPLEMENTATION_AUDIT_4.0.2.md).


## Start learning immediately

After installation, open **Overview**. The starter Learning Library is bundled with the application and does not require Synthea, a connected dataset, an AI model or an API key. The first curated pack contains eight synthetic acute-care learning units and 24 formative retrieval questions. Each unit also includes learning objectives, a fictional case, teaching points, common pitfalls, two viva prompts, an OSCE station outline and reflection questions.

A suggested first session:

1. Open **Learning library** and choose Acute asthma or Acute chest pain.
2. Read the synthetic presentation and reveal additional findings only after considering what you need to ask or examine.
3. Answer the three formative questions and read each rationale.
4. Open **Simulation lab** for the interactive synthetic asthma scenario.
5. Use **Skills & OSCE** and **Rounds** for stations and viva practice.

The Learning Library now persists formative quiz attempts as canonical event records with idempotency, objective-level feedback and derived progress. These records are not validated competency measures. The Simulation Lab has its own event-backed run and debrief workflow.

## Sustainable, model-free content generation

Open **Content factory** to select learning units and output types. One batch can create up to 72 drafts (12 units × 6 output types); the bundled eight-unit pack can generate 48 derivatives across case reports, debriefs, question sets, topic summaries, viva sets and OSCE stations. Generation is deterministic, uses versioned JSON content packs and templates, does not require AI models or API keys, and deduplicates identical outputs by content hash.

All generated artifacts remain drafts. A qualified reviewer must inspect and approve material before it is distributed into the existing workspace content routes. To add new topics, create a versioned pack following `backend/content_packs/content_pack.schema.json` and `docs/templates/clinical_learning_content_unit.template.json`, then run `python scripts/validate_content_packs.py`. Every installed `*_v*.json` pack is discovered automatically at application start; adding content does not require a new service or route. See [Content Factory Operations](docs/content-authoring/CONTENT_FACTORY_OPERATIONS.md).

## Hospital workspaces

1. **Clinic — Diagnosis:** Case Reports, Case Debriefs, Case Conference and Case Archives.
2. **Rounds — Examination:** Viva Questions, Tagged Report Library and Procedure Theatre.
3. **Lab — Investigations:** Spot Diagnosis and OSCE.
4. **Ward — Management:** On-Call Room, Handover Desk, Consult Room and evidence-based progression from Intern towards Consultant.
5. **Exam Hall:** High-Yield Pearls, Summaries, Attending Lectures, Questions and F-to-S performance scores.
6. **Portfolio:** Profile, Progress Board, Data Tools and administrative question review.

HSPTL is a clinical case-solving and performance platform. Learning activity and workflow completion are formative records; they do not independently establish clinical competence or authorise unsupervised clinical practice.

## Shared tag system

HSPTL uses stable, controlled tag IDs to connect the same clinical concept across workspaces. Current facets include:

- Specialty and body system
- Presentation
- Clinical task (diagnosis, differential, investigation, management, interpretation, communication, procedure)
- Modality (clinical photo, ECG, X-ray, CT/MRI, ultrasound, histopathology, laboratory, fundoscopy, spirometry)
- Care setting, competency, difficulty and learner level

The additive SQLite tag model consists of `learning_tags`, `tagged_content_items`, `content_tag_links` and `tag_learning_events`. It supports a shared catalogue, cross-workspace content lookup and tag-level activity analytics. Items are indexed as the relevant workspace loads them; older content is indexed progressively rather than destructively rewritten. Unknown tag labels are not force-matched to an unrelated concept.

Tag-level activity is formative: recorded attempts and averages are not validated measures of clinical competence.

## Data Tools

### MedNoteGen

MedNoteGen deterministically transforms Synthea FHIR JSON exports into encounter-linked narrative notes and draft learning seeds. It requires no AI API key and does not use an LLM. It preserves source-resource provenance and leaves undocumented findings missing. Its output is synthetic educational source material, not a clinical diagnosis or treatment note.

Default FHIR path on Windows:

```text
%USERPROFILE%\YouseCodes\Synthea\output\fhir
```

Output defaults to:

```text
%USERPROFILE%\HSPTL\imports\mednotegen
```

It writes `hsptl_import.json` and Markdown documents. Pearl seeds remain draft-only pending human review and supporting references.

### Specialty Harvest

The Clinical Knowledge Harvester searches specialty-filtered case reports and broader evidence profiles across Europe PMC, PubMed free-full-text discovery, PMC OA, licence-declared Crossref metadata and DOAJ. It supports 20 specialty categories and can stage metadata/abstract-only records when full text is unavailable. Each harvested article remains unreviewed until source rights, clinical accuracy and educational suitability have been checked.

Open-access status does not by itself grant permission to redistribute or adapt full text or images. Preserve the article's own rights statement and obey its licence conditions.

## Windows requirements

- Windows 10/11 64-bit
- Python 3.12 or 3.13, 64-bit (Python 3.13 recommended; Python 3.14 is not supported by this pinned pandas environment)
- Node.js 20.19+ or 22.12+
- 8 GB RAM for the lightweight local core

## Install

1. Extract the `HSPTL` folder to a local path (not a cloud-synchronised database folder).
2. Run `install_hsptl.bat`. The installer selects Python 3.13 (or 3.12), installs pandas/numpy from binary wheels, and installs pytest and uvicorn into `.venv`.
3. Run `start_hsptl.bat`.
4. Open `http://127.0.0.1:8000` if it does not open automatically.

`check_hsptl.bat` invokes the full release verification suite, including tests and frontend build. The consolidated verification result for this release is recorded in `RELEASE_STATUS.md`.

The server binds to loopback only. Do not expose it to a public network.

### Changing the port

HSPTL uses port 8000 by default. If that port cannot be used, the launcher says why before opening a browser window, because the causes need different fixes:

- **Another program is using the port.** `netstat -ano | findstr :8000` names it; `taskkill /PID <pid> /F` stops it.
- **HSPTL is already running.** The launcher recognises this and points at the window that is already open.
- **Windows reserved the port.** Nothing is holding it, so there is nothing to close. Hyper-V, WSL2 and Docker Desktop reserve ranges. Run `netsh interface ipv4 show excludedportrange protocol=tcp` in an Administrator terminal and choose a port outside them.

To use a different port:

```bat
set HSPTL_PORT=8080
start_hsptl.bat
```

`HSPTL_PORT` moves the backend and the Vite dev proxy together. For the development server, `HSPTL_DEV_PORT` changes the Vite port (default 5173). Both launchers and the frontend read the same defaults from `backend/hsptl_core/config.py`, so there is no second place to keep in sync.

## Developer commands

```powershell
$env:PYTHONPATH = "."
python -m pytest -q

cd frontend
npm ci
npm run typecheck
npm run build
```

## Local data and migration

New data defaults to `%USERPROFILE%\HSPTL` (`hsptl.sqlite3`, `settings.json`, `imports`, `references`, `logs`). On first launch, HSPTL can non-destructively migrate data from earlier WardX, Wardle and Casedle data directories where present. Original source folders are not deleted. Set `HSPTL_HOME` to choose another HSPTL data directory.

## Safety and provenance

- Synthea records are synthetic and must remain labelled as such.
- Missing clinical facts are not converted to normal findings.
- FHIR resources are linked to an encounter only when an explicit encounter reference exists.
- A coded condition in a synthetic record is source data, not automatically an approved final diagnosis.
- Harvested published cases need source and licence review, clinical review, privacy review where relevant, and an authored teaching blueprint before promotion into the case or exam banks.
- This software is for education only and must not be used to make decisions about real patients.


## Unified Clinical Knowledge System (UCKS)

The UCKS foundation and current limitations are documented in [docs/UCKS.md](docs/UCKS.md). The current development increment adds source registration, provenance-aware document ingestion, immutable versions, heading-aware chunks and full-text search, plus automatic ingestion of MedNoteGen synthetic cases and Specialty Harvester JATS articles. The current development increment adds PDF/DOCX/CSV/TSV/JSON/JSONL/Markdown/TXT ingestion and deterministic SQLite FTS5 lexical retrieval. HSPTL 4.0 disables embedding-model indexing and vector similarity retrieval to keep the application model-free. Historical embedding rows, if present in an upgraded database, are ignored.

### Data Tools and UCKS architecture

MedNoteGen and Specialty Harvest execute through application services and the durable job runner. Their outputs pass through shared UCKS ingestion contracts and remain unreviewed until the appropriate clinical and rights review is completed. See [HSPTL Tools Architecture](docs/HSPTL-TOOLS-ARCHITECTURE.md) for package boundaries, monitoring endpoints and remaining refactor limitations.


## Clinical Knowledge Harvester and governance monitoring

The decomposed harvester supports specialty-scoped case-report, guideline, systematic-review, trial, observational/diagnostic and combined evidence profiles across multiple provider adapters. Provider discovery filters do not imply reuse rights; metadata-only records are explicitly labelled. See [Clinical Knowledge Harvester](docs/CLINICAL_KNOWLEDGE_HARVESTER.md) for module boundaries, licence handling, provider health checks and UCKS governance monitoring.


### UCKS governance reviewer configuration

To enable authenticated rights and evidence-appraisal decisions, set `HSPTL_REVIEWER_TOKEN` (at least 32 random characters) and `HSPTL_REVIEWER_ID` in the Windows user environment, then restart HSPTL. Governance writes fail closed until configured. See `docs/UCKS.md` for the PowerShell setup and workflow limitations.


For continuous UCKS feed, connector and provider-reachability checks, start `run_ucks_scheduler.bat` after HSPTL is running. The scheduler can also be run once through `scripts/run_ucks_scheduler.py`; details and limitations are documented in `docs/UCKS.md`.


## HSPTL 5.1.0

This release adds source reliability appraisal, learner-specific case practice recommendations, formative lottery submissions, and safer Windows install/start launchers. See `RELEASE_STATUS.md` for scope and limitations.
=======
# HSPTL
>>>>>>> 4dcc48cc794d4e4e7ea0e723e6ff49a30cce5a78
