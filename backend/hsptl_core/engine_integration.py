"""Cross-workspace integration of the seven shared core engines.

The six workspace skins are presentation only: they carry labels, density and
route maps, never clinical facts or executable predicates. This module is the
other half of that contract. It declares, per skin and per real product area,
*which* shared engine performs the work and *how* it is invoked, then offers a
single entry point that actually calls the engine and returns its real result.

Nothing here reimplements an engine. Every operation delegates to
Kernel, Reasoner, Logic, Composer, Router, Guards or Explain and returns the
engine's own derivation, guard trace or abstention.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class IntegrationError(ValueError):
    """Raised when an operation is not wired for a skin or area."""


@dataclass(frozen=True, slots=True)
class EngineBinding:
    """One engine applied to one product area of one skin."""

    skin: str
    area: str
    engine: str
    operation: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {"skin": self.skin, "area": self.area, "engine": self.engine,
                "operation": self.operation, "description": self.description}


# The seven engines, named exactly as the architecture endpoint reports them.
SEVEN_ENGINES: tuple[str, ...] = ("Kernel", "Reasoner", "Logic", "Composer", "Router", "Guards", "Explain")

# Six skins, matching frontend/src/hsptl40/skinRegistry.ts.
SKINS: tuple[str, ...] = ("clinic", "rounds", "lab", "ward", "exam", "portfolio")

# Real product areas per skin, taken from each skin's routeMap so the binding is
# anchored to an area that actually exists in the UI.
_BINDINGS: tuple[EngineBinding, ...] = (
    # Clinic — diagnostic reasoning over a case.
    EngineBinding("clinic", "simulation", "Logic", "enact_pathway",
                  "Enact the PROforma diagnostic pathway for the case."),
    EngineBinding("clinic", "reports", "Reasoner", "detect_conflict",
                  "Surface conflicting propositions across the case evidence."),
    EngineBinding("clinic", "debriefs", "Explain", "render_explanation",
                  "Render the derivation behind each debrief conclusion."),
    EngineBinding("clinic", "conference", "Router", "route",
                  "Route the composed case object into the conference area."),
    EngineBinding("clinic", "archives", "Kernel", "replay",
                  "Replay the canonical ledger to rebuild the archive projection."),
    # Rounds — oral examination and tagged reports.
    EngineBinding("rounds", "viva", "Composer", "compose",
                  "Compose the viva learning object from canonical slots."),
    EngineBinding("rounds", "reports", "Reasoner", "entailed_competencies",
                  "Derive the competencies a tagged report actually evidences."),
    EngineBinding("rounds", "procedure", "Guards", "decide",
                  "Evaluate the procedural precondition guard before rehearsal."),
    EngineBinding("rounds", "viva", "Explain", "render_explanation",
                  "Explain a viva answer against its derivation trace."),
    # Lab — investigation interpretation and skills.
    EngineBinding("lab", "spotters", "Reasoner", "entails_type",
                  "Check the asserted type of a spotter finding against the taxonomy."),
    EngineBinding("lab", "osce", "Logic", "enact_pathway",
                  "Enact the OSCE station workflow deterministically."),
    EngineBinding("lab", "spotters", "Guards", "decide",
                  "Guard interpretation claims against missing evidence."),
    EngineBinding("lab", "osce", "Router", "coverage_gaps",
                  "Report station coverage gaps before summative use."),
    # Ward — prioritisation, management and continuity.
    EngineBinding("ward", "oncall", "Logic", "enact_pathway",
                  "Enact the acute on-call PROforma plan."),
    EngineBinding("ward", "handover", "Composer", "compose",
                  "Compose the handover object with mandatory slots."),
    EngineBinding("ward", "consult", "Router", "route",
                  "Route a consultation request to the correct workspace area."),
    EngineBinding("ward", "progression", "Router", "record_mastery_signal",
                  "Record a progression mastery signal against a competency."),
    EngineBinding("ward", "oncall", "Guards", "decide",
                  "Abstain rather than guess when on-call evidence is missing."),
    # Exam Hall — assessment and IRT.
    EngineBinding("exam", "questions", "Router", "estimate_irt",
                  "Estimate ability from item responses with authored parameters."),
    EngineBinding("exam", "pearls", "Composer", "compose",
                  "Compose the pearl learning object from reviewed slots."),
    EngineBinding("exam", "summaries", "Reasoner", "entailed_competencies",
                  "Map summaries to the competencies they evidence."),
    EngineBinding("exam", "scores", "Explain", "render_explanation",
                  "Explain a score from its derivation, not from a black box."),
    # Portfolio — governance, progression, review.
    EngineBinding("portfolio", "progress", "Router", "mastery_fold",
                  "Fold recorded mastery signals into a progression projection."),
    EngineBinding("portfolio", "studio", "Composer", "compose",
                  "Compose content-factory objects through the shared composer."),
    EngineBinding("portfolio", "admin", "Guards", "decide",
                  "Evaluate the publication guard before release."),
    EngineBinding("portfolio", "tools", "Kernel", "status",
                  "Report canonical ledger status and projection freshness."),
    EngineBinding("portfolio", "admin", "Explain", "render_explanation",
                  "Explain a governance decision to an auditor."),
)


# Canonical product destinations are distinct from presentation skins. The UI
# exposes seven clinical workspaces while the six skins remain visual themes.
WORKSPACES: tuple[str, ...] = (
    "clinic", "lab", "ward", "library", "learning", "exam_hall", "rounds",
)

# Each workspace maps to real skin/area bindings already backed by the shared
# engines. Keeping this adapter declarative prevents workspace pages from
# growing their own clinical reasoning or governance logic.
_WORKSPACE_AREAS: dict[str, tuple[tuple[str, str], ...]] = {
    "clinic": (("clinic", "simulation"), ("clinic", "reports"),
               ("clinic", "debriefs"), ("clinic", "conference"), ("clinic", "archives")),
    "lab": (("lab", "spotters"), ("lab", "osce")),
    "ward": (("ward", "oncall"), ("ward", "handover"),
             ("ward", "consult"), ("ward", "progression")),
    "library": (("exam", "pearls"), ("exam", "summaries"), ("portfolio", "tools")),
    "learning": (("portfolio", "studio"), ("rounds", "viva"), ("exam", "pearls")),
    "exam_hall": (("exam", "questions"), ("exam", "scores"), ("exam", "summaries")),
    "rounds": (("rounds", "viva"), ("rounds", "reports"), ("rounds", "procedure")),
}


class EngineIntegration:
    """Invoke the real engines, per skin and area, with one uniform surface."""

    def __init__(self, *, kernel, reasoner, logic, composer, router, guards):
        self.kernel = kernel
        self.reasoner = reasoner
        self.logic = logic
        self.composer = composer
        self.router = router
        self.guards = guards

    # -- catalogue -------------------------------------------------------- #

    @staticmethod
    def catalogue() -> dict[str, Any]:
        matrix: dict[str, dict[str, list[dict[str, Any]]]] = {skin: {} for skin in SKINS}
        for binding in _BINDINGS:
            matrix[binding.skin].setdefault(binding.area, []).append(binding.to_dict())
        engine_coverage: dict[str, list[str]] = {engine: [] for engine in SEVEN_ENGINES}
        for binding in _BINDINGS:
            if binding.skin not in engine_coverage[binding.engine]:
                engine_coverage[binding.engine].append(binding.skin)
        return {
            "engines": list(SEVEN_ENGINES),
            "skins": list(SKINS),
            "matrix": matrix,
            "engine_coverage": {engine: sorted(skins) for engine, skins in engine_coverage.items()},
            "binding_count": len(_BINDINGS),
            "all_engines_integrated": all(engine_coverage[engine] for engine in SEVEN_ENGINES),
            "all_skins_integrated": all(matrix[skin] for skin in SKINS),
            "note": ("Skins contribute presentation and routing labels only. Every clinical or "
                     "decision operation below is executed by a shared engine."),
        }

    @staticmethod
    def bindings_for(skin: str, area: str = "") -> list[EngineBinding]:
        if skin not in SKINS:
            raise IntegrationError(f"Unknown workspace skin: {skin}")
        return [b for b in _BINDINGS
                if b.skin == skin and (not area or b.area == area)]

    @classmethod
    def workspace_catalogue(cls) -> dict[str, Any]:
        """Return the seven canonical workspaces and their real engine bindings."""
        matrix: dict[str, list[dict[str, Any]]] = {}
        for workspace, areas in _WORKSPACE_AREAS.items():
            entries: list[dict[str, Any]] = []
            for skin, area in areas:
                entries.extend(binding.to_dict() for binding in cls.bindings_for(skin, area))
            matrix[workspace] = entries
        covered = {entry["engine"] for entries in matrix.values() for entry in entries}
        return {
            "workspaces": list(WORKSPACES),
            "matrix": matrix,
            "workspace_count": len(matrix),
            "binding_count": sum(len(entries) for entries in matrix.values()),
            "engine_coverage": {engine: any(
                entry["engine"] == engine for entries in matrix.values() for entry in entries
            ) for engine in SEVEN_ENGINES},
            "all_workspaces_integrated": all(matrix.get(name) for name in WORKSPACES),
            "all_seven_engines_covered": all(engine in covered for engine in SEVEN_ENGINES),
            "note": "Workspace destinations are product areas; skins are presentation-only adapters.",
        }

    @classmethod
    def bindings_for_workspace(cls, workspace: str) -> list[EngineBinding]:
        if workspace not in _WORKSPACE_AREAS:
            raise IntegrationError(f"Unknown HSPTL workspace: {workspace}")
        return [binding for skin, area in _WORKSPACE_AREAS[workspace]
                for binding in cls.bindings_for(skin, area)]

    # -- dispatch --------------------------------------------------------- #

    def invoke(self, *, skin: str, area: str, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run one engine operation and return its genuine result."""
        allowed = {(b.engine, b.operation) for b in self.bindings_for(skin, area)}
        engine = next((e for e, op in allowed if op == operation), None)
        if engine is None:
            raise IntegrationError(
                f"Operation {operation!r} is not wired for {skin}/{area}. "
                f"Allowed: {sorted(op for _, op in allowed)}")
        handler: Callable[[dict[str, Any]], dict[str, Any]] = getattr(self, f"_op_{operation}")
        result = handler(payload)
        return {"skin": skin, "area": area, "engine": engine, "operation": operation,
                "result": result}

    # -- Kernel ----------------------------------------------------------- #

    def _op_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.kernel.status()

    def _op_replay(self, payload: dict[str, Any]) -> dict[str, Any]:
        through = payload.get("through_seq")
        return self.kernel.replay(through_seq=int(through) if through is not None else None)

    # -- Reasoner --------------------------------------------------------- #

    def _op_entails_type(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.reasoner.entails_type(payload["entity_id"], payload["requested_class"])

    def _op_detect_conflict(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.reasoner.detect_conflict(payload["proposition_key"], payload["scope_key"])

    def _op_entailed_competencies(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.reasoner.entailed_competencies(list(payload.get("learning_object_ids", [])))

    # -- Logic (PROforma) -------------------------------------------------- #

    def _op_enact_pathway(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.logic.enact(payload["plan"], facts=payload.get("facts"),
                                metadata=payload.get("metadata"))

    # -- Composer --------------------------------------------------------- #

    def _op_compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.composer.compose(payload["object_id"], payload["workspace"],
                                     payload["template_key"], payload.get("slots", {}))

    # -- Router ----------------------------------------------------------- #

    def _op_route(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.router.route(payload["object_id"], payload["workspace"],
                                 payload["expression"], payload.get("context", {}))

    def _op_estimate_irt(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.router.estimate_irt(list(payload.get("responses", [])))

    def _op_coverage_gaps(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.router.coverage_gaps(list(payload.get("required", [])),
                                         list(payload.get("covered", [])))

    def _op_record_mastery_signal(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.router.record_mastery_signal(
            payload["competency_id"], payload["learner_id"], payload["signal"],
            evidence_ref=payload.get("evidence_ref", ""), reviewer=payload.get("reviewer", ""))

    def _op_mastery_fold(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.router.mastery_fold(payload.get("learner_id"))

    # -- Guards ----------------------------------------------------------- #

    def _op_decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.guards.decide(payload["guard_id"], payload["expression"],
                                    payload.get("context", {}),
                                    rule_id=payload.get("rule_id", "PROFORMA-GUARD-001"))
        return result.as_dict() if hasattr(result, "as_dict") else dict(result)

    # -- Explain ---------------------------------------------------------- #

    def _op_render_explanation(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .hsp_tl40.explain import render_explanation
        return render_explanation(payload["derivation"], payload.get("audience", "clinical"))
