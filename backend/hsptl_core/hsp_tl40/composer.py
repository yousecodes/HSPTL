"""Template-and-slot composition over canonical graph projections."""
from __future__ import annotations

import json
from typing import Any

from ..deterministic_intelligence.engine import DeterministicIntelligenceEngine
from .explain import derive
from .guards import Guards
from .kernel import EventKernel


TEMPLATES: dict[str, dict[str, Any]] = {
    "evidence-linked-assertion@1.0.0": {
        "template_id": "evidence-linked-assertion", "version": "1.0.0",
        "slots": [
            {"name": "assertion", "required": True, "type": "clinical_assertion"},
            {"name": "evidence_context", "required": True, "type": "evidence_reference"},
            {"name": "limitations", "required": True, "type": "reviewed_limitation"},
        ],
        "preconditions": {"op": "and", "args": [
            {"op": "exists", "left": {"ref": "slots.assertion"}},
            {"op": "exists", "left": {"ref": "slots.evidence_context"}},
            {"op": "exists", "left": {"ref": "slots.limitations"}},
        ]},
    },
    "learning-note@1.0.0": {
        "template_id": "learning-note", "version": "1.0.0",
        "slots": [
            {"name": "objective", "required": True, "type": "authored_learning_objective"},
            {"name": "content", "required": True, "type": "authored_content"},
            {"name": "review_state", "required": True, "type": "review_state"},
        ],
        "preconditions": {"op": "and", "args": [
            {"op": "exists", "left": {"ref": "slots.objective"}},
            {"op": "exists", "left": {"ref": "slots.content"}},
            {"op": "eq", "left": {"ref": "slots.review_state"}, "right": "reviewed"},
        ]},
    },
}


