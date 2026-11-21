"""Deterministic, provenance-aware FHIR case ingestion and retrieval.

The importer never edits source files or invents clinical facts. It supports
FHIR JSON Bundles, standalone resources and NDJSON. JSON files are size-bounded;
resource persistence is committed in bounded, idempotent batches so interrupted
imports can be safely rerun.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .case_events import evaluate_case_events
from .case_quality import assess_fhir_case_quality
from .reasoning_feedback import assess_reasoning_completeness, build_feedback

MAX_JSON_FILE_BYTES = 32 * 1024 * 1024
MAX_NDJSON_LINE_BYTES = 4 * 1024 * 1024
SUPPORTED_RESOURCES = {
    "Patient", "Encounter", "Condition", "Observation", "MedicationRequest",
    "Procedure", "DiagnosticReport", "AllergyIntolerance", "Immunization",
    "CarePlan", "CareTeam", "Device", "ImagingStudy", "Medication",
    "MedicationAdministration", "DocumentReference", "SupplyDelivery",
}
CLINICAL_RESOURCES = SUPPORTED_RESOURCES - {"Patient", "CareTeam", "Device", "Medication", "DocumentReference", "SupplyDelivery"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()[:limit]
    return ""


def _reference_id(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("reference")
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().split("|")[0].split("#")[0].rstrip("/")
    if "/_history/" in raw:
        raw = raw.split("/_history/", 1)[0]
    if raw.startswith("urn:uuid:"):
        return raw[len("urn:uuid:"):]
    return raw.rsplit("/", 1)[-1]


def _coding_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if value.get("text"):
        return _text(value.get("text"), 300)
    codings = value.get("coding") or []
    if isinstance(codings, list):
        for coding in codings:
            if isinstance(coding, dict) and coding.get("display"):
                return _text(coding.get("display"), 300)
    return ""


def _resource_summary(resource: dict[str, Any]) -> dict[str, Any]:
    kind = resource.get("resourceType", "")
    code = _coding_text(resource.get("code"))
    if kind == "Encounter":
        code = _coding_text(resource.get("type")) or _coding_text(resource.get("serviceType"))
    elif kind == "MedicationRequest":
        code = _coding_text(resource.get("medicationCodeableConcept")) or _text((resource.get("medicationReference") or {}).get("display"), 300)
    elif kind == "DiagnosticReport":
        code = _coding_text(resource.get("code"))
    elif kind == "Immunization":
        code = _coding_text(resource.get("vaccineCode"))
    elif kind == "CarePlan":
        code = _text(resource.get("title"), 300) or _text(resource.get("description"), 300)
    value: Any = None
    unit = ""
    if "valueQuantity" in resource and isinstance(resource["valueQuantity"], dict):
        quantity = resource["valueQuantity"]
        value = quantity.get("value")
        unit = _text(quantity.get("unit"), 80)
    elif "valueString" in resource:
        value = _text(resource.get("valueString"), 300)
    elif "valueCodeableConcept" in resource:
        value = _coding_text(resource.get("valueCodeableConcept"))
    date = (
        resource.get("effectiveDateTime") or resource.get("issued") or
        resource.get("authoredOn") or resource.get("performedDateTime") or
        resource.get("occurrenceDateTime") or resource.get("recordedDate") or
        (resource.get("period") or {}).get("start") or
        (resource.get("meta") or {}).get("lastUpdated") or ""
    )
    status = _text(resource.get("status"), 80)
    conclusion = _text(resource.get("conclusion"), 1000)
    return {"code": code, "value": value, "unit": unit, "date": _text(date, 80),
            "status": status, "conclusion": conclusion}


def _patient_ref(resource: dict[str, Any]) -> str | None:
    return _reference_id(resource.get("subject") or resource.get("patient"))


def _encounter_ref(resource: dict[str, Any]) -> str | None:
    return _reference_id(resource.get("encounter"))


def _iter_file_resources(path: Path) -> Iterator[tuple[dict[str, Any], str | None]]:
    """Yield (resource, fullUrl) without retaining an entire cohort in memory."""
    if path.suffix.casefold() in {".ndjson", ".jsonl"}:
        with path.open("rb") as stream:
            for line_no, raw in enumerate(stream, 1):
                if len(raw) > MAX_NDJSON_LINE_BYTES:
                    raise ValueError(f"NDJSON line {line_no} exceeds the 4 MB safety limit")
                if not raw.strip():
                    continue
                try:
                    item = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError(f"Malformed NDJSON at line {line_no}") from exc
                if isinstance(item, dict) and item.get("resourceType") == "Bundle":
                    for entry in item.get("entry", []):
                        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                            yield entry["resource"], _text(entry.get("fullUrl"), 500) or None
                elif isinstance(item, dict):
                    yield item, None
        return
    size = path.stat().st_size
    if size > MAX_JSON_FILE_BYTES:
        raise ValueError(f"JSON file exceeds the 32 MB per-file safety limit: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not parse {path.name}: {exc}") from exc
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        for entry in payload.get("entry", []):
            if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                yield entry["resource"], _text(entry.get("fullUrl"), 500) or None
    elif isinstance(payload, dict):
        yield payload, None


class CaseRepository:
    """SQLite repository for normalized case identity and source-linked facts."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()
        from .migrations import apply as _apply_phase_migrations
        with self.transaction() as conn:
            _apply_phase_migrations(conn)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
        return conn

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self.transaction() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS clinical_patients (
                    patient_key TEXT PRIMARY KEY, source_key TEXT NOT NULL, source_patient_id TEXT NOT NULL,
                    gender TEXT NOT NULL DEFAULT '', birth_date TEXT NOT NULL DEFAULT '',
                    deceased TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL, provenance TEXT NOT NULL DEFAULT 'Documented',
                    updated_at TEXT NOT NULL, UNIQUE(source_key, source_patient_id)
                );
                CREATE TABLE IF NOT EXISTS clinical_encounters (
                    encounter_key TEXT PRIMARY KEY, patient_key TEXT NOT NULL REFERENCES clinical_patients(patient_key) ON DELETE CASCADE,
                    source_encounter_id TEXT NOT NULL, start_at TEXT NOT NULL DEFAULT '', end_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '', encounter_type TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL, source_file TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(patient_key, source_encounter_id)
                );
                CREATE INDEX IF NOT EXISTS idx_clinical_encounters_patient ON clinical_encounters(patient_key, start_at);
                CREATE TABLE IF NOT EXISTS clinical_facts (
                    fact_key TEXT PRIMARY KEY, patient_key TEXT NOT NULL REFERENCES clinical_patients(patient_key) ON DELETE CASCADE,
                    encounter_key TEXT REFERENCES clinical_encounters(encounter_key) ON DELETE SET NULL,
                    resource_type TEXT NOT NULL, source_resource_id TEXT NOT NULL,
                    effective_at TEXT NOT NULL DEFAULT '', code_text TEXT NOT NULL DEFAULT '',
                    value_text TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT '',
                    conclusion TEXT NOT NULL DEFAULT '', raw_json TEXT NOT NULL,
                    provenance TEXT NOT NULL DEFAULT 'Documented', source_file TEXT NOT NULL,
                    updated_at TEXT NOT NULL, UNIQUE(patient_key, resource_type, source_resource_id)
                );
                CREATE INDEX IF NOT EXISTS idx_clinical_facts_patient_date ON clinical_facts(patient_key, effective_at);
                CREATE INDEX IF NOT EXISTS idx_clinical_facts_encounter ON clinical_facts(encounter_key, resource_type);
                CREATE TABLE IF NOT EXISTS clinical_import_files (
                    source_key TEXT NOT NULL, relative_path TEXT NOT NULL, sha256 TEXT NOT NULL,
                    resources_seen INTEGER NOT NULL DEFAULT 0, imported_at TEXT NOT NULL,
                    PRIMARY KEY(source_key, relative_path)
                );
                CREATE TABLE IF NOT EXISTS clinical_import_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, source_key TEXT NOT NULL,
                    relative_path TEXT NOT NULL, error_code TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clinical_learning_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    patient_key TEXT NOT NULL REFERENCES clinical_patients(patient_key) ON DELETE CASCADE,
                    encounter_key TEXT NOT NULL REFERENCES clinical_encounters(encounter_key) ON DELETE CASCADE,
                    case_code TEXT NOT NULL,
                    problem_representation TEXT NOT NULL DEFAULT '',
                    differential_json TEXT NOT NULL DEFAULT '[]',
                    evidence_for TEXT NOT NULL DEFAULT '',
                    evidence_against TEXT NOT NULL DEFAULT '',
                    investigation_plan TEXT NOT NULL DEFAULT '',
                    confidence INTEGER NOT NULL CHECK(confidence BETWEEN 1 AND 5),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_attempts_encounter
                    ON clinical_learning_attempts(encounter_key, updated_at DESC);
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
                );
            """)
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(2, ?)", (_now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(3, ?)", (_now(),))
            # Additive migration: existing learner drafts remain intact.
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(clinical_learning_attempts)")}
            additions = {
                "working_diagnosis": "TEXT NOT NULL DEFAULT ''",
                "management_plan": "TEXT NOT NULL DEFAULT ''",
                "safety_net": "TEXT NOT NULL DEFAULT ''",
                "communication_plan": "TEXT NOT NULL DEFAULT ''",
                "stage_completed": "INTEGER NOT NULL DEFAULT 1",
                "history_plan_json": "TEXT NOT NULL DEFAULT '[]'",
                "examination_plan_json": "TEXT NOT NULL DEFAULT '[]'",
                "investigation_selection_json": "TEXT NOT NULL DEFAULT '[]'",
                "specialty_pathway": "TEXT NOT NULL DEFAULT 'Emergency'",
            }
            for column, definition in additions.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE clinical_learning_attempts ADD COLUMN {column} {definition}")
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(4, ?)", (_now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(5, ?)", (_now(),))

    @staticmethod
    def _patient_key(source_key: str, patient_id: str) -> str:
        return hashlib.sha256(f"{source_key}\0{patient_id}".encode()).hexdigest()

    def _save_batch(self, source_key: str, source_label: str, items: list[tuple[dict[str, Any], str | None, str]]) -> dict[str, int]:
        counts = {"patients": 0, "encounters": 0, "facts": 0, "unlinked": 0}
        aliases: dict[str, str] = {}
        for resource, full_url, _ in items:
            rid = _text(resource.get("id"), 200)
            if rid and full_url:
                aliases[full_url] = rid
                aliases[_reference_id(full_url) or full_url] = rid
        with self.transaction() as conn:
            now = _now()
            for resource, full_url, relpath in items:
                kind = resource.get("resourceType")
                rid = _text(resource.get("id"), 200)
                if kind not in SUPPORTED_RESOURCES or not rid:
                    continue
                if kind == "Patient":
                    pkey = self._patient_key(source_key, rid)
                    names = resource.get("name") or []
                    name = ""
                    if isinstance(names, list) and names and isinstance(names[0], dict):
                        first = names[0]
                        given = first.get("given") or []
                        name = " ".join([*(str(x) for x in given if x), _text(first.get("family"), 100)]).strip()
                    conn.execute("""INSERT INTO clinical_patients
                        (patient_key,source_key,source_patient_id,gender,birth_date,deceased,name,raw_json,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_key,source_patient_id) DO UPDATE SET
                        gender=excluded.gender,birth_date=excluded.birth_date,deceased=excluded.deceased,
                        name=excluded.name,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
                        (pkey, source_key, rid, _text(resource.get("gender"), 40), _text(resource.get("birthDate"), 40),
                         _text(resource.get("deceasedDateTime") or ("true" if resource.get("deceasedBoolean") else ""), 80),
                         name, json.dumps(resource, ensure_ascii=False), now))
                    counts["patients"] += 1
            # Patient aliases from fullUrl and literal Patient/<id> references.
            for alias, pid in list(aliases.items()):
                aliases[alias.removeprefix("urn:uuid:")] = pid
            for resource, full_url, relpath in items:
                kind = resource.get("resourceType")
                rid = _text(resource.get("id"), 200)
                if kind != "Encounter" or not rid:
                    continue
                ref = _patient_ref(resource)
                if ref:
                    ref = aliases.get(ref, ref)
                if not ref:
                    counts["unlinked"] += 1
                    continue
                pkey = self._patient_key(source_key, ref)
                exists = conn.execute("SELECT 1 FROM clinical_patients WHERE patient_key=?", (pkey,)).fetchone()
                if not exists:
                    counts["unlinked"] += 1
                    continue
                if kind == "Encounter":
                    period = resource.get("period") or {}
                    code = _coding_text(resource.get("type")) or _coding_text(resource.get("serviceType"))
                    ekey = hashlib.sha256(f"{pkey}\0{rid}".encode()).hexdigest()
                    conn.execute("""INSERT INTO clinical_encounters
                        (encounter_key,patient_key,source_encounter_id,start_at,end_at,status,encounter_type,raw_json,source_file,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(patient_key,source_encounter_id) DO UPDATE SET
                        start_at=excluded.start_at,end_at=excluded.end_at,status=excluded.status,
                        encounter_type=excluded.encounter_type,raw_json=excluded.raw_json,source_file=excluded.source_file,updated_at=excluded.updated_at""",
                        (ekey,pkey,rid,_text(period.get("start"),80),_text(period.get("end"),80),
                         _text(resource.get("status"),80),code,json.dumps(resource,ensure_ascii=False),relpath,now))
                    counts["encounters"] += 1
            # Resolve encounter links after all encounter resources in this batch are inserted.
            for resource, full_url, relpath in items:
                kind = resource.get("resourceType")
                rid = _text(resource.get("id"), 200)
                if kind not in CLINICAL_RESOURCES or kind == "Encounter" or not rid:
                    continue
                ref = _patient_ref(resource)
                if ref:
                    ref = aliases.get(ref, ref)
                if not ref:
                    counts["unlinked"] += 1
                    continue
                pkey = self._patient_key(source_key, ref)
                if not conn.execute("SELECT 1 FROM clinical_patients WHERE patient_key=?", (pkey,)).fetchone():
                    counts["unlinked"] += 1
                    continue
                enc_ref = _encounter_ref(resource)
                if enc_ref:
                    enc_ref = aliases.get(enc_ref, enc_ref)
                    enc_row = conn.execute("SELECT encounter_key FROM clinical_encounters WHERE patient_key=? AND source_encounter_id=?", (pkey, enc_ref)).fetchone()
                else:
                    enc_row = None
                summary = _resource_summary(resource)
                fkey = hashlib.sha256(f"{pkey}\0{kind}\0{rid}".encode()).hexdigest()
                value = "" if summary["value"] is None else str(summary["value"])
                conn.execute("""INSERT INTO clinical_facts
                    (fact_key,patient_key,encounter_key,resource_type,source_resource_id,effective_at,code_text,value_text,unit,status,conclusion,raw_json,source_file,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(patient_key,resource_type,source_resource_id) DO UPDATE SET
                    encounter_key=excluded.encounter_key,effective_at=excluded.effective_at,code_text=excluded.code_text,
                    value_text=excluded.value_text,unit=excluded.unit,status=excluded.status,conclusion=excluded.conclusion,
                    raw_json=excluded.raw_json,source_file=excluded.source_file,updated_at=excluded.updated_at""",
                    (fkey,pkey,enc_row["encounter_key"] if enc_row else None,kind,rid,summary["date"],summary["code"],value,
                     summary["unit"],summary["status"],summary["conclusion"],json.dumps(resource,ensure_ascii=False),relpath,now))
                counts["facts"] += 1
        return counts

    def save_learning_attempt(self, *, patient_key: str, encounter_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        now = _now()
        with self.transaction() as conn:
            valid = conn.execute("SELECT 1 FROM clinical_encounters WHERE encounter_key=? AND patient_key=?", (encounter_key, patient_key)).fetchone()
            if not valid:
                raise ValueError("The selected encounter does not belong to this patient")
            conn.execute("""INSERT INTO clinical_learning_attempts
                (attempt_id,patient_key,encounter_key,case_code,problem_representation,differential_json,
                 evidence_for,evidence_against,investigation_plan,confidence,working_diagnosis,
                 management_plan,safety_net,communication_plan,stage_completed,history_plan_json,
                 examination_plan_json,investigation_selection_json,specialty_pathway,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                attempt_id, patient_key, encounter_key, payload["case_code"],
                payload.get("problem_representation", ""), json.dumps(payload.get("differentials", []), ensure_ascii=False),
                payload.get("evidence_for", ""), payload.get("evidence_against", ""),
                payload.get("investigation_plan", ""), int(payload["confidence"]),
                payload.get("working_diagnosis", ""), payload.get("management_plan", ""),
                payload.get("safety_net", ""), payload.get("communication_plan", ""),
                int(payload.get("stage_completed", 1)),
                json.dumps(payload.get("history_plan", []), ensure_ascii=False),
                json.dumps(payload.get("examination_plan", []), ensure_ascii=False),
                json.dumps(payload.get("investigation_selection", []), ensure_ascii=False),
                str(payload.get("specialty_pathway", "Emergency")), now, now))
            conn.execute(
                "UPDATE clinical_learning_attempts SET cited_fact_keys_json=?, prioritisation_rationale=? "
                "WHERE attempt_id=?",
                (json.dumps(payload.get("cited_fact_keys", []), ensure_ascii=False),
                 str(payload.get("prioritisation_rationale", ""))[:2000], attempt_id),
            )
            facts = [dict(r) for r in conn.execute(
                "SELECT fact_key, resource_type, code_text, effective_at FROM clinical_facts "
                "WHERE encounter_key=?", (encounter_key,)).fetchall()]
        feedback = build_feedback(payload, available_facts=facts)
        return {
            "attempt_id": attempt_id,
            "saved": True,
            "created_at": now,
            "feedback": feedback,
            "case_events": evaluate_case_events(payload),
        }

    def list_learning_attempts(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent learner reasoning records without patient identifiers."""
        limit = max(1, min(int(limit), 250))
        with self.transaction() as conn:
            rows = conn.execute(
                """SELECT attempt_id, case_code, problem_representation, working_diagnosis,
                          specialty_pathway, confidence, stage_completed, created_at, updated_at
                   FROM clinical_learning_attempts
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_learning_attempt(self, attempt_id: str) -> dict[str, Any] | None:
        """Return a learner-authored attempt without joining identifiable patient data."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM clinical_learning_attempts WHERE attempt_id=?", (attempt_id,)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        for source, target in (
            ("differential_json", "differentials"),
            ("history_plan_json", "history_plan"),
            ("examination_plan_json", "examination_plan"),
            ("investigation_selection_json", "investigation_selection"),
        ):
            try:
                item[target] = json.loads(item.get(source) or "[]")
            except (TypeError, ValueError):
                item[target] = []
        return item

    def import_directory(self, directory: Path, *, batch_size: int = 250) -> dict[str, Any]:
        directory = Path(directory).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError("FHIR source path must be an existing directory")
        batch_size = max(25, min(int(batch_size), 1000))
        source_key = hashlib.sha256(str(directory).casefold().encode()).hexdigest()[:24]
        files = sorted([*directory.rglob("*.json"), *directory.rglob("*.ndjson"), *directory.rglob("*.jsonl")])
        if not files:
            raise ValueError("No .json, .ndjson or .jsonl FHIR files were found")
        totals = {"patients": 0, "encounters": 0, "facts": 0, "unlinked": 0, "files": 0, "skipped_unchanged": 0, "errors": 0}
        for path in files:
            relpath = path.relative_to(directory).as_posix()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            sha = digest.hexdigest()
            with self.transaction() as conn:
                previous = conn.execute("SELECT sha256 FROM clinical_import_files WHERE source_key=? AND relative_path=?", (source_key, relpath)).fetchone()
            if previous and previous["sha256"] == sha:
                totals["skipped_unchanged"] += 1
                continue
            batch: list[tuple[dict[str, Any], str | None, str]] = []
            stored_source_file = f"{source_key}/{relpath}"
            file_counts = {"patients": 0, "encounters": 0, "facts": 0, "unlinked": 0}
            seen_encounters: set[str] = set()
            seen_facts: set[tuple[str, str]] = set()
            try:
                for resource, full_url in _iter_file_resources(path):
                    if resource.get("resourceType") not in SUPPORTED_RESOURCES:
                        continue
                    batch.append((resource, full_url, stored_source_file))
                    kind = resource.get("resourceType")
                    rid = _text(resource.get("id"), 200)
                    if kind == "Encounter" and rid and _patient_ref(resource):
                        seen_encounters.add(rid)
                    elif kind in CLINICAL_RESOURCES and rid and kind != "Encounter" and _patient_ref(resource):
                        seen_facts.add((str(kind), rid))
                    if len(batch) >= batch_size:
                        counts = self._save_batch(source_key, directory.name, batch)
                        for key, value in counts.items():
                            file_counts[key] += value
                        batch.clear()
                if batch:
                    counts = self._save_batch(source_key, directory.name, batch)
                    for key, value in counts.items():
                        file_counts[key] += value
                # Resolve explicit encounter references after all batches. This also
                # handles a resource appearing before its Encounter in a later batch.
                with self.transaction() as conn:
                    pending = conn.execute("SELECT fact_key,patient_key,raw_json FROM clinical_facts WHERE source_file=? AND encounter_key IS NULL", (stored_source_file,)).fetchall()
                    for fact in pending:
                        try:
                            resource = json.loads(fact["raw_json"])
                        except (TypeError, json.JSONDecodeError):
                            continue
                        encounter_id = _encounter_ref(resource)
                        if encounter_id:
                            encounter = conn.execute("SELECT encounter_key FROM clinical_encounters WHERE patient_key=? AND source_encounter_id=?", (fact["patient_key"], encounter_id)).fetchone()
                            if encounter:
                                conn.execute("UPDATE clinical_facts SET encounter_key=? WHERE fact_key=?", (encounter["encounter_key"], fact["fact_key"]))
                # Prune records removed from a successfully re-imported source file.
                # Pruning happens only after every batch has committed, so interruption
                # leaves the previous records recoverable and a rerun remains safe.
                with self.transaction() as conn:
                    old_encounters = conn.execute("SELECT encounter_key,source_encounter_id FROM clinical_encounters WHERE source_file=?", (stored_source_file,)).fetchall()
                    for old in old_encounters:
                        if old["source_encounter_id"] not in seen_encounters:
                            conn.execute("DELETE FROM clinical_encounters WHERE encounter_key=?", (old["encounter_key"],))
                    old_facts = conn.execute("SELECT fact_key,resource_type,source_resource_id FROM clinical_facts WHERE source_file=?", (stored_source_file,)).fetchall()
                    for old in old_facts:
                        if (old["resource_type"], old["source_resource_id"]) not in seen_facts:
                            conn.execute("DELETE FROM clinical_facts WHERE fact_key=?", (old["fact_key"],))
                    conn.execute("""INSERT INTO clinical_import_files(source_key,relative_path,sha256,resources_seen,imported_at)
                        VALUES(?,?,?,?,?) ON CONFLICT(source_key,relative_path) DO UPDATE SET sha256=excluded.sha256,
                        resources_seen=excluded.resources_seen,imported_at=excluded.imported_at""",
                        (source_key, relpath, sha, sum(file_counts.values()), _now()))
                for key, value in file_counts.items():
                    totals[key] += value
                totals["files"] += 1
            except (OSError, ValueError, sqlite3.Error) as exc:
                totals["errors"] += 1
                with self.transaction() as conn:
                    conn.execute("INSERT INTO clinical_import_errors(source_key,relative_path,error_code,created_at) VALUES(?,?,?,?)",
                                 (source_key, relpath, type(exc).__name__, _now()))
                # Keep prior committed batches. Re-running the import is safe due to upserts.
        totals["source_key"] = source_key
        totals["status"] = "completed_with_errors" if totals["errors"] else "completed"
        return totals

    def list_patients(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200)); offset = max(0, int(offset))
        with self.transaction() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM clinical_patients").fetchone()["n"]
            rows = conn.execute("""SELECT p.*, (SELECT COUNT(*) FROM clinical_encounters e WHERE e.patient_key=p.patient_key) encounter_count,
                (SELECT COUNT(*) FROM clinical_facts f WHERE f.patient_key=p.patient_key) fact_count
                FROM clinical_patients p ORDER BY p.birth_date DESC,p.source_patient_id LIMIT ? OFFSET ?""", (limit, offset)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item.pop("raw_json", None)
            items.append(item)
        return {"total": int(total), "limit": limit, "offset": offset, "items": items}

    def patient_case(self, patient_key: str, encounter_key: str | None = None) -> dict[str, Any] | None:
        with self.transaction() as conn:
            patient = conn.execute("SELECT * FROM clinical_patients WHERE patient_key=?", (patient_key,)).fetchone()
            if not patient:
                return None
            encounters = conn.execute("SELECT * FROM clinical_encounters WHERE patient_key=? ORDER BY start_at DESC", (patient_key,)).fetchall()
            if encounter_key:
                selected = conn.execute("SELECT * FROM clinical_encounters WHERE patient_key=? AND encounter_key=?", (patient_key, encounter_key)).fetchone()
                if not selected:
                    return None
                facts = conn.execute("SELECT * FROM clinical_facts WHERE patient_key=? AND encounter_key=? ORDER BY effective_at,resource_type", (patient_key, encounter_key)).fetchall()
                scope = "encounter_linked_only"
            else:
                selected = None
                facts = conn.execute("SELECT * FROM clinical_facts WHERE patient_key=? ORDER BY effective_at,resource_type", (patient_key,)).fetchall()
                scope = "patient_timeline_including_unlinked_encounter_facts"
        def fact_dict(row: sqlite3.Row) -> dict[str, Any]:
            item = dict(row)
            item.pop("raw_json", None)
            return item
        encounter_items = []
        for row in encounters:
            item = dict(row)
            item.pop("raw_json", None)
            encounter_items.append(item)
        selected_item = dict(selected) if selected else None
        if selected_item:
            selected_item.pop("raw_json", None)
        fact_items = [fact_dict(row) for row in facts]
        quality = assess_fhir_case_quality(encounters=encounter_items, facts=fact_items,
                                           unlinked_facts=sum(1 for row in facts if row["encounter_key"] is None),
                                           selected_encounter=selected_item)
        return {
            "patient": {"patient_key": patient["patient_key"], "source": patient["source_key"],
                        "source_patient_id": patient["source_patient_id"], "gender": patient["gender"],
                        "birth_date": patient["birth_date"], "deceased": patient["deceased"],
                        "name": patient["name"], "provenance": "Documented"},
            "selected_encounter": selected_item,
            "encounters": encounter_items,
            "facts": fact_items,
            "unlinked_facts": sum(1 for row in facts if row["encounter_key"] is None),
            "quality": quality,
            "scope": scope,
            "limitations": ["Only source-documented fields are shown.",
                            "Missing history, examination, vital signs or investigations are not treated as negative findings.",
                            "Facts without an explicit encounter reference are not assigned to an encounter."],
        }
