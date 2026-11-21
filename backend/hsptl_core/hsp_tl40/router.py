"""Predicate routing, deterministic sequencing, IRT and FSRS derived views."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from ..deterministic_intelligence.engine import DeterministicIntelligenceEngine
from ..scheduling import CardState, get_scheduler
from .explain import derive
from .argumentation import evaluate_decision
from .guards import Guards
from .kernel import EventKernel
from .proforma import evaluate


class Router:
    def __init__(self, kernel: EventKernel, guards: Guards,
                 engine: DeterministicIntelligenceEngine):
        self.kernel, self.guards, self.engine = kernel, guards, engine

    def eligibility(self, expression: Any, context: dict[str, Any]) -> dict[str, Any]:
        result = self.guards.decide("G-ROUTE-ELIGIBILITY-001", expression, context,
                                    rule_id="PROFORMA-ROUTE-001")
        derivation = derive(output_type="route.eligibility", output={"decision": result.decision},
                           rules=["PROFORMA-ROUTE-001"], inputs=[{"context_keys": sorted(context)}],
                           steps=result.trace)
        return {**result.as_dict(), "derivation": derivation}

    @staticmethod
    def topological_order(graph: dict[str, list[str]]) -> dict[str, Any]:
        nodes = set(graph)
        for dependencies in graph.values():
            nodes.update(dependencies)
        remaining = {node: set(graph.get(node, [])) for node in nodes}
        order: list[str] = []
        trace: list[dict[str, Any]] = []
        while remaining:
            ready = sorted(node for node, dependencies in remaining.items() if not dependencies)
            if not ready:
                return {"state": "fail", "order": [], "reason": "Prerequisite graph contains a cycle.",
                        "remaining": {key: sorted(value) for key, value in remaining.items()},
                        "derivation": derive(output_type="curriculum.order", output=None,
                            rules=["CURRICULUM-DAG-001"], steps=trace)}
            for node in ready:
                order.append(node)
                trace.append({"step": len(trace) + 1, "selected": node,
                              "reason": "all prerequisites already ordered"})
                remaining.pop(node)
            for dependencies in remaining.values():
                dependencies.difference_update(ready)
        return {"state": "pass", "order": order, "trace": trace,
                "derivation": derive(output_type="curriculum.order", output=order,
                    rules=["CURRICULUM-DAG-001", "DETERMINISTIC-KAHN-001"], steps=trace)}

    def route(self, object_id: str, workspace: str, expression: Any,
              context: dict[str, Any]) -> dict[str, Any]:
        eligibility = self.eligibility(expression, context)
        if eligibility["decision"] != "pass":
            return {"state": eligibility["decision"], "eligibility": eligibility}
        with self.engine.connect() as conn:
            exists = conn.execute("SELECT 1 FROM di_learning_objects WHERE object_id=?", (object_id,)).fetchone()
        # HSPTL 4.0 composed objects are also first-class event projections.
        if not exists:
            for event in reversed(self.kernel.platform_events(limit=10000)):
                if event["event_type"] == "platform.learning_object.composed" and event["payload"].get("object", {}).get("object_id") == object_id:
                    exists = True
                    break
        object_guard = self.guards.structural("G-ROUTE-OBJECT-001", bool(exists),
            "Learning object is canonical." if exists else "Learning object is not canonical.",
            {"object_id": object_id})
        if object_guard.decision != "pass":
            return {"state": object_guard.decision, "guard": object_guard.as_dict()}
        payload = {"object_id": object_id, "workspace": workspace,
                   "attributes": context, "predicate": expression,
                   "eligibility": eligibility["decision"]}
        event = self.kernel.append("platform.route.decided", payload)
        derivation = derive(output_type="workspace.route", output={"object_id": object_id,
                           "workspace": workspace, "routed": True},
                           rules=["PROFORMA-ROUTE-001"], inputs=[{"object_id": object_id,
                           "workspace": workspace}], steps=eligibility["derivation"]["steps"],
                           source_events=[{"event_id": event["event_id"], "seq": event["seq"]}])
        return {"state": "pass", "route": payload, "event": event, "derivation": derivation}

    @staticmethod
    def estimate_irt(responses: list[dict[str, Any]], *, prior_precision: float = 0.0625,
                     max_iterations: int = 40) -> dict[str, Any]:
        """Regularized 2PL IRT ability estimate with deterministic Newton steps.

        Item difficulties/discriminations are authored parameters, not learned
        by the runtime. The weak normal prior prevents infinite estimates for
        all-correct/all-incorrect response patterns.
        """
        if not responses:
            return {"state": "abstain", "reason": "At least one scored response is required."}
        rows = []
        for index, item in enumerate(responses):
            if not isinstance(item, dict) or not isinstance(item.get("correct"), bool):
                return {"state": "abstain", "reason": f"Response {index} has no explicit correctness value."}
            try:
                difficulty = float(item["difficulty"])
                discrimination = float(item.get("discrimination", 1.0))
            except (TypeError, ValueError):
                return {"state": "abstain", "reason": f"Response {index} has invalid IRT parameters."}
            if not math.isfinite(difficulty) or not math.isfinite(discrimination) or discrimination <= 0:
                return {"state": "abstain", "reason": f"Response {index} has invalid IRT parameters."}
            rows.append((bool(item["correct"]), difficulty, discrimination))

        theta = 0.0
        iterations = 0
        for iterations in range(1, max_iterations + 1):
            score = -prior_precision * theta
            information = prior_precision
            for correct, difficulty, discrimination in rows:
                z = max(-35.0, min(35.0, discrimination * (theta - difficulty)))
                probability = 1.0 / (1.0 + math.exp(-z))
                score += discrimination * ((1.0 if correct else 0.0) - probability)
                information += discrimination * discrimination * probability * (1.0 - probability)
            delta = score / information
            theta_next = max(-4.0, min(4.0, theta + delta))
            if abs(theta_next - theta) < 1e-7:
                theta = theta_next
                break
            theta = theta_next
        information = prior_precision
        for _, difficulty, discrimination in rows:
            z = max(-35.0, min(35.0, discrimination * (theta - difficulty)))
            probability = 1.0 / (1.0 + math.exp(-z))
            information += discrimination * discrimination * probability * (1.0 - probability)
        trace = [{"item": index, "correct": correct, "difficulty": difficulty,
                  "discrimination": discrimination}
                 for index, (correct, difficulty, discrimination) in enumerate(rows)]
        output = {"theta": round(theta, 6), "standard_error": round(math.sqrt(1.0 / information), 6),
                  "responses": len(rows), "correct": sum(x[0] for x in rows),
                  "iterations": iterations, "estimator": "2PL logistic IRT with fixed item parameters and weak normal prior"}
        return {"state": "pass", **output,
                "derivation": derive(output_type="assessment.irt", output=output,
                    rules=["IRT-2PL-MLE-001"], inputs=trace,
                    steps=[{"step": "newton-raphson", "iterations": iterations,
                            "prior_precision": prior_precision}])}


    @staticmethod
    def coverage_gaps(required: list[str], covered: list[str]) -> dict[str, Any]:
        required_set, covered_set = set(required), set(covered)
        missing = sorted(required_set - covered_set)
        return {"state": "pass", "missing": missing,
                "covered": sorted(required_set & covered_set),
                "unmapped": sorted(covered_set - required_set),
                "derivation": derive(output_type="coverage.gaps", output=missing,
                    rules=["SET-DIFFERENCE-001"], inputs=[
                        {"required": sorted(required_set)}, {"covered": sorted(covered_set)}])}

    def record_mastery_signal(self, competency_id: str, learner_id: str,
                              signal: str, evidence_ref: str, reviewer: str) -> dict[str, Any]:
        allowed = {"demonstrated", "needs_reinforcement", "not_assessed"}
        if signal not in allowed or not all([competency_id, learner_id, evidence_ref, reviewer]):
            raise ValueError("Mastery signal requires a known state, competency, learner, evidence reference and reviewer.")
        event = self.kernel.append("platform.mastery.signal_recorded", {
            "competency_id": competency_id, "learner_id": learner_id, "signal": signal,
            "evidence_ref": evidence_ref, "reviewer": reviewer,
            "scope": "formative_learning_signal_not_clinical_competence"})
        return {"recorded": True, "event": event,
                "note": "This signal is formative and does not confer clinical competence or privileges."}

    def mastery_fold(self, learner_id: str | None = None) -> dict[str, Any]:
        state: dict[tuple[str, str], dict[str, Any]] = {}
        events = self.kernel.platform_events(limit=10000)
        for event in events:
            if event["event_type"] != "platform.mastery.signal_recorded":
                continue
            payload = event["payload"]
            if learner_id and payload.get("learner_id") != learner_id:
                continue
            key = (payload["learner_id"], payload["competency_id"])
            current = state.setdefault(key, {"attempts": 0, "signal": "not_assessed", "history": []})
            current["attempts"] += 1
            current["signal"] = payload["signal"]
            current["history"].append({"event_id": event["event_id"], "seq": event["seq"],
                                       "signal": payload["signal"], "reviewer": payload["reviewer"],
                                       "evidence_ref": payload["evidence_ref"]})
        output = [{"learner_id": key[0], "competency_id": key[1], **value}
                  for key, value in sorted(state.items())]
        return {"state": "pass", "items": output,
                "projection": "derived event fold; no mastery value is stored",
                "scope": "formative learning signal, not clinical competence"}


    @staticmethod
    def brier_score(predictions: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute a deterministic Brier score from explicit forecasts/outcomes."""
        if not predictions:
            return {"state": "abstain", "reason": "Brier calibration requires at least one forecast/outcome pair."}
        scores = []
        trace = []
        for index, item in enumerate(predictions):
            try:
                probability = float(item["probability"])
                outcome = item["outcome"]
            except (KeyError, TypeError, ValueError):
                return {"state": "abstain", "reason": f"Calibration row {index} is malformed."}
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0 or outcome not in (0, 1, False, True):
                return {"state": "abstain", "reason": f"Calibration row {index} has an invalid probability or binary outcome."}
            score = (probability - float(outcome)) ** 2
            scores.append(score)
            trace.append({"index": index, "probability": probability,
                          "outcome": int(outcome), "squared_error": round(score, 8)})
        value = sum(scores) / len(scores)
        output = {"brier_score": round(value, 8), "observations": len(scores),
                  "interpretation": "lower is better; this is a calibration summary, not a clinical probability"}
        return {"state": "pass", **output,
                "derivation": derive(output_type="calibration.brier", output=output,
                    rules=["BRIER-SCORE-001"], inputs=trace,
                    steps=[{"aggregation": "mean_squared_probability_error"}])}

    @staticmethod
    def _irt_success_probability(theta: float, difficulty: float,
                                 discrimination: float = 1.0) -> float:
        z = max(-35.0, min(35.0, discrimination * (theta - difficulty)))
        return 1.0 / (1.0 + math.exp(-z))

    def reasoned_sequence(self, candidates: list[dict[str, Any]], *,
                          responses: list[dict[str, Any]] | None = None,
                          completed_prerequisites: list[str] | None = None,
                          calibration_history: list[dict[str, Any]] | None = None,
                          today: str | None = None,
                          target_success_probability: float = 0.65,
                          brier_threshold: float = 0.20) -> dict[str, Any]:
        """Build argument profiles for every proposed learning object.

        IRT, FSRS due state, prerequisite satisfaction and Brier calibration
        each contribute a separately identified PROforma-style argument.
        Candidates with missing prerequisites are reported but never made
        routeable. No candidate is silently selected.
        """
        if not candidates:
            return {"state": "abstain", "reason": "At least one candidate is required."}
        if not 0.0 < target_success_probability < 1.0 or not 0.0 <= brier_threshold <= 1.0:
            return {"state": "abstain", "reason": "Target success probability and Brier threshold are invalid."}
        today_value = today or date.today().isoformat()
        try:
            current_day = date.fromisoformat(today_value)
        except ValueError:
            return {"state": "abstain", "reason": "today must be an ISO date."}
        completed = set(completed_prerequisites or [])
        irt = self.estimate_irt(responses or [])
        brier = self.brier_score(calibration_history or [])
        proposals = []
        blocked = []
        trace = [{"source": "IRT", "result": irt}, {"source": "Brier", "result": brier}]

        for candidate in candidates:
            if not isinstance(candidate, dict) or not candidate.get("object_id"):
                return {"state": "abstain", "reason": "Every candidate requires object_id."}
            object_id = str(candidate["object_id"])
            args: list[dict[str, Any]] = []

            # IRT argument: favour items close to the authored target challenge.
            if irt.get("state") == "pass" and candidate.get("irt_difficulty") is not None:
                try:
                    difficulty = float(candidate["irt_difficulty"])
                    discrimination = float(candidate.get("irt_discrimination", 1.0))
                    if not math.isfinite(difficulty) or not math.isfinite(discrimination) or discrimination <= 0:
                        raise ValueError
                    probability = self._irt_success_probability(irt["theta"], difficulty, discrimination)
                    closeness = max(0.0, 1.0 - abs(probability - target_success_probability) / 0.5)
                    polarity = "for" if closeness > 0.0 else "against"
                    weight = round(1.5 * closeness if polarity == "for" else min(1.5, abs(probability - target_success_probability)), 8)
                    args.append({"id": f"{object_id}:irt", "polarity": polarity, "weight": weight,
                                 "status": "pass", "label": "IRT challenge fit",
                                 "evidence": [{"type": "irt_estimate", "theta": irt["theta"],
                                               "success_probability": round(probability, 8),
                                               "target": target_success_probability}]})
                except (TypeError, ValueError):
                    args.append({"id": f"{object_id}:irt", "polarity": "against", "weight": 0,
                                 "status": "abstain", "label": "IRT input unavailable", "reason": "Invalid item parameters."})
            else:
                args.append({"id": f"{object_id}:irt", "polarity": "against", "weight": 0,
                             "status": "abstain", "label": "IRT input unavailable",
                             "reason": irt.get("reason", "Candidate has no IRT difficulty parameter.")})

            # FSRS argument: an already-due card supports a review object.
            card = candidate.get("fsrs_card")
            if isinstance(card, dict) and card.get("due_date"):
                try:
                    due = date.fromisoformat(str(card["due_date"])[:10])
                    is_due = due <= current_day
                    fsrs_projection = None
                    if candidate.get("fsrs_grade"):
                        fsrs_projection = self.fsrs_next_review(card, str(candidate["fsrs_grade"]), today=today_value)
                    args.append({"id": f"{object_id}:fsrs", "polarity": "for" if is_due else "against",
                                 "weight": 1.5 if is_due else 0.75, "status": "pass",
                                 "label": "FSRS review timing", "evidence": [{"due_date": due.isoformat(),
                                 "today": today_value, "is_due": is_due, "projection": fsrs_projection}]})
                except ValueError:
                    args.append({"id": f"{object_id}:fsrs", "polarity": "against", "weight": 0,
                                 "status": "abstain", "label": "FSRS input unavailable", "reason": "Invalid due date."})
            else:
                args.append({"id": f"{object_id}:fsrs", "polarity": "against", "weight": 0,
                             "status": "abstain", "label": "FSRS input unavailable",
                             "reason": "No FSRS due-date state supplied."})

            # Prerequisite argument is also a hard routing gate.
            required = candidate.get("prerequisites", [])
            if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
                return {"state": "abstain", "reason": f"Candidate {object_id} has malformed prerequisites."}
            missing = sorted(set(required) - completed)
            prereq_ok = not missing
            args.append({"id": f"{object_id}:prerequisites", "polarity": "for" if prereq_ok else "against",
                         "weight": 2.0, "status": "pass" if prereq_ok else "fail",
                         "label": "Prerequisite satisfaction",
                         "evidence": [{"required": sorted(set(required)), "completed": sorted(completed),
                                       "missing": missing}]})

            # Brier argument: support objects that explicitly address poor
            # calibration; do not infer learner calibration without outcomes.
            relevance = candidate.get("calibration_relevance", 0.0)
            try:
                relevance = float(relevance)
                if not math.isfinite(relevance) or not 0.0 <= relevance <= 1.0:
                    raise ValueError
            except (TypeError, ValueError):
                relevance = 0.0
            if brier.get("state") == "pass":
                high_error = brier["brier_score"] > brier_threshold
                weight = round(abs(brier["brier_score"] - brier_threshold) * 2.0 * relevance, 8)
                args.append({"id": f"{object_id}:brier", "polarity": "for" if high_error else "against",
                             "weight": weight, "status": "pass", "label": "Brier calibration need",
                             "evidence": [{"brier_score": brier["brier_score"],
                                           "threshold": brier_threshold, "relevance": relevance}]})
            else:
                args.append({"id": f"{object_id}:brier", "polarity": "against", "weight": 0,
                             "status": "abstain", "label": "Brier calibration unavailable",
                             "reason": brier.get("reason", "Calibration history unavailable.")})

            item = {"id": object_id, "label": candidate.get("title", object_id),
                    "arguments": args, "when": True}
            if prereq_ok:
                proposals.append(item)
            else:
                blocked.append({"object_id": object_id, "missing_prerequisites": missing,
                                "arguments": args, "routeable": False})
            trace.append({"candidate_id": object_id, "arguments": args,
                          "prerequisite_gate": {"pass": prereq_ok, "missing": missing}})

        if not proposals:
            return {"state": "blocked", "proposals": [], "blocked_candidates": blocked,
                    "reason": "No candidate has satisfied prerequisites.",
                    "derivation": derive(output_type="learning.sequence", output=[],
                        rules=["IRT-ARGUMENT-001", "FSRS-ARGUMENT-001", "PREREQUISITE-ARGUMENT-001", "BRIER-ARGUMENT-001"],
                        steps=trace)}
        decision = evaluate_decision({"id": "reasoned-learning-sequence", "options": proposals}, {})
        if decision.get("state") != "pass":
            return {"state": "abstain", "decision": decision, "blocked_candidates": blocked,
                    "reason": "At least one candidate argument could not be evaluated."}
        derivation = derive(output_type="learning.sequence",
            output={"preferred_candidates": decision.get("preferred_candidates"),
                    "profiles": decision.get("profiles"), "blocked": [x["object_id"] for x in blocked]},
            rules=["IRT-ARGUMENT-001", "FSRS-ARGUMENT-001", "PREREQUISITE-ARGUMENT-001", "BRIER-ARGUMENT-001"],
            inputs=[{"today": today_value, "completed_prerequisites": sorted(completed),
                     "candidate_ids": [str(x["object_id"]) for x in candidates]}],
            steps=trace + [{"argumentation": decision}])
        return {"state": "pass", "proposals": decision["profiles"],
                "preferred_candidates": decision["preferred_candidates"],
                "blocked_candidates": blocked, "automatic_selection": False,
                "argumentation": decision, "irt": irt, "brier": brier,
                "derivation": derivation}

    @staticmethod
    def fsrs_next_review(card: dict[str, Any], grade: str, *, today: str | None = None) -> dict[str, Any]:
        try:
            state = CardState(
                card_id=str(card.get("card_id", "derived-card")),
                state=str(card.get("state", "new")),
                interval_days=int(card.get("interval_days", 0)),
                repetitions=int(card.get("repetitions", 0)),
                lapses=int(card.get("lapses", 0)),
                stability=float(card.get("stability", 0.0)),
                difficulty=float(card.get("difficulty", 0.0)),
                due_date=str(card.get("due_date", "")),
                last_reviewed=str(card.get("last_reviewed", "")),
            )
            result = get_scheduler("fsrs").next_review(state, grade, date.fromisoformat(today) if today else date.today())
        except (KeyError, TypeError, ValueError) as exc:
            return {"state": "abstain", "reason": f"Invalid FSRS input: {exc}"}
        output = {"due_date": result.due_date, "interval_days": result.interval_days,
                  "card_state": result.state, "repetitions": result.repetitions,
                  "lapses": result.lapses, "stability": result.stability,
                  "difficulty": result.difficulty, "scheduler": result.scheduler,
                  "diagnostics": result.diagnostics}
        return {"state": "pass", **output,
                "derivation": derive(output_type="review.fsrs", output=output,
                    rules=["FSRS-STYLE-PREVIEW-001"],
                    inputs=[{"card": card, "grade": grade, "today": today or date.today().isoformat()}],
                    steps=[{"interval_days": result.interval_days,
                            "stability": result.stability, "difficulty": result.difficulty}])}
