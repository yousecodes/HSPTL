"""Deterministic, template-driven clinical learning content factory.

All source learning material is authored in versioned JSON packs. The factory
creates reproducible derivatives for provisional supervised educational use;
it never uses an AI model or invents clinical measurements.
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .generation_distribution import WORKSPACE_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "content_packs" / "acute_care_foundations_v1.json"
OUTPUT_WORKSPACE = {
    "case_report": "clinic",
    "case_debrief": "clinic",
    "question_set": "exam_hall",
    "topic_summary": "exam_hall",
    "viva_set": "rounds",
    "osce_station": "lab",
    "on_call_scenario": "ward",
    "handover_template": "ward",
    "simulation_brief": "simulation",
}
OUTPUT_SECTION = {
    "case_report": "reports",
    "case_debrief": "debriefs",
    "question_set": "questions",
    "topic_summary": "summaries",
    "viva_set": "viva",
    "osce_station": "osce",
    "on_call_scenario": "on_call",
    "handover_template": "handover",
    "simulation_brief": "scenario_briefs",
}
DEFAULT_OUTPUT_TYPES = tuple(OUTPUT_WORKSPACE)


class ContentPackError(ValueError):
    pass


class ContentFactory:
    def __init__(self, pack_path: Path | None = None):
        """Load one pack, a pack directory, or all installed versioned packs.

        The default directory discovery makes content expansion a data-only
        operation: a new `*_vN.json` pack is validated and appears in the
        learner library without adding a new route or service.
        """
        if pack_path is None:
            pack_paths = sorted(DEFAULT_PACK.parent.glob("*_v*.json"))
        else:
            selected = Path(pack_path)
            pack_paths = sorted(selected.glob("*_v*.json")) if selected.is_dir() else [selected]
        if not pack_paths:
            raise ContentPackError("No versioned content packs were found")

        self.pack_paths = pack_paths
        self.packs: dict[str, dict[str, Any]] = {}
        self.units: dict[str, dict[str, Any]] = {}
        self.unit_packs: dict[str, dict[str, Any]] = {}
        for path in pack_paths:
            pack = json.loads(path.read_text(encoding="utf-8"))
            self._validate_pack(pack)
            pack_id = pack["pack_id"]
            if pack_id in self.packs:
                raise ContentPackError(f"Duplicate content pack id: {pack_id}")
            self.packs[pack_id] = pack
            for unit in pack["units"]:
                unit_id = unit["unit_id"]
                if unit_id in self.units:
                    raise ContentPackError(f"Duplicate unit id across content packs: {unit_id}")
                self.units[unit_id] = unit
                self.unit_packs[unit_id] = pack
        # Backward-compatible primary pack attribute for existing callers.
        self.pack = next(iter(self.packs.values()))
        self.pack_path = self.pack_paths[0]

    def _validate_pack(self, pack: dict[str, Any]) -> None:
        if not isinstance(pack, dict) or not pack.get("pack_id") or not pack.get("version"):
            raise ContentPackError("Content pack requires an id and version")
        units = pack.get("units")
        if not isinstance(units, list) or not units:
            raise ContentPackError("Content pack must contain at least one unit")
        seen: set[str] = set()
        sources = pack.get("sources", {})
        if not isinstance(sources, dict):
            raise ContentPackError("Content pack sources must be an object")
        if not isinstance(pack.get("generation_policy"), dict):
            raise ContentPackError("Content pack requires a generation policy")
        for source_id, source in sources.items():
            if not isinstance(source, dict) or not source.get("title") or not source.get("publisher") or not source.get("url"):
                raise ContentPackError(f"Source {source_id!r} requires title, publisher and URL")
            if not str(source["url"]).startswith("https://"):
                raise ContentPackError(f"Source {source_id!r} must use HTTPS")
        for unit in units:
            uid = unit.get("unit_id", "")
            if not uid or uid in seen:
                raise ContentPackError(f"Missing or duplicate unit id: {uid!r}")
            seen.add(uid)
            required = {"title", "specialty", "level", "minutes", "tags", "objectives", "case", "teaching_points", "pitfalls", "quiz", "viva", "osce", "debrief", "source_ids"}
            missing = sorted(required - set(unit))
            if missing:
                raise ContentPackError(f"{uid}: missing required fields: {', '.join(missing)}")
            if not isinstance(unit["minutes"], int) or not 5 <= unit["minutes"] <= 180:
                raise ContentPackError(f"{uid}: minutes must be an integer between 5 and 180")
            if not isinstance(unit["tags"], list) or not unit["tags"] or len(set(unit["tags"])) != len(unit["tags"]):
                raise ContentPackError(f"{uid}: tags must be a non-empty unique list")
            if len(unit.get("objectives", [])) < 2:
                raise ContentPackError(f"{uid}: at least two learning objectives are required")
            case = unit.get("case", {})
            case_fields = ("patient", "setting", "presentation", "history", "observations", "revealed_findings", "task")
            if not isinstance(case, dict) or any(not case.get(key) for key in case_fields):
                raise ContentPackError(f"{uid}: synthetic case is incomplete")
            if len(unit.get("teaching_points", [])) < 2 or not unit.get("pitfalls") or len(unit.get("debrief", [])) < 2:
                raise ContentPackError(f"{uid}: teaching points, pitfalls and debrief prompts are required")
            if len(unit.get("viva", [])) < 2:
                raise ContentPackError(f"{uid}: at least two viva prompts are required")
            for prompt in unit["viva"]:
                if not prompt.get("prompt") or len(prompt.get("key_points", [])) < 2:
                    raise ContentPackError(f"{uid}: every viva prompt requires key points")
            quiz = unit.get("quiz", [])
            if len(quiz) < 3:
                raise ContentPackError(f"{uid}: at least three retrieval questions are required")
            for index, item in enumerate(quiz):
                options = item.get("options", [])
                answer_index = item.get("correct_index")
                if len(options) < 3 or len(set(options)) != len(options):
                    raise ContentPackError(f"{uid}: question {index + 1} has invalid options")
                if type(answer_index) is not int or not 0 <= answer_index < len(options):
                    raise ContentPackError(f"{uid}: question {index + 1} has invalid answer index")
                if len(item.get("rationale", "").strip()) < 20:
                    raise ContentPackError(f"{uid}: question {index + 1} needs a meaningful rationale")
            osce = unit.get("osce", {})
            if (not osce.get("title") or not osce.get("candidate_instructions")
                    or len(osce.get("checklist", [])) < 4 or len(osce.get("critical_errors", [])) < 1
                    or type(osce.get("time_seconds")) is not int or not 60 <= osce["time_seconds"] <= 3600):
                raise ContentPackError(f"{uid}: OSCE station, checklist, critical errors and valid duration are required")
            for source_id in unit.get("source_ids", []):
                if source_id not in sources:
                    raise ContentPackError(f"{uid}: unknown source reference {source_id}")

    def catalog(self) -> dict[str, Any]:
        units = []
        pack_summaries = []
        for pack_id, pack in self.packs.items():
            pack_summaries.append({"pack_id": pack_id, "title": pack["title"], "version": pack["version"],
                                   "unit_count": len(pack["units"]), "content_status": pack["content_status"]})
            for unit in pack["units"]:
                units.append({
                    "unit_id": unit["unit_id"], "title": unit["title"],
                    "specialty": unit["specialty"], "level": unit["level"],
                    "minutes": unit["minutes"], "tags": unit["tags"],
                    "objectives": unit["objectives"],
                    "case_preview": unit["case"]["presentation"],
                    "quiz_count": len(unit["quiz"]),
                    "source_count": len(unit.get("source_ids", [])),
                    "pack_id": pack_id, "pack_version": pack["version"],
                    "content_status": "provisional_educational_use",
                    "available_outputs": list(DEFAULT_OUTPUT_TYPES),
                })
        return {
            "pack_id": self.pack["pack_id"], "title": self.pack["title"],
            "version": self.pack["version"], "description": self.pack["description"],
            "content_status": self.pack["content_status"],
            "generation_policy": self.pack["generation_policy"],
            "pack_count": len(self.packs), "packs": pack_summaries,
            "unit_count": len(units), "question_count": sum(u["quiz_count"] for u in units),
            "outputs_per_unit": 6, "units": units,
        }

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        unit = self.units.get(unit_id)
        if unit is None:
            return None
        pack = self.unit_packs[unit_id]
        result = dict(unit)
        result["source_refs"] = [pack["sources"][key] | {"source_id": key} for key in unit.get("source_ids", [])]
        result["content_status"] = "educator_review_required"
        result["pack"] = {"pack_id": pack["pack_id"], "version": pack["version"], "title": pack["title"]}
        return result

    @staticmethod
    def _claim_section(heading: str, claims: list[str]) -> dict[str, Any]:
        return {"heading": heading, "claims": [{"text": claim, "citations": []} for claim in claims if claim.strip()]}

    def build(self, unit_id: str, kind: str, seed: int = 0) -> dict[str, Any]:
        unit = self.units.get(unit_id)
        if unit is None:
            raise ContentPackError("Unknown content unit")
        pack = self.unit_packs[unit_id]
        workspace = OUTPUT_WORKSPACE.get(kind)
        if workspace is None or kind not in WORKSPACE_SCRIPTS[workspace]["outputs"]:
            raise ContentPackError(f"Unsupported content output: {kind}")
        refs = [pack["sources"][key] | {"source_id": key, "review_status": "reference_only"}
                for key in unit.get("source_ids", [])]
        title = f"{unit['title']} · {kind.replace('_', ' ').title()}"
        metadata = {
            "generation_mode": "deterministic_template_composer",
            "generator_version": "1.0.0",
            "content_pack_id": pack["pack_id"],
            "content_pack_version": pack["version"],
            "unit_id": unit_id,
            "seed": int(seed),
            "content_status": "provisional_educational_use",
            "clinical_use": "not_for_patient_care",
            "review_policy": "human_expert_approval_required_before_distribution",
            "variation_policy": "only question option ordering may vary; clinical scenario facts are immutable",
        }
        case = unit["case"]
        if kind == "case_report":
            sections = [
                self._claim_section("problem_representation", [case["presentation"], case["history"], case["observations"]]),
                self._claim_section("learning_objectives", unit["objectives"]),
                self._claim_section("discriminating_evidence", case["revealed_findings"]),
                self._claim_section("clinical_reasoning", unit["teaching_points"]),
                self._claim_section("pitfalls", unit["pitfalls"]),
                self._claim_section("task", [case["task"]]),
            ]
            body = {"sections": sections, "limitations": ["Synthetic educational case; not a patient record.", "Requires clinical educator review before distribution."]}
        elif kind == "case_debrief":
            body = {"sections": [
                self._claim_section("learning_points", unit["teaching_points"]),
                self._claim_section("reasoning_gaps", unit["pitfalls"]),
                self._claim_section("reflection_questions", unit["debrief"]),
            ], "limitations": ["Debrief prompts are formative and require educator review."]}
        elif kind == "topic_summary":
            body = {"sections": [
                self._claim_section("learning_objectives", unit["objectives"]),
                self._claim_section("core_concepts", unit["teaching_points"]),
                self._claim_section("common_pitfalls", unit["pitfalls"]),
                self._claim_section("case_application", [case["task"]]),
            ], "limitations": ["Summary is a teaching aid, not a clinical protocol."]}
        elif kind == "question_set":
            items = []
            for index, question in enumerate(unit["quiz"]):
                order = list(range(len(question["options"])))
                random.Random(f"{pack['version']}:{unit_id}:{seed}:{index}").shuffle(order)
                options = [question["options"][i] for i in order]
                correct = question["options"][question["correct_index"]]
                items.append({
                    "kind": "MCQ", "specialty": unit["specialty"], "difficulty": unit["level"],
                    "question": question["stem"], "options": options, "answer": correct,
                    "explanation": question["rationale"], "source_title": pack["title"],
                    "source_url": refs[0]["url"] if refs else "",
                    "licence": "HSPTL-authored educational content; external sources are attributed, not reproduced.",
                    "tags": unit["tags"], "citations": refs,
                })
            body = {"sections": [
                self._claim_section("questions", [item["question"] for item in items]),
                self._claim_section("answer_key", [f"{item['question']} — {item['answer']}" for item in items]),
                self._claim_section("rationales", [item["explanation"] for item in items]),
                self._claim_section("coverage_map", unit["objectives"]),
            ], "assessment_items": items, "limitations": ["Formative draft; answer key requires independent review before summative use."]}
        elif kind == "viva_set":
            items = [{
                "kind": "Viva", "specialty": unit["specialty"], "difficulty": unit["level"],
                "question": prompt["prompt"], "answer": "\n".join(prompt["key_points"]),
                "explanation": "Credit should be awarded for a coherent, safe and evidence-aware explanation; this outline is not an exhaustive model answer.",
                "source_title": pack["title"], "source_url": refs[0]["url"] if refs else "",
                "licence": "HSPTL-authored educational content; external sources are attributed, not reproduced.",
                "tags": unit["tags"],
            } for prompt in unit["viva"]]
            body = {"sections": [
                self._claim_section("viva_questions", [p["prompt"] for p in unit["viva"]]),
                self._claim_section("model_answer_points", ["; ".join(p["key_points"]) for p in unit["viva"]]),
                self._claim_section("scoring_criteria", ["Clinical reasoning, prioritisation, uncertainty, communication and safety."]),
            ], "assessment_items": items, "limitations": ["Viva prompts require examiner calibration before formal assessment."]}
        elif kind == "osce_station":
            station = unit["osce"]
            items = [{
                "kind": "OSCE", "specialty": unit["specialty"], "difficulty": unit["level"],
                "question": station["title"], "answer": "\n".join(station["checklist"]),
                "explanation": "Use the checklist as an educator review aid; it is not a validated assessment instrument.",
                "candidate_instructions": station["candidate_instructions"],
                "checklist": station["checklist"], "critical_errors": station["critical_errors"],
                "timer_seconds": station["time_seconds"], "source_title": pack["title"],
                "source_url": refs[0]["url"] if refs else "",
                "licence": "HSPTL-authored educational content; external sources are attributed, not reproduced.",
                "tags": unit["tags"],
            }]
            body = {"sections": [
                self._claim_section("candidate_instructions", [station["candidate_instructions"]]),
                self._claim_section("examiner_checklist", station["checklist"]),
                self._claim_section("critical_safety_items", station["critical_errors"]),
            ], "assessment_items": items, "limitations": ["Checklist is formative until reviewed and standard-set by qualified educators."]}
        elif kind == "on_call_scenario":
            body = {"sections": [
                self._claim_section("presentation", [case["presentation"], case["setting"]]),
                self._claim_section("available_background", [case["history"], case["observations"]]),
                self._claim_section("staged_findings", case["revealed_findings"]),
                self._claim_section("learner_tasks", [case["task"]]),
                self._claim_section("reasoning_and_safety_points", unit["teaching_points"] + unit["pitfalls"]),
                self._claim_section("debrief_prompts", unit["debrief"]),
            ], "limitations": ["Text-based educational scenario only; not a clinical protocol or patient-care instruction.", "Priorities, escalation and management must be reviewed by a qualified clinical educator."]}
        elif kind == "handover_template":
            body = {"sections": [
                self._claim_section("situation", [case["presentation"]]),
                self._claim_section("background", [case["history"], case["setting"]]),
                self._claim_section("assessment", [case["observations"], *case["revealed_findings"]]),
                self._claim_section("recommendation_prompt", ["Learner: state the immediate priorities, escalation plan and review requested."]),
                self._claim_section("safety_checks", unit["pitfalls"]),
            ], "limitations": ["Formative SBAR-style exercise; learner recommendations are not pre-filled.", "Requires educator review before use as a formal assessment template."]}
        elif kind == "simulation_brief":
            body = {"sections": [
                self._claim_section("prebrief", [case["setting"], "Educational simulation; explain the learning objectives and psychological safety before starting."]),
                self._claim_section("patient_presentation", [case["presentation"], case["history"], case["observations"]]),
                self._claim_section("learning_objectives", unit["objectives"]),
                self._claim_section("staged_findings", case["revealed_findings"]),
                self._claim_section("learner_tasks", [case["task"]]),
                self._claim_section("debrief_prompts", unit["debrief"] + unit["pitfalls"]),
            ], "limitations": ["This is a scenario brief, not an executable patient simulator or validated physiological model.", "A qualified clinical educator must verify the sequence, decisions and expected responses before scenario authoring or publication."]}
        else:
            raise ContentPackError(f"No generator for output kind: {kind}")
        body.update(metadata)
        body["validation"] = {"valid": True, "validator": "content_factory_v1", "checks": [
            "required learning objectives", "structured sections", "valid assessment answer keys" if kind == "question_set" else "output schema",
            "source attribution or explicit authored-framework status", "review gate retained",
        ]}
        if not refs:
            body["authorship_note"] = "HSPTL-authored framework; no external clinical guideline is claimed for this unit. Educator review is required."
        return {"workspace": workspace, "kind": kind, "title": title, "body": body,
                "source_refs": refs, "template_version": 1, "seed": int(seed),
                "destination_section": OUTPUT_SECTION[kind]}

    def build_batch(self, unit_ids: list[str], kinds: list[str], seed: int = 0) -> list[dict[str, Any]]:
        if not unit_ids or len(unit_ids) > 12:
            raise ContentPackError("Select between 1 and 12 content units")
        if not kinds or len(kinds) > len(DEFAULT_OUTPUT_TYPES):
            raise ContentPackError(f"Select between 1 and {len(DEFAULT_OUTPUT_TYPES)} output types")
        if len(set(unit_ids)) != len(unit_ids) or len(set(kinds)) != len(kinds):
            raise ContentPackError("Duplicate units or output types are not allowed")
        drafts = []
        for unit_id in unit_ids:
            for kind in kinds:
                drafts.append(self.build(unit_id, kind, seed))
        return drafts
