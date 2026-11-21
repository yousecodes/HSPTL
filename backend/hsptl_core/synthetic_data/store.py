"""Repository for the synthetic data factory domain.

Thin SQLite access. Pipeline logic lives in ``pipeline.py``; this module only
reads and writes rows so the state machine stays testable without a database
transaction open across stages.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class FactoryStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _connect(self):
        """Yield a configured connection and always close its file handle.

        ``sqlite3.Connection``'s own context manager commits or rolls back,
        but does not close the connection. This wrapper provides both the
        transaction boundary and deterministic cleanup (important on Windows,
        where an open SQLite handle prevents temporary database deletion).
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # -- runs ------------------------------------------------------------- #

    def create_run(self, *, job_id: str, recipe_id: str, recipe_version: str,
                   idempotency_key: str, staging_path: str) -> dict[str, Any]:
        run_id = _new_id("synrun")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO synthetic_dataset_runs(run_id, job_id, recipe_id, recipe_version, "
                "idempotency_key, status, stage, stage_index, staging_path, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, job_id, recipe_id, recipe_version, idempotency_key,
                 "queued", "queued", 0, staging_path, now, now),
            )
        return self.get_run(run_id)  # type: ignore[return-value]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM synthetic_dataset_runs WHERE run_id=?", (run_id,)).fetchone()
        return self._run_row(row)

    def get_run_by_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM synthetic_dataset_runs WHERE job_id=? ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            ).fetchone()
        return self._run_row(row)

    def get_run_by_idempotency(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM synthetic_dataset_runs WHERE idempotency_key=?", (key,)
            ).fetchone()
        return self._run_row(row)

    def _run_row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        record = dict(row)
        record["counts"] = json.loads(record.pop("counts_json") or "{}")
        return record

    def update_run(self, run_id: str, **changes: Any) -> None:
        allowed = {"status", "stage", "stage_index", "attempt", "dataset_id", "error_code",
                   "diagnostic", "counts"}
        fields: list[str] = ["updated_at=?"]
        values: list[Any] = [_now()]
        for key, value in changes.items():
            if key not in allowed:
                raise ValueError(f"Unsupported run field: {key}")
            if key == "counts":
                fields.append("counts_json=?")
                values.append(json.dumps(value, sort_keys=True, ensure_ascii=False))
            else:
                fields.append(f"{key}=?")
                values.append(value)
        values.append(run_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE synthetic_dataset_runs SET {', '.join(fields)} WHERE run_id=?", values)

    def list_runs(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM synthetic_dataset_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (max(1, min(limit, 200)), max(0, offset)),
            ).fetchall()
        return [self._run_row(row) for row in rows]  # type: ignore[misc]

    def count_runs(self, status: str | None = None) -> int:
        with self._connect() as conn:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM synthetic_dataset_runs WHERE status=?", (status,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS n FROM synthetic_dataset_runs").fetchone()
        return int(row["n"] if row else 0)

    def has_active_generation(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM synthetic_dataset_runs WHERE status IN ('queued','running')"
            ).fetchone()
        return bool(row and row["n"])

    # -- datasets --------------------------------------------------------- #

    def register_dataset(self, record: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        dataset_id = record.get("dataset_id") or _new_id("synds")
        values: dict[str, Any] = {
            "dataset_id": dataset_id,
            "run_id": record["run_id"],
            "job_id": record["job_id"],
            "recipe_id": record["recipe_id"],
            "recipe_version": record["recipe_version"],
            "name": record.get("name", dataset_id),
            "status": record.get("status", "accepted"),
            "cohort_status": record.get("cohort_status", "complete"),
            "seed": str(record.get("seed", "")),
            "synthea_version": record.get("synthea_version", ""),
            "fhir_version": record.get("fhir_version", "4.0.1"),
            "manifest_digest": record.get("manifest_digest", ""),
            "content_digest": record.get("content_digest", ""),
            "generated_patients": int(record.get("generated_patients", 0)),
            "matched_patients": int(record.get("matched_patients", 0)),
            "accepted_patients": int(record.get("accepted_patients", 0)),
            "quarantined_patients": int(record.get("quarantined_patients", 0)),
            "imported_patients": int(record.get("imported_patients", 0)),
            "validation_status": record.get("validation_status", "pending"),
            "strict_conformance": 1 if record.get("strict_conformance") else 0,
            "terminology_status": record.get("terminology_status", "pending"),
            "storage_bytes": int(record.get("storage_bytes", 0)),
            "created_at": now,
            "updated_at": now,
        }
        columns = ", ".join(values)
        placeholders = ",".join("?" for _ in values)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO synthetic_datasets({columns}) VALUES({placeholders})",
                tuple(values.values()),
            )
        return self.get_dataset(dataset_id)  # type: ignore[return-value]

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM synthetic_datasets WHERE dataset_id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None

    def list_datasets(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM synthetic_datasets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (max(1, min(limit, 200)), max(0, offset)),
            ).fetchall()
        return [dict(row) for row in rows]

    def dataset_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM synthetic_datasets GROUP BY status"
            ).fetchall()
        counts = {"accepted": 0, "quarantined": 0, "rejected": 0, "total": 0}
        for row in rows:
            counts[row["status"]] = int(row["n"])
            counts["total"] += int(row["n"])
        return counts

    # -- artifacts -------------------------------------------------------- #

    def add_artifact(self, *, dataset_id: str, relative_path: str, kind: str,
                     byte_size: int, sha256: str, immutable: bool = True) -> str:
        artifact_id = _new_id("synart")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO synthetic_dataset_artifacts(artifact_id, dataset_id, relative_path, kind, "
                "byte_size, sha256, immutable, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (artifact_id, dataset_id, relative_path, kind, int(byte_size), sha256,
                 1 if immutable else 0, _now()),
            )
        return artifact_id

    def list_artifacts(self, dataset_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM synthetic_dataset_artifacts WHERE dataset_id=? ORDER BY relative_path",
                (dataset_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- findings --------------------------------------------------------- #

    def add_findings(self, dataset_id: str, findings: list[dict[str, Any]]) -> int:
        now = _now()
        rows = [
            (_new_id("synfind"), dataset_id, finding.get("patient_key", ""),
             finding.get("dimension", ""), finding.get("rule_id", ""),
             str(finding.get("rule_version", "1")), finding.get("severity", "info"),
             finding.get("resource_type", ""), finding.get("message", ""),
             json.dumps(finding.get("detail", {}), sort_keys=True, ensure_ascii=False), now)
            for finding in findings
        ]
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO synthetic_quality_findings(finding_id, dataset_id, patient_key, dimension, "
                "rule_id, rule_version, severity, resource_type, message, detail_json, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows,
            )
        return len(rows)

    def list_findings(self, dataset_id: str, *, dimension: str = "", severity: str = "",
                      limit: int = 500) -> list[dict[str, Any]]:
        sql = "SELECT * FROM synthetic_quality_findings WHERE dataset_id=?"
        params: list[Any] = [dataset_id]
        if dimension:
            sql += " AND dimension=?"
            params.append(dimension)
        if severity:
            sql += " AND severity=?"
            params.append(severity)
        sql += " ORDER BY severity, dimension LIMIT ?"
        params.append(max(1, min(limit, 2000)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["detail"] = json.loads(item.pop("detail_json") or "{}")
            items.append(item)
        return items

    # -- quarantine ------------------------------------------------------- #

    def add_quarantine_item(self, *, dataset_id: str, job_id: str, patient_key: str,
                            bundle_path: str, reason: str, rule_ids: list[str],
                            severity: str = "quarantine") -> str:
        item_id = _new_id("synq")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO synthetic_quarantine_items(item_id, dataset_id, job_id, patient_key, "
                "bundle_path, reason, rule_ids_json, severity, status, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, dataset_id, job_id, patient_key, bundle_path, reason,
                 json.dumps(sorted(set(rule_ids)), ensure_ascii=False), severity, "open", now, now),
            )
        return item_id

    def list_quarantine(self, *, dataset_id: str = "", status: str = "", severity: str = "",
                        rule_id: str = "", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        sql = "SELECT * FROM synthetic_quarantine_items WHERE 1=1"
        params: list[Any] = []
        if dataset_id:
            sql += " AND dataset_id=?"
            params.append(dataset_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        if severity:
            sql += " AND severity=?"
            params.append(severity)
        if rule_id:
            sql += " AND rule_ids_json LIKE ?"
            params.append(f'%"{rule_id}"%')
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 200)), max(0, offset)])
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["rule_ids"] = json.loads(item.pop("rule_ids_json") or "[]")
            items.append(item)
        return items

    def get_quarantine_item(self, item_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM synthetic_quarantine_items WHERE item_id=?", (item_id,)
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["rule_ids"] = json.loads(item.pop("rule_ids_json") or "[]")
        return item

    def review_quarantine_item(self, item_id: str, *, reviewer: str, decision: str,
                               rationale: str) -> bool:
        now = _now()
        with self._connect() as conn:
            changed = conn.execute(
                "UPDATE synthetic_quarantine_items SET status=?, reviewer=?, rationale=?, "
                "reviewed_at=?, updated_at=? WHERE item_id=?",
                (decision, reviewer[:160], rationale[:2000], now, now, item_id),
            ).rowcount
        return bool(changed)

    # -- reviews ---------------------------------------------------------- #

    def record_review(self, *, item_kind: str, item_id: str, dataset_id: str,
                      reviewer: str, decision: str, rationale: str) -> str:
        action_id = _new_id("synrev")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO synthetic_review_actions(action_id, item_kind, item_id, dataset_id, "
                "reviewer, decision, rationale, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (action_id, item_kind, item_id, dataset_id, reviewer[:160], decision,
                 rationale[:2000], _now()),
            )
        return action_id

    def list_reviews(self, *, item_id: str = "", dataset_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM synthetic_review_actions WHERE 1=1"
        params: list[Any] = []
        if item_id:
            sql += " AND item_id=?"
            params.append(item_id)
        if dataset_id:
            sql += " AND dataset_id=?"
            params.append(dataset_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    # -- schedules -------------------------------------------------------- #

    def create_schedule(self, record: dict[str, Any]) -> dict[str, Any]:
        schedule_id = record.get("schedule_id") or _new_id("synsch")
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO synthetic_schedules(schedule_id, name, recipe_id, recipe_version, "
                "population, accepted_target, frequency, enabled, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (schedule_id, record["name"], record["recipe_id"], record["recipe_version"],
                 int(record.get("population", 5)), int(record.get("accepted_target", 0)),
                 record.get("frequency", "weekly"), 1 if record.get("enabled") else 0, now, now),
            )
        return self.get_schedule(schedule_id)  # type: ignore[return-value]

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM synthetic_schedules WHERE schedule_id=?", (schedule_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_schedules(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM synthetic_schedules ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def update_schedule(self, schedule_id: str, **changes: Any) -> dict[str, Any] | None:
        allowed = {"name", "recipe_id", "recipe_version", "population", "accepted_target",
                   "frequency", "enabled", "last_run_at", "next_run_at", "last_status"}
        fields: list[str] = ["updated_at=?"]
        values: list[Any] = [_now()]
        for key, value in changes.items():
            if key not in allowed:
                raise ValueError(f"Unsupported schedule field: {key}")
            fields.append(f"{key}=?")
            values.append(1 if key == "enabled" and value else (0 if key == "enabled" else value))
        values.append(schedule_id)
        with self._connect() as conn:
            conn.execute(f"UPDATE synthetic_schedules SET {', '.join(fields)} WHERE schedule_id=?", values)
        return self.get_schedule(schedule_id)

    def due_schedules(self, now_iso: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM synthetic_schedules WHERE enabled=1 AND next_run_at<>'' AND next_run_at<=?",
                (now_iso,),
            ).fetchall()
        return [dict(row) for row in rows]
