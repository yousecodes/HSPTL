"""Single pass/fail/abstain interface over structural, PROforma and declared SMT rules."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..deterministic_intelligence.engine import DeterministicIntelligenceEngine
from .explain import derive
from .kernel import EventKernel
from .proforma import evaluate
from .provability import Z3DecisionAdapter, classify_rule


@dataclass(frozen=True)
class GuardResult:
    decision: str
    guard_id: str
    reason: str
    trace: list[dict[str, Any]]
    audit_event: dict[str, Any] | None = None
    rule_id: str | None = None
    provability: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class Guards:
    def __init__(self, kernel: EventKernel, engine: DeterministicIntelligenceEngine,
                 z3_adapter: Z3DecisionAdapter | None = None):
        self.kernel = kernel
        self.engine = engine
        self.z3_adapter = z3_adapter or Z3DecisionAdapter()

    def _audit(self, guard_id: str, decision: str, reason: str,
               context: dict[str, Any], trace: list[dict[str, Any]],
               rule_id: str | None = None) -> dict[str, Any]:
        event_type = "platform.guard.checked" if decision in {"pass", "fail"} else "platform.guard.abstained"
        return self.kernel.append(event_type, {
            "guard_id": guard_id, "decision": decision, "reason": reason,
            "rule_id": rule_id, "context": context, "trace": trace,
        })

    def decide(self, guard_id: str, expression: Any, context: dict[str, Any],
               *, rule_id: str = "PROFORMA-GUARD-001") -> GuardResult:
        policy = classify_rule(rule_id)
        classification = policy["classification"]
        trace: list[dict[str, Any]] = [{"rule_id": rule_id, "provability": classification,
                                       "solver": policy["solver"]}]
        if classification == "unclassified":
            decision = "abstain"
            reason = policy["rationale"]
        elif classification == "z3_required":
            result = self.z3_adapter.decide(expression, context)
            decision, reason = result["decision"], result["reason"]
            trace.extend(result.get("trace", []))
        else:
            evaluated = evaluate(expression, context)
            decision = evaluated.state
            reason = {
                "pass": "Predicate is proven true by the registered non-SMT rule.",
                "fail": "Predicate is proven false by the registered non-SMT rule.",
                "abstain": "Predicate is unknown or contains an unsupported construct.",
            }[decision]
            trace.extend(evaluated.trace)
        event = self._audit(guard_id, decision, reason, context, trace, rule_id)
        return GuardResult(decision, guard_id, reason, trace, event, rule_id, policy)

    def structural(self, guard_id: str, ok: bool | None, reason: str,
                   context: dict[str, Any] | None = None) -> GuardResult:
        decision = "pass" if ok is True else "fail" if ok is False else "abstain"
        event = self._audit(guard_id, decision, reason, context or {}, [], "STRUCTURAL-IDENTITY-001")
        return GuardResult(decision, guard_id, reason, [], event, "STRUCTURAL-IDENTITY-001",
                           classify_rule("STRUCTURAL-IDENTITY-001"))

    def optional_solver(self, context: dict[str, Any], *, required: bool = False,
                        rule_id: str = "SMT-SAFETY-001") -> GuardResult:
        """Run Z3 only when the requested rule is explicitly classified as z3_required."""
        policy = classify_rule(rule_id)
        if policy["classification"] != "z3_required":
            reason = "Solver invocation refused: rule is not classified as z3_required."
            event = self._audit("G-SMT-POLICY-001", "abstain", reason, context, [], rule_id)
            return GuardResult("abstain", "G-SMT-POLICY-001", reason, [], event, rule_id, policy)
        if not required:
            return self.structural("G-SMT-OPTIONAL-001", True,
                "This call did not request the registered SMT rule; no solver was invoked.", context)
        expression = context.get("expression")
        if expression is not None:
            return self.decide("G-SMT-OPTIONAL-001", expression, context, rule_id=rule_id)
        try:
            result = self.engine.verify_safety_properties()
            reason = "Registered SMT safety implications were proven."
            trace = [{"solver": "z3", **result}]
            event = self._audit("G-SMT-OPTIONAL-001", "pass", reason, context, trace, rule_id)
            return GuardResult("pass", "G-SMT-OPTIONAL-001", reason, trace, event, rule_id, policy)
        except Exception as exc:
            reason = f"SMT proof unavailable or undecidable: {exc}"
            trace = [{"solver": "z3", "result": "abstain"}]
            event = self._audit("G-SMT-OPTIONAL-001", "abstain", reason, context, trace, rule_id)
            return GuardResult("abstain", "G-SMT-OPTIONAL-001", reason, trace, event, rule_id, policy)
