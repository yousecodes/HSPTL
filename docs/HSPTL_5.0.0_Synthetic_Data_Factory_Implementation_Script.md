# HSPTL 5.0.0 — Automated Synthetic Data Factory
## Repository Implementation Directive for a Coding Agent

**Target release:** HSPTL 5.0.0  
**Baseline:** HSPTL 4.0.2 repository  
**Execution model:** Local-first, model-free, deterministic where supported, single-process modular monolith  
**Primary generator:** Synthea  
**Primary exchange format:** HL7 FHIR R4 (4.0.1)  
**Additional export:** CSV; C-CDA optional  
**Target operating system:** Windows 10/11, with the existing Python/FastAPI and React/Vite stack  
**Reference hardware:** 8 GB RAM; default to one generation job at a time

---

# COPY THE IMPLEMENTATION DIRECTIVE BELOW INTO YOUR CODING AGENT

## 0. Role and objective

Act as a senior software architect, Python/FastAPI engineer, React/TypeScript engineer, clinical data interoperability engineer, test engineer, and release engineer.

Your task is to **implement**, not merely plan, the HSPTL 5.0.0 Automated Synthetic Data Factory in the existing HSPTL repository.

The finished feature must let a local HSPTL user configure or select an approved generation recipe, press **Generate**, and have the application automatically:

1. Validate local prerequisites and the selected recipe.
2. Launch a pinned, locally installed Synthea distribution with a reproducible seed and isolated output directory.
3. Generate FHIR R4 and optional CSV exports.
4. Validate FHIR structure and profile conformance using a pinned HL7 FHIR Validator when configured.
5. Check references, patient/resource identity, chronology, terminology coverage, data completeness, and conservative clinical plausibility rules.
6. Apply only approved, semantics-preserving technical normalizations.
7. Quarantine failures and unresolved cases with actionable diagnostic reports.
8. Register accepted datasets with complete provenance and immutable source exports.
9. Import eligible accepted records into HSPTL's existing dataset/case capabilities without duplicate records.
10. Publish a dataset catalogue entry, batch report, and audit metadata.
11. Support cancellation, progress, retry, restart recovery, scheduling, and storage management.

A routine run using an already approved recipe must finish unattended. No AI model, cloud API, API key, external database server, or additional microservice is required.

**Clinical safety boundary:** Technical validation and import into the synthetic fixture registry may be automated. Do not represent generated records as clinically validated teaching scenarios, treatment guidance, clinical evidence, or competency assessments. New clinical modules, novel plausibility rules, or conversion of patient records into learner-facing scenarios require a separate qualified review and explicit publication workflow. Existing reviewed recipes may run unattended under their locked versions.

## 1. Inspect the repository before changing it

Start by inspecting the actual checked-out repository. Do not assume the code has the same state as an earlier archive. Produce a short internal implementation map, then proceed directly to implementation.

The known 4.0.2 baseline includes:

- Python FastAPI backend and React 19 / TypeScript / Vite frontend.
- Local SQLite storage under the HSPTL user-data directory, configurable through `HSPTL_HOME`.
- `backend/runtime.py` singleton wiring for stores and `JobRunner`.
- `backend/hsptl_core/jobs.py` durable-job runner with lease, heartbeat, retry, and cancellation intent.
- `backend/hsptl_core/store.py` SQLite schema and background job storage.
- `backend/hsptl_core/case_engine.py` FHIR JSON/Bundle/NDJSON parsing and `CaseRepository.import_directory(...)`.
- `backend/hsptl_core/config.py` user-data paths and settings.
- `backend/hsptl_core/hsp_tl40/kernel.py`, `event_contracts.py`, and `docs/hsptl40/event_catalogue.json` for the canonical append-only event log and event contracts.
- Existing FastAPI routers under `backend/routers/` and React pages/components under `frontend/src/`.
- Existing release verification and packaging scripts under `scripts/`.

Inspect at minimum:

- `backend/runtime.py`
- `backend/hsptl_core/jobs.py`
- `backend/hsptl_core/store.py`
- `backend/hsptl_core/config.py`
- `backend/hsptl_core/case_engine.py`
- `backend/hsptl_core/hsp_tl40/kernel.py`
- `backend/hsptl_core/hsp_tl40/event_contracts.py`
- `backend/main.py`
- `backend/routers/`
- `frontend/src/App.tsx`
- `frontend/src/pages/`
- `frontend/src/components/`
- `requirements.txt`, `requirements-dev.txt`, `frontend/package.json`
- `scripts/verify_release.py`, packaging scripts, current docs and tests.

### Mandatory baseline audit: background job schema

Before relying on `JobRunner`, compare the current `background_jobs` table with every column referenced by `JobRunner.claim`, `heartbeat`, `complete`, `fail`, `request_cancel`, and `reap_expired`.

