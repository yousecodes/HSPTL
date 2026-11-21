"""Conservative formative feedback for learner-authored reasoning drafts.

This checks whether reasoning components were documented. It does not score
clinical correctness, rank diagnoses, or recommend patient care.
"""
from __future__ import annotations
from typing import Any


def assess_reasoning_completeness(payload: dict[str, Any]) -> dict[str, Any]:
    differentials = [str(x).strip() for x in payload.get("differentials", []) if str(x).strip()]
    checks = [
        ("problem_representation", "Problem representation", bool(str(payload.get("problem_representation", "")).strip()), "Summarise the key documented findings, timeframe and clinical context without adding missing facts."),
        ("differential_breadth", "Differential breadth", len(differentials) >= 2, "Record at least two plausible alternatives, then prioritise them with explicit reasons."),
        ("supporting_evidence", "Supporting evidence", bool(str(payload.get("evidence_for", "")).strip()), "Link each leading possibility to specific findings in the source record."),
        ("opposing_evidence", "Opposing evidence and uncertainty", bool(str(payload.get("evidence_against", "")).strip()), "Document contradictory evidence, missing information and what would change your view."),
        ("investigation_strategy", "Investigation strategy", bool(str(payload.get("investigation_plan", "")).strip()), "For each proposed test, state its purpose and how a positive or negative result could change management."),
        ("working_diagnosis", "Working diagnosis stated", bool(str(payload.get("working_diagnosis", "")).strip()), "State your current working diagnosis and what uncertainty remains. This is not checked for correctness."),
        ("management_plan", "Management plan documented", bool(str(payload.get("management_plan", "")).strip()), "Outline a learning-level plan and identify what requires senior or local guideline input."),
        ("safety_net", "Safety-netting considered", bool(str(payload.get("safety_net", "")).strip()), "Record deterioration features, escalation triggers and follow-up considerations."),
        ("communication_plan", "Communication considered", bool(str(payload.get("communication_plan", "")).strip()), "Consider explanation, consent, uncertainty and shared decision-making."),
    ]
    completed = sum(1 for _, _, ok, _ in checks if ok)
    return {
        "type": "completeness_only",
        "label": "Reasoning documentation review",
        "completed": completed,
        "total": len(checks),
        "coverage_percent": round(completed / len(checks) * 100),
        "dimensions": [{"id": key, "label": label, "documented": ok, "suggestion": suggestion if not ok else None} for key, label, ok, suggestion in checks],
        "confidence_reflection": {
            "self_rated": int(payload.get("confidence", 3)),
            "prompt": "What specific evidence would increase or decrease your confidence?",
        },
        "limitations": [
            "This is a completeness check, not a measure of diagnostic accuracy or clinical competence.",
            "No diagnosis is marked correct or incorrect because this imported record is not a curated diagnostic case.",
            "A blank section may reflect missing source data rather than a learner omission.",
            "Management and safety-net prompts are educational reflections, not patient-specific care instructions.",
        ],
    }

# ---------------------------------------------------------------------------
# Phase 2 - process-level feedback.
# No keyword scoring of clinical prose, no diagnosis ranking, no competence
# inference. Every signal is an explicit learner action or a structural count.
# ---------------------------------------------------------------------------

