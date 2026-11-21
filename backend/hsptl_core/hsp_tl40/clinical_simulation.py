"""Deterministic, event-backed clinical teaching simulation vertical slice.

This is a bounded educational model, not a validated physiological simulator or
clinical decision support system. Simulation state is reconstructed from the
canonical HSPTL event ledger; no parallel run database is introduced.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from .event_contracts import canonical_json, payload_digest
from .explain import derive
from .model_library import load_model
from .proforma import LOGIC_VERSION, ProformaError, ProformaRuntime, evaluate

ENGINE_VERSION = "HSPTL-SimulationRuntime/1.0.0"
SEED_ALGORITHM = "sha256-seed-variant-v1"
SIMULATION_EVENT_TYPES = {
    "simulation.run.started", "simulation.event.scheduled", "simulation.action.requested",
    "simulation.action.accepted", "simulation.action.rejected", "simulation.clock.advanced",
    "simulation.event.fired", "simulation.event.skipped", "simulation.state.transitioned",
    "simulation.observation.released", "simulation.result.available",
    "simulation.document.saved", "simulation.order.entered", "simulation.handover.submitted",
    "simulation.assessment.derived", "simulation.debrief.completed",
    "simulation.run.completed", "simulation.run.abandoned",
}


class SimulationError(ValueError):
    """Invalid scenario, run or simulation operation."""


class SimulationConflict(SimulationError):
    """A valid operation conflicts with the run's current lifecycle state."""


class ScenarioCatalog:
    def __init__(self, root: Path | None = None, additional_roots: list[Path] | None = None):
        self.root = root or (Path(__file__).resolve().parents[3] / "fixtures" / "scenarios")
        self.roots = [*(additional_roots or []), self.root]

    def _path(self, scenario_id: str) -> Path:
        if not scenario_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in scenario_id):
            raise KeyError(scenario_id)
        for root in self.roots:
            path = (root / scenario_id / "scenario.json").resolve()
            if root.resolve() in path.parents and path.is_file():
                return path
        raise KeyError(scenario_id)

    def load(self, scenario_id: str) -> dict[str, Any]:
        path = self._path(scenario_id)
        try:
            scenario = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SimulationError(f"Scenario package could not be read: {exc}") from exc
        errors = self.validate(scenario)
        if errors:
            raise SimulationError("Invalid scenario package: " + "; ".join(errors))
        return scenario

    @staticmethod
    def validate(scenario: Any) -> list[str]:
        if not isinstance(scenario, dict):
            return ["Scenario must be a JSON object."]
        errors: list[str] = []
        for key in ("scenario_id", "version", "title", "patient", "initial_state", "action_catalogue", "assessment"):
            if key not in scenario:
                errors.append(f"Missing required scenario field: {key}.")
        if not isinstance(scenario.get("patient"), dict) or not scenario.get("patient", {}).get("synthetic"):
            errors.append("The first simulation scenario must explicitly identify a synthetic patient.")
        actions = scenario.get("action_catalogue")
        if not isinstance(actions, dict) or not actions:
            errors.append("Scenario action_catalogue must be a non-empty object.")
        else:
            for action_id, action in actions.items():
                if not isinstance(action, dict) or not isinstance(action.get("model_path"), str):
                    errors.append(f"Action {action_id} requires a PROforma model_path.")
        rubric = scenario.get("assessment", {}).get("criteria", []) if isinstance(scenario.get("assessment"), dict) else []
        if not isinstance(rubric, list) or sum(int(item.get("points", 0)) for item in rubric if isinstance(item, dict)) != 100:
            errors.append("Formative rubric criteria must be a list totaling exactly 100 points.")
        if scenario.get("clinical_review_status") != "approved":
            # Draft scenarios may run in local development, but this status is explicit in all outputs.
            if not str(scenario.get("clinical_review_status", "")).startswith("draft_"):
                errors.append("Scenario clinical_review_status must be an explicit draft or approved status.")
        return errors

    def list_public(self) -> list[dict[str, Any]]:
        result = []
        seen: set[str] = set()
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*/scenario.json")):
                try:
                    scenario = json.loads(path.read_text(encoding="utf-8"))
                    scenario_id = str(scenario.get("scenario_id", ""))
                    if scenario_id and scenario_id not in seen:
                        result.append(self.public_summary(scenario))
                        seen.add(scenario_id)
                except (OSError, json.JSONDecodeError):
                    continue
        return result

    @staticmethod
    def public_summary(scenario: dict[str, Any]) -> dict[str, Any]:
        patient = scenario.get("patient", {})
        return {
            "scenario_id": scenario.get("scenario_id"), "version": scenario.get("version"),
            "title": scenario.get("title"), "specialty": scenario.get("specialty"),
            "setting": scenario.get("setting"), "learner_level": scenario.get("learner_level"),
            "clinical_review_status": scenario.get("clinical_review_status"),
            "intended_use": scenario.get("intended_use"),
            "educational_purpose": scenario.get("educational_purpose"),
            "learning_objectives": scenario.get("learning_objectives", []),
            "patient": {"synthetic": True, "display_id": patient.get("display_id"),
                        "age_years": patient.get("age_years"), "presenting_complaint": patient.get("presenting_complaint")},
            "source_basis": scenario.get("source_basis", []),
            "simulation_model": scenario.get("simulation_model", {}),
        }