The 4.0.2 baseline may have a mismatch: the job runner references lease, cancellation, retry, heartbeat, and result fields that may not yet exist in the original SQLite table definition. Add a **non-destructive, additive schema migration** for every missing field and index. Do not drop, recreate, or truncate existing learner tables or job rows. Make the migration idempotent and versioned. Add regression tests proving an existing 4.0.2 database upgrades without losing learner data or queued jobs.

Do not assume the job worker is currently started automatically. Trace the actual startup lifecycle and implement an explicit, safe worker lifecycle for the Synthetic Data Factory. The local installer/runtime must enable the worker for normal factory operation, with a documented opt-out. A queued factory job must never remain silently unprocessed.

## 2. Non-negotiable architectural constraints

1. Keep HSPTL a **single modular monolith**. Add internal modules, repositories, routers, React pages, and local worker logic; do not add microservices or a separate database service.
2. Use the existing SQLite store and migrations. Use file-backed storage for large FHIR/CSV artifacts; do not put whole FHIR bundles into SQLite rows or event payloads.
3. Use the existing `JobRunner` / `background_jobs` infrastructure after repairing it safely. Do not invent a second parallel job framework.
4. Use the existing `Kernel` and canonical event log for audit metadata. Do not create a second event log. Events must contain metadata, hashes, counts, state changes, and references—not full patient resource payloads.
5. Keep raw Synthea exports immutable. Any normalized or transformed projection must be a separate derived artifact with transformation lineage.
6. The pipeline must be deterministic/reproducible when the same Synthea build, configuration, modules, seed, and input artifacts are used. Record all of these inputs.
7. Use local, deterministic, model-free validation and mapping. Do not call generative AI, hosted AI, or any API requiring a key.
8. Do not silently fabricate, fill, infer, or alter clinical facts, observations, diagnoses, medication instructions, units, or dates to improve a quality score.
9. Treat abnormal values as potentially intentional clinical content. An abnormal value is not automatically an error.
10. Fail closed for missing prerequisites, unpinned generator versions, invalid manifests, broken patient references, corrupted bundles, and mandatory validation failures. Quarantine uncertain records rather than silently accepting them.
11. Default to one Synthea process at a time and bounded validation/import batches for an 8 GB RAM computer.
12. Bind the local app to loopback by default. Do not expose factory controls to a LAN or public network without a future authenticated deployment architecture.
13. Preserve all existing HSPTL 4.0.2 features and data. Do not replace or simplify the existing clinical simulation, learning, assessment, replay, content factory, curriculum, or scenario authoring capabilities.
14. Do not claim clinical safety validation, institutional readiness, real-world prevalence representativeness, or psychometric validity from synthetic data alone.

## 3. Synthea runtime management

### 3.1 Local installation and version pinning

Implement a setup/settings area for the user to configure:

- Path to the local Synthea executable JAR or distribution directory.
- Exact Synthea release/version or commit identifier.
- SHA-256 checksum of the executable artifact.
- Java executable path or detected Java runtime.
- Java runtime version.
- Optional custom Synthea module directory.
- Optional Synthea config file path.
- Optional pinned HL7 FHIR Validator JAR path and checksum.
- Local cache location for FHIR packages/terminology artifacts.

Do not silently download an unpinned `master` build or latest JAR during a background job. Runtime downloads are disabled. If the user elects to install/update Synthea or the HL7 validator, use an explicit setup action, show the official source, record the version and checksum, and verify the artifact before enabling it.

Use official project references:

- Synthea repository and CLI: https://github.com/synthetichealth/synthea
- Synthea common configuration: https://github.com/synthetichealth/synthea/wiki/Common-Configuration
- Synthea Generic Module Framework: https://github.com/synthetichealth/synthea/wiki/Generic-Module-Framework
- Synthea Module Builder: https://synthetichealth.github.io/module-builder/
- HL7 FHIR Validator: https://hl7.org/fhir/validator/

### 3.2 Preflight check

Before accepting a job, validate:

- Synthea artifact exists, is readable, has a recorded checksum and matches the configured checksum.
- Java exists and meets the pinned Synthea distribution's supported runtime requirement.
- The configured module directory and config file exist and are readable.
- The requested output path is under HSPTL-managed storage; reject arbitrary paths and traversal.
- There is sufficient free disk space according to a configurable conservative threshold.
- The requested population and output options are within configured limits.
- The configured FHIR validator is available when strict FHIR conformance is required.
- No other population generation job is running.

Return precise actionable messages. Do not start a partial job if preflight fails.

### 3.3 Process invocation and safety

