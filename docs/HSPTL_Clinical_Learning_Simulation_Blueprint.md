# HSPTL Clinical Learning Simulation Blueprint

**Blueprint line:** HSPTL 4.0 G → clinical learning simulation roadmap  
**Status:** Code-grounded roadmap; Phase 0 discovery completed against the supplied G-release archive.  
**Scope assumption:** Local-first, single-learner, curated synthetic teaching scenarios first. Cohorts and institutional integration are later phases.  
**Product boundary:** Educational simulation only. This blueprint does not authorize use for live patient care, autonomous diagnosis, prescribing, or unsupervised clinical decision-making.

---

## Executive decision

HSPTL should evolve into a rich clinical learning environment without being rewritten. It should let a learner observe a simulated patient, take permitted clinical actions, advance simulated time, see the simulated consequences, document decisions, receive transparent formative assessment, and review a replayable debrief.

The supplied HSPTL 4.0.0 G archive was inspected. **Phase 0 is therefore no longer blocked by code access.** The archive contains a substantial clinical-learning application and several useful seams, but it does **not** contain a general, seed-driven patient-physiology simulator or an action-to-physiology response loop.

The key architectural decision is to add one bounded, in-process **Simulation Runtime** behind the existing PROforma and Pulse boundaries. It must not be a new deployable, a second general-purpose rule engine, or a parallel application. PROforma remains the workflow and decision language; the Simulation Runtime is a narrow, versioned state-transition implementation for the simulated patient. The Kernel remains the canonical history for new simulation runs. The existing React application and six skins remain the client.

The roadmap retains the original Phase 0–8 sequence, but makes the current capabilities, missing capabilities, integration points, deterministic contract, and independent exit criteria explicit.

## 1. Objective and success definition

Turn HSPTL from a case-solving and clinical-learning workspace into a sequenced clinical learning environment in which students and practitioners can:

1. enter a reviewed synthetic scenario with explicit learning goals;
2. observe the patient through a clinician-facing information surface;
3. choose from scenario-permitted assessment, investigation, treatment, escalation, and communication actions;
4. advance simulated time and observe versioned, deterministic patient-state responses;
5. document notes, orders, and handovers during the run;
6. receive itemized, explainable, initially formative assessment based on their trace;
7. replay the run and receive structured debrief; and
8. progress through authored cases and curricula, with instructor/cohort functions added only after identity, privacy, and deployment requirements are established.

**End-to-end pilot outcome:** A learner completes one clinically reviewed synthetic case from prebrief through observation, actions, documentation, formative scoring, replay, and debrief. An educator can explain every assessment item from the scenario version, rubric, learner actions, and event history. The pilot group and its educators judge the feedback useful and clinically sound for the stated teaching purpose.

## 2. Product principles and non-goals

### 2.1 Principles

- **Preserve the existing application.** Extend the FastAPI/SQLite backend and React client through internal modules and existing APIs.
- **One canonical simulation history.** Simulation actions, state transitions, released observations, documentation, assessment, and debrief completion are events in the existing HSPTL 4.0 Kernel ledger. Read models are projections, not competing truth stores.
- **PROforma remains the only executable workflow/rule language.** Scenario pathways, task preconditions, action eligibility, assessment predicates, and routing guards use the bounded PROforma runtime. Do not add a parallel decision-table language or general rule engine.
- **Pulse remains the physiological boundary.** Learner-facing vital signs and observations are read from Pulse. A new in-process simulator may implement the Pulse provider contract; skins must not read internal patient-state variables directly.
- **Simulation is deterministic and versioned.** Same scenario package, model versions, engine version, seed, clock policy, and ordered learner action sequence must reproduce the same semantic trace, state digests, and assessment result.
- **Unknown is not normal.** Missing, unreleased, stale, conflicting, and unavailable information remain explicitly distinct. An incomplete observation feed must not be interpreted as a negative finding.
- **Assessment is explainable.** Every awarded or withheld point links to an observable event, scenario criterion, rubric version, and explanation. Multiple clinically defensible paths must be representable.
- **Clinical content is governed.** Scenarios, state-transition parameters, action catalogues, rubrics, and teaching points are versioned, sourced, reviewed, and approved before release.
- **No AI/ML models.** No model server, vector database, broker, separate QA service, or separately deployed simulation service is added.

### 2.2 Non-goals for this roadmap

- Rewriting HSPTL or replacing its six workspaces.
- Building a full hospital information system or an unrestricted digital twin of human physiology.
- Using imported real-patient data as a live simulated encounter without explicit legal, privacy, and governance approval. The first simulator should use synthetic/curated teaching material.
- Using the simulator to guide care for real patients or to issue autonomous clinical recommendations.
- High-stakes certification before independent assessment validation and an appropriate trusted assessment boundary.
- VR/3D, multiplayer networking, external LMS deep integration, or additional deployable services in the first vertical slice.

