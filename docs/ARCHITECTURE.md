# HSPTL architecture — current development baseline

## Runtime components

- `frontend/`: React UI, Tailwind CSS 4 theme and Vite build.
- `backend/main.py`: FastAPI HTTP surface and application lifecycle.
- `backend/hsptl_core/config.py`: paths, settings and non-destructive legacy migration.
- `backend/hsptl_core/data.py`: existing CSV/FHIR cohort discovery and source-record summaries.
- `backend/hsptl_core/case_engine.py`: deterministic FHIR import, patient/encounter identity, source-linked facts and case retrieval.
- `backend/hsptl_core/case_quality.py`: structural quality flags; explicitly does not certify clinical validity.
- `backend/hsptl_core/store.py`: SQLite schema, additive migrations, learning records, notes, versions, FTS5 search, job checkpoints and backups.
- `backend/hsptl_core/capabilities.py`: optional dependency status without importing optional modules.
- `backend/hsptl_core/provenance.py`: shared clinical fact provenance contract.
- `backend/hsptl_core/terminology.py`: conservative medication mapping and UMLS export guard.
- `backend/hsptl_core/learning.py`: curated clinical knowledge-check packs.
- `backend/hsptl_core/note_engine.py`: source-linked note template assembly and Markdown export.
- `backend/hsptl_core/integrations.py`: explicit online literature/reference and local document operations.
- `tests/`: backend and API regression tests.

## Runtime

- Backend: Uvicorn on `127.0.0.1:8000` (override with `HSPTL_PORT`).
- Frontend development server: Vite on `127.0.0.1:5173` (override with `HSPTL_DEV_PORT`), proxying `/api` to the backend port.
- Production: FastAPI serves the built `frontend/dist` from the same origin.

Port defaults live in `backend/hsptl_core/config.py` (`DEFAULT_PORT`, `DEFAULT_DEV_PORT`) and are the single source the launchers and `frontend/vite.config.ts` follow.

## Core/optional boundary

Core services use Python standard library, FastAPI, Pydantic, pandas and SQLite. Optional integrations are discovered by module metadata and loaded only by their feature adapters when those are implemented. Chroma is not a search prerequisite. Search uses FTS5 with a LIKE fallback. Ragas is development/test-only. Fiji is a separate specialist application.

## Data boundaries

Synthea resources are synthetic source records and may be incomplete. Missing values are not converted to negative findings. Coded conditions are not independently confirmed diagnoses. The shared `ClinicalFact` contract requires provenance for documented and derived values. Medication terminology matching is exact-alias-only and jurisdiction-aware.

## Universal Case Engine — current increment

- `CaseRepository` stores clinical patient, encounter and fact records in additive SQLite tables.
- Supported inputs: FHIR JSON Bundle, standalone FHIR JSON resources and NDJSON/JSONL.
- Imports use stable source/resource identities and upserts; unchanged files are skipped. A failed file does not roll back already committed files or batches; rerunning is safe.
- Resource persistence is committed in bounded batches (25–1,000 resources). File hashing reads 1 MiB chunks. JSON Bundle parsing is capped at 32 MiB per file; NDJSON lines are capped at 4 MiB. This bounds worst-case parser memory, although a single JSON Bundle is still parsed as one bounded file.
- Facts are attached to encounters only when the FHIR resource explicitly references an encounter. Unlinked facts remain visible in patient timelines but are never silently assigned.
- Raw resource JSON, source file and `Documented` provenance are retained. Missing fields remain missing; no synthetic normal findings or inferred examination details are generated.
- Case quality flags identify sparse, undated, unlinked and condition-only records. Raw FHIR imports are never diagnostic-puzzle eligible until separately curated and clinically reviewed.
- Clinic includes a collapsible patient record explorer with paginated patient lists and encounter-specific views.
- API: `POST /api/clinical/fhir/import`, `GET /api/clinical/patients`, and `GET /api/clinical/patients/{patient_key}` (optional `encounter_key`).

## SQLite and recovery

- SQLite is the authoritative store.
- Schema changes are additive and recorded in `schema_migrations`.
- WAL mode and bounded busy timeout support local concurrency.
- `StudyStore.backup_to()` uses SQLite's online backup API.
- Long-running work records durable status/progress/checkpoints in `background_jobs`.
- Note content changes preserve the previous version.

## Local security posture

The supplied launcher binds to loopback. There are no remote accounts or cloud database. Do not expose this development API to a network without authentication, CSRF protections appropriate to deployment, access control, transport security and a formal security review.
