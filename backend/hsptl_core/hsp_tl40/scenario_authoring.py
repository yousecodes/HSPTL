"""Governed, file-backed scenario authoring over the existing simulation package format.

Drafts are local data artifacts. Publishing requires a separately configured clinical
review credential; it does not imply that the reviewer is clinically qualified unless
the institution has verified that identity outside this local application.
"""
from __future__ import annotations

import copy
import hmac
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .clinical_simulation import ScenarioCatalog
from .model_library import load_model


class ScenarioAuthoringError(ValueError):
    pass


class ScenarioAuthoring:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.drafts = self.root / "scenario_drafts"
        self.published = self.root / "scenarios"
        self.drafts.mkdir(parents=True, exist_ok=True)
        self.published.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate(scenario: Any) -> dict[str, Any]:
        try:
            errors = ScenarioCatalog.validate(scenario)
        except (TypeError, ValueError, AttributeError) as exc:
            errors = [f"Scenario contains malformed typed fields: {exc}"]
        warnings: list[str] = []
        if not isinstance(scenario, dict):
            return {"valid": False, "errors": errors, "warnings": warnings, "checks": []}
        scenario_id = str(scenario.get("scenario_id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,100}", scenario_id):
            errors.append("scenario_id must contain 3–100 letters, numbers, underscores or hyphens.")
        if not isinstance(scenario.get("title"), str) or not scenario["title"].strip():
            errors.append("Scenario title is required.")
        if not isinstance(scenario.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", scenario["version"]):
            errors.append("Scenario version must be semantic version text (major.minor.patch with optional prerelease).")
        if not isinstance(scenario.get("patient"), dict) or scenario["patient"].get("synthetic") is not True:
            errors.append("Scenario patient must be explicitly marked synthetic=true.")
        actions = scenario.get("action_catalogue", {})
        if isinstance(actions, dict):
            for action_id, action in actions.items():
                if not re.fullmatch(r"[A-Za-z0-9_-]{2,100}", str(action_id)):
                    errors.append(f"Action id {action_id!r} is not a stable identifier.")
                path = action.get("model_path") if isinstance(action, dict) else None
                if not isinstance(path, str):
                    errors.append(f"Action {action_id} requires a PROforma model_path.")
                    continue
                try:
                    model = load_model(path)
                    if not model.get("id"):
                        errors.append(f"Action {action_id} model has no stable PROforma id.")
                except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                    errors.append(f"Action {action_id} references an invalid PROforma model: {exc}")
        scheduled = scenario.get("scheduled_events", [])
        if not isinstance(scheduled, list):
            errors.append("scheduled_events must be a list.")
        else:
            event_ids: set[str] = set()
            for item in scheduled:
                if not isinstance(item, dict):
                    errors.append("Every scheduled event must be an object.")
                    continue
                event_id = str(item.get("event_id", ""))
                if not event_id or event_id in event_ids:
                    errors.append(f"Scheduled event id is missing or duplicated: {event_id!r}.")
                event_ids.add(event_id)
                if type(item.get("due_at_minute")) is not int or item["due_at_minute"] < 0:
                    errors.append(f"Scheduled event {event_id!r} requires a non-negative integer due_at_minute.")
                if item.get("kind") not in {"untreated_worsening", "peak_flow_result", "bronchodilator_response"}:
                    errors.append(f"Scheduled event {event_id!r} has an unsupported transition kind.")
        observation_policy = scenario.get("observation_policy", {})
        if not isinstance(observation_policy, dict) or observation_policy.get("internal_model_state_never_returned") is not True:
            errors.append("observation_policy must explicitly prevent internal model state from being returned.")
        rubric = scenario.get("assessment", {}).get("criteria", []) if isinstance(scenario.get("assessment"), dict) else []
        criterion_ids = [item.get("id") for item in rubric if isinstance(item, dict)] if isinstance(rubric, list) else []
        if isinstance(rubric, list) and len(criterion_ids) != len(set(criterion_ids)):
            errors.append("Assessment criterion ids must be unique.")
        if isinstance(rubric, list) and any(type(item.get("points")) is not int or item["points"] < 0 for item in rubric if isinstance(item, dict)):
            errors.append("Every assessment criterion must have a non-negative integer point value.")
        objectives = scenario.get("learning_objectives", [])
        if not isinstance(objectives, list) or not objectives or any(not isinstance(item, str) or not item.strip() for item in objectives):
            errors.append("learning_objectives must be a non-empty list of strings.")
        elif len(objectives) != len(set(objectives)):
            errors.append("Learning objectives must be unique.")
        if not isinstance(scenario.get("source_basis", []), list):
            errors.append("source_basis must be a list.")
        for source in scenario.get("source_basis", []) if isinstance(scenario.get("source_basis", []), list) else []:
            if not isinstance(source, dict) or not source.get("title") or not source.get("publisher"):
                errors.append("Each source_basis item requires a title and publisher.")
            elif source.get("url") and not str(source["url"]).startswith("https://"):
                errors.append("Scenario source URLs must use HTTPS.")
        simulation_model = scenario.get("simulation_model", {})
        if not isinstance(simulation_model, dict) or not all(simulation_model.get(k) for k in ("model_id", "version")):
            errors.append("simulation_model requires a model_id and version.")
        if scenario.get("clinical_review_status") != "approved":
            warnings.append("Scenario remains a draft and must not be presented as clinically approved.")
        if not scenario.get("source_basis"):
            warnings.append("No source_basis entries are declared; add sources and licence metadata before review.")
        if not scenario.get("learning_objectives"):
            errors.append("At least one explicit learning objective is required.")
        initial_state = scenario.get("initial_state")
        if not isinstance(initial_state, dict) or not initial_state:
            errors.append("initial_state must be a non-empty object.")
        else:
            if not isinstance(initial_state.get("heart_rate_seed_options_bpm"), list) or not initial_state["heart_rate_seed_options_bpm"]:
                errors.append("initial_state requires a non-empty heart_rate_seed_options_bpm list.")
            if any(type(value) is not int for value in initial_state.get("heart_rate_seed_options_bpm", [])):
                errors.append("Every heart-rate seed variant must be an integer.")
        for required_key in ("assessment_complete", "peak_flow_ordered", "bronchodilator_given",
                             "systemic_corticosteroid_started", "reassessment_complete",
                             "senior_review_requested", "patient_worsening"):
            if not isinstance(initial_state, dict) or type(initial_state.get(required_key)) is not bool:
                errors.append(f"initial_state.{required_key} must be an explicit boolean.")
        if isinstance(scheduled, list):
            due_values = [item.get("due_at_minute") for item in scheduled if isinstance(item, dict) and type(item.get("due_at_minute")) is int]
            if len(due_values) != len(set(due_values)):
                errors.append("Scheduled events must not share the same due minute unless priority and event ids provide deterministic ties.")
            for item in scheduled:
                if not isinstance(item, dict):
                    continue
                condition = item.get("condition")
                if condition is not None and not isinstance(condition, str):
                    errors.append("Scheduled-event conditions must be named strings, not executable expressions.")
        action_ids = set(actions.keys()) if isinstance(actions, dict) else set()
        required_action_ids = {"focused_assessment", "order_peak_flow", "administer_bronchodilator",
                               "start_systemic_corticosteroid", "escalate_for_senior_review", "reassess_patient"}
        missing_actions = sorted(required_action_ids - action_ids)
        if missing_actions:
            warnings.append("Scenario does not use the first-slice action catalogue; dynamic coverage is limited: " + ", ".join(missing_actions))
        checks = ["scenario_structure", "synthetic_patient", "semantic_version", "rubric_total_and_unique_criteria", "proforma_model_references", "scheduled_event_contract", "observation_state_withholding", "source_metadata", "simulation_model_identity"]
        return {"valid": not errors, "errors": errors, "warnings": warnings, "checks": checks,
                "dynamic_path_coverage": "bounded_static_trace_coverage" if not missing_actions else "partial_bounded_action_coverage",
                "clinical_validity": "requires_independent_qualified_review"}

    @staticmethod
    def trace_matrix(scenario: Any) -> dict[str, Any]:
        validation = ScenarioAuthoring.validate(scenario)
        if not validation["valid"]:
            raise ScenarioAuthoringError("Trace matrix requires a structurally valid scenario.")
        action_ids = list((scenario.get("action_catalogue") or {}).keys())
        required = {
            "strong": ["focused_assessment", "order_peak_flow", "administer_bronchodilator",
                       "start_systemic_corticosteroid", "reassess_patient"],
            "partial": ["focused_assessment", "administer_bronchodilator", "reassess_patient"],
            "poor": [],
            "unsafe": ["administer_bronchodilator"],
        }
        traces: list[dict[str, Any]] = []
        for trace_name, preferred in required.items():
            sequence = [action for action in preferred if action in action_ids]
            traces.append({
                "trace": trace_name,
                "ordered_actions": sequence,
                "seed": 20261119,
                "clock_steps": [2, 20, 40] if trace_name != "poor" else [30, 60],
                "expected": {
                    "strong": "No protected criterion should remain entirely unknown.",
                    "partial": "Incomplete objective-assessment or treatment evidence is surfaced.",
                    "poor": "The trace must be explainable, non-competence-claiming and low-scored.",
                    "unsafe": "A single action must not be represented as complete pathway conformance.",
                }[trace_name],
            })
        return {
            "valid": True,
            "scenario_id": scenario["scenario_id"],
            "scenario_version": scenario["version"],
            "trace_matrix": traces,
            "fault_injection": [
                {"fault": "duplicate_action", "policy": "action request is audited; repeated acceptance policy is scenario-controlled"},
                {"fault": "out_of_order_action", "policy": "PROforma guard rejects or records a withheld action"},
                {"fault": "clock_jump", "policy": "scheduled events are processed at authored boundaries"},
                {"fault": "malformed_action", "policy": "typed payload validation fails closed"},
                {"fault": "unsupported_action", "policy": "catalogue boundary rejects the action"},
            ],
            "clinical_review_required": True,
        }

    def list_drafts(self) -> list[dict[str, Any]]:
        items = []
        seen: set[str] = set()
        for path in sorted(self.drafts.glob("*/*/scenario.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                scenario = json.loads(path.read_text(encoding="utf-8"))
                scenario_id = str(scenario.get("scenario_id", ""))
                if not scenario_id or scenario_id in seen:
                    continue
                seen.add(scenario_id)
                published_path = self.published / scenario_id / "scenario.json"
                published_version = None
                if published_path.is_file():
                    try:
                        published_version = json.loads(published_path.read_text(encoding="utf-8")).get("version")
                    except (OSError, json.JSONDecodeError):
                        published_version = None
                items.append({"scenario_id": scenario_id, "version": scenario.get("version"),
                              "title": scenario.get("title"), "clinical_review_status": scenario.get("clinical_review_status"),
                              "published": published_version == scenario.get("version"),
                              "updated_at": scenario.get("authoring", {}).get("updated_at", "")})
            except (OSError, json.JSONDecodeError):
                continue
        return items

    def get_draft(self, scenario_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,100}", scenario_id):
            raise ScenarioAuthoringError("Invalid scenario id.")
        candidates = sorted((self.drafts / scenario_id).glob("*/scenario.json"),
                            key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            raise KeyError(scenario_id)
        return json.loads(candidates[0].read_text(encoding="utf-8"))

    def save_draft(self, scenario: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate(scenario)
        if not validation["valid"]:
            raise ScenarioAuthoringError("Scenario validation failed: " + "; ".join(validation["errors"]))
        item = copy.deepcopy(scenario)
        item["clinical_review_status"] = "draft_pending_clinical_review"
        target = self.drafts / item["scenario_id"] / str(item["version"]) / "scenario.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            comparable_existing = {key: value for key, value in existing.items() if key != "authoring"}
            comparable_incoming = {key: value for key, value in item.items() if key != "authoring"}
            if comparable_existing != comparable_incoming:
                raise ScenarioAuthoringError("Scenario versions are immutable. Increment the version before saving changed content.")
            item["authoring"] = existing.get("authoring", {})
            reused = True
        else:
            item["authoring"] = {**item.get("authoring", {}), "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "draft_id": item.get("authoring", {}).get("draft_id", "scdraft_" + uuid.uuid4().hex)}
            reused = False
        serialized = json.dumps(item, indent=2, ensure_ascii=False, sort_keys=True)
        if not reused:
            temp = target.with_suffix(".json.tmp")
            temp.write_text(serialized, encoding="utf-8")
            temp.replace(target)
        digest = __import__("hashlib").sha256(serialized.encode("utf-8")).hexdigest()
        return {"scenario_id": item["scenario_id"], "version": item["version"], "title": item["title"],
                "clinical_review_status": item["clinical_review_status"], "validation": validation,
                "scenario_digest": digest, "reused": reused, "draft_path": str(target)}

    def publish(self, scenario_id: str, token: str | None) -> dict[str, Any]:
        expected = os.environ.get("HSPTL_CLINICAL_REVIEWER_TOKEN", "")
        reviewer = os.environ.get("HSPTL_CLINICAL_REVIEWER_ID", "").strip()
        if len(expected) < 32 or not reviewer:
            raise PermissionError("Clinical reviewer authentication is not configured. Set HSPTL_CLINICAL_REVIEWER_TOKEN (32+ characters) and HSPTL_CLINICAL_REVIEWER_ID.")
        if not token or not hmac.compare_digest(token, expected):
            raise PermissionError("Valid clinical reviewer credentials are required.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,100}", scenario_id):
            raise ScenarioAuthoringError("Invalid scenario id.")
        candidates = sorted((self.drafts / scenario_id).glob("*/scenario.json"),
                            key=lambda item: item.stat().st_mtime, reverse=True)
        source = candidates[0] if candidates else None
        if source is None or not source.is_file():
            raise KeyError(scenario_id)
        scenario = json.loads(source.read_text(encoding="utf-8"))
        published_path = self.published / scenario_id / "scenario.json"
        if published_path.is_file():
            try:
                published_current = json.loads(published_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                published_current = {}
            if published_current.get("version") == scenario.get("version"):
                raise ScenarioAuthoringError("This scenario version has already been published. Increment the version to publish a revision.")
        validation = self.validate(scenario)
        if not validation["valid"]:
            raise ScenarioAuthoringError("Scenario validation failed: " + "; ".join(validation["errors"]))
        scenario["clinical_review_status"] = "approved"
        scenario["clinical_review"] = {"reviewer_id": reviewer[:160],
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "approval_scope": "scenario_package_review; external qualification verification remains institutional responsibility"}
        target = self.published / scenario_id / "scenario.json"
        version_archive = self.published / scenario_id / "versions" / str(scenario["version"]) / "scenario.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        version_archive.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(scenario, indent=2, ensure_ascii=False, sort_keys=True)
        for destination in (version_archive, target):
            temp = destination.with_suffix(".json.tmp")
            temp.write_text(serialized, encoding="utf-8")
            temp.replace(destination)
        digest = __import__("hashlib").sha256(serialized.encode("utf-8")).hexdigest()
        return {"scenario_id": scenario_id, "version": scenario["version"], "published": True,
                "scenario_digest": digest, "reviewer_id": reviewer[:160], "reviewed_at": scenario["clinical_review"]["reviewed_at"],
                "clinical_review_status": "approved",
                "qualification_note": "Reviewer qualification must be verified by the deploying institution."}
