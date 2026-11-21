# HSPTL 4.0 — deterministic modular monolith

**Release line:** 4.0.0 development build  
**Runtime policy:** no AI/ML models, no embedding inference, no new deployable services.

HSPTL 4.0 keeps the existing 3.0 web application, six-workspace experience and legacy workflows. The 4.0 intelligence increment is implemented as in-process modules over the existing FastAPI/SQLite application. It adds no worker service, broker, model server or separately deployed plugin host.

## 1. Runtime shape

```text
One React application
  ├─ six workspace skins (Clinic, Rounds, Lab, Ward, Exam Hall, Portfolio)
  ├─ Pulse state renderers / action controls
  ├─ PROforma enactment components
  └─ plugin module registry
             │ core event API
             ▼
One FastAPI modular monolith
  ├─ Kernel   — append-only event ledger, provenance, replay
  ├─ Reasoner — finite ontology subset, entailment and proof paths
  ├─ Logic    — bounded PROforma execution subset
  ├─ Composer — templates/slots over graph projections
  ├─ Router   — predicate eligibility, DAG sequencing, IRT, FSRS
  ├─ Guards   — pass / fail / abstain, structural and optional SMT checks
  ├─ Explain  — deterministic derivation envelopes
  └─ SimulationRuntime — versioned scenario runs, integer clock, typed transitions
             │ in-process ports
             ├─ Terminology: embedded exact-match concept index; Snowstorm port
             ├─ Standards: FHIR R4 / CQL export / CDS Hooks descriptor
             └─ Interop: LTI 1.3 descriptor / xAPI statement / SCORM runtime data

Existing SQLite repositories and legacy HSPTL 3.0 routes remain available for
compatibility. The 4.0 platform paths use the shared deterministic-intelligence
ledger. Full migration of every legacy table and workflow into event-sourced
projections is not complete; legacy persistence must not be mistaken for the
new 4.0 proof contract.
```

## 2. Core module contracts

| Module | Responsibility | Boundary |
|---|---|---|
| Kernel | Append-only SHA-256-linked events, event read, replay, head/projection status | Reuses `di_events`; no broker or event service |
| Reasoner | Positive finite taxonomy entailment, typed relationships, competency entailment | Missing/unsupported facts remain unknown; not full OWL-DL |
| Logic | Safe PROforma task/predicate subset for plans, decisions, actions, inquiries | No Python/JS/SQL evaluation and no parallel rule syntax |
| Composer | Versioned slot templates, template preconditions, graph-derived composition | Templates hold contracts, not embedded clinical facts |
| Router | PROforma eligibility predicates, deterministic topological order, fixed-parameter 2PL IRT, FSRS-style review output | Computed views are returned, not persisted as derived truth |
| Guards | Shared `pass` / `fail` / `abstain` result; Poka-yoke and optional Z3 | Unknown/solver unavailable => audited abstention |
| Explain | Stable SHA-256 derivation envelope | Captures rules, inputs, steps and source-event references |
| SimulationRuntime | Scenario catalogue, seeded run, typed transition model, clock, event-folded state, formative assessment and replay | Bounded educational model only; no general physiology engine or separate run database |

### One executable language

The runtime identifies itself as `HSPTL-PROforma-Subset/1.1`. It supports task types `plan`, `decision`, `action`, and `inquiry`, plus a deliberately constrained predicate vocabulary. All executable preconditions, appraisal expressions, template preconditions and routing predicates at the 4.0 boundary are evaluated through this runtime. Unsupported operators and missing inputs resolve to `abstain`.

This is a bounded PROforma execution subset with explicit validation and event-backed enactment, not a claim of complete PROforma language or conformance-suite compatibility. The runtime never evaluates arbitrary user code.

### Event lineage and replay

New 4.0 pathway, guard, composition, routing, Pulse action-request, plugin-configuration, mastery-signal and clinical-simulation transitions append to the same `di_events` ledger used by the deterministic-intelligence core. Event hashes link to the previous event. Replay verifies the chain and rebuilds the registered canonical projection.

