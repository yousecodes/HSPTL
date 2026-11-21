# HSPTL 4.0 implementation addendum

The sections below preserve the original deterministic-intelligence design history. Where they describe PROforma, embeddings, or full event migration as future work, this 4.0 addendum is the current product status:

- HSPTL 4.0 now ships a bounded, safe PROforma execution subset used for pathway enactments and all new 4.0 preconditions, appraisal expressions, template preconditions and routing predicates. It is not full-language conformance.
- HSPTL 4.0 uses the same append-only `di_events` hash chain for new 4.0 platform events. All legacy HSPTL 3.0 persistence has **not** been migrated to event sourcing; its compatibility routes remain outside the universal 4.0 proof contract until individually migrated.
- UCKS vector retrieval and embedding-model routes are disabled in the model-free 4.0 product runtime. Lexical FTS5 remains enabled. Historical vector schema/data are inert.
- The finite positive ontology subset, optional Z3 conflict/safety checks, Pulse provider requirement, and external standards/interop port limits are detailed in [HSPTL 4.0 Architecture](HSPTL_4.0_ARCHITECTURE.md).

---

# HSPTL Deterministic Intelligence Architecture (No AI Models)

**Status:** additive implementation, architecture version `1.0.0`. No ML, neural network, LLM, embeddings, or probabilistic inference is used by this package. Existing UCKS retrieval/embedding facilities remain separate; this architecture does not treat similarity as clinical inference.

## 1. Canonical state and ontology

`backend/hsptl_core/deterministic_intelligence/ontology.py` is the versioned vocabulary. Classes include ClinicalEntity (Condition, Finding, Intervention, Investigation, Population, Outcome), EvidenceEntity (Guideline, Trial, SystematicReview, CaseReport), LearningObject (Recommendation), Competency, Appraisal, SourceSpan and ClinicalQuestion. Typed relationships include supports, derived_from, has_appraisal, has_source_span, assesses, requires_prerequisite, supersedes, contradicts and supports_learning_objective.

The implemented description-logic profile is deliberately bounded: named classes, multiple inheritance, transitive subclass closure, typed properties and explicit assertions. It is a finite positive taxonomy profile, **not full OWL-DL**. Existential/cardinality restrictions, negation, disjunction, universal restrictions, anonymous individuals and negative entailment are unsupported and must abstain. Absence of an assertion means unknown, not false. Full OWL-DL entailment is not claimed.

## 2. Canonical event log and projections

SQLite `di_events` is the append-only event ledger. UPDATE/DELETE triggers reject mutation. Each event has a monotonic sequence, unique ID, canonical JSON payload, UTC timestamp, previous hash and SHA-256 event hash. Current canonical tables are projections/materialized indexes. `POST /api/deterministic-intelligence/replay` rebuilds the projection from genesis (or a specified sequence), verifies every link and stores a projection hash. `GET /events` exposes the immutable stream. Event log corruption or a stale projection blocks canonical reads.

### Event catalogue

| Event | Preconditions | Guards | Projections |
|---|---|---|---|
| entity.registered | Known class, stable ID | G-ONTO-001, G-EVENT-001 | canonical_entities |
| evidence.registered | Source, hash, version, permitted rights | G-EVID-001, G-RIGHTS-001 | evidence_ledger |
| source_span.registered | Evidence exists; exact text offsets/hash | G-PROV-001 | source_spans |
| appraisal.recorded | Evidence exists; versioned table and derivation | G-APP-001 | appraisal_ledger |
| relationship.asserted | Typed endpoints, known predicate, provenance | G-ONTO-001, G-PROV-001 | knowledge_graph |
| learning_object.composed | Required slots and fully evidenced claims | G-LO-001, G-APP-001, G-RIGHTS-001, G-PROV-001 | learning_objects, derivation_index |
| competency.registered | Known prerequisites; acyclic graph | G-CURR-001 | competency graph |
| route.decided | Canonical object and all predicates true | G-ROUTE-001, G-STALE-001 | workspace_routes |
| guard.abstained | Guard failure/unknown | G-AUDIT-001 | guard audit |