## 3. Phase 0 — verified capability inventory

### 3.1 Inspection basis and verification

The inspected source is `HSPTL-4.0.0-Deterministic-Modular-Monolith-G.zip`, extracted and reviewed in the working environment. The Python backend suite was run against that extracted package: **247 tests passed**. This verifies the included test suite at the inspected baseline; it does not establish clinical validity, a production frontend build, or the existence of an untested simulator.

The archive's existing documentation also records that frontend TypeScript typechecking/production bundling has not been verified in the prior build environment because dependencies were unavailable. That remains a release gate.

### 3.2 What exists today

| Capability | Verified implementation | Blueprint interpretation |
|---|---|---|
| Application/runtime | `backend/main.py`, `backend/runtime.py`, `backend/routers/`, React `frontend/src/App.tsx`; SQLite repositories | One local-first FastAPI/SQLite application and one React client. Keep it. |
| Clinical case data | `backend/hsptl_core/case_engine.py`; FHIR JSON/NDJSON/JSONL import, patient/encounter/fact repository, encounter narrative | Source-backed case review exists. This is record ingestion and learning, not an evolving patient simulator. |
| Case solving | `backend/hsptl_core/puzzles.py`, `puzzle_engine.py`; `/api/clinic/*`; `ClinicPage.tsx` | Curated static vignettes, clue reveal, answer attempts and source-linked teaching content exist. A static puzzle is not a first-class interactive scenario. |
| Learner reasoning | `case_engine.py`; `/api/clinical/learning-attempts`; `reasoning_feedback.py` | Learners can save problem representation, differentials, evidence for/against, investigation plan, confidence, working diagnosis, management, safety-net and communication fields. Reuse this as an existing learning artifact, not a new parallel form. |
| Debrief | `backend/hsptl_core/simulation.py`; `store.py` `simulation_debriefs`; `/api/clinical/learning-attempts/{id}/debrief`; `CaseDebriefsPage.tsx` | Prebrief objectives, PEARLS-style reflection prompts and persisted debrief answers exist. They are not yet a replay of a physiological simulation trace. |
| Exams and OSCE | `backend/hsptl_core/exams.py`; `backend/routers/assessment.py`; `ExamCentrePage.tsx`, `OSCEPage.tsx` | Versioned question snapshots, attempts, objective answer marking, OSCE text responses/checklists and timing exist. They do not yet score a full clinical action/state timeline. |
| Rubric helpers | `backend/hsptl_core/assessment.py` | Transparent 0–3 criterion guidance and learner self-assessment exist. The module expressly avoids claiming a clinical competence score. |
| Branching | `backend/hsptl_core/advanced.py`; `/api/branching/start`, `/api/branching/choose`; `policy.py` | Deterministic traversal of clinician-authored graph nodes exists behind a disabled-by-default feature policy. It does not simulate physiology or delayed test/treatment effects. |
| Simulation module | `backend/hsptl_core/simulation.py` | Contains learning outcomes, prebrief prompts and PEARLS debrief prompts. It is not a simulation loop or physiology model. |
| Pulse | `backend/hsptl_core/hsp_tl40/pulse.py`; `PulsePanel.tsx`; `/api/v4/pulse/*` | A thin bridge and renderer exist. The default provider is disconnected; it returns unavailable/unknown state. Action requests are recorded, but are not applied to a physiological patient model by default. |
| PROforma | `backend/hsptl_core/hsp_tl40/proforma.py`, `debugger.py`; `/api/v4/logic/*`; `ProformaWorkbench.tsx` | A bounded task runtime and enactment/debugger exist. It can become the workflow controller for scenarios and typed learner actions. It is not full PROforma language conformance. |
| Event history | `backend/hsptl_core/hsp_tl40/kernel.py`, `deterministic_intelligence/engine.py`, event catalogue and replay API | Append-only, hash-linked event history and replay exist for 4.0 paths. Legacy 3.0 workflows are not universally event-sourced. New simulation runs must use the 4.0 ledger from the start. |
| Episodes/artifacts | `backend/hsptl_core/episodes.py` | `LearningEpisode` and content-addressed learner artifacts link attempts, drafts, source references and debriefs. This is useful metadata/artifact storage; the new run's canonical sequence remains the Kernel event log. |
| Authoring/distribution | `ContentStudioPage.tsx`, `content.py`, `content_review.py`, `generation_distribution.py`, `workspace_distribution.py` | Existing content authoring/review/distribution surfaces can be extended for scenario packages and curricula. A full scenario authoring workflow is not established. |
| Workspaces | `frontend/src/App.tsx`, `frontend/src/pages/`, `frontend/src/hsptl40/skinRegistry.ts` | Keep Clinic, Rounds, Lab, Ward, Exam Hall and Portfolio as skins over shared modules. |
| Terminology/standards | `hsp_tl40/terminology_port.py`, `standards.py`, ports docs | Existing terminology and interoperability boundaries are adapters/limited exports. Extend only when scenario observations and actions require the codes. |
| Cohorts/identity | local profile and existing local data boundaries; no verified complete instructor/cohort identity workflow | Defer cohort-wide shared runs until authentication, authorization, learner privacy and deployment model are designed. |

