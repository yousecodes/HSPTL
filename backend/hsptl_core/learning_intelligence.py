"""HSPTL 5.1 formative learning intelligence.

Keeps source reliability appraisal separate from licensing and evidence certainty,
and adds learner practice preferences/attempt history without changing the shared
once-per-day Clinic/Ward Board lottery selection.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from typing import Any

RUBRIC = {
    "peer_review": "Editorial or peer-review controls",
    "authorship": "Author and institutional transparency",
    "method_transparency": "Methods and evidence traceability",
    "currency": "Currency and update visibility",
    "conflict_controls": "Conflict-of-interest and correction controls",
}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class LearningIntelligence:
    def __init__(self, store, lottery):
        self.store, self.lottery = store, lottery
        with store.transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS source_reliability_reviews (
                source_id TEXT PRIMARY KEY, scores_json TEXT NOT NULL, total_score REAL NOT NULL,
                band TEXT NOT NULL, reviewer TEXT NOT NULL, rationale TEXT NOT NULL,
                reviewed_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS learner_case_preferences (
                learner_id TEXT PRIMARY KEY, specialties_json TEXT NOT NULL DEFAULT '[]',
                difficulty TEXT NOT NULL DEFAULT 'Any', updated_at TEXT NOT NULL)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS learner_case_attempts (
                attempt_id TEXT PRIMARY KEY, learner_id TEXT NOT NULL, draw_id TEXT NOT NULL,
                case_id TEXT NOT NULL, response TEXT NOT NULL, confidence INTEGER,
                created_at TEXT NOT NULL, UNIQUE(learner_id, draw_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_learner_attempts_case ON learner_case_attempts(learner_id, case_id)")
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(35, ?)", (_now(),))

    @staticmethod
    def _band(score: float) -> str:
        if score >= 3.5: return "strong_source_controls"
        if score >= 2.5: return "moderate_source_controls"
        if score >= 1.5: return "limited_source_controls"
        return "weak_or_unverified_source_controls"

    def appraise_source(self, source_id: str, scores: dict[str, int], reviewer: str, rationale: str) -> dict[str, Any]:
        if set(scores) != set(RUBRIC):
            raise ValueError("Scores must include exactly: " + ", ".join(RUBRIC))
        if any(type(v) is not int or not 0 <= v <= 4 for v in scores.values()):
            raise ValueError("Each reliability score must be an integer from 0 to 4")
        if not reviewer.strip() or len(rationale.strip()) < 12:
            raise ValueError("A named reviewer and rationale of at least 12 characters are required")
        total = sum(scores.values()) / len(RUBRIC)
        item = {"source_id": source_id, "scores": scores, "mean_score": round(total, 2),
                "band": self._band(total), "reviewer": reviewer[:160],
                "rationale": rationale[:4000], "reviewed_at": _now(),
                "scope": "source reliability controls; not licence permission, clinical validity, or evidence certainty"}
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO source_reliability_reviews
                (source_id,scores_json,total_score,band,reviewer,rationale,reviewed_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
                scores_json=excluded.scores_json,total_score=excluded.total_score,band=excluded.band,
                reviewer=excluded.reviewer,rationale=excluded.rationale,reviewed_at=excluded.reviewed_at""",
                (source_id,json.dumps(scores,sort_keys=True),total,item['band'],item['reviewer'],item['rationale'],item['reviewed_at']))
        return item

    def source_appraisal(self, source_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM source_reliability_reviews WHERE source_id=?",(source_id,)).fetchone()
        if not row: return None
        return {"source_id":row["source_id"],"scores":json.loads(row["scores_json"]),
                "mean_score":row["total_score"],"band":row["band"],"reviewer":row["reviewer"],
                "rationale":row["rationale"],"reviewed_at":row["reviewed_at"],
                "scope":"source reliability controls; not licence permission, clinical validity, or evidence certainty"}

    def set_preferences(self, learner_id: str, specialties: list[str], difficulty: str) -> dict[str, Any]:
        learner_id=learner_id.strip()[:160]
        if not learner_id: raise ValueError("learner_id is required")
        if difficulty not in {"Any","Foundational","Intermediate","Advanced"}: raise ValueError("Unsupported difficulty")
        clean=sorted({" ".join(s.split())[:120] for s in specialties if s.strip()})[:30]
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO learner_case_preferences(learner_id,specialties_json,difficulty,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(learner_id) DO UPDATE SET specialties_json=excluded.specialties_json,
                difficulty=excluded.difficulty,updated_at=excluded.updated_at""",(learner_id,json.dumps(clean),difficulty,_now()))
        return {"learner_id":learner_id,"specialties":clean,"difficulty":difficulty}

    def recommendations(self, learner_id: str, limit: int = 8) -> dict[str, Any]:
        learner_id=learner_id.strip()[:160]
        with self.store.transaction() as conn:
            pref=conn.execute("SELECT * FROM learner_case_preferences WHERE learner_id=?",(learner_id,)).fetchone()
            done={r[0] for r in conn.execute("SELECT case_id FROM learner_case_attempts WHERE learner_id=?",(learner_id,))}
        specialties=json.loads(pref["specialties_json"]) if pref else []
        difficulty=pref["difficulty"] if pref else "Any"
        pool=self.lottery.eligible_pool()
        ranked=[]
        for case in pool:
            score=0
            if case["case_id"] not in done: score+=100
            if specialties and case.get("specialty") in specialties: score+=20
            if difficulty != "Any" and case.get("difficulty")==difficulty: score+=10
            tie=hashlib.sha256(f"{learner_id}:{case['case_id']}".encode()).hexdigest()
            ranked.append((score,tie,case))
        ranked.sort(key=lambda x:(-x[0],x[1]))
        return {"learner_id":learner_id,"items":[{"case_id":c["case_id"],"title":c["title"],"specialty":c["specialty"],"difficulty":c["difficulty"],"reason":"not_attempted" if c["case_id"] not in done else "preference_match"} for _,_,c in ranked[:max(1,min(limit,20))]],"eligible_pool":len(pool),"completed_cases":len(done),"scope":"practice recommendations, not competence or clinical-performance estimates"}

    def submit_case_attempt(self, learner_id: str, draw_id: str, response: str, confidence: int | None = None) -> dict[str, Any]:
        learner_id=learner_id.strip()[:160]; response=response.strip()
        if not learner_id or len(response)<20: raise ValueError("Learner ID and a reasoning response of at least 20 characters are required")
        if confidence is not None and not 1 <= confidence <= 5: raise ValueError("Confidence must be 1–5")
        with self.store.transaction() as conn:
            draw=conn.execute("SELECT * FROM lottery_draws WHERE draw_id=?",(draw_id,)).fetchone()
            if draw is None or not draw["case_id"]: raise ValueError("Unknown or empty daily draw")
            case=self.lottery.get_case(draw["case_id"])
            if case is None or self.lottery._ineligibility_reasons(case): raise ValueError("Drawn case is no longer eligible")
            attempt_id="lat_"+hashlib.sha256(f"{learner_id}:{draw_id}".encode()).hexdigest()[:24]
            conn.execute("""INSERT INTO learner_case_attempts(attempt_id,learner_id,draw_id,case_id,response,confidence,created_at)
                VALUES(?,?,?,?,?,?,?) ON CONFLICT(learner_id,draw_id) DO UPDATE SET response=excluded.response,
                confidence=excluded.confidence,created_at=excluded.created_at""",
                (attempt_id,learner_id,draw_id,draw["case_id"],response,confidence,_now()))
        return {"attempt_id":attempt_id,"state":"submitted","answer_reveal_available":True,"scope":"formative reasoning submission; not a diagnostic accuracy score"}
