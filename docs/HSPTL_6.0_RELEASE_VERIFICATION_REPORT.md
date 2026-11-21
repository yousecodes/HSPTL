> Historical preview record: this report describes the earlier 5.2.0-based 6.0 development candidate and its then-open gates. It is superseded by [the HSPTL 6.0.0 promotion verification report](HSPTL_6.0.0_RELEASE_VERIFICATION_REPORT.md) and [current release status](RELEASE_STATUS.md).

# HSPTL 6.0 — Phases 5–8 Implementation Report

**Artifact:** HSPTL 6.0 development preview, built on the 5.2.0 application baseline  
**Scope:** Clinical Events, Daily Case Archive, Specialty Rounds, My Profile / Clinical Journey, export and release preparation  
**Release identity:** `APP_VERSION` remains `5.2.0`; this is not a final 6.0 release.

## Phase 5 — Variable clinical events

- Persisted the clinical event catalogue in SQLite (`clinical_event_catalogue`) and seed it idempotently from the existing 30-theme catalogue.
- Catalogue records are versioned and can be added, revised or paused without a frontend redeployment.
- Added reviewer-token-gated `PUT /api/v5/clinical-events/{event_id}` and learner-safe `GET /api/v5/clinical-events` endpoints. The existing `/api/clinical-catalogue/events` endpoint now reads the persisted catalogue.
- Added event matching against eligible case specialty, complaint, title, stem and configured case signals. An event is only selected when at least one eligible case matches.
- Event selection uses cryptographically secure weighted randomness, configurable `selection_weight`, and configurable `cooldown_days`. If no event matches, the ordinary daily case draw continues without an event. If no eligible case exists, the system abstains.
- The selected event is snapshotted into the persisted daily lottery row, together with pool digest and policy version. Refresh/restart returns the same case/event assignment.
- Added reviewer controls to the Clinical Event Catalogue panel for creating and pausing themes.

**Safety boundary:** event themes are educational metadata, not live hospital alerts, triage rules or clinical protocols. Events never fabricate cases or bypass clinical review, publication and reuse-rights gates.

## Phase 6 — Daily Case Archive and Specialty Rounds

- Replaced the old Archive-to-specialty-directory route with a dedicated Daily Case Archive page.
- Archive records are grouped newest-first by date and searchable by presenting complaint, specialty and event.
- Archive projection includes complaint, age-at-encounter, specialty, difficulty, event snapshot and assignment metadata only. It deliberately excludes diagnosis, answer/reveal payload and patient date of birth.
- Historical event icon/title/category are read from the assignment snapshot, so later catalogue edits do not rewrite history.
- The Archive action remains available from the workspace header, including when no daily case is eligible.
- The Rounds workspace now opens the specialty-indexed learning experience (`SpecialtiesPage mode="rounds"`). Viva station practice remains accessible separately under All Modules.
- Daily case source display now includes available source type, licence and reuse status alongside the source link.

## Phase 7 — My Profile and Clinical Journey

- Preserved the single My Profile destination with Profile and Progress tabs.
- Added local learner-goal management to Profile. Goals are personal study intentions, not competency sign-offs.
- Clarified that the self-described training stage is display-only; validation permissions rely on the institution-assigned level from the authenticated session.
- Added evidence-derived learning milestones in Progress for reasoning attempts, debriefs, quizzes, spaced review, OSCE practice and topic activity.
- Milestones explicitly represent recorded educational activity, not clinical competence, entrustment or readiness for unsupervised practice.

## Phase 8 — Sharing, performance and release preparation

- Added explicit JSON export of the learner's existing portfolio/learning journey from Progress. Export is user-initiated and generated locally in the browser.
- Kept route-level lazy loading; the new Daily Case Archive is lazy-loaded and does not increase the initial route bundle by being eagerly imported.
- Preserved the existing modular monolith, local-first architecture, seven engines, source governance, post-use validation and API-key-free local content generation.
- Added migration coverage for event snapshot, pool digest and policy-version fields in existing lottery databases.
- Packaged a source ZIP with SHA-256 manifest and independently verified every manifest entry and ZIP CRC.

## Database/API changes

Additive schema changes in `CaseLottery`:

- `clinical_event_catalogue(event_id, event_json, active, version, updated_at)`
- `lottery_draws.event_json`
- `lottery_draws.pool_digest`
- `lottery_draws.policy_version`

Existing rows are preserved; missing columns are added through additive migration. Event catalogue seeds use `INSERT OR IGNORE` so administrator edits are not overwritten on restart.

New/updated API routes:

- `GET /api/v5/clinical-events`
- `PUT /api/v5/clinical-events/{event_id}` (reviewer token required)
- `GET /api/clinical-catalogue/events` (now reads persisted event catalogue)
- `GET /api/v5/lottery/history` (non-revealing archive projection)
- Existing `GET /api/v5/lottery/daily` now includes the persisted event snapshot when a compatible event is selected.

