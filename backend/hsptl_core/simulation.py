"""Structured prebrief, facilitation and guided reflection for case simulation."""
from __future__ import annotations

LEARNING_OUTCOMES = [
    [
        "Construct a one-sentence problem representation from documented facts.",
        "Distinguish explicit negative findings from unavailable information.",
        "Identify immediate threats that need active exclusion.",
    ],
    [
        "Generate a concise differential that includes important dangerous alternatives.",
        "Prioritise diagnoses using both likelihood and consequence if missed.",
        "Compare hypotheses using supporting and opposing case evidence.",
    ],
    [
        "Link each proposed investigation to a focused clinical question.",
        "Interpret available results using units and patient context.",
        "Identify missing, discordant or uninterpretable data.",
    ],
    [
        "Separate management documented in the record from a proposed plan.",
        "State safety, monitoring, escalation and follow-up considerations.",
        "Identify medication and patient-specific factors requiring verification.",
    ],
    [
        "Describe the outcome only where it is documented.",
        "Identify uncertainty, reasoning strengths and learning gaps.",
        "Set one actionable goal for the next clinical case.",
    ],
]

PREBRIEF_ITEMS = [
    "I understand the learning objectives and expected level of performance.",
    "I understand the learner role, time frame and how to progress through the case.",
    "I will distinguish source-recorded facts from inference and missing information.",
    "I understand that this is a synthetic educational case, not a real clinical encounter.",
    "I will pause when needed, state uncertainty and prioritise safety over completion.",
]

PEARLS_DEBRIEF = [
    {
        "key": "setting",
        "title": "1 · Set the scene",
        "prompt": "What was the purpose of this exercise? What would make this a psychologically safe learning discussion?",
        "hint": "Treat uncertainty and mistakes as learning opportunities. This is private study; do not enter real patient identifiers.",
    },
    {
        "key": "reactions",
        "title": "2 · Reactions",
        "prompt": "What felt difficult, surprising or uncertain during the case?",
        "hint": "Name the moment where your confidence changed and what triggered it.",
    },
    {
        "key": "description",
        "title": "3 · Description",
        "prompt": "What happened? Summarise the documented facts, your decisions and what information was unavailable.",
        "hint": "Keep record facts, interpretations and unknowns separate.",
    },
    {
        "key": "analysis",
        "title": "4 · Analysis",
        "prompt": "Why did you make those decisions? Which evidence supported or opposed your leading hypotheses? What else could explain the findings?",
        "hint": "Explore reasoning, prioritisation, investigation choices, safety and the effect of missing data.",
    },
    {
        "key": "summary",
        "title": "5 · Summary and transfer",
        "prompt": "What are your three most transferable learning points, and what will you do differently in the next case?",
        "hint": "End with one specific, observable improvement goal and a retrieval question.",
    },
]


def debrief_completion(payload: dict[str, str]) -> tuple[int, int]:
    total = len(PEARLS_DEBRIEF)
    completed = sum(bool(str(payload.get(item["key"], "")).strip()) for item in PEARLS_DEBRIEF)
    return completed, total


def clean_debrief_payload(payload: dict[str, object]) -> dict[str, str]:
    allowed = {item["key"] for item in PEARLS_DEBRIEF}
    return {key: str(value or "").strip()[:5000] for key, value in payload.items() if key in allowed}
