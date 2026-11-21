"""Bounded positive ontology entailment with explicit proof paths."""
from __future__ import annotations

from typing import Any

from ..deterministic_intelligence.ontology import CLASSES, RELATIONSHIPS, ancestors
from ..deterministic_intelligence.engine import DeterministicIntelligenceEngine
from .explain import derive
from .provability import classify_rule


class Reasoner:
    def __init__(self, engine: DeterministicIntelligenceEngine):
        self.engine = engine

    @staticmethod
    def _class_path(asserted: str, requested: str) -> list[str] | None:
        if asserted not in CLASSES or requested not in CLASSES:
            return None
        queue: list[tuple[str, list[str]]] = [(asserted, [asserted])]
        visited: set[str] = set()
        while queue:
            node, path = queue.pop(0)
            if node == requested:
                return path
            if node in visited:
                continue
            visited.add(node)
            for parent in CLASSES.get(node, []):
                queue.append((parent, path + [parent]))
        return None

    def entails_type(self, entity_id: str, requested_class: str) -> dict[str, Any]:
        if requested_class not in CLASSES:
            return {"entailed": None, "state": "abstain",
                    "reason": "Requested class is outside the supported ontology profile.",
                    "proof": [], "derivation": derive(output_type="ontology.entailment", output=None,
                    rules=["DL-POSITIVE-TAXONOMY-001"], inputs=[{"entity_id": entity_id,
                    "requested_class": requested_class}])}
        with self.engine.connect() as conn:
            entity = conn.execute("SELECT entity_id,entity_class,label,created_seq FROM di_entities WHERE entity_id=?",
                                  (entity_id,)).fetchone()
        if not entity:
            return {"entailed": None, "state": "abstain", "reason": "Entity is not in the canonical ontology projection.",
                    "proof": [], "derivation": derive(output_type="ontology.entailment", output=None,
                    rules=["DL-POSITIVE-TAXONOMY-001"], inputs=[{"entity_id": entity_id}])}
        asserted = entity["entity_class"]
        path = self._class_path(asserted, requested_class)
        entailed = path is not None
        proof = ([{"step": index, "class": name,
                   "relation": "asserted_type" if index == 0 else "subclass_of"}
                  for index, name in enumerate(path)] if path else [])
        state = "pass" if entailed else "fail"
        derivation = derive(output_type="ontology.entailment", output={"entity_id": entity_id,
                           "requested_class": requested_class, "entailed": entailed},
                           rules=["DL-POSITIVE-TAXONOMY-001"],
                           inputs=[{"entity_id": entity_id, "asserted_class": asserted,
                                    "source_event_seq": entity["created_seq"]}], steps=proof)
        return {"entailed": entailed, "state": state, "asserted_class": asserted,
                "requested_class": requested_class, "proof": proof, "derivation": derivation,
                "semantics": "positive finite taxonomy; absence is unknown, not false"}

    def relationship(self, subject_id: str, predicate: str, object_id: str) -> dict[str, Any]:
        if predicate not in RELATIONSHIPS:
            return {"entailed": None, "state": "abstain", "reason": "Unknown ontology predicate.", "proof": []}
        domain, range_class = RELATIONSHIPS[predicate]
        subject = self.entails_type(subject_id, domain)
        obj = self.entails_type(object_id, range_class)
        if subject["state"] == "abstain" or obj["state"] == "abstain":
            return {"entailed": None, "state": "abstain", "proof": [],
                    "reason": "One or both endpoints are not canonical."}
        if not subject["entailed"] or not obj["entailed"]:
            return {"entailed": False, "state": "fail", "proof": [],
                    "reason": "Typed relationship domain/range is not satisfied."}
        with self.engine.connect() as conn:
            row = conn.execute("""SELECT r.event_seq,e.entity_class,s.entity_class
                FROM di_relationships r
                JOIN di_entities e ON e.entity_id=r.subject_id
                JOIN di_entities s ON s.entity_id=r.object_id
                WHERE r.subject_id=? AND r.predicate=? AND r.object_id=?
                ORDER BY r.event_seq DESC LIMIT 1""", (subject_id, predicate, object_id)).fetchone()
        if not row:
            return {"entailed": None, "state": "abstain", "proof": [],
                    "reason": "No explicit relationship assertion exists; open-world absence is unknown."}
        proof = [{"step": 1, "fact": f"{subject_id} {predicate} {object_id}",
                  "evidence_event_seq": row["event_seq"]},
                 {"step": 2, "domain_proof": subject["proof"]},
                 {"step": 3, "range_proof": obj["proof"]}]
        derivation = derive(output_type="ontology.relationship", output={"entailed": True,
                           "subject_id": subject_id, "predicate": predicate, "object_id": object_id},
                           rules=["DL-TYPED-RELATIONSHIP-001"], inputs=[{"event_seq": row["event_seq"]}],
                           steps=proof)
        return {"entailed": True, "state": "pass", "proof": proof, "derivation": derivation}



    def detect_conflict(self, proposition_key: str, scope_key: str,
                        evidence_a: str, evidence_b: str,
                        polarity_a: str, polarity_b: str) -> dict[str, Any]:
        """Compute a scoped evidence conflict using Z3 only for its registered SMT rule."""
        import hashlib

        provability = classify_rule("SMT-CONFLICT-001")
        if provability["classification"] != "z3_required":
            return {"state": "abstain", "conflict": None,
                    "reason": "Conflict solver is not permitted by the provability registry.",
                    "provability": provability,
                    "derivation": derive(output_type="evidence.conflict", output=None,
                        rules=["SMT-CONFLICT-001"], inputs=[{"provability": provability}])}

        if not proposition_key or not scope_key or polarity_a not in {"positive", "negative"} or polarity_b not in {"positive", "negative"}:
            return {"state": "abstain", "conflict": None,
                    "reason": "Conflict comparison requires explicit proposition, scope and polarities.",
                    "derivation": derive(output_type="evidence.conflict", output=None,
                        rules=["SMT-CONFLICT-001"], inputs=[{"proposition_key": proposition_key,
                        "scope_key": scope_key, "polarity_a": polarity_a, "polarity_b": polarity_b}])}

        source_events: list[dict[str, Any]] = []
        with self.engine.connect() as conn:
            for evidence_id in (evidence_a, evidence_b):
                exists = conn.execute("SELECT 1 FROM di_evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
                event = conn.execute("""SELECT event_id,seq,event_type FROM di_events
                    WHERE event_type='evidence.registered'
                    AND json_extract(payload_json,'$.evidence_id')=? ORDER BY seq LIMIT 1""",
                    (evidence_id,)).fetchone()
                if not exists or not event:
                    return {"state": "abstain", "conflict": None,
                            "reason": "Both evidence items must be registered in the canonical evidence ledger.",
                            "derivation": derive(output_type="evidence.conflict", output=None,
                                rules=["SMT-CONFLICT-001"], inputs=[{"evidence_id": evidence_id}])}
                source_events.append(dict(event))

        try:
            from z3 import Bool, Solver, Not, sat, unsat
        except Exception:
            return {"state": "abstain", "conflict": None,
                    "reason": "Z3 is unavailable; conflict status cannot be decided.",
                    "derivation": derive(output_type="evidence.conflict", output=None,
                        rules=["SMT-CONFLICT-001"],
                        inputs=[{"proposition_key": proposition_key, "scope_key": scope_key,
                                 "evidence_a": evidence_a, "evidence_b": evidence_b}],
                        source_events=source_events)}

        symbol = "p_" + hashlib.sha256(f"{proposition_key}|{scope_key}".encode()).hexdigest()[:20]
        proposition = Bool(symbol)
        solver = Solver()
        solver.add(proposition if polarity_a == "positive" else Not(proposition))
        solver.add(proposition if polarity_b == "positive" else Not(proposition))
        result = solver.check()
        if result == unsat:
            state, conflict = "fail", True
        elif result == sat:
            state, conflict = "pass", False
        else:
            state, conflict = "abstain", None
        proof = {"solver": "z3", "result": str(result), "rule_id": "SMT-CONFLICT-001",
                 "provability": provability["classification"], "proposition_key": proposition_key,
                 "scope_key": scope_key, "polarity_a": polarity_a, "polarity_b": polarity_b}
        return {"state": state, "conflict": conflict, "proof": proof, "provability": provability,
                "derivation": derive(output_type="evidence.conflict",
                    output={"state": state, "conflict": conflict}, rules=["SMT-CONFLICT-001"],
                    inputs=[{"proposition_key": proposition_key, "scope_key": scope_key,
                             "evidence_a": evidence_a, "evidence_b": evidence_b,
                             "polarity_a": polarity_a, "polarity_b": polarity_b}],
                    steps=[proof], source_events=source_events)}

    def entailed_competencies(self, learning_object_ids: list[str]) -> dict[str, Any]:
        if not learning_object_ids:
            return {"state": "abstain", "competencies": [],
                    "reason": "At least one canonical learning-object id is required."}
        placeholders = ",".join("?" for _ in learning_object_ids)
        with self.engine.connect() as conn:
            rows = conn.execute(
                f"SELECT r.subject_id,r.predicate,r.object_id,r.event_seq,c.label,c.entity_class "
                f"FROM di_relationships r JOIN di_entities c ON c.entity_id=r.object_id "
                f"WHERE r.subject_id IN ({placeholders}) AND r.predicate IN ('assesses','supports_learning_objective') "
                "ORDER BY r.event_seq", tuple(learning_object_ids)).fetchall()
        if not rows:
            return {"state": "pass", "competencies": [],
                    "reason": "No explicit competency relation is entailed; no competency is inferred from activity alone.",
                    "derivation": derive(output_type="competency.entailment", output=[],
                        rules=["COMPETENCY-RELATION-001"], inputs=[{"learning_object_ids": learning_object_ids}])}
        competencies: dict[str, dict[str, Any]] = {}
        for row in rows:
            competencies[row["object_id"]] = {"competency_id": row["object_id"],
                "label": row["label"], "source_learning_object": row["subject_id"],
                "predicate": row["predicate"], "event_seq": row["event_seq"]}
        output = list(competencies.values())
        return {"state": "pass", "competencies": output,
                "derivation": derive(output_type="competency.entailment", output=output,
                    rules=["COMPETENCY-RELATION-001"],
                    inputs=[{"learning_object_ids": learning_object_ids}],
                    steps=[{"step": i + 1, **item} for i, item in enumerate(output)])}

    def catalogue(self) -> dict[str, Any]:
        return {"classes": CLASSES, "relationships": RELATIONSHIPS,
                "profile": {"name": "HSPTL-DL-FiniteTaxonomy-1",
                            "semantics": "positive finite entailment; missing assertions remain unknown",
                            "unsupported": ["negation", "disjunction", "cardinality", "existential and universal restrictions", "anonymous individuals"]}}
