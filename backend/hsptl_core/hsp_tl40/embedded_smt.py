"""In-process PROforma-to-CNF and Z3 reasoning adapter.

No service or second rule language is introduced. Expressions are the same
bounded PROforma expression trees consumed by the runtime. Z3 is imported only
for rules explicitly classified as z3_required.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .provability import classify_rule


@dataclass
class CNFProgram:
    clauses: list[list[int]] = field(default_factory=list)
    variables: dict[int, str] = field(default_factory=dict)
    roots: list[tuple[str, int | bool]] = field(default_factory=list)


class _CNFBuilder:
    def __init__(self, context: dict[str, Any]):
        self.context = context
        self.program = CNFProgram()
        self.atom_ids: dict[str, int] = {}
        self.next_id = 1

    @staticmethod
    def _canonical_atom(expr: dict[str, Any]) -> tuple[str, bool]:
        op = expr.get("op")
        args = expr.get("args", [])
        left = expr.get("left", args[0] if args else None)
        right = expr.get("right", args[1] if len(args) > 1 else None)
        complement = {"neq": ("eq", True), "not_equals": ("eq", True),
                      "equals": ("eq", False), "eq": ("eq", False),
                      "gt": ("lte", True), "lte": ("lte", False),
                      "gte": ("lt", True), "lt": ("lt", False)}
        normalized, inverted = complement.get(op, (str(op), False))
        if normalized == "eq":
            left_is_ref = isinstance(left, dict) and set(left) == {"ref"}
            right_is_ref = isinstance(right, dict) and set(right) == {"ref"}
            if right_is_ref and not left_is_ref:
                left, right = right, left
            elif left_is_ref and right_is_ref:
                if str(right.get("ref")) < str(left.get("ref")):
                    left, right = right, left
            elif not left_is_ref and not right_is_ref:
                if json.dumps(right, sort_keys=True, separators=(",", ":")) < json.dumps(left, sort_keys=True, separators=(",", ":")):
                    left, right = right, left
        key = json.dumps([normalized, left, right], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return key, inverted

    def _new(self, label: str) -> int:
        variable = self.next_id
        self.next_id += 1
        self.program.variables[variable] = label
        return variable

    def _clause(self, *literals: int | bool) -> None:
        if any(item is True for item in literals):
            return
        cleaned = [item for item in literals if item is not False]
        # A repeated literal is harmless; opposite literals make a tautology.
        if any(-item in cleaned for item in cleaned if isinstance(item, int)):
            return
        if cleaned:
            self.program.clauses.append([int(item) for item in cleaned])
        else:
            self.program.clauses.append([])

    def encode(self, expression: Any) -> int | bool:
        if isinstance(expression, bool):
            return expression
        if expression is None:
            key = "null:unknown"
            if key not in self.atom_ids:
                self.atom_ids[key] = self._new(key)
            return self.atom_ids[key]
        if not isinstance(expression, dict) or "op" not in expression:
            key = json.dumps(["unsupported", expression], sort_keys=True, default=str)
            if key not in self.atom_ids:
                self.atom_ids[key] = self._new(key)
            return self.atom_ids[key]
        op = expression.get("op")
        args = expression.get("args", []) if isinstance(expression.get("args", []), list) else []
        if op == "not" and len(args) == 1:
            child = self.encode(args[0])
            return not child if isinstance(child, bool) else -child
        if op == "implies" and len(args) == 2:
            return self.encode({"op": "or", "args": [
                {"op": "not", "args": [args[0]]}, args[1]]})
        if op in {"and", "all", "or", "any"}:
            children = [self.encode(item) for item in args]
            is_and = op in {"and", "all"}
            if not children:
                return is_and
            if any(isinstance(child, bool) for child in children):
                if is_and:
                    if False in children: return False
                    children = [child for child in children if child is not True]
                else:
                    if True in children: return True
                    children = [child for child in children if child is not False]
                if not children: return is_and
            if len(children) == 1:
                return children[0]
            result = self._new(f"{op}:{len(self.program.variables)}")
            if is_and:
                for child in children:
                    self._clause(-result, child)
                self._clause(result, *[-child for child in children])
            else:
                for child in children:
                    self._clause(result, -child)
                self._clause(-result, *children)
            return result

        from .proforma import evaluate
        grounded = evaluate(expression, self.context)
        if grounded.value is not None:
            return grounded.value
        key, inverted = self._canonical_atom(expression)
        if key not in self.atom_ids:
            self.atom_ids[key] = self._new(key)
        variable = self.atom_ids[key]
        return -variable if inverted else variable

    def add_formula(self, formula_id: str, expression: Any) -> int | bool:
        root = self.encode(expression)
        self.program.roots.append((formula_id, root))
        return root


def compile_proforma_to_cnf(expressions: list[tuple[str, Any]], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compile one or more PROforma boolean expressions using Tseitin CNF."""
    builder = _CNFBuilder(context or {})
    # Store each root separately; callers may instead use root assumptions
    # when they need an unsatisfiable core.
    for formula_id, expression in expressions:
        builder.add_formula(str(formula_id), expression)
    equality_atoms: dict[str, list[tuple[str, int]]] = {}
    for atom_key, variable in builder.atom_ids.items():
        try:
            atom = json.loads(atom_key)
        except (TypeError, ValueError):
            continue
        if len(atom) == 3 and atom[0] == "eq" and isinstance(atom[1], dict) and set(atom[1]) == {"ref"}:
            ref_key = json.dumps(atom[1], sort_keys=True, separators=(",", ":"))
            value_key = json.dumps(atom[2], sort_keys=True, separators=(",", ":"))
            equality_atoms.setdefault(ref_key, []).append((value_key, variable))
    for entries in equality_atoms.values():
        for index, (value_a, var_a) in enumerate(entries):
            for value_b, var_b in entries[index + 1:]:
                if value_a != value_b:
                    builder._clause(-var_a, -var_b)
    return {"clauses": builder.program.clauses,
            "variables": {str(key): value for key, value in builder.program.variables.items()},
            "roots": [{"id": key, "literal": value} for key, value in builder.program.roots],
            "encoding": "Tseitin-CNF", "source_language": "PROforma",
            "variable_count": len(builder.program.variables),
            "symbolic_declarations": (context or {}).get("variables", {})}


