# HSPTL 6.1.0 — Operationally Autonomous Clinical Learning Platform

**Milestone type:** Integrated product capability  
**Baseline:** HSPTL 6.0.0, Windows verification green on commit `e3fb4216e70a44e35587cd4db701128e85b1b768`  
**Release rule:** Do not tag or publish `v6.1.0` until the end-to-end definition of done in this document is met.

## 1. Product objective

HSPTL 6.1 makes the existing HSPTL capabilities operate as one dependable, largely unattended clinical-learning system. It is not a navigation redesign or a feature-count release.

The core product loop is:

**discover and acquire → preserve provenance and rights → screen → generate → provisionally publish and distribute → learner uses the material → collect post-use feedback → validate and monitor → refresh, correct, quarantine or withdraw when sources change.**

The same operational system must also maintain a reliable supply of eligible, clearly labelled synthetic daily cases through the persisted Daily Case Lottery.

Routine acquisition, processing, generation, refresh and eligible provisional educational distribution must not require per-record human pre-approval or a mandatory external AI API key. Human expertise remains essential for clinical sign-off, ambiguous source lifecycle decisions, rights exceptions and other genuinely judgement-dependent cases. These are exception paths, not routine gates on every record.

## 2. Product principles that 6.1 must preserve

1. **Automation by default.** Eligible work proceeds automatically; failed or ineligible work receives an explicit reason and a recoverable state.
2. **Provisional is not approved.** Automated publication makes eligible learning material available with an honest provisional/unreviewed label. It never sets clinical validation to complete.
3. **Rights are a hard boundary.** Metadata discovery does not grant full-text or image reuse rights. Unknown, restricted or unsupported rights block unauthorised reuse; permitted metadata-only records may remain discoverable.
4. **Provenance is continuous.** Every derived artefact retains the source, source version, licence/rights facts, generation method, citations and lifecycle state needed to audit and refresh it.
5. **Synthetic means synthetic.** Synthea-derived cases are privacy-minimised, explicitly labelled and assessed by synthetic-data quality checks. Synthetic QA is not clinical validation and the cases are never real-patient records.
6. **Validation follows use.** Learners provide post-use feedback against the exact artefact version they used. Educational, clinical, source and assessment dimensions remain distinct in the 0–100 validation metric.
7. **No competence claims.** Usage, learner ratings and validation scores do not establish clinical competence, entrustment or readiness for unsupervised practice.
8. **No mandatory AI dependency.** Deterministic local processing is the guaranteed fallback. An optional local model may improve authoring, but core workflows must work without a model, cloud service or API key.
9. **Preserve the architecture.** Retain the seven workspaces and seven engines. Prefer integration, reliability and observable workflows over replacing architecture or adding destinations.
10. **Fail visibly and recover safely.** No silent data loss, duplicate artefacts, hidden provider failure or false claim of exhaustive external-source coverage.

## 3. Scope and workstreams

### 3.1 Code-grounded capability audit

Before implementing more features, map the actual `main` branch code paths for source acquisition, background scheduling, UCKS ingestion, generation, provisional distribution, source lifecycle reconciliation, synthetic data, Daily Case Lottery, learner post-use feedback and monitoring.

For every capability, record one of:
- implemented and verified end to end;
- implemented but only unit-tested or manually exercised;
- partially implemented;
- missing;
- externally constrained or not reliably verifiable.

Do not reimplement working components simply because their integration is incomplete. Identify duplicate schedulers, competing state transitions, inconsistent identifiers and missing cross-component contracts.

### 3.2 Autonomous acquisition and recovery

- Prove keyless scheduled acquisition for supported public providers.
- Persist provider cursors/checkpoints, retry/backoff state, last attempt, last success, records/pages processed and explicit failure reasons.
- Resume bounded pagination after restarts without duplicate source records or unbounded loops.
- Make result-window limits, indexing delay, unavailable full text and incomplete historical backfill visible.
- Treat provider health as endpoint reachability, not proof of source completeness or evidence quality.

### 3.3 Rights-aware processing, generation and distribution

