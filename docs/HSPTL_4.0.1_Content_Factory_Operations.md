# HSPTL Content Factory — Sustainable Authoring and Release Workflow

## Purpose

The content factory is an embedded, deterministic composition module. It produces reusable learning drafts from versioned JSON content packs. It does not use an AI model, external inference endpoint, vector database, or background generation service.

The learner library reads authored packs directly. This means the application has usable starter content immediately after installation; content generation is a separate editorial workflow that creates reviewable derivatives.

## Current starter content

`backend/content_packs/acute_care_foundations_v1.json` provides eight synthetic acute-care learning units, 24 retrieval questions, 16 viva prompts, eight OSCE station outlines, teaching points, common pitfalls, debrief prompts and versioned source references. The units are educational drafts and require clinical educator review before distribution or use in summative assessment.

## Pack discovery

The factory discovers `*_v*.json` files from `backend/content_packs/` at application startup. Each pack must have:

- A unique `pack_id` and explicit `version`.
- A title, description, intended use and generation policy.
- A source registry with title, publisher and HTTPS URL for each external reference.
- Unique unit IDs across all installed packs.
- At least two learning objectives per unit.
- At least three MCQs per unit, each with unique options, a valid answer index and a meaningful rationale.
- A structured synthetic case, teaching points and pitfalls.
- Viva prompts and an OSCE station with a checklist and critical errors.
- Source IDs that resolve within the pack, or an explicit authored-framework status.

A new pack is data, not a new application module. The factory aggregates its units into the existing library and allows the same six output composers to build from it.

## Six deterministic outputs

For each unit, the factory can compose:

1. `case_report`
2. `case_debrief`
3. `question_set`
4. `topic_summary`
5. `viva_set`
6. `osce_station`

The only seeded variation currently permitted is MCQ option ordering. Clinical statements, case observations and answer meaning are not mutated. The answer key is retained by answer text rather than by the original option index.

## Standard production workflow

1. A qualified author creates or updates a pack using `docs/templates/clinical_learning_content_unit.template.json` and the pack schema.
2. Run `python scripts/validate_content_packs.py` before committing the pack.
3. Increment the pack version when authored content changes. Do not silently replace a published version.
4. Open **Content factory** in HSPTL and select units and output types. A full six-output batch for the eight-unit starter pack requests 48 drafts.
5. The generator validates output structure, records pack/version/template/seed metadata and persists drafts in the existing generated-artifact store.
6. Content hashes deduplicate identical output; a changed pack version or content produces a new content hash and a new reviewable draft.
7. A qualified reviewer inspects and approves, requests revision or rejects each artifact using the existing review lifecycle.
8. Only approved artifacts can be routed into the existing workspace content destinations.
9. Retain review decisions and source lineage. Re-review changed content rather than silently updating existing approved artifacts.

There is no automatic clinical approval or unattended auto-publishing. Batch composition is automated; clinical release remains governed by a human reviewer.

## Validation command

```bash
python scripts/validate_content_packs.py
```

The validator first checks every pack against `backend/content_packs/content_pack.schema.json`, then loads every installed versioned pack, builds every supported output for every unit, verifies deterministic output hashes, and checks that MCQ answer text remains present after seeded option variation. `jsonschema` is a development/authoring dependency, not a runtime service.

## API

- `GET /api/content-factory/catalog`
- `GET /api/content-factory/units/{unit_id}`
- `GET /api/content-factory/status`
- `POST /api/content-factory/generate`
- `POST /api/content-factory/batch`

Batch generation accepts 1–12 units and 1–6 output types. Every response explicitly reports `auto_approved: false`.

## Governance boundary

The source URLs are references to current external guidance, not copied guideline text. Each pack's clinical content is HSPTL-authored and must be reviewed against the current jurisdiction, local pathway and intended learner level. A content approval is an editorial governance event; it is not proof that a clinical statement is correct or that an assessment instrument is validated.