- Invoke Java with `subprocess.Popen([...])` using an argument list; never concatenate user input into a shell command and never use `shell=True`.
- Record the exact sanitized argument vector and effective configuration hash in the run manifest.
- Capture stdout and stderr to per-job log files with bounded log size and log rotation.
- Do not expose arbitrary shell commands or arbitrary executable paths through public API payloads.
- Support cooperative cancellation and terminate the child process safely; on Windows, handle process termination and descendants reliably.
- Set a configurable timeout and resource bounds.
- Default Java heap to approximately 1.5–2 GB for an 8 GB PC, configurable by the user; do not over-allocate memory.
- Run one Synthea generation process at a time. Validation and import should also use bounded batches and avoid loading an entire cohort into RAM.
- Store every job's outputs in a unique staging directory. Never point Synthea at a shared output directory.

### 3.4 Supported generation options

Use only options supported by the configured pinned Synthea version. Support, as appropriate:

- Population size (`-p`).
- Fixed seed (`-s`).
- Age range (`-a`).
- Gender filter (`-g`).
- Geography arguments only for locations present in that Synthea build's demographic data.
- Local configuration file (`-c`).
- Custom modules directory (`-d`).
- Explicit exporter settings, such as FHIR export, CSV export, and base output directory.
- Configurable years of history.

For FHIR R4, record and verify the actual version. Do not silently assume that an exporter's default profile configuration is suitable for every jurisdiction. Make US Core profiles explicitly selectable; the generic HSPTL base recipe should not claim US Core conformance unless the dataset is configured and validated against the corresponding US Core release.

Default history retention should be explicit and configurable. Do not force full lifetime history (`exporter.years_of_history=0`) by default because it can greatly increase export size. Record the actual setting in the manifest.

### 3.5 Cohort targeting honesty

Synthea population generation is probabilistic. A requested patient count is not the same as a guarantee that the same number of patients will have a target diagnosis.

Implement cohort selectors over generated FHIR resources using a versioned, explicit set of clinical codes and code systems. For disease-targeted cohorts:

- Support a target accepted count and configurable maximum over-generation multiplier.
- Generate bounded batches with deterministic derived seeds.
- Select matching patient bundles using coded criteria.
- Preserve the complete bundle for each selected patient.
- Stop at the configured limit.
- If the target count is not reached, report `partial_cohort`; do not invent conditions or modify records to fill the cohort.
- Record generated count, matched count, selected count, discarded count, and the exact cohort criteria version.

Do not claim that synthetic population distributions represent Egypt or any other country unless the demographics, epidemiology and validation evidence support that claim. A city or country string must never be used as a substitute for actual demographic calibration.

## 4. Generation recipes

Create versioned, declarative recipes stored locally. A recipe describes intent and constraints; it must not contain executable Python, JavaScript, shell, or other arbitrary code.

Each recipe must include:

- Stable recipe ID, version, title, description, owner, creation date, and status.
- Intended educational or technical use.
- Pinned Synthea version and module pack checksums.
- Population target and maximum population/over-generation limits.
- Demographic constraints.
- Geography, if supported by loaded Synthea demographics.
- Included module identifiers and module pack version.
- FHIR release, exporter options, CSV option, years of history, and optional profile/IG configuration.
- Cohort selection criteria and code systems.
- Required resource types and completeness rules for the recipe's purpose.
- Validation rule-pack IDs and versions.
- Terminology package/release identifiers and mapping set versions.
- Output size/resource limits.
- Provenance metadata.
- Review state and reviewer details for new clinical recipes.

Initial built-in recipe families:

1. General mixed population.
2. Asthma.
3. Diabetes.
4. Hypertension.
5. Pneumonia.
6. Heart failure.
7. Multimorbidity/polypharmacy.
8. FHIR/CSV integration test fixtures.

These are recipe placeholders until their module definitions and clinical mappings have been reviewed. Do not describe all built-in recipes as clinically approved merely because they ship with the application.

Recipe lifecycle: `draft -> technical_validated -> clinical_reviewed -> active -> retired`.

A new recipe can be generated in draft/test mode, but it cannot silently become an active clinically curated teaching recipe. Existing active, pinned recipes can run unattended.

## 5. Factory pipeline and state machine

Implement the following durable state machine. Persist state transitions and checkpoints so a restart can resume safely.

`queued -> preflight -> generating -> exporting -> inventorying -> fhir_validating -> reference_validating -> chronology_validating -> terminology_auditing -> plausibility_auditing -> completeness_scoring -> normalizing -> quarantine_partitioning -> importing -> registering -> completed`

Alternative terminal states:

- `failed`: non-recoverable or exhausted technical failure.
- `cancelled`: user cancellation.
- `partial_cohort`: generator completed but the target cohort count was not reached.
- `completed_with_quarantine`: accepted records registered and unresolved records quarantined.
- `blocked`: missing setup or mandatory validator/prerequisite.

A failed validation stage must not proceed to import. A warning-only clinical plausibility finding may proceed only if the active recipe explicitly allows that severity and the warning is retained. A hard validation failure is quarantined/rejected.

