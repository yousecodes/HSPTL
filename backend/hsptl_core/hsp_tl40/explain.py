"""Canonical derivation traces for HSPTL 4.0 outputs."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def derive(
    *,
    output_type: str,
    output: Any,
    rules: list[str] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    steps: list[dict[str, Any]] | None = None,
    source_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a stable, replay-friendly derivation envelope.

    Timestamps are metadata only. The digest excludes the timestamp so the same
    inputs, rules and steps reproduce the same derivation hash.
    """
    body = {
        "schema": "hsptl.derivation/1.0",
        "output_type": output_type,
        "output": output,
        "rules": rules or [],
        "inputs": inputs or [],
        "steps": steps or [],
        "source_events": source_events or [],
    }
    digest = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
    return {
        **body,
        "derivation_hash": digest,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "replayable": True,
    }


def render_explanation(derivation: dict[str, Any], audience: str = "clinical") -> dict[str, Any]:
    """Render one canonical derivation trace for different explanation audiences.

    Audience changes the lens only. The underlying trace and derivation hash are
    never forked into separate clinical/pedagogical rule stores.
    """
    if audience not in {"clinical", "pedagogical", "negative"}:
        raise ValueError("audience must be clinical, pedagogical or negative")

    found: list[tuple[str, dict[str, Any]]] = []

    def walk(value: Any, path: str = "trace") -> None:
        if isinstance(value, dict):
            found.append((path, value))
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(derivation.get("steps", []))
    walk(derivation.get("inputs", []))
    sections: list[dict[str, Any]] = []

    if audience == "clinical":
        items = []
        for path, node in found:
            if node.get("kind") == "argument" or "evidence" in node or "source_events" in node:
                evidence = node.get("evidence", [])
                source_events = node.get("source_events", [])
                if evidence or source_events or node.get("kind") == "argument":
                    items.append({"path": path, "argument": node.get("node") or node.get("id"),
                                  "candidate_id": node.get("candidate_id"),
                                  "polarity": node.get("polarity"), "weight": node.get("weight"),
                                  "evidence": evidence, "source_events": source_events,
                                  "condition": node.get("condition")})
        sections.append({"heading": "Arguments and evidence chains", "items": items,
                         "empty_message": "No evidence-linked arguments were present in this derivation."})

    elif audience == "pedagogical":
        items = []
        for path, node in found:
            if any(key in node for key in ("op", "result", "entailment", "postcondition", "completed", "satisfied")):
                summary = {key: node[key] for key in
                           ("op", "result", "node", "entailment", "postcondition", "completed", "satisfied", "task_id")
                           if key in node}
                if summary:
                    items.append({"path": path, **summary})
        sections.append({"heading": "Reasoning and learning trace", "items": items,
                         "empty_message": "No predicate or postcondition trace was recorded."})

    else:
        items = []
        for path, node in found:
            text = json.dumps(node, sort_keys=True, default=str).casefold()
            negative = (node.get("result") in {False, "unknown", "abstain", "fail"} or
                        node.get("state") in {"abstain", "fail", "blocked"} or
                        any(term in text for term in ("temporal_missing", "deviation", "unreached", "conflict", "abstain")))
            if negative:
                items.append({"path": path, "finding": node})
        sections.append({"heading": "Conflicts, abstentions and unreached states", "items": items,
                         "empty_message": "No negative or unresolved state was recorded."})

    return {"schema": "hsptl.derivation-render/1.0", "audience": audience,
            "derivation_hash": derivation.get("derivation_hash"),
            "output_type": derivation.get("output_type"), "output": derivation.get("output"),
            "rules": derivation.get("rules", []), "sections": sections,
            "source_derivation": derivation,
            "same_trace": True}
