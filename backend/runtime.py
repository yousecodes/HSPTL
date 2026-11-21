"""Shared singletons: routes -> services -> repositories -> SQLite.

main.py imports these names so the API and the routers share one set of
repository objects. No background thread is started at import time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .hsptl_core.config import ensure_user_dirs, load_settings, save_settings, PACKAGE_DIR
from .hsptl_core.case_engine import CaseRepository
from .hsptl_core.content_review import ContentReviewService
from .hsptl_core.episodes import EpisodeRepository
from .hsptl_core.exams import ExamRepository
from .hsptl_core.jobs import JobRunner
from .hsptl_core.search import SearchService
from .hsptl_core.source_cache import ExternalSourceCache
from .hsptl_core.store import StudyStore
from .hsptl_core.institutional import InstitutionalAuth, CohortRepository

PATHS = ensure_user_dirs()
SETTINGS: dict[str, Any] = load_settings(PATHS["settings"])
STORE = StudyStore(PATHS["database"])
CASE_STORE = CaseRepository(PATHS["database"])
EPISODES = EpisodeRepository(PATHS["database"])
EXAMS = ExamRepository(PATHS["database"])
SEARCH = SearchService(STORE)
REVIEWS = ContentReviewService(STORE)
CACHE = ExternalSourceCache(STORE)
JOBS = JobRunner(STORE)
INSTITUTIONAL_AUTH = InstitutionalAuth(PATHS["database"])
COHORTS = CohortRepository(PATHS["database"])

from .hsptl_core.synthetic_data.service import JOB_KIND as SYNTHETIC_JOB_KIND, SyntheticDataFactory
from .hsptl_core.synthetic_data.pipeline import STAGE_VERSION as SYNTHETIC_STAGE_VERSION
from .hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine
from .hsptl_core.hsp_tl40.kernel import EventKernel

SYNTHETIC_FACTORY = SyntheticDataFactory(
    PATHS["database"],
    storage_root=Path(PATHS["database"]).parent,
    event_kernel=EventKernel(DeterministicIntelligenceEngine(PATHS["database"])),
    job_store=STORE,
)
SYNTHETIC_FACTORY.attach_case_repository(CASE_STORE)


def update_settings(**changes: Any) -> dict[str, Any]:
    SETTINGS.update(changes)
    save_settings(SETTINGS, PATHS["settings"])
    return SETTINGS


def _register_default_jobs() -> None:
    def fhir_import(payload: dict, checkpoint) -> dict:
        checkpoint({"phase": "importing", "path": payload.get("path", "")})
        return CASE_STORE.import_directory(Path(payload["path"]),
                                           batch_size=int(payload.get("batch_size", 250)))

    def content_rebuild(payload: dict, checkpoint) -> dict:
        flagged = REVIEWS.flag_stale_sources()
        checkpoint({"phase": "stale_sources_flagged", "flagged": flagged})
        return {"flagged_notes": flagged}

    JOBS.register("fhir_import", fhir_import)
    JOBS.register("content_rebuild", content_rebuild)

    def synthetic_generation(payload: dict, checkpoint) -> dict:
        job_id = str(payload.get("_job_id") or payload.get("job_id") or "")
        if not job_id:
            raise RuntimeError("Synthetic generation job is missing its job identifier.")
        return SYNTHETIC_FACTORY.run_job(job_id, checkpoint=checkpoint)

    JOBS.register(SYNTHETIC_JOB_KIND, synthetic_generation)

    from .hsptl_tools.jobs import register_tool_jobs
    register_tool_jobs(JOBS, paths=PATHS, store=STORE)


_register_default_jobs()

from .hsptl_tools.execution import ToolExecutionService
TOOL_EXECUTION = ToolExecutionService(STORE, JOBS)

# --- HSPTL 5.1.0 learning intelligence ------------------------------------------ #
from .hsptl_core.content_labels import ContentLabelRegistry
from .hsptl_core.source_registry import SourceRegistry
from .hsptl_core.local_sources import LocalSourceManager, register_rescan_job
from .hsptl_core.case_lottery import CaseLottery
from .hsptl_core.pearls_factory import PearlsFactory
from .hsptl_core.engine_integration import EngineIntegration
from .hsptl_core.ucks import UCKSRepository as _UCKSRepository
from .hsptl_core.hsp_tl40.guards import Guards as _Guards
from .hsptl_core.hsp_tl40.reasoner import Reasoner as _Reasoner
from .hsptl_core.hsp_tl40.composer import Composer as _Composer
from .hsptl_core.hsp_tl40.router import Router as _Router
from .hsptl_core.hsp_tl40.proforma import ProformaRuntime as _ProformaRuntime

LABELS = ContentLabelRegistry(STORE)
SOURCE_REGISTRY = SourceRegistry(STORE)
LOCAL_SOURCES = LocalSourceManager(STORE, labels=LABELS, registry=SOURCE_REGISTRY)
CASE_LOTTERY = CaseLottery(STORE, auto_replenish=True)
SYNTHETIC_FACTORY.attach_case_lottery(CASE_LOTTERY)
UCKS_REPO = _UCKSRepository(STORE)
PEARLS_FACTORY = PearlsFactory(STORE, ucks_repo=UCKS_REPO,
                               registry=SOURCE_REGISTRY, labels=LABELS)

_ENGINE = DeterministicIntelligenceEngine(PATHS["database"])
_KERNEL = EventKernel(_ENGINE)
_GUARDS = _Guards(_KERNEL, _ENGINE)
ENGINE_INTEGRATION = EngineIntegration(
    kernel=_KERNEL, reasoner=_Reasoner(_ENGINE), logic=_ProformaRuntime(_KERNEL),
    composer=_Composer(_ENGINE, _KERNEL, _GUARDS),
    router=_Router(_KERNEL, _GUARDS, _ENGINE), guards=_GUARDS,
)

LOCAL_SOURCE_JOB_KIND = LocalSourceManager.JOB_KIND
register_rescan_job(JOBS, LOCAL_SOURCES)

# --- HSPTL 5.1 learning intelligence ------------------------------------- #
from .hsptl_core.learning_intelligence import LearningIntelligence
LEARNING_INTELLIGENCE = LearningIntelligence(STORE, CASE_LOTTERY)