Every stage must:

- Have a stable stage identifier and version.
- Record start/end timestamp and duration.
- Record counts and artifact digests.
- Emit a progress update and resumable checkpoint.
- Be idempotent when retried.
- Never overwrite a previously accepted dataset.

## 6. FHIR validation and quality engine

Build a layered validation engine. Do not rely on a single percentage score.

### 6.1 Structural and official FHIR validation

- Parse JSON and NDJSON safely with file-size and line-size limits.
- Validate FHIR resource types and Bundle structure.
- Validate R4 using a pinned official HL7 FHIR Validator CLI when strict mode is enabled.
- Pin the validator JAR, FHIR version (`4.0.1` for R4), implementation guide/package dependencies, and checksums.
- Use a local package cache/offline mode after dependencies are installed. Do not download implementation guides in a background job without explicit setup approval.
- Preserve the validator's OperationOutcome or diagnostic output as a per-run report.
- Differentiate `FHIR structural validation` from `FHIR profile conformance`. Never display a green “FHIR compliant” label when only local shape checks ran.
- If the official validator is not configured, mark strict validation as blocked or limited according to the chosen system policy. Do not overstate conformance.

### 6.2 Referential integrity

Validate at minimum:

- Each generated Patient is uniquely identified in its dataset.
- Every clinical resource's `subject` or `patient` reference resolves to a Patient in the same patient bundle/dataset according to resource semantics.
- Encounter references resolve where expected.
- Bundle `fullUrl` references resolve and do not collide.
- Cross-resource links are internally consistent.
- Duplicate logical resources are detected with resource ID plus source provenance; do not incorrectly deduplicate identical clinical values with different legitimate dates.

### 6.3 Chronology and temporal checks

Check:

- Valid date/dateTime/instant/period types.
- Start is not after end.
- Encounter period is not negative.
- Recorded/onset/abatement relationships are plausible according to resource semantics.
- Medication authored/validity periods are coherent when present.
- Resource dates do not exceed the configured simulation/reference-date policy without an explicit exception.
- Patient birth date is not after an encounter or observation.

Do not use one simplistic universal chronology rule for all FHIR resources. Rules must be resource-specific, versioned and unit tested.

### 6.4 Terminology audit

- Preserve original code, system, display, and source resource.
- Validate known CodeSystem/ValueSet bindings when the relevant package is locally available.
- Maintain versioned, explicit mapping sets for SNOMED CT, LOINC, RxNorm and other supported systems.
- Never infer a mapping from display-text similarity alone and automatically replace the source code.
- Unmapped codes remain unmapped with a warning and stable mapping-review record.
- SNOMED CT and other licensed terminology content may only be imported from files the user is authorized to use. Do not download or redistribute licensed terminology.
- Store terminology edition, effective date, local package ID and file hashes.

### 6.5 Clinical plausibility audit

Implement conservative, transparent, deterministic rules. Each rule must have:

- Stable ID and version.
- Applicable resource/profile/recipe.
- Severity (`info`, `warning`, `quarantine`, `error`).
- Explicit condition and rationale.
- Scope and limitations.
- Unit tests and reviewed status.

Check only data quality and internal consistency. For clinical ranges, use reviewed age/sex/context-specific reference sets with units. If a required reference set is missing, abstain and create an informational finding instead of making an unsupported clinical claim.

Do not automatically alter clinical facts. No automated filling of absent observations, diagnoses, medicines, lab values, or procedure dates.

### 6.6 Educational completeness

Assess completeness relative to the recipe's intended purpose, not a universal checklist. For example, an asthma teaching cohort might specify the resource types and longitudinal features it expects. A record that does not meet the criteria may be quarantined for that recipe but could still be valid for a general-population dataset.

Keep technical validity, clinical plausibility, terminology coverage, and educational usefulness as distinct dimensions.

### 6.7 Quality report

Generate JSON and human-readable Markdown/HTML reports with:

- Counts of generated, selected, accepted, quarantined and rejected patients.
- Resource counts by type.
- Official FHIR validation status and diagnostics.
- Referential integrity findings.
- Chronology findings.
- Terminology coverage and unmapped code counts.
- Plausibility findings by rule/severity.
- Completeness by recipe objective.
- Normalizations performed (if any), with before/after hashes.
- Validator, rule-pack, terminology, Synthea, recipe and module versions.
- Explicit limitations and confidence scope.

Avoid a single overall score that hides hard failures. A summary may show separate dimension percentages but must explain denominators and exclusions.

## 7. Safe normalization, quarantine and acceptance

### 7.1 Normalization

Only deterministic and semantics-preserving operations are allowed automatically, such as:

- Canonical JSON serialization for derived copies.
- Consistent encoding and whitespace handling.
- Safe reference resolution in an import projection when the source semantics remain identical.
- Approved, one-to-one terminology URI normalization that preserves the original coding and records the mapping.

