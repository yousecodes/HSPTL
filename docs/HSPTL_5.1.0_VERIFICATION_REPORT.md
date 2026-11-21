# HSPTL 5.1.0 — Implementation and verification report

Date: 2026-11-20

## Implemented

- Fixed legacy institutional SQLite initialization by creating tables, adding missing `institution_id` columns, then creating dependent indexes in one explicit transaction. Existing rows are preserved; initialization is idempotent.
- Added `scripts/startup_preflight.py`; `start_hsptl.bat` now sets `HSPTL_HOME` before imports, runs the backend import/migration preflight, then resolves the port and opens the browser.
- Added `scripts/clean_venv_artifacts.py`, which removes only known interrupted pip-upgrade temporary artifacts inside the project's `.venv` site-packages. Installer now disables pip version-check noise and runs `pip check`.
- Added source reliability appraisal across five reviewer-scored dimensions, separate from licensing, evidence certainty and clinical validity.
- Added learner case preferences, deterministic practice recommendations, and persisted formative reasoning submissions before answer reveal.
- Updated the Daily Case Lottery UI to capture reasoning and confidence before revealing the debrief; added preference controls and recommendations.
- Bumped application, frontend and synthetic manifest version metadata to 5.1.0; added release notes.

## Verification actually performed

- Full Python suite: **473 passed, 0 failed** at the consolidated run.
- Focused institutional + next-increments suite after adding the final successful-attempt regression: **118 passed, 0 failed**.
- Python compilation: passed.
- Content pack validation: passed.
- Product identity scan: passed.
- Local Uvicorn boot: passed; `/api/health` returned HTTP 200.
- Startup preflight: passed against a fresh temporary HSPTL data directory.
- Package ZIP integrity: passed.
- Archive manifest: **334 files, zero hash mismatches**.

## Not verified / outstanding

- `npm ci` timed out in this environment. Consequently frontend TypeScript and production build could not complete because React and its type packages were unavailable. Run `install_hsptl.bat` on a connected Windows machine to finish these checks.
- The consolidated verification recorded 6 passing and 3 failing gates: frontend typecheck, frontend build (both blocked by absent npm dependencies), and an overly literal launcher-contract string check. The installer contract was corrected after that run, but the full release script was not rerun.
- The batch files were inspected and their Python startup preflight was exercised in this Linux environment; actual Windows CMD behavior remains to be confirmed on the target Windows machine.
- This is not production-certified clinical software. Institutional identity, hardened multi-tenancy, encryption-at-rest, clinical validation and institutional governance limitations remain as documented in `RELEASE_STATUS.md`.

## Archive

`HSPTL-5.1.0-Complete.zip`

SHA-256: `697ece7f43732eca7f654cd0a78c323480a86ed3776a8fff2861be89bcb91e86`
