# HSPTL 5.2.0 — Release status

**Application version:** 5.2.0  
**Release focus:** simplified navigation, automatic local learning-draft preparation, cross-workspace content refresh and reference-derived brand assets.

## Included

- Seven primary learner destinations: Home, Learn, Practice, Simulate, Skills, Exams and Progress.
- Existing destinations remain routable through the Essentials / All modules directory. No module data or route was deleted in this release.
- Startup prepares deterministic draft content from installed versioned learning packs.
- A global **Update content** action is available in every workspace through the shared application shell.
- Nine generated draft types are prepared for six learning destinations: Clinic, Exam Hall, Rounds, Lab, Ward and Simulation.
- New output types: on-call scenario, handover template (SBAR) and simulation brief.
- Refresh is idempotent. Unchanged outputs are reused; changed pack versions produce new drafts.
- Existing reviewed and approved material is not automatically replaced. Generated outputs remain drafts until the review and distribution workflow is completed.
- Logo variants are supplied as scalable SVGs, including color and monochrome variants.

## Content safety and operational behavior

Automatic preparation uses local deterministic templates and installed pack data. It is not generative medical reasoning, a source-verification service or clinical approval. Each generated artifact carries educational limitations and must pass appropriate educator review before publication. Startup failures are logged but do not prevent the rest of HSPTL from starting; the user can retry via **Update content**.

The current refresh scans installed packs and prepares a bounded maximum of 250 units. It does not fetch external content and does not require an API key.

## Verification

- Backend tests: see the release verification report generated with this package.
- Archive manifest: SHA-256 for each included file, excluding the manifest itself.
- Frontend build: must be run on Windows after `npm ci` / installer dependency setup if this release was packaged in an environment without frontend dependencies.

## Important limitations

The simplified navigation changes visibility and grouping, not the underlying route architecture. Modules proposed for eventual consolidation are retained in All modules until their functions have been deliberately migrated and regression-tested. The content factory creates educational drafts; a qualified reviewer remains responsible for clinical accuracy, suitability and publication.