Clinical assertions composed through `evidence-linked-assertion@1.0.0` require canonical evidence, a passing appraisal, permitted reuse rights, and a source span whose content hash matches the evidence. The returned lineage is:

`assertion → evidence entity → appraisal → evidence/source event → source span`

The derivation envelope contains the exact source event IDs/sequences and a stable digest. A missing lineage item blocks composition. Legacy HSPTL 3.0 workflows are preserved, but not all of them have yet been migrated to this strict assertion contract.

## 3. Closed-form intelligence

- **Competencies:** derived from explicit typed learning-object relationships; no competency score is stored by this module.
- **Coverage gaps:** `required − covered` set difference.
- **Conflicts:** opposing scoped evidence polarities are checked with Z3 as a read-only derivation. The computed conflict result is not stored. Missing evidence, missing solver or undecidable checks abstain. This does not determine which source is clinically correct.
- **Mastery:** formative signals are append-only events; the displayed state is a fold over that event sequence. It is not proof of independent clinical competence or authorization.
- **Review dates:** calculated through the existing FSRS-style scheduler from the supplied card state and grade. The inherited scheduler documents this as an FSRS-4.5-style preview, not a bit-identical or validated FSRS implementation.
- **Assessment adaptation:** deterministic 2PL IRT estimate using supplied, authored item difficulty/discrimination parameters. Parameters are not trained by the platform.
- **Sequence:** stable Kahn topological sort; cycles fail closed.

No AI/ML model is loaded or called by the HSPTL 4.0 product runtime. UCKS retrieval is lexical SQLite FTS5. The vector/embedding HTTP paths now abstain; legacy stored vector rows are retained for compatibility but ignored. The provider sentinel cannot load a Sentence Transformers model.

## 4. Client and skins

The client remains one React application. The six skins are selected by a module registry and are presentation/routing configuration, not separate apps:

- Clinic — case reasoning and debrief
- Rounds — evidence teaching, viva and reports
- Lab — Pulse renderers, visual spotters and OSCE
- Ward — PROforma workflows
- Exam Hall — assessment and review scheduling
- Portfolio — progress, data tools and governance

Plugin modules execute in the host process and contribute through the core event API. Skin configuration rejects obvious clinical fact and executable-rule ownership. The registry does not provide an untrusted third-party code sandbox; only trusted modules shipped with the app should be registered.

## 5. Pulse bridge

The bridge exposes `step`, `getState`, and `applyAction`. The default provider is deliberately unavailable: it returns empty observations and `connected=false`, never fabricated vital signs. The frontend renders only supplied observations, with unavailable values shown as unknown. Optional SVG trend marks are drawn only when the Pulse provider supplies a numeric history series; they auto-scale to that series and do not apply clinical reference thresholds. An action request is audited to the event ledger; without a connected Pulse provider the action is not applied and the result is `abstain`.

The default general Pulse provider remains unavailable. The clinical SimulationRuntime now supplies a run-scoped Pulse provider for its synthetic, bounded scenario; this is an educational transition model, not a validated physiological simulator or a real device/provider integration.

## 6. Terminology, standards and interoperability ports

- **Terminology:** small embedded exact-match index is the default. Approximate matching abstains. Full SNOMED CT ECL requires a configured Snowstorm adapter; network transport/authentication is not bundled.
- **FHIR:** deterministic FHIR R4 `Observation` export mapping for already sourced observations.
- **CQL:** wrapper export for an authored/reviewed CQL expression; no CQL interpreter or clinical validation.
- **CDS Hooks:** descriptor export only; no hosted clinical decision support service.
- **xAPI / SCORM:** statement and runtime-data adapters; no Learning Record Store or LMS endpoint is bundled.
- **LTI 1.3:** configuration descriptor only; institutional registration, OIDC launch, JWT/JWKS verification and secure launch handling require an external adapter.

These are in-process ports/adapters; they do not create new deployment units.

## 7. API surface

All 4.0 routes are under `/api/v4`:

