# Changelog

## 6.0.0 — Unified clinical learning and simulation platform

- Consolidated the seven learner workspaces: Clinic, Lab, Ward, Library, Learning, Exam Hall and Rounds, with My Profile and the daily archive in the shared workspace shell.
- Made the persisted Daily Case Lottery the single source for the daily case; Clinic and Ward resolve to the same date-scoped draw, and historical assignments are archived without answer or diagnosis disclosure.
- Expanded the versioned clinical-event and specialty catalogues used to theme learning and case discovery without inventing patient cases.
- Integrated deterministic local content composition, startup preparation and workspace-level content refresh without requiring an AI model or API key.
- Added automated metadata discovery/import from supported external evidence services while keeping provenance, licence permissions, safety screening, clinical review and learner post-use validation as distinct controls.
- Added learner post-use assessments and version-specific educational validation scoring, with role-aware evidence and qualified domain sign-offs; the score is not a clinical competency or entrustment measure.
- Consolidated workspace-to-engine contracts and exposed operational status for the seven shared engines.
- Strengthened the Windows clean-install and release workflow, including Python dependency checks, `npm ci`, TypeScript typecheck, Vite production build, startup preflight, backend tests and health smoke test.
- Promoted backend and frontend application metadata to the same `6.0.0` release identity.

**Safety boundary:** HSPTL is for supervised clinical education and simulation. Automated import, machine screening, learner feedback and validation scores do not authorise clinical decisions or unsupervised practice. External-source reuse remains subject to the source's actual licence and terms.

## 5.2.0 — Simplified navigation and automatic learning content

- Reduced the primary navigation to seven essential learner destinations; all existing destinations remain available in the Essentials / All modules directory.
- Added a global **Update content** action available from every workspace.
- Added deterministic, local startup preparation for nine draft output types across Clinic, Exam Hall, Rounds, Lab, Ward and Simulation.
- Added on-call scenarios, SBAR handover templates and simulation briefs to the content factory.
- Made content refresh idempotent and version-aware; unchanged outputs are reused and malformed new packs do not replace the last valid factory.
- Kept generated educational material in draft status; no automatic clinical approval or publication.
- Refreshed the vector brand assets to follow the original HSPTL reference monogram.

## 5.1.0 — Learning intelligence and launcher reliability

- Added reviewer-entered source reliability appraisals, explicitly separate from rights and evidence certainty.
- Added learner practice preferences, deterministic case recommendations and saved reasoning submissions.
- Updated Daily Case Lottery UI to save a reasoning attempt before answer reveal.
- Added additive SQLite migration 35.
- Fixed legacy institutional auth schema migration ordering and atomicity.
- Improved Windows installer residue cleanup, pip diagnostics and dependency consistency checks.
- Added startup import/migration preflight before browser launch.

## 5.0.0

See the 5.0.0 release history and `RELEASE_STATUS.md` for Synthetic Data Factory, provenance, rights registry, local sources, case lottery, engine integration and pearls factory.
