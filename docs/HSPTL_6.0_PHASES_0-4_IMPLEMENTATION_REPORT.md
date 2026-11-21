# HSPTL 6.0 — Phases 0–4 implementation report

**Baseline:** HSPTL 5.2.0 Automated Content & Navigation package  
**Build status:** 6.0 development branch; not a final 6.0 release.

## Phase 0 — Audit and stabilization

- Audited the supplied 5.2.0 package (343 files after extraction).
- Confirmed the existing seven-engine architecture: Kernel, Reasoner, Logic, Composer, Router, Guards and Explain.
- Confirmed the existing governed content lifecycle, versioned content packs, source registry, local folder ingestion, synthetic data factory, startup content preparation and shared daily lottery.
- Baseline backend suite: 475 tests passed before modifications.
- Preserved the 5.2.0 release identity while the 6.0 work remains incomplete.

## Phase 1 — Unified content architecture

- Added `backend/hsptl_core/unified_content.py` as the shared orchestration boundary for deterministic content pack generation and governed artifact persistence.
- Startup preparation and the learner-facing Update content action now call the same idempotent pipeline.
- Existing Composer and the other six engines remain in place; this is an orchestration consolidation, not an engine replacement.
- Generated content remains draft-only and requires human review; no automatic approval or publication was introduced.

## Phase 2 — Hospital navigation and icon update

- Reduced the primary navigation to seven clinical destinations: Clinic, Lab, Ward, Library, Learning, Exam Hall and Rounds.
- Home is excluded from the navigation and remains accessible through the HSPTL logo.
- Archive and My Profile are workspace-header actions.
- My Profile now contains Profile and Progress tabs.
- Added dedicated graduation-cap, clipboard-list, bed-double and siren icon primitives; navigation uses recognizable clinical icons.
- Secondary/admin functions remain discoverable through All modules.

## Phase 3 — Automatic Content Factory

- Retained startup preparation in FastAPI lifespan; it safely creates/reuses installed-pack drafts at application startup.
- The explicit Update content action reuses the same unified pipeline.
- Content generation is deterministic and model/API-key independent for installed packs.
- Added a local background external-source scheduler with idempotent startup provisioning of four keyless public-provider profiles: Europe PMC, PubMed, ClinicalTrials.gov and Crossref.
- Built-in profiles run bounded daily metadata/abstract searches, use rolling date windows, retry with backoff and persist connector runs/checkpoints. A local startup refresh and one-click refresh request can queue an immediate sync; no external cron/periodic trigger is required.
- Added `/api/ucks/automation/status` and `/api/ucks/automation/refresh`, plus an External Sources panel in Content Operations showing provider, interval, scheduler state, last run and governance state.
- The global Update content action now refreshes installed local content and queues external metadata sync in the same user action.
- Provider records are retained as harvested with document/source provenance. Full-text retrieval is off by default; public availability does not grant reuse/adaptation rights. Admin pause/disable choices are preserved. No automatic clinical approval, rights approval, adaptation or publication is performed.
- This automates source discovery and ingestion; it does **not** automatically turn unreviewed external records into clinical learning artefacts. That remains deliberately blocked pending explicit clinical review and rights clearance.

## Phase 4 — Clinical case quality and daily lottery

- Replaced date-and-case-ID hash ordering with `secrets.choice` over the eligible pool.
- The selected draw is persisted and remains shared across Clinic and Ward Board; refreshes do not redraw it.
- Eligibility still requires the existing publication, clinical-review and rights checks; no unreviewed fallback is allowed.
- Added additive SQLite fields for presenting complaint and patient age value/unit; existing records and draws are preserved.
- Exposed complaint and age in the learner-facing case presentation while the answer remains server-side withheld until reveal.
- Added age-range/unit validation and regression tests.

## Verification

- Backend regression suite: **486 passed** (including external-source profile provisioning, rolling provider query windows, mocked connector sync and harvested-status governance tests).
- Python backend compile check: passed.
- Versioned content-pack validation: passed (1 pack, 8 units, 24 retrieval questions, 48 deterministic output recipes).
- Frontend production build and typecheck remain **unverified**. `npm ci` could not complete because the environment could not resolve `registry.npmjs.org` and the dependency tarballs were not cached (`ENOTCACHED` on offline retry). The installed global TypeScript compiler parsed all 36 `.ts`/`.tsx` files with zero syntax diagnostics, but this is not a substitute for `tsc --noEmit` with React declarations or a Vite production bundle.
- The release verifier also timed out when it reached the frontend typecheck stage. No successful `vite build` is claimed.
- Windows CMD installer execution is not verified in this environment.
- Phases 5–8 (Clinical Events and redesigned dated archive, specialty-themed Rounds, full learner gamification, sharing/deployment and final release hardening) are not included in this build.
