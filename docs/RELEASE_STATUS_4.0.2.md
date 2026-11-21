# HSPTL 4.0.2 — implementation record (superseded)

> **Superseded.** This is the historical 4.0.2 implementation record. The current release status,
> including the completed consolidated verification (9 gates passed, 0 failed; 287 backend tests),
> is in [RELEASE_STATUS.md](RELEASE_STATUS.md).

**Implementation status:** 4.0.2 learning pathways and scenario authoring features integrated. **Verification status at the time:** consolidated verification had not been executed.

## Delivered in 4.0.2

- Server-scored Learning Library quizzes, idempotent retry handling and canonical event records.
- Event-derived topic and objective progress in Overview and Progress Board.
- Curriculum composition from versioned content-pack units, prerequisite DAG validation, PROforma unlock predicates and reviewer-gated activation.
- Local scenario package authoring, structural validation, PROforma model-reference validation, immutable versioned draft storage and separately credentialed clinical-review publication.
- Scenario draft/publication lifecycle events and local published-scenario discovery through the existing ScenarioCatalog.
- New event schemas and checked-in event catalogue entries.

## Existing capability retained

- One FastAPI/SQLite modular monolith and React client.
- Existing six workspace skins and legacy feature routes.
- HSPTL 4.0 Kernel, Reasoner, PROforma Logic, Composer, Router, Guards and Explain modules.
- In-process Z3/Clingo boundaries, Pulse bridge, standards/interop adapters and deterministic simulation vertical slice.
- Model-free content pack discovery, deterministic content factory, review and distribution lifecycle.

## Known incomplete or blocked requirements

- Phase 8 cohorts/team facilitation is blocked pending a real authentication/authorization design, consent, data isolation, retention and deployment governance. The current learner identifier is local single-user only.
- Phase 7 scenario authoring is partially complete: the JSON package editor and structural validator exist, but full dynamic path reachability/fault-injection validation and a non-developer visual scenario builder remain incomplete.
- The asthma scenario and rubric remain `draft_pending_clinical_review`; no clinical approval is asserted by this package.
- The simulation transition model is an educational deterministic fixture, not validated physiology.
- Full migration of legacy 3.0 persistence to the 4.0 canonical event ledger is incomplete.
- FHIR/CQL/CDS Hooks/LTI/xAPI/SCORM external institutional integrations remain adapter boundaries; external endpoint and identity configuration is required.
- IRT parameters are fixed and not cohort-calibrated; FSRS output remains a scheduling implementation, not proof of learning.
- The complete safety case, clinical validation, educational validation and production security assessment require institutional work.

## Verification

Not run for 4.0.2 at the time of writing. The consolidated pass was subsequently executed against
5.0.0 and is recorded in [RELEASE_STATUS.md](RELEASE_STATUS.md): 9 gates passed, 0 failed, 287 backend
tests passing, frontend typecheck and production build green.

## Windows launch

1. Extract the `HSPTL` folder to a local, non-synchronized directory.
2. Run `install_hsptl.bat` (this installs runtime dependencies and builds the frontend; it requires package access or a populated local npm cache).
3. Run `start_hsptl.bat`.
4. Open `http://127.0.0.1:8000`.

Do not run `check_hsptl.bat` if preserving the one-time verification policy; it reruns the consolidated tests and frontend build. The one recorded verification result is above.

The app binds to loopback. Do not expose it to a public network. Configure `HSPTL_REVIEWER_TOKEN` / `HSPTL_REVIEWER_ID` for curriculum activation and `HSPTL_CLINICAL_REVIEWER_TOKEN` / `HSPTL_CLINICAL_REVIEWER_ID` for scenario publication. Each token must be at least 32 characters. Institutional reviewer qualification verification remains external to this local application.

## HSPTL 5.0.0 implementation record

- Backend and frontend package metadata updated to 5.0.0.
- Password-backed institutional subjects and PBKDF2-SHA256 local sessions added.
- Learner, facilitator, reviewer and admin role boundaries added.
- Cohorts, members, facilitation sessions and facilitator events are durable local records.
- Privacy, retention and SQLite recovery controls added.
- Scenario visual metadata fields and trace/fault matrices are available.
- FHIR base configuration, CQL export limits, CDS Hooks card/descriptor exports and terminology lookup are bounded adapters.
- Psychometric activation remains fail-closed until independent representative validation.
- Clinical-safety ownership and approval remain external institutional work.

These capabilities do not claim enterprise SSO/MFA, production encryption, multi-tenant isolation,
clinical validity or validated psychometric competence scores.

## Current implementation correction and verification record

The implementation-complete build was followed by one consolidated verification pass. That pass found:

- A missing local Python virtual environment and dependencies.
- Four shared frontend icon-name union omissions.
- Learning/curriculum event types missing from the deterministic engine allowlist.

Corrections were then made:

- A Python 3.13 `.venv` was created and populated from `requirements-dev.txt`.
- The shared icon registry was completed.
- Learning, curriculum, scenario, order, handover and debrief event types were aligned across the engine, Kernel, event schemas and runtime contracts.
- Structured simulation debrief and bounded read-only counterfactual replay were added to the learner workflow.

Post-correction targeted verification (not a repeated consolidated full-suite pass):

- Frontend typecheck: passed.
- Frontend production build: passed.
- Python compile: passed.
- Content pack validation: passed.
- Learning/curriculum targeted tests: 6 passed.
- HSPTL 4.0 deterministic targeted tests: 19 passed.
- Clinical simulation targeted tests: 12 passed.
- Backend health boot: HTTP 200.

The consolidated pass remains recorded as the one-time full gate; subsequent results above are targeted checks for corrections and changed modules.

### Consolidated verification pass — 2026-11-20

The single requested consolidated pass was executed once.

| Gate | Result | Detail |
|---|---|---|
| Python environment | Passed | Python 3.13.5; required backend/test modules available. |
| Product identity scan | Passed | No prohibited legacy identifiers found. |
| Python compile | Passed | `compileall` completed. |
| Content pack schema/recipe validation | Passed | 1 pack, 8 units, 24 questions and 48 deterministic recipes validated. |
| Backend test suite | Failed at collection | Seven test modules failed to import the app because `Header` was missing from `backend/routers/hsp_tl40.py`; test assertions did not execute. The missing import was corrected after this pass. No rerun was performed under the one-time policy. |
| Frontend typecheck | Blocked/failed | `react` and its JSX runtime/types were unavailable because the offline `npm ci` attempt timed out. The reported JSX/type errors are cascading dependency-resolution errors and cannot establish source-level type correctness. |
| Frontend production build | Blocked/failed | Same missing frontend dependencies; no production bundle was produced. |
| Launcher contract | Passed | Expected Windows launchers and commands are present. |
| Local backend boot | Failed | App import stopped at the same missing `Header` symbol. The import was corrected after the pass; boot was not rerun. |

**Final verification summary:** 5 gates passed, 4 failed/blocked. The import correction is included in the delivered source but remains unverified by a rerun. This package is an implementation build, not a production-qualified release.
