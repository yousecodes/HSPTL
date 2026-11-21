# HSPTL 4.0.2 — event-backed learning pathways and scenario authoring

## What changed

### 1. Learning Library persistence

The Learning Library now submits answers to the backend rather than treating the browser as the score authority. The backend checks answer indexes against the versioned content pack, computes the formative result, creates objective-level aggregates, and appends `platform.learning.quiz_submitted` to the existing HSPTL 4.0 event ledger. A caller-supplied idempotency key is checked under a process lock; retries with the same key return the original attempt rather than recording another result. Reusing a key for another unit is a conflict.

Opening a unit appends `platform.learning.unit_opened`. Both event types retain learner scope (`local-default` for the current local single-user deployment), curriculum identity/version, and source content pack/version. This is a local single-user identity, not an authentication system.

### 2. Derived learning progress

`GET /api/content-factory/progress` folds unit-open and quiz-submission events into per-topic counts, latest scores and objective-level performance. The Overview and Progress Board render these projections. No computed progress values are written to a second database. A topic is considered completed for pathway prerequisite purposes when at least one quiz submission is recorded; this is an activity-completion rule, not a mastery threshold.

### 3. Curriculum composer

`POST /api/content-factory/curricula/compose` accepts a title, selected content-pack unit IDs and prerequisite graph. It:

- verifies that each unit exists and is unique;
- rejects prerequisite references outside the selected set;
- runs the existing deterministic topological ordering algorithm and rejects cycles;
- maps each stage to learning objectives, assessment count and source pack/version;
- writes a PROforma predicate (`set_includes`) for each prerequisite gate; and
- appends `platform.curriculum.draft_created` with the content digest.

`POST /api/content-factory/curricula/{id}/activate` requires the configured reviewer token and appends `platform.curriculum.activated`. Learner unit-open and quiz-submission requests are bound to the active curriculum version. The active stage predicate is evaluated by the existing PROforma guard/router; fail or abstain prevents the action. The current completion predicate is intentionally simple: a recorded quiz attempt completes a unit for sequencing purposes.

### 4. Scenario package authoring

The Content Factory includes a JSON scenario package editor seeded from the reference synthetic asthma package. The author can edit a scenario package, validate it and save an immutable local draft version. Validation checks the scenario contract, synthetic-patient marker, unique action/objective/criterion identifiers, rubric total, scheduled-event identities/times, observation-state withholding declaration, source metadata and referenced PROforma model paths.

Draft packages are stored under the local HSPTL data directory (`scenario_drafts/<scenario-id>/<version>/scenario.json`). A changed package cannot overwrite the same version; increment the version. Draft save and publication append `platform.scenario.draft_saved` and `platform.scenario.published` events.

Publication requires `HSPTL_CLINICAL_REVIEWER_TOKEN` (at least 32 characters) and `HSPTL_CLINICAL_REVIEWER_ID`. The application checks the configured credential only. The deploying institution remains responsible for verifying the reviewer's clinical qualification, scope and authority. Published versions are archived under `scenarios/<scenario-id>/versions/<version>/` and the current published version is made discoverable by the existing ScenarioCatalog.

### 5. New event contracts

- `platform.curriculum.draft_created`
- `platform.curriculum.activated`
- `platform.learning.unit_opened`
- `platform.learning.quiz_submitted`
- `platform.scenario.draft_saved`
- `platform.scenario.published`

The executable event schemas and checked-in event catalogue are aligned. All these events use the existing Kernel and hash-chained SQLite event ledger.

## Configuration

Curriculum activation reuses:

- `HSPTL_REVIEWER_TOKEN` (minimum 32 characters)
- `HSPTL_REVIEWER_ID`

Scenario publication uses separate credentials:

- `HSPTL_CLINICAL_REVIEWER_TOKEN` (minimum 32 characters)
- `HSPTL_CLINICAL_REVIEWER_ID`

These should be configured in the local process environment by the deploying institution. Do not commit credentials to source control or expose the local server to a public network.

## Routes added

- `POST /api/content-factory/units/{unit_id}/opened`
- `POST /api/content-factory/units/{unit_id}/attempts`
- `GET /api/content-factory/progress`
- `GET /api/content-factory/curricula`
- `POST /api/content-factory/curricula/compose`
- `POST /api/content-factory/curricula/{curriculum_id}/activate`
- `GET /api/v4/simulation/scenario-authoring/template`
- `GET /api/v4/simulation/scenario-authoring/drafts`
- `GET /api/v4/simulation/scenario-authoring/drafts/{scenario_id}`
- `GET /api/v4/simulation/scenario-authoring/drafts/{scenario_id}`
- `POST /api/v4/simulation/scenario-authoring/validate`
- `POST /api/v4/simulation/scenario-authoring/drafts`
- `POST /api/v4/simulation/scenario-authoring/drafts/{scenario_id}/publish`

## Explicit limitations

- Scenario validation is structural and checks PROforma model references. It does not yet execute a full reachability/fault-injection harness over every scenario path; the validator reports dynamic path coverage as not run.
- Scenario package publication credential verification is not a substitute for an institutional clinical governance process or external identity proofing.
- The local learner identifier is a fixed single-user identifier. It must not be reused for multi-user deployments.
- No cohort/team workflow is enabled. Authentication, role-based access control, consent, data isolation, retention, secure backup/recovery and deployment governance are prerequisites.
- Existing 3.0 tables and repositories remain for compatibility. A complete migration of every legacy workflow into the single 4.0 event ledger is not complete.
- The clinical asthma scenario remains draft pending qualified review. It is a synthetic teaching model, not a validated physiological model or treatment protocol.
