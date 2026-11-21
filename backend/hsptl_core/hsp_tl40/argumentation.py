"""PROforma-native weighted argumentation helpers.

This is not a separate decision engine: ProformaRuntime calls these functions
while enacting a PROforma decision task. Arguments and their conditions are
ordinary PROforma model data.
"""
from __future__ import annotations

import math
from typing import Any


ARGUMENTATION_VERSION = "hsptl.argumentation/1.0"


def evaluate_decision(task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    from .proforma import evaluate
    """Evaluate all candidates and preserve the full balance of reasons.

    A positive net force establishes a preference, not a clinical conclusion.
    No option is selected automatically; all eligible candidates remain visible.
    """
    profiles: list[dict[str, Any]] = []
    graph: list[dict[str, Any]] = []
    undecidable: list[str] = []
    for option in task.get("options", []):
        option_id = str(option.get("id", ""))
        eligibility = evaluate(option.get("when", True), context)
        graph.append({"node": f"candidate:{option_id}", "kind": "candidate",
                      "eligible": eligibility.state, "trace": eligibility.trace})
        if eligibility.value is None:
            undecidable.append(f"{option_id}:eligibility")
            continue
        if eligibility.value is False:
            continue

        support = 0.0
        opposition = 0.0
        active_arguments: list[dict[str, Any]] = []
        for index, argument in enumerate(option.get("arguments", [])):
            argument_id = str(argument.get("id") or f"{option_id}:argument:{index + 1}")
            polarity = argument.get("polarity")
            if polarity not in {"for", "against"}:
                return {"state": "abstain", "reason": f"Argument {argument_id} has invalid polarity.",
                        "profiles": profiles, "argument_graph": graph}
            try:
                weight = float(argument.get("weight", 1.0))
            except (TypeError, ValueError):
                weight = float("nan")
            if not math.isfinite(weight) or weight < 0:
                return {"state": "abstain", "reason": f"Argument {argument_id} has invalid weight.",
                        "profiles": profiles, "argument_graph": graph}
            condition = evaluate(argument.get("when", True), context)
            node = {"node": f"argument:{argument_id}", "kind": "argument",
                    "candidate_id": option_id, "polarity": polarity,
                    "weight": weight, "condition": condition.state,
                    "status": argument.get("status", "pass"),
                    "reason": argument.get("reason"),
                    "evidence": argument.get("evidence", []),
                    "source_events": argument.get("source_events", []),
                    "trace": condition.trace}
            graph.append(node)
            if condition.value is None:
                undecidable.append(f"{option_id}:{argument_id}")
                continue
            if condition.value is False:
                continue
            if argument.get("status") == "abstain":
                active_arguments.append({"id": argument_id, "polarity": polarity,
                                         "weight": 0.0, "status": "abstain",
                                         "reason": argument.get("reason"),
                                         "label": argument.get("label", ""),
                                         "evidence": argument.get("evidence", []),
                                         "source_events": argument.get("source_events", []),
                                         "trace": condition.trace})
                continue
            if polarity == "for":
                support += weight
            else:
                opposition += weight
            active_arguments.append({"id": argument_id, "polarity": polarity,
                                     "weight": weight, "status": argument.get("status", "pass"),
                                     "label": argument.get("label", ""),
                                     "evidence": argument.get("evidence", []),
                                     "source_events": argument.get("source_events", []),
                                     "trace": condition.trace})
        profiles.append({
            "candidate_id": option_id,
            "label": option.get("label", option_id),
            "eligible": True,
            "support_force": round(support, 8),
            "opposition_force": round(opposition, 8),
            "net_force": round(support - opposition, 8),
            "arguments": active_arguments,
            "conclusive": False,
        })

    if undecidable:
        return {"state": "abstain", "reason": "Decision argument conditions or candidate eligibility are undecidable.",
                "undecidable": undecidable, "profiles": profiles,
                "argument_graph": graph, "version": ARGUMENTATION_VERSION}
    profiles.sort(key=lambda item: (-item["net_force"], -item["support_force"], item["candidate_id"]))
    for rank, profile in enumerate(profiles, 1):
        profile["preference_rank"] = rank
    preferred = []
    if profiles:
        top = profiles[0]["net_force"]
        preferred = [item["candidate_id"] for item in profiles if item["net_force"] == top]
    return {
        "state": "pass" if profiles else "fail",
        "profiles": profiles,
        "preferred_candidates": preferred,
        "argument_graph": graph,
        "preference_is_indicative": True,
        "automatic_selection": False,
        "version": ARGUMENTATION_VERSION,
        "reason": "Preference is the aggregate of independently weighted active arguments; all candidates remain available.",
    }
