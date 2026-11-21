# HSPTL Autonomous Vision — Implementation Status

## Operating objective

HSPTL should acquire, screen, process, generate, provisionally publish, distribute, refresh and monitor educational content with minimal routine intervention and no external AI API key for core operation. Clinical validation and learner competency remain distinct from automated publication.

## Implemented in this working tree

### 1. No-key source acquisition

- Built-in Europe PMC, PubMed, ClinicalTrials.gov and Crossref connectors remain API-key-free.
- Managed profiles are provisioned and scheduled by the local application.
- Imported records are machine-screened and do not wait for per-record human import approval.
- Rights remain item-specific. Import does not grant text-reuse permission; unknown, restricted or unsupported rights block full-text derivation.

### 2. Acquisition-to-learning pipeline

- Successful managed-source runs trigger generation for supported evidence types.
- Supported mappings include case reports/series, synthetic cases, clinical notes, reference documents, datasets, guidelines, systematic reviews, trials, diagnostic studies and observational studies.
- Generation is local and deterministic/extractive, with source-span citations and rights checks.
- Eligible outputs are routed automatically to their matching workspace as `provisional`.
- The learner-facing index remains `unreviewed`; it is never falsely labelled clinically approved.
- Repeated scheduler runs are idempotent for an unchanged source version.

### 3. Autonomous local execution

- The background job worker starts automatically with the application.
- Synthetic-data schedules start automatically with the application.
- Worker start is idempotent and worker shutdown is cooperative.
- `HSPTL_DISABLE_BACKGROUND_WORKERS=1` is the explicit opt-out for tests or maintenance.
- External-source automation remains independently controllable through `HSPTL_DISABLE_EXTERNAL_AUTOMATION=1`.

### 4. Source-change safety propagation

- A new immutable source version causes a new learning artefact to be generated.
- Existing artefacts whose cited source version is no longer current are marked `source_update_required` in the artefact record and learner-facing index; their old distribution routes are no longer considered delivered.
- When a source lifecycle is confirmed as retracted or superseded, dependent artefacts and their routes are marked `withdrawn`.
- Publisher change signals are still confirmation-gated before changing a source's authoritative lifecycle state; false-positive retraction signals must not silently rewrite evidence status.

### 5. Learner feedback and validation

- Existing post-use feedback workflow remains separate from publication.
- Feedback is linked to actual use, deduplicated for verified learners, and can be triaged after publication.
- Validation scoring remains separate from XP and clinical competence. Automated publication does not set clinical validation to complete.

### 6. Daily case

- Clinic and Ward continue to consume the shared daily-case lottery only.
- Startup seeds the HSPTL-authored fictional curriculum bank idempotently.
- The lottery continues to exclude unreviewed, restricted-rights and unpublished cases and withholds answers server-side.
- Newly authored curated curriculum entries are enrolled on the next application startup. Automatic conversion of arbitrary generated or harvested records into lottery cases is intentionally not enabled because it could turn unvalidated evidence into patient-like teaching cases.

## Explicit limitations / work still required for a fully exhaustive vision

1. **Evidence synthesis:** the no-key generator is deterministic and extractive, not a clinically reasoning local LLM. It does not synthesize novel recommendations or independently grade certainty.
2. **Provider completeness:** built-in connector queries are bounded and scheduled; provider pagination and historical backfill are not exhaustive. Updated-date watermarks and reliable full-corpus reconciliation remain to be implemented.
3. **Automated source-event confirmation:** publisher correction/retraction signals are detected as proposals, but confirmation remains a governance action. Once confirmed, downstream quarantine/withdrawal is automatic.
4. **Dynamic lottery replenishment:** the lottery seeds authored curriculum at startup, but there is not yet a continuous validated synthetic-case authoring pipeline that creates and quality-checks new lottery candidates from the synthetic data factory.
5. **Native Windows release verification:** this Linux working environment cannot certify the user's Windows clean-install workflow. Run the repository's Windows CI workflow after applying the package.
6. **Frontend production build:** frontend source was not changed in this layer. `frontend/node_modules` is absent in this working copy, so `npm run build` was not run here.

## Verification in this working tree

- Focused autonomous-source, UCKS, content-factory, background-job, synthetic-data and lottery/frontend-contract tests were run during implementation.
- Full backend suite: **528 passed in 53.45 seconds**.
- Python compile check: `python -m compileall -q backend tests`.

## Release state

This is a working-tree implementation package based on the HSPTL 6.0.0 source archive. It has not been pushed to or merged into the user's GitHub `main` branch. Apply it to a backup of the local repository, run the Windows clean-install and GitHub Actions workflows, then commit and push only after those checks pass.