def assess_evidence_coverage(payload: dict[str, Any],
                             available_facts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    facts = available_facts or []
    available_keys = {str(f.get("fact_key")) for f in facts if f.get("fact_key")}
    cited = [str(k) for k in (payload.get("cited_fact_keys") or []) if str(k).strip()]
    valid = [k for k in cited if k in available_keys]
    unknown = [k for k in cited if k not in available_keys]
    undated = sum(1 for f in facts if not f.get("effective_at"))
    return {
        "available_facts": len(facts), "cited_facts": len(valid), "cited_fact_keys": valid,
        "unresolvable_citations": unknown, "undated_facts": undated,
        "coverage_percent": round(len(valid) / len(facts) * 100) if facts else 0,
        "linked": bool(valid),
        "suggestion": None if valid else (
            "Cite at least one documented finding so your reasoning can be traced to the source."),
        "scope": "Citation linkage only; a citation does not confirm the interpretation.",
    }


def assess_reasoning_process(payload: dict[str, Any]) -> dict[str, Any]:
    differentials = [str(x).strip() for x in payload.get("differentials", []) if str(x).strip()]
    checks = [
        ("alternatives_externalised", "More than one explanation recorded", len(differentials) >= 2,
         "Record at least two competing explanations before committing."),
        ("prioritisation_explicit", "Priority order justified",
         bool(str(payload.get("prioritisation_rationale", "")).strip()),
         "State why one explanation ranks above another (likelihood and harm if missed)."),
        ("contradiction_sought", "Opposing evidence sought",
         bool(str(payload.get("evidence_against", "")).strip()),
         "Look actively for findings that argue against your leading explanation."),
        ("missing_data_named", "Expected-but-missing data named",
         bool(str(payload.get("expected_missing", "")).strip()),
         "Name what you expected to find and could not; unavailable is not normal."),
        ("next_discriminator", "Next discriminating question stated",
         bool(str(payload.get("next_discriminating_question", "")).strip()),
         "Write the question or observation that would most change your ranking."),
        ("decision_impact", "Investigation linked to a decision",
         bool(str(payload.get("investigation_plan", "")).strip()),
         "For each test, state the result that would change your next step."),
        ("safety_considered", "Safety and escalation considered",
         bool(str(payload.get("safety_net", "")).strip()),
         "Record deterioration features and an escalation threshold."),
    ]
    completed = sum(1 for _, _, ok, _ in checks if ok)
    return {
        "completed": completed, "total": len(checks),
        "checks": [{"id": k, "label": label, "demonstrated": ok,
                    "suggestion": None if ok else suggestion}
                   for k, label, ok, suggestion in checks],
        "method": "Explicit-field structural review; no natural-language scoring.",
        "limitations": [
            "A completed field shows reasoning was externalised, not that it is clinically sound.",
            "No diagnosis is ranked, marked correct, or compared with a hidden answer key.",
        ],
    }


def suggest_learning_actions(process: dict[str, Any],
                             coverage: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if not coverage["linked"]:
        actions.append({"id": "cite-evidence", "label": "Practise citing documented findings",
                        "rationale": "Your reasoning was not linked to any source fact.",
                        "review_prompt": "How do I distinguish documented absence from unavailable data?"})
    for check in process["checks"]:
        if not check["demonstrated"]:
            actions.append({"id": check["id"], "label": check["label"],
                            "rationale": check["suggestion"],
                            "review_prompt": f"In my next case, what will I write for: {check['label'].lower()}?"})
    return actions[:4]


def build_feedback(payload: dict[str, Any], *,
                   available_facts: list[dict[str, Any]] | None = None,
                   curated_rubric: dict[str, Any] | None = None) -> dict[str, Any]:
    base = assess_reasoning_completeness(payload)
    coverage = assess_evidence_coverage(payload, available_facts)
    process = assess_reasoning_process(payload)
    base["evidence_coverage"] = coverage
    base["process"] = process
    base["learning_actions"] = suggest_learning_actions(process, coverage)
    base["scope"] = "process_only"
    base["curated_rubric"] = None
    if curated_rubric:
        if not (curated_rubric.get("reviewer") and curated_rubric.get("review_date")):
            raise ValueError("A curated rubric requires a named reviewer and review date")
        base["scope"] = "curated_rubric"
        base["curated_rubric"] = {
            "author": curated_rubric.get("author", ""), "reviewer": curated_rubric["reviewer"],
            "review_date": curated_rubric["review_date"],
            "criteria": curated_rubric.get("criteria", []),
            "note": "Author-supplied teaching rubric for a curated case; not a competence assessment.",
        }
    return base
