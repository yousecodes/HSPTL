"""In-process Clingo adapter over canonical event-log projections."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

RULESET_PATH = Path(__file__).with_name("asp_rules") / "pathway_temporal_v1.lp"
RULESET_ID = "pathway-temporal/1.1"


def _asp_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


class TemporalReasoner:
    """Run versioned ASP data in-process; return abstention if Clingo is absent."""

    def __init__(self, ruleset_path: Path | None = None):
        self.ruleset_path = ruleset_path or RULESET_PATH

    def analyze(self, events: list[dict[str, Any]], plan: dict[str, Any],
                enactment_id: str, subject_id: str | None = None) -> dict[str, Any]:
        try:
            import clingo
        except Exception as exc:
            return {"state": "abstain", "reason": f"Clingo library unavailable: {exc}",
                    "ruleset": RULESET_ID, "recognized_states": [],
                    "deviations": [], "prerequisite_ready": {}}
        try:
            program = self.ruleset_path.read_text(encoding="utf-8")
            digest = hashlib.sha256(program.encode("utf-8")).hexdigest()
            scoped_subject = subject_id or plan.get("patient_id") or plan.get("subject_id")
            facts = self._event_facts(events, enactment_id, str(scoped_subject) if scoped_subject else None)
            # Routing is evaluated before the next task's step event is appended.
            # Give ASP an explicit next canonical sequence so prerequisites must
            # have completed earlier in the same enactment, not merely eventually.
            head_sequence = max((int(item.get("seq", 0)) for item in events), default=0)
            facts.append(f"current_sequence({_asp_string(enactment_id)},{head_sequence + 1}).")
            facts.extend(self._plan_facts(plan, enactment_id))
            control = clingo.Control(["--warn=none", "--models=0"])
            control.add("base", [], program + "\n" + "\n".join(facts) + "\n")
            control.ground([("base", [])])
            models: list[list[str]] = []
            with control.solve(yield_=True) as handle:
                for model in handle:
                    models.append(sorted(str(symbol) for symbol in model.symbols(shown=True)))
            if not models:
                return {"state": "abstain", "reason": "ASP program produced no model.",
                        "ruleset": RULESET_ID, "ruleset_hash": digest,
                        "recognized_states": [], "deviations": [], "prerequisite_ready": {}}
            # The core ruleset is deterministic and stratified. If an extension
            # later introduces multiple models, preserve the intersection only.
            common = set(models[0])
            for model in models[1:]:
                common.intersection_update(model)
            shown = sorted(common)
            recognized = [item for item in shown if item.startswith("recognized_state(")]
            deviations = [item for item in shown if item.startswith("pathway_deviation(")]
            deviation_sources = []
            for event in events:
                event_id = event.get("event_id")
                if event_id and any(_asp_string(event_id) in atom for atom in deviations):
                    payload = event.get("payload", {})
                    deviation_sources.append({"event_id": event_id, "seq": event.get("seq"),
                                              "task_id": payload.get("task_id"),
                                              "event_type": event.get("event_type")})
            ready: dict[str, bool] = {}
            for task in plan.get("tasks", []):
                task_id = task.get("id")
                if isinstance(task_id, str):
                    ready[task_id] = f"prerequisite_ready({_asp_string(enactment_id)},{_asp_string(task_id)})" in shown
                    if not task.get("requires_before"):
                        ready[task_id] = True
            missing = [item for item in shown if item.startswith("temporal_missing(")]
            satisfied = [item for item in shown if item.startswith("temporal_satisfied(")]
            clinical_states = [item for item in shown if item.startswith("clinical_state(")]
            clinical_conflicts = [item for item in shown if item.startswith("clinical_state_conflict(")]
            state = "fail" if deviations else "pass"
            return {"state": state, "ruleset": RULESET_ID, "ruleset_hash": digest,
                    "recognized_states": recognized, "deviations": deviations,
                    "deviation_sources": deviation_sources,
                    "prerequisite_ready": ready, "temporal_missing": missing,
                    "temporal_satisfied": satisfied, "clinical_states": clinical_states,
                    "clinical_conflicts": clinical_conflicts, "shown_atoms": shown,
                    "model_count": len(models)}
        except Exception as exc:
            return {"state": "abstain", "reason": f"In-process ASP execution failed: {exc}",
                    "ruleset": RULESET_ID, "recognized_states": [],
                    "deviations": [], "prerequisite_ready": {}}

    @staticmethod
    def _event_facts(events: list[dict[str, Any]], enactment_id: str,
                     subject_id: str | None = None) -> list[str]:
        facts: list[str] = []
        for event in events:
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            etype = event.get("event_type")
            if etype == "platform.pulse.observation_recorded":
                for item in payload.get("clinical_state_evidence", []):
                    if (subject_id and isinstance(item, dict) and
                            item.get("patient_id") == subject_id and
                            all(item.get(k) for k in ("patient_id", "state_id", "evidence_id", "polarity"))):
                        facts.append("clinical_state_evidence(" + ",".join([
                            _asp_string(item["patient_id"]), _asp_string(item["state_id"]),
                            _asp_string(item["evidence_id"]), str(item["polarity"])
                        ]) + ").")
                continue
            if payload.get("enactment_id") != enactment_id:
                continue
            seq = int(event.get("seq", 0))
            eid = _asp_string(enactment_id)
            if etype == "platform.pathway.enacted":
                facts.append(f"pathway_started({eid},{seq}).")
            elif etype == "platform.pathway.stepped":
                task_id = payload.get("task_id")
                if isinstance(task_id, str):
                    tid = _asp_string(task_id)
                    facts.append(f"pathway_step({eid},{tid},{seq}).")
                    facts.append(f"pathway_step_source({eid},{tid},{seq},{_asp_string(event.get('event_id') or f'seq-{seq}')}).")
                    facts.append(f"task_completed({eid},{tid},{seq}).")
            elif etype == "platform.pathway.abstained":
                facts.append(f"pathway_abstained({eid},{seq}).")
            state = payload.get("state")
            if isinstance(state, dict) and state.get("status") == "completed":
                facts.append(f"pathway_finished({eid},{seq}).")
        return facts

    @staticmethod
    def _plan_facts(plan: dict[str, Any], enactment_id: str) -> list[str]:
        facts: list[str] = []
        eid = _asp_string(enactment_id)
        for task in plan.get("tasks", []):
            task_id = task.get("id")
            if not isinstance(task_id, str):
                continue
            tid = _asp_string(task_id)
            facts.append(f"pathway_task({eid},{tid}).")
            for prerequisite in task.get("requires_before", []):
                if isinstance(prerequisite, str):
                    facts.append(f"requires_before({eid},{_asp_string(prerequisite)},{tid}).")
        return facts