### 3.3 What is not present or not verified

The inspected archive does not establish:

- a general patient physiology model that changes state over simulated time;
- a seeded pseudo-random simulation engine;
- an event scheduler for delayed investigation results or intervention onset/duration;
- a typed learner-action vocabulary that applies interventions to a simulated patient;
- a unified scenario manifest combining baseline state, event triggers, goals, allowed actions, model versions, and assessment criteria;
- a chart/order/handover workflow linked to a running simulated case;
- assessment scoring over a full simulation trace;
- debrief replay that reconstructs patient state and consequences from the same trace;
- a non-developer scenario authoring and curriculum workflow; or
- instructor-led cohort/facilitation capability with a complete identity and access boundary.

The code contains deterministic components, including stable daily puzzle selection based on a date hash and deterministic logic/derivation operations. However, the source inspection did not find a seed-driven physiology engine or a contract proving that the same seed plus learner actions reproduces a whole patient simulation. Several repositories generate UUIDs and wall-clock timestamps; those metadata values should not be included in the semantic simulation equality check.

### 3.4 Phase 0 exit decision

**Discovery is complete.** The next step is not a rewrite. It is a narrow vertical slice built around one versioned scenario, one learner observation view, a small reviewed action set, and a deterministic run trace.

## 4. Target architecture and module attachment points

```text
One React application (existing)
  ├─ Clinic skin: scenario launch, patient view, reasoning and run workspace
  ├─ Ward skin: PROforma tasks, actions, orders and handover
  ├─ Lab skin: Pulse observations, results and visual findings
  ├─ Rounds skin: rationale, case conference and educator review
  ├─ Exam Hall skin: formative assessment and retrieval practice
  └─ Portfolio skin: progress, competencies and evidence
                 │ existing API / event contracts
                 ▼
One FastAPI modular monolith (existing)
  ├─ Kernel: canonical run events, provenance, replay and projections
  ├─ Scenario Catalog: versioned data packages, validation and release status
  ├─ PROforma Logic: scenario plan, task sequencing, preconditions and action eligibility
  ├─ Simulation Runtime (new in-process module): fixed simulation clock,
  │    seeded deterministic transitions, scheduled events and state digest
  ├─ Pulse Bridge: the only client-facing physiological state/action boundary
  ├─ Composer: scenario templates and learner-facing observation/documentation projections
  ├─ Reasoner / SMT / ASP: supported entailment, consistency and temporal checks
  ├─ Assessment: versioned, trace-based formative rubric and proof-carrying score
  ├─ Explain: one derivation for actions, consequences, score and debrief
  ├─ Router: next task/scenario selection and later calibrated learning sequence
  └─ Existing Episodes / Exams / Content / UCKS modules reused through adapters
                 │ optional in-process ports
                 ├─ terminology (SNOMED CT / LOINC / UCUM as needed)
                 ├─ standards (FHIR / CQL / CDS Hooks adapters)
                 └─ learning interop (xAPI / SCORM / LTI / cmi5 later)
```

### 4.1 Responsibilities and boundaries

| Module/seam | Responsibility for the simulation roadmap | Must not do |
|---|---|---|
| Scenario Catalog | Load, validate, version and select authored scenarios | Execute arbitrary code embedded in scenario files |
| Kernel | Record every accepted/rejected action, simulation tick, state transition, released observation, document, score and debrief event | Depend on a separate broker or event service |
| PROforma | Own the executable workflow, decision tasks, preconditions, guards, task availability and next-action eligibility | Duplicate the workflow in UI code or a second rule engine |
| Simulation Runtime | Apply typed, reviewed state-transition functions and scheduled effects using a deterministic clock and seed | Become a general clinical reasoning engine or unrestricted digital twin |
| Pulse Bridge | Expose the patient-facing state stream and accept typed simulation actions | Let skins inspect hidden internal state or bypass event recording |
| Composer | Project the permitted observations, chart, orders and handover templates for the learner | Store independent clinical truth in templates |
| Assessment | Derive transparent criterion-level results from the run trace and versioned rubric | Claim competence from activity counts or unvalidated scores |
| Explain | Explain why an action was available, what changed, how a score was derived and what remains unknown | Maintain a second trace format or fabricate reasons |
| Episodes | Link run IDs to learner goals, documents, reflections and source artifacts | Become a parallel canonical event log |
| Existing skins | Configure display, interaction and navigation | Own clinical facts, scenario logic or safety rules |

