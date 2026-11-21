"""The synthetic data factory pipeline.

A durable, resumable state machine. Every stage records start/end, counts and
artifact digests, writes a checkpoint the worker can resume from, and is safe to
re-run. A failed validation stage never proceeds to import: the run stops and
the affected patient bundles are quarantined.

The stage order is fixed and versioned. ``STAGE_ORDER`` is the contract; the
checkpoint stores the last completed stage index, so a restart resumes at the
next stage rather than repeating work or skipping ahead.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import manifest as manifest_module
from .cohort import CohortCriteria, select_cohort
from .fhir_parse import bundle_patient_id, load_bundles
from .manifest import ArtifactRecord, DatasetManifest, file_digest, write_manifest
from .paths import (
    dataset_dir, quarantine_dir, quarantine_filename, safe_artifact_name, staging_dir,
)
from .recipes import canonical_digest
from .runtime import (
    FactorySettings,
    GenerationError,
    GenerationSpec,
    GeneratorAdapter,
    preflight,
)
from .validation import RULE_PACK_ID, RULE_PACK_VERSION, validate_dataset

STAGE_VERSION = "pipeline/1.0"

STAGE_ORDER = (
    "queued",
    "preflight",
    "generating",
    "exporting",
    "inventorying",
    "fhir_validating",
    "reference_validating",
    "chronology_validating",
    "terminology_auditing",
    "plausibility_auditing",
    "completeness_scoring",
    "normalizing",
    "quarantine_partitioning",
    "importing",
    "registering",
    "completed",
)

TERMINAL_STATES = {"completed", "failed", "cancelled", "partial_cohort",
                   "completed_with_quarantine", "blocked"}

# Stages whose failure must stop the run before import.
MANDATORY_STAGES = {"preflight", "generating", "exporting", "inventorying",
                    "fhir_validating", "reference_validating"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StageFailure(RuntimeError):
    def __init__(self, stage: str, code: str, detail: str):
        super().__init__(f"{stage}: {detail}")
        self.stage = stage
        self.code = code
        self.detail = detail


@dataclass
class PipelineContext:
    """Everything a stage needs, assembled once per run."""
    run: dict[str, Any]
    recipe: dict[str, Any]
    settings: FactorySettings
    storage_root: Path
    adapter: GeneratorAdapter
    cancel: threading.Event
    event_sink: Callable[[str, dict[str, Any]], None]
    import_adapter: Callable[[Path], dict[str, Any]] | None = None
    checkpoint_sink: Callable[[dict[str, Any]], None] | None = None
    progress_sink: Callable[[int, int], None] | None = None
    started_at: str = field(default_factory=_now)
    counts: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return self.run["run_id"]

    @property
    def job_id(self) -> str:
        return self.run["job_id"]


def idempotency_key(recipe: dict[str, Any], spec: GenerationSpec, settings: FactorySettings) -> str:
    """Canonical key: identical inputs return the same run."""
    payload = {
        "pipeline": STAGE_VERSION,
        "recipe": {"id": recipe["recipe_id"], "version": recipe["version"],
                   "digest": recipe.get("content_digest", "")},
        "generator": {"version": settings.synthea_version,
                      "sha256": settings.synthea_sha256.casefold()},
        "spec": spec.canonical(),
        "modules": {"dir": settings.module_dir, "config": settings.config_file},
    }
    return canonical_digest(payload)


class SyntheticDataPipeline:
    """Runs one dataset job from preflight to registration."""

    def __init__(self, store, *, adapter: GeneratorAdapter | None = None,
                 java_detector: Callable[[str], tuple[bool, str]] | None = None):
        self.store = store
        self._adapter_override = adapter
        self._java_detector = java_detector

    def adapter_for(self, recipe: dict[str, Any]) -> GeneratorAdapter:
        if self._adapter_override is not None:
            return self._adapter_override
        from .runtime import SyntheaProcessAdapter
        return SyntheaProcessAdapter()

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        start_index = int(ctx.run.get("stage_index") or 0)
        outcome = "completed"
        try:
            for index in range(start_index + 1, len(STAGE_ORDER)):
                stage = STAGE_ORDER[index]
                if ctx.cancel.is_set() and stage not in {"queued", "completed"}:
                    outcome = "cancelled"
                    self._emit(ctx, "platform.synthetic_data.job_cancelled", {
                        "job_id": ctx.job_id, "stage": stage, "reason": "user_cancelled",
                    })
                    break
                self._set_stage(ctx, stage, index)
                handler = getattr(self, f"_stage_{stage}", None)
                if handler is None:
                    continue
                result = handler(ctx) or {}
                if result.get("terminal"):
                    outcome = str(result.get("status") or "completed")
                    break
                if ctx.progress_sink:
                    ctx.progress_sink(index + 1, len(STAGE_ORDER) - 1)
        except StageFailure as failure:
            outcome = "blocked" if failure.code == "preflight_failed" else "failed"
            self.store.update_run(ctx.run_id, status=outcome, stage=failure.stage,
                                  error_code=failure.code, diagnostic=failure.detail[:2000])
            self._emit(ctx, "platform.synthetic_data.stage_changed", {
                "job_id": ctx.job_id, "stage": failure.stage, "stage_version": STAGE_VERSION,
                "status": "failed", "counts": {"code": failure.code},
            })
            return {"status": outcome, "stage": failure.stage, "error_code": failure.code,
                    "detail": failure.detail}
        except GenerationError as exc:
            self.store.update_run(ctx.run_id, status="failed", error_code="generation_failed",
                                  diagnostic=str(exc)[:2000])
            return {"status": "failed", "stage": "generating", "error_code": "generation_failed"}
        except Exception as exc:  # noqa: BLE001 - the worker must survive a stage bug
            self.store.update_run(ctx.run_id, status="failed", error_code=type(exc).__name__,
                                  diagnostic=str(exc)[:2000])
            raise

        if outcome == "cancelled":
            self.store.update_run(ctx.run_id, status="cancelled")
        return {"status": outcome, "stage": self.store.get_run(ctx.run_id)["stage"] if self.store.get_run(ctx.run_id) else "",
                "counts": ctx.counts}

    # -- helpers ---------------------------------------------------------- #

    def _emit(self, ctx: PipelineContext, event_type: str, payload: dict[str, Any]) -> None:
        try:
            ctx.event_sink(event_type, payload)
        except Exception:  # noqa: BLE001 - audit failure must not corrupt the run
            pass

    def _set_stage(self, ctx: PipelineContext, stage: str, index: int) -> None:
        self.store.update_run(ctx.run_id, stage=stage, stage_index=index, status="running")
        if ctx.checkpoint_sink:
            ctx.checkpoint_sink({"stage": stage, "stage_index": index, "stage_version": STAGE_VERSION,
                                 "counts": ctx.counts})
        self._emit(ctx, "platform.synthetic_data.stage_changed", {
            "job_id": ctx.job_id, "stage": stage, "stage_version": STAGE_VERSION,
            "status": "running", "counts": dict(ctx.counts),
        })

    def _staging(self, ctx: PipelineContext) -> Path:
        return staging_dir(ctx.storage_root, ctx.run_id)

    # -- stages ----------------------------------------------------------- #

    def _stage_preflight(self, ctx: PipelineContext) -> dict[str, Any]:
        spec = self._spec(ctx)
        report = preflight(
            ctx.settings, ctx.storage_root,
            population=spec.population, fhir=spec.fhir, csv=spec.csv,
            require_validator=bool(ctx.recipe["body"].get("validation", {}).get("strict_fhir_required")),
            generation_running=self._other_active_run(ctx.run_id),
            java_detector=self._java_detector,
        )
        java_check = next((item for item in report.checks if item.check_id == "java_runtime"), None)
        ctx.counts["preflight"] = report.to_dict()
        ctx.counts["preflight"]["java"] = java_check.detail if java_check else ""
        if not report.ok:
            details = "; ".join(item.detail for item in report.blockers)
            raise StageFailure("preflight", "preflight_failed", details)
        return {}

    def _other_active_run(self, run_id: str) -> bool:
        for run in self.store.list_runs(limit=50):
            if run["run_id"] != run_id and run["status"] in {"queued", "running"}:
                return True
        return False

    def _spec(self, ctx: PipelineContext) -> GenerationSpec:
        options = ctx.run.get("counts", {}).get("request", {}) or {}
        body = ctx.recipe["body"]
        population_cfg = body.get("population", {})
        exports = body.get("exports", {})
        demographics = body.get("demographics", {})
        return GenerationSpec(
            population=int(options.get("population") or population_cfg.get("default", 5)),
            seed=int(options.get("seed") or 0),
            fhir=bool(options.get("fhir", exports.get("fhir", True))),
            csv=bool(options.get("csv", exports.get("csv", True))),
            years_of_history=int(options.get("years_of_history", exports.get("years_of_history", 5))),
            age_min=int(demographics.get("age_min", 0)),
            age_max=int(demographics.get("age_max", 105)),
            gender=str(demographics.get("gender", "any")),
            max_heap_mb=ctx.settings.max_heap_mb,
        )

    def _stage_generating(self, ctx: PipelineContext) -> dict[str, Any]:
        spec = self._spec(ctx)
        staging = self._staging(ctx)
        output = staging / "source"
        logs = staging / "logs"
        result = ctx.adapter.generate(
            spec, ctx.settings, output,
            log_path=logs / "generation.log", cancel=ctx.cancel,
            on_progress=lambda phase: None,
        )
        if result.cancelled:
            return {"terminal": True, "status": "cancelled"}
        ctx.counts["generation"] = {
            "generated_patients": result.generated_patients,
            "returncode": result.returncode,
            "duration_seconds": round(result.duration_seconds, 3),
            "seed": spec.seed,
        }
        if result.generated_patients == 0:
            raise StageFailure("generating", "empty_output",
                               "The generator produced no patient files.")
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_exporting(self, ctx: PipelineContext) -> dict[str, Any]:
        staging = self._staging(ctx)
        source = staging / "source"
        fhir_dir = source / "fhir"
        csv_dir = source / "csv"
        exported: dict[str, Any] = {
            "fhir": fhir_dir.is_dir(),
            "csv": csv_dir.is_dir(),
            "fhir_files": sum(1 for _ in fhir_dir.rglob("*.json")) if fhir_dir.is_dir() else 0,
            "csv_files": sum(1 for _ in csv_dir.rglob("*.csv")) if csv_dir.is_dir() else 0,
        }
        ctx.counts["exports"] = exported
        if not exported["fhir"] and not exported["csv"]:
            raise StageFailure("exporting", "no_exports",
                               "Neither a FHIR nor a CSV export directory was produced.")
        return {}

    def _stage_inventorying(self, ctx: PipelineContext) -> dict[str, Any]:
        staging = self._staging(ctx)
        fhir_dir = staging / "source" / "fhir"
        bundles, problems = load_bundles(fhir_dir)
        ctx.counts["inventory"] = {
            "bundles": len(bundles),
            "parse_problems": [problem.__dict__ for problem in problems],
        }
        if not bundles:
            raise StageFailure("inventorying", "no_parseable_bundles",
                               "No parseable FHIR bundles were found in the export.")
        self._bundles = bundles
        self._bundles_run = ctx.run_id

        # Cohort selection happens here, once, over the full generated set. A
        # shortfall is reported as partial_cohort and is never padded.
        criteria = CohortCriteria.from_recipe(ctx.recipe["body"].get("cohort"))
        request = ctx.run.get("counts", {}).get("request", {}) or {}
        target = int(request.get("accepted_target") or 0)
        selection = select_cohort(bundles, criteria, target_patients=target)
        self._cohort = selection
        ctx.counts["cohort"] = selection.to_dict()
        if selection.status == "partial_cohort":
            ctx.counts["cohort"]["shortfall"] = target - selection.selected_patients
        # Subsequent stages evaluate only the selected bundles.
        self._bundles = selection.selected
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _bundles_for(self, ctx: PipelineContext) -> list[tuple[str, dict[str, Any]]]:
        if getattr(self, "_bundles", None) is not None and getattr(self, "_bundles_run", None) == ctx.run_id:
            return self._bundles
        staging = self._staging(ctx)
        bundles, _ = load_bundles(staging / "source" / "fhir")
        self._bundles = bundles
        self._bundles_run = ctx.run_id
        return bundles

    def _stage_fhir_validating(self, ctx: PipelineContext) -> dict[str, Any]:
        bundles = self._bundles_for(ctx)
        required = ctx.recipe["body"].get("validation", {}).get("required_resources", [])
        criteria = CohortCriteria.from_recipe(ctx.recipe["body"].get("cohort"))
        strict = bool(ctx.settings.strict_fhir_required and ctx.settings.validator_jar)
        report = validate_dataset(
            bundles, required_resources=required,
            cohort_codes=criteria.codes if criteria else None,
            strict_conformance=strict,
            validator_id="hl7-validator" if strict else "local-shape-checks",
            validator_version=ctx.settings.validator_version or RULE_PACK_VERSION,
        )
        self._report = report
        ctx.counts["validation"] = {
            "strict_conformance": report.strict_conformance,
            "validator_id": report.validator_id,
            "severity_counts": report.severity_counts(),
            "dimension_counts": report.dimension_counts(),
            "patients_total": len(report.patients),
            "patients_quarantined": len(report.quarantined()),
        }
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_reference_validating(self, ctx: PipelineContext) -> dict[str, Any]:
        return self._audit_stage(ctx, "reference")

    def _stage_chronology_validating(self, ctx: PipelineContext) -> dict[str, Any]:
        return self._audit_stage(ctx, "chronology")

    def _stage_terminology_auditing(self, ctx: PipelineContext) -> dict[str, Any]:
        return self._audit_stage(ctx, "terminology")

    def _stage_plausibility_auditing(self, ctx: PipelineContext) -> dict[str, Any]:
        return self._audit_stage(ctx, "plausibility")

    def _stage_completeness_scoring(self, ctx: PipelineContext) -> dict[str, Any]:
        return self._audit_stage(ctx, "completeness")

    def _audit_stage(self, ctx: PipelineContext, dimension: str) -> dict[str, Any]:
        report = getattr(self, "_report", None)
        if report is None:
            self._stage_fhir_validating(ctx)
            report = self._report
        counts = {severity: 0 for severity in ("info", "warning", "quarantine", "error")}
        for finding in report.all_findings():
            if finding.dimension == dimension:
                counts[finding.severity] = counts.get(finding.severity, 0) + 1
        ctx.counts.setdefault("dimensions", {})[dimension] = counts
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_normalizing(self, ctx: PipelineContext) -> dict[str, Any]:
        """Only semantics-preserving operations are automatic.

        The one normalization applied is canonical JSON re-serialisation of a
        derived copy. The immutable source is never touched, and the before/after
        digests are recorded so the transformation is auditable.
        """
        staging = self._staging(ctx)
        source_dir = staging / "source" / "fhir"
        derived_dir = staging / "derived" / "fhir"
        derived_dir.mkdir(parents=True, exist_ok=True)
        transformations: list[dict[str, Any]] = []
        for path in sorted(source_dir.rglob("*.json")):
            relative = path.relative_to(source_dir)
            target = derived_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            target.write_text(canonical, encoding="utf-8")
            transformations.append({
                "transformation_id": "canonical-json",
                "transformation_version": "1.0.0",
                "relative_path": relative.as_posix(),
                "source_sha256": file_digest(path),
                "output_sha256": file_digest(target),
                "reason": "Deterministic canonical serialisation of a derived copy; clinical values unchanged.",
                "timestamp": _now(),
            })
        ctx.counts["normalizations"] = {
            "count": len(transformations),
            "transformation_ids": sorted({item["transformation_id"] for item in transformations}),
        }
        self._transformations = transformations
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_quarantine_partitioning(self, ctx: PipelineContext) -> dict[str, Any]:
        report = getattr(self, "_report", None)
        if report is None:
            raise StageFailure("quarantine_partitioning", "no_validation_report",
                               "Validation did not run; refusing to partition.")
        bundles = self._bundles_for(ctx)
        by_file = {source_file: bundle for source_file, bundle in bundles}
        staging = self._staging(ctx)
        quarantine_root = staging / "quarantine" / "bundles"
        quarantine_root.mkdir(parents=True, exist_ok=True)

        quarantined = report.quarantined()
        accepted = report.accepted()
        ctx.counts["quarantine"] = {
            "quarantined_patients": len(quarantined),
            "accepted_patients": len(accepted),
            "rule_ids": sorted({rule for patient in quarantined for rule in patient.block_reasons}),
        }
        self._quarantine_records = []
        for patient in quarantined:
            bundle = by_file.get(patient.source_file)
            if bundle is not None:
                (quarantine_root / quarantine_filename(patient.patient_key)).write_text(
                    json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
            self._quarantine_records.append(patient)
        self._accepted = [(patient.source_file, by_file[patient.source_file])
                          for patient in accepted if patient.source_file in by_file]
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_importing(self, ctx: PipelineContext) -> dict[str, Any]:
        accepted = getattr(self, "_accepted", None)
        if accepted is None:
            raise StageFailure("importing", "no_acceptance_decision",
                               "Quarantine partitioning did not run; refusing to import.")
        staging = self._staging(ctx)
        import_root = staging / "import"
        import_root.mkdir(parents=True, exist_ok=True)
        for source_file, bundle in accepted:
            name = safe_artifact_name(source_file)
            (import_root / name).write_text(json.dumps(bundle, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
        result: dict[str, Any] = {"patients": len(accepted), "imported": False}
        if ctx.import_adapter is not None and accepted:
            result = ctx.import_adapter(import_root)
            result["imported"] = True
        ctx.counts["import"] = result
        self._import_result = result
        self.store.update_run(ctx.run_id, counts=ctx.counts)
        return {}

    def _stage_registering(self, ctx: PipelineContext) -> dict[str, Any]:
        staging = self._staging(ctx)
        dataset_id = ctx.run["dataset_id"] or f"synds_{ctx.run_id[-20:]}"
        target = dataset_dir(ctx.storage_root, dataset_id)
        target.mkdir(parents=True, exist_ok=True)

        source_dir = staging / "source"
        derived_dir = staging / "derived"
        artifacts: list[ArtifactRecord] = []
        storage_bytes = 0
        for kind, root in (("source", source_dir), ("derived", derived_dir)):
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(staging).as_posix()
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                size = destination.stat().st_size
                storage_bytes += size
                artifacts.append(ArtifactRecord(relative_path=relative, kind=kind,
                                                byte_size=size, sha256=file_digest(destination)))

        spec = self._spec(ctx)
        report = getattr(self, "_report", None)
        quarantine_records = getattr(self, "_quarantine_records", [])
        cohort_selection = getattr(self, "_cohort", None)

        dataset_manifest = DatasetManifest(
            dataset_id=dataset_id, job_id=ctx.job_id, run_id=ctx.run_id,
            recipe_id=ctx.recipe["recipe_id"], recipe_version=ctx.recipe["version"],
            recipe_digest=ctx.recipe.get("content_digest", ""),
            idempotency_key=ctx.run["idempotency_key"],
            synthea_version=ctx.settings.synthea_version,
            synthea_sha256=ctx.settings.synthea_sha256,
            java_version=ctx.counts.get("preflight", {}).get("java", ""),
            seed=str(spec.seed),
            command_digest=canonical_digest(spec.digestible_arguments(ctx.settings)),
            module_pack=ctx.recipe["body"].get("generator", {}).get("module_pack", ""),
            module_pack_version=ctx.recipe["body"].get("generator", {}).get("module_pack_version", ""),
            fhir_version=ctx.recipe["body"].get("exports", {}).get("fhir_version", "4.0.1"),
            exports=ctx.counts.get("exports", {}),
            years_of_history=spec.years_of_history,
            cohort=cohort_selection.to_dict() if cohort_selection else {},
            validator_id=report.validator_id if report else "",
            validator_version=report.validator_version if report else "",
            validator_sha256=ctx.settings.validator_sha256,
            rule_pack_id=RULE_PACK_ID, rule_pack_version=RULE_PACK_VERSION,
            mapping_set_version=ctx.recipe["body"].get("validation", {}).get("terminology_mapping_set", ""),
            generation_started_at=ctx.started_at,
            generation_finished_at=_now(),
            counts={"generated": ctx.counts.get("generation", {}).get("generated_patients", 0),
                    "accepted": len(getattr(self, "_accepted", [])),
                    "quarantined": len(quarantine_records)},
            resource_counts=report.resource_counts if report else {},
            artifacts=artifacts,
            validation_totals=report.to_dict() if report else {},
            quarantine_totals={"quarantined_patients": len(quarantine_records),
                               "rule_ids": sorted({r for p in quarantine_records for r in p.block_reasons})},
            import_result=getattr(self, "_import_result", {}),
            import_idempotency_key=f"{ctx.run['idempotency_key']}:import",
            normalizations=getattr(self, "_transformations", []),
            limitations=[
                "Technically accepted synthetic fixture; not a clinically reviewed learning scenario.",
                "Strict FHIR conformance is claimed only when a pinned HL7 validator ran.",
                "Synthetic distributions do not represent any real population.",
            ],
        )
        manifest_path = target / "manifests" / "dataset-manifest.json"
        written = write_manifest(dataset_manifest, manifest_path)

        record = self.store.register_dataset({
            "dataset_id": dataset_id, "run_id": ctx.run_id, "job_id": ctx.job_id,
            "recipe_id": ctx.recipe["recipe_id"], "recipe_version": ctx.recipe["version"],
            "name": f"{ctx.recipe['title']} {dataset_id[-6:]}",
            "status": "accepted" if not quarantine_records else "accepted",
            "cohort_status": cohort_selection.status if cohort_selection else "complete",
            "seed": spec.seed, "synthea_version": ctx.settings.synthea_version,
            "manifest_digest": written["manifest_digest"],
            "content_digest": written["content_digest"],
            "generated_patients": ctx.counts.get("generation", {}).get("generated_patients", 0),
            "matched_patients": cohort_selection.matched_patients if cohort_selection else 0,
            "accepted_patients": len(getattr(self, "_accepted", [])),
            "quarantined_patients": len(quarantine_records),
            "imported_patients": int(getattr(self, "_import_result", {}).get("patients", 0)),
            "validation_status": "validated" if report else "pending",
            "strict_conformance": bool(report.strict_conformance) if report else False,
            "terminology_status": "audited" if report else "pending",
            "storage_bytes": storage_bytes,
        })
        for artifact in artifacts:
            self.store.add_artifact(dataset_id=dataset_id, relative_path=artifact.relative_path,
                                    kind=artifact.kind, byte_size=artifact.byte_size,
                                    sha256=artifact.sha256)
        if report:
            self.store.add_findings(dataset_id, [finding.to_dict() for finding in report.all_findings()])
        for patient in quarantine_records:
            self.store.add_quarantine_item(
                dataset_id=dataset_id, job_id=ctx.job_id, patient_key=patient.patient_key,
                bundle_path=f"bundles/{patient.patient_key}.json",
                reason="; ".join(sorted({f.message for f in patient.findings
                                         if f.severity in {"quarantine", "error"}}))[:1000],
                rule_ids=patient.block_reasons,
            )

        # Quarantine artifacts are kept beside the dataset for reviewer inspection.
        quarantine_target = quarantine_dir(ctx.storage_root, dataset_id) / "bundles"
        if quarantine_target.parent.is_dir():
            staging_quarantine = staging / "quarantine"
            if staging_quarantine.is_dir():
                shutil.copytree(staging_quarantine, quarantine_target.parent, dirs_exist_ok=True)

        self.store.update_run(ctx.run_id, dataset_id=dataset_id, counts=ctx.counts)
        self._emit(ctx, "platform.synthetic_data.dataset_registered", {
            "dataset_id": dataset_id, "job_id": ctx.job_id,
            "recipe_id": ctx.recipe["recipe_id"], "recipe_version": ctx.recipe["version"],
            "manifest_digest": written["manifest_digest"],
            "content_digest": written["content_digest"], "artifact_count": len(artifacts),
            "accepted_patients": len(getattr(self, "_accepted", [])),
        })
        if quarantine_records:
            self._emit(ctx, "platform.synthetic_data.records_quarantined", {
                "job_id": ctx.job_id, "dataset_id": dataset_id,
                "quarantined_patients": len(quarantine_records),
                "rule_ids": sorted({r for p in quarantine_records for r in p.block_reasons}),
                "severity_counts": report.severity_counts() if report else {},
            })
        if getattr(self, "_import_result", {}).get("imported"):
            self._emit(ctx, "platform.synthetic_data.dataset_imported", {
                "dataset_id": dataset_id, "job_id": ctx.job_id,
                "imported_patients": int(self._import_result.get("patients", 0)),
                "imported_facts": int(self._import_result.get("facts", 0)),
                "idempotency_key": f"{ctx.run['idempotency_key']}:import",
                "import_status": "completed",
            })
        self._registered_dataset = record
        return {}

    def _stage_completed(self, ctx: PipelineContext) -> dict[str, Any]:
        report = getattr(self, "_report", None)
        quarantine_count = len(getattr(self, "_quarantine_records", []))
        cohort_selection = getattr(self, "_cohort", None)
        status = "completed"
        if cohort_selection is not None and cohort_selection.status == "partial_cohort":
            status = "partial_cohort"
        elif quarantine_count:
            status = "completed_with_quarantine"
        self.store.update_run(ctx.run_id, status=status, counts=ctx.counts)
        self._emit(ctx, "platform.synthetic_data.generation_completed", {
            "job_id": ctx.job_id,
            "generated_patients": ctx.counts.get("generation", {}).get("generated_patients", 0),
            "matched_patients": cohort_selection.matched_patients if cohort_selection else 0,
            "selected_patients": cohort_selection.selected_patients if cohort_selection else 0,
            "cohort_status": cohort_selection.status if cohort_selection else "not_applicable",
        })
        if report is not None:
            self._emit(ctx, "platform.synthetic_data.validation_completed", {
                "job_id": ctx.job_id,
                "dataset_id": ctx.run.get("dataset_id", ""),
                "validator_id": report.validator_id,
                "validator_version": report.validator_version,
                "strict_conformance": bool(report.strict_conformance),
                "finding_counts": report.severity_counts(),
                "dimension_results": report.dimension_counts(),
            })
        return {"terminal": True, "status": status}