Never automatically change clinical meaning.

For each normalization, store source hash, output hash, transformation ID/version, timestamp, and reason. The source files remain immutable.

### 7.2 Quarantine

Quarantine at patient-bundle granularity when possible so resources from the same patient do not become fragmented. Preserve failure reports and explain which rule failed. Allow retry after a corrected validator/rule configuration, but do not mutate source exports.

The quarantine UI must support:

- Filtering by rule, resource type, patient pseudonymous key, severity and batch.
- Viewing a redacted/controlled resource excerpt and validation diagnostics.
- Exporting the finding report.
- Re-running validation under a newer rule pack without regenerating the patient.
- Marking a finding as reviewed with reviewer identity and rationale.

No quarantined bundle can enter active clinical learning fixtures unless it passes the relevant rules or is explicitly accepted under an audited, narrowly scoped exception. A reviewer cannot waive FHIR structural corruption or broken patient identity links.

### 7.3 Acceptance and import

- Auto-import records that pass all mandatory technical gates and the selected recipe's configured acceptance policy.
- Use the existing `CaseRepository.import_directory(...)` or a compatible adapter after inspecting its idempotency and transactional behaviour.
- Preserve source dataset ID, source file digest, Synthea patient ID, original resource IDs, and run provenance.
- Re-importing the same dataset is idempotent; it must not create duplicate clinical patients/facts.
- Keep raw exports, normalized projections, quality reports and registry metadata in separate locations.
- Distinguish `technically accepted synthetic fixture` from `clinically reviewed learning scenario` in all UI/API labels.

## 8. Storage layout and provenance

Extend `ensure_user_dirs()` additively with an HSPTL-managed storage root, for example:

```text
HSPTL_HOME/
  synthetic_data/
    runtime/
      synthea/
      fhir_validator/
      module_packs/
      terminology_cache/
    staging/
      <job-id>/
        source/
        fhir/
        csv/
        logs/
        validation/
        derived/
    datasets/
      <dataset-id>/
        source/             # immutable Synthea exports
        derived/            # normalized copies or projections
        manifests/
        reports/
    quarantine/
      <dataset-id>/
        bundles/
        findings/
    recipes/
      <recipe-id>/
        <version>/recipe.json
    schedules/
    temp/
```

Use path-safe IDs and resolve every path under the HSPTL-managed root. Reject path traversal, symlink escapes where applicable, and user-controlled absolute paths for job outputs.

Create additive SQLite tables/migrations for the factory domain, for example:

- `synthetic_recipes`
- `synthetic_dataset_runs`
- `synthetic_datasets`
- `synthetic_dataset_artifacts`
- `synthetic_quality_findings`
- `synthetic_quarantine_items`
- `synthetic_schedules`
- `synthetic_review_actions`

Use the existing `background_jobs` table for job orchestration; link each factory run to one durable job ID. Do not duplicate generic job state in a separate factory queue.

Each dataset must have a signed or hash-protected manifest containing at minimum:

- Dataset ID and schema version.
- Job ID and recipe ID/version.
- Synthea exact version/commit and JAR SHA-256.
- Java version.
- Random seed and any clinician seed.
- Complete command/configuration hash (secrets excluded).
- Module pack identifiers, versions and hashes.
- FHIR version and profile/IG package versions.
- CSV/export settings and years of history.
- Cohort criteria and code-set versions.
- Validator exact version/hash and validator parameters.
- Terminology release/mapping-set versions and hashes.
- Rule-pack versions.
- Generation start/end timestamps.
- Counts by resource type and cohort selection metrics.
- File paths relative to the dataset root, sizes and SHA-256 digests.
- Validation and quarantine totals.
- Import result and idempotency key.
- Software version (`HSPTL 5.0.0` build identifier).

Use canonical JSON for manifest hashing. Never put secrets in manifests or events.

## 9. Job orchestration, recovery and scheduling

Use the existing durable `JobRunner` after adding/migrating all missing schema fields. Required behaviour:

- One active Synthea generation job by default.
- Worker startup/shutdown integrated into FastAPI lifespan or a documented local worker mode.
- Configurable `HSPTL_ENABLE_WORKER`, enabled by the normal local installer unless explicitly opted out.
- Durable lease and heartbeat; stale jobs are safely reclaimed.
- Persist stage checkpoint and progress after each meaningful unit of work.
- Retry transient I/O/process-start errors with bounded exponential backoff.
- Do not retry deterministic validation failures endlessly.
- Cooperative cancellation between stages and safe child-process termination during generation.
- Pause is supported only at safe stage boundaries; do not claim a subprocess can be paused if it cannot.
- On restart, inspect the last completed checkpoint and either resume safely or mark the staging run for deterministic cleanup/retry.
- Idempotency key derived from canonical recipe/version + Synthea build/hash + seed + population settings + module hashes + export settings. An identical request returns or links to the existing run unless the user explicitly requests a new run ID with a new seed.
- Record attempt count, last error code, and safe diagnostic text.

