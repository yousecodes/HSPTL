"""Four progress dimensions, deliberately not aggregated into one score.

Practice, reasoning process, retention and transfer are reported separately.
A single combined number would create false precision and could be mistaken
for clinical competence.
"""
from __future__ import annotations

import json
from typing import Any


def progress_dimensions(store, case_store, episodes, exams) -> dict[str, Any]:
    lifetime = store.stats()
    with case_store.transaction() as conn:
        rows = conn.execute(
            "SELECT differential_json, evidence_against, expected_missing, safety_net, "
            "cited_fact_keys_json FROM clinical_learning_attempts").fetchall()
    attempts = len(rows)
    externalised = cited = 0
    for row in rows:
        try:
            differentials = json.loads(row["differential_json"] or "[]")
        except (TypeError, ValueError):
            differentials = []
        if (len(differentials) >= 2 and (row["evidence_against"] or "").strip()
                and (row["expected_missing"] or "").strip() and (row["safety_net"] or "").strip()):
            externalised += 1
        try:
            if json.loads(row["cited_fact_keys_json"] or "[]"):
                cited += 1
        except (TypeError, ValueError):
            pass
    analytics = store.review_analytics()
    exam_stats = exams.stats()
    completed = episodes.list(status="completed", limit=200)["total"]
    with store.transaction() as conn:
        transfer = conn.execute("SELECT COUNT(*) n FROM artifact_links "
                                "WHERE relation='revisited'").fetchone()["n"]
    recommendations: list[dict[str, str]] = []
    for bucket in exam_stats["by_specialty"]:
        if bucket["total"] >= 2 and bucket["percentage"] < 70:
            recommendations.append({
                "id": f"exam-{bucket['specialty'].lower().replace(' ', '-')}",
                "department": "Specialties",
                "action": f"Review {bucket['specialty']} fundamentals",
                "reason": f"Recent reviewed questions scored {bucket['percentage']}%",
            })
    if exam_stats["osce_attempts"]:
        weak_osce = [b for b in exam_stats["osce_by_kind"] if b["total"] >= 2 and b["percentage"] < 70]
        for bucket in weak_osce:
            recommendations.append({
                "id": f"osce-{bucket['kind'].lower().replace(' ', '-')}",
                "department": "OSCE",
                "action": f"Practise {bucket['kind']}",
                "reason": f"Recent reviewed station attempts scored {bucket['percentage']}%",
            })
    if lifetime["due"]:
        recommendations.append({
            "id": "revision-due",
            "department": "Pearls",
            "action": "Complete due spaced-revision cards",
            "reason": f"{lifetime['due']} revision card(s) are due",
        })
    if attempts and attempts > externalised:
        recommendations.append({
            "id": "reasoning-documentation",
            "department": "Clinic",
            "action": "Externalise the next differential and uncertainty",
            "reason": "Some saved reasoning attempts do not complete the evidence-and-safety documentation dimensions",
        })
    return {
        "practice": {"cases_completed": completed, "reasoning_attempts": attempts,
                     "quiz_attempts": lifetime["quizzes"],
                     "exam_attempts": exam_stats["exam_attempts"],
                     "review_sessions": analytics["reviews_recorded"]},
        "reasoning_process": {
            "attempts_with_externalised_reasoning": externalised, "attempts_total": attempts,
            "percent": round(externalised / attempts * 100, 1) if attempts else None,
            "attempts_citing_source_facts": cited,
            "scope": "Structure of documented reasoning; not diagnostic accuracy."},
        "retention": {"cards_due": lifetime["due"],
                      "again_rate_percent": analytics["again_rate_percent"],
                      "forecast": analytics["forecast"],
                      "scope": "Card recall only; not clinical performance."},
        "transfer": {"learning_actions_revisited": int(transfer),
                     "scope": "Learner-marked revisits of earlier learning actions."},
        "exam": exam_stats,
        "recommendations": recommendations,
        "guardrail": "These dimensions are intentionally not combined into a single score.",
    }