- Connect successful acquisition runs to the shared ingestion and generation path.
- Automatically create source-derived learning artefacts for eligible, supported record types.
- Distribute eligible artefacts to the appropriate workspaces as provisional/unreviewed; do not wait for routine per-record approval.
- Keep restricted/unknown-rights records metadata-only where permitted; never infer permission from open-access discovery flags alone.
- Make processing idempotent for an unchanged source version.
- When source content materially changes, create a new artefact version or clearly mark the old artefact as needing refresh. Preserve history and citations.
- Record skips, rejections and failures with machine-readable reasons and operator-visible explanations.

### 3.4 Synthetic daily-case supply

- Prove the accepted Synthea/FHIR import → privacy-minimised teaching-case authoring → synthetic QA → lottery eligibility → persisted lottery draw path.
- Require explicit quality gates for eligible synthetic bundles; skip incomplete or unsuitable bundles with reasons.
- Never expose patient names, contact details, direct identifiers or raw FHIR IDs in learner-facing cases.
- Keep Clinic and Ward on the same date-scoped persisted draw. Refreshing the page must not redraw the case.
- Preserve withheld answers until the intended reveal step.
- Do not permit arbitrary harvested articles or unsupported model output to become synthetic patient-like lottery cases.

### 3.5 Source-change and lifecycle propagation

- Reconcile exact, unambiguous source identifiers and explicit provider lifecycle relations against the source registry.
- On confirmed retraction, automatically quarantine/withdraw all dependent artefacts and distribution routes, with a traceable event.
- On correction or supersession, preserve the old version, record the new lifecycle state and refresh or flag dependent artefacts as appropriate.
- Treat ambiguous notices and unresolved relations as proposals for review; do not silently promote uncertain signals to authoritative lifecycle changes.
- Provide a report of affected artefacts and the propagation outcome.

### 3.6 Learner use and post-use validation

- Verify that feedback can only be submitted after the learner has actually accessed/completed the applicable workflow, according to the existing product policy.
- Bind every assessment and expert sign-off to the artefact content hash/version.
- Preserve separate educational, clinical, source and assessment domains and the documented 0–100 scoring rules.
- Ensure revised content starts a new validation cycle; old evidence remains linked to the version previously assessed.
- Keep publication state, rights state, source lifecycle, clinical validation and learner competence separate.
- Provide transparent score components, coverage and outstanding sign-offs rather than displaying an unexplained number alone.

### 3.7 Operations and observability

Expose one coherent operational view for:
- scheduler and worker health;
- provider runs, checkpoints, last success and retry state;
- ingestion and generation queue depth;
- generated, provisionally distributed, skipped, failed and refreshed artefacts;
- source corrections/retractions and affected dependent artefacts;
- synthetic-data runs, QA outcomes and lottery-eligible case supply;
- post-use feedback, validation coverage, domain scores and outstanding sign-offs.

Every failure should include the stage, timestamp, relevant source/job/artefact identifier, reason and whether retry or human intervention is required. Worker startup/shutdown must remain safe and idempotent. Operators need pause/maintenance controls, but ordinary operation must not depend on manual approval of each record.

## 4. Required end-to-end acceptance scenarios

These are release-level scenarios, not merely unit tests.

### A. New evidence to learner feedback

A scheduled keyless provider run discovers an eligible source. HSPTL records provenance and rights, ingests and screens it, generates a supported educational artefact, provisionally distributes it to the correct workspace, and records a learner's post-use assessment against that exact content version.

**Pass evidence:** one traceable source-to-artefact lineage; correct provisional state; no per-record approval gate; successful learner-use and feedback records; repeat run does not create duplicates.

### B. Source revision and refresh

A provider returns a changed source version. HSPTL persists the immutable new version, identifies dependent artefacts, regenerates or flags them for refresh, and prevents stale artefacts from being presented as current without disclosure.

**Pass evidence:** version history, dependency links, refresh status, preserved old learner feedback and idempotent repeat processing.

### C. Confirmed retraction

A test provider supplies an exact, unambiguous retraction relation for an indexed source. HSPTL identifies all dependent artefacts and automatically quarantines/withdraws them from learner distribution.

**Pass evidence:** lifecycle event, affected-artefact report, withdrawal state and no silent deletion of historical provenance. Ambiguous signals must not trigger automatic retraction.

### D. Synthetic FHIR to Daily Case Lottery

An accepted synthetic FHIR bundle passes explicit eligibility and synthetic QA rules, becomes a privacy-minimised synthetic teaching case, and is enrolled once in the lottery. Clinic and Ward show the same persisted draw.

