# HSPTL 6.0.0 — Promotion candidate status

**Application identity:** `6.0.0`  
**Status:** version promotion and source release package prepared. Do not create the `v6.0.0` tag until the fresh Windows workflow passes for the exact pushed commit.

## Earlier native Windows confirmation

The maintainer confirmed that the corrected Windows clean-install and release-verification workflow completed green after the Windows test fixes. That run validates the corrected 5.2.0-based source before the following version-only/application-metadata alignment increment.

## Version-aligned source checks

- Full backend suite: **521 passed, 0 failed**.
- Static/boot release-verifier gates: **6 passed, 0 failed**.
- Frontend and native Windows must be reconfirmed by the fresh exact-commit workflow below.

## Final exact-commit gate

Push the 6.0.0-aligned source, then confirm a new green run of `.github/workflows/windows-release-check.yml`. The workflow performs the clean Windows installer, npm dependency install, TypeScript typecheck, Vite build, isolated startup preflight, full backend release checks and health smoke test.

The versioned release package and SHA-256 files should be attached to the GitHub Release after that run passes. See `RELEASE_STATUS.md` and `HSPTL_6.0.0_RELEASE_VERIFICATION_REPORT.md`.
