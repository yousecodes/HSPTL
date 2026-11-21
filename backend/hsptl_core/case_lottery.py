"""Daily Clinical Case Lottery: one shared case per day for Ward Board and Clinic.

Design constraints that shape this module:

* **Shared, not duplicated.** The same selection serves both workspaces. A learner
  who opens Ward Board and then Clinic sees the same case for that day, because
  the randomly selected assignment is persisted and shared.
* **Gated selection.** A case is eligible when it is an HSPTL-curated teaching
  vignette or has been clinically reviewed/validated, is published, and its
  rights permit the use being made of it. If nothing
  qualifies the lottery returns an explicit ``no_eligible_case`` state. It never
  falls back to an unreviewed case and never invents one.
* **No answer leakage.** The reveal payload is withheld until the learner
  submits or explicitly reveals. Withholding is enforced server-side, not by
  hiding fields in the UI.
* **Stable within a day, fresh across days.** A cryptographically secure random
  draw is persisted under a unique date key, so refreshes and restarts return
  the same assignment. Event cooldowns reduce repetitive themes when alternatives exist.
"""
from __future__ import annotations

import secrets
import json
import uuid
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

WORKSPACES = ("ward_board", "clinic")

# A case must have a curriculum-eligible or clinical-review status before it can be drawn.
REQUIRED_CLINICAL_REVIEW = {"curated", "reviewed", "validated", "synthetic_qa_passed"}
REQUIRED_PUBLICATION = {"published"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_" + uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class LotteryCandidate:
    """One eligible case, already reduced to non-revealing metadata."""

    case_id: str
    title: str
    specialty: str
    difficulty: str
    stem: str
    prompt: str
    presenting_complaint: str
    patient_age_value: int | None
    patient_age_unit: str
    label: str
    rights_status: str
    clinical_review_status: str
    publication_status: str
    source_refs: tuple[dict[str, Any], ...] = ()
    reveal: dict[str, Any] | None = None

    def public_dict(self, *, revealed: bool) -> dict[str, Any]:
        """Serialise for a learner. The reveal payload is only present when allowed."""
        payload = {
            "case_id": self.case_id,
            "title": self.title,
            "specialty": self.specialty,
            "difficulty": self.difficulty,
            "stem": self.stem,
            "prompt": self.prompt,
            "presenting_complaint": self.presenting_complaint,
            "patient_age_value": self.patient_age_value,
            "patient_age_unit": self.patient_age_unit,
            "label": self.label,
            "rights_status": self.rights_status,
            "clinical_review_status": self.clinical_review_status,
            "clinical_validation_status": ("not_assessed_synthetic_qa_only" if self.clinical_review_status == "synthetic_qa_passed" else
                                            "not_assessed" if self.clinical_review_status == "curated" else
                                            self.clinical_review_status),
            "publication_status": self.publication_status,
            "publication_label": ("Provisional educational use" if self.clinical_review_status == "synthetic_qa_passed" else
                                  "Published HSPTL curriculum" if self.clinical_review_status == "curated" else
                                  self.publication_status.replace("_", " ").title()),
            "source_refs": [dict(ref) for ref in self.source_refs],
            "answer_withheld": not revealed,
        }
        if revealed and self.reveal is not None:
            payload["reveal"] = dict(self.reveal)
        return payload


class LotteryError(ValueError):
    """Raised for invalid lottery requests."""


class CaseLottery:
    """Securely random daily selection over an eligible, rights-cleared pool."""

    def __init__(self, store, *, auto_replenish: bool = False):
        self.store = store
        self.auto_replenish = bool(auto_replenish)
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS lottery_cases (
                case_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                specialty TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT 'Intermediate',
                stem TEXT NOT NULL,
                prompt TEXT NOT NULL,
                presenting_complaint TEXT NOT NULL DEFAULT '',
                patient_age_value INTEGER,
                patient_age_unit TEXT NOT NULL DEFAULT 'years',
                label TEXT NOT NULL,
                rights_status TEXT NOT NULL DEFAULT 'unknown',
                clinical_review_status TEXT NOT NULL DEFAULT 'unreviewed',
                publication_status TEXT NOT NULL DEFAULT 'unpublished',
                reveal_json TEXT NOT NULL DEFAULT '{}',
                source_refs_json TEXT NOT NULL DEFAULT '[]',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_lottery_eligible
                ON lottery_cases(enabled, publication_status, clinical_review_status);
            CREATE TABLE IF NOT EXISTS lottery_draws (
                draw_id TEXT PRIMARY KEY,
                draw_date TEXT NOT NULL,
                workspace TEXT NOT NULL,
                case_id TEXT NOT NULL,
                pool_size INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'selected',
                selection_method TEXT NOT NULL DEFAULT 'secure_random',
                event_json TEXT NOT NULL DEFAULT '{}',
                pool_digest TEXT NOT NULL DEFAULT '',
                policy_version TEXT NOT NULL DEFAULT '6.0.0',
                created_at TEXT NOT NULL,
                UNIQUE(draw_date, workspace)
            );
            CREATE INDEX IF NOT EXISTS idx_lottery_draw_date ON lottery_draws(draw_date DESC);
            CREATE TABLE IF NOT EXISTS clinical_event_catalogue (
                event_id TEXT PRIMARY KEY,
                event_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                version INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lottery_reveals (
                reveal_id TEXT PRIMARY KEY,
                draw_id TEXT NOT NULL REFERENCES lottery_draws(draw_id),
                learner_id TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT 'explicit_reveal',
                created_at TEXT NOT NULL,
                UNIQUE(draw_id, learner_id)
            );
            CREATE INDEX IF NOT EXISTS idx_lottery_reveal_draw ON lottery_reveals(draw_id);
            """)
            # Additive migration: existing lottery cases and daily assignments are preserved.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(lottery_cases)")}
            for name, ddl in {
                "presenting_complaint": "TEXT NOT NULL DEFAULT ''",
                "patient_age_value": "INTEGER",
                "patient_age_unit": "TEXT NOT NULL DEFAULT 'years'",
            }.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE lottery_cases ADD COLUMN {name} {ddl}")
            draw_columns = {row[1] for row in conn.execute("PRAGMA table_info(lottery_draws)")}
            if "selection_method" not in draw_columns:
                conn.execute("ALTER TABLE lottery_draws ADD COLUMN selection_method TEXT NOT NULL DEFAULT 'legacy_deterministic'")
            for name, ddl in {
                "event_json": "TEXT NOT NULL DEFAULT '{}'",
                "pool_digest": "TEXT NOT NULL DEFAULT ''",
                "policy_version": "TEXT NOT NULL DEFAULT '6.0.0'",
            }.items():
                if name not in draw_columns:
                    conn.execute(f"ALTER TABLE lottery_draws ADD COLUMN {name} {ddl}")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(36, ?)", (_now(),)
            )
            from .clinical_catalogues import clinical_event_catalogue
            for event in clinical_event_catalogue():
                conn.execute(
                    "INSERT OR IGNORE INTO clinical_event_catalogue(event_id,event_json,active,version,updated_at) VALUES(?,?,1,1,?)",
                    (event["id"], json.dumps(event, ensure_ascii=False), _now()),
                )

    # -- pool ------------------------------------------------------------- #

    def seed_curated_cases(self) -> dict[str, int]:
        """Idempotently enrol HSPTL's existing authored teaching vignettes.

        These are the same fictional, source-linked learning cases that were
        already available in Clinic.  Their ``curated`` status is deliberately
        distinct from ``reviewed`` or ``validated``: they are usable as authored
        educational material, but are not represented as expert-validated
        patient records or clinical protocols.
        """
        from .content_labels import LABEL_GENERATED
        from .puzzles import PUZZLES

        created = 0
        existing = 0
        for puzzle in PUZZLES:
            puzzle_id = str(puzzle.get("id", "")).strip()
            clues = [str(item).strip() for item in puzzle.get("clues", []) if str(item).strip()]
            answer = str(puzzle.get("answer", "")).strip()
            explanation = str(puzzle.get("explanation", "")).strip()
            if not puzzle_id or len(clues) < 2 or not answer or not explanation:
                continue

            case_id = f"hsptl-curriculum-{puzzle_id}"
            if self.get_case(case_id) is not None:
                existing += 1
                continue

            first_clue = clues[0]
            age_match = re.search(r"\b(\d{1,3})[- ]year[- ]old\b", first_clue, re.IGNORECASE)
            age_value = int(age_match.group(1)) if age_match else None
            specialty = str(puzzle.get("specialty", "General medicine"))
            title = f"{specialty} clinical reasoning case"
            source_title = str(puzzle.get("source_title", "HSPTL educational source"))
            source_url = str(puzzle.get("source_url", ""))
            source_refs = ([{
                "title": source_title,
                "source_url": source_url,
                "source_type": "guideline_or_reference",
                "reuse_status": "citation_only",
                "note": "Citation only; the HSPTL vignette is independently authored.",
            }] if source_url else [])
            stem = "\n\n".join(f"{index + 1}. {clue}" for index, clue in enumerate(clues[:5]))
            self.register_case(
                case_id=case_id,
                title=title,
                specialty=specialty,
                difficulty=str(puzzle.get("difficulty", "Intermediate")),
                stem=stem,
                prompt=("What is the most likely diagnosis? Explain the key supporting findings, "
                        "one important alternative, and how you would confirm or safely assess it."),
                presenting_complaint=first_clue,
                patient_age_value=age_value,
                patient_age_unit="years",
                label=LABEL_GENERATED,
                rights_status="permitted",
                clinical_review_status="curated",
                publication_status="published",
                reveal={
                    "diagnosis": answer,
                    "explanation": explanation,
                    "key_takeaways": list(puzzle.get("takeaways", [])),
                    "educational_status": "HSPTL-authored fictional teaching vignette; not a real patient record.",
                },
                source_refs=source_refs,
            )
            created += 1
        return {"created": created, "already_present": existing,
                "total_curated_cases": created + existing}

    def replenish_curated_cases(self) -> dict[str, int]:
        """Idempotently import every HSPTL-authored curriculum vignette.

        This is intentionally limited to the authored curriculum bank. Harvested
        publisher records and arbitrary model output are never promoted into the
        daily lottery by this operation.
        """
        result = self.seed_curated_cases()
        result["source"] = "hsptl_authored_curriculum"
        result["automatic"] = 1
        return result

    def register_case(self, *, case_id: str = "", title: str, stem: str, prompt: str,
                      label: str, specialty: str = "", difficulty: str = "Intermediate",
                      presenting_complaint: str = "", patient_age_value: int | None = None,
                      patient_age_unit: str = "years",
                      rights_status: str = "unknown", clinical_review_status: str = "unreviewed",
                      publication_status: str = "unpublished",
                      reveal: dict[str, Any] | None = None,
                      source_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        from .content_labels import normalise_label
        resolved_label = normalise_label(label)
        if not title.strip() or not stem.strip() or not prompt.strip():
            raise LotteryError("A lottery case requires a title, stem and prompt")
        if patient_age_value is not None and not 0 <= int(patient_age_value) <= 125:
            raise LotteryError("patient_age_value must be between 0 and 125")
        if patient_age_unit not in {"years", "months", "weeks", "days"}:
            raise LotteryError("patient_age_unit must be years, months, weeks or days")
        identifier = case_id.strip() or _id("lcase")
        now = _now()
        with self.store.transaction() as conn:
            conn.execute(
                """INSERT INTO lottery_cases
                   (case_id,title,specialty,difficulty,stem,prompt,presenting_complaint,patient_age_value,patient_age_unit,label,rights_status,
                    clinical_review_status,publication_status,reveal_json,source_refs_json,
                    enabled,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
                   ON CONFLICT(case_id) DO UPDATE SET
                     title=excluded.title, specialty=excluded.specialty,
                     difficulty=excluded.difficulty, stem=excluded.stem, prompt=excluded.prompt,
                     presenting_complaint=excluded.presenting_complaint,
                     patient_age_value=excluded.patient_age_value, patient_age_unit=excluded.patient_age_unit,
                     label=excluded.label, rights_status=excluded.rights_status,
                     clinical_review_status=excluded.clinical_review_status,
                     publication_status=excluded.publication_status,
                     reveal_json=excluded.reveal_json, source_refs_json=excluded.source_refs_json,
                     updated_at=excluded.updated_at""",
                (identifier, title.strip(), specialty, difficulty, stem.strip(), prompt.strip(),
                 presenting_complaint.strip(), patient_age_value, patient_age_unit,
                 resolved_label, rights_status, clinical_review_status, publication_status,
                 json.dumps(reveal or {}, ensure_ascii=False),
                 json.dumps(source_refs or [], ensure_ascii=False), now, now),
            )
        return self.get_case(identifier)  # type: ignore[return-value]

    def set_eligibility(self, case_id: str, *, enabled: bool) -> dict[str, Any]:
        with self.store.transaction() as conn:
            conn.execute("UPDATE lottery_cases SET enabled=?, updated_at=? WHERE case_id=?",
                         (int(enabled), _now(), case_id))
        record = self.get_case(case_id)
        if record is None:
            raise LotteryError("Unknown lottery case")
        return record

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM lottery_cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["reveal"] = json.loads(record.pop("reveal_json") or "{}")
        record["source_refs"] = json.loads(record.pop("source_refs_json") or "[]")
        record["enabled"] = bool(record["enabled"])
        return record

    def list_cases(self, *, include_ineligible: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT case_id FROM lottery_cases"
        if not include_ineligible:
            sql += (" WHERE enabled=1 AND publication_status IN ('published')"
                    " AND clinical_review_status IN ('curated','reviewed','validated','synthetic_qa_passed')")
        sql += " ORDER BY updated_at DESC LIMIT ?"
        with self.store.transaction() as conn:
            ids = [row["case_id"] for row in conn.execute(sql, (max(1, min(int(limit), 1000)),))]
        return [item for item in (self.get_case(cid) for cid in ids) if item]

    def eligibility_report(self) -> dict[str, Any]:
        """Explain exactly why cases are or are not eligible."""
        with self.store.transaction() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT case_id,title,enabled,publication_status,clinical_review_status,rights_status"
                " FROM lottery_cases ORDER BY title")]
        eligible, blocked = [], []
        for row in rows:
            reasons = self._ineligibility_reasons(row)
            if reasons:
                blocked.append({**row, "reasons": reasons})
            else:
                eligible.append(row)
        return {"eligible_count": len(eligible), "blocked_count": len(blocked),
                "eligible": eligible, "blocked": blocked}

    @staticmethod
    def _ineligibility_reasons(row: dict[str, Any]) -> list[str]:
        reasons = []
        if not row.get("enabled"):
            reasons.append("case_disabled")
        if row.get("publication_status") not in REQUIRED_PUBLICATION:
            reasons.append("not_published")
        if row.get("clinical_review_status") not in REQUIRED_CLINICAL_REVIEW:
            reasons.append("not_clinically_reviewed")
        if row.get("rights_status") in {"prohibited", "restricted", "unknown", ""}:
            reasons.append("rights_not_cleared_for_reuse")
        return reasons

    def eligible_pool(self) -> list[dict[str, Any]]:
        return [case for case in self.list_cases() if not self._ineligibility_reasons(case)]

    # -- draw ------------------------------------------------------------- #

    def draw(self, *, workspace: str, draw_date: str | None = None) -> dict[str, Any]:
        """Return the day's case for a workspace, creating the draw if needed.

        The draw is shared: both workspaces resolve to the same persisted ``case_id``
        and event snapshot for a given date.
        """
        if workspace not in WORKSPACES:
            raise LotteryError(f"Unknown lottery workspace: {workspace}")
        # Runtime instances opt into reconciliation; isolated/test instances keep
        # explicit pool semantics. Harvested records are never promoted here.
        if self.auto_replenish:
            self.replenish_curated_cases()
        day = (draw_date or date.today().isoformat())[:10]
        try:
            date.fromisoformat(day)
        except ValueError as exc:
            raise LotteryError("draw_date must be an ISO date (YYYY-MM-DD)") from exc

        existing = self._existing_draw(day)
        if existing is not None and existing.get("state") != "no_eligible_case":
            return self._draw_payload(existing, workspace)

        # Re-evaluate an earlier empty draw. This matters when startup seeding or
        # automatic source preparation populates the pool later on the same day.
        pool = self.eligible_pool()
        if not pool:
            if existing is not None:
                return self._draw_payload(existing, workspace)
            record = self._record_draw(day, workspace, case_id="", pool_size=0, state="no_eligible_case", selection_method="none")
            return {
                "state": "no_eligible_case",
                "draw_date": day,
                "workspace": workspace,
                "pool_size": 0,
                "case": None,
                "message": ("No eligible case is currently available in the shared daily lottery. "
                            "The lottery will not substitute an unreviewed or rights-unclear case."),
                "eligibility": self.eligibility_report(),
                "draw_id": record["draw_id"],
            }

        # Select with a cryptographically secure source of randomness. The draw is
        # persisted immediately, so all workspaces and refreshes see the same case.
        chosen = secrets.choice(pool)
        event = self._select_event(pool, day)
        record = self._record_draw(day, workspace, case_id=chosen["case_id"],
                                   pool_size=len(pool), state="selected", selection_method="secure_random",
                                   event=event, pool_digest=__import__("hashlib").sha256(
                                       "|".join(sorted(x["case_id"] for x in pool)).encode()).hexdigest())
        return self._draw_payload(record, workspace)

    def event_catalogue(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT event_json,active,version FROM clinical_event_catalogue"
        if active_only:
            sql += " WHERE active=1"
        sql += " ORDER BY event_id"
        with self.store.transaction() as conn:
            rows = conn.execute(sql).fetchall()
        result = []
        for row in rows:
            item = json.loads(row["event_json"])
            item["active"] = bool(row["active"])
            item["catalogue_version"] = int(row["version"])
            result.append(item)
        return result

    def upsert_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(event.get("id", "")).strip()
        title = str(event.get("title", "")).strip()
        if not event_id or len(event_id) > 100 or not title or len(title) > 160:
            raise LotteryError("Event requires a stable id and title")
        weight = int(event.get("selection_weight", 1))
        if not 1 <= weight <= 100:
            raise LotteryError("selection_weight must be between 1 and 100")
        event["selection_weight"] = weight
        with self.store.transaction() as conn:
            old = conn.execute("SELECT version FROM clinical_event_catalogue WHERE event_id=?", (event_id,)).fetchone()
            version = int(old["version"]) + 1 if old else 1
            conn.execute("""INSERT INTO clinical_event_catalogue(event_id,event_json,active,version,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET event_json=excluded.event_json,
                active=excluded.active,version=excluded.version,updated_at=excluded.updated_at""",
                (event_id, json.dumps(event, ensure_ascii=False), int(bool(event.get("active", True))), version, _now()))
        return next(item for item in self.event_catalogue(active_only=False) if item["id"] == event_id)

    @staticmethod
    def _event_matches(event: dict[str, Any], case: dict[str, Any]) -> bool:
        text = " ".join(str(case.get(k, "")) for k in ("title", "specialty", "presenting_complaint", "stem", "prompt")).casefold()
        signals = [str(x).casefold() for x in event.get("case_signals", [])]
        specialty = str(case.get("specialty", "")).casefold()
        category = str(event.get("category", "")).casefold()
        return any(signal and signal in text for signal in signals) or (category and category in specialty) or (specialty and specialty in str(event.get("title", "")).casefold())

    def _select_event(self, pool: list[dict[str, Any]], day: str) -> dict[str, Any] | None:
        eligible = []
        for event in self.event_catalogue(active_only=True):
            if not event.get("active", True):
                continue
            if any(self._event_matches(event, case) for case in pool):
                eligible.append(event)
        if not eligible:
            return None
        # Apply each event's configured cooldown where alternatives exist.
        with self.store.transaction() as conn:
            rows = conn.execute("SELECT draw_date,event_json FROM lottery_draws WHERE event_json!='{}' ORDER BY draw_date DESC LIMIT 90").fetchall()
        cooled = []
        for event in eligible:
            cooldown = max(0, min(int(event.get("cooldown_days", 2)), 90))
            recent_same = 0
            for row in rows:
                if (day > row["draw_date"] and (date.fromisoformat(day) - date.fromisoformat(row["draw_date"])).days <= cooldown):
                    try:
                        if json.loads(row["event_json"]).get("id") == event["id"]:
                            recent_same += 1
                    except (TypeError, ValueError):
                        continue
            if recent_same == 0:
                cooled.append(event)
        choices = cooled or eligible
        weights = [max(1, min(int(event.get("selection_weight", 1)), 100)) for event in choices]
        pick = secrets.randbelow(sum(weights))
        for event, weight in zip(choices, weights):
            if pick < weight:
                return {k: event[k] for k in ("id", "title", "category", "icon", "summary", "setting", "learning_objectives", "workspaces")}
            pick -= weight
        return None

    def _existing_draw(self, day: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM lottery_draws WHERE draw_date=? ORDER BY created_at LIMIT 1", (day,)
            ).fetchone()
        return dict(row) if row else None

    def _record_draw(self, day: str, workspace: str, *, case_id: str, pool_size: int,
                     state: str, selection_method: str = "secure_random",
                     event: dict[str, Any] | None = None, pool_digest: str = "") -> dict[str, Any]:
        draw_id = _id("ldraw")
        now = _now()
        with self.store.transaction() as conn:
            # One row per date: the draw is shared across workspaces.
            existing = conn.execute("SELECT * FROM lottery_draws WHERE draw_date=? LIMIT 1",
                                    (day,)).fetchone()
            if existing:
                # Keep the date's original identity while replacing only a prior
                # empty-state record once an eligible pool has since appeared.
                if existing["state"] == "no_eligible_case" and state == "selected":
                    conn.execute("""UPDATE lottery_draws SET workspace=?,case_id=?,pool_size=?,state=?,
                        selection_method=?,event_json=?,pool_digest=?,policy_version=?,created_at=?
                        WHERE draw_id=?""",
                        (workspace, case_id, pool_size, state, selection_method,
                         json.dumps(event or {}, ensure_ascii=False), pool_digest,
                         "6.0.0", now, existing["draw_id"]))
                    updated = conn.execute("SELECT * FROM lottery_draws WHERE draw_id=?",
                                           (existing["draw_id"],)).fetchone()
                    return dict(updated)
                return dict(existing)
            conn.execute(
                """INSERT INTO lottery_draws(draw_id,draw_date,workspace,case_id,pool_size,state,selection_method,event_json,pool_digest,policy_version,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (draw_id, day, workspace, case_id, pool_size, state, selection_method,
                 json.dumps(event or {}, ensure_ascii=False), pool_digest, "6.0.0", now),
            )
        return {"draw_id": draw_id, "draw_date": day, "workspace": workspace,
                "case_id": case_id, "pool_size": pool_size, "state": state,
                "selection_method": selection_method, "event_json": json.dumps(event or {}, ensure_ascii=False),
                "pool_digest": pool_digest, "policy_version": "6.0.0", "created_at": now}

    def _draw_payload(self, draw_record: dict[str, Any], workspace: str) -> dict[str, Any]:
        case = self.get_case(draw_record["case_id"]) if draw_record["case_id"] else None
        if case is None:
            return {
                "state": "no_eligible_case", "draw_date": draw_record["draw_date"],
                "workspace": workspace, "pool_size": int(draw_record["pool_size"]),
                "case": None, "draw_id": draw_record["draw_id"],
                "message": "The drawn case is no longer available. It has been withdrawn from the pool.",
                "eligibility": self.eligibility_report(),
            }
        # Re-check at read time: a case withdrawn after the draw must not leak.
        reasons = self._ineligibility_reasons(case)
        if reasons:
            return {
                "state": "no_eligible_case", "draw_date": draw_record["draw_date"],
                "workspace": workspace, "pool_size": int(draw_record["pool_size"]),
                "case": None, "draw_id": draw_record["draw_id"],
                "message": "The drawn case no longer meets eligibility requirements.",
                "ineligibility_reasons": reasons,
                "eligibility": self.eligibility_report(),
            }
        candidate = LotteryCandidate(
            case_id=case["case_id"], title=case["title"], specialty=case["specialty"],
            difficulty=case["difficulty"], stem=case["stem"], prompt=case["prompt"],
            presenting_complaint=case.get("presenting_complaint") or case["stem"],
            patient_age_value=case.get("patient_age_value"),
            patient_age_unit=case.get("patient_age_unit") or "years",
            label=case["label"], rights_status=case["rights_status"],
            clinical_review_status=case["clinical_review_status"],
            publication_status=case["publication_status"],
            source_refs=tuple(case["source_refs"]), reveal=case["reveal"] or {},
        )
        return {
            "state": "selected",
            "draw_id": draw_record["draw_id"],
            "draw_date": draw_record["draw_date"],
            "workspace": workspace,
            "pool_size": int(draw_record["pool_size"]),
            "selection_method": draw_record.get("selection_method", "legacy_deterministic"),
            "clinical_event": json.loads(draw_record.get("event_json") or "{}") or None,
            "shared_across_workspaces": list(WORKSPACES),
            "case": candidate.public_dict(revealed=False),
        }

    # -- reveal ----------------------------------------------------------- #

    def reveal(self, *, draw_id: str, learner_id: str, reason: str = "explicit_reveal") -> dict[str, Any]:
        """Release the answer payload. Recorded so leakage can be audited."""
        if not learner_id.strip():
            raise LotteryError("A learner identifier is required to reveal an answer")
        if reason not in {"explicit_reveal", "after_submission"}:
            raise LotteryError("Unsupported reveal reason")
        with self.store.transaction() as conn:
            draw = conn.execute("SELECT * FROM lottery_draws WHERE draw_id=?", (draw_id,)).fetchone()
            if draw is None:
                raise LotteryError("Unknown lottery draw")
            conn.execute(
                """INSERT OR IGNORE INTO lottery_reveals(reveal_id,draw_id,learner_id,reason,created_at)
                   VALUES(?,?,?,?,?)""",
                (_id("lrev"), draw_id, learner_id.strip()[:160], reason, _now()),
            )
        case = self.get_case(draw["case_id"]) if draw["case_id"] else None
        if case is None:
            raise LotteryError("The drawn case is no longer available")
        reasons = self._ineligibility_reasons(case)
        if reasons:
            raise LotteryError("The drawn case no longer meets eligibility requirements")
        candidate = LotteryCandidate(
            case_id=case["case_id"], title=case["title"], specialty=case["specialty"],
            difficulty=case["difficulty"], stem=case["stem"], prompt=case["prompt"],
            presenting_complaint=case.get("presenting_complaint") or case["stem"],
            patient_age_value=case.get("patient_age_value"),
            patient_age_unit=case.get("patient_age_unit") or "years",
            label=case["label"], rights_status=case["rights_status"],
            clinical_review_status=case["clinical_review_status"],
            publication_status=case["publication_status"],
            source_refs=tuple(case["source_refs"]), reveal=case["reveal"] or {},
        )
        payload = candidate.public_dict(revealed=True)
        payload.update({"draw_id": draw_id, "learner_id": learner_id.strip()[:160],
                        "reveal_reason": reason, "revealed_at": _now()})
        return payload

    def reveal_count(self, draw_id: str) -> int:
        with self.store.transaction() as conn:
            return int(conn.execute("SELECT COUNT(*) AS n FROM lottery_reveals WHERE draw_id=?",
                                    (draw_id,)).fetchone()["n"])

    def history(self, *, limit: int = 30) -> list[dict[str, Any]]:
        """Non-revealing archive projection; never returns diagnosis or reveal JSON."""
        with self.store.transaction() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM lottery_draws ORDER BY draw_date DESC LIMIT ?",
                (max(1, min(int(limit), 365)),))]
        items = []
        for row in rows:
            case = self.get_case(row["case_id"]) if row.get("case_id") else None
            event = {}
            try:
                event = json.loads(row.get("event_json") or "{}")
            except (TypeError, ValueError):
                event = {}
            items.append({
                "draw_id": row["draw_id"], "draw_date": row["draw_date"],
                "state": row["state"], "pool_size": int(row["pool_size"]),
                "selection_method": row.get("selection_method", "legacy_deterministic"),
                "policy_version": row.get("policy_version", "legacy"),
                "event": event or None,
                "case": ({
                    "case_id": case["case_id"], "presenting_complaint": case.get("presenting_complaint") or "Unknown presentation",
                    "patient_age_value": case.get("patient_age_value"),
                    "patient_age_unit": case.get("patient_age_unit") or "years",
                    "specialty": case.get("specialty") or "Unspecified specialty",
                    "difficulty": case.get("difficulty") or "Unspecified",
                    "label": case.get("label") or "Clinical case",
                } if case else None),
                "reveal_count": self.reveal_count(row["draw_id"]),
            })
        return items

    def summary(self) -> dict[str, Any]:
        report = self.eligibility_report()
        with self.store.transaction() as conn:
            draws = conn.execute("SELECT COUNT(*) AS n FROM lottery_draws").fetchone()["n"]
            reveals = conn.execute("SELECT COUNT(*) AS n FROM lottery_reveals").fetchone()["n"]
        return {
            "workspaces": list(WORKSPACES),
            "eligible_cases": report["eligible_count"],
            "blocked_cases": report["blocked_count"],
            "draws_recorded": int(draws),
            "reveals_recorded": int(reveals),
            "requirements": {
                "eligible_curriculum_or_review_status": sorted(REQUIRED_CLINICAL_REVIEW),
                "publication": sorted(REQUIRED_PUBLICATION),
                "rights": "must not be unknown, restricted or prohibited",
            },
            "answer_leakage": "withheld server-side until an explicit, audited reveal",
        }