The Simulation Runtime is a new **module**, not a deployable. It should initially support only a deliberately small set of variables and state transitions needed by the first approved scenario. Physiology fidelity must be expanded only with clinical review and validation evidence.

## 5. Canonical contracts for the first simulator

### 5.1 Scenario package

Each scenario is an immutable, versioned data package. A scenario package should contain:

- `scenario_id`, semantic version, title, specialty, setting and learner level;
- educational purpose, measurable learning objectives and expected prior knowledge;
- provenance, source references, licence/reuse status, jurisdiction, reviewer, review date and expiry/review trigger;
- synthetic patient identity and initial simulated state;
- explicit facts, explicit negatives, unknowns, unreleased findings and source-completeness status;
- the PROforma plan/model ID and digest;
- the permitted observation and disclosure policy;
- the permitted learner-action catalogue and typed payload schemas;
- deterministic state-transition model ID/version and parameters;
- scheduled events, triggers, delays and simulation-time windows;
- outcome/goal predicates and terminal conditions;
- versioned formative assessment criteria and scoring rationale;
- debrief prompts, teaching points and reference trace(s); and
- compatibility metadata for engine, event schema, terminology and rubric versions.

Scenario data must not contain arbitrary Python, JavaScript, SQL or shell code. Executable pathway logic is PROforma. The simulation model uses reviewed, typed in-process transition functions with versioned parameters; it is not a second general-purpose rules language.

### 5.2 Simulation run identity and replay contract

A run is reproducible only when all relevant inputs are fixed and recorded:

`scenario_digest + scenario_model_version + PROforma_digest + engine_version + transition_model_version + PRNG_algorithm/version + seed + clock_policy + ordered learner_action_sequence`

The run record must preserve:

- scenario and all executable/data package digests;
- seed and PRNG algorithm/version (if stochastic variation is used);
- simulation clock starting point, tick size and time-advance policy;
- event sequence numbers and event-time ordering;
- action requests, validation outcomes, accepted actions and rejected actions;
- scheduled events, result availability and state-transition inputs;
- state digest after each committed transition;
- released observation digest and disclosure stage;
- documentation artifact versions;
- assessment rubric version and derived score digest; and
- software/logic/terminology versions needed for replay.

**Determinism rule:** the same run inputs must reproduce the same semantic event sequence, patient-state digests, visible observation sequence, and assessment result. Unique run IDs, event UUIDs, export timestamps and wall-clock audit metadata may differ; they are excluded from the semantic replay digest but remain in the audit envelope.

Use an integer simulation clock (ticks or fixed-precision time units), never wall-clock time inside state transitions. If randomness is needed, use an explicitly named/versioned PRNG and record the seed and draw sequence or enough state to replay it. Scheduled-event ties require a stable ordering key, for example `(simulation_time, event_priority, insertion_sequence)`. Never depend on thread scheduling, system time, unordered iteration or network response order for a simulation outcome.

### 5.3 Run event catalogue additions

Add simulation event types to the existing event catalogue, subject to schema review. The initial candidate set is:

- `simulation.scenario.loaded`
- `simulation.run.started`
- `simulation.observation.released`
- `simulation.action.requested`
- `simulation.action.accepted`
- `simulation.action.rejected`
- `simulation.clock.advanced`
- `simulation.event.scheduled`
- `simulation.event.fired`
- `simulation.state.transitioned`
- `simulation.result.available`
- `simulation.document.saved`
- `simulation.order.entered`
- `simulation.handover.submitted`
- `simulation.assessment.derived`
- `simulation.debrief.completed`
- `simulation.run.completed`
- `simulation.run.abandoned`

Rejected actions and blocked transitions are retained as auditable events with reasons. They do not alter the simulated patient state. The state of a run is reconstructed by folding its canonical events; materialized tables are rebuildable projections.

### 5.4 Knowledge-state vocabulary

All observation and finding surfaces must distinguish at least:

- `present` / positive;
- `explicitly_absent` / negative;
- `unknown`;
- `conflicting`;
- `stale`;
- `not_applicable`;
- `not_yet_released`; and
- `source_feed_incomplete`.

An absent property in JSON is not a negative finding. A finding not yet released to the learner is not the same as an unavailable finding. A source feed that is known to be incomplete cannot satisfy a temporal absence check. PROforma, guards and ASP rules must preserve these distinctions.

## 6. Phased implementation roadmap

