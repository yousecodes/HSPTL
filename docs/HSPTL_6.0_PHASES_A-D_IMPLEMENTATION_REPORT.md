# HSPTL 6.0.0 — Phases A–D implementation report

**Implementation base:** HSPTL 5.2.0 Daily Lottery / Automatic Import / Windows CI Preview  
**Package identity:** 5.2.0 development base (not promoted to 6.0.0)  
**Scope:** Phase A foundation consolidation; Phase B content engine; Phase C post-use validation; Phase D seven-workspace integration.

## Executive summary

Phases A–C were already substantially present in the supplied 5.2.0 candidate. This increment preserves and consolidates those implementations rather than duplicating their stores or engines. The concrete addition in this increment is a canonical seven-workspace integration contract that bridges the seven user-facing workspaces to the existing six presentation skins and seven shared engines. The contract is exposed through read-only API endpoints and surfaced in Content Operations.

## Phase A — Foundation consolidation

- Preserved the existing FastAPI/React/SQLite modular monolith and additive migrations.
- Preserved the seven engines: Kernel, Reasoner, Logic, Composer, Router, Guards and Explain.
- Preserved the single persisted Daily Case Lottery used by Clinic and Ward; the Clinic page uses the lottery component as its Daily Case experience.
- Preserved the unified deterministic content pipeline for startup preparation and manual Update content. It creates idempotent drafts and does not approve or publish them.
- Preserved the independent state dimensions for provenance, source rights, clinical review and publication.
- Preserved the existing synthetic-data factory and its deterministic generation/validation lifecycle.

## Phase B — Content engine and automatic source ingestion

- Preserved the API-key-free Europe PMC, PubMed, ClinicalTrials.gov and Crossref scheduled connectors.
- Startup provisions default source profiles and runs due connector jobs; the explicit refresh action queues a refresh.
- Imports are automatic and do not require per-record human approval. Machine-screened denotes structural/provenance integrity checks only; it is not clinical validation.
- Full-text retrieval remains item-licence constrained. Europe PMC full text is fetched only for explicit CC0, CC-BY or CC-BY-SA records. Unknown, NC and ND records remain citation/metadata-only unless separately permitted.
- Preserved deterministic, source-linked Pearls Factory templates. It fails closed when no rights-cleared source spans support an output; generated pearls remain drafts until separately reviewed.
- Preserved the Daily Case Lottery eligibility rules. An article or event theme is not silently converted into a patient case. Lottery candidates still require an eligible authored/curated or clinically reviewed status, publication and suitable rights.

## Phase C — Post-use learner validation

- Preserved use-session recording and completion before feedback submission.
- Preserved content-hash/version binding so evidence submitted against an older artefact version cannot validate a changed version.
- Preserved four weighted dimensions: clinical 35%, educational 25%, sources 20%, assessment 20%.
- Preserved authenticated unique-learner evidence, training-level diversity, four domain sign-offs, audit history and critical-issue score cap.
- Preserved separate reviewer triage and sign-off authorization. Learner ratings do not independently approve clinical content, publication or reuse rights.
- The validation state is version-specific and is not represented as proof of clinician competence.

## Phase D — Seven-workspace integration

Added `WORKSPACES` and a canonical mapping in `backend/hsptl_core/engine_integration.py` for:

1. Clinic
2. Lab
3. Ward
4. Library
5. Learning
6. Exam Hall
7. Rounds

The mapping reuses real existing engine bindings across the six presentation skins. New endpoints:

- `GET /api/v5/workspaces/contracts` — full seven-workspace binding matrix and completeness flags.
- `GET /api/v5/workspaces/{workspace}/engines` — bindings for one canonical workspace.

Content Operations now displays the seven-workspace integration coverage and each workspace's shared-engine bindings. This is a product-workspace contract; it does not create duplicate engines or treat skins as separate clinical logic.

## Verification performed in this implementation environment

| Check | Result |
|---|---|
| Focused next-increments + unified-content tests | **107 passed** |
| Post-use validation + UCKS + connectors + content factory tests | **80 passed** |
| Python compile | Passed |
| Content pack schema/recipe validation | Passed — 1 pack, 8 units, 24 questions, 48 recipes |
| Release verifier with `--skip-tests --skip-frontend` | **6 passed, 0 failed**, including backend boot/health smoke |
| Full backend pytest suite | Started but exceeded the 300-second execution limit after partial progress; complete suite result not established |
| Frontend `npm ci` | Timed out while resolving/installing dependencies |
| Frontend TypeScript and Vite production build | Not verified in this environment |
| Native Windows clean-install workflow | Not run in this environment; Windows CI remains the authoritative check |

The 187 passing tests above are focused suites, not a claim that the complete backend suite passed.

## Remaining work before HSPTL 6.0.0

- Run the complete backend suite to a final exit code in CI.
- Complete `npm ci`, `npm run typecheck` and `npm run build` on a network-enabled Windows runner.
- Run the complete native Windows clean-install workflow from a fresh checkout, including startup and health checks.
- Inspect the resulting frontend in all seven workspaces and verify that the browser is serving the newly built bundle.
- Reconcile release metadata and promote `APP_VERSION` / frontend package version to 6.0.0 only after all release gates pass.

## Release decision

**Not a 6.0.0 release.** This package is a 5.2.0 development preview with Phases A–D consolidation work. The frontend production build, complete backend suite and native Windows clean-install workflow remain release blockers.