class EmbeddedSMT:
    """Z3-backed decision support. All methods are in-process and fail closed."""

    def prove_decision_precondition(self, expression: Any, context: dict[str, Any] | None = None,
                                    *, rule_id: str = "SMT-DECISION-PRECONDITION-001") -> dict[str, Any]:
        if self._authorized(rule_id) is None:
            return {"state": "abstain", "reason": "SMT invocation is not authorized for this rule.", "rule_id": rule_id}
        from .provability import Z3DecisionAdapter
        result = Z3DecisionAdapter().decide(expression, context or {})
        return {"state": result.get("decision", "abstain"), "reason": result.get("reason"),
                "trace": result.get("trace", []), "solver": "z3-in-process", "rule_id": rule_id}

    def _authorized(self, rule_id: str) -> dict[str, str] | None:
        policy = classify_rule(rule_id)
        return policy if policy["classification"] == "z3_required" else None

    @staticmethod
    def _new_z3():
        try:
            import z3
            return z3
        except Exception:
            return None

    def check_argument_consistency(self, arguments: list[dict[str, Any]],
                                   context: dict[str, Any] | None = None,
                                   *, rule_id: str = "SMT-ARGUMENT-CONSISTENCY-001") -> dict[str, Any]:
        policy = self._authorized(rule_id)
        if policy is None:
            return {"state": "abstain", "reason": "SMT invocation is not authorized for this rule.", "rule_id": rule_id}
        z3 = self._new_z3()
        if z3 is None:
            return {"state": "abstain", "reason": "Z3 library is unavailable; argument consistency was not guessed.",
                    "rule_id": rule_id}
        context = context or {}
        shared = context.get("constraints", [])
        if not isinstance(shared, list):
            return {"state": "abstain", "reason": "Shared symbolic constraints must be a list of PROforma expressions.",
                    "rule_id": rule_id}
        issues = []
        cnf_by_argument = {}
        for index, argument in enumerate(arguments):
            argument_id = str(argument.get("id", f"argument-{index + 1}"))
            expressions = []
            for constraint_index, constraint in enumerate(shared):
                if isinstance(constraint, dict) and "expression" in constraint:
                    expressions.append((str(constraint.get("id", f"constraint-{constraint_index + 1}")),
                                        constraint["expression"]))
                else:
                    expressions.append((f"context-constraint-{constraint_index + 1}", constraint))
            expressions.append((argument_id, argument.get("when", True)))
            compiled = compile_proforma_to_cnf(expressions, context)
            cnf_by_argument[argument_id] = compiled
            result = _check_compiled_core(compiled, z3)
            if result["state"] == "fail":
                issues.append({"argument_id": argument_id,
                               "minimal_unsat_core": result["minimal_unsat_core"],
                               "core_kind": result.get("core_kind"), "cnf": compiled})
            elif result["state"] == "abstain":
                return {"state": "abstain", "reason": result.get("reason"),
                        "argument_id": argument_id, "cnf": compiled, "rule_id": rule_id}
        return {"state": "fail" if issues else "pass", "consistent": not issues,
                "contradictions": issues, "cnf_by_argument": cnf_by_argument,
                "solver": "z3-in-process", "rule_id": rule_id,
                "semantics": "Each argument condition is checked against shared PROforma constraints; alternative arguments are not incorrectly asserted simultaneously."}

    def enumerate_differentials(self, hypotheses: list[dict[str, Any]],
                                findings: list[dict[str, Any]],
                                context: dict[str, Any] | None = None,
                                *, rule_id: str = "SMT-DIFFERENTIAL-001") -> dict[str, Any]:
        if self._authorized(rule_id) is None:
            return {"state": "abstain", "reason": "SMT invocation is not authorized for this rule."}
        z3 = self._new_z3()
        if z3 is None:
            return {"state": "abstain", "reason": "Z3 library is unavailable; differential hypotheses were not guessed."}
        output = []
        rejected = []
        shared_constraints = (context or {}).get("constraints", [])
        if not isinstance(shared_constraints, list):
            return {"state": "abstain", "reason": "Shared symbolic constraints must be a list of PROforma expressions."}
        for hypothesis in hypotheses:
            hid = str(hypothesis.get("id", ""))
            expressions = []
            for constraint_index, constraint in enumerate(shared_constraints):
                if isinstance(constraint, dict) and "expression" in constraint:
                    expressions.append((str(constraint.get("id", f"constraint-{constraint_index + 1}")), constraint["expression"]))
                else:
                    expressions.append((f"context-constraint-{constraint_index + 1}", constraint))
            for index, finding in enumerate(findings):
                expression = finding.get("when", finding.get("condition", True))
                if finding.get("observed", True) is False:
                    expression = {"op": "not", "args": [expression]}
                expressions.append((f"finding:{finding.get('id', index)}", expression))
            expressions.append((f"hypothesis:{hid}", hypothesis.get("when", hypothesis.get("condition", True))))
            compiled = compile_proforma_to_cnf(expressions, context or {})
            state = _solve_compiled(compiled, z3)
            if state == "sat":
                output.append({"hypothesis_id": hid, "consistent": True,
                               "finding_ids": [str(x.get("id", i)) for i, x in enumerate(findings)],
                               "cnf": compiled})
            elif state == "unsat":
                rejected.append({"hypothesis_id": hid, "consistent": False,
                                 "reason": "Hypothesis conflicts with the inquiry findings."})
            else:
                return {"state": "abstain", "reason": "Z3 could not decide every differential hypothesis.",
                        "consistent_hypotheses": output, "rejected": rejected}
        return {"state": "pass", "consistent_hypotheses": output, "rejected": rejected,
                "solver": "z3-in-process", "rule_id": rule_id}

    def counterfactual_single_finding(self, decision: dict[str, Any], context: dict[str, Any],
                                      proposed_findings: list[dict[str, Any]],
                                      *, rule_id: str = "SMT-COUNTERFACTUAL-001") -> dict[str, Any]:
        if self._authorized(rule_id) is None:
            return {"state": "abstain", "reason": "SMT invocation is not authorized for this rule."}
        z3 = self._new_z3()
        if z3 is None:
            return {"state": "abstain", "reason": "Z3 library is unavailable; counterfactuals were not guessed."}
        from .argumentation import evaluate_decision
        baseline = evaluate_decision(decision, context)
        if baseline["state"] != "pass" or not baseline.get("preferred_candidates"):
            return {"state": "abstain", "reason": "Current decision preference is not decidable."}
        current = baseline["preferred_candidates"]
        reversals = []
        for finding in proposed_findings:
            expression = finding.get("when", finding.get("condition", True))
            compiled = compile_proforma_to_cnf([(str(finding.get("id", "finding")), expression)], context)
            if _solve_compiled(compiled, z3) != "sat":
                continue
            patch = finding.get("context_patch", {})
            if not isinstance(patch, dict) or not patch:
                continue
            simulated_context = json.loads(json.dumps(context))
            _apply_context_patch(simulated_context, patch)
            from .proforma import evaluate
            finding_check = evaluate(expression, simulated_context)
            if finding_check.value is not True:
                continue
            alternate = evaluate_decision(decision, simulated_context)
            if alternate["state"] != "pass":
                continue
            preferred = alternate.get("preferred_candidates", [])
            if preferred and set(preferred).isdisjoint(current):
                reversals.append({"finding_id": finding.get("id"),
                                  "current_preference": current,
                                  "counterfactual_preference": preferred,
                                  "profiles": alternate["profiles"],
                                  "condition_cnf": compiled})
        return {"state": "pass", "current_preference": current,
                "single_findings_that_reverse_preference": reversals,
                "solver": "z3-in-process", "rule_id": rule_id,
                "note": "Counterfactual preference changes are indicative, not conclusive."}


