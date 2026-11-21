"""Transparent, learner-facing clinical reasoning rubric helpers.

This module organises self-assessment; it does not judge clinical correctness
or infer competence from keywords. A human or qualified educator must review
clinical reasoning and safety-critical decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCORE_ANCHORS = {
    0: "Not demonstrated: absent, materially inaccurate, or unsafe.",
    1: "Emerging: partial or vague; important elements are missing or unsupported.",
    2: "Developing: mostly appropriate; reasoning is present but not fully integrated or justified.",
    3: "Strong: focused, accurate, justified with relevant evidence, and explicit about uncertainty.",
}

DOMAIN_GUIDANCE: dict[str, str] = {
    "problem representation": "Compress the case into a one-sentence summary using discriminating background, time course and findings.",
    "relevant background": "Include only background that changes pre-test probability, risk or management; state what is not known.",
    "chronology": "Clarify onset, duration, progression, pattern and important associated symptoms.",
    "positive findings": "Prioritise discriminating positive findings and link each to the clinical problem.",
    "negative": "Use only explicitly documented negatives; never convert a missing field into a negative finding.",
    "missing data": "Name the missing information and explain how obtaining it could change the assessment.",
    "history": "Choose focused questions that distinguish the leading diagnoses and identify immediate risks.",
    "examination": "Specify the focused examination, expected findings and limitations of the available record.",
    "risk": "Identify time-critical threats, justify urgency and state the escalation threshold.",
    "differential": "Generate a concise, relevant differential including a dangerous alternative not to miss.",
    "prioritisation": "Rank by likelihood and consequence if missed; explain the order rather than listing diagnoses.",
    "supporting": "Link case-specific findings to each leading hypothesis and explain their diagnostic value.",
    "opposing": "Actively seek contradictory findings and explain what would weaken each hypothesis.",
    "investigation": "State the clinical question, test choice, expected result and decision that would follow.",
    "result": "Interpret values with units, date, age, context and appropriate reference information.",
    "uncertainty": "Separate established facts, plausible interpretation and unknown information.",
    "management": "Separate documented care from a proposed plan; address immediate priorities and evidence sources.",
    "medication": "Check current use, indication, dose, age/weight, allergies, interactions and contraindications.",
    "monitoring": "Specify what to monitor, how often, triggers for escalation and follow-up.",
    "outcome": "Report only outcomes documented in the source; do not infer recovery or treatment success.",
    "reflection": "Identify a specific reasoning strength, a gap, an uncertainty and an actionable next step.",
    "transferable": "Extract a generalisable clinical lesson and a retrieval question for future cases.",
}


def normalise_rubric(payload: Any, criteria: list[str]) -> tuple[dict[str, int], dict[str, str]]:
    """Read new schema and old flat int dictionaries without losing legacy data."""
    if not isinstance(payload, dict):
        payload = {}
    if isinstance(payload.get("ratings"), dict):
        raw_ratings = payload.get("ratings", {})
        raw_evidence = payload.get("evidence", {}) if isinstance(payload.get("evidence"), dict) else {}
    else:
        # Wardle 1.0 stored {criterion: 0..2}; retain as an initial 0..2 rating.
        raw_ratings = payload
        raw_evidence = {}
    ratings: dict[str, int] = {}
    evidence: dict[str, str] = {}
    for criterion in criteria:
        try:
            value = int(raw_ratings.get(criterion, 0))
        except (TypeError, ValueError):
            value = 0
        ratings[criterion] = max(0, min(3, value))
        evidence[criterion] = str(raw_evidence.get(criterion, "") or "")[:1500]
    return ratings, evidence


def criterion_guidance(criterion: str) -> str:
    name = criterion.casefold()
    for token, guidance in DOMAIN_GUIDANCE.items():
        if token in name:
            return guidance
    return "State what you did, cite the relevant case evidence, and identify what remains uncertain or could be improved."


@dataclass(frozen=True)
class RubricSummary:
    earned: int
    possible: int
    percentage: float
    strengths: tuple[str, ...]
    priorities: tuple[str, ...]


def summarise_self_assessment(ratings: dict[str, int]) -> RubricSummary:
    """Summarise learner-selected ratings; intentionally not a competence score."""
    if not ratings:
        return RubricSummary(0, 0, 0.0, (), ())
    safe = {str(k): max(0, min(3, int(v))) for k, v in ratings.items()}
    earned = sum(safe.values())
    possible = len(safe) * 3
    strengths = tuple(k for k, v in safe.items() if v == 3)
    priorities = tuple(k for k, v in safe.items() if v <= 1)
    return RubricSummary(earned, possible, earned / possible * 100 if possible else 0.0, strengths, priorities)


def build_tutor_feedback_prompt(
    *, case_context: str, stage_name: str, questions: list[str], answer: str,
    ratings: dict[str, int], evidence: dict[str, str],
) -> str:
    """Create a rigorous human/AI review prompt while preserving provenance caveats."""
    rating_lines = []
    for criterion, score in ratings.items():
        rating_lines.append(
            f"- {criterion}: learner self-rating {score}/3 ({SCORE_ANCHORS[score]})\n"
            f"  Learner's evidence / reflection: {evidence.get(criterion, '').strip() or '[not supplied]'}\n"
            f"  Improvement focus: {criterion_guidance(criterion)}"
        )
    question_lines = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    return f"""You are a supportive, rigorous clinical educator reviewing a medical student's written case reasoning.

SAFETY AND PROVENANCE RULES
- This is a synthetic educational case, not a real patient.
- Do not invent patient findings, observations, examination results, diagnoses or outcomes.
- Explicitly separate (1) source-recorded facts, (2) clinical interpretation, and (3) unknown or unavailable information.
- A coded condition is a record entry, not independent proof of a diagnosis.
- Missing data are not negative findings. Historical medication requests are not proof of current use.
- Do not give patient-specific prescribing or emergency-care instructions. Frame management as educational principles and cite current authoritative guidance when available.
- Do not treat the learner's self-ratings as objective marks. Challenge them constructively against the answer and evidence.

CASE RECORD
{case_context}

LEARNING STAGE: {stage_name}
QUESTIONS
{question_lines}

LEARNER ANSWER
{answer or '[No answer supplied]'}

LEARNER SELF-ASSESSMENT (0–3 anchors)
{chr(10).join(rating_lines) or '[Not completed]'}

REQUIRED FEEDBACK
1. Give an accurate problem representation (or explain why the evidence is insufficient).
2. Identify the strongest parts of the student's reasoning and quote the relevant answer text.
3. Identify omissions and incorrect assumptions. For every criticism, explain its clinical significance.
4. Review differential generation, likelihood and consequence prioritisation, supporting and opposing evidence.
5. Review the logic of investigations and whether results are interpreted in clinical context.
6. Review safety, escalation, medication cautions and uncertainty as relevant to this stage.
7. Give one improved model answer using only case facts plus clearly labelled general teaching.
8. Give three targeted retrieval questions and one specific action for the next case.
9. Explicitly flag any point requiring educator verification or an up-to-date local guideline.

Do not produce a single numeric competence grade. Provide criterion-level formative feedback instead."""
