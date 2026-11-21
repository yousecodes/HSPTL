# HSPTL Daily Case Hierarchy Fix — Implementation Report

**Artifact type:** HSPTL 6.0 development preview / UI correction  
**Underlying application version:** 5.2.0 (not promoted to 6.0.0)  
**Date:** 2026-11-21

## Problem confirmed

Clinic mounted two separate daily-case experiences at the top of the page:

1. The Clinic daily challenge, served by `/api/clinic/daily`, uses the HSPTL-curated puzzle bank plus human-approved imported puzzle adaptations.
2. The shared Clinic/Ward reviewed-case lottery, served by `/api/v5/lottery/daily`, uses its own `lottery_cases` table and requires publication, clinical review and reuse-rights clearance.

When the second pool was empty, its prominent **“No eligible case today”** card appeared before the actual Clinic daily challenge. This was misleading: an empty shared lottery pool did not mean the Clinic daily challenge was unavailable.

The clinical event catalogue is a catalogue of educational event themes. It is not itself a patient-case source and is not a prerequisite for the Clinic daily challenge.

## Changes implemented

- Promoted the actual Clinic daily challenge to the top of the Clinic workspace.
- Moved the shared reviewed-case lottery below the primary daily case under an **Additional Learning Content** section.
- Replaced the ambiguous empty-state heading with **“Shared reviewed-case pool is empty”**.
- Added explicit text explaining that the lottery's empty state does not affect the Clinic daily teaching case.
- Kept the lottery eligibility gate intact. No unreviewed, unpublished or rights-unclear case is substituted into that governed pool.
- Made the primary case's `source_title` visible in the case header for clearer provenance.
- Clarified that the Clinical Events Catalogue contains teaching themes, not patient-case content.
- Added frontend contract tests to prevent the lottery empty state from being placed before the primary Clinic daily challenge and to preserve the case-source separation.

## Daily case source model verified

The Clinic daily challenge pool in `backend/main.py::_pool()` combines:

- The 12 built-in HSPTL-curated educational vignettes in `backend/hsptl_core/puzzles.py`.
- Human-approved imported puzzle adaptations returned by `load_approved_puzzles(STORE)` from the `ApprovedPuzzle` store.

This is not the same as the governed shared lottery pool. Raw synthetic FHIR records are not automatically converted to diagnostic puzzles; source metadata is not itself a reviewed teaching case. External adaptations remain subject to licensing and human approval controls.

## Verification

- Full backend test suite: **508 passed**.
- Focused frontend-contract, lottery and API tests: **129 passed**.
- Python compile, content-pack validation, product-identity scan and launcher contract checks passed in the release-verification run.
- The frontend dependency install/build could not be rerun in this build environment: `npm ci` timed out while contacting the npm registry, and an offline retry confirmed the Vite package was not cached. Run `install_hsptl.bat` on Windows to perform the production frontend typecheck/build for this exact patch.
- This environment is Linux; native Windows execution is not claimed here.

## Release status

This is a focused development preview, not a 6.0.0 release promotion. `APP_VERSION` and `frontend/package.json` remain at 5.2.0 pending the outstanding full release gates.
