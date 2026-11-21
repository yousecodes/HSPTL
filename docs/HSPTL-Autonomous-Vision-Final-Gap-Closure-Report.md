# HSPTL Autonomous Vision — Final Gap-Closure Update

## Implemented in this update

### 1. Continuous synthetic teaching-case authoring

- The synthetic-data pipeline now passes only its accepted FHIR import bundles to a teaching-case author.
- The author creates idempotent, privacy-minimised cases from records with exactly one Patient, at least one Encounter, at least one Observation, and an active/verified coded Condition.
- Patient names, FHIR IDs, addresses and contact details are not exposed in the lottery case. A stable one-way digest is used for deduplication.
- Cases are automatically enrolled in the daily lottery as `synthetic_qa_passed` and explicitly report `clinical_validation_status=not_assessed_synthetic_qa_only`.
- The answer reproduces the coded condition in the synthetic record; it is not represented as an independently inferred diagnosis. The learner prompt asks what the code records and what additional evidence would be needed for real clinical assessment.
- Ineligible or incomplete bundles are skipped with explicit reasons. Arbitrary harvested sources and model output cannot enter this path.
- The runtime lottery also reconciles the HSPTL-authored curriculum automatically before a draw. This remains idempotent and does not admit unreviewed external records.

### 2. Provider update monitoring and lifecycle reconciliation

- Added scheduled rolling 30-day update searches for Crossref (`from-update-date` / `until-update-date`, sorted by update date), PubMed (`mdat`), and ClinicalTrials.gov (`LastUpdatePostDate`).
- ClinicalTrials.gov records now retain the actual last-update submitted and posted dates, and the posted date is included in the source body so a changed registry snapshot creates a new immutable source version.
- Crossref DOI relations with explicit `is-retracted-by`, `is-retraction-of`, `is-corrected-by`, and `is-correction-of` semantics are resolved against indexed DOI identifiers. PubMed `CommentsCorrections` relations (`RetractionIn`, `RetractionOf`, `ErratumIn`, `ErratumFor`, `CorrectionIn`, `CorrectionOf`) are resolved against indexed PMIDs. Exact retraction relations automatically retract the target; exact correction relations mark the target corrected. Existing downstream reconciliation withdraws retracted/superseded artefacts and flags corrected/version-changed artefacts for refresh.
- Ambiguous or unresolvable relations are ignored rather than promoted to authoritative lifecycle changes.

### 3. Optional local no-key clinical-learning synthesis

- Added an opt-in Ollama-compatible local model adapter, defaulting to `qwen2.5:1.5b` for low-memory machines.
- It only connects to a validated local loopback endpoint (`localhost`, `127.0.0.1` or `::1`). Remote endpoints are rejected. No cloud provider, API key, telemetry or remote fallback is used.
- The prompt constrains output to supplied source spans and requires exact source quotes. The existing schema and exact-quote citation validator remains mandatory; numeric claims are additionally rejected if their values do not appear in cited text.
- If the local model is not installed, unavailable, or returns invalid output, HSPTL automatically falls back to its existing deterministic extractive generation. Core operation remains API-key-free.
- Model-generated content remains provisional and `clinical_validation=not_assessed`.

## Enable the optional local model on Windows

Install Ollama from its official Windows installer, then in PowerShell run:

```powershell
ollama pull qwen2.5:1.5b
setx HSPTL_LOCAL_MODEL_ENABLED "1"
setx HSPTL_LOCAL_MODEL "qwen2.5:1.5b"
```

Restart PowerShell and HSPTL. Ollama must be running locally on `http://127.0.0.1:11434`. If it is not running, HSPTL uses deterministic extractive generation without blocking the workflow. Leave `HSPTL_LOCAL_MODEL_ENABLED` unset or set it to `0` to use the no-model default.

## Remaining release limitations

- The provider update searches are rolling discovery windows, not a mathematically complete or immutable snapshot of every provider's history. Provider-specific result caps and indexing delays still apply. The scheduler paginates bounded batches and persists cursors, but an exhaustive global backfill cannot be guaranteed.
- Europe PMC does not yet have a separate reliable publisher-updated-date feed in this implementation. Its stable historical cursor and newest-first refresh continue to run.
- Crossref and PubMed relation metadata are provider-dependent; missing or ambiguous relationships remain review proposals, not automatic status changes.
- The local model is optional and not installed or exercised in this build environment. The deterministic fallback is the default until the user installs a local model.
- The frontend production build and native Windows clean-install workflow remain unverified. `npm ci` timed out in this environment and offline install reported a missing cached Vite package. No successful frontend build is claimed.

## Verification

- Python compile check: see final test report.
- Windows clean-install and frontend build must pass in the user's Windows GitHub Actions workflow before release.

## Safety and lifecycle semantics

- Synthetic QA is not clinical validation.
- Provisional publication is not clinical approval.
- XP, learner usage and post-use ratings are not evidence of clinical competence.
- A generated case is a fictional educational record and must not be used for patient-care decisions.
- Source reuse rights and clinical validity remain independent checks.

## Final verification results for this implementation package

- Full backend suite: **540 passed in 58.28 seconds**.
- Focused lottery, connector, generation, local-model, synthetic-case and frontend-contract tests: **142 passed**.
- `python -m compileall -q backend scripts tests`: passed.
- `scripts/validate_content_packs.py`: passed (8 units, 24 questions, 48 deterministic output recipes).
- `scripts/verify_release.py --skip-tests --skip-frontend`: **6 passed, 0 failed**, including supported Python check, identity scan, compile, content-pack validation, Windows launcher contract checks, and local backend health boot.
- Frontend dependency installation: `npm ci` timed out; `npm ci --offline` failed because Vite was not present in the local npm cache. Therefore TypeScript and Vite production build are not verified.
- Native Windows clean-install GitHub Actions workflow: not run from this environment. It remains mandatory before release.
