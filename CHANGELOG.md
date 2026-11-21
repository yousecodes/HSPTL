# Changelog

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
