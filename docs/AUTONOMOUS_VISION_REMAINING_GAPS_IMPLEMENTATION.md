# HSPTL Autonomous Vision — Remaining Gaps Implementation

## Implemented in this update

### Provider pagination and historical discovery

- `sync_connector` now accepts a bounded `max_pages_per_run` budget (1–100); the normal scheduled managed-source path uses 10 pages per run.
- Provider cursors are resumed across scheduler runs and repeated/non-advancing cursors fail safely instead of looping forever.
- Checkpoints record pages completed in each run and cumulative pages, record counts, cursor and completion state.
- Built-in Europe PMC, PubMed and Crossref profiles now use stable non-date-limited query templates, allowing historical backfill to progress rather than changing the query hash every day.
- Manual connector calls retain the one-page default for predictable interactive behaviour.

### Explicit publisher retraction metadata

- Europe PMC and PubMed normalizers retain publication-type metadata.
- An explicit `Retracted Publication` designation from those providers sets the source document lifecycle to `retracted` automatically.
- Existing downstream reconciliation then quarantines/withdraws learning artefacts that cite the retracted source.
- The automation deliberately does not infer retraction from trial status, article age, generic corrections or ambiguous publisher signals.

### Status transparency

- UCKS status limitations now describe the paged backfill behavior and distinguish explicit auto-detected retractions from other publisher signals that still require confirmation.

## Verification

- Focused connector, UCKS and lottery suite: **169 passed**.
- Full backend suite: **530 passed in 84.66 seconds**.
- Python compile check: `python -m compileall -q backend tests` passed.

## Still not complete (not hidden by this update)

1. Provider updated-date watermarks and stable-snapshot reconciliation are not implemented. Paged searches are not guaranteed to represent a consistent remote snapshot while records are changing, and provider result-window limits may apply.
2. Only explicit PubMed/Europe PMC retraction publication types are automatically acted on. Other publisher corrections, notices, Crossref relation signals and ClinicalTrials registry lifecycle changes remain proposals/metadata and are not auto-promoted to authoritative retractions.
3. Continuous synthetic-case authoring into the daily lottery is not implemented. HSPTL still protects the lottery from automatically promoting arbitrary generated/harvested records into patient-like teaching cases. It continues to use its authored curated curriculum and eligible reviewed cases.
4. Advanced clinical synthesis by a local no-key reasoning model is not implemented. Source-derived generation remains deterministic/extractive and citation-checked; it does not independently synthesize recommendations or grade evidence certainty.
5. Frontend production build could not be verified here. `npm ci --no-audit --no-fund` timed out; the partially populated `node_modules` then caused `npm run build` to fail because TypeScript could not find the Node, React and React DOM type definitions. This is an environment/dependency-install failure, not a successful build.
6. Native Windows clean-install and GitHub Actions release workflows have not been run from the user's Windows machine. They remain mandatory before release.

## Release state

This is an implementation package based on the previously supplied HSPTL autonomous-vision working tree. It has not been pushed to GitHub or merged into `main`. The package is not a certified production release. Apply it to a backup of the local repository, run dependency installation and the Windows clean-install workflow, then commit and push only after those checks pass.
