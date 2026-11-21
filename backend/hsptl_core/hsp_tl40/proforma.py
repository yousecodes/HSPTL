"""A bounded, deterministic PROforma runtime used as HSPTL's sole logic language.

The runtime implements a deliberately explicit execution subset: plans,
decisions, actions and inquiries plus a safe predicate vocabulary. It does not
evaluate Python, JavaScript, SQL or user-supplied code. Unsupported constructs
return ``unknown`` and are surfaced as an abstention.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .explain import derive
from .kernel import EventKernel
from .argumentation import evaluate_decision
from .embedded_smt import EmbeddedSMT
from .temporal_reasoning import TemporalReasoner

UNKNOWN = object()
TASK_TYPES = {"plan", "decision", "action", "inquiry"}
LOGIC_VERSION = "HSPTL-PROforma-Subset/1.1"


@dataclass(frozen=True)
class Evaluation:
    value: bool | None
    state: str
    trace: list[dict[str, Any]]


class ProformaError(ValueError):
    pass


def _path(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return UNKNOWN
        current = current[part]
    return current


def _resolve(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict) and set(value) == {"ref"}:
        ref = value["ref"]
        return _path(context, ref) if isinstance(ref, str) else UNKNOWN
    return value


def evaluate(expression: Any, context: dict[str, Any]) -> Evaluation:
    """Evaluate one expression and produce a node-by-node proof trace."""
    trace: list[dict[str, Any]] = []

    def visit(expr: Any, path: str = "root") -> bool | None:
        if isinstance(expr, bool):
            trace.append({"node": path, "op": "literal", "result": expr})
            return expr
        if expr is None:
            trace.append({"node": path, "op": "unknown", "result": "unknown"})
            return None
        if not isinstance(expr, dict) or "op" not in expr:
            trace.append({"node": path, "op": "unsupported", "result": "unknown"})
            return None

        op = expr.get("op")
        args = expr.get("args", [])
        if not isinstance(args, list):
            args = []

        def operand(item: Any) -> Any:
            return _resolve(item, context)

        result: bool | None
        try:
            if op in {"and", "all"}:
                children = [visit(item, f"{path}.{index}") for index, item in enumerate(args)]
                result = False if False in children else (None if None in children or not children else True)
            elif op in {"or", "any"}:
                children = [visit(item, f"{path}.{index}") for index, item in enumerate(args)]
                result = True if True in children else (None if None in children or not children else False)
            elif op == "not" and len(args) == 1:
                child = visit(args[0], f"{path}.0")
                result = None if child is None else not child
            elif op == "implies" and len(args) == 2:
                left = visit(args[0], f"{path}.0")
                right = visit(args[1], f"{path}.1")
                result = True if left is False or right is True else (False if left is True and right is False else None)
            else:
                left = operand(expr.get("left", args[0] if args else UNKNOWN))
                right = operand(expr.get("right", args[1] if len(args) > 1 else UNKNOWN))
                if op == "exists":
                    result = None if left is UNKNOWN else (left is not None and left != "")
                elif op in {"eq", "equals"}:
                    result = None if left is UNKNOWN or right is UNKNOWN else left == right
                elif op in {"neq", "not_equals"}:
                    result = None if left is UNKNOWN or right is UNKNOWN else left != right
                elif op == "in":
                    result = None if left is UNKNOWN or right is UNKNOWN else (
                        left in right if isinstance(right, (list, tuple, set, str, dict)) else None
                    )
                elif op == "contains":
                    result = None if left is UNKNOWN or right is UNKNOWN else (
                        right in left if isinstance(left, (list, tuple, set, str, dict)) else None
                    )
                elif op in {"gt", "gte", "lt", "lte"}:
                    if left is UNKNOWN or right is UNKNOWN or left is None or right is None:
                        result = None
                    else:
                        result = {"gt": left > right, "gte": left >= right,
                                  "lt": left < right, "lte": left <= right}[op]
                elif op == "set_includes":
                    result = None if left is UNKNOWN or right is UNKNOWN else (
                        set(right).issubset(set(left)) if isinstance(left, (list, tuple, set)) and isinstance(right, (list, tuple, set)) else None
                    )
                else:
                    result = None
        except (TypeError, ValueError, KeyError):
            result = None

        trace.append({"node": path, "op": str(op), "result": "unknown" if result is None else result})
        return result

    value = visit(expression)
    state = "pass" if value is True else "fail" if value is False else "abstain"
    return Evaluation(value, state, trace)


def _walk_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return plan.get("tasks", []) if isinstance(plan.get("tasks"), list) else []


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return {"valid": False, "errors": ["Plan must be an object."], "logic_version": LOGIC_VERSION}
    if plan.get("type") != "plan":
        errors.append("Root task type must be 'plan'.")
    if not isinstance(plan.get("id"), str) or not plan.get("id", "").strip():
        errors.append("Plan id is required.")
    if not isinstance(plan.get("tasks"), list) or not plan.get("tasks"):
        errors.append("A plan requires at least one task.")

    seen: set[str] = {plan.get("id", "")}
    for index, task in enumerate(_walk_tasks(plan)):
        if not isinstance(task, dict):
            errors.append(f"Task {index} must be an object.")
            continue
        task_id = task.get("id")
        task_type = task.get("type")
        if not isinstance(task_id, str) or not task_id.strip():
            errors.append(f"Task {index} requires an id.")
        elif task_id in seen:
            errors.append(f"Duplicate task id: {task_id}.")
        else:
            seen.add(task_id)
        if task_type not in TASK_TYPES - {"plan"}:
            errors.append(f"Task {task_id or index} has unsupported type {task_type!r}.")
        if task_type == "decision":
            options = task.get("options")
            if not isinstance(options, list) or not options:
                errors.append(f"Decision {task_id} requires options.")
            elif any(not isinstance(option, dict) or not option.get("id") for option in options):
                errors.append(f"Decision {task_id} has a malformed option.")
            else:
                for option in options:
                    if "when" in option and not _valid_expression_shape(option["when"]):
                        errors.append(f"Decision option {option.get('id')} has an unsupported when expression.")
                    arguments = option.get("arguments", [])
                    if not isinstance(arguments, list):
                        errors.append(f"Decision option {option.get('id')} arguments must be a list.")
                        continue
                    for argument in arguments:
                        if not isinstance(argument, dict) or argument.get("polarity") not in {"for", "against"}:
                            errors.append(f"Decision option {option.get('id')} has a malformed argument.")
                            continue
                        try:
                            weight = float(argument.get("weight", 1.0))
                            if weight < 0 or not __import__("math").isfinite(weight):
                                raise ValueError
                        except (TypeError, ValueError):
                            errors.append(f"Decision argument {argument.get('id', '')} has an invalid non-negative weight.")
                        if "when" in argument and not _valid_expression_shape(argument["when"]):
                            errors.append(f"Decision argument {argument.get('id', '')} has an unsupported when expression.")
        if task_type == "inquiry" and not task.get("response_key"):
            errors.append(f"Inquiry {task_id} requires response_key.")
        if "requires_before" in task and (not isinstance(task["requires_before"], list) or
                any(not isinstance(value, str) for value in task["requires_before"])):
            errors.append(f"Task {task_id} requires_before must be a list of task identifiers.")
        for expression_key in ("preconditions", "when"):
            if expression_key in task and not _valid_expression_shape(task[expression_key]):
                errors.append(f"Task {task_id} has an unsupported {expression_key} expression shape.")
    task_ids = {task.get("id") for task in _walk_tasks(plan) if isinstance(task, dict)}
    for task in _walk_tasks(plan):
        if isinstance(task, dict):
            for prerequisite in task.get("requires_before", []):
                if prerequisite not in task_ids:
                    errors.append(f"Task {task.get('id')} references unknown temporal prerequisite {prerequisite}.")
    if "preconditions" in plan and not _valid_expression_shape(plan["preconditions"]):
        errors.append("Plan has an unsupported preconditions expression shape.")
    return {"valid": not errors, "errors": errors, "logic_version": LOGIC_VERSION,
            "task_types": sorted(TASK_TYPES)}


def _valid_expression_shape(expr: Any) -> bool:
    if isinstance(expr, bool) or expr is None:
        return True
    if not isinstance(expr, dict) or "op" not in expr:
        return False
    if "args" in expr and not isinstance(expr["args"], list):
        return False
    allowed = {"and", "all", "or", "any", "not", "implies", "exists", "eq", "equals",
               "neq", "not_equals", "in", "contains", "gt", "gte", "lt", "lte", "set_includes"}
    if expr.get("op") not in allowed:
        return False
    return all(_valid_expression_shape(x) for x in expr.get("args", []) if isinstance(x, dict) and "op" in x)


class ProformaRuntime:
    """Event-backed enactment runtime for the bounded PROforma task subset."""

    def __init__(self, kernel: EventKernel, *, smt: EmbeddedSMT | None = None,
                 temporal_reasoner: TemporalReasoner | None = None):
        self.kernel = kernel
        self.smt = smt or EmbeddedSMT()
        self.temporal_reasoner = temporal_reasoner or TemporalReasoner()

    @staticmethod
    def _context(state: dict[str, Any]) -> dict[str, Any]:
        return {"facts": state.get("facts", {}), "answers": state.get("answers", {}),
                "metadata": state.get("metadata", {}), "inferred": state.get("inferred", {}),
                "constraints": state.get("plan", {}).get("smt_constraints", []),
                "variables": state.get("plan", {}).get("symbolic_variables", {})}

    def _refresh_temporal(self, state: dict[str, Any]) -> dict[str, Any]:
        enactment_id = state.get("enactment_id", "")
        temporal = self.temporal_reasoner.analyze(
            self.kernel.events(limit=10000), state.get("plan", {}), enactment_id)
        state["inferred"] = {
            "recognized_states": temporal.get("recognized_states", []),
            "deviations": temporal.get("deviations", []),
            "deviation_sources": temporal.get("deviation_sources", []),
            "clinical_states": temporal.get("clinical_states", []),
            "clinical_conflicts": temporal.get("clinical_conflicts", []),
            "ruleset": temporal.get("ruleset"),
            "state": temporal.get("state", "abstain"),
        }
        state["temporal_derivation"] = derive(
            output_type="proforma.temporal_state",
            output={"state": temporal.get("state"),
                    "recognized_states": temporal.get("recognized_states", []),
                    "deviations": temporal.get("deviations", []),
                    "deviation_sources": temporal.get("deviation_sources", []),
                    "clinical_states": temporal.get("clinical_states", []),
                    "clinical_conflicts": temporal.get("clinical_conflicts", []),
                    "prerequisite_ready": temporal.get("prerequisite_ready", {})},
            rules=["ASP-PATHWAY-TEMPORAL-1.0"],
            inputs=[{"enactment_id": enactment_id, "event_count": len(self.kernel.events(limit=10000))}],
            steps=[{"ruleset": temporal.get("ruleset"), "ruleset_hash": temporal.get("ruleset_hash"),
                    "shown_atoms": temporal.get("shown_atoms", []), "reason": temporal.get("reason")}])
        return temporal

    def _availability(self, state: dict[str, Any]) -> dict[str, Any]:
        plan = state["plan"]
        temporal = self._refresh_temporal(state)
        context = self._context(state)
        has_temporal_requirements = any(task.get("requires_before") for task in _walk_tasks(plan) if isinstance(task, dict))
        if has_temporal_requirements and temporal.get("state") == "abstain":
            return {"status": "abstain", "available_tasks": [],
                    "trace": [{"source": "ASP", "reason": temporal.get("reason"),
                               "ruleset": temporal.get("ruleset")}],
                    "reason": "Temporal prerequisites cannot be verified; routing is withheld.",
                    "temporal": temporal}
        plan_eval = evaluate(plan.get("preconditions", True), context)
        if plan_eval.value is False:
            return {"status": "blocked", "available_tasks": [], "trace": plan_eval.trace,
                    "reason": "Plan preconditions are false."}
        if plan_eval.value is None:
            return {"status": "abstain", "available_tasks": [], "trace": plan_eval.trace,
                    "reason": "Plan preconditions are undecidable."}
        tasks = _walk_tasks(plan)
        statuses = state.setdefault("task_status", {})
        for task in tasks:
            status = statuses.get(task["id"], "not_started")
            if status == "completed":
                continue
            task_type = task["type"]
            if task.get("requires_before"):
                readiness = temporal.get("prerequisite_ready", {}).get(task["id"])
                if readiness is not True:
                    return {"status": "blocked", "available_tasks": [],
                            "trace": plan_eval.trace + [{"source": "ASP", "task_id": task["id"],
                                "required_before": task.get("requires_before"), "ready": readiness}],
                            "reason": f"Task {task['id']} has an unmet temporal prerequisite.",
                            "temporal": temporal}
            if task_type == "inquiry":
                answered = task["response_key"] in state.get("answers", {})
                return {"status": "completed" if answered else "active",
                        "available_tasks": [] if answered else [{"task": task, "options": []}],
                        "trace": plan_eval.trace}
            if task_type == "action":
                checked = evaluate(task.get("preconditions", True), context)
                if checked.value is None:
                    return {"status": "abstain", "available_tasks": [],
                            "trace": plan_eval.trace + checked.trace,
                            "reason": f"Action {task['id']} preconditions are undecidable."}
                if checked.value is False:
                    return {"status": "blocked", "available_tasks": [],
                            "trace": plan_eval.trace + checked.trace,
                            "reason": f"Action {task['id']} preconditions are false."}
                return {"status": "active", "available_tasks": [{"task": task, "options": []}],
                        "trace": plan_eval.trace + checked.trace}
            if task_type == "decision":
                preconditions = []
                if "preconditions" in task:
                    preconditions.append(task["preconditions"])
                if "when" in task:
                    preconditions.append(task["when"])
                decision_precondition = (preconditions[0] if len(preconditions) == 1 else
                                         {"op": "and", "args": preconditions} if preconditions else True)
                precondition_eval = evaluate(decision_precondition, context)
                precondition_trace = list(precondition_eval.trace)
                if precondition_eval.value is False:
                    return {"status": "blocked", "available_tasks": [],
                            "trace": plan_eval.trace + precondition_trace,
                            "reason": f"Decision {task['id']} preconditions are false.",
                            "temporal": temporal}
                precondition_solver = None
                if precondition_eval.value is None:
                    precondition_solver = self.smt.prove_decision_precondition(decision_precondition, context)
                    if precondition_solver.get("state") == "fail":
                        return {"status": "blocked", "available_tasks": [],
                                "trace": plan_eval.trace + precondition_trace + precondition_solver.get("trace", []),
                                "reason": f"Decision {task['id']} precondition is refuted by declared constraints.",
                                "temporal": temporal}
                    if precondition_solver.get("state") != "pass":
                        consistency_context = dict(context)
                        shared_constraints = list(context.get("constraints", []))
                        shared_constraints.append({"id": f"decision-precondition:{task['id']}",
                                                   "expression": decision_precondition})
                        consistency_context["constraints"] = shared_constraints
                        symbolic_arguments = [{"id": f"option:{option.get('id')}:eligibility",
                                                "when": option.get("when", True)}
                                               for option in task.get("options", [])]
                        symbolic_arguments.extend(argument for option in task.get("options", [])
                                                  for argument in option.get("arguments", []))
                        consistency = self.smt.check_argument_consistency(symbolic_arguments, consistency_context)
                        return {"status": "abstain", "available_tasks": [],
                                "trace": plan_eval.trace + precondition_trace + precondition_solver.get("trace", []) +
                                         [{"source": "SMT", "result": consistency}],
                                "reason": "Decision precondition is undecidable; symbolic consistency was checked without guessing.",
                                "precondition_solver": precondition_solver,
                                "smt_consistency": consistency, "temporal": temporal}

                decision_task = copy.deepcopy(task)
                deviation_sources = temporal.get("deviation_sources", [])
                if deviation_sources:
                    for option in decision_task.get("options", []):
                        mapped_task = option.get("pathway_task_id") or option.get("task_id")
                        relevant = [item for item in deviation_sources
                                    if mapped_task is None or mapped_task == item.get("task_id")]
                        option.setdefault("arguments", [])
                        for item in relevant:
                            event_id = str(item.get("event_id") or f"seq-{item.get('seq')}")
                            option["arguments"].append({
                                "id": f"asp-deviation:{event_id}", "polarity": "against",
                                "weight": plan.get("metadata", {}).get("asp_deviation_argument_weight", 1.0),
                                "when": True, "status": "pass", "label": "ASP pathway deviation",
                                "reason": "The canonical event log contains a pathway step without a prior enactment.",
                                "source_events": [{"event_id": item.get("event_id"), "seq": item.get("seq"),
                                                   "event_type": item.get("event_type")}]
                            })

                argumentation = evaluate_decision(decision_task, context)
                consistency = None
                if argumentation["state"] == "abstain":
                    consistency_context = dict(context)
                    shared_constraints = list(context.get("constraints", []))
                    shared_constraints.append({"id": f"decision-precondition:{task['id']}",
                                               "expression": decision_precondition})
                    consistency_context["constraints"] = shared_constraints
                    symbolic_arguments = [{"id": f"option:{option.get('id')}:eligibility",
                                            "when": option.get("when", True)}
                                           for option in decision_task.get("options", [])]
                    symbolic_arguments.extend(argument for option in decision_task.get("options", [])
                                              for argument in option.get("arguments", []))
                    consistency = self.smt.check_argument_consistency(symbolic_arguments, consistency_context)
                    argumentation["smt_consistency"] = consistency
                    if consistency.get("state") == "fail":
                        argumentation["reason"] = "Decision argument conditions contain a contradiction."
                        argumentation["minimal_unsat_core"] = consistency.get("minimal_unsat_core", [])
                state.setdefault("decision_profiles", {})[task["id"]] = argumentation
                option_trace = argumentation.get("argument_graph", [])
                if argumentation["state"] == "abstain":
                    return {"status": "abstain", "available_tasks": [],
                            "trace": plan_eval.trace + option_trace + [{"source": "SMT", "result": consistency}],
                            "reason": argumentation.get("reason", "Decision argumentation is undecidable."),
                            "argumentation": argumentation, "temporal": temporal}
                if argumentation["state"] != "pass":
                    return {"status": "blocked", "available_tasks": [],
                            "trace": plan_eval.trace + option_trace,
                            "reason": "No decision option is eligible.",
                            "argumentation": argumentation, "temporal": temporal}
                profile_map = {item["candidate_id"]: item for item in argumentation["profiles"]}
                options = []
                for option in task.get("options", []):
                    profile = profile_map.get(option["id"])
                    if profile is not None:
                        options.append({**option, "argument_profile": profile})
                ordered = sorted(options, key=lambda item: item["argument_profile"]["preference_rank"])
                return {"status": "active", "available_tasks": [{"task": task, "options": ordered,
                        "argumentation": argumentation}],
                        "trace": plan_eval.trace + precondition_trace + option_trace + [{"source": "ASP", "result": temporal.get("state"),
                            "recognized_states": temporal.get("recognized_states", []),
                            "deviation_sources": temporal.get("deviation_sources", [])}],
                        "argumentation": argumentation, "temporal": temporal}
        return {"status": "completed", "available_tasks": [], "trace": plan_eval.trace}

    def enact(self, plan: dict[str, Any], *, facts: dict[str, Any] | None = None,
              metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        validated = validate_plan(plan)
        if not validated["valid"]:
            raise ProformaError(" ".join(validated["errors"]))
        enactment_id = "enact_" + __import__("uuid").uuid4().hex
        state = {"enactment_id": enactment_id, "plan": copy.deepcopy(plan), "facts": facts or {},
                 "metadata": metadata or {}, "answers": {}, "task_status": {},
                 "selected_options": {}, "decision_profiles": {}, "inferred": {},
                 "status": "active", "logic_version": LOGIC_VERSION}
        availability = self._availability(state)
        state["status"] = availability["status"]
        state["available"] = availability["available_tasks"]
        if availability.get("reason"):
            state["abstention_reason"] = availability["reason"]
        derivation = derive(output_type="proforma.enactment", output={"enactment_id": enactment_id,
                           "status": state["status"]}, rules=["PROFORMA-PLAN-001"],
                           inputs=[{"plan_id": plan["id"], "logic_version": LOGIC_VERSION}],
                           steps=availability["trace"] + [{"temporal_derivation": state.get("temporal_derivation")}])
        state["derivation"] = derivation
        event_type = "platform.pathway.abstained" if state["status"] == "abstain" else "platform.pathway.enacted"
        event = self.kernel.append(event_type, {"enactment_id": enactment_id, "state": state,
                                                "reason": availability.get("reason")})
        return {"state": state, "event": event, "availability": availability}

    def get(self, enactment_id: str) -> dict[str, Any]:
        state = self.kernel.latest_enactment(enactment_id)
        if state is None:
            raise KeyError(enactment_id)
        return {"state": state, "availability": self._availability(copy.deepcopy(state))}

    def step(self, enactment_id: str, task_id: str, *, value: Any = None,
             context_patch: dict[str, Any] | None = None) -> dict[str, Any]:
        state = self.kernel.latest_enactment(enactment_id)
        if state is None:
            raise KeyError(enactment_id)
        state = copy.deepcopy(state)
        availability = self._availability(state)
        if availability["status"] != "active":
            raise ProformaError(f"Enactment is {availability['status']}; no task can be advanced.")
        available = availability["available_tasks"]
        if not available or available[0]["task"]["id"] != task_id:
            raise ProformaError("Task is not the next eligible PROforma task.")
        task = available[0]["task"]
        if context_patch:
            # Context patches are limited to named non-clinical task variables;
            # clinical facts must arrive from the Pulse/clinical data bridge.
            if "facts" in context_patch:
                raise ProformaError("PROforma enactment cannot overwrite canonical facts.")
            state.setdefault("metadata", {}).update(context_patch.get("metadata", {}))
        if task["type"] == "inquiry":
            if task.get("required", True) and (value is None or str(value).strip() == ""):
                raise ProformaError("A response is required for this inquiry.")
            state.setdefault("answers", {})[task["response_key"]] = value
        elif task["type"] == "action":
            checked = evaluate(task.get("preconditions", True), self._context(state))
            if checked.value is not True:
                reason = f"Action {task_id} could not be proven eligible."
                state["status"] = "abstain"
                state["available"] = []
                state["abstention_reason"] = reason
                derivation = derive(output_type="proforma.abstention",
                    output={"enactment_id": enactment_id, "task_id": task_id, "status": "abstain"},
                    rules=["PROFORMA-PRECONDITION-001"], inputs=[{"plan_id": state["plan"]["id"], "task_id": task_id}],
                    steps=checked.trace)
                state["derivation"] = derivation
                event = self.kernel.append("platform.pathway.abstained", {
                    "enactment_id": enactment_id, "state": state, "reason": reason,
                    "trace": checked.trace, "derivation": derivation,
                })
                raise ProformaError(f"{reason} Event: {event['event_id']}")
            state.setdefault("answers", {})[f"action:{task_id}"] = {"completed": True, "value": value}
        elif task["type"] == "decision":
            choices = {item["id"] for item in available[0]["options"]}
            if value not in choices:
                raise ProformaError("Selected decision option is not currently eligible.")
            state.setdefault("selected_options", {})[task_id] = value
            state.setdefault("answers", {})[f"decision:{task_id}"] = value
            profile = next((item for item in available[0].get("argumentation", {}).get("profiles", [])
                            if item.get("candidate_id") == value), None)
            state.setdefault("decision_profiles", {})[task_id] = {
                **available[0].get("argumentation", {}), "selected_candidate": value,
                "selected_profile": profile, "selection_is_user_confirmed": True}
        state.setdefault("task_status", {})[task_id] = "completed"
        after = self._availability(state)
        state["status"] = after["status"]
        state["available"] = after["available_tasks"]
        if after.get("reason"):
            state["abstention_reason"] = after["reason"]
        derivation = derive(output_type="proforma.step", output={"enactment_id": enactment_id,
                           "task_id": task_id, "status": state["status"]},
                           rules=["PROFORMA-SEQUENCE-001", "PROFORMA-PRECONDITION-001"],
                           inputs=[{"plan_id": state["plan"]["id"], "task_id": task_id,
                                    "response_present": value is not None}],
                           steps=availability["trace"] + after["trace"] + [
                               {"argumentation": state.get("decision_profiles", {}).get(task_id)},
                               {"temporal_derivation": state.get("temporal_derivation")}])
        state["derivation"] = derivation
        event_type = "platform.pathway.abstained" if after["status"] == "abstain" else "platform.pathway.stepped"
        event = self.kernel.append(event_type, {
            "enactment_id": enactment_id, "state": state, "task_id": task_id,
            "trace": derivation,
        })
        return {"state": state, "event": event, "availability": after}
