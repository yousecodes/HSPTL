"""One read-only PROforma debugger using the exact production predicate evaluator."""
from __future__ import annotations

from typing import Any

from .proforma import evaluate, validate_plan
from .argumentation import evaluate_decision


def debug_proforma(plan: dict[str, Any], facts: dict[str, Any] | None = None,
                   answers: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validate_plan(plan)
    if not validation["valid"]:
        return {"state": "invalid", "validation": validation, "steps": [], "writes": 0}
    context = {"facts": facts or {}, "answers": answers or {}, "metadata": {}}
    steps: list[dict[str, Any]] = []
    root = evaluate(plan.get("preconditions", True), context)
    steps.append({"kind": "plan_preconditions", "state": root.state, "trace": root.trace})
    if root.state != "pass":
        return {"state": "abstain" if root.state == "abstain" else "blocked",
                "validation": validation, "steps": steps, "writes": 0}

    for task in plan.get("tasks", []):
        task_type = task.get("type")
        if task.get("requires_before"):
            steps.append({"task_id": task.get("id"), "kind": "temporal_prerequisite",
                          "state": "abstain_no_event_history", "requires_before": task.get("requires_before")})
            return {"state": "abstain", "next_task": task.get("id"),
                    "validation": validation, "steps": steps, "writes": 0}
        if task_type == "inquiry":
            response_key = task.get("response_key")
            answered = response_key in context["answers"]
            state = "completed" if answered else "pending_input"
            steps.append({"task_id": task["id"], "kind": task_type, "state": state,
                          "response_key": response_key, "trace": []})
            if not answered:
                return {"state": "active", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
        elif task_type == "decision":
            argumentation = evaluate_decision(task, context)
            eligible = [item["candidate_id"] for item in argumentation.get("profiles", [])]
            steps.append({"task_id": task["id"], "kind": task_type,
                          "state": "active" if argumentation.get("state") == "pass" else argumentation.get("state"),
                          "eligible_options": eligible, "argumentation": argumentation,
                          "trace": argumentation.get("argument_graph", [])})
            if argumentation.get("state") == "abstain":
                return {"state": "abstain", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            if not eligible:
                return {"state": "blocked", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            # This debugger is read-only and has no event-history input. A task
            # with temporal prerequisites therefore remains explicitly unresolved.
            if task.get("requires_before"):
                steps[-1]["temporal_state"] = "abstain_no_event_history"
                return {"state": "abstain", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            answer_key = f"decision:{task['id']}"
            if answer_key not in context["answers"]:
                return {"state": "active", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            if context["answers"][answer_key] not in eligible:
                steps[-1]["state"] = "fail"
                return {"state": "blocked", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
        elif task_type == "action":
            checked = evaluate(task.get("preconditions", True), context)
            steps.append({"task_id": task["id"], "kind": task_type, "state": checked.state, "trace": checked.trace})
            if checked.state == "abstain":
                return {"state": "abstain", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            if checked.state == "fail":
                return {"state": "blocked", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
            if f"action:{task['id']}" not in context["answers"]:
                return {"state": "active", "next_task": task["id"], "validation": validation, "steps": steps, "writes": 0}
    return {"state": "completed", "validation": validation, "steps": steps, "writes": 0}
