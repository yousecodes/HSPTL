# HSPTL Clinical Simulation — First Vertical Slice

**Scenario:** Acute breathlessness: moderate asthma exacerbation  
**Scenario ID:** `asthma-moderate-adult-001`  
**Scenario package:** `fixtures/scenarios/asthma-moderate-adult-001/scenario.json`  
**Runtime:** `backend/hsptl_core/hsp_tl40/clinical_simulation.py`  
**Client:** `frontend/src/pages/ClinicalSimulationPage.tsx`  
**Status:** Implemented as a bounded, formative, synthetic teaching slice; clinical educator review pending.

## What the learner can do

1. Start a run with a deterministic 32-bit seed.
2. See the synthetic presenting complaint, opening history and arrival observations. Peak expiratory flow is not displayed until the investigation result is released.
3. Complete the focused assessment to reveal the authored focused history and examination.
4. Request peak expiratory flow. Its result is released at T+2 simulated minutes.
5. Record a scenario bronchodilator action and a systemic-treatment-plan action through the simulation's Pulse provider. The model does not specify drug doses.
6. Advance the integer simulation clock. A deterministic response event is scheduled 20 simulated minutes after the bronchodilator action; an untreated-worsening branch is scheduled at T+30 if the bronchodilator action has not been accepted.
7. Reassess at or after T+60.
8. Save structured clinical-note and handover versions. These are append-only events; prose is not automatically graded.
9. Derive an itemized formative trace score, inspect its supporting event IDs and derivation, replay the run, and complete/seal it.

## Module boundaries

- **Scenario data:** JSON fixture containing case, learning objectives, staged disclosures, typed actions, scheduled events, transition-model metadata, rubric and debrief prompts. It contains no executable code.
- **Simulation Runtime:** in-process module. It applies typed, authored transitions and reconstructs run state by folding `simulation.*` events from the canonical Kernel. It does not own a second run database.
- **PROforma:** each learner action is gated by a versioned PROforma plan and enacted using the existing PROforma runtime. No second rule language is introduced.
- **Pulse:** each run exposes a scoped Pulse provider. Learner actions pass through `PulseBridge.applyAction`; snapshot reads pass through `PulseBridge.step`.
- **Kernel:** run creation, observations, action requests/acceptance/rejection, clock advances, scheduled events, state transitions, result availability, documents, assessment and completion are event records.
- **Client:** the existing React application, Clinic workspace, and `case-reasoning` skin module expose the Simulation Lab. No second application is created.

## API surface

All endpoints are under `/api/v4`:

| Method | Route | Purpose |
|---|---|---|
| GET | `/simulation/scenarios` | List public scenario summaries |
| GET | `/simulation/scenarios/{scenario_id}` | Read a scenario summary |
| POST | `/simulation/runs` | Start a seeded run |
| GET | `/simulation/runs/{run_id}` | Read the learner projection and current eligible actions |
| POST | `/simulation/runs/{run_id}/pulse/step` | Read and record a Pulse snapshot |
| POST | `/simulation/runs/{run_id}/actions` | Apply `{ "action": { "id": "..." } }` through Pulse and PROforma |
| POST | `/simulation/runs/{run_id}/advance` | Advance the integer clock by 1–60 minutes |
| POST | `/simulation/runs/{run_id}/documents` | Append a clinical-note or handover version |
| POST | `/simulation/runs/{run_id}/assessment` | Derive formative assessment from the event trace |
| GET | `/simulation/runs/{run_id}/replay` | Return event timeline and semantic/state digests |
| POST | `/simulation/runs/{run_id}/complete` | Seal a run after assessment |

A completed run rejects further mutations. Invalid actions are recorded as rejected events and do not transition patient state. Lifecycle conflicts return HTTP 409; malformed inputs return HTTP 422.

## Determinism contract

The run records scenario digest, transition-model ID/version, engine version, PROforma logic version, seed algorithm and seed. The first scenario's seed variation currently chooses one of three initial heart-rate values; the rest of its scenario behavior is a fixed, versioned transition sequence.