A guard decision is persisted before the operation returns. Failure to persist the audit decision blocks the operation.

## 3. Rule inventory

| Rule | Version | Owner | Deterministic rule |
|---|---|---|---|
| APP-001 | 1.0.0 | Evidence Intelligence | Only current explicit `pass` appraisal can support clinical composition; fail/abstain blocks |
| RIGHTS-001 | 1.0.0 | UCKS | Explicit permitted rights and scope are required; unknown/restricted blocks |
| TEMPLATE-001 | 1.0.0 | Generation | Required slots must be canonical, class-compatible and provenance-linked |
| CURR-001 | 1.0.0 | Curriculum | Prerequisite graph is a DAG; eligibility is prerequisite set inclusion |
| ROUTE-001 | 1.0.0 | Distribution | All required workspace predicates must evaluate true |
| FRESH-001 | 1.0.0 | Workspace projections | Projection sequence must equal event-log head |

Rules are versioned data/specifications, not learned parameters. This initial package publishes the inventory; editable, authenticated rule-table administration and migration tooling remain follow-on work.

## 4. Guard matrix

| Guard | Boundary / schema poka-yoke | Formal property | Runtime monitor | Abstention/failure |
|---|---|---|---|---|
| G-EVENT-001 | Append-only triggers, unique IDs, hash fields | Strict sequence and hash linkage | Verify chain/head | Unknown event or chain mismatch |
| G-ONTO-001 | Ontology allow-lists and typed endpoints | Domain/range compatibility | Class/predicate validation | Unsupported constructor/class |
| G-EVID-001 | Required source/hash/version, unique evidence ID | Stable identity per version | Re-read evidence version | Missing identity |
| G-APP-001 | Decision CHECK and evidence/event FKs | No output from fail/abstain appraisal | Current appraisal lookup | Missing or non-pass appraisal |
| G-RIGHTS-001 | Rights decision/scope constrained | Requested use within permitted scope | Recheck at compose/route | Unknown/restricted/ambiguous |
| G-PROV-001 | Claim/source-span/evidence references | Every claim maps to exact source span | Verify text/hash/offset | Missing or mismatched span |
| G-LO-001 | Required slot and claim constraints | Emitted implies appraisal pass, rights permitted, span valid | Full object validation | Empty slot, missing proof, solver unavailable |
| G-CURR-001 | Prerequisite FK/unique edge | Prerequisite graph is DAG | Cycle check/topological sort | Cycle or unknown node |
| G-ROUTE-001 | Canonical object FK | All route predicates satisfied | Attribute re-evaluation | Missing/false predicate |
| G-STALE-001 | Projection sequence | Projection=head | Compare event head | Stale/missing projection |
| G-AUDIT-001 | Append-only guard records | Every failed/unknown guard audited | Durable audit write | Audit failure blocks |

### SMT status

An optional Z3 adapter proves three Boolean safety implications: emitted ⇒ appraisal_pass, emitted ⇒ rights_permitted, emitted ⇒ span_valid. If `z3-solver` is absent, returns `unknown`, or cannot prove a property, composition abstains. Z3 is not an AI model. **The solver is not bundled or installed by this change**, so clinical object composition through this new strict API remains fail-closed until the deployment installs and validates the solver. Other structural checks are deterministic runtime checks, not represented as SMT proofs.

## 5. Template schema

The declarative template `clinical-evidence-object@1.0.0` has required slots:

- `clinical_assertion`: LearningObject claim, with SourceSpan and EvidenceEntity references, current appraisal pass, permitted rights.
- `evidence_context`: canonical EvidenceEntity with appraisal derivation.
- `limitations`: SourceSpan or explicitly authored/reviewed limitation.

Validation requires all slots, canonical IDs, current pass appraisal, permitted operation rights, exact immutable source text/hash/offset, no unresolved conflict, and pinned template version. Any unfilled slot blocks emission. The existing extractive generator is retained for compatibility; it is not silently promoted to this stricter canonical workflow.