Scheduling must be local and persisted in SQLite. It must not require Windows Task Scheduler, a cloud queue, or external cron for normal operation. Prevent overlapping scheduled jobs. Default schedules are off until explicitly enabled.

## 10. Event log integration

Use the existing HSPTL Kernel and append-only event log. Add versioned event contracts and update `docs/hsptl40/event_catalogue.json` (or its versioned successor) for metadata events such as:

- `platform.synthetic_data.recipe_created`
- `platform.synthetic_data.recipe_activated`
- `platform.synthetic_data.job_queued`
- `platform.synthetic_data.stage_changed`
- `platform.synthetic_data.generation_completed`
- `platform.synthetic_data.validation_completed`
- `platform.synthetic_data.dataset_registered`
- `platform.synthetic_data.records_quarantined`
- `platform.synthetic_data.dataset_imported`
- `platform.synthetic_data.review_recorded`
- `platform.synthetic_data.job_cancelled`

Events should include stable IDs, recipe/dataset/job IDs, versions, state, counts, rule-pack/validator IDs, digests, timestamps and reviewer metadata where relevant. **Never include full FHIR payloads, names, addresses, birth dates, or raw clinical resource values in the append-only event log.** Store patient data in access-controlled file-backed synthetic datasets and use pseudonymous identifiers in audit metadata.

All event payloads must pass the existing canonical JSON and schema validator. Malformed writes must fail closed and be audited through the existing write-prevention mechanism.

## 11. Backend API

Create a focused router, such as `backend/routers/synthetic_data_factory.py`, and wire it into the existing FastAPI app. Follow current Pydantic version and router patterns.

Provide endpoints similar to:

- `GET /api/synthetic-factory/status` — prerequisites, worker health, storage capacity, configured versions.
- `GET /api/synthetic-factory/settings` — safe settings only; never expose secret values.
- `PUT /api/synthetic-factory/settings` — update allowed local paths and bounded settings.
- `GET /api/synthetic-factory/recipes` — list built-in and user recipes with lifecycle status.
- `GET /api/synthetic-factory/recipes/{recipe_id}` — recipe detail/version.
- `POST /api/synthetic-factory/recipes` — create a draft recipe.
- `POST /api/synthetic-factory/recipes/{recipe_id}/validate` — validate schema, Synthea modules and code criteria.
- `POST /api/synthetic-factory/recipes/{recipe_id}/activate` — activate only after required review.
- `POST /api/synthetic-factory/jobs` — create an idempotent generation job.
- `GET /api/synthetic-factory/jobs` — paginated job list.
- `GET /api/synthetic-factory/jobs/{job_id}` — state, progress, checkpoint, safe logs and result.
- `POST /api/synthetic-factory/jobs/{job_id}/cancel` — request cancellation.
- `POST /api/synthetic-factory/jobs/{job_id}/retry` — retry an eligible failed run safely.
- `GET /api/synthetic-factory/datasets` — accepted dataset catalogue.
- `GET /api/synthetic-factory/datasets/{dataset_id}` — manifest summary and metrics.
- `GET /api/synthetic-factory/datasets/{dataset_id}/report` — download/view quality report.
- `GET /api/synthetic-factory/quarantine` — filtered quarantine list.
- `GET /api/synthetic-factory/quarantine/{item_id}` — finding and redacted diagnostic.
- `POST /api/synthetic-factory/quarantine/{item_id}/review` — audited review decision.
- `GET /api/synthetic-factory/schedules` and `PUT /api/synthetic-factory/schedules/{schedule_id}` — local scheduling controls.

Use strict request schemas, bounded numeric values, pagination, safe path handling and stable error codes. Do not expose a generic endpoint that accepts arbitrary shell arguments or executable commands. Do not permit arbitrary user-supplied filesystem paths as source/output locations.

## 12. Frontend dashboard

Create a dedicated **Synthetic Data Factory** workspace/page integrated into the existing HSPTL navigation and Midnight Cobalt design system. Do not build a separate application.

The UI must include:

### A. Factory overview

- Generator/validator readiness.
- Worker status.
- Dataset counts.
- Accepted/quarantined/rejected counts.
- Recent jobs and stage progress.
- Storage usage and warnings.

### B. Generation wizard

1. Choose an active recipe.
2. Choose target number of accepted patients or generation population size.
3. Select approved demographic constraints.
4. Select seed mode: fixed/reproducible or generated once and then recorded.
5. Choose FHIR R4, CSV, or both.
6. Choose history window and allowed output options.
7. Preview Synthea version, module hashes and cohort criteria.
8. Run preflight.
9. Confirm and queue.

