# HSPTL 4.0 Blueprint implementation audit — 4.0.2

## HSPTL 5.0.0 institutional implementation delta

| Remaining blueprint area | 5.0 status | Implementation boundary |
|---|---|---|
| Authentication and RBAC | Implemented for local deployment | PBKDF2-SHA256 password accounts and 8-hour role sessions; no SSO/MFA |
| Cohorts and facilitation | Implemented as local institutional records | Durable cohorts, memberships, facilitator sessions and event controls; no production multi-tenant isolation |
| Privacy and retention | Implemented | Policy records, consent status, retention values and expired-session purge; encryption-at-rest remains deployment responsibility |
| Backup and recovery | Implemented | Consistent SQLite backups with SHA-256 manifests and documented stop/replace/restart recovery |
| Standards integration | Partially implemented | Configurable FHIR base, CQL export, CDS descriptors/cards and terminology exact-match; external transport/conformance remains institutional |
| Psychometric calibration | Blocked | Data export and 500-row review threshold added; activation remains disabled pending representative independent validation |
| Clinical safety | Partially implemented | Hazard/safety/control/residual-risk records and approval status added; independent clinical approval remains external |

**Audit basis:** source archive `HSPTL-4.0.1-Learning-Experience-Content-Factory.zip`, extracted to a working tree and inspected. This audit records code/documentation status, not clinical approval or institutional production certification.

## Phase-by-phase status

| Blueprint phase / requirement | Status | Evidence and boundary |
|---|---|---|
| Phase 0 — repository discovery, module map, determinism mechanism | Completed | `docs/HSPTL_CLINICAL_LEARNING_SIMULATION_BLUEPRINT.md`; FastAPI/SQLite + React; seed contract and module seams documented. |
| Phase 1 — first-class scenario package | Partially completed | Versioned JSON reference scenario and package validator exist. 4.0.2 adds local immutable drafts and publication. A general visual editor and dynamic all-path validation are incomplete. |
| Phase 2 — learner observation surface | Completed for reference scenario | Staged observations and Pulse projection; internal state withheld by the scenario policy. Not a general patient-monitoring renderer for arbitrary scenarios. |
| Phase 3 — actions, time and patient response | Completed for bounded reference scenario | Six typed PROforma-gated actions, integer clock, scheduled events and deterministic state transitions. This is an educational transition model, not validated physiology. |
| Phase 4 — notes/orders/handover | Completed for bounded pilot | Structured note, handover and educational order versions are event-backed. A general medication/order catalogue remains outside the bounded scenario. |
| Phase 5 — explainable assessment | Partially completed | Seven-item trace-based formative rubric for the reference scenario; Learning Library quiz attempts are now event-backed with objective-level feedback. No prose grading, validated psychometrics or competence claim. |
| Phase 6 — replay/debrief | Completed for reference scenario | Event timeline, semantic/state digests, assessment rationale, saved structured debrief, and bounded read-only counterfactual forks are implemented. Instructor feedback remains incomplete. |
| Phase 7 — educator authoring and curriculum | Partially completed | Scenario JSON authoring/validation, immutable local draft versions, authenticated publication boundary, curriculum composer, DAG validation, PROforma unlock predicates and reviewer-gated activation. Dynamic path coverage/fault-injection authoring validation and non-developer visual scenario builder remain incomplete. |
| Phase 8 — cohorts/facilitation/team cases | Blocked | The blueprint explicitly makes this conditional on authentication, roles, consent, data isolation, retention, backup/recovery and deployment decisions. Current local-default learner identity is single-user only; enabling cohorts would be unsafe. |

## Cross-cutting requirement audit

