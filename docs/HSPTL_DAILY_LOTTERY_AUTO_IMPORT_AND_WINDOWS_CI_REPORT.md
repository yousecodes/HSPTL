# HSPTL — Daily lottery, automatic human-source import and Windows CI update

**Build identity:** internal project version remains `5.2.0`  
**Status:** implementation preview; not promoted as HSPTL 6.0.0

## 1. Clinic Daily Case is now lottery-only

- `ClinicPage` mounts `DailyCaseLottery` as its only Daily Case source. The former Clinic puzzle daily-challenge card is no longer rendered in parallel.
- Clinic and Ward Board continue to share the same persisted date draw.
- Startup idempotently seeds the HSPTL-authored teaching vignette bank into `lottery_cases`.
- `curated` is a distinct curriculum status. It is not represented as independent expert clinical validation. Published, rights-permitted curated teaching vignettes can be drawn, alongside other eligible published cases that have been reviewed or validated and have suitable rights.
- The eligible database query now includes `curated`, matching the eligibility policy.
- If the day's draw was previously persisted as `no_eligible_case`, the lottery rechecks eligibility and can recover that record after startup seeding, preserving its draw ID. An already selected daily case remains stable.
- The event catalogue remains a source of themes, not a source of patient cases. No synthetic-patient record or event theme is substituted into the lottery.

The seeded curriculum cases are fictional HSPTL-authored educational vignettes with source links. They are **not real patient records**. External articles/metadata imported into UCKS are not silently converted into patient cases.

## 2. Automatic human-authored source import

Managed public-source profiles now import records without per-record human approval and label successful structural/provenance screening as `machine_screened`.

Default API-key-free providers:

- Europe PMC — abstract/metadata and full text only when the individual record explicitly declares an allow-listed CC0, CC-BY or CC-BY-SA licence.
- PubMed — bibliographic records and abstracts where supplied.
- ClinicalTrials.gov — study registry metadata and descriptions.
- Crossref — bibliographic metadata.

The automatic screen checks provider identity, stable external identifier, non-empty/bounded title and body, and an HTTPS source URL. It does not evaluate clinical truth, certainty, completeness, or fitness for patient care. A machine-screened record is available as an imported knowledge record, but it is not called clinically reviewed or validated.

Rights are item-specific. Public availability alone does not grant text reuse. Non-allowlisted, unknown, NC or ND full text is not fetched by the Europe PMC importer. Explicitly allow-listed fetched full text can be used by the deterministic Pearls factory with source attribution; other content remains citation-only unless a separate source-rights decision permits text use. Derived artefacts remain draft-gated; the importer does not auto-publish or auto-validate them.

Existing UCKS records from managed profiles are idempotently migrated from `harvested` to `machine_screened` on successful re-sync, unless their state is already `reviewed`, `validated` or `rejected`.

## 3. Avoiding a stale frontend bundle

- `frontend/package.json` now runs `clean-dist.mjs` before TypeScript checking and Vite production build. The frontend contract suite also checks that every literal icon reference is declared; the new lottery icon is registered.
- `install_hsptl.bat` removes the previous `frontend/dist` before `npm ci`.
- If dependency installation, typechecking or Vite build fails, the previous bundle is not left behind to be served as though it were the newly updated UI.

## 4. Native Windows clean-install workflow

`.github/workflows/windows-release-check.yml` now runs on push, pull request and manual dispatch on `windows-latest`. It starts with no `.venv`, `frontend/node_modules` or `frontend/dist`, then runs:

1. Python 3.13 x64 and Node.js 22.16.0 setup.
2. `install_hsptl.bat` (pip install, `pip check`, `npm ci`, TypeScript typecheck, Vite production build).
3. `scripts/startup_preflight.py` using a CI-isolated `HSPTL_HOME`.
4. `check_hsptl.bat` (full release verification and backend health smoke test).
5. Production `frontend/dist/index.html` assertion and upload of `frontend/dist` as a build artifact.

See `WINDOWS_CLEAN_INSTALL_AND_PRODUCTION_BUILD.md` for copy/paste local PowerShell commands and the GitHub Actions procedure.

## 5. Verification actually performed in this workspace

| Check | Result |
|---|---|
| Python backend test suite | **516 passed** (including a static frontend icon-name contract) |
| `scripts/startup_preflight.py` with isolated data home | **Passed** |
| Python compile, content-pack validation, identity scan and launcher contract checks | **Passed** |
| Frontend `npm ci` | **Not completed** — npm registry DNS retry failed with `EAI_AGAIN` |
| Frontend TypeScript typecheck after these changes | **Not run** — dependencies could not be installed |
| Frontend Vite production build after these changes | **Not run** — dependencies could not be installed |
| Native Windows clean-install workflow | **Not run here** — must be triggered on the GitHub-hosted Windows runner or run locally on Windows |

The backend suite was run directly and passed 515 tests. The release-verification script was also run for its non-frontend, non-test, non-boot static gates; those 5 gates passed. A full release-verifier/Windows green status is not claimed.

## 6. Version and promotion

`backend/hsptl_core/config.py` and `frontend/package.json` remain at internal version `5.2.0`. Do not describe this preview as a completed 6.0.0 release. Promote only after the full frontend production build and native Windows clean-install workflow have both completed successfully.