class Composer:
    def __init__(self, engine: DeterministicIntelligenceEngine, kernel: EventKernel, guards: Guards):
        self.engine, self.kernel, self.guards = engine, kernel, guards

    def catalogue(self) -> dict[str, Any]:
        return {"templates": list(TEMPLATES.values()),
                "principle": "Templates contain slot contracts only; clinical facts live in canonical evidence entities."}

    def compose(self, object_id: str, workspace: str, template_key: str,
                slots: dict[str, Any]) -> dict[str, Any]:
        template = TEMPLATES.get(template_key)
        if not template:
            raise ValueError("Unknown or unversioned template.")
        required = [slot["name"] for slot in template["slots"] if slot["required"]]
        missing = [name for name in required if name not in slots or slots[name] in (None, "", [], {})]
        precondition = self.guards.decide("G-TEMPLATE-PRECONDITION-001",
            template["preconditions"], {"slots": slots}, rule_id="PROFORMA-TEMPLATE-001")
        if precondition.decision != "pass":
            return {"state": precondition.decision, "guard": precondition.as_dict(),
                    "missing_slots": missing}
        structural = self.guards.structural("G-COMPOSE-SLOTS-001", not missing,
            "Required slots are filled." if not missing else "Required slots are missing.",
            {"template": template_key, "missing": missing})
        if structural.decision != "pass":
            return {"state": structural.decision, "guard": structural.as_dict(), "missing_slots": missing}

        lineage: list[dict[str, Any]] = []
        assertion = slots.get("assertion") if template["template_id"] == "evidence-linked-assertion" else None
        if assertion is not None:
            if not isinstance(assertion, dict) or not all(assertion.get(k) for k in
                    ("text", "evidence_id", "appraisal_id", "source_span_id")):
                checked = self.guards.structural("G-PROV-001", False,
                    "Clinical assertions require text, evidence, appraisal and source span identifiers.",
                    {"object_id": object_id})
                return {"state": checked.decision, "guard": checked.as_dict()}
            with self.engine.connect() as conn:
                evidence = conn.execute("SELECT * FROM di_evidence WHERE evidence_id=?",
                                        (assertion["evidence_id"],)).fetchone()
                appraisal = conn.execute("SELECT * FROM di_appraisals WHERE appraisal_id=? AND evidence_id=?",
                                         (assertion["appraisal_id"], assertion["evidence_id"])).fetchone()
                span = conn.execute("SELECT * FROM di_source_spans WHERE span_id=? AND evidence_id=?",
                                    (assertion["source_span_id"], assertion["evidence_id"])).fetchone()
            proof_complete = bool(evidence and appraisal and span)
            proof_guard = self.guards.structural("G-PROV-001", proof_complete,
                "Assertion lineage entities exist." if proof_complete else "Assertion evidence/appraisal/source span is incomplete.",
                {"evidence_id": assertion["evidence_id"], "appraisal_id": assertion["appraisal_id"],
                 "source_span_id": assertion["source_span_id"]})
            if proof_guard.decision != "pass":
                return {"state": proof_guard.decision, "guard": proof_guard.as_dict()}
            appraisal_state = {"pass": True, "fail": False, "abstain": None}.get(appraisal["decision"])
            appraisal_guard = self.guards.structural("G-APP-001", appraisal_state,
                "Current appraisal is pass." if appraisal["decision"] == "pass" else
                "Current appraisal failed." if appraisal["decision"] == "fail" else
                "Current appraisal is unknown or abstained.",
                {"appraisal_id": appraisal["appraisal_id"], "decision": appraisal["decision"]})
            if appraisal_guard.decision != "pass":
                return {"state": appraisal_guard.decision, "guard": appraisal_guard.as_dict()}
            rights_state = {"permitted": True, "restricted": False, "prohibited": False}.get(evidence["rights_decision"])
            rights_guard = self.guards.structural("G-RIGHTS-001", rights_state,
                "Evidence reuse is explicitly permitted." if rights_state is True else
                "Evidence reuse is explicitly restricted." if rights_state is False else
                "Evidence rights are unknown; permission cannot be established.",
                {"evidence_id": evidence["evidence_id"], "rights_decision": evidence["rights_decision"]})
            if rights_guard.decision != "pass":
                return {"state": rights_guard.decision, "guard": rights_guard.as_dict()}
            span_guard = self.guards.structural("G-PROV-002", span["content_hash"] == evidence["content_hash"],
                "Source span hash matches immutable evidence." if span["content_hash"] == evidence["content_hash"] else "Source span hash mismatch.",
                {"span_id": span["span_id"]})
            if span_guard.decision != "pass":
                return {"state": span_guard.decision, "guard": span_guard.as_dict()}
            with self.engine.connect() as conn:
                evidence_event = conn.execute("SELECT event_id,seq,event_type FROM di_events WHERE event_type='evidence.registered' AND json_extract(payload_json,'$.evidence_id')=? ORDER BY seq LIMIT 1",
                                              (assertion["evidence_id"],)).fetchone()
                appraisal_event = conn.execute("SELECT event_id,seq,event_type FROM di_events WHERE seq=?",
                                               (appraisal["event_seq"],)).fetchone()
                span_event = conn.execute("SELECT event_id,seq,event_type FROM di_events WHERE seq=?",
                                          (span["event_seq"],)).fetchone()
            lineage = [
                {"kind": "assertion", "text": assertion["text"]},
                {"kind": "evidence_entity", "evidence_id": evidence["evidence_id"], "content_hash": evidence["content_hash"]},
                {"kind": "appraisal", "appraisal_id": appraisal["appraisal_id"], "decision": appraisal["decision"],
                 "event": dict(appraisal_event) if appraisal_event else None},
                {"kind": "source_event", "event": dict(evidence_event) if evidence_event else None},
                {"kind": "source_span", "span_id": span["span_id"], "event": dict(span_event) if span_event else None},
            ]
            if not evidence_event or not appraisal_event or not span_event:
                checked = self.guards.structural("G-PROV-003", None,
                    "A source event in the derivation chain is unavailable.", {"evidence_id": assertion["evidence_id"]})
                return {"state": checked.decision, "guard": checked.as_dict()}

        output = {"object_id": object_id, "workspace": workspace,
                  "template_id": template["template_id"], "template_version": template["version"],
                  "slots": slots, "assertion_lineage": lineage}
        derivation = derive(output_type="learning_object", output={"object_id": object_id,
                           "workspace": workspace, "template": template_key},
                           rules=["TEMPLATE-SLOT-001", "APP-001", "RIGHTS-001", "PROV-001"],
                           inputs=[{"slot": name, "filled": True} for name in required],
                           steps=[{"step": i + 1, **item} for i, item in enumerate(lineage)],
                           source_events=[item["event"] for item in lineage if item.get("event")])
        output["derivation"] = derivation
        event = self.kernel.append("platform.learning_object.composed", {"object": output})
        return {"state": "pass", "object": output, "event": event, "derivation": derivation}

    def graph_projection(self) -> dict[str, Any]:
        with self.engine.connect() as conn:
            entities = [dict(row) for row in conn.execute("SELECT entity_id,entity_class,label,created_seq FROM di_entities ORDER BY created_seq")]
            edges = [dict(row) for row in conn.execute("SELECT subject_id,predicate,object_id,evidence_id,event_seq FROM di_relationships ORDER BY event_seq")]
        return {"entities": entities, "relationships": edges,
                "projection": "query-time view over canonical event-backed graph tables"}
