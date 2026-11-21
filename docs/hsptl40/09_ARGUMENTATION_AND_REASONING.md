# 9. Argumentation, symbolic consistency and temporal reasoning (G)

## Non-negotiable boundary

G does not add an independently deployable service. The existing PROforma runtime calls embedded libraries and reads versioned data. The canonical append-only event log remains the source for replay; the Pulse bridge remains the only physiological interface; the existing router remains the only sequencing surface.

## 1. PROforma weighted argumentation

A decision option may contain `arguments[]` entries with:

- `id`: stable argument identity;
- `polarity`: `for` or `against`;
- `weight`: finite, non-negative additive force;
- `when`: an ordinary PROforma expression (default `true`);
- `status`: `pass` or `abstain` (an abstaining argument contributes no force);
- `label`, `reason`, `evidence`, `source_events`: display and provenance data.

For each option, the runtime calculates:

`support_force = Σ active for-argument weights`

`opposition_force = Σ active against-argument weights`

`net_force = support_force − opposition_force`

Preference order is deterministic: descending net force, descending support force, then candidate id. The force is an argument-balance aid, not a clinical conclusion or a calibrated probability. Every eligible candidate is presented; no candidate is automatically selected. Unknown option eligibility or argument conditions abstain rather than silently omitting uncertainty.

The enactment response includes the full argument graph and each option profile. The user confirms the actual selected option, which is recorded as a PROforma pathway step. The client renders support, opposition, net force, argument labels and whether evidence/source-event references exist.

## 2. Embedded SMT — PROforma to CNF

`embedded_smt.py` compiles the bounded PROforma expression tree to Tseitin CNF. It does not accept a second rule language. Z3 is imported in-process only for rule IDs classified `z3_required` by `provability.py`; all other or unregistered rule IDs abstain.

The adapter exposes three bounded operations:

1. **Argument consistency:** checks each argument condition with the shared symbolic constraints; returns a subset-minimal unsatisfiable core identifying inconsistent PROforma formula roots.
2. **Differential hypotheses:** checks each candidate hypothesis against explicit inquiry findings and returns consistent, rejected, or undecidable results.
3. **Single-finding counterfactual:** tests candidate finding conditions, applies the declared `context_patch` to a copy of the current facts, re-runs the same argumentation function and reports findings that reverse the preference set.

These operations are not a substitute for general SMT theory support. Unsupported operators, undeclared references, solver `unknown`, or missing Z3 lead to abstention. A reported preference reversal is only as trustworthy as the caller's explicit `context_patch` mapping from the proposed finding to PROforma facts.

## 3. Embedded ASP — temporal and event-derived state

`temporal_reasoning.py` invokes Clingo's Python API in-process. It projects canonical event-log records and the current PROforma plan into ASP facts. The rules live as versioned `.lp` data under `asp_rules/` with a JSON manifest.

The included ruleset:

- recognizes pathway active/completed/abstained and completed-task states;
- detects pathway steps that have no prior enactment;
- evaluates declared `requires_before` task prerequisites against ordered event sequence numbers;
- identifies missing/satisfied temporal prerequisites;
- combines explicitly reviewed, evidence-id-bearing clinical state assertions into support or conflict states.

Raw Pulse measurements are not converted into clinical states or thresholds by ASP. A provider may attach reviewed `clinical_state_evidence` to a canonical Pulse observation event. Those facts are subject-scoped; if no matching subject is provided, patient-scoped state evidence is not projected. Recognized states are available as `inferred.*` PROforma inquiry inputs. Deviations can be represented as arguments against a selected path; temporal prerequisites are hard routing gates. If Clingo is missing, returns no model, or cannot decide, routing abstains.

## 4. One derivation, three explanation lenses

The existing `derive()` envelope is the only trace shape. `render_explanation()` supports:

- `clinical`: PROforma arguments and their evidence/source-event chains;
- `pedagogical`: entailment, predicate traces and postcondition/task completion;
- `negative`: conflicts, failed guards, abstentions, deviations and unreached temporal states.

The view does not alter the derivation hash or underlying trace. The three endpoints are render modes of one derivation, not separate explanation engines.

## 5. Reasoned sequencing

`Router.reasoned_sequence()` evaluates each candidate learning object using the existing IRT estimate, FSRS due-state projection, hard prerequisite gate and Brier calibration summary. Each signal emits an individually identified argument attached to that candidate. Every routeable candidate receives a profile; missing prerequisites are reported as blocked rather than made routeable. The router returns the entire ranked set and a preferred set, but it does not auto-select.

Brier score is calculated only from explicit probability/outcome pairs. It is a calibration summary, not an assessment of clinical probability. FSRS output is a derived scheduling projection; no review date is stored as a computed fact.

## Interfaces

- `POST /api/v4/logic/smt/argument-consistency`
- `POST /api/v4/logic/smt/differentials`
- `POST /api/v4/logic/smt/counterfactual`
- `POST /api/v4/logic/temporal/analyze`
- `POST /api/v4/logic/explanations/render`
- `POST /api/v4/router/reasoned-sequence`

All are in-process routes in the existing app. They do not imply additional deployables.

## Verification boundary

Unit tests cover formula compilation, contradiction shape, provability gating, argument accumulation, abstention, all four router arguments, derivation view identity, subject scoping, and Pulse event logging. Z3 and Clingo are declared optional library dependencies, but the release build environment could not install either library because package-network access was unavailable. Successful positive solver execution and live ASP model grounding therefore remain unverified in this build environment. Missing libraries fail closed; they do not trigger approximations.
