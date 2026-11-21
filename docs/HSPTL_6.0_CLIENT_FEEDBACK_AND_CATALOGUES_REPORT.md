# HSPTL 6.0 Development Preview — Learner Post-use Review & Expanded Clinical Catalogues

## Delivered in this preview

### 1. Learner review of published learning artefacts

The Learning Library now lists only learning artefacts that satisfy both publication requirements:

- the artefact has an approved clinical/editorial review status; and
- at least one workspace distribution route has been delivered.

A learner workflow is available on each published artefact:

1. **Open & use artefact** creates a local usage session.
2. The published content and its linked source references are shown.
3. The learner explicitly marks the activity complete.
4. Only then is the post-use review form enabled.
5. The learner can rate usefulness, select a quality category, identify linked source records, and provide a comment.

Feedback categories include possible factual error, outdated information, missing context, unclear explanation, citation/source problem, accessibility/format, technical problem and other. Source selection is restricted to source records already linked to the artefact. The form warns users not to include patient-identifiable information.

Duplicate feedback for the same usage session is rejected. A session cannot be reviewed before completion. Feedback does not itself alter clinical approval, publication status, source lifecycle or source-rights permission.

### 2. Educator review queue

Content Operations includes a reviewer-only queue. It supports four triage outcomes:

- Acknowledged
- Source review required
- Artefact revision required
- Closed

Each resolution requires an audit note and is recorded in a separate audit table. Triage deliberately does not perform the underlying source or artefact change; an authorised educator must use the existing source-rights and content-review workflows to make that change.

The queue uses the existing HSPTL reviewer credential convention:

- `HSPTL_REVIEWER_TOKEN` — at least 32 characters
- `HSPTL_REVIEWER_ID` — named reviewer identity

Example PowerShell setup for a local Windows user (run once, then restart HSPTL):

```powershell
$token = python -c "import secrets; print(secrets.token_hex(32))"
[Environment]::SetEnvironmentVariable("HSPTL_REVIEWER_TOKEN", $token, "User")
[Environment]::SetEnvironmentVariable("HSPTL_REVIEWER_ID", "clinical-educator", "User")
```

The token is entered into the reviewer queue UI and sent in the `X-HSPTL-Reviewer-Token` request header. It is not stored in browser local storage.

### 3. Expanded specialty directory

The specialty directory now contains **44 specialty/service entries**, each with:

- service description and focus areas;
- common clinical presentations;
- learning themes and discovery topics;
- installed curated-pack counts separated from discovery-theme counts.

The search matches specialty names, descriptions, focus areas, common presentations and learning themes. Existing curated question packs are retained and mapped into their relevant specialties; the expanded discovery topics are labelled as themes rather than being misrepresented as completed question packs.

### 4. Clinical events catalogue

The Clinic workspace now includes **30 clinical-event scenario themes**. Each theme includes its category, icon, teaching summary, likely setting, learning objectives, case-discovery signals and suitable workspaces.

The catalogue is a teaching-scenario taxonomy only. It is not a live hospital alert feed, an operational response protocol, or patient-specific clinical advice. A theme does not manufacture or publish a case: case material still needs source provenance, rights clearance and clinical review.

### 5. Source directory

The Content Operations source directory now contains **57 source entries across 27 source families** (the exact family count is shown in the UI). Each entry is enriched with content value, coverage tags, access/reuse/adaptation defaults, an integration route where known, a note and a link-out URL where available.

The directory spans:

- national and international guidelines and specialist societies;
- bibliographic and open-access literature discovery;
- clinical trial registries;
- public-health agencies and surveillance sources;
- clinical datasets and health indicators;
- terminology, coding and medicines reference systems;
- imaging, patient-education and clinical reference libraries.

The four existing scheduled metadata connectors remain Europe PMC, PubMed, ClinicalTrials.gov and Crossref. Other directory entries are explicitly marked as link-out, licensed access, manual/institutional import, API/download, or item-level licence review. Directory inclusion never implies an available connector or permission to copy/adapt a source. Defaults remain conservative and the exact source version, licence, jurisdiction and third-party content must be checked.

## Technical changes

- Added `backend/routers/published_learning.py` for published-item listing, usage/completion sessions, feedback submission, reviewer triage and audit history.
- Added additive SQLite migration for learner usage completion timestamps.
- Added `/api/clinical-catalogue/events` and `/api/clinical-catalogue/summary`.
- Expanded `/api/specialties` and `/api/specialties/{slug}` with specialty focus, presentation and theme metadata.
- Added learner panel to the Learning Library, scenario catalogue to Clinic, and searchable source/feedback operations views to Content Operations.
- Allowed the reviewer token header in the local development CORS configuration.
- Added automated tests for publication gating, completion-before-feedback, linked-source restriction, duplicate prevention, reviewer authentication, no automatic governance mutation and catalogue integrity.

## Verification

- Backend regression: **493 tests passed** (final result after the new publication-gate test).
- Python compile check: passed.
- Startup preflight and database migrations: passed.
- Content-pack validation: passed (1 pack, 8 units, 24 questions, 48 deterministic output recipes).
- Frontend TypeScript/TSX syntax transpilation: 38 source files, zero syntax diagnostics.
- Frontend dependency installation and full production build: **not verified**. `npm ci` timed out because `registry.npmjs.org` failed DNS resolution (`EAI_AGAIN`); the repository has no complete local `node_modules` cache. Syntax transpilation does not replace `tsc --noEmit` or the Vite production build.

## Release status and limits

This is a **6.0 development preview**, not a final 6.0 release. The internal application/package version remains 5.2.0 until the complete release gate, including a successful frontend typecheck and production build, can be run. The reviewer queue also requires local reviewer environment credentials to be configured before it can be used.

The catalogue makes discovery richer; it does not imply that every listed source is automatically ingested. Only the managed metadata connectors are scheduled automatically. Rights-sensitive documents and all clinical learning artefacts remain subject to their existing review and publication gates.
