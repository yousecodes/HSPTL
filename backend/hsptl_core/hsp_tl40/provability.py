"""Per-rule provability policy. Z3 is invoked only for rules marked z3_required."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleProvability:
    rule_id: str
    classification: str
    rationale: str
    solver: str = "none"


RULE_PROVABILITY: dict[str, RuleProvability] = {
    "PROFORMA-GUARD-001": RuleProvability("PROFORMA-GUARD-001", "proforma", "Finite, ground predicate; PROforma three-valued evaluation is sufficient."),
    "PROFORMA-TEMPLATE-001": RuleProvability("PROFORMA-TEMPLATE-001", "proforma", "Template preconditions are finite PROforma predicates."),
    "PROFORMA-ROUTE-001": RuleProvability("PROFORMA-ROUTE-001", "proforma", "Routing eligibility is a finite PROforma predicate."),
    "PROFORMA-APPRAISAL-001": RuleProvability("PROFORMA-APPRAISAL-001", "proforma", "Appraisal workflow predicates execute in the PROforma runtime."),
    "PROFORMA-PRECONDITION-001": RuleProvability("PROFORMA-PRECONDITION-001", "proforma", "Task preconditions execute in the PROforma runtime."),
    "PROFORMA-PLAN-001": RuleProvability("PROFORMA-PLAN-001", "proforma", "Plan preconditions and eligibility execute in the PROforma runtime."),
    "SMT-SAFETY-001": RuleProvability("SMT-SAFETY-001", "z3_required", "Symbolic implication must be proven over declared constraints.", "z3"),
    "SMT-CONFLICT-001": RuleProvability("SMT-CONFLICT-001", "z3_required", "Opposing assertions require scoped satisfiability analysis.", "z3"),
    "SMT-BOUNDS-001": RuleProvability("SMT-BOUNDS-001", "z3_required", "Interacting symbolic numeric bounds require solver proof.", "z3"),
    "SMT-ARGUMENT-CONSISTENCY-001": RuleProvability("SMT-ARGUMENT-CONSISTENCY-001", "z3_required", "Argument conditions are compiled from PROforma to CNF and checked for contradictions with a minimal unsatisfiable core.", "z3"),
    "SMT-DECISION-PRECONDITION-001": RuleProvability("SMT-DECISION-PRECONDITION-001", "z3_required", "Undecidable decision preconditions may only pass when entailed by declared symbolic constraints.", "z3"),
    "SMT-DIFFERENTIAL-001": RuleProvability("SMT-DIFFERENTIAL-001", "z3_required", "Differential hypotheses are checked against inquiry findings using the PROforma expression tree.", "z3"),
    "SMT-COUNTERFACTUAL-001": RuleProvability("SMT-COUNTERFACTUAL-001", "z3_required", "Single-finding counterfactuals require in-process satisfiability checks.", "z3"),
    "STRUCTURAL-IDENTITY-001": RuleProvability("STRUCTURAL-IDENTITY-001", "closed_form", "Identity, presence and allow-list checks are directly decidable."),
    "STRUCTURAL-LINEAGE-001": RuleProvability("STRUCTURAL-LINEAGE-001", "closed_form", "Lineage completeness is a finite reference/shape check."),
}


def classify_rule(rule_id: str) -> dict[str, str]:
    rule = RULE_PROVABILITY.get(rule_id)
    if rule is None:
        return {"rule_id": rule_id, "classification": "unclassified", "solver": "none",
                "rationale": "No provability contract is registered; fail closed."}
    return {"rule_id": rule.rule_id, "classification": rule.classification,
            "solver": rule.solver, "rationale": rule.rationale}


def provability_catalogue() -> dict[str, Any]:
    return {"policy": "solver invocation is permitted only for z3_required rules",
            "unknown_rule_policy": "abstain", "rules": [classify_rule(key) for key in sorted(RULE_PROVABILITY)]}


class Z3DecisionAdapter:
    """Compile a PROforma predicate subset to SMT for explicitly classified rules."""

    def decide(self, expression: Any, context: dict[str, Any]) -> dict[str, Any]:
        try:
            from z3 import (And, Bool, BoolVal, Implies, Int, IntVal, Not, Or, Real,
                            RealVal, Solver, String, StringVal, sat, unsat)
        except Exception as exc:
            return {"decision": "abstain", "reason": f"Z3 unavailable: {exc}", "trace": []}

        declarations = context.get("variables", {})
        if not isinstance(declarations, dict) or not declarations:
            return {"decision": "abstain", "reason": "Z3-required PROforma rule has no declared symbolic references.", "trace": []}
        symbols: dict[str, Any] = {}
        solver = Solver()
        try:
            for name, spec in declarations.items():
                if not isinstance(name, str) or not isinstance(spec, dict):
                    raise ValueError("Variable declarations must map names to typed objects.")
                kind = spec.get("type")
                if kind == "bool":
                    symbols[name] = Bool(name)
                elif kind == "int":
                    symbols[name] = Int(name)
                    if spec.get("min") is not None:
                        solver.add(symbols[name] >= int(spec["min"]))
                    if spec.get("max") is not None:
                        solver.add(symbols[name] <= int(spec["max"]))
                elif kind == "real":
                    symbols[name] = Real(name)
                    if spec.get("min") is not None:
                        solver.add(symbols[name] >= RealVal(str(spec["min"])))
                    if spec.get("max") is not None:
                        solver.add(symbols[name] <= RealVal(str(spec["max"])))
                elif kind == "string":
                    symbols[name] = String(name)
                else:
                    raise ValueError(f"Unsupported Z3 variable type for {name!r}.")

            def compile_term(node: Any) -> Any:
                """Compile the same PROforma expression tree, not a second DSL."""
                if isinstance(node, bool): return BoolVal(node)
                if isinstance(node, int): return IntVal(node)
                if isinstance(node, float): return RealVal(str(node))
                if isinstance(node, str): return StringVal(node)
                if not isinstance(node, dict): raise ValueError("Unsupported PROforma term.")
                if set(node) == {"ref"}:
                    name = node["ref"]
                    if name not in symbols: raise ValueError(f"Undeclared PROforma reference: {name}")
                    return symbols[name]
                op = node.get("op")
                args = node.get("args", [])
                if op in {"and", "all", "or", "any"}:
                    compiled = [compile_term(arg) for arg in args]
                    return And(*compiled) if op in {"and", "all"} else Or(*compiled)
                if op == "not" and len(args) == 1:
                    return Not(compile_term(args[0]))
                if op == "implies" and len(args) == 2:
                    return Implies(compile_term(args[0]), compile_term(args[1]))
                left_node = node.get("left", args[0] if len(args) > 0 else None)
                right_node = node.get("right", args[1] if len(args) > 1 else None)
                left = compile_term(left_node); right = compile_term(right_node)
                operators = {
                    "eq": lambda: left == right,
                    "equals": lambda: left == right,
                    "neq": lambda: left != right,
                    "not_equals": lambda: left != right,
                    "gt": lambda: left > right,
                    "gte": lambda: left >= right,
                    "lt": lambda: left < right,
                    "lte": lambda: left <= right,
                }
                if op not in operators:
                    raise ValueError(f"PROforma operator {op!r} is outside the SMT-compiled subset.")
                return operators[op]()

            for item in context.get("constraints", []):
                solver.add(compile_term(item))
            target = compile_term(expression)
            if str(target.sort()) != "Bool":
                raise ValueError("Z3 rule expression must be Boolean.")
            baseline = solver.check()
            if baseline != sat:
                return {"decision": "abstain", "reason": f"Declared constraints are not satisfiable ({baseline}).", "trace": [{"solver": "z3", "base": str(baseline)}]}
            solver.push(); solver.add(Not(target)); counterexample = solver.check(); solver.pop()
            if counterexample == unsat:
                return {"decision": "pass", "reason": "The predicate is entailed by the declared constraints.",
                        "trace": [{"solver": "z3", "counterexample_check": str(counterexample), "proof": "entailed"}]}
            solver.push(); solver.add(target); witness = solver.check(); solver.pop()
            if witness == unsat:
                return {"decision": "fail", "reason": "The negation of the predicate is entailed by the declared constraints.",
                        "trace": [{"solver": "z3", "witness_check": str(witness), "proof": "refuted"}]}
            return {"decision": "abstain", "reason": "The predicate is not entailed or refuted by the declared constraints.",
                    "trace": [{"solver": "z3", "counterexample_check": str(counterexample), "witness_check": str(witness)}]}
        except Exception as exc:
            return {"decision": "abstain", "reason": f"PROforma-to-Z3 compilation unsupported or undecidable: {exc}", "trace": []}
