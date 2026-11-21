"""The HSPTL 4.0 kernel: one append-only event ledger and deterministic reads."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..deterministic_intelligence.engine import DeterministicIntelligenceEngine
from .event_contracts import payload_digest, validate_event_payload
from .event_monitors import inspect_event


class WritePrevented(RuntimeError):
    """Raised when a write-boundary or runtime monitor blocks an event."""
    def __init__(self, reason: str, audit_event: dict[str, Any]):
        self.reason = reason
        self.audit_event = audit_event
        super().__init__(f"WRITE PREVENTED: {reason} (audit event {audit_event.get('event_id', 'unavailable')})")


class EventKernel:
    """A lightweight module over the existing SQLite event ledger.

    It deliberately does not start a worker, broker or separate process. All
    platform state transitions are appended to the existing hash-chained
    ``di_events`` ledger and read back as event projections.
    """

    PLATFORM_EVENTS = {
        "platform.pathway.enacted",
        "platform.pathway.stepped",
        "platform.pathway.abstained",
        "platform.learning_object.composed",
        "platform.route.decided",
        "platform.guard.checked",
        "platform.guard.abstained",
        "platform.pulse.action_requested",
        "platform.pulse.observation_recorded",
        "platform.plugin.configured",
        "platform.mastery.signal_recorded",
        "platform.write.prevented",
        "platform.terminology.imported",
        "platform.curriculum.draft_created",
        "platform.curriculum.activated",
        "platform.learning.unit_opened",
        "platform.learning.quiz_submitted",
        "platform.scenario.draft_saved",
        "platform.scenario.published",
        "platform.facilitation.session_created",
        "platform.facilitation.event_recorded",
        "platform.safety.case_reviewed",
        "platform.synthetic_data.recipe_created",
        "platform.synthetic_data.recipe_activated",
        "platform.synthetic_data.job_queued",
        "platform.synthetic_data.stage_changed",
        "platform.synthetic_data.generation_completed",
        "platform.synthetic_data.validation_completed",
        "platform.synthetic_data.dataset_registered",
        "platform.synthetic_data.records_quarantined",
        "platform.synthetic_data.dataset_imported",
        "platform.synthetic_data.review_recorded",
        "platform.synthetic_data.job_cancelled",
        "simulation.run.started",
        "simulation.event.scheduled",
        "simulation.action.requested",
        "simulation.action.accepted",
        "simulation.action.rejected",
        "simulation.clock.advanced",
        "simulation.event.fired",
        "simulation.event.skipped",
        "simulation.state.transitioned",
        "simulation.observation.released",
        "simulation.result.available",
        "simulation.document.saved",
        "simulation.order.entered",
        "simulation.handover.submitted",
        "simulation.assessment.derived",
        "simulation.debrief.completed",
        "simulation.run.completed",
        "simulation.run.abandoned",
    }

    def __init__(self, engine: DeterministicIntelligenceEngine):
        self.engine = engine

    def _audit_prevented(self, event_type: str, payload: Any, reason: str, layer: str,
                         monitor: str | None = None) -> dict[str, Any]:
        audit_payload = {
            "attempted_event_type": str(event_type), "reason": reason,
            "payload_digest": payload_digest(payload), "layer": layer,
            "monitor": monitor,
        }
        with self.engine.connect() as conn:
            seq, event_id, event_hash = self.engine._append(conn, "platform.write.prevented", audit_payload)
        return {"seq": seq, "event_id": event_id, "event_hash": event_hash,
                "event_type": "platform.write.prevented", "payload": audit_payload}

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        valid, reason = validate_event_payload(event_type, payload)
        if event_type not in self.PLATFORM_EVENTS or not valid:
            audit = self._audit_prevented(event_type, payload, reason or "Unsupported HSPTL 4.0 event type.",
                                          "write_boundary")
            raise WritePrevented(reason or f"Unsupported HSPTL 4.0 event: {event_type}", audit)
        violations = inspect_event(event_type, payload)
        if violations:
            first = violations[0]
            audit = self._audit_prevented(event_type, payload, first["reason"],
                                          "runtime_event_monitor", first["monitor"])
            raise WritePrevented(first["reason"], audit)
        with self.engine.connect() as conn:
            seq, event_id, event_hash = self.engine._append(conn, event_type, payload)
        return {"seq": seq, "event_id": event_id, "event_hash": event_hash,
                "event_type": event_type, "payload": payload}

    def head(self) -> dict[str, Any]:
        with self.engine.connect() as conn:
            seq, digest = self.engine._head(conn)
        return {"seq": seq, "event_hash": digest}

    def events(self, *, after: int = 0, limit: int = 200,
               event_type: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 10000))
        with self.engine.connect() as conn:
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM di_events WHERE seq>? AND event_type=? ORDER BY seq LIMIT ?",
                    (max(0, after), event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM di_events WHERE seq>? ORDER BY seq LIMIT ?",
                    (max(0, after), limit),
                ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def platform_events(self, *, after: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        allowed = tuple(sorted(self.PLATFORM_EVENTS))
        placeholders = ",".join("?" for _ in allowed)
        with self.engine.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM di_events WHERE seq>? AND event_type IN ({placeholders}) ORDER BY seq LIMIT ?",
                (max(0, after), *allowed, max(1, min(int(limit), 10000))),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            output.append(item)
        return output

    def latest_enactment(self, enactment_id: str) -> dict[str, Any] | None:
        for event in reversed(self.platform_events(limit=10000)):
            payload = event["payload"]
            if payload.get("enactment_id") == enactment_id and event["event_type"] in {
                "platform.pathway.enacted", "platform.pathway.stepped", "platform.pathway.abstained"
            }:
                return payload.get("state")
        return None

    def replay(self, through_seq: int | None = None) -> dict[str, Any]:
        return self.engine.replay(through_seq)

    def status(self) -> dict[str, Any]:
        head = self.head()
        with self.engine.connect() as conn:
            row = conn.execute(
                "SELECT projection_seq, projection_hash FROM di_projections WHERE name='canonical'"
            ).fetchone()
        projection_seq = row["projection_seq"] if row else None
        return {
            "event_log": "append_only_sha256_chain",
            "head_seq": head["seq"],
            "head_hash": head["event_hash"],
            "canonical_projection_seq": projection_seq,
            "projection_fresh": projection_seq == head["seq"],
            "replay_required": projection_seq != head["seq"],
            "database": str(self.engine.db_path),
            "services_added": 0,
        }
