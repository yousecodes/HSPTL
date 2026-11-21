# HSPTL 4.0.0 — release status

**Status:** development build with the first clinical simulation vertical slice; Python backend and API workflow verified; frontend production build not verified in this environment. This package should not be represented as a production-certified clinical system.

## Architecture delivery

- One existing FastAPI/SQLite modular monolith; no new service, broker, model server or plugin deployable.
- Existing HSPTL 3.0 React application and six workspaces retained.
- HSPTL 4.0 modules include Kernel, Reasoner, Logic, Composer, Router, Guards, Explain and the in-process SimulationRuntime.
- Bounded PROforma execution subset is the sole executable rule/predicate interface at the 4.0 boundary.
- New 4.0 event transitions share the append-only SHA-256-linked `di_events` ledger; replay verifies event-chain integrity.
- Six in-process workspace skins; Pulse and standards/interoperability boundaries are documented.
- Four error-proofing layers are enforced inside the monolith: write-boundary schema constraints, per-rule provability classification, pre-append runtime monitors, and immutable audit/replay. Rejected writes append `platform.write.prevented` events.
- Z3 is permitted only for rules classified `z3_required`; PROforma and closed-form rules do not fall back to SMT. Unknown rule IDs abstain.
- Eight D–F artifacts are included: event schema/catalogue, PROforma library/visual notation/debugger, Pulse specification/renderer inventory, skin specification/schema, guard matrix/fault-injection tests, explanation contract/renderer, golden corpus/replay-diff harness, and terminology/standards/interop ports.
- PheKB source-derived Type 2 diabetes EHR+ case/control logic is re-expressed as a PROforma test fixture with synthetic input vectors; a separate synthetic converter fixture is also retained. The fixture covers a bounded subset of the published preferred algorithm and universal control path, not site-specific data extraction or the full source code lexicons. CaSS and MedBiquitous examples are synthetic reference graphs, not official frameworks. GRADE appraisal fixtures are human-reviewed domain inputs and do not perform automated certainty aggregation. SNOMED CT RF2 import is opt-in; licensed terminology release files are not bundled.
- No AI/ML or embedding model is loaded or called. UCKS uses lexical FTS5; vector and embedding API paths abstain.

## Verification performed

- Original HSPTL 3.0 regression suite before 4.0 changes: **190 passed**.
- 4.0 focused behavior is included in the final combined backend suite.
- Full backend regression suite including the new simulation runtime and HTTP vertical-slice test: **259 passed**.
- HTTP end-to-end workflow: scenario list, run start, staged observation, blocked action, PROforma-gated learner actions through Pulse, delayed result, deterministic time advance, response transition, documentation, assessment, replay and immutable completion all passed.
- Python compilation: passed.
- TypeScript/TSX syntax transpilation: **26 files passed with zero syntax diagnostics** (syntax-only; not a typecheck).
- Frontend `npm run typecheck`: blocked because frontend npm dependencies are not installed in this offline environment (`react` and `@types/react` are unavailable); production build remains unverified.
- API boot smoke check: `/api/health` returned HTTP 200 using an isolated data directory. The backend test suite also covers the D–F API contracts.

## Environment limitation

The frontend dependency installation could not complete because the environment is offline and the npm cache lacks the pinned Vite package. A direct `npm run typecheck` attempt therefore reported missing `react`, `react/jsx-runtime` and React type declarations; the many follow-on JSX/type errors are dependency-cascade errors and do not establish a source typecheck result. `npm run build` is likewise unverified. `node_modules` is not included in the release archive. On the target machine, run `npm ci`, `npm run typecheck` and `npm run build` from `frontend/` before production deployment.

## Explicitly incomplete integrations / conformance

1. Full migration of legacy 3.0 repositories/routes into the universal event-sourced canonical projection is not complete. Existing 3.0 features remain compatible, but legacy persistence is not silently claimed to meet the 4.0 proof contract. The four-layer write gate applies to new HSPTL 4.0 platform events; legacy compatibility writes remain under the documented legacy contracts.
2. PROforma is a bounded safe subset, not certified full-language conformance.
3. Ontology entailment is a positive finite taxonomy, not full OWL-DL.
4. The general/default Pulse provider has no external source connected; the synthetic scenario has a run-scoped provider backed by its own bounded teaching transition model. Neither is a live medical-device integration or validated physiology source.
5. Snowstorm full ECL requires external configuration/transport. The embedded SNOMED index contains a small fallback concept set and can import active RF2 Snapshot Concepts and Descriptions for exact code/term lookup when a locally entitled release is supplied; it does not import relationships, provide relationship-based entailment or implement full ECL. The official RF2 model includes Concept, Description and Relationship components; therefore this importer is intentionally a limited indexer rather than a complete terminology server. <https://www.snomed.org>
6. CQL is export-only; CDS Hooks is descriptor-only; LTI 1.3 is a configuration port requiring secure institutional launch handling; xAPI/SCORM are in-process adapters without hosted LMS/LRS services.
7. FSRS uses the inherited FSRS-style preview and is not asserted to be bit-identical to a validated reference implementation. IRT parameters are authored and fixed, not trained.
8. Mastery signals are formative and do not certify clinical competence or privileges.

## Clinical simulation vertical slice

- Added the synthetic `asthma-moderate-adult-001` case and six PROforma action models.
- Added `ClinicalSimulationRuntime` as an in-process module that uses the canonical event Kernel; no separate run database or deployable was added.
- Added staged observation, integer-minute clock, deterministic PEF/response/worsening events, run-scoped Pulse provider, structured note/handover versions, itemized formative assessment, replay digests and completion sealing.
- Added Clinic → Simulation Lab UI and the `/api/v4/simulation/*` API routes.
- The scenario and rubric are draft pending qualified clinical educator review. The state transitions are illustrative pedagogical fixtures, not empirically calibrated physiology or treatment recommendations. No medication doses are encoded.
- See `docs/HSPTL_CLINICAL_SIMULATION_VERTICAL_SLICE.md` for the learner flow, API contract, determinism details and limitations.

## Safe deployment note

HSPTL is educational software. It is not a medical device or a patient-specific clinical decision-support system. Do not use it to diagnose, treat, triage or otherwise make decisions about real patients. Review external source rights, provenance, local governance and security configuration before importing or distributing material.


## G — argumentation and temporal reasoning

- PROforma Decision tasks now compute additive `for` / `against` argument profiles and expose the full preference ordering to the user. The UI requires explicit user selection; a preference is not a conclusive clinical decision.
- The same PROforma expression trees can be compiled to CNF. Embedded Z3 adapters implement argument consistency/minimal unsatisfiable cores, consistent differential enumeration and one-finding preference counterfactuals behind the provability registry.
- Versioned ASP data is executed through the in-process Clingo Python API to infer event-backed pathway states, detect deviations and gate task-level temporal prerequisites. Pulse observations enter the canonical event log as source-labelled events.
- One derivation envelope serves clinical, pedagogical and negative explanation views. The reasoned router attaches IRT, FSRS, prerequisite and Brier arguments to every routeable candidate and does not auto-select.
- G-specific tests pass in the package build environment. Z3 and Clingo were not installed because external package installation was unavailable, so their positive runtime paths are not claimed as locally executed; unavailable dependencies fail closed. The frontend enactment TSX is syntax-checked, but dependency-backed TypeScript typecheck and production bundling remain separate verification requirements.