- `GET /architecture`, `GET /status`, `GET /events`, `POST /replay`
- `GET /logic/catalogue`, `POST /logic/validate`, `POST /logic/enactments`, `GET /logic/enactments/{id}`, `POST /logic/enactments/{id}/step`
- `POST /guards/evaluate`, `POST /guards/smt`, `POST /appraisal/evaluate`
- `GET /reasoner/catalogue`, `POST /reasoner/entail`, `/relationship`, `/competencies`, `/conflicts`
- `GET /composer/templates`, `GET /composer/graph`, `POST /composer/compose`
- `POST /router/eligibility`, `/route`, `/topological-order`, `/irt/estimate`, `/fsrs/next-review`
- `POST /analytics/gaps`, `POST /analytics/mastery/events`, `GET /analytics/mastery`
- `GET /workspaces/skins`, `PUT /workspaces/{workspace}/plugins/config`
- `GET /pulse/state`, `POST /pulse/step`, `POST /pulse/actions`
- `GET /simulation/scenarios`, `GET /simulation/scenarios/{id}`, `POST /simulation/runs`, `GET /simulation/runs/{id}`, run-scoped Pulse step/actions, clock advance, documents, assessment, replay and completion routes
- `GET /ports`, terminology lookup/ECL and standards/interop adapter endpoints

A blocked/unknown operation returns an explicit abstention at the API boundary (commonly HTTP 409), rather than silently selecting a default clinical action.

## 8. Compatibility and known limitations

1. Existing 3.0 pages, routes and repositories are retained. Migration of all historical 3.0 state to a single event-sourced projection is not complete; this is the principal remaining architectural migration gap.
2. The ontology is a finite positive taxonomy/profile, not full OWL-DL. Unsupported constructors and absent assertions do not entail a negative fact.
3. PROforma is a bounded subset, not certified full-language conformance.
4. Pulse is an adapter contract; no provider is connected by default.
5. Terminology, CQL, CDS Hooks and LTI are adapters/descriptors with the boundaries above, not production external endpoints.
6. FSRS is an inherited style preview. IRT uses fixed item parameters and is not calibrated automatically.
7. Mastery signals are formative and do not certify professional competence.
8. Frontend package dependencies must be installed on the target environment before typecheck/production build. The source package has no vendored `node_modules`.

## 9. Verification

The package is verified with its Python backend/test suite and API smoke checks. The release note records the exact test counts and the environment limitation on the frontend build. Run the release verification script on the target Windows/Python environment before production deployment.


## G — argumentation and event-derived temporal reasoning

PROforma decisions now carry independent additive arguments for and against every eligible candidate. The enactment UI displays support, opposition and net force with evidence/event references; preference is indicative and the user confirms the decision. The existing router exposes all defendable candidate learning objects with IRT, FSRS, prerequisite and Brier argument profiles.

A bounded PROforma-to-CNF compiler supports Z3-backed consistency, differential hypothesis and counterfactual checks for rule IDs explicitly classified `z3_required`. The optional Z3 library is imported in-process. Versioned ASP `.lp` data is run through the optional in-process Clingo library over the canonical event log; it supplies recognized states, pathway deviations and time-ordered prerequisites. Neither library is a separately deployed service. Missing solvers or unknown results abstain.

One derivation envelope is rendered through clinical, pedagogical and negative explanation views. These are display lenses over the same trace and hash, not separate explanation engines.

## 10. Clinical learning simulation roadmap

The starting G-release contained clinical case review, static puzzle solving, learner reasoning attempts, exams/OSCEs, PEARLS debrief prompts, a gated authored branching graph and a disconnected-by-default Pulse bridge. A first bounded SimulationRuntime vertical slice is now implemented for one synthetic adult moderate-asthma scenario. It covers staged observation, PROforma-gated actions, deterministic timed transitions, structured notes/handover, a trace-based formative rubric and replay/debrief in the existing Clinic workspace. It is not a general physiology simulator and remains pending qualified clinical educator review. See [HSPTL Clinical Learning Simulation Blueprint](HSPTL_CLINICAL_LEARNING_SIMULATION_BLUEPRINT.md) and [first vertical slice implementation record](HSPTL_CLINICAL_SIMULATION_VERTICAL_SLICE.md).