def _root_pairs(compiled: dict[str, Any]) -> list[tuple[str, int | bool]]:
    return [(item["id"], item["literal"]) for item in compiled["roots"]]


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)[:48]


def _add_theory_axioms(solver: Any, symbols: dict[int, Any],
                       compiled: dict[str, Any], z3: Any) -> None:
    """Bind recognized PROforma comparison atoms to typed in-process symbols."""
    declarations = compiled.get("symbolic_declarations", {})
    variables: dict[str, Any] = {}
    for variable_id, label in compiled.get("variables", {}).items():
        try:
            atom = json.loads(label)
        except (TypeError, ValueError):
            continue
        if not isinstance(atom, list) or len(atom) != 3:
            continue
        op, left, right = atom
        if not (isinstance(left, dict) and set(left) == {"ref"}):
            continue
        ref = str(left["ref"])
        if isinstance(right, bool):
            symbol = variables.setdefault(ref, z3.Bool(ref))
            term = z3.BoolVal(right)
        elif isinstance(right, (int, float)):
            symbol = variables.setdefault(ref, z3.Real(ref))
            term = z3.RealVal(str(right))
        elif isinstance(right, str):
            symbol = variables.setdefault(ref, z3.String(ref))
            term = z3.StringVal(right)
        else:
            continue
        if op == "eq":
            condition = symbol == term
        elif op == "lt" and isinstance(right, (int, float)) and not isinstance(right, bool):
            condition = symbol < term
        elif op == "lte" and isinstance(right, (int, float)) and not isinstance(right, bool):
            condition = symbol <= term
        else:
            continue
        solver.add(symbols[int(variable_id)] == condition)
    for ref, spec in declarations.items() if isinstance(declarations, dict) else []:
        if not isinstance(spec, dict):
            continue
        symbol = variables.get(ref)
        if symbol is None:
            continue
        if spec.get("type") in {"int", "real"}:
            if spec.get("min") is not None:
                solver.add(symbol >= z3.RealVal(str(spec["min"])))
            if spec.get("max") is not None:
                solver.add(symbol <= z3.RealVal(str(spec["max"])))