Each phase is independently useful and has a shippable acceptance boundary. Later phases may depend on prior outputs, but no phase requires a new deployable.

### Phase 0 — Discovery and capability inventory

**Status: completed against the supplied G archive.**

**Completed outputs:** code/module inventory in §3; existing route and UI seams; distinction between static cases, branching, encounter learning and actual physiology simulation; baseline test run (247 passed); list of missing capabilities.

**Remaining release housekeeping:** install frontend dependencies in a network-enabled target environment; run `npm ci`, TypeScript typecheck and production build; verify Windows install/upgrade. These do not block writing the roadmap, but they block a complete release qualification.

**Exit:** a reviewer can identify the implementation seam for every phase. This criterion is met at blueprint level.

### Phase 1 — Scenario as a first-class, data-driven object

**Goal:** replace case-specific implicit state with a validated, versioned scenario package while preserving existing curated cases.

**Reuse:** `puzzles.py`, `puzzle_engine.py`, `advanced.py` branching graphs, content review/source references, `ContentStudioPage.tsx`, PROforma model library, Kernel event catalogue.

**Build:**

1. Define and version a Scenario Package schema.
2. Add a loader/catalogue and structural/content validator inside the monolith.
3. Store source, reviewer, review date, licence, model and rubric versions.
4. Represent goals, trigger conditions, initial state, permitted disclosures, permitted actions and assessment criteria as data.
5. Migrate one existing curated puzzle or authored branching case as the reference package; do not silently reinterpret raw FHIR records as approved simulation scenarios.
6. Validate that every referenced PROforma model, transition model, asset and criterion exists.
7. Keep legacy case routes operational while the new scenario route is introduced.

**Independent value:** reproducible, versioned, reviewable case packages become reusable across Clinic, Ward, Lab and Exam Hall, even before physiology simulation is added.

**Acceptance:** valid reference scenario loads; missing model, invalid action, missing provenance, expired review or unsupported schema version is rejected with an actionable error; scenario digest is stable; old case workflows still pass.

### Phase 2 — Learner observation surface

**Goal:** show only what a clinician learner should see, without exposing internal simulation state.

**Reuse:** FHIR encounter narratives and facts, `clinical_narrative.py`, Pulse bridge and `PulsePanel.tsx`, Composer, existing Clinic/Lab skins and the six-skin registry.

**Build:**

1. Create a read-only Observation Projection API over the scenario/run state.
2. Present presenting complaint, history, examination, vital signs, available results and chart context.
3. Separate source facts, simulated findings, derived teaching annotations and unavailable/unknown information.
4. Apply a staged disclosure policy so scenario authors can control what is revealed at each point.
5. Use terminology-coded observations and explicit units where available; validate units before comparisons.
6. Ensure hidden scenario goals, latent state variables and answer keys are never returned in learner payloads.

**Independent value:** learners can work through structured cases using a clinician-facing display, even before intervention effects are implemented.

**Acceptance:** a clinician unfamiliar with the code can summarize the disclosed state from the learner view alone; no hidden fields leak; unknown is not shown as normal; exact same run state produces the same observation projection.

### Phase 3 — Learner actions, simulation clock and patient consequences

**Goal:** create the first genuine interactive simulation loop.

**Reuse:** PROforma `action` tasks and guards, Pulse `step/getState/applyAction`, Kernel event ledger, existing event monitors, Reasoner/SMT/ASP where explicitly required.

**Build:**

1. Add one in-process Simulation Runtime implementing a discrete-event clock and deterministic state transitions.
2. Define a small, typed action catalogue: for example assessment, investigation order, treatment action, escalation/consultation and communication. The exact actions and payloads must be selected and reviewed for the reference scenario.
3. Route all learner actions through PROforma task availability, schema validation, write-boundary guards and Pulse `applyAction`.
4. Record requested, accepted and rejected actions in the canonical event log.
5. Advance simulated time only through explicit learner or scenario clock events.
6. Schedule delayed effects and investigation results using a stable priority queue and stable tie-break rules.
7. Return every visible vital/result change through Pulse; do not let the UI alter physiology directly.
8. Record the source/version of each state transition and expose its derivation in the debugger/debrief.
9. Start with one bounded clinical scenario and only the state variables needed for its learning objectives.

**Independent value:** the first end-to-end interactive simulation becomes usable for deliberate practice.

**Acceptance:** same scenario digest + engine/model versions + seed + action sequence reproduces identical semantic trace and state digests; invalid actions do not mutate state; delayed results appear only after their simulated time; missing/unknown state remains unknown; every visible change has a traceable event and model explanation; fault-injection tests cover duplicate, late, malformed and out-of-order actions.

**Important design restriction:** do not attempt to build a universal human physiology model in this phase. Build one clinically reviewed, bounded simulation slice. Expand only when validation justifies it.