class ClinicalSimulationRuntime:
    def __init__(self, kernel, proforma: ProformaRuntime, catalog: ScenarioCatalog | None = None):
        self.kernel = kernel
        self.proforma = proforma
        self.catalog = catalog or ScenarioCatalog()

    def list_scenarios(self) -> dict[str, Any]:
        items = self.catalog.list_public()
        return {"items": items, "count": len(items), "purpose": "synthetic_formative_education_only"}

    def start_run(self, scenario_id: str, seed: int) -> dict[str, Any]:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
            raise SimulationError("Seed must be an integer from 0 through 4294967295.")
        scenario = self.catalog.load(scenario_id)
        initial = copy.deepcopy(scenario["initial_state"])
        variants = initial.pop("heart_rate_seed_options_bpm", [])
        if not isinstance(variants, list) or not variants:
            raise SimulationError("Scenario requires deterministic heart-rate seed variants.")
        seed_digest = hashlib.sha256(f"{SEED_ALGORITHM}|{scenario_id}|{seed}".encode()).digest()
        initial["heart_rate_bpm"] = int(variants[seed_digest[0] % len(variants)])
        run_id = "simrun_" + uuid.uuid4().hex
        scenario_digest = payload_digest(scenario)
        model_digest = payload_digest(scenario["simulation_model"])
        started_payload = {
            "run_id": run_id, "scenario_id": scenario_id, "scenario_version": scenario["version"],
            "scenario_digest": scenario_digest, "simulation_model_digest": model_digest,
            "engine_version": scenario["simulation_model"].get("engine_version", ENGINE_VERSION),
            "transition_model_id": scenario["simulation_model"]["model_id"],
            "transition_model_version": scenario["simulation_model"]["version"],
            "proforma_logic_version": LOGIC_VERSION,
            "seed": seed, "seed_algorithm": SEED_ALGORITHM, "simulation_time_min": 0,
            "initial_state": initial,
        }
        self.kernel.append("simulation.run.started", started_payload)
        for scheduled in scenario.get("scheduled_events", []):
            self.kernel.append("simulation.event.scheduled", {
                "run_id": run_id, "scheduled_event_id": scheduled["event_id"],
                "due_at_minute": int(scheduled["due_at_minute"]), "priority": int(scheduled.get("priority", 100)),
                "kind": scheduled["kind"], "condition": scheduled.get("condition", "always"),
            })
        self._release_observation(run_id, "arrival", {
            "presenting_complaint": self._text_observation("Presenting complaint", scenario["patient"]["presenting_complaint"]),
            "opening_history": self._text_observation("Opening history", scenario["patient"]["opening_history"]),
            **self._vital_observations(initial, include_pef=False, previous={}),
        })
        return self.get_run(run_id)

    def _events(self, run_id: str) -> list[dict[str, Any]]:
        events = self.kernel.events(limit=10000)
        return [event for event in events if event.get("event_type", "").startswith("simulation.")
                and event.get("payload", {}).get("run_id") == run_id]

    def _fold(self, run_id: str) -> dict[str, Any]:
        events = self._events(run_id)
        started = next((event for event in events if event["event_type"] == "simulation.run.started"), None)
        if started is None:
            raise KeyError(run_id)
        payload = started["payload"]
        state = copy.deepcopy(payload["initial_state"])
        sim_time = 0
        observations: dict[str, Any] = {}
        actions: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        scheduled: list[dict[str, Any]] = []
        fired: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        documents: list[dict[str, Any]] = []
        assessment = None
        completed = False
        for event in events:
            item = event["payload"]
            kind = event["event_type"]
            if kind == "simulation.clock.advanced":
                sim_time = int(item["to_minute"])
            elif kind == "simulation.state.transitioned":
                state = copy.deepcopy(item["state_after"])
            elif kind == "simulation.observation.released":
                observations.update(copy.deepcopy(item.get("observations", {})))
            elif kind == "simulation.action.accepted":
                actions.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind == "simulation.action.rejected":
                rejected.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind == "simulation.event.scheduled":
                scheduled.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind == "simulation.event.fired":
                fired.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind == "simulation.event.skipped":
                skipped.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind in {"simulation.document.saved", "simulation.order.entered", "simulation.handover.submitted"}:
                documents.append({**item, "event_id": event["event_id"], "seq": event["seq"]})
            elif kind == "simulation.assessment.derived":
                assessment = {**item, "event_id": event["event_id"], "seq": event["seq"]}
            elif kind == "simulation.run.completed":
                completed = True
        return {"events": events, "started": payload, "state": state, "simulation_time_min": sim_time,
                "observations": observations, "actions": actions, "rejected_actions": rejected,
                "scheduled": scheduled, "fired": fired, "skipped": skipped, "documents": documents,
                "assessment": assessment, "completed": completed}

    @staticmethod
    def _text_observation(display: str, value: str) -> dict[str, Any]:
        return {"display": display, "value": value, "unit": "", "status": "Scenario-released finding"}

    @staticmethod
    def _vital_observations(state: dict[str, Any], *, include_pef: bool, previous: dict[str, Any]) -> dict[str, Any]:
        specs = {
            "heart_rate": ("Heart rate", state.get("heart_rate_bpm"), "beats/min"),
            "respiratory_rate": ("Respiratory rate", state.get("respiratory_rate_per_min"), "breaths/min"),
            "spo2": ("Oxygen saturation", state.get("spo2_percent_room_air"), "% on room air"),
            "blood_pressure": ("Blood pressure", f"{state.get('systolic_bp_mmhg')}/{state.get('diastolic_bp_mmhg')}", "mmHg"),
            "temperature": ("Temperature", state.get("temperature_c"), "°C"),
        }
        if include_pef:
            specs["peak_flow"] = ("Peak expiratory flow", state.get("pef_percent_predicted"), "% predicted")
        result = {}
        for key, (label, value, unit) in specs.items():
            history = list(previous.get(key, {}).get("history", []))
            old = previous.get(key, {}).get("value")
            if value is not None and (old is None or old != value):
                history.append(value)
            result[key] = {"display": label, "value": value, "unit": unit,
                           "status": "Simulated teaching observation", "history": history[-20:]}
        return result

    def _release_observation(self, run_id: str, stage: str, observations: dict[str, Any]) -> dict[str, Any]:
        return self.kernel.append("simulation.observation.released", {
            "run_id": run_id, "stage": stage, "simulation_time_min": self._fold(run_id)["simulation_time_min"] if self._has_started(run_id) else 0,
            "observations": observations, "observation_digest": payload_digest(observations),
        })

    def _has_started(self, run_id: str) -> bool:
        return any(event["event_type"] == "simulation.run.started" for event in self._events(run_id))

    def _facts(self, folded: dict[str, Any]) -> dict[str, Any]:
        state = folded["state"]
        return {
            "assessment_complete": bool(state.get("assessment_complete")),
            "peak_flow_ordered": bool(state.get("peak_flow_ordered")),
            "bronchodilator_given": bool(state.get("bronchodilator_given")),
            "systemic_corticosteroid_started": bool(state.get("systemic_corticosteroid_started")),
            "patient_worsening": bool(state.get("patient_worsening")),
            "senior_review_requested": bool(state.get("senior_review_requested")),
            "reassessment_complete": bool(state.get("reassessment_complete")),
            "simulation_time_min": folded["simulation_time_min"],
        }

    def _available_actions(self, scenario: dict[str, Any], folded: dict[str, Any]) -> list[dict[str, Any]]:
        facts = self._facts(folded)
        context = {"facts": facts}
        output = []
        for action_id, definition in scenario["action_catalogue"].items():
            try:
                plan = load_model(definition["model_path"])
                task = plan["tasks"][0]
                precondition = task.get("preconditions", True)
                check = evaluate(precondition, context)
                enabled = check.value is True
                reason = "Available under the current PROforma preconditions." if enabled else (
                    "Preconditions are not met." if check.value is False else "Eligibility is undecidable; action withheld.")
            except (KeyError, ValueError, IndexError) as exc:
                enabled, reason, check = False, f"Action model unavailable: {exc}", None
            output.append({"id": action_id, "label": definition["label"], "description": definition["description"],
                           "available": enabled, "reason": reason,
                           "proof_trace": check.trace if check else [], "logic_model": definition["model_path"]})
        return output

    def get_run(self, run_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        scenario = self.catalog.load(folded["started"]["scenario_id"])
        return {
            "run_id": run_id, "status": "completed" if folded["completed"] else "active",
            "scenario": self.catalog.public_summary(scenario),
            "scenario_digest": folded["started"]["scenario_digest"],
            "seed": folded["started"]["seed"], "seed_algorithm": folded["started"]["seed_algorithm"],
            "engine_version": folded["started"]["engine_version"],
            "simulation_time_min": folded["simulation_time_min"],
            "observations": folded["observations"],
            "actions": folded["actions"], "rejected_actions": folded["rejected_actions"],
            "documents": folded["documents"], "assessment": folded["assessment"],
            "available_actions": self._available_actions(scenario, folded) if not folded["completed"] else [],
            "patient_status": self._patient_status(folded["state"]),
            "debrief_prompts": scenario.get("debrief", {}).get("prompts", []),
            "review_notice": "Scenario and scoring rubric remain draft pending qualified clinical educator review.",
            "education_only": True,
        }

    @staticmethod
    def _patient_status(state: dict[str, Any]) -> str:
        if state.get("bronchodilator_response_observed"):
            return "Improvement observed in the bounded teaching model; this is not a real physiological prediction."
        if state.get("patient_worsening"):
            return "Worsening transition occurred in the bounded teaching model."
        return "Initial state; observe, assess and act within the scenario."

    def pulse_provider(self, run_id: str) -> "SimulationPulseProvider":
        return SimulationPulseProvider(self, run_id)

    def pulse_state(self, run_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        return {"connected": True, "source": "hsptl_deterministic_simulation", "sequence": folded["events"][-1]["seq"] if folded["events"] else None,
                "observations": copy.deepcopy(folded["observations"]), "status": "connected",
                "message": "Observations are produced by this synthetic scenario's versioned teaching model."}

    def perform_action(self, run_id: str, action: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(action, dict):
            raise SimulationError("Action must be an object.")
        action_id = str(action.get("id", ""))
        folded = self._fold(run_id)
        if folded["completed"]:
            raise SimulationConflict("Completed simulation runs are immutable.")
        scenario = self.catalog.load(folded["started"]["scenario_id"])
        definition = scenario["action_catalogue"].get(action_id)
        request_payload = {"run_id": run_id, "action_id": action_id,
                           "simulation_time_min": folded["simulation_time_min"],
                           "payload": {key: value for key, value in action.items() if key != "id"}}
        request_event = self.kernel.append("simulation.action.requested", request_payload)
        if definition is None:
            rejection = self.kernel.append("simulation.action.rejected", {
                "run_id": run_id, "action_id": action_id or "<missing>",
                "simulation_time_min": folded["simulation_time_min"],
                "reason": "Action is not in the scenario's typed action catalogue.",
                "guard": "scenario_action_catalogue", "request_event_id": request_event["event_id"],
            })
            return {"applied": False, "reason": "Action is not permitted by this scenario.", "event": rejection}
        try:
            plan = load_model(definition["model_path"])
            facts = self._facts(folded)
            task = plan["tasks"][0]
            check = evaluate(task.get("preconditions", True), {"facts": facts})
            if check.value is not True:
                reason = "PROforma preconditions are false." if check.value is False else "PROforma eligibility is undecidable; action withheld."
                rejection = self.kernel.append("simulation.action.rejected", {
                    "run_id": run_id, "action_id": action_id,
                    "simulation_time_min": folded["simulation_time_min"],
                    "reason": reason, "guard": "PROforma", "proof_trace": check.trace,
                    "request_event_id": request_event["event_id"],
                })
                return {"applied": False, "reason": reason, "event": rejection, "proof_trace": check.trace}
            enacted = self.proforma.enact(plan, facts=facts, metadata={"simulation_run_id": run_id, "action_id": action_id})
            enactment_id = enacted["state"]["enactment_id"]
            stepped = self.proforma.step(enactment_id, task["id"], value={"simulation_run_id": run_id})
        except (KeyError, ValueError, ProformaError) as exc:
            rejection = self.kernel.append("simulation.action.rejected", {
                "run_id": run_id, "action_id": action_id,
                "simulation_time_min": folded["simulation_time_min"], "reason": str(exc),
                "guard": "PROforma_runtime", "request_event_id": request_event["event_id"],
            })
            return {"applied": False, "reason": str(exc), "event": rejection}

        state = copy.deepcopy(folded["state"])
        accepted_count = len(folded["actions"]) + 1
        rationale = "PROforma action gate passed; the typed simulation transition was accepted."
        if action_id == "focused_assessment":
            state["assessment_complete"] = True
        elif action_id == "order_peak_flow":
            state["peak_flow_ordered"] = True
        elif action_id == "administer_bronchodilator":
            state["bronchodilator_given"] = True
        elif action_id == "start_systemic_corticosteroid":
            state["systemic_corticosteroid_started"] = True
            rationale = "The scenario records a treatment-plan action; this model does not attribute immediate physiological change to corticosteroid initiation."
        elif action_id == "escalate_for_senior_review":
            state["senior_review_requested"] = True
        elif action_id == "reassess_patient":
            state["reassessment_complete"] = True
        accepted = self.kernel.append("simulation.action.accepted", {
            "run_id": run_id, "action_id": action_id,
            "simulation_time_min": folded["simulation_time_min"],
            "proforma_plan_id": plan["id"], "proforma_task_id": task["id"],
            "proforma_logic_version": stepped["state"].get("logic_version"),
            "proforma_derivation_hash": stepped["state"].get("derivation", {}).get("derivation_hash"),
            "proforma_proof_trace": check.trace, "rationale": rationale,
        })
        self._record_state_transition(run_id, state, "learner_action:" + action_id, rationale)
        if action_id == "focused_assessment":
            patient = scenario["patient"]
            self._release_observation(run_id, "focused_assessment", {
                "history_after_assessment": self._text_observation("Focused history", canonical_json(patient["history_after_assessment"])),
                "examination_after_assessment": self._text_observation("Focused examination", canonical_json(patient["examination_after_assessment"])),
            })
        elif action_id == "order_peak_flow":
            self._schedule(run_id, f"peak-flow-result-{accepted_count}", folded["simulation_time_min"] + 2, 10,
                           "peak_flow_result", "result_when_due")
        elif action_id == "administer_bronchodilator":
            self._schedule(run_id, f"bronchodilator-response-{accepted_count}", folded["simulation_time_min"] + 20, 15,
                           "bronchodilator_response", "response_after_20_simulated_minutes")
        elif action_id == "reassess_patient":
            latest = self._fold(run_id)
            self._release_observation(run_id, "formal_reassessment", {
                "reassessment_summary": self._text_observation("Reassessment", self._patient_status(latest["state"])),
                **self._vital_observations(latest["state"], include_pef=bool(latest["state"].get("pef_measured")), previous=latest["observations"]),
            })
        return {"applied": True, "request_event": request_event, "event": accepted,
                "proforma": stepped, "run": self.get_run(run_id)}

    def _schedule(self, run_id: str, event_id: str, due_at: int, priority: int, kind: str, condition: str) -> dict[str, Any]:
        return self.kernel.append("simulation.event.scheduled", {
            "run_id": run_id, "scheduled_event_id": event_id, "due_at_minute": due_at,
            "priority": priority, "kind": kind, "condition": condition,
        })

    def _record_state_transition(self, run_id: str, state: dict[str, Any], triggered_by: str, explanation: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        digest = payload_digest(state)
        event = self.kernel.append("simulation.state.transitioned", {
            "run_id": run_id, "simulation_time_min": folded["simulation_time_min"],
            "transition_model_id": folded["started"]["transition_model_id"],
            "transition_model_version": folded["started"]["transition_model_version"],
            "triggered_by": triggered_by, "explanation": explanation,
            "state_after": state, "state_digest": digest,
        })
        previous = folded["observations"]
        self._release_observation(run_id, "state_transition:" + triggered_by,
                                  self._vital_observations(state, include_pef=bool(state.get("pef_measured")), previous=previous))
        return event

    def advance_time(self, run_id: str, minutes: int) -> dict[str, Any]:
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 60:
            raise SimulationError("Advance time by an integer from 1 through 60 minutes.")
        folded = self._fold(run_id)
        if folded["completed"]:
            raise SimulationConflict("Completed simulation runs are immutable.")
        from_minute = folded["simulation_time_min"]
        target_minute = from_minute + minutes
        if target_minute > 180:
            raise SimulationError("This teaching scenario is limited to 180 simulated minutes.")
        pending = [item for item in folded["scheduled"]
                   if item["scheduled_event_id"] not in {x["scheduled_event_id"] for x in folded["fired"] + folded["skipped"]}
                   and int(item["due_at_minute"]) <= target_minute]
        pending.sort(key=lambda item: (int(item["due_at_minute"]), int(item.get("priority", 100)), item["scheduled_event_id"]))
        clock_events = []
        processed_events = []
        current_minute = from_minute

        def move_clock(next_minute: int) -> None:
            nonlocal current_minute
            if next_minute <= current_minute:
                return
            clock_event = self.kernel.append("simulation.clock.advanced", {
                "run_id": run_id, "from_minute": current_minute, "to_minute": next_minute,
                "requested_advance_min": next_minute - current_minute,
                "clock_policy": "explicit_integer_minute_steps_with_due_event_boundaries",
            })
            clock_events.append(clock_event)
            current_minute = next_minute

        for item in pending:
            due_minute = int(item["due_at_minute"])
            move_clock(due_minute)
            current = self._fold(run_id)
            state = copy.deepcopy(current["state"])
            kind = item["kind"]
            if kind == "untreated_worsening" and state.get("bronchodilator_given"):
                skipped = self.kernel.append("simulation.event.skipped", {
                    "run_id": run_id, "scheduled_event_id": item["scheduled_event_id"],
                    "simulation_time_min": due_minute,
                    "reason": "Bronchodilator action was accepted before the scheduled deterioration point.",
                })
                processed_events.append(skipped)
                continue
            result_event = None
            if kind == "untreated_worsening":
                state.update({"heart_rate_bpm": 120, "respiratory_rate_per_min": 30,
                              "spo2_percent_room_air": 92, "pef_percent_predicted": 50,
                              "speech": "speaks_in_phrases", "work_of_breathing": "increased_accessory_muscle_use",
                              "air_entry": "reduced", "patient_worsening": True})
                explanation = "The scenario's untreated-worsening event fired at its authored simulation time. This is a fixed teaching-model transition, not a clinical prediction."
            elif kind == "peak_flow_result":
                state["pef_measured"] = True
                state["peak_flow_result_available"] = True
                explanation = "The delayed peak-flow investigation result became available at its scheduled simulation time."
                result_event = self.kernel.append("simulation.result.available", {
                    "run_id": run_id, "result_id": item["scheduled_event_id"], "result_type": "peak_flow",
                    "simulation_time_min": due_minute,
                    "value": state["pef_percent_predicted"], "unit": "% predicted",
                    "interpretation": "Objective lung-function result for this synthetic scenario; interpret alongside clinical findings.",
                })
            elif kind == "bronchodilator_response":
                if state.get("patient_worsening"):
                    state.update({"heart_rate_bpm": 108, "respiratory_rate_per_min": 24,
                                  "spo2_percent_room_air": 94, "pef_percent_predicted": 66,
                                  "speech": "speaks_in_sentences", "work_of_breathing": "mild_accessory_muscle_use",
                                  "air_entry": "improved", "wheeze": "persistent_expiratory_wheeze"})
                else:
                    state.update({"heart_rate_bpm": 104, "respiratory_rate_per_min": 22,
                                  "spo2_percent_room_air": 95, "pef_percent_predicted": 70,
                                  "speech": "speaks_in_sentences", "work_of_breathing": "minimal_accessory_muscle_use",
                                  "air_entry": "improved", "wheeze": "mild_expiratory_wheeze"})
                state["bronchodilator_response_observed"] = True
                if state.get("pef_measured"):
                    state["peak_flow_result_available"] = True
                explanation = "A deterministic improvement transition was applied 20 simulated minutes after the scenario bronchodilator action; it is not a dose-response model."
            else:
                skipped = self.kernel.append("simulation.event.skipped", {
                    "run_id": run_id, "scheduled_event_id": item["scheduled_event_id"],
                    "simulation_time_min": due_minute, "reason": f"Unknown scheduled event kind: {kind}.",
                })
                processed_events.append(skipped)
                continue
            fired = self.kernel.append("simulation.event.fired", {
                "run_id": run_id, "scheduled_event_id": item["scheduled_event_id"],
                "kind": kind, "due_at_minute": due_minute,
                "processed_at_minute": due_minute, "priority": int(item.get("priority", 100)),
                "explanation": explanation,
            })
            processed_events.append(fired)
            if result_event:
                processed_events.append(result_event)
            transition = self._record_state_transition(run_id, state, "scheduled_event:" + kind, explanation)
            processed_events.append(transition)
        move_clock(target_minute)
        return {"clock_events": clock_events, "processed_events": processed_events, "run": self.get_run(run_id)}

    def save_document(self, run_id: str, document_type: str, content: dict[str, Any]) -> dict[str, Any]:
        if document_type not in {"clinical_note", "handover", "order"}:
            raise SimulationError("Document type must be clinical_note, handover or order.")
        if not isinstance(content, dict):
            raise SimulationError("Document content must be an object of structured fields.")
        folded = self._fold(run_id)
        if folded["completed"]:
            raise SimulationConflict("Completed simulation runs are immutable.")
        field_limits = {"clinical_note": {"assessment": 3000, "findings": 3000, "plan": 3000, "uncertainties": 2000},
                        "handover": {"situation": 2000, "background": 2000, "assessment": 2000,
                                     "recommendation": 2000, "outstanding_tasks": 2000},
                        "order": {"order_type": 120, "display": 300, "rationale": 2000,
                                  "status": 40, "result_link": 160}}
        allowed = field_limits[document_type]
        clean = {}
        for key, limit in allowed.items():
            value = content.get(key, "")
            if not isinstance(value, str):
                raise SimulationError(f"Document field {key} must be text.")
            if len(value) > limit:
                raise SimulationError(f"Document field {key} exceeds the {limit}-character limit.")
            clean[key] = value.strip()
        previous_versions = [d for d in folded["documents"] if d["document_type"] == document_type]
        document_id = f"{run_id}:{document_type}"
        version = len(previous_versions) + 1
        event_type = "simulation.order.entered" if document_type == "order" else (
            "simulation.handover.submitted" if document_type == "handover" else "simulation.document.saved")
        event = self.kernel.append(event_type, {
            "run_id": run_id, "document_id": document_id, "document_type": document_type,
            "document_version": version, "simulation_time_min": folded["simulation_time_min"],
            "content": clean, "content_digest": payload_digest(clean),
            "author": "local_practice_user", "state": "submitted" if document_type == "handover" else "saved",
        })
        return {"document": {"document_id": document_id, "document_type": document_type,
                             "document_version": version, "content": clean, "event_id": event["event_id"]},
                "run": self.get_run(run_id)}

    @staticmethod
    def _first_action(actions: list[dict[str, Any]], action_id: str) -> dict[str, Any] | None:
        return next((action for action in actions if action.get("action_id") == action_id), None)

    def derive_assessment(self, run_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        if folded["completed"]:
            raise SimulationConflict("Completed simulation runs are immutable.")
        scenario = self.catalog.load(folded["started"]["scenario_id"])
        actions = folded["actions"]
        docs = folded["documents"]
        note = next((item for item in reversed(docs) if item["document_type"] == "clinical_note"), None)
        handover = next((item for item in reversed(docs) if item["document_type"] == "handover"), None)
        by_id = {action["action_id"]: action for action in actions}
        criteria = []
        def item(cid: str, earned: int, possible: int, reason: str, evidence: list[str]):
            criteria.append({"criterion_id": cid, "points_earned": earned, "points_possible": possible,
                             "rationale": reason, "evidence_event_ids": evidence})
        assessment_action = by_id.get("focused_assessment")
        item("focused_assessment", 10 if assessment_action else 0, 10,
             "Focused history/examination was recorded through a PROforma action." if assessment_action else "No focused assessment action was recorded.",
             [assessment_action["event_id"]] if assessment_action else [])
        pef_order = by_id.get("order_peak_flow")
        pef_result = next((event for event in folded["events"] if event["event_type"] == "simulation.result.available"
                           and event["payload"].get("result_type") == "peak_flow"), None)
        bronchodilator = by_id.get("administer_bronchodilator")
        if pef_order and pef_result:
            earned = 15 if not bronchodilator or pef_result["seq"] < bronchodilator["seq"] else 10
            reason = "Peak-flow result was available before the bronchodilator action." if earned == 15 else "Peak-flow result became available after the bronchodilator action; objective reassessment was still documented."
        else:
            earned, reason = 0, "No completed peak-flow result is present in the trace."
        item("objective_lung_function", earned, 15, reason,
             ([pef_order["event_id"]] if pef_order else []) + ([pef_result["event_id"]] if pef_result else []))
        if bronchodilator:
            early = bronchodilator["simulation_time_min"] <= 30
            earned = 20 if early else 12
            reason = "Bronchodilator action was recorded before the scenario's 30-minute deterioration checkpoint." if early else "Bronchodilator action was recorded after the deterioration checkpoint."
        else:
            earned, reason = 0, "No bronchodilator action was recorded."
        item("initial_bronchodilator", earned, 20, reason, [bronchodilator["event_id"]] if bronchodilator else [])
        steroid = by_id.get("start_systemic_corticosteroid")
        item("systemic_treatment_plan", 15 if steroid else 0, 15,
             "Systemic corticosteroid plan action was recorded; the model does not attribute immediate physiological response to it." if steroid else "No systemic corticosteroid plan action was recorded.",
             [steroid["event_id"]] if steroid else [])
        response_event = next((event for event in folded["events"] if event["event_type"] == "simulation.event.fired"
                               and event["payload"].get("kind") == "bronchodilator_response"), None)
        reassessment = by_id.get("reassess_patient")
        reassessed_after_response = bool(reassessment and response_event and reassessment["seq"] > response_event["seq"])
        item("response_reassessment", 20 if reassessed_after_response else 0, 20,
             "Formal reassessment followed the modelled response event." if reassessed_after_response else "A formal reassessment after the modelled response event is not present.",
             ([response_event["event_id"]] if response_event else []) + ([reassessment["event_id"]] if reassessment else []))
        note_content = note.get("content", {}) if note else {}
        note_fields = ["assessment", "findings", "plan", "uncertainties"]
        note_points = {"assessment": 2, "findings": 2, "plan": 3, "uncertainties": 3}
        note_earned = sum(points for key, points in note_points.items() if str(note_content.get(key, "")).strip())
        item("clinical_note", note_earned, 10,
             f"Structured field completeness only: {sum(bool(str(note_content.get(k, '')).strip()) for k in note_fields)}/{len(note_fields)} fields present; prose quality is not graded.",
             [note["event_id"]] if note else [])
        handover_content = handover.get("content", {}) if handover else {}
        handover_fields = ["situation", "background", "assessment", "recommendation", "outstanding_tasks"]
        handover_earned = sum(2 for key in handover_fields if str(handover_content.get(key, "")).strip())
        item("handover", handover_earned, 10,
             f"Structured field completeness only: {sum(bool(str(handover_content.get(k, '')).strip()) for k in handover_fields)}/{len(handover_fields)} fields present; content accuracy is not automatically graded.",
             [handover["event_id"]] if handover else [])
        earned_total = sum(entry["points_earned"] for entry in criteria)
        possible_total = sum(entry["points_possible"] for entry in criteria)
        trace_digest = self._semantic_trace_digest(folded["events"])
        state_digest = payload_digest(folded["state"])
        critical_flags = []
        worsening = next((event for event in folded["events"] if event["event_type"] == "simulation.event.fired"
                          and event["payload"].get("kind") == "untreated_worsening"), None)
        escalation = by_id.get("escalate_for_senior_review")
        if worsening and not escalation:
            critical_flags.append({"code": "WORSENING_WITHOUT_ESCALATION", "severity": "review", 
                                   "message": "The scenario worsened before treatment; no senior-review action was recorded. Review the decision sequence with an educator."})
        assessment_output = {
            "assessment_type": "formative_trace_based", "status": "formative_pending_clinical_review",
            "rubric_id": scenario["assessment"]["rubric_id"], "rubric_version": scenario["assessment"]["version"],
            "score": earned_total, "maximum": possible_total,
            "percentage": round((earned_total / possible_total) * 100, 1) if possible_total else 0,
            "criteria": criteria, "critical_flags": critical_flags,
            "trace_digest": trace_digest, "state_digest": state_digest,
            "competence_claimed": False, "free_text_semantics_scored": False,
            "limitations": scenario["assessment"]["limitations"],
        }
        derivation = derive(output_type="simulation.formative_assessment", output=copy.deepcopy(assessment_output),
                            rules=["SIM-ASSESSMENT-RUBRIC-1.0.0"],
                            inputs=[{"scenario_digest": folded["started"]["scenario_digest"],
                                     "trace_digest": trace_digest, "state_digest": state_digest}],
                            steps=criteria,
                            source_events=[{"event_id": event_id} for row in criteria for event_id in row["evidence_event_ids"]])
        assessment_output["derivation"] = derivation
        assessment_digest = payload_digest({key: value for key, value in assessment_output.items()
                                            if key not in {"derivation", "criteria"}} | {"criteria": [
                                                {key: value for key, value in row.items() if key != "evidence_event_ids"}
                                                for row in criteria]})
        assessment_event = self.kernel.append("simulation.assessment.derived", {
            "run_id": run_id, "rubric_id": scenario["assessment"]["rubric_id"],
            "rubric_version": scenario["assessment"]["version"], "trace_digest": trace_digest,
            "assessment_digest": assessment_digest, "score": earned_total, "maximum": possible_total,
            "percentage": assessment_output["percentage"], "criteria": criteria,
            "critical_flags": critical_flags, "derivation": derivation,
            "status": "formative_pending_clinical_review", "competence_claimed": False,
        })
        return {"assessment": assessment_output, "event": assessment_event, "run": self.get_run(run_id)}

    @staticmethod
    def _semantic_clean(value: Any) -> Any:
        if isinstance(value, dict):
            excluded = {"run_id", "event_id", "seq", "created_at", "recorded_at", "document_id",
                        "assessment_id", "proforma_event_ids", "proforma_derivation_hash"}
            return {key: ClinicalSimulationRuntime._semantic_clean(child)
                    for key, child in sorted(value.items()) if key not in excluded}
        if isinstance(value, list):
            return [ClinicalSimulationRuntime._semantic_clean(item) for item in value]
        return value

    def _semantic_trace_digest(self, events: list[dict[str, Any]]) -> str:
        semantic = []
        for event in events:
            if event["event_type"] not in SIMULATION_EVENT_TYPES:
                continue
            if event["event_type"] in {"simulation.assessment.derived", "simulation.run.completed", "simulation.run.abandoned"}:
                continue
            semantic.append({"event_type": event["event_type"], "payload": self._semantic_clean(event["payload"])})
        return hashlib.sha256(canonical_json(semantic).encode()).hexdigest()

    def replay(self, run_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        timeline = []
        for event in folded["events"]:
            if event["event_type"] == "simulation.run.started":
                title = "Simulation started"
                detail = f"Scenario {event['payload']['scenario_id']} · seed {event['payload']['seed']}"
            elif event["event_type"] == "simulation.action.accepted":
                title = "Learner action: " + event["payload"]["action_id"].replace("_", " ")
                detail = event["payload"].get("rationale", "Action accepted by PROforma.")
            elif event["event_type"] == "simulation.action.rejected":
                title = "Action withheld: " + event["payload"]["action_id"].replace("_", " ")
                detail = event["payload"]["reason"]
            elif event["event_type"] == "simulation.clock.advanced":
                title = "Simulation clock advanced"
                detail = f"T+{event['payload']['from_minute']} → T+{event['payload']['to_minute']} minutes"
            elif event["event_type"] == "simulation.event.fired":
                title = "Scheduled event: " + event["payload"]["kind"].replace("_", " ")
                detail = event["payload"].get("explanation", "Scheduled scenario event fired.")
            elif event["event_type"] == "simulation.document.saved":
                title = "Document saved: " + event["payload"]["document_type"].replace("_", " ")
                detail = f"Version {event['payload']['document_version']} · {event['payload']['state']}"
            elif event["event_type"] == "simulation.order.entered":
                title = "Order entered"
                detail = event["payload"].get("content", {}).get("display", "Scenario order")
            elif event["event_type"] == "simulation.handover.submitted":
                title = "Handover submitted"
                detail = f"Version {event['payload']['document_version']}"
            elif event["event_type"] == "simulation.debrief.completed":
                title = "Structured debrief completed"
                detail = f"{event['payload']['completed']}/{event['payload']['total']} reflection prompts"
            elif event["event_type"] == "simulation.assessment.derived":
                title = "Formative assessment derived"
                detail = f"{event['payload']['score']}/{event['payload']['maximum']} · rubric {event['payload']['rubric_version']}"
            elif event["event_type"] == "simulation.observation.released":
                title = "Observation released: " + event["payload"]["stage"].replace("_", " ")
                detail = f"{len(event['payload'].get('observations', {}))} observation(s)"
            elif event["event_type"] in {"simulation.action.requested", "simulation.state.transitioned", "simulation.event.scheduled", "simulation.result.available", "simulation.event.skipped", "simulation.run.completed"}:
                continue
            else:
                title, detail = event["event_type"], "Recorded"
            timeline.append({"seq": event["seq"], "event_id": event["event_id"],
                             "event_type": event["event_type"], "simulation_time_min": event["payload"].get("simulation_time_min", 0),
                             "title": title, "detail": detail})
        return {
            "run_id": run_id, "scenario_id": folded["started"]["scenario_id"],
            "timeline": timeline, "semantic_trace_digest": self._semantic_trace_digest(folded["events"]),
            "state_digest": payload_digest(folded["state"]),
            "event_count": len(folded["events"]), "actions_accepted": len(folded["actions"]),
            "actions_rejected": len(folded["rejected_actions"]), "documents": folded["documents"],
            "assessment": folded["assessment"], "completed": folded["completed"],
            "replay_contract": "Replay is a deterministic event fold over this run's canonical simulation events. UUIDs and wall-clock audit metadata are excluded from semantic trace digests.",
        }

    def save_debrief(self, run_id: str, responses: dict[str, str]) -> dict[str, Any]:
        folded = self._fold(run_id)
        if folded["completed"]:
            raise SimulationConflict("Completed simulation runs are immutable.")
        if not isinstance(responses, dict):
            raise SimulationError("Debrief responses must be an object.")
        clean: dict[str, str] = {}
        for key, value in responses.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
                raise SimulationError("Debrief response keys must be stable identifiers.")
            if not isinstance(value, str) or len(value) > 3000:
                raise SimulationError("Each debrief response must be text no longer than 3000 characters.")
            clean[key] = value.strip()
        scenario = self.catalog.load(folded["started"]["scenario_id"])
        prompts = scenario.get("debrief", {}).get("prompts", [])
        total = len(prompts)
        completed = sum(1 for key, value in clean.items() if value)
        event = self.kernel.append("simulation.debrief.completed", {
            "run_id": run_id, "simulation_time_min": folded["simulation_time_min"],
            "responses": clean, "response_digest": payload_digest(clean),
            "completed": completed, "total": total,
        })
        return {"debrief": {"responses": clean, "completed": completed, "total": total,
                            "response_digest": payload_digest(clean), "event_id": event["event_id"]},
                "run": self.get_run(run_id)}

    def counterfactual(self, run_id: str, omit_action_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        scenario = self.catalog.load(folded["started"]["scenario_id"])
        if omit_action_id not in scenario["action_catalogue"]:
            raise SimulationError("The counterfactual action must exist in the scenario action catalogue.")
        original_action = next((item for item in folded["actions"] if item["action_id"] == omit_action_id), None)
        if original_action is None:
            raise SimulationError("The omitted action is not present in the original run; a fork still requires a real baseline action.")

        state = copy.deepcopy(folded["started"]["initial_state"])
        heart_options = state.pop("heart_rate_seed_options_bpm", [])
        if heart_options:
            seed_digest = hashlib.sha256(f"{SEED_ALGORITHM}|{folded['started']['scenario_id']}|{folded['started']['seed']}".encode()).digest()
            state["heart_rate_bpm"] = int(heart_options[seed_digest[0] % len(heart_options)])

        fork_actions = [item for item in folded["actions"] if item["action_id"] != omit_action_id]
        state_changes: list[str] = []
        for action in fork_actions:
            action_id = action["action_id"]
            if action_id == "focused_assessment":
                state["assessment_complete"] = True
            elif action_id == "order_peak_flow":
                state["peak_flow_ordered"] = True
            elif action_id == "administer_bronchodilator":
                state["bronchodilator_given"] = True
            elif action_id == "start_systemic_corticosteroid":
                state["systemic_corticosteroid_started"] = True
            elif action_id == "escalate_for_senior_review":
                state["senior_review_requested"] = True
            elif action_id == "reassess_patient":
                state["reassessment_complete"] = True

        if omit_action_id == "administer_bronchodilator":
            state.update({"heart_rate_bpm": 120, "respiratory_rate_per_min": 30,
                          "spo2_percent_room_air": 92, "pef_percent_predicted": 50,
                          "patient_worsening": True})
            state_changes.append("At T+30 the authored untreated-worsening transition remains on the fork.")
        elif omit_action_id == "order_peak_flow":
            state["peak_flow_result_available"] = False
            state["pef_measured"] = False
            state_changes.append("The peak-flow result is not available because the result-order action was removed.")
        elif omit_action_id == "focused_assessment":
            state["assessment_complete"] = False
            state_changes.append("Focused-history findings remain unreleased in the counterfactual fork.")
        elif omit_action_id == "reassess_patient":
            state["reassessment_complete"] = False
            state_changes.append("Formal reassessment is absent in the counterfactual fork.")
        else:
            state_changes.append("Only the selected action was removed; the remaining trace was preserved.")

        fork_digest = payload_digest({
            "scenario_id": folded["started"]["scenario_id"],
            "scenario_digest": folded["started"]["scenario_digest"],
            "seed": folded["started"]["seed"],
            "omitted_action_id": omit_action_id,
            "retained_actions": [item["action_id"] for item in fork_actions],
            "final_state": state,
        })
        return {
            "run_id": run_id,
            "counterfactual": True,
            "read_only": True,
            "mutates_original": False,
            "omitted_action_id": omit_action_id,
            "omitted_action": {"simulation_time_min": original_action["simulation_time_min"],
                               "event_id": original_action["event_id"]},
            "retained_action_ids": [item["action_id"] for item in fork_actions],
            "projected_state": state,
            "projected_state_digest": payload_digest(state),
            "fork_digest": fork_digest,
            "state_changes": state_changes,
            "limitations": ["This is a bounded read-only fork of the first educational scenario, not a dynamically simulated alternative patient.",
                            "The original run and event log are unchanged."],
        }

    def complete(self, run_id: str) -> dict[str, Any]:
        folded = self._fold(run_id)
        if folded["completed"]:
            return self.get_run(run_id)
        if not folded["assessment"]:
            raise SimulationError("Derive the formative assessment before completing the run.")
        replay = self.replay(run_id)
        event = self.kernel.append("simulation.run.completed", {
            "run_id": run_id, "simulation_time_min": folded["simulation_time_min"],
            "trace_digest": replay["semantic_trace_digest"],
            "assessment_digest": folded["assessment"]["assessment_digest"],
        })
        return {"event": event, "run": self.get_run(run_id)}


class SimulationPulseProvider:
    """A run-scoped Pulse provider backed by the in-process simulation runtime."""
    def __init__(self, runtime: ClinicalSimulationRuntime, run_id: str):
        self.runtime = runtime
        self.run_id = run_id

    def step(self) -> dict[str, Any]:
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        return self.runtime.pulse_state(self.run_id)

    def apply_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return self.runtime.perform_action(self.run_id, action)