def _check_compiled_core(compiled: dict[str, Any], z3: Any) -> dict[str, Any]:
    symbols = {int(key): z3.Bool(f"cnf_{key}") for key in compiled["variables"]}
    solver = z3.Solver()
    for clause in compiled["clauses"]:
        solver.add(z3.Or(*[(symbols[abs(lit)] if lit > 0 else z3.Not(symbols[abs(lit)])) for lit in clause]))
    _add_theory_axioms(solver, symbols, compiled, z3)
    roots = _root_pairs(compiled)
    tracks = []
    for index, (label, literal) in enumerate(roots):
        root = z3.BoolVal(literal) if isinstance(literal, bool) else (
            symbols[abs(literal)] if literal > 0 else z3.Not(symbols[abs(literal)]))
        track = z3.Bool(f"core_{index}_{_safe(label)}")
        solver.add(z3.Implies(track, root))
        tracks.append((label, track))
    result = solver.check(*[track for _, track in tracks])
    if result == z3.sat:
        return {"state": "pass", "minimal_unsat_core": []}
    if result == z3.unknown:
        return {"state": "abstain", "reason": solver.reason_unknown()}
    core_names = {str(item) for item in solver.unsat_core()}
    minimized = [(label, track) for label, track in tracks if str(track) in core_names]
    for candidate in list(minimized):
        trial = [item for item in minimized if item != candidate]
        check = z3.Solver()
        for clause in compiled["clauses"]:
            check.add(z3.Or(*[(symbols[abs(lit)] if lit > 0 else z3.Not(symbols[abs(lit)])) for lit in clause]))
        _add_theory_axioms(check, symbols, compiled, z3)
        for label, track in trial:
            index = next(i for i, pair in enumerate(roots) if pair[0] == label)
            literal = roots[index][1]
            root = z3.BoolVal(literal) if isinstance(literal, bool) else (
                symbols[abs(literal)] if literal > 0 else z3.Not(symbols[abs(literal)]))
            check.add(z3.Implies(track, root))
        if check.check(*[track for _, track in trial]) == z3.unsat:
            minimized = trial
    return {"state": "fail", "minimal_unsat_core": [label for label, _ in minimized],
            "core_kind": "subset_minimal"}


def _solve_compiled(compiled: dict[str, Any], z3: Any) -> str:
    symbols = {int(key): z3.Bool(f"cnf_{key}") for key in compiled["variables"]}
    solver = z3.Solver()
    for clause in compiled["clauses"]:
        solver.add(z3.Or(*[(symbols[abs(lit)] if lit > 0 else z3.Not(symbols[abs(lit)])) for lit in clause]))
    _add_theory_axioms(solver, symbols, compiled, z3)
    for _, literal in _root_pairs(compiled):
        if isinstance(literal, bool):
            solver.add(z3.BoolVal(literal))
        else:
            solver.add(symbols[abs(literal)] if literal > 0 else z3.Not(symbols[abs(literal)]))
    result = solver.check()
    return "sat" if result == z3.sat else "unsat" if result == z3.unsat else "unknown"


def _apply_context_patch(context: dict[str, Any], patch: dict[str, Any]) -> None:
    for path, value in patch.items():
        if not isinstance(path, str) or not path:
            continue
        parts = path.split(".")
        target = context
        for part in parts[:-1]:
            current = target.get(part)
            if not isinstance(current, dict):
                current = {}
                target[part] = current
            target = current
        target[parts[-1]] = value