### Phase 4 — Documentation practice

**Goal:** make learner documentation part of the simulation run.

**Reuse:** LearningEpisode and artifact APIs, existing case-learning attempt fields, `note_engine.py`, Composer/templates, source references and event Kernel.

**Build:**

- In-run notes with a structured minimum dataset plus free text.
- Orders linked to the learner's action and resulting simulated event/result.
- Handover artifact with situation, background, assessment, recommendation and outstanding tasks, or another institution-approved format.
- Draft/final states, timestamps in simulation time, author identity, and immutable document versions.
- Link every document to the run and relevant findings/actions.
- Keep automated prose grading off initially. Assess structured completeness and consistency only where criteria are explicit.

**Independent value:** learners practise record keeping and handover in context, not as disconnected exercises.

**Acceptance:** completed run contains readable, versioned notes/orders/handover; replay restores the correct document versions; edited drafts do not overwrite prior submitted artifacts; document claims can be traced to observed facts, learner interpretation or explicit unknowns.

### Phase 5 — Trace-based formative assessment

**Goal:** derive a transparent score and criterion-level feedback from the deterministic run trace.

**Reuse:** `assessment.py`, `exams.py`, OSCE rubric/checklist support, PROforma arguments, Guards, Explain, existing review governance.

**Build:**

1. Create a versioned assessment rubric attached to each scenario package.
2. Score observable criteria such as required action, ordering, timing, reassessment, contraindicated action, omissions, escalation and documentation completeness.
3. Support multiple defensible sequences; do not compare every learner only against one hidden gold path.
4. Distinguish process, reasoning, patient-state outcome, documentation and communication dimensions.
5. Link each score item to event IDs, criterion text, rubric version and derivation.
6. Record critical errors separately and explain the educational significance; do not silently bury them in an aggregate percentage.
7. Keep human-reviewed rubric criteria and clinically authored reference traces versioned.
8. Mark results **formative** until reliability, validity, fairness and intended-use requirements are demonstrated.

**Independent value:** each practice run produces an itemized, auditable learning result without claiming professional competence.

**Acceptance:** known strong, partial and poor synthetic traces produce expected criterion breakdowns; every point and deduction is reproducible; ambiguous/unsupported criteria abstain or route to educator review; equivalent defensible paths are not unfairly penalized; scoring does not change when the display skin changes.

**High-stakes boundary:** the existing `formal_assessment` feature policy is hard-blocked because the local-first boundary is not a trusted examination environment. This roadmap does not remove that block. A future high-stakes assessment proposal requires a separate security, identity, invigilation, psychometric and regulatory review.

### Phase 6 — Debrief and replay

**Goal:** reconstruct the run, patient response, learner decisions, documentation and assessment as one timeline.

**Reuse:** Kernel replay, replay-diff, Explain derivation envelope, `simulation.py` PEARLS prompts, Case Debriefs UI, PROforma debugger and argumentation graph.

**Build:**

- A synchronized timeline of observations, actions, clock advances, scheduled events, results, documents and state transitions.
- Replay from the canonical event log, with playback speed and event-by-event inspection.
- Side-by-side comparison with one or more educator-reviewed reference pathways, including alternative defensible paths.
- Explanations of why an action was available/blocked, what consequences followed, and which prerequisites were not met.
- Counterfactual replay in a forked, read-only simulation branch; never mutate the original run.
- PEARLS reflection tied to concrete timeline events and learning goals.
- A stable replay diff comparing expected and actual state, trace and score digests.

**Independent value:** learners and instructors can understand not only the final result but the sequence that produced it.

**Acceptance:** replay reproduces the same semantic state and score at every checkpoint; the original run remains immutable; debrief feedback cites actual event IDs; forks are clearly labeled as counterfactual and cannot be confused with the original run.

### Phase 7 — Authoring and curriculum

**Goal:** allow qualified non-developers to create, validate, review and sequence scenarios.

**Reuse:** Content Studio, content review, generation/distribution pipeline, PROforma workbench/debugger, scenario catalogue and Router.

**Build:**

- A visual scenario editor for baseline state, triggers, observations, action catalogue, goals, rubrics and debriefs.
- PROforma model linking and visual debugging rather than a second executable authoring language.
- Static validation: schema, references, action payloads, terminology, source/licence metadata and model compatibility.
- Dynamic validation: all reachable paths, dead ends, unhandled actions, impossible goals, time-order contradictions and fail-closed behaviour.
- Deterministic scenario test harness with good/partial/poor traces and seeded variant coverage.
- Clinical/content review workflow with reviewer identity, review date, evidence references and approval status.
- Curriculum manifests with learning objectives, prerequisites and route eligibility using the existing Router.
- Versioned release and rollback of scenario packages.

