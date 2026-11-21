"""Tool execution facade: job submission, status, cancellation and dispatch."""
from __future__ import annotations
from typing import Any

class ToolExecutionService:
    ALLOWED_KINDS = {"mednotegen_generate", "specialty_harvest"}
    def __init__(self, store, runner):
        self.store = store
        self.runner = runner
    def enqueue(self, kind: str, payload: dict[str, Any]) -> str:
        if kind not in self.ALLOWED_KINDS:
            raise ValueError("Unsupported data-tool job")
        return self.store.create_job(kind, payload)
    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        return [job for job in self.store.jobs(limit) if job.get("kind") in self.ALLOWED_KINDS]
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return next((job for job in self.store.jobs(200) if job.get("id") == job_id and job.get("kind") in self.ALLOWED_KINDS), None)
    def run_once(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if not job:
            raise KeyError("Job not found")
        if job.get("status") not in {"queued", "failed"}:
            raise ValueError("Only a queued or failed job can be run")
        if job.get("status") == "failed":
            self.store.update_job(job_id, status="queued", error_code="")
        return self.runner.run_once(job_id)
    def cancel(self, job_id: str) -> bool:
        if not self.get_job(job_id):
            raise KeyError("Job not found")
        return self.runner.request_cancel(job_id)
