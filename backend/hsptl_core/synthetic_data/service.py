"""Service facade for the synthetic data factory.

Wires the repository, recipe registry, pipeline and the canonical event kernel
together. The router talks to this object; the worker handler talks to this
object; tests talk to this object.
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import paths
from .cohort import pseudonymous_key
from .pipeline import (
    STAGE_ORDER,
    STAGE_VERSION,
    PipelineContext,
    StageFailure,
    SyntheticDataPipeline,
    idempotency_key,
)
from .recipes import RecipeRegistry
from .runtime import (
    FactorySettings,
    GenerationSpec,
    GeneratorAdapter,
    detect_java,
    free_disk_mb,
    load_settings,
    preflight,
    save_settings,
)
from .schema import apply as apply_schema
from .store import FactoryStore
from .validation import RULE_PACK_ID, RULE_PACK_VERSION

JOB_KIND = "synthetic_generation"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SyntheticDataFactory:
    def __init__(self, db_path: Path, *, storage_root: Path | None = None,
                 event_kernel=None, adapter: GeneratorAdapter | None = None,
                 job_store=None,
                 java_detector: Callable[[str], tuple[bool, str]] | None = None):
        self.db_path = Path(db_path)
        self.storage_root = paths.ensure_layout(Path(storage_root) if storage_root
                                                else self.db_path.parent)
        self.store = FactoryStore(self.db_path)
        with self._connect() as conn:
            apply_schema(conn)
        self.recipes = RecipeRegistry(self._connect)
        self.recipes.seed_builtins()
        self.kernel = event_kernel
        self.adapter = adapter
        self.job_store = job_store
        self.java_detector = java_detector
        self._cancel_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _connect(self):
        return self.store._connect()

    # -- events ----------------------------------------------------------- #

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.kernel is None:
            return
        self.kernel.append(event_type, payload)

    # -- settings --------------------------------------------------------- #

    def settings(self) -> FactorySettings:
        return load_settings(self._connect)

    def update_settings(self, changes: dict[str, Any]) -> FactorySettings:
        current = self.settings()
        data = current.to_dict()
        for key, value in changes.items():
            if key in data:
                data[key] = value
        updated = FactorySettings.from_dict(data)
        save_settings(self._connect, updated)
        return updated

    def status(self) -> dict[str, Any]:
        settings = self.settings()
        java_ok, java_detail = detect_java(settings.java_path)
        jar = Path(settings.synthea_jar).expanduser() if settings.synthea_jar else None
        validator = Path(settings.validator_jar).expanduser() if settings.validator_jar else None
        worker_enabled = os.environ.get("HSPTL_DISABLE_BACKGROUND_WORKERS", "") != "1"
        return {
            "generator": {
                "configured": bool(jar and jar.is_file()),
                "version": settings.synthea_version,
                "path_set": bool(settings.synthea_jar),
                "checksum_pinned": bool(settings.synthea_sha256),
            },
            "java": {"available": java_ok, "detail": java_detail},
            "validator": {
                "configured": bool(validator and validator.is_file()),
                "version": settings.validator_version,
                "strict_available": bool(validator and validator.is_file() and settings.validator_sha256),
            },
            "worker": {
                "enabled": worker_enabled,
                "note": ("The local worker and synthetic scheduler start automatically with HSPTL."
                         if worker_enabled else
                         "Background workers are explicitly disabled by HSPTL_DISABLE_BACKGROUND_WORKERS=1."),
            },
            "storage": {
                "root": str(self.storage_root),
                "free_mb": free_disk_mb(self.storage_root),
                "min_free_mb": settings.min_free_disk_mb,
            },
            "limits": {"max_heap_mb": settings.max_heap_mb, "concurrency": 1},
            "datasets": self.store.dataset_counts(),
            "runs": {
                "queued": self.store.count_runs("queued"),
                "running": self.store.count_runs("running"),
                "completed": self.store.count_runs("completed"),
                "failed": self.store.count_runs("failed"),
            },
            "pipeline": {"stage_version": STAGE_VERSION, "stages": list(STAGE_ORDER)},
            "rule_pack": {"rule_pack_id": RULE_PACK_ID, "rule_pack_version": RULE_PACK_VERSION},
        }

    def preflight_preview(self, recipe_id: str, *, population: int, fhir: bool, csv: bool,
                          version: str | None = None) -> dict[str, Any]:
        recipe = self.recipes.get(recipe_id, version)
        if recipe is None:
            raise ValueError("Recipe not found.")
        settings = self.settings()
        spec = GenerationSpec(population=int(population), seed=0, fhir=fhir, csv=csv,
                              years_of_history=int(recipe["body"].get("exports", {}).get("years_of_history", 5)),
                              max_heap_mb=settings.max_heap_mb)
        report = preflight(settings, self.storage_root, population=spec.population,
                           fhir=fhir, csv=csv,
                           require_validator=bool(recipe["body"].get("validation", {}).get("strict_fhir_required")),
                           generation_running=self.store.has_active_generation())
        payload = report.to_dict()
        payload["recipe"] = {"recipe_id": recipe["recipe_id"], "version": recipe["version"],
                             "status": recipe["status"]}
        payload["generator"] = {"version": settings.synthea_version,
                                "checksum_pinned": bool(settings.synthea_sha256)}
        payload["cohort"] = recipe["body"].get("cohort") or {}
        return payload

    # -- jobs ------------------------------------------------------------- #

    def queue_job(self, *, recipe_id: str, population: int, accepted_target: int = 0,
                  seed: int | None = None, fhir: bool = True, csv: bool = True,
                  years_of_history: int | None = None,
                  version: str | None = None) -> dict[str, Any]:
        recipe = self.recipes.get(recipe_id, version)
        if recipe is None:
            raise ValueError("Recipe not found.")
        if recipe["status"] not in {"active", "clinical_reviewed", "technical_validated", "draft"}:
            raise ValueError("Recipe cannot be run in its current lifecycle state.")
        body = recipe["body"]
        limits = body.get("population", {})
        maximum = int(limits.get("maximum", 500))
        population = max(1, min(int(population), maximum))
        settings = self.settings()
        if seed is None:
            seed = int(datetime.now(timezone.utc).timestamp()) % 1_000_000
        spec = GenerationSpec(
            population=population, seed=int(seed), fhir=bool(fhir), csv=bool(csv),
            years_of_history=int(years_of_history if years_of_history is not None
                                 else body.get("exports", {}).get("years_of_history", 5)),
            age_min=int(body.get("demographics", {}).get("age_min", 0)),
            age_max=int(body.get("demographics", {}).get("age_max", 105)),
            gender=str(body.get("demographics", {}).get("gender", "any")),
            max_heap_mb=settings.max_heap_mb,
        )
        key = idempotency_key(recipe, spec, settings)
        existing = self.store.get_run_by_idempotency(key)
        if existing is not None:
            return {"run": existing, "idempotent_reuse": True}

        if self.job_store is None:
            raise RuntimeError("Job store is not wired; cannot queue a durable job.")
        job_id = self.job_store.create_job(JOB_KIND, {
            "recipe_id": recipe["recipe_id"], "recipe_version": recipe["version"],
            "population": population, "accepted_target": int(accepted_target),
            "seed": int(seed), "fhir": bool(fhir), "csv": bool(csv),
            "years_of_history": spec.years_of_history, "idempotency_key": key,
        })
        run = self.store.create_run(
            job_id=job_id, recipe_id=recipe["recipe_id"], recipe_version=recipe["version"],
            idempotency_key=key,
            staging_path=str(paths.staging_dir(self.storage_root, job_id)),
        )
        self.store.update_run(run["run_id"], counts={
            "request": {"population": population, "accepted_target": int(accepted_target),
                        "seed": int(seed), "fhir": bool(fhir), "csv": bool(csv),
                        "years_of_history": spec.years_of_history},
        })
        self._emit("platform.synthetic_data.job_queued", {
            "job_id": job_id, "recipe_id": recipe["recipe_id"],
            "recipe_version": recipe["version"], "idempotency_key": key,
        })
        return {"run": self.store.get_run(run["run_id"]), "job_id": job_id,
                "idempotent_reuse": False}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        run = self.store.get_run_by_job(job_id)
        event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()
        if self.job_store is not None:
            self.job_store.update_job(job_id, status="cancelled")
        if run is not None:
            self.store.update_run(run["run_id"], status="cancelled")
            self._emit("platform.synthetic_data.job_cancelled", {
                "job_id": job_id, "stage": run["stage"], "reason": "user_requested",
            })
        return {"job_id": job_id, "cancelled": run is not None}

    def cancel_event(self, job_id: str) -> threading.Event:
        with self._lock:
            event = self._cancel_events.get(job_id)
            if event is None:
                event = threading.Event()
                self._cancel_events[job_id] = event
            return event

    # -- worker handler --------------------------------------------------- #

    def run_job(self, job_id: str, checkpoint: Callable[[dict], bool] | None = None,
                progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
        """Execute one queued job. Registered with JobRunner as ``synthetic_generation``."""
        run = self.store.get_run_by_job(job_id)
        if run is None:
            raise RuntimeError("No factory run is linked to this job.")
        recipe = self.recipes.get(run["recipe_id"], run["recipe_version"])
        if recipe is None:
            raise RuntimeError("The recipe for this run no longer exists.")
        settings = self.settings()
        cancel = self.cancel_event(job_id)
        pipeline = SyntheticDataPipeline(
            self.store, adapter=self.adapter, java_detector=self.java_detector
        )
        self._active_case_context = {
            "dataset_id": str(run.get("dataset_id") or f"synds_{run['run_id'][-20:]}"),
            "recipe_id": str(run.get("recipe_id") or ""),
        }
        ctx = PipelineContext(
            run=run, recipe=recipe, settings=settings, storage_root=self.storage_root,
            adapter=pipeline.adapter_for(recipe), cancel=cancel,
            event_sink=self._emit,
            import_adapter=self._import_directory,
            checkpoint_sink=(lambda data: checkpoint(data) if checkpoint else None),
            progress_sink=progress,
        )
        try:
            return pipeline.run(ctx)
        finally:
            self._active_case_context = {}

    def _import_directory(self, directory: Path) -> dict[str, Any]:
        """Import accepted bundles and create privacy-minimised lottery cases."""
        if self._case_repository is None:
            result = {"patients": 0, "facts": 0, "imported": False,
                      "note": "No case repository is wired."}
        else:
            result = self._case_repository.import_directory(directory)
        if self._case_lottery is not None and self._active_case_context:
            from .teaching_cases import author_cases_from_accepted_fhir
            teaching = author_cases_from_accepted_fhir(
                directory, self._case_lottery,
                dataset_id=self._active_case_context.get("dataset_id", ""),
                recipe_id=self._active_case_context.get("recipe_id", ""),
            )
            result["teaching_cases"] = teaching
        return result

    _case_repository = None
    _case_lottery = None

    def attach_case_repository(self, repository) -> None:
        self._case_repository = repository

    def attach_case_lottery(self, lottery) -> None:
        """Attach the shared daily lottery for automatic synthetic teaching cases."""
        self._case_lottery = lottery

    # -- read models ------------------------------------------------------ #

    def job_detail(self, job_id: str) -> dict[str, Any] | None:
        run = self.store.get_run_by_job(job_id)
        if run is None:
            return None
        job = None
        if self.job_store is not None:
            with self.job_store.transaction() as conn:
                row = conn.execute("SELECT * FROM background_jobs WHERE id=?", (job_id,)).fetchone()
            if row is not None:
                job = dict(row)
                job["payload"] = _maybe_json(job.pop("payload_json", "{}"))
                job["checkpoint"] = _maybe_json(job.pop("checkpoint_json", "{}"))
                job["result"] = _maybe_json(job.pop("result_json", "{}"))
        return {"run": run, "job": job, "stages": list(STAGE_ORDER)}

    def dataset_detail(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self.store.get_dataset(dataset_id)
        if dataset is None:
            return None
        dataset["artifacts"] = self.store.list_artifacts(dataset_id)
        dataset["quarantine"] = self.store.list_quarantine(dataset_id=dataset_id, limit=200)
        dataset["finding_counts"] = self._finding_counts(dataset_id)
        return dataset

    def _finding_counts(self, dataset_id: str) -> dict[str, int]:
        findings = self.store.list_findings(dataset_id, limit=5000)
        counts: dict[str, int] = {}
        for finding in findings:
            key = f"{finding['dimension']}:{finding['severity']}"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def quality_report(self, dataset_id: str) -> dict[str, Any] | None:
        dataset = self.store.get_dataset(dataset_id)
        if dataset is None:
            return None
        findings = self.store.list_findings(dataset_id, limit=5000)
        return {
            "dataset": dataset,
            "findings": findings,
            "severity_counts": _count_by(findings, "severity"),
            "dimension_counts": _count_by(findings, "dimension"),
            "limitations": [
                "A technically accepted synthetic fixture is not a clinically reviewed learning scenario.",
                "Strict FHIR conformance is reported only when a pinned HL7 validator ran.",
                "Findings describe data shape and internal consistency; they do not judge clinical normality.",
            ],
        }

    def quarantine_detail(self, item_id: str) -> dict[str, Any] | None:
        item = self.store.get_quarantine_item(item_id)
        if item is None:
            return None
        item["patient_key"] = pseudonymous_key(item["patient_key"])
        item["reviews"] = self.store.list_reviews(item_id=item_id)
        return item

    # -- schedules -------------------------------------------------------- #

    def create_schedule(self, *, name: str, recipe_id: str, population: int,
                        accepted_target: int = 0, frequency: str = "weekly",
                        enabled: bool = False, version: str | None = None) -> dict[str, Any]:
        recipe = self.recipes.get(recipe_id, version)
        if recipe is None:
            raise ValueError("Recipe not found.")
        if frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("Frequency must be daily, weekly or monthly.")
        record = self.store.create_schedule({
            "name": name, "recipe_id": recipe["recipe_id"],
            "recipe_version": recipe["version"], "population": population,
            "accepted_target": accepted_target, "frequency": frequency, "enabled": enabled,
        })
        if enabled:
            record = self.store.update_schedule(record["schedule_id"],
                                                next_run_at=_next_run(frequency))
        return record

    def ensure_default_schedule(self) -> dict[str, Any]:
        """Create the bounded, durable daily synthetic teaching-case supply schedule once.

        The schedule only produces explicitly synthetic data. Recipe and dataset QA
        remain required before cases can enter the daily lottery; this is not clinical
        approval. A stable ID makes startup/restart idempotent.
        """
        schedule_id = "synsch_hsptl_daily_teaching_supply_v1"
        existing = self.store.get_schedule(schedule_id)
        if existing is not None:
            return existing
        recipe_id = "asthma-cohort"
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            raise RuntimeError("The built-in asthma synthetic recipe is unavailable")
        now = _now()
        record = self.store.create_schedule({
            "schedule_id": schedule_id,
            "name": "HSPTL daily synthetic teaching-case supply",
            "recipe_id": recipe_id,
            "recipe_version": recipe["version"],
            "population": min(20, int(recipe["body"].get("population", {}).get("maximum", 20))),
            "accepted_target": 10,
            "frequency": "daily",
            "enabled": True,
        })
        return self.store.update_schedule(schedule_id, next_run_at=now,
                                          last_status="seeded_automatically") or record

    def run_due_schedules(self) -> list[dict[str, Any]]:
        """Queue any due schedule. Never overlaps with an active run."""
        queued: list[dict[str, Any]] = []
        if self.store.has_active_generation():
            return queued
        for schedule in self.store.due_schedules(_now()):
            if not schedule["enabled"]:
                continue
            try:
                result = self.queue_job(recipe_id=schedule["recipe_id"],
                                        population=int(schedule["population"]),
                                        accepted_target=int(schedule["accepted_target"]),
                                        version=schedule["recipe_version"])
            except (ValueError, RuntimeError) as exc:
                self.store.update_schedule(schedule["schedule_id"], last_status=f"error:{exc}"[:120])
                continue
            self.store.update_schedule(
                schedule["schedule_id"], last_run_at=_now(),
                next_run_at=_next_run(schedule["frequency"]), last_status="queued",
            )
            queued.append({"schedule_id": schedule["schedule_id"], "job_id": result.get("job_id")})
        return queued


def _next_run(frequency: str) -> str:
    now = datetime.now(timezone.utc)
    delta = {"daily": timedelta(days=1), "weekly": timedelta(days=7),
             "monthly": timedelta(days=30)}.get(frequency, timedelta(days=7))
    return (now + delta).isoformat(timespec="seconds")


def _maybe_json(text: str) -> Any:
    import json
    try:
        return json.loads(text or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return counts