Never imply that a requested disease cohort count is guaranteed. Clearly display expected/probabilistic cohort behaviour and actual matched counts after generation.

### C. Job monitor

- Queued, running, stage, percentage/count progress, elapsed time, retry count.
- Cancel button while safe to cancel.
- Expandable logs and failure diagnosis.
- Resume/retry only when a safe checkpoint exists.
- No false progress or fabricated ETA.

### D. Dataset registry

- Dataset name/ID, recipe/version, generator/version, seed, creation date.
- Generated, matched, accepted, quarantined and imported patient counts.
- FHIR validation and terminology status.
- File formats, sizes and checksum verification.
- Download quality report.
- Open dataset details and provenance.

### E. Quality workbench

- Findings grouped by structural/reference/chronology/terminology/plausibility/completeness.
- Severity and rule IDs.
- A controlled, redacted diagnostic view.
- Compare source and derived hashes/metadata.
- Re-run a newer validation pack against an immutable dataset.
- Review and disposition with a reason.

### F. Schedules and settings

- Enable/disable local schedule.
- Frequency, recipe, patient target and time window.
- Show next run and last result.
- Configure Synthea JAR, Java, validator JAR, modules, package cache and memory limits.
- Validate setup without generating a population.

The UI must clearly distinguish:

- `Technically accepted synthetic dataset`
- `Quarantined dataset`
- `Clinically reviewed recipe`
- `Published learner-facing scenario`

Do not use a green status alone to imply clinical safety.

## 13. Windows installation and operator experience

Update the existing Windows installation/start scripts and documentation.

The setup experience should:

1. Detect Java and display its version.
2. Ask the user to locate a Synthea JAR/distribution or guide them to the official Synthea repository/release.
3. Verify file readability and SHA-256.
4. Record the exact Synthea version.
5. Ask for an HL7 FHIR Validator JAR or configure a clearly marked limited-validation mode.
6. Verify free storage and default output paths.
7. Set a conservative 1.5–2 GB Synthea heap default for an 8 GB machine.
8. Configure single-job concurrency.
9. Enable the local worker by default for the normal local install, with a documented opt-out.
10. Run a tiny test generation (for example 2–5 patients) only when the user explicitly chooses “Run setup smoke test”.

Do not require Docker, PostgreSQL, Redis, cloud credentials or an API key.

Update README, installation notes, operator manual, security/privacy note, release notes and the architecture document.

## 14. Security, privacy and governance

Although Synthea data are synthetic, they may look realistic and can contain personal-looking attributes. Treat them as sensitive test data for safe handling.

- Keep all factory data under `HSPTL_HOME` by default.
- Keep the API bound to loopback in local mode.
- Do not expose arbitrary import/export paths.
- Never log full patient bundles, names, addresses, birth dates or complete clinical histories in standard application logs.
- Use pseudonymous patient keys in dashboard lists and audit events.
- Enforce safe download paths and prevent path traversal.
- Bound upload/import file sizes and NDJSON line sizes.
- Keep validator logs and diagnostic excerpts controlled.
- Keep source datasets immutable and record retention policy.
- Make cleanup explicit and safe; never automatically delete a registered dataset or active source artifact because a temporary directory cleanup ran.
- Do not treat synthetic data as de-identified real data or evidence of privacy protection for all deployment contexts.
- Clearly label every dataset as synthetic.

Future multi-user/cohort sharing remains gated by HSPTL's authentication, authorization, privacy and institutional governance requirements. Do not claim Phase 8 production controls are solved by the factory.

## 15. Testing requirements

Create unit, integration, API, UI and migration tests. Avoid needing the full Synthea JAR for ordinary CI tests by using a deterministic fake Synthea process/adapter and small checked-in synthetic FHIR fixtures. Add an optional integration smoke test for a locally configured pinned Synthea distribution.

### Required backend tests

- Additive SQLite migration from a 4.0.2 database preserves all existing rows.
- Background job runner claim/lease/heartbeat/result/cancel/retry lifecycle works with the migrated schema.
- Synthea preflight detects missing JAR, missing Java, wrong checksum and invalid module directory.
- Argument construction is safe and deterministic; shell injection/path traversal is rejected.
- Distinct jobs use separate output directories.
- Fixed seed/version/config yields the same job input manifest hash.
- Cohort selector correctly detects coded conditions and selects whole patient bundles.
- Target cohort shortage returns partial status and never fabricates a condition.
- Empty or corrupted output fails safely.
- FHIR Bundle, JSON and NDJSON parsing respects size limits.
- HL7 validator adapter parses success/failure and preserves OperationOutcome diagnostics.
- Patient/Encounter/subject references resolve and invalid references are quarantined.
- Resource-specific chronology rules detect reversed periods without flagging valid abnormal clinical observations.
- Terminology mapping preserves source coding and refuses ambiguous mapping.
- Plausibility rules are versioned, transparent and do not rewrite clinical values.
- Technical pass auto-registers and imports once; rerun is idempotent.
- Quarantined records never enter active fixture catalogue.
- Resume/restart/cancel/retry does not duplicate records.
- Event log stores metadata/digests only, never full FHIR resource contents.
- Worker lifecycle starts/stops correctly and does not spawn duplicate workers.
- Schedule avoids overlapping runs.

