# HSPTL Phase 2-4 delivery notes

## What was added
- Phase 2: `migrations`, `source_refs`, `episodes`, `exams` (versioned question bank,
  immutable attempt snapshots), `scheduling` (SimpleScheduler + unvalidated FSRS preview),
  process-level feedback (`reasoning_feedback.build_feedback`).
- Phase 3: `search` (faceted FTS5 + LIKE fallback), `jobs` (lease/heartbeat/backoff/cancel),
  `source_cache`, `content_review`, `progress` (four non-aggregated dimensions).
- Phase 4: `policy` (feature gates), `advanced` (curated branching, offline export bundle,
  prompt-only tutor), `runtime` singletons, `routers/` package.
- Frontend build blockers fixed: SpecialtiesPage `useState`, Icon names
  (`image`/`microscope`/`filePlus`/`osce`), `api.ts` exam/OSCE/episode types + methods,
  hardcoded FHIR path removed.
- `tests/test_learning_hub.py` quarantined to `tests/_quarantine/` (targeted a removed API).

## Feature gates (Phase 4)
All advanced capabilities are **off by default**. `formal_assessment` is hard-blocked and
cannot be enabled by any flag. Enable others with `HSPTL_FEATURES=<key>=1`, but note:
- `branching_simulation` also requires the submitted graph to declare a reviewer, review
  date, and `source_type: "curated_case"`.
- `conversational_tutoring` is never auto-satisfied; `/api/tutor/prompt` returns 403 until
  its requirements are explicitly met. Prompt export already exists via `/api/pearls/generate`.

## Ordering dependency
`progress.py` calls `store.review_analytics()`, added by the `store.py` edit. Apply the whole
patch in one pass (the engine preflights everything) rather than partial chunks.

## Not executed
These payloads were hand-checked against `extracted_code.txt`, not run. After applying, run
the verification steps below before trusting the result.