The simulation clock uses integer minutes. Scheduled events are ordered by due minute, priority and stable event ID. A scheduled result or transition is processed at its authored simulation minute, not merely at the end of a large time advance.

For the same scenario package, model versions, seed and ordered learner action/document sequence, the runtime is tested to reproduce the same semantic trace digest, final state digest and formative score. Run/event UUIDs and wall-clock audit timestamps are excluded from the semantic digest but remain in the audit ledger.

## Formative assessment

The versioned rubric has seven items (100 points maximum): focused assessment (10), objective lung-function result (15), initial bronchodilator action (20), systemic-treatment-plan action (15), post-response reassessment (20), structured note completeness (10), and structured handover completeness (10).

The objective lung-function criterion distinguishes an order request from an available result: full points require the PEF result event to precede the bronchodilator action; a result available afterward receives partial points. The rubric also checks whether the bronchodilator action precedes the authored T+30 deterioration checkpoint.

The assessment is a formative process trace only. It does not grade clinical prose, establish diagnosis correctness, claim clinical competence, or certify readiness for practice. The rubric must be reviewed and approved by qualified clinical educators before wider use.

## Clinical and model boundary

The case is synthetic and is loosely informed by GINA 2026 adult acute-asthma assessment and reassessment guidance. The authored values and response transitions are pedagogical fixtures, not empirically calibrated patient physiology. In particular, the post-bronchodilator vital-sign/PEF changes and untreated-worsening transition are deterministic teaching transitions, not predictions of an actual patient's response.

No drug dose, route-specific prescription, oxygen titration, or treatment recommendation for a real patient is encoded. A qualified clinical educator must review the scenario, action catalogue, assessment rubric, debrief prompts, source mapping and local-protocol fit before learner deployment. It is not for live patient care or clinical decision support.

Sources recorded in the scenario package:

- Global Initiative for Asthma (GINA), *Global Strategy for Asthma Management and Prevention, 2026*: <https://ginasthma.org/wp-content/uploads/2026/05/GINA-2026-Strategy-Report-WMS.pdf>
- GINA, *Summary Guide for Asthma Management and Prevention, 2026*: <https://ginasthma.org/wp-content/uploads/2026/07/GINA-Summary-Guide-2026-WEB-WMS.pdf>

## Verification

Focused and API-level tests cover scenario validation, disclosure boundaries, PROforma action eligibility, blocked-action audit, timed PEF result, deterministic treatment-response and deterioration branches, Pulse bridge reads/actions, append-only note/handover versions, score provenance, replay digests, same-seed reproducibility, completed-run immutability and a full HTTP workflow.

Run from the repository root:

```powershell
$env:PYTHONPATH = "."
python -m pytest -q
```

Frontend source syntax was transpiled with TypeScript. Full dependency-backed `npm run typecheck` and `npm run build` still require installing the pinned frontend dependencies in a network-enabled environment.

## Roadmap status after this slice

- **Phase 0 — Discovery:** completed against the supplied source archive.
- **Phase 1 — Scenario object:** implemented for one versioned reference scenario; no general educator authoring UI yet.
- **Phase 2 — Observation surface:** implemented for the reference scenario, including staged disclosure and hidden internal state.
- **Phase 3 — Actions, time and response:** implemented for the bounded asthma teaching model; not a general physiological simulator.
- **Phase 4 — Documentation:** structured note and handover capture implemented; no full order-entry/documentation catalogue yet.
- **Phase 5 — Assessment:** one transparent formative trace rubric implemented; clinical and psychometric validation pending.
- **Phase 6 — Debrief and replay:** event replay, timeline, digests, assessment rationale and reflection prompts implemented; instructor-authored feedback and multi-branch replay remain future work.
- **Phase 7 — Authoring and curriculum:** not implemented.
- **Phase 8 — Cohorts and facilitation:** not implemented; requires identity, privacy and deployment decisions.
