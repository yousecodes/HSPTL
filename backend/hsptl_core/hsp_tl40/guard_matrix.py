"""Consolidated four-layer HSPTL 4.0 guard matrix."""
from __future__ import annotations

from typing import Any

from .provability import provability_catalogue


GUARD_MATRIX_V4: list[dict[str, Any]] = [
    {"id": "G-WRITE-BOUNDARY-001", "layer": 1, "boundary": "canonical event append",
     "provability": "closed_form", "poka_yoke": "event allow-list, payload schema, canonical JSON, size cap",
     "monitor": "write-boundary validation before SQLite append", "blocked_event": "platform.write.prevented"},
    {"id": "G-RULE-PROVABILITY-001", "layer": 2, "boundary": "rule execution",
     "provability": "per_rule_classified", "poka_yoke": "unclassified rules abstain; Z3 only for z3_required rules",
     "monitor": "solver invocation policy and solver-result monitor", "blocked_event": "platform.guard.abstained"},
    {"id": "G-PROFORMA-001", "layer": 2, "boundary": "workflow / appraisal / template / routing predicate",
     "provability": "proforma", "poka_yoke": "one bounded executable PROforma subset",
     "monitor": "three-valued evaluator; unknown cannot authorize action", "blocked_event": "platform.pathway.abstained"},
    {"id": "G-EVENT-MONITOR-001", "layer": 3, "boundary": "runtime event transition",
     "provability": "closed_form", "poka_yoke": "status/event consistency and lineage checks",
     "monitor": "in-process pre-append monitor registry", "blocked_event": "platform.write.prevented"},
    {"id": "G-AUDIT-REPLAY-001", "layer": 4, "boundary": "immutable audit and replay",
     "provability": "cryptographic_integrity", "poka_yoke": "SQLite update/delete triggers and SHA-256 previous-hash link",
     "monitor": "full chain verification and replay-diff harness", "blocked_event": "platform.write.prevented"},
    {"id": "G-SKIN-FACT-001", "layer": 1, "boundary": "workspace plugin configuration",
     "provability": "closed_form", "poka_yoke": "config JSON schema allow-list excludes clinical facts and rules",
     "monitor": "plugin config runtime monitor", "blocked_event": "platform.write.prevented"},
    {"id": "G-LINEAGE-001", "layer": 3, "boundary": "clinical assertion composition",
     "provability": "closed_form", "poka_yoke": "evidence, appraisal, rights and source-span preconditions",
     "monitor": "source event completeness and span hash equality", "blocked_event": "platform.write.prevented"},
    {"id": "G-CONFLICT-001", "layer": 2, "boundary": "same-scope opposing evidence assertions",
     "provability": "z3_required", "poka_yoke": "explicit proposition, scope and evidence IDs are required",
     "monitor": "SAT/UNSAT/unknown result captured in derivation", "blocked_event": "platform.guard.abstained"},
]


def guard_catalogue() -> dict[str, Any]:
    return {"layers": [
        {"number": 1, "name": "Write-boundary poka-yoke", "description": "Reject malformed or forbidden writes before canonical append."},
        {"number": 2, "name": "Per-rule provability", "description": "PROforma/closed-form first; Z3 only for rules classified z3_required."},
        {"number": 3, "name": "Runtime event monitors", "description": "Check cross-event invariants before accepting transitions."},
        {"number": 4, "name": "Immutable audit and replay", "description": "Prevented failures are immutable events; replay verifies the hash chain."},
    ], "guards": GUARD_MATRIX_V4, "provability": provability_catalogue()}