**Independent value:** educators can safely maintain a growing case library without asking developers to edit code for every scenario.

**Acceptance:** a domain expert can author a bounded scenario, run automated validation, resolve errors, submit it for review, and publish a version that can be replayed and assessed. No unreviewed scenario can enter the learner catalogue.

### Phase 8 — Cohorts, facilitation and progress

**Goal:** support instructor-led groups, team cases and cohort-level learning analytics.

**Prerequisites:** authentication, role-based authorization, data isolation, consent, retention, backup/recovery, audit access policy and an agreed deployment model.

**Reuse:** local episode/progress records, assessment artifacts, event Kernel, six skins and portability export. Extend them rather than creating a separate LMS.

**Build:**

- Instructor, learner, observer and assessor roles.
- Cohort and session manifests with scenario/version lock.
- Facilitator controls for start, pause, clock advance, reveal, debrief and session close.
- Individual and team action attribution.
- Shared case state with explicit turn/role controls and conflict prevention.
- Per-learner progress views with clear privacy and retention controls.
- Cohort summaries that distinguish participation from measured performance.
- Optional xAPI/cmi5/LTI adapters only after the local workflow is stable.

**Independent value:** instructors can run structured teaching sessions and review group performance.

**Acceptance:** an instructor can create a session, assign learners/roles, run a shared case, review individual contributions and criterion-level formative outcomes, and export a privacy-reviewed report. If the deployment is local single-user only, this phase remains deferred rather than weakening privacy/security.

## 7. Cross-cutting upgrades integrated into the phases

These research-driven upgrades strengthen the simulation roadmap. They are not independent services.

| Upgrade | Where it belongs | Required change |
|---|---|---|
| Proof-carrying outputs | Phases 3, 5 and 6 | Each important action/consequence/score carries source events, model/rubric versions, argument profile, uncertainty and replay digest. |
| Open-world and temporal safety | Phases 1–3 | Preserve unknown, explicit negative, conflicting, stale, not-yet-released and incomplete-feed states. ASP temporal absence rules require evidence that the source window is complete. |
| Living evidence lifecycle | Phases 1, 7 | Track source versions, appraisal, review date and downstream scenario/rubric dependencies. New evidence flags affected content for human review; it never silently changes a live scenario. |
| Process conformance | Phases 5–6, later analytics | Compare the actual action/event trace with reviewed PROforma pathways; identify missing, repeated, delayed and out-of-order steps without assuming there is only one defensible path. |
| Clinical terminology | Phases 1–3 | Bind scenario observations/actions to versioned SNOMED CT, LOINC and UCUM concepts when appropriate; validate units and relationships. Keep the embedded index as default and external terminology as an optional port. |
| Adaptive learning calibration | Phase 8 and later | Validate IRT parameters against suitable assessment data; use the reference FSRS algorithm/version for review scheduling; keep probability calibration (such as Brier) separate from argument force, evidence certainty and clinical outcome. |
| Safety case and hazard traceability | All phases; gate Phase 3 pilot | Link hazards → safety requirements → PROforma/Guard controls → tests/replay evidence → residual risk and named approval. |
| Security and privacy | Before Phase 8; baseline from Phase 1 | Add identity/authorization, learner-data minimization, protected audit checkpoints, encrypted backup and access reviews according to deployment risk. |
| Standards interoperability | Phase 8 or explicit institutional requirement | Keep FHIR/CDS Hooks/SMART/xAPI/cmi5/LTI behind typed adapters. Do not let external notifications bypass source validation, deduplication and canonical event recording. |

## 8. Assessment and teaching validation strategy

Passing software tests is necessary but not sufficient. HSPTL must prove three different things:

1. **Software correctness:** identical controlled inputs reproduce identical semantic traces and scores; malformed or unsupported actions fail closed.
2. **Simulation/model adequacy:** the bounded state-transition model behaves as intended for its declared educational scope, with documented assumptions, limitations, expert review and regression scenarios.
3. **Educational usefulness:** learners can use the observation/action/documentation workflow; debrief feedback is understandable and judged clinically sound; learning outcomes are measured rather than inferred from activity counts.

### 8.1 Technical validation

- Schema validation and contract tests for every scenario package.
- Golden run corpus with fixed scenario/model/logic versions, seeds and action sequences.
- Replay-diff over every event, state digest, observation projection and score item.
- Fault injection for duplicate actions, invalid payloads, clock jumps, delayed/late events, incomplete source feeds, rejected writes and unavailable solvers.
- Metamorphic tests: equivalent defensible action sequences; no action after terminal state; hidden facts never leak before release; display skin changes do not change semantics.
- Migration tests for legacy case/exam/debrief data and rollback safety.
- Frontend typecheck, production build, browser-level workflows and accessibility checks.

