# HSPTL 4.0.1 — Release status

## Delivered

- Replaced the previous hospital-service navigation shell with a responsive learner-first application shell.
- Added Overview dashboard, Learning Library and Content Factory pages.
- Bundled Acute Care Foundations v1: 8 synthetic units, 24 MCQs, 16 viva prompts and 8 OSCE station outlines.
- Added six deterministic content derivatives per unit and batch generation (maximum 72 outputs/request).
- Added multi-pack discovery for versioned JSON packs, JSON Schema, authoring template and content-pack validation script.
- Reused the existing artifact audit, reviewer approval and workspace distribution lifecycle.
- Kept existing Clinic, Rounds, Lab, Ward, Exam Hall, Portfolio and legacy feature routes accessible.

## Verification

- Backend regression tests: run from the delivered package; see release verification output.
- Content pack schema and recipe validation: `python scripts/validate_content_packs.py`.
- Frontend TS/TSX syntax transpilation: all source files checked; no syntax diagnostics.
- Full frontend typecheck and Vite build: not verified in the current build environment because the pinned React/Vite packages are not installed and the environment has no available npm dependency cache.

## Safety and governance

- The starter units are HSPTL-authored educational material with synthetic cases and reference links. They are not clinical protocols or patient-care recommendations.
- Educator review is required before distribution; OSCE checklists require calibration before summative use.
- Batch generation creates drafts only. It cannot approve or publish content automatically.
- The in-page Learning Library quiz is formative and currently does not persist attempts as learner assessment records.
