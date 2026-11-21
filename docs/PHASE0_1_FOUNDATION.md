# HSPTL 2.0 — Phase 0/1 foundation

Status: implemented incrementally through `2.0.0-dev.7`; this is not a completed HSPTL 2.0 release.

## Core/optional dependency boundary

- Core API and learning modules do not import Chroma, MedCPT, LlamaIndex, Presidio, scispaCy, medSpaCy, Fiji or Ragas.
- `/api/system/capabilities` reports optional dependency availability without importing those packages or loading model weights.
- `/api/search` uses SQLite FTS5 and falls back to SQLite `LIKE` search when FTS5 is unavailable. Chroma is not required.
- Presidio is described as privacy-scanning assistance, never as guaranteed or complete de-identification.
- Fiji is an independent optional desktop tool. Its absence does not affect the API.
- Ragas is not imported by the normal runtime.

## Data integrity

- SQLite schema changes are additive and recorded in `schema_migrations`.
- Study-note saves are idempotent for identical content. Changed content updates the note and preserves the prior version in `study_note_versions`.
- `StudyStore.backup_to()` uses SQLite's backup API so committed WAL content is included.
- Background jobs persist status, progress and checkpoints; queued/running jobs can be paused, and paused/failed jobs can be re-queued.
- PDF uploads are written in 1 MiB chunks to a temporary file, size-limited while streaming, validated and atomically published.
- Lifetime progress is computed with SQL aggregates and does not depend on recent-activity pagination.

## Clinical safety contracts

- `ClinicalFact` distinguishes documented, derived, authored and unavailable values.
- Documented facts require a source resource type and id.
- Derived facts require an explicit derivation description.
- Unavailable facts cannot carry a clinical value.
- Medication mapping is exact-alias-only and jurisdiction-aware. An unmatched Egyptian medication remains unmatched; no fuzzy RxNorm assignment is made.
- UMLS export policy requires an active licence and explicit redistribution permission for every requested source vocabulary.

## Acceptance tests added

- Core capability report works without optional dependencies.
- Local search works without Chroma.
- Note saves are idempotent and versioned.
- Background jobs retain checkpoints across pause/resume.
- Lifetime counts remain correct beyond a paginated page.
- SQLite backups contain committed data.
- PDF upload streams and rejects invalid files.

## Not yet implemented

- Full Universal Case Engine normalization, source selection, case variation and longitudinal encounter workflows.
- Durable pause/resume checkpoints for an actively running FHIR import worker (the current importer is bounded and safely rerunnable, but invoked synchronously).
- Real background worker execution for document/FHIR/model indexing jobs (the durable job/control layer exists first).
- The Clinic/OSCE/Specialties/Pearls/Exam Centre/My Progress 2.0 vertical slices and frontend redesign.
- Optional MedCPT, Chroma, NLP and Fiji adapters.
- Full Windows install/upgrade and visual QA on the target machine.

## Environment-limited checks

- The frontend dependency install and production build could not be completed in this build environment: npm registry DNS resolution failed (`EAI_AGAIN`). No incomplete or fabricated `package-lock.json` was added. Generate and verify the lockfile on a machine with registry access, then run `npm ci` and `npm run build`.
- Backend compile checks and all 40 Python tests pass in the available environment.


## Dev.5 — formative reasoning debrief

- Saving a reasoning attempt returns a deterministic completeness review across problem representation, differential breadth, evidence for/against and investigation strategy.
- The debrief prompts confidence reflection and suggests how to complete missing documentation.
- The review is explicitly non-diagnostic: it does not claim correctness, competence or clinical safety.
- Added tests for complete and incomplete drafts; backend suite has 40 passing tests.

## Dev.4 — Clinic encounter learning slice

- FHIR encounter narratives are generated deterministically from encounter-linked resources. The output labels source-documentation and unavailable sections; it never infers a diagnosis from `Condition`.
- The learner can save a reasoning attempt containing a problem representation, up to eight differential entries, evidence for/against, investigation strategy, and confidence rating.
- Age is calculated only from a documented birth date and encounter date and carries explicit derived provenance.
- Attempts are stored in SQLite with foreign-key ownership constraints. This is a learning draft only; raw imported encounters remain ineligible for diagnostic puzzles pending clinical curation.
- Frontend production build remains unverified until npm dependencies can be installed on a network-enabled machine.

## Clinic evidence disclosure (dev.7)

- The staged encounter begins with encounter context and explicit unavailable HPI/examination states.
- Learners request source-backed record groups during the investigation stage; only requested groups are revealed in subsequent reasoning stages.
- Switching patient/encounter resets the reveal state. No history, examination or test result is simulated or inferred.
- This is a user-interface learning workflow, not a validated simulation of a live patient interview.