### 8.2 Clinical and scenario validation

For every scenario and transition model:

- named clinical reviewer and intended learner level;
- source and licence review;
- explicit model scope and assumptions;
- reviewed expected state changes and time windows;
- known strong, partial, unsafe and ambiguous traces;
- alternative defensible routes;
- uncertainty and abstention examples;
- periodic review trigger and retirement policy.

The first pilot must use synthetic/curated teaching data and a bounded scenario. It must not imply that the simulation predicts real-patient responses.

### 8.3 Educational validation

Measure:

- completion and abandonment;
- ability to identify key findings and missing information;
- quality of action selection, timing and reassessment;
- documentation and handover completeness;
- learner understanding of consequences and uncertainty;
- pre/post learning objectives;
- delayed retention and transfer to a new case; and
- learner/instructor usefulness and cognitive burden.

Do not equate time spent, number of clicks, self-reported confidence, or completion with clinical competence. Psychometric calibration requires suitable sample size, item/rater analysis, subgroup fairness review and independent educational evaluation.

## 9. Release packaging and independent milestones

A practical release grouping is:

| Release grouping | Included phases | Shippable value |
|---|---|---|
| 4.0.1 — Blueprint and scenario foundation | Phase 0 complete; Phase 1 | Verified module map, scenario schema/catalogue, first migrated case package, validation and versioning. |
| 4.1 — Learner patient view | Phase 2 | Read-only, staged, source-aware observations over scenario data. |
| 4.2 — Interactive simulation slice | Phase 3 | One bounded seeded simulation with typed actions, fixed clock, Pulse output and replayable run trace. |
| 4.3 — Practice, assessment and debrief | Phases 4–6 | Notes/orders/handover, transparent formative scoring, synchronized replay and PEARLS debrief. |
| 4.4 — Educator authoring and curriculum | Phase 7 | Scenario authoring, validation, review, release and curriculum sequences. |
| 5.0 — Facilitated institutional learning | Phase 8 plus governance | Cohort/team sessions, instructor controls, access governance and optional institutional adapters. |

Each release remains one deployable modular monolith and one web application. These are roadmap groupings, not claims that the features are already present.

## 10. Pilot definition

The first complete pilot should be deliberately small:

- one synthetic, clinically reviewed scenario;
- one initial patient state and a small number of scheduled events;
- one learner observation surface;
- a small, approved action catalogue;
- a fixed simulation clock and seeded deterministic runtime;
- at least one delayed investigation/result path;
- one structured note and one handover artifact;
- a versioned, itemized formative rubric;
- one reference pathway plus at least one alternative defensible path;
- full event replay and debrief; and
- one educator review of the scenario, simulation behavior, rubric and feedback.

The pilot is accepted only if the same run inputs reproduce the same semantic trace and score, no hidden information leaks, all patient-state changes are explainable, unsupported inputs abstain safely, and educators judge the scenario and debrief sound for the stated educational objectives.

## 11. Decisions to confirm before implementation beyond Phase 1

The code inspection resolves the technical baseline, but several product choices remain open. The roadmap assumes the lowest-risk default until these are decided:

1. **Learner audience:** medical students, postgraduates, practising clinicians, or multiple levels with separate objectives and scoring anchors.
2. **Initial specialty/scenario:** choose one clinically reviewed, bounded case based on available expertise and teaching priority.
3. **Simulation scope:** which state variables and actions are necessary for that case; explicitly avoid universal physiology ambitions.
4. **Deployment:** local/offline single-user first, or hosted multi-user from the outset. Hosted/cohort use changes identity, privacy and operations requirements.
5. **Data policy:** synthetic-only for the initial simulator, or whether any imported records can be transformed into approved de-identified teaching cases under a separate review process.
6. **Assessment stakes:** formative practice only for the initial release. Any summative/high-stakes use requires a distinct program and assurance boundary.
7. **Facilitation:** self-directed practice first or instructor-led sessions as an early pilot requirement.

## 12. Final architecture decision

**Build a clinical learning simulation layer, not a second HSPTL.**

Reuse the existing case engine, learner episodes, exam/OSCE repositories, PEARLS debrief, content studio, PROforma runtime, Pulse bridge, event Kernel, explanation engine and six skins. Add only the missing in-process Scenario Catalog and bounded Simulation Runtime, then connect documentation, assessment and replay through the existing run/event/artifact boundaries.

The first proof of value is not a large scenario catalogue or a sophisticated dashboard. It is one safe, reproducible, clinically reviewed case in which a learner can observe, act, see consequences, document, receive transparent feedback and replay the entire experience.

That is the smallest credible step from a hospital-style clinical learning workspace to a platform that teaches clinical decisions measurably.
