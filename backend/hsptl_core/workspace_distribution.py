"""Distribution adapters into HSPTL's shared tagged-content workspace index."""
from __future__ import annotations
import re
from typing import Any
from .tagging import TagRepository
from .exams import ExamRepository, normalise_question_row

WORKSPACE_TARGETS = {
    "clinic": "conference", "rounds": "rounds", "lab": "lab",
    "ward": "on_call", "exam_hall": "exam", "portfolio": "data_tools",
}
CONTENT_TYPES = {
    "case_report": "case_report", "case_debrief": "debrief", "conference_brief": "case",
    "viva_set": "viva", "tagged_report": "case_report", "procedure_checklist": "case",
    "spot_diagnosis": "osce", "osce_station": "osce", "investigation_guide": "topic",
    "on_call_scenario": "simulation", "handover_template": "simulation", "consult_note": "case",
    "progression_record": "case", "pearl": "pearl", "topic_summary": "topic",
    "lecture_outline": "lecture", "question_set": "exam_question",
    "progress_snapshot": "case", "review_packet": "case", "development_plan": "topic",
}

class WorkspaceDistributionAdapter:
    """Writes approved artefacts to the native tagged-content index used by workspace libraries."""
    def __init__(self, store):
        self.tags = TagRepository(store)
        self.exams = ExamRepository(store.db_path)

    def deliver(self, artifact: dict[str, Any], section: str) -> dict[str, str]:
        self.tags.seed()
        kind=artifact["kind"]
        content_type=CONTENT_TYPES.get(kind)
        if not content_type:
            raise ValueError(f"No workspace content adapter for output kind: {kind}")
        workspace=WORKSPACE_TARGETS[artifact["workspace"]]
        body=artifact.get("body", {})
        sections=body.get("sections", [])
        summary=" ".join(claim.get("text", "") for item in sections for claim in item.get("claims", []))[:1200]
        # Deterministic broad tags are an index aid, not an inferred diagnosis or coding assertion.
        tag_ids=["task.clinical-reasoning"]
        if artifact["workspace"] == "lab": tag_ids=["task.investigation"]
        elif artifact["workspace"] == "ward": tag_ids=["task.management"]
        elif artifact["workspace"] == "exam_hall": tag_ids=["task.diagnosis"]
        elif artifact["workspace"] == "portfolio": tag_ids=["competency.evidence-appraisal"]
        # Assessment outputs are also inserted into the real examination bank as
        # unreviewed items. The artifact remains the citation/provenance authority.
        assessment_question_ids=[]
        if kind in {"question_set", "viva_set", "osce_station"}:
            items=body.get("assessment_items", [])
            if not items:
                raise ValueError(f"{kind} cannot be delivered without validated structured assessment items")
            prepared=[]
            source_refs=artifact.get("source_refs", [])
            for item in items:
                citation_note="\n\nHSPTL source-span citations: "+str(item.get("citations", []))
                payload={
                    "kind":{"question_set":"MCQ","viva_set":"Viva","osce_station":"OSCE"}[kind],
                    "specialty":(source_refs[0].get("specialty") if source_refs else "General medicine") or "General medicine",
                    "difficulty":"Intermediate","question":item["question"],"options":item.get("options",[]),
                    "answer":item["answer"],"explanation":(item.get("explanation","")+citation_note),
                    "candidate_instructions":item.get("candidate_instructions", ""),
                    "checklist":item.get("checklist", []),"critical_errors":item.get("critical_errors", []),
                    "timer_seconds":item.get("timer_seconds",600),
                    "source_title":artifact["title"],
                    "source_url":(source_refs[0].get("source_url") if source_refs else "") or "",
                    "licence":(source_refs[0].get("licence") if source_refs else "") or "",
                }
                if normalise_question_row(payload) is None:
                    raise ValueError("Assessment item failed examination-bank validation")
                prepared.append(payload)
            for payload in prepared:
                assessment_question_ids.append(self.exams.add_question(payload, reviewed=False)["id"])
        result=self.tags.register_content({
            "content_type":content_type,"content_id":artifact["id"],"title":artifact["title"],
            "workspace":workspace,"summary":f"[{section}] {summary}"[:1200],
            "source_status":"approved","content_url":f"/api/generation/artifacts/{artifact['id']}",
            "tags":tag_ids,"assigned_by":"ucks_generation_adapter",
        })
        return {"destination_id":result["item_id"],"destination_refs":assessment_question_ids,"adapter":"tagged_content_index+exam_question_bank" if assessment_question_ids else "tagged_content_index"}
