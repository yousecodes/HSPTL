# 5. Four-layer guard matrix and fault injection

There is no separate QA service. The checks execute in the core write path, rule runtime, and replay path.

## Four layers

1. **Write-boundary poka-yoke:** event type allow-list; required-field schema; JSON canonicalization; payload size cap; per-skin config schema; typed preconditions at existing repositories.
2. **Per-rule provability:** every HSPTL 4.0 rule is registered as `closed_form`, `proforma`, or `z3_required`. Unregistered rules abstain. Z3 is not a fallback for a PROforma rule.
3. **Runtime event monitors:** pre-append checks enforce event/status pairing, route eligibility, assertion lineage completeness and presentation-only skin config.
4. **Immutable audit/replay:** SQLite prevents update/delete of ledger rows; SHA-256 links each row to its predecessor; refused writes are logged as `platform.write.prevented`; replay verifies the chain and recomputes the canonical projection.

## Provability classification

The authoritative registry is `provability.py`; `GET /api/v4/guards/catalogue` exposes the matrix and per-rule classification.

| Class | Evaluation path | Z3 allowed? |
|---|---|---:|
| `closed_form` | Direct finite identity, presence, allow-list or lineage checks | No |
| `proforma` | Bounded PROforma three-valued evaluator | No |
| `z3_required` | Small declared-variable SMT adapter or the scoped evidence-conflict checker | Yes, only here |
| `unclassified` | Immediate abstention and guard audit | No |

The Z3 adapter compiles a constrained subset of the same PROforma expression tree (`ref`, Boolean connectives and comparisons) over explicitly declared symbolic references. It does not introduce a second decision language. Unsatisfiable assumptions, solver absence, unsupported PROforma operators or an indeterminate result abstain. It does not run arbitrary user code.

## Fault-injection cases

The `tests/test_hsptl40_d_to_f.py` suite intentionally attempts malformed and inconsistent writes:

| Fault | Expected behavior | Evidence |
|---|---|---|
| Unknown event type | Reject; append `platform.write.prevented` | Audit payload digest and layer `write_boundary` |
| Missing required payload key | Reject before target event append | Prevented event |
| Guard decision `abstain` emitted as `checked` | Reject at schema boundary | Prevented event |
| Abstaining pathway emitted as `stepped` | Reject at runtime monitor | `M-PROFORMA-ABSTAIN-001` |
| Route emitted with eligibility not `pass` | Reject at runtime monitor | `M-ROUTE-ELIGIBILITY-001` |
| Assertion has incomplete source event derivation | Reject at runtime monitor | `M-LINEAGE-001/002` |
| Skin config contains a clinical-fact key | Reject at registry/write monitor | `M-SKIN-FACT-001` |
| Event row altered in SQLite | Replay hash check fails | `G-EVENT-001` |
| Unknown rule id | Abstain; no solver | Provability trace says `unclassified` |
| PROforma-classified rule | Run PROforma, not Z3 | Provability trace says `proforma` |
| Z3-required rule with solver absent/unknown | Abstain | Z3 decision trace |

The fault-injection tests verify system behavior; they are not evidence of clinical safety certification.
