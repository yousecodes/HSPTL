# HSPTL 4.0 D–G deliverables

This release retains the eight minimal artifacts requested in sections D–F and adds the argumentation/SMT/ASP reasoning increment G. They are library files and in-process modules under the existing FastAPI/SQLite/React deployment. No QA service, model service, broker, terminology service, or separate plugin host is introduced.

| # | Deliverable | Implementation |
|---|---|---|
| 1 | Event schema and catalogue | `event_contracts.py`, `01_EVENT_SCHEMA_AND_CATALOG.md`, `event_catalogue.json` |
| 2 | PROforma model library, visual notation, one debugger | `hsp_tl40/models/`, `02_PROFORMA_MODEL_LIBRARY.md`, `debugger.py`, `POST /api/v4/logic/debug` |
| 3 | Pulse bridge specification and vital-renderer inventory | `03_PULSE_BRIDGE_SPEC.md`, `pulse_renderer_inventory.json`, `PulsePanel.tsx` |
| 4 | Skin specification template | `04_SKIN_SPEC_TEMPLATE.md`, `skin_config.schema.json`, `plugins.py`, `skinRegistry.ts` |
| 5 | Guard matrix and fault injection | `05_GUARD_MATRIX_AND_FAULT_INJECTION.md`, `guard_matrix.json`, `tests/test_hsptl40_d_to_f.py` |
| 6 | Explanation service contract and derivation renderer | `06_EXPLANATION_CONTRACT.md`, `explain.py`, `debugger.py` |
| 7 | Golden corpus and replay-diff harness | `fixtures/golden_corpus/`, `golden.py`, `scripts/replay_diff.py` |
| 8 | Terminology, standards and interop port interfaces | `08_PORT_INTERFACES.md`, `ports.py`, `terminology_port.py`, `standards.py` |

## Boundary rule

External datasets are fixtures or reference inputs, not a production runtime dependency. The exception is the specifically requested SNOMED CT terminology index: its importer is opt-in, local-file-only, requires explicit entitlement confirmation, and logs release provenance. PheKB and competency framework imports normalize supplied source content into fixture/reference-graph objects; they do not create learner state or clinical assertions.

## Verification status

The regression tests cover the write gate, prevented-write audit events, event monitors, PROforma debugger, generic PheKB fixture conversion, source-attributed PheKB Type 2 Diabetes EHR+ case/control logic (with synthetic inputs), CaSS/MedBiquitous graph normalization, RF2 indexing with an explicit synthetic test release, provability classification, skin configuration schema and replay-diff. Passing these tests verifies this bounded implementation; it does not certify PROforma conformance, GRADE calibration, SNOMED CT licensing, clinical safety, LTI launch security, or any external system integration.

## G — intelligence through existing primitives

| Capability | In-process implementation / data |
|---|---|
| PROforma argumentation | `argumentation.py`; `models/pathways/reasoned_choice.json`; enactment UI shows support/opposition/net force and asks the user to confirm |
| PROforma-to-CNF / embedded SMT | `embedded_smt.py`; the same PROforma expression tree; per-rule `provability.py`; optional `z3-solver` library |
| Temporal ASP | `temporal_reasoning.py`; versioned `asp_rules/pathway_temporal_v1.lp`; optional `clingo` library; canonical event-log projection |
| Unified derivation | `explain.py`; one trace with clinical, pedagogical and negative renderer lenses |
| Reasoned adaptivity | `router.py`; IRT, FSRS, prerequisites and Brier arguments on all candidate learning objects |
| Pulse-to-event path | `pulse.py`; connected snapshots append `platform.pulse.observation_recorded` events for temporal projections |

Both solver libraries are imported in-process and are fail-closed when unavailable. `z3-solver` and `clingo` are declared in `requirements.txt`; the build environment used for this release did not have network access to install them, so positive solver execution and live Clingo grounding are not claimed as locally verified. No new deployable service, process worker, broker, or external model is added.


## 4.0.2 learner/curriculum lifecycle additions

- Learning Library opens and formative quiz attempts are canonical Kernel events with pack/curriculum version identity and idempotent quiz retries.
- Topic and objective progress are event-derived views.
- Curriculum composition reuses the existing topological router and PROforma predicate evaluator; activation is reviewer-gated.
- Scenario authoring stores immutable local draft versions, validates references to the existing PROforma model library and publishes only through a separately configured clinical-review credential.
