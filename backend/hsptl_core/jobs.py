"""Durable job execution: ownership, leases, heartbeat, backoff, cancel, checkpoints.

The local application starts its worker automatically. Set
HSPTL_DISABLE_BACKGROUND_WORKERS=1 only for tests or deliberate maintenance.
Paused jobs are never claimed; the existing pause/resume API keeps working.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

logger = logging.getLogger("hsptl.jobs")
LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 15
BASE_BACKOFF_SECONDS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class JobRunner:
    def __init__(self, store):
        self.store = store
        self.owner = f"worker-{uuid.uuid4().hex[:8]}"
        self.handlers: dict[str, Callable[..., dict]] = {}
        self._worker_stop = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def register(self, kind: str, handler) -> None:
        self.handlers[kind] = handler

    def claim(self, job_id: str | None = None) -> dict[str, Any] | None:
        now = _iso(_now())
        with self.store.transaction() as conn:
            sql = (
                "SELECT * FROM background_jobs WHERE cancel_requested=0 "
                "AND (status='queued' OR (status='running' AND lease_expires_at<:now)) "
                "AND (next_attempt_at='' OR next_attempt_at<=:now) "
            )
            params = {"now": now}
            if job_id:
                sql += "AND id=:job_id "
                params["job_id"] = job_id
            sql += "ORDER BY created_at LIMIT 1"
            row = conn.execute(sql, params).fetchone()
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            conn.execute(
                "UPDATE background_jobs SET status='running', lease_owner=?, lease_expires_at=?, "
                "heartbeat_at=?, attempts=?, updated_at=? WHERE id=?",
                (self.owner, _iso(_now() + timedelta(seconds=LEASE_SECONDS)), now, attempts,
                 now, row["id"]))
            job = dict(row)
            job["attempts"] = attempts
            job["payload"] = json.loads(job.pop("payload_json") or "{}")
            job["checkpoint"] = json.loads(job.pop("checkpoint_json") or "{}")
            return job

    def heartbeat(self, job_id: str, checkpoint: dict | None = None,
                  done: int | None = None, total: int | None = None) -> bool:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT cancel_requested FROM background_jobs WHERE id=?",
                               (job_id,)).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE background_jobs SET heartbeat_at=?, lease_expires_at=?, updated_at=?, "
                "progress_done=COALESCE(?, progress_done), progress_total=COALESCE(?, progress_total), "
                "checkpoint_json=COALESCE(?, checkpoint_json), "
                "status=CASE WHEN cancel_requested=1 THEN 'cancelled' ELSE status END WHERE id=?",
                (_iso(_now()), _iso(_now() + timedelta(seconds=LEASE_SECONDS)), _iso(_now()),
                 done, total,
                 json.dumps(checkpoint, ensure_ascii=False) if checkpoint is not None else None,
                 job_id))
            return not bool(row["cancel_requested"])

    def complete(self, job_id: str, result: dict) -> None:
        self.store.update_job(job_id, status="completed")
        with self.store.transaction() as conn:
            conn.execute("UPDATE background_jobs SET result_json=?, lease_owner='', updated_at=? "
                         "WHERE id=?", (json.dumps(result, ensure_ascii=False), _iso(_now()), job_id))

    def fail(self, job_id: str, attempts: int, max_attempts: int, error_code: str) -> None:
        if attempts >= max_attempts:
            self.store.update_job(job_id, status="failed", error_code=error_code)
            return
        delay = BASE_BACKOFF_SECONDS * (2 ** (attempts - 1))
        with self.store.transaction() as conn:
            conn.execute(
                "UPDATE background_jobs SET status='queued', error_code=?, lease_owner='', "
                "next_attempt_at=?, updated_at=? WHERE id=?",
                (error_code, _iso(_now() + timedelta(seconds=delay)), _iso(_now()), job_id))

    def request_cancel(self, job_id: str) -> bool:
        with self.store.transaction() as conn:
            return conn.execute("UPDATE background_jobs SET cancel_requested=1, updated_at=? "
                                "WHERE id=?", (_iso(_now()), job_id)).rowcount > 0

    def reap_expired(self) -> int:
        with self.store.transaction() as conn:
            return conn.execute(
                "UPDATE background_jobs SET status='queued', lease_owner='', updated_at=? "
                "WHERE status='running' AND cancel_requested=0 "
                "AND lease_expires_at<>'' AND lease_expires_at<?",
                (_iso(_now()), _iso(_now()))).rowcount

    def run_once(self, job_id: str | None = None) -> bool:
        job = self.claim(job_id)
        if job is None:
            return False
        handler = self.handlers.get(job["kind"])
        if handler is None:
            self.fail(job["id"], job["attempts"], int(job["max_attempts"]), "no_handler_registered")
            return True
        stopped = threading.Event()

        def beat() -> None:
            while not stopped.wait(HEARTBEAT_SECONDS):
                if not self.heartbeat(job["id"]):
                    return

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            def checkpoint(data: dict) -> bool:
                return self.heartbeat(job["id"], checkpoint=data)
            payload = dict(job["payload"])
            payload["_checkpoint"] = job["checkpoint"]
            payload["_job_id"] = job["id"]
            self.complete(job["id"], handler(payload, checkpoint) or {})
        except Exception as exc:  # noqa: BLE001 - the worker must survive handler failure
            logger.exception("Job %s failed", job["id"])
            # A cooperative cancellation must remain cancelled; do not feed it
            # into retry/backoff and accidentally resurrect the job as queued.
            with self.store.transaction() as conn:
                state = conn.execute("SELECT cancel_requested, status FROM background_jobs WHERE id=?",
                                     (job["id"],)).fetchone()
            if state and (bool(state["cancel_requested"]) or state["status"] == "cancelled"):
                self.store.update_job(job["id"], status="cancelled")
            else:
                self.fail(job["id"], job["attempts"], int(job["max_attempts"]), type(exc).__name__)
        finally:
            stopped.set()
        return True


def start_worker_thread(runner: JobRunner) -> threading.Thread | None:
    if os.environ.get("HSPTL_DISABLE_BACKGROUND_WORKERS", "") == "1":
        return None
    if runner._worker_thread is not None and runner._worker_thread.is_alive():
        return runner._worker_thread
    runner._worker_stop.clear()

    def loop() -> None:
        while not runner._worker_stop.is_set():
            try:
                runner.reap_expired()
                if not runner.run_once():
                    runner._worker_stop.wait(1.0)
            except Exception:  # noqa: BLE001
                logger.exception("Worker loop error")
                runner._worker_stop.wait(2.0)

    thread = threading.Thread(target=loop, daemon=True, name="hsptl-jobs")
    runner._worker_thread = thread
    thread.start()
    return thread


def stop_worker_thread(runner: JobRunner, timeout: float = 2.0) -> None:
    runner._worker_stop.set()
    if runner._worker_thread is not None and runner._worker_thread.is_alive():
        runner._worker_thread.join(timeout=max(0.0, timeout))