## Verification performed

- `python -m compileall -q backend scripts` — passed.
- `python scripts/validate_content_packs.py` — passed; 1 pack, 8 units, 24 questions and 48 deterministic output recipes.
- `python scripts/startup_preflight.py` — passed; database migrations and application imports completed.
- `python -m pytest -q` — **502 passed**.
- Frontend TypeScript/TSX syntax transpilation — **40 files, zero syntax diagnostics** using the globally available TypeScript compiler API.
- ZIP CRC test — passed.
- SHA-256 manifest verification — all packaged source entries verified.

## Blocked release gates / limitations

- **Frontend typecheck and Vite production build are not verified.** `npm ci --offline` failed because Vite was not cached; an online `npm ci` attempt timed out while resolving/downloading packages. Global `tsc --noEmit` consequently stopped because `@types/node`, `@types/react` and `@types/react-dom` were unavailable. Syntax transpilation is not a substitute for semantic typechecking or a production build.
- Windows clean-install/launcher execution was not performed in this environment.
- Archive history is capped at 365 records per request; this version does not yet expose cursor-based pagination or learner-specific completion state. The reveal count is explicitly labelled as installation-wide, not as the current learner's completion.
- The event matching algorithm is metadata-based discovery, not clinical triage. The event catalogue still requires institutional curation and review.
- Cohort analytics, SSO/MFA, hardened multi-tenant isolation and production institutional deployment remain outside this preview.

## Final status

Phases 5–7 workflows and the Phase 8 export/performance/release-preparation work are implemented in this development preview. The final 6.0 release gate remains open until the frontend dependencies can be installed, the full typecheck and production build pass, and a clean Windows installation check is completed. Do not treat this preview as a clinically validated or institutionally accredited system.

## Release verification addendum — 21 November 2026

The release-verification scripts and Windows automation were hardened after reviewing the actual installer/release-check paths.

### Fixes made

- Aligned `scripts/verify_release.py` with the Windows installer: both 64-bit Python 3.12 and 3.13 are now accepted. The verifier previously rejected 3.12 even though `install_hsptl.bat` explicitly supported it.
- Added unit coverage for supported/unsupported Python versions and 32-bit rejection.
- Added `HSPTL_NO_PAUSE=1` support to the install, check and startup batch files so they can be run unattended in CI while retaining interactive pauses for normal users.
- Normalised edited Windows batch files to CRLF line endings.
- Added `.github/workflows/windows-release-check.yml`, which runs on a clean `windows-latest` runner, asserts that no virtual environment or frontend build artifacts pre-exist, runs the actual Windows installer (including `npm ci`, TypeScript typecheck and Vite build), then runs `check_hsptl.bat` including the full backend test suite and local backend boot/health smoke test.

### Verification performed in this environment

- Runtime: 64-bit Python 3.13.5; Node.js 22.16.0.
- Backend suite: **506 passed** (includes 4 release/Windows workflow contract tests).
- `scripts/verify_release.py --skip-frontend`: **7 gates passed, 0 failed**, including full tests and local backend `/api/health` smoke test.
- `scripts/verify_release.py --skip-tests --skip-frontend`: **6 gates passed, 0 failed**.
- Python compilation, content-pack validation and startup preflight: passed.
- Frontend TypeScript/TSX syntax parse using globally available TypeScript 5.8.3: **40 files, zero syntax diagnostics**. This is syntax-only; it is not semantic typechecking.
- Frontend dependency installation: **blocked**. `npm ci` could not resolve multiple locked packages from `registry.npmjs.org` (`EAI_AGAIN`). React, React DOM, Vite and the project-local type packages therefore could not be installed. The semantic TypeScript check and Vite production build were not run and are not claimed as passing.
- Windows batch execution / clean Windows install: **not run here** because this verification container is Linux and has no Windows command interpreter, PowerShell or Wine. The real Windows clean-install verification workflow is included in the source and must run on a GitHub-hosted Windows runner before release promotion.

### Promotion decision

**Do not promote this archive to final HSPTL 6.0.0.** The application and frontend package versions remain 5.2.0. Two release gates remain unverified: (1) npm dependency installation followed by semantic TypeScript typecheck and Vite production build; and (2) successful execution of the included Windows clean-install workflow. The archive is a release-verification candidate, not a final 6.0 release.
- Shared host interpreter `python -m pip check`: reports an unrelated preinstalled-environment conflict (`moviepy 2.2.1` requires `pillow<12.0`, while the shared tool image has `pillow 12.3.0`). Neither package is declared in HSPTL's `requirements.txt` or `requirements-dev.txt`; the Windows installer creates an isolated `.venv`, where its own `pip check` is part of the clean-install workflow. The shared interpreter result is not represented as an HSPTL dependency pass.
