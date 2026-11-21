# HSPTL 6.0.0 — Release promotion verification report

**Prepared:** 2026-11-21  
**Package identity:** `6.0.0`  
**Artifact status:** version-aligned release candidate; a fresh Windows workflow run for the exact pushed commit is required before tag/publication.

## Promotion changes

- Updated backend `APP_VERSION`, frontend `package.json`/`package-lock.json`, synthetic-data provenance version, operational overview API and user-visible app labels to `6.0.0`.
- Changed API overview reporting to use the canonical backend version constant.
- Added a regression assertion that backend and frontend package/lockfile versions remain aligned.
- Updated README, changelog and current release-status/checklist documentation.
- Removed unresolved Git merge-conflict markers from README and corrected the release-status links.
- Preserved historical 5.x and 6.0 development implementation reports as historical records; they are not rewritten to imply that earlier previews were final releases.

## Verification for this source candidate

- Full backend suite: **521 passed, 0 failed** (`python -m pytest -q`, 32.00 seconds).
- Release verifier with the test and frontend stages skipped: **6 passed, 0 failed**. This included the supported Python 3.13 runtime/dependency check, product-identity scan, Python compilation, content-pack schema/recipe validation, Windows launcher contract and local backend `/api/health` smoke test.
- A second release-verifier invocation with tests enabled timed out during its redundant second test run; the full test suite had already completed independently and passed. The wrapper timeout is not represented as a pass.
- Frontend install/typecheck/production build: the maintainer reports that the corrected native Windows workflow completed green before this version-alignment increment. They have not yet been rerun here against this exact 6.0.0 candidate.
- Native Windows verification for the exact 6.0.0 source commit: pending a fresh GitHub Actions run after push.

## Required publication sequence

1. Push the version-aligned source commit to `main`.
2. Confirm `.github/workflows/windows-release-check.yml` is green for that exact commit.
3. Create and push annotated tag `v6.0.0`.
4. Publish GitHub Release `v6.0.0` with the ZIP, SHA-256 checksum and this report attached.

## Product boundary

HSPTL is educational software for supervised learning and simulation. It is not accredited clinical software, not a clinical decision-support system and not a substitute for qualified clinical supervision. Educational validation metrics do not establish clinical competence or entrustment.
