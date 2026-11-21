# 6. Explanation service contract and derivation renderer

The explanation module is a pure in-process derivation function, not a network service. `derive()` returns `hsptl.derivation/1.0`.

## Derivation envelope

| Field | Meaning |
|---|---|
| `output_type`, `output` | Exact derived output or decision |
| `rules` | Stable rule/model identifiers |
| `inputs` | Input identifiers and non-sensitive relevant values |
| `steps` | Ordered proof/evaluation/appraisal steps |
| `source_events` | Canonical event IDs/sequences for event-backed evidence |
| `derivation_hash` | SHA-256 of canonical output type/output/rules/inputs/steps/source-events |
| `created_at` | Display metadata; excluded from derivation hash |
| `replayable` | True only when source references and rule trace are retained |

## Clinical assertion lineage

The minimum lineage path is:

`assertion → evidence entity → appraisal → source event → source span`

Assertion emission requires all of the following: registered evidence; an explicit appraisal `pass`; permitted rights for the intended use; a source span linked to the same evidence; exact content-hash match; and replayable source-event references. Missing or stale lineage prevents emission. A derivation digest is not a substitute for the source evidence or reviewer appraisal.

## Renderer contract

One renderer projects the same derivation envelope into three audience views: `clinical` (argument polarity/weight plus evidence and source-event chains), `pedagogical` (entailment, predicate evaluation and postcondition satisfaction), and `negative` (conflicts, abstentions, failed guards and unreached temporal states). Audience selection changes only the presentation lens; the derivation hash and underlying trace remain identical. The PROforma debugger is the only built-in interactive trace viewer; its output includes evaluator nodes, argument profiles, eligible options and temporal trace. No opaque AI-generated rationale is inserted.

Timestamps and event IDs are trace metadata, not the basis for a clinical decision. The digest is reproducible for identical canonical content, while the ledger hash additionally binds actual event identity/time/sequence.

## Argument graph and temporal derivations (G)

PROforma decision derivations include candidate nodes, argument nodes, their condition traces, weights, polarity, evidence references and canonical source-event references. Temporal ASP output is included as recognized states, pathway deviations and prerequisite/temporal findings. These records are inputs to the same `derive()` function; there is no separate clinical or pedagogical explanation engine.
