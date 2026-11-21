"""Deterministic reflection prompts for learner-authored case drafts."""
from __future__ import annotations

from typing import Any


_TIME_SENSITIVE_TERMS = ("chest pain", "syncope", "hypoxia")


def evaluate_case_events(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return cautious learning prompts; these are not triage or care advice."""
    confidence_value = payload.get("confidence", 3)
    try:
        confidence = int(confidence_value)
    except (TypeError, ValueError):
        confidence = 3

    pathway = str(payload.get("specialty_pathway") or "").strip().casefold()
    differentials = payload.get("differentials")
    if not isinstance(differentials, (list, tuple)):
        differentials = []
    problem = str(payload.get("problem_representation") or "").casefold()
    events: list[dict[str, str]] = []

    if pathway in {"emergency", "emergency / acute assessment"} and confidence >= 4:
        events.append({
            "id": "high-confidence-emergency-review",
            "title": "Review confidence and safety-netting",
            "message": "Before finalising this learning draft, check which documented evidence supports your confidence and whether your escalation and safety-net considerations are explicit.",
        })

    if len(differentials) >= 4:
        events.append({
            "id": "broad-differential-review",
            "title": "Choose a discriminating next step",
            "message": "You recorded several alternatives. Identify what evidence would distinguish them; this prompt does not rank or validate the possibilities.",
        })

    if confidence <= 2 and any(term in problem for term in _TIME_SENSITIVE_TERMS):
        events.append({
            "id": "uncertain-time-sensitive-term",
            "title": "Reflect on uncertainty and escalation",
            "message": "A time-sensitive term appears in your draft alongside low confidence. If it describes an active concern, review the appropriate local process with a supervisor; this keyword prompt is not triage advice.",
        })

    return events