| Requirement | Status | Notes |
|---|---|---|
| One canonical event log for new 4.0 learning/simulation activity | Partially completed | Simulation, curriculum, scenario lifecycle and Learning Library quiz/open events append to the same Kernel ledger. Historical 3.0 repositories are not universally event-sourced. |
| PROforma as single executable logic language | Completed at 4.0 boundary | Scenario action models and curriculum unlock predicates use the existing bounded PROforma runtime. Full external PROforma language conformance is not claimed. |
| Fail-closed unknown/abstention | Completed for 4.0 guards and curriculum unlocks | Unsupported or missing predicate facts abstain; non-pass eligibility blocks the learner action. |
| Proof-carrying clinical/pedagogical output | Partially completed | Simulation assessment and PROforma/router outputs carry derivations and event references. Learning Library quiz records carry item and objective evidence but do not yet share the full clinical derivation envelope. |
| Deterministic replay | Completed for simulation run contract | Same scenario/model/seed/action sequence reproduces semantic trace/state digest. No broad cross-platform byte-for-byte guarantee for all legacy application workflows. |
| Open-world clinical knowledge states | Partially completed | Pulse and staged findings distinguish unavailable/unknown; complete source-feed semantics are not implemented across every legacy workflow. |
| Evidence lifecycle and impact graph | Partially completed | UCKS source/appraisal/review structures exist; full downstream impact graph from source update to all affected scenario/rubric versions is incomplete. |
| Process conformance | Partially completed | Trace-based rubric and PROforma task gates identify selected deviations. General multi-path process-mining/conformance analysis is not implemented. |
| Terminology ports | Partially completed | Embedded exact-match index and optional Snowstorm boundary exist; licensed full SNOMED CT ECL service is not bundled. |
| Standards/interoperability ports | Partially completed | FHIR/CQL/CDS Hooks/LTI/xAPI/SCORM adapters/descriptors exist. Institutional production launch/endpoint conformance and delivery reliability are external dependencies. |
| Adaptive learning IRT/FSRS/Brier | Partially completed | Fixed-parameter IRT, FSRS-style scheduling and Brier calculations exist. Parameters are not calibrated against representative cohort data. |
| Safety case/hazard traceability | Partially completed | Four-layer guards and audit infrastructure exist. A complete hazard log, named safety owners, residual-risk acceptance and independent clinical safety case are not complete. |
| Security/privacy | Partially completed | Local loopback deployment and reviewer-token gates exist. No general learner authentication, role management, multi-tenant data isolation or cohort privacy controls. |
| Model-free content generation | Completed for bundled content factory | Versioned packs, deterministic templates, validation, deduplication, draft review and distribution. Clinical facts must be authored/imported and approved; generator does not autonomously create verified medical facts. |
| Learner progress | Partially completed | Event-derived unit/quiz progress, objective breakdown and legacy portfolio measures. No authenticated multi-learner portfolio. |

## Files created or changed in 4.0.2

### Backend

- `backend/hsptl_core/hsp_tl40/scenario_authoring.py` — local scenario draft/version lifecycle, structural/model-reference validation and clinical-review-gated publication.
- `tests/test_z_4_0_2_learning_pathways.py` — one-time-suite coverage for new event contracts, scenario authoring/publishing, PROforma prerequisite semantics and the quiz/curriculum API flow.
- `backend/routers/hsp_tl40.py` — scenario authoring template, validation, draft and publication routes; published scenario root integration.
- `backend/routers/content_factory.py` — event-backed unit opens and quiz submissions, idempotency, objective aggregation, curriculum composition/activation and PROforma eligibility projection.
- `backend/hsptl_core/hsp_tl40/event_contracts.py` — new scenario, curriculum and learning event schemas and payload constraints.
- `backend/hsptl_core/hsp_tl40/kernel.py` — allowlisted event catalogue additions.
- `backend/hsptl_core/hsp_tl40/clinical_simulation.py` — scenario catalogue supports the local published-scenario root.
- `backend/hsptl_core/config.py` — release version 4.0.2.

### Frontend

- `frontend/src/components/ScenarioAuthoringPanel.tsx` — JSON package editor, validation, draft save and clinical-review publication UI.
- `frontend/src/pages/ContentFactoryPage.tsx` — curriculum composer, prerequisite sequence and reviewer activation.
- `frontend/src/pages/LearningLibraryPage.tsx` — server-scored, saved quiz submissions and active-curriculum gating.
- `frontend/src/pages/ProgressPage.tsx` — event-derived topic and objective progress.
- `frontend/src/pages/HomeDashboardPage.tsx` — learning-path progress summary.
- `frontend/src/lib/api.ts` — typed API contracts for new workflows.
- `frontend/src/App.tsx`, `frontend/src/index.css` — version and learning dashboard presentation updates.

### Documentation and release metadata

- `CHANGELOG.md`, `README.md`, `docs/hsptl40/event_catalogue.json`.
- `docs/LEARNING_EXPERIENCE_4.0.2.md`.
- `docs/BLUEPRINT_IMPLEMENTATION_AUDIT_4.0.2.md`.
- `RELEASE_STATUS_4.0.2.md`.

## One-time verification results

One consolidated verification pass was executed after implementation. Five gates passed and four failed/blocked. Backend test collection and local boot initially failed because the new scenario publication route omitted the FastAPI `Header` import; that import was corrected after the pass and was not rerun. Frontend typecheck/build were blocked by absent React/Vite dependencies after `npm ci` timed out offline. Exact results are recorded in `RELEASE_STATUS_4.0.2.md`. No second test/build pass was run.

## Launch

On Windows, run `install_hsptl.bat`, then `start_hsptl.bat`, and open `http://127.0.0.1:8000`. `check_hsptl.bat` reruns the consolidated test/build verification and should be skipped if preserving the one-time verification policy. Reviewer environment variables are documented in `docs/LEARNING_EXPERIENCE_4.0.2.md`. Keep the server on loopback.
