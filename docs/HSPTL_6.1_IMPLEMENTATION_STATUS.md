# HSPTL 6.1 implementation status

**Status: implementation work in progress; not a release approval.** The changes below are based on the supplied repository snapshot. Version identity remains 6.0.0 until the complete release gates pass.

## 6.1.1 — Provisional learner access

- Learner-facing publication now includes delivered artefacts in `provisional` or `approved` state. Drafts, rejected items, source-update-required items and withdrawn items remain excluded.
- API response explicitly distinguishes `publication_state` from `clinical_approval`; provisional availability is not clinical approval.
- Existing use and feedback records retain the exact `content_hash`. Completion and feedback reject stale-version sessions.
- Frontend labels provisional items as educational-use provisional rather than approved.

## 6.1.2 — Autonomous synthetic supply

- Added `SyntheticDataFactory.ensure_default_schedule()` with a stable schedule ID, daily frequency, population cap of 20 and accepted target of 10. Repeated startup calls reuse the existing record.
- Application lifespan seeds the schedule before starting the scheduler. The scheduler queues durable work; the existing job runner performs generation.
- The schedule uses the built-in asthma synthetic recipe. It does not confer clinical approval; the existing validation and teaching-case quality gates still apply.
- Actual Synthea execution depends on the user's configured local Java/Synthea runtime and has not been exercised in this environment.

## 6.1.3 — Workspace distribution

- Delivery adapters now target the product workspace identifiers: Clinic, Rounds, Lab, Ward, Exam Hall, Library and Learning.
- Existing generator identifiers remain compatible: `portfolio` routes to Library and `simulation` routes to Learning. The generator manifest labels now use the product-facing names.

## 6.1.4 — Lifecycle automation

- Existing automatic source reconciliation remains in place: revised/corrected sources flag dependent artefacts for refresh; confirmed retraction/supersession withdraws artefacts and delivered routes.
- Learner publication excludes source-stale and withdrawn artefacts, so the new provisional learner path does not bypass lifecycle safeguards.

## 6.1.5 — Verification

- Added an integrated test covering machine-screened reusable source → generated provisional artefact → learner list/use/completion/feedback → confirmed retraction → learner unavailability.
- Added a durable/idempotent default schedule test and updated workspace destination contract tests.
- All 542 collected backend tests pass, executed in bounded batches across the complete test-file set. Python `compileall` passes. `npm ci` could not complete because the npm registry was unreachable and the Vite package tarball was not cached; frontend typecheck/build therefore remain unverified.

## Remaining release gates

1. Re-run the full backend suite in the repository's Windows clean-install workflow.
2. Run `npm ci`, `npm run typecheck` and `npm run build` on the supported Windows environment.
3. Execute a real Synthea schedule with the configured local Java/Synthea runtime; verify accepted FHIR imports and lottery replenishment.
4. Verify Clinic and Ward still resolve the same persisted daily lottery draw.
5. Exercise source revision/correction/retraction using real connector responses, while retaining provider coverage limitations and rights checks.
6. Review UI routing to confirm the Library and Learning destinations are consumed by the intended native pages.
7. Regenerate `MANIFEST.sha256` using the repository's release script only after all files and release gates are final.

**No claim is made that 6.1 is release-ready.** No clinical approval, clinical competence or institutional accreditation is implied by provisional publication, synthetic QA or learner validation scores.