**Pass evidence:** no direct identifiers in learner output; synthetic label and QA status visible; clinical validation remains `not_assessed`; duplicate import does not duplicate the case; answer remains withheld until reveal.

### E. Restart and partial failure recovery

Interrupt a provider or generation job, restart the application, and allow workers to resume.

**Pass evidence:** durable checkpoint recovery, bounded retries, no duplicated artefacts, preserved provenance, visible failure/retry status and no job silently abandoned.

### F. No-key, no-model operation

Run core acquisition, deterministic processing, generation, distribution and daily-case workflows without a cloud AI key and without a local model installed.

**Pass evidence:** supported workflows complete using deterministic local paths; optional-model absence is not an application failure and no remote AI fallback is attempted.

### G. Rights boundary

A source with unknown or restrictive reuse permissions is acquired. HSPTL may retain permitted metadata, but must not create a derivative from restricted full text or images.

**Pass evidence:** rights state and skip reason are visible; no restricted body/image appears in generated artefacts; unrelated eligible sources continue through the pipeline.

## 5. Definition of done

HSPTL 6.1.0 is complete only when:

- All seven end-to-end acceptance scenarios pass, using deterministic provider fixtures/mocks for repeatable CI and a documented live-provider smoke test for external connectivity.
- The core workflow runs without external AI API keys or a required local model.
- Background jobs recover safely across restart and partial provider failure.
- The source-to-learner journey and source-change propagation are auditable end to end.
- Synthetic daily-case creation and lottery selection are proven through integration tests.
- Rights, provisional publication, source lifecycle, clinical validation and competency boundaries are preserved.
- The full backend test suite passes.
- Windows clean-install CI passes on the exact candidate commit.
- Frontend typechecking and production build pass on the exact candidate commit.
- A clean installation from the release package starts successfully and reports healthy operational status.
- README, changelog, operator docs, release status and verification report describe the actual shipped behaviour.

No feature is complete solely because an isolated unit test passes. The integrated learner journey must be demonstrated.

## 6. Explicit non-goals for 6.1

- Adding workspaces or changing the seven-engine architecture.
- Replacing the deterministic core with a mandatory LLM or cloud AI provider.
- Claiming exhaustive historical source coverage where provider APIs impose limits.
- Treating discovery, automated screening, open-access flags, synthetic QA or learner feedback as clinical approval.
- Treating the validation percentage as competency, entrustment or fitness-to-practise evidence.
- Claiming SSO/MFA, enterprise multi-tenant isolation, accreditation or validated clinical safety without separate implementation and verification.
- Broad UI redesign unrelated to making the autonomous learning loop observable and usable.

## 7. Recommended execution order

1. **Audit:** map existing code paths, tests and runtime behaviour; classify the current state without assumptions.
2. **Instrumentation:** make job/source/artefact lineage and operational status visible before changing orchestration.
3. **Vertical slice A:** deliver one supported provider source all the way to provisional workspace delivery and learner post-use assessment.
4. **Recovery and lifecycle:** add restart-safe execution, source revision handling and confirmed retraction propagation to the same vertical slice.
5. **Synthetic vertical slice:** prove accepted FHIR data reaches the shared persisted Daily Case Lottery safely.
6. **Rights and exception tests:** prove restricted and ambiguous cases are blocked or routed correctly without stopping unrelated eligible work.
7. **Release hardening:** run full backend, frontend and native Windows release gates; clean-install the release package.

For each step, reuse existing code and make the smallest coherent integration change. Avoid parallel pipelines that create competing sources of truth.

## 8. Release and versioning policy

- Keep the existing `6.0.0` baseline stable while 6.1 work is in progress.
- Use `6.1.0` as the release identity only after all definition-of-done checks pass.
- Update backend/frontend version metadata, changelog, release status, verification report and package manifest together.
- Tag and publish `v6.1.0` only after a green Windows workflow for that exact version-aligned commit.
- Preserve the distinction between implementation completion and clinical/rights approval of individual learning artefacts.

## 9. Milestone success statement

**HSPTL 6.1 succeeds when a learner can reliably use newly acquired, traceable, rights-permitted, provisionally published learning material and synthetic daily cases that HSPTL has acquired, processed, generated, distributed and refreshed automatically—without routine pre-use approval or mandatory AI API keys—while preserving post-use validation, provenance, rights and clinical safety boundaries.**