## 6. Curriculum constraint model

Variables: `position` (registered competency IDs), `eligible` (true/false/unknown), `workload` (non-negative integer), `coverage` (required competency domains). Domains are finite and explicit. Hard constraints: DAG prerequisites; prerequisites precede dependents; ineligible nodes cannot schedule; declared workload cap; mandatory coverage must be met. Unknown eligibility blocks. Default ordering is deterministic lexicographic Kahn topological sort; no score or optimization objective is enabled. A finite sequence/precedence model is used as the PROforma-equivalent task skeleton; full PROforma execution and CQL runtime compatibility are not claimed in this increment.

The predicate DSL supports equality, inequality, membership, set inclusion, existence and numeric comparisons. Missing values and unsupported operators return unknown. It never evaluates arbitrary code. FHIR mapping/CQL export and formal temporal-logic model checking remain future interoperability adapters.

## 7. Fault-injection test plan

| Guard | Forbidden input injection | Expected assertion |
|---|---|---|
| G-EVENT-001 | Duplicate entity/event ID; mutate/delete event | Reject; immutable event remains unchanged |
| G-ONTO-001 | Unknown class/predicate | Reject or abstain; no entity/edge persisted |
| G-EVID-001 | Empty source/hash/version | Reject; no evidence row |
| G-APP-001 | Appraisal missing/fail/abstain | Composition abstains; no learning object |
| G-RIGHTS-001 | Unknown/restricted rights | Abstain; no evidence reuse |
| G-PROV-001 | Wrong evidence, altered text, invalid offsets | Reject; no source span/claim |
| G-LO-001 | Missing slot/claim or unavailable solver | Abstain; no learning object |
| G-CURR-001 | Unknown prerequisite or cycle | Abstain/reject; no cyclic edge |
| G-ROUTE-001 | Missing or mismatched required attribute | Abstain/reject; no route |
| G-STALE-001 | Append event after projection | Stale read abstains until replay |
| G-AUDIT-001 | Force audit write failure | Operation blocked |

Executable tests are in `tests/test_deterministic_intelligence.py`. They exercise schema constraints, append-only behavior, provenance, appraisal, rights, solver-unavailable abstention, prerequisite cycles, route predicates, replay and hash verification.

## 8. Replay and output trace

1. Start at sequence 1 and genesis hash of 64 zeroes.
2. Verify each event's previous hash and recomputed SHA-256 before applying it.
3. Apply events in sequence to fresh in-memory canonical maps; never use current projections as replay input.
4. Rebuild evidence, source spans, appraisals, relationships, learning objects, competencies and routes.
5. Hash the canonical serialization and persist projection sequence/hash.
6. For an output, follow `learning_object.composed` → derivation payload → claim evidence ID → appraisal event and decision table/version → source-span event/text/hash/offset → evidence registration/source ID/version/rights → original source record.
7. Re-run the same event prefix and pinned rule/template versions to reproduce the derivation. A changed source version creates a new evidence identity/version and requires a new appraisal and artifact.

## 9. API surface

Prefix: `/api/deterministic-intelligence`

- `GET /specification`, `GET /status`, `GET /events`
- `POST /replay`
- `POST /entities`, `/evidence`, `/source-spans`, `/appraisals`, `/relationships`
- `POST /learning-objects`, `/competencies`, `/routes`
- `GET /curriculum/order`, `GET /competencies/{id}/eligibility`

HTTP 409 with `state=abstain` represents a first-class abstention. It is not a successful empty result.

## 10. Known implementation boundaries

This increment establishes an append-only canonical event subsystem and API, but does not yet migrate every legacy HSPTL table into this event stream. Legacy generation/distribution routes remain for compatibility and must not be interpreted as satisfying the new canonical proof contract. The new strict composition path requires canonical evidence registration, appraisal, exact source spans and a working Z3 installation. Full OWL-DL, a complete CQL interpreter, PROforma runtime, institutional/user policy inheritance, and all-workspace stale-read middleware are not claimed as complete. The system abstains at the new API boundaries where it cannot establish required guarantees.
