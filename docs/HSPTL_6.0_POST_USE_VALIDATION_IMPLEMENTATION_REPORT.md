# HSPTL 6.0 — Post-use validation implementation report

**Build type:** Development preview  
**Internal application version:** 5.2.0 (intentionally unchanged pending full release verification)  
**Feature scope:** Version-bound, post-use, multi-role learner validation with a 0–100% score

## Delivered

### Learner post-use workflow

- Published Library artefacts are available to assess only after they are approved and delivered through an existing workspace route.
- An authenticated learner opens an artefact, completes the learning activity, and then submits a four-domain validation assessment.
- Feedback is tied to a completed usage session and the exact content hash.
- Guest reports may still be received for triage, but are not included in the numeric validation score.
- The UI displays the validation score, status, contributor target/coverage, domain scores and latest expert sign-off decisions.

### Institutional role/training-level evidence

- Institutional account creation supports an institution-assigned training level: student, intern, resident, registrar, fellow, specialist, consultant, faculty or unspecified.
- The training level is stored on the institutional account and authenticated session. It is not read from an editable learner profile field.
- Role-weighted evidence uses modest multipliers documented in `HSPTL_6.0_POST_USE_VALIDATION_SPEC.md`.
- Database changes are additive and existing records migrate with an `unspecified` default.

### Validation score

The score combines domain quality ratings, unique verified learner evidence coverage, expert sign-off coverage and learner-level diversity. Domain weights are educational 25%, clinical 35%, sources 20%, and assessment 20%. Each 1–5 rating maps to 0–100. The contributor target is 10.

The final `validated` state requires all four domain sign-offs affirmed, at least 10 verified contributors, at least two distinct institution-assigned learner levels, a score of 90% or higher, and no unresolved critical issue. An unresolved critical report caps the score at 49% and blocks that state.

### Expert sign-offs and audit

- Clinical sign-off requires an authenticated reviewer/administrator with specialist or consultant training level.
- Educational and assessment sign-off requires an authenticated facilitator/reviewer/administrator with faculty training level.
- Source sign-off requires an authenticated reviewer/administrator.
- Sign-offs are append-only and bound to artifact content hash, with identity, role, institution, training level, decision, rationale and timestamp.
- An expert sign-off does not itself change publication or rights status.

### Versioning and safety

- Learner votes and expert decisions are bound to the current content hash.
- Revised content creates a fresh validation cycle; old evidence remains associated with the version previously assessed.
- Duplicate learner votes per artefact version are rejected.
- Learner issue reports can identify only sources linked to the artefact.
- Existing source licensing, attribution, approval and publication safeguards remain separate mandatory gates.

## Verification performed

| Check | Result |
|---|---|
| Full backend test suite | **498 passed** |
| Python compile check | Passed |
| Startup preflight and database migrations | Passed |
| Content-pack validator | Passed: 1 pack, 8 units, 24 questions, 48 deterministic output recipes |
| Frontend TypeScript/TSX syntax transpilation | 39 files, zero syntax diagnostics |
| Frontend production build and complete typecheck | **Not verified** |

The frontend production build could not be completed because the npm registry was unavailable (`EAI_AGAIN` resolving `registry.npmjs.org`) and locked React/Vite dependencies were not installed locally. The TypeScript syntax transpilation checks parsing only; it is not a replacement for dependency-aware typechecking or a Vite production build.

## Important limitations

1. The score is a structured quality/evidence metric, not a mathematical proof of clinical truth or a substitute for clinical governance.
2. Institutional account roles and training levels are locally administered. This implementation does not provide enterprise SSO, MFA, external professional registration verification or hardened multi-tenant identity management.
3. Institutions must assign training levels accurately and appoint qualified reviewers. The weight multipliers are a transparent initial policy and should be reviewed by each institution before operational use.
4. A critical issue blocks the `validated` state and caps the score; an authorised human must still make any separate suspend/withdraw/republication decision. The metric does not silently alter publication status.
5. Source permission, copyright/licensing, provenance and institutional approval remain independent gates. A positive learner score cannot grant content reuse rights.
6. The app's internal version remains 5.2.0. This package is a 6.0 development preview, not a final 6.0 release.

## Files of interest

- `backend/routers/published_learning.py` — use, completion, feedback, score and sign-off endpoints.
- `backend/hsptl_core/institutional.py` — account training levels and session persistence.
- `frontend/src/components/PublishedLearningPanel.tsx` — learner use and post-use validation UI.
- `frontend/src/components/ArtifactValidationOperations.tsx` — domain sign-off and score operations UI.
- `frontend/src/pages/ContentOperationsPage.tsx` — validation operations and learner feedback queue.
- `frontend/src/pages/AdminReviewPage.tsx` — institution-assigned training level at account creation.
- `HSPTL_6.0_POST_USE_VALIDATION_SPEC.md` — full score methodology, states, and safeguards.
