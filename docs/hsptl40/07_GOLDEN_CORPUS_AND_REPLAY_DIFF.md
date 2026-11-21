# 7. Golden corpus and replay-diff harness

The corpus lives in `fixtures/golden_corpus/golden_logic_cases.json` and consists of synthetic PROforma/fixture input-output expectations. It is not live learner data or a source of runtime facts.

## Contents

- PheKB-shaped synthetic converter fixture with explicit known facts and an unknown-fact abstention case.
- Source-attributed PheKB Type 2 Diabetes EHR+ case/control vectors: qualifying case, universal control, age exclusion and missing-input abstention; all values are synthetic.
- GRADE-domain appraisal fixture with a human-review requirement and no automated certainty aggregate.
- CaSS and MedBiquitous graph fixtures are generated from synthetic reference inputs only.
- SNOMED CT import tests use synthetic RF2-shaped rows, never a copied terminology release.

## Replay diff

`golden.py` runs two full replays against the same ledger and compares stable canonical projection trees. It strips only transport/time fields (`created_at`, `occurred_at`, event IDs and event hashes) before structural diff; clinical content, rule IDs, derivation hashes, references and projection shape remain compared. The underlying replay still verifies the full event hash chain.

Run:

```bash
python scripts/replay_diff.py PATH_TO_HSPTL_SQLITE_DB
```

A non-zero exit indicates replay verification or stable projection equality failed. It does not rewrite or repair event history.