### Required frontend tests/checks

- Recipe selection and generation wizard validation.
- Clear display of generator prerequisites.
- Job progress and cancellation states.
- Accepted vs quarantined dataset statuses.
- Quality report and provenance views.
- Responsive layout and keyboard controls.
- All forms enforce configured population limits and valid input ranges.

### Adversarial fixtures

Include at least these cases:

1. Valid single-patient FHIR R4 Bundle.
2. Valid patient with a clinically abnormal observation.
3. Broken subject reference.
4. Missing Patient in a bundle.
5. Reversed Encounter period.
6. Duplicate resource ID collision.
7. Invalid Quantity unit/value data type.
8. Unknown/unmapped terminology code.
9. Unsupported profile declaration.
10. Malformed JSON and oversized NDJSON line.
11. Valid cohort with fewer matches than requested.
12. Repeated same import request.

A clinically abnormal but structurally valid observation must not be rejected solely because it is outside a normal reference range.

## 16. Verification and release discipline

- Implement all backend, frontend, migration, documentation and packaging changes before the consolidated test/build phase.
- Run the existing full release verification and new tests once after implementation is complete.
- If failures occur, fix the identified cause without repeatedly running the entire suite. Use targeted checks only when needed; report exactly what was and was not reverified.
- Do not claim a passed build or test unless it actually ran and passed.
- Produce HSPTL 5.0.0 release notes, implementation audit, operator guide, configuration reference and a final ZIP package with a SHA-256 checksum.
- Preserve the previous 4.0.2 release artifact and do not overwrite it.
- Report any blocked capabilities candidly (for example, official validator JAR not configured, missing Synthea distribution, clinical module review pending, or UI build blocked by unavailable dependencies).

## 17. Definition of done

HSPTL 5.0.0 Synthetic Data Factory is complete only when all of the following are true:

1. A user can configure Synthea and the validator locally without API keys or cloud services.
2. The user can select an active recipe and queue a generation job from the HSPTL UI.
3. The job is automatically executed by the durable local worker.
4. Every run uses a unique isolated output directory and a complete manifest.
5. Generation is reproducible when Synthea build, seed, recipe, modules and configuration match.
6. FHIR R4 and CSV exports are handled according to the selected recipe.
7. Strict FHIR conformance status is based on a pinned HL7 validator; limited validation is labelled accurately.
8. Referential, chronology, terminology, plausibility and completeness audits are available with distinct results.
9. No clinical facts are silently fabricated or changed during cleanup.
10. Failed or uncertain records are quarantined with actionable diagnostics.
11. Passed records are automatically registered and imported idempotently into HSPTL's existing fixture/case capabilities.
12. Dataset provenance is complete, immutable and auditable.
13. Cancellation, retries, worker restart and schedule execution are safe.
14. The dashboard exposes job status, quality results, registry, quarantine and settings.
15. Existing HSPTL features and user data remain intact.
16. Tests, verification, release documentation and the HSPTL 5.0.0 package are produced with honest status reporting.

## 18. Final implementation report required from the coding agent

At the end, provide:

- Implemented file/change summary.
- New SQLite migrations and backward-compatibility result.
- Exact Synthea and FHIR validator setup requirements.
- API endpoint list.
- UI page and workflow summary.
- Generation recipe list and review status.
- Validation rules implemented and limitations.
- Test/build results, with pass/fail/blocked status.
- Known limitations and safety boundaries.
- Windows install/configuration/run instructions.
- Release ZIP location and SHA-256.

Do not stop at a design document or scaffold. Implement the feature end-to-end in the checked-out repository.

---

# END OF IMPLEMENTATION DIRECTIVE

## Reference links

- Synthea repository, command-line options, export formats: https://github.com/synthetichealth/synthea
- Synthea common configuration: https://github.com/synthetichealth/synthea/wiki/Common-Configuration
- Synthea module framework: https://github.com/synthetichealth/synthea/wiki/Generic-Module-Framework
- Synthea Module Builder: https://synthetichealth.github.io/module-builder/
- HL7 FHIR Validator: https://hl7.org/fhir/validator/
- FHIR R4 specification: https://hl7.org/fhir/R4/

**Important:** This document is an implementation prompt for a coding agent. It does not itself install Synthea, modify HSPTL, run migrations, or certify clinical safety.
