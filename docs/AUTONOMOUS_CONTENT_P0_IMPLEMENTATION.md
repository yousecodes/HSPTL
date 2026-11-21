# Autonomous Content P0 Implementation

## Scope

This change implements the first two P0 objectives:

1. Remove mandatory human pre-approval as a prerequisite for provisional educational publication.
2. Connect successful managed-source acquisition to source-derived educational generation and workspace distribution.

## Publication lifecycle

- Structurally validated content-pack outputs and source-derived outputs are stored with status `provisional`.
- Eligible outputs are routed automatically to the matching workspace.
- The workspace index marks them `unreviewed`; it does not falsely label them `approved`.
- Learners may access provisional material for supervised educational use.
- The optional reviewer workflow remains available after publication. Reviewers may approve, reject or request revision.
- `clinical_validation` remains `not_assessed` until evidence-based post-use validation is completed. Provisional publication is not clinical endorsement.

## Acquisition-to-generation flow

After a successful managed connector cycle, the automation service:

1. Finds current `machine_screened` documents from successful managed sources.
2. Maps supported document types to an educational output and workspace.
3. Checks whether the current source version already has a derived artefact.
4. Invokes deterministic, source-extractive generation.
5. Enforces the existing explicit reuse allow-list or a recorded rights decision before reusing full text.
6. Automatically routes eligible generated artefacts to the workspace index.
7. Records skipped records and reasons in the automation result.

A revised source version produces a new derived artefact version; unchanged versions are not regenerated on every scheduler cycle.

## Rights and safety boundaries

- Importing a record does not grant rights to reproduce or adapt its full text.
- Unknown, restrictive or unsupported reuse permissions cause generation to be skipped; the source record remains imported and searchable as permitted metadata.
- The deterministic extractor does not perform clinical synthesis or independently establish evidence certainty.
- Automated integrity and citation checks are not clinical validation.
- Clinical retractions, corrections and downstream invalidation remain future work beyond these two P0 items.

## Verification

- Targeted generation, content factory, unified pipeline, connector and autonomous-pipeline tests: 37 passed before the final revision-version test was added.
- Final full backend suite: **524 passed**.
- Python compile check: passed.
- Content pack/schema policy consistency check: passed.
- Frontend source was not changed; no new frontend build was required by this backend-only change.
- Native Windows CI was not run from this environment. Run the repository's existing Windows GitHub Actions workflow against the resulting commit before merging or distributing this package.

## Changed areas

- `backend/hsptl_core/generation_distribution.py`
- `backend/hsptl_core/workspace_distribution.py`
- `backend/hsptl_core/external_source_automation.py`
- `backend/hsptl_core/unified_content.py`
- `backend/hsptl_core/content_factory.py`
- `backend/routers/content_factory.py`
- `backend/routers/generation_distribution.py`
- `backend/content_packs/acute_care_foundations_v1.json`
- `backend/content_packs/content_pack.schema.json`
- Relevant backend tests, including new autonomous-pipeline tests

## Important release note

This is an implementation preview based on the audited HSPTL 6.0.0 source archive. It has not been pushed to GitHub or merged into `main`. The connected GitHub integration denied branch creation with HTTP 403. Review and run Windows CI on the user's local repository before treating it as a release.
