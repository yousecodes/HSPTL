"""Pluggable review scheduling.

SimpleScheduler reproduces the shipped interval algorithm exactly, so existing
cards keep their behaviour. FsrsScheduler is an FSRS-4.5-style memory-state
adapter offered as an opt-in preview: it is not bit-identical to any released
FSRS version, has not been validated in HSPTL, and makes no retention claim.
Keep `simple` as the default until review history supports a change.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal, Protocol

Grade = Literal["Again", "Hard", "Good", "Easy"]
GRADES: tuple[Grade, ...] = ("Again", "Hard", "Good", "Easy")
CARD_STATES = {"new", "learning", "review", "suspended", "retired", "needs_source_review"}


@dataclass(slots=True)
class CardState:
    card_id: str
    state: str = "new"
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0
    stability: float = 0.0
    difficulty: float = 0.0
    due_date: str = ""
    last_reviewed: str = ""


@dataclass(slots=True)
class ScheduleResult:
    due_date: str
    interval_days: int
    state: str
    repetitions: int
    lapses: int
    stability: float
    difficulty: float
    scheduler: str
    diagnostics: dict = field(default_factory=dict)


class Scheduler(Protocol):
    name: str
    def next_review(self, card: CardState, grade: Grade, now: date) -> ScheduleResult: ...


class SimpleScheduler:
    """Deterministic legacy algorithm; default for backward compatibility."""
    name = "simple"

    def next_review(self, card: CardState, grade: Grade, now: date) -> ScheduleResult:
        interval, repetitions, lapses = card.interval_days, card.repetitions, card.lapses
        if grade == "Again":
            interval, repetitions, lapses = 1, 0, lapses + 1
        elif grade == "Hard":
            interval = 2 if interval == 0 else max(interval + 1, round(interval * 1.2))
            repetitions += 1
        elif grade == "Good":
            interval = 1 if interval == 0 else (3 if interval == 1
                                                else max(interval + 1, round(interval * 2.0)))
            repetitions += 1
        else:
            interval = 4 if interval == 0 else max(interval + 2, round(interval * 2.5))
            repetitions += 1
        state = "learning" if repetitions == 0 or interval <= 1 else "review"
        return ScheduleResult((now + timedelta(days=interval)).isoformat(), interval, state,
                              repetitions, lapses, 0.0, 0.0, self.name)


class FsrsScheduler:
    """FSRS-4.5-style preview: power forgetting curve with stability/difficulty."""
    name = "fsrs"
    DECAY = -0.5
    FACTOR = 19 / 81

    def __init__(self, request_retention: float = 0.9, weights: list[float] | None = None,
                 maximum_interval: int = 36500):
        self.request_retention = min(max(request_retention, 0.7), 0.99)
        self.w = weights or [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
                             1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61]
        self.maximum_interval = maximum_interval

    def retrievability(self, elapsed_days: float, stability: float) -> float:
        if stability <= 0:
            return 0.0
        return (1 + self.FACTOR * elapsed_days / stability) ** self.DECAY

    def _initial_difficulty(self, rating: int) -> float:
        return min(10.0, max(1.0, self.w[4] - (rating - 3) * self.w[5]))

    def _interval(self, stability: float) -> int:
        raw = stability / self.FACTOR * (self.request_retention ** (1 / self.DECAY) - 1)
        return int(max(1, min(round(raw), self.maximum_interval)))

    def next_review(self, card: CardState, grade: Grade, now: date) -> ScheduleResult:
        rating = GRADES.index(grade) + 1
        elapsed = 0
        if card.last_reviewed:
            try:
                elapsed = max(0, (now - date.fromisoformat(card.last_reviewed[:10])).days)
            except ValueError:
                elapsed = 0
        w = self.w
        if card.stability <= 0 or card.state == "new":
            stability = max(0.1, w[rating - 1])
            difficulty = self._initial_difficulty(rating)
            lapses, repetitions = card.lapses + int(rating == 1), int(rating > 1)
        else:
            retrievability = self.retrievability(elapsed, card.stability)
            reverted = w[7] * self._initial_difficulty(4) + (1 - w[7]) * (
                card.difficulty - w[6] * (rating - 3))
            difficulty = min(10.0, max(1.0, reverted))
            if rating == 1:
                stability = max(0.1, w[11] * difficulty ** (-w[12])
                                * ((card.stability + 1) ** w[13] - 1)
                                * math.exp(w[14] * (1 - retrievability)))
                lapses, repetitions = card.lapses + 1, 0
            else:
                modifier = w[15] if rating == 2 else (w[16] if rating == 4 else 1.0)
                stability = max(0.1, card.stability * (
                    1 + math.exp(w[8]) * (11 - difficulty) * card.stability ** (-w[9])
                    * (math.exp(w[10] * (1 - retrievability)) - 1) * modifier))
                lapses, repetitions = card.lapses, card.repetitions + 1
        interval = self._interval(stability)
        state = "learning" if rating == 1 or interval <= 1 else "review"
        return ScheduleResult((now + timedelta(days=interval)).isoformat(), interval, state,
                              repetitions, lapses, round(stability, 4), round(difficulty, 4),
                              self.name, {"elapsed_days": elapsed,
                                          "request_retention": self.request_retention,
                                          "validated_locally": False})


SCHEDULERS: dict[str, Scheduler] = {"simple": SimpleScheduler(), "fsrs": FsrsScheduler()}


def get_scheduler(name: str | None) -> Scheduler:
    return SCHEDULERS.get((name or "simple").casefold(), SCHEDULERS["simple"])


def scheduler_catalogue() -> list[dict]:
    return [
        {"id": "simple", "label": "Simple intervals (default)", "default": True,
         "validated_locally": False,
         "note": "Deterministic legacy algorithm retained for compatibility."},
        {"id": "fsrs", "label": "FSRS-style preview", "default": False,
         "validated_locally": False,
         "note": "Opt-in preview. No retention advantage has been measured in HSPTL."},
    ]
