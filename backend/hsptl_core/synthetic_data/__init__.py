"""HSPTL automated synthetic data factory.

Local-first, model-free generation of synthetic clinical fixtures with layered
validation, immutable provenance, quarantine and idempotent import.

Safety boundary: technical validation and registration of synthetic fixtures is
automated. Nothing here represents a generated record as a clinically validated
teaching scenario, treatment guidance, clinical evidence or competency
assessment.
"""
from __future__ import annotations

from .cohort import CohortCriteria, CohortSelection, select_cohort
from .manifest import DatasetManifest, verify_manifest, write_manifest
from .paths import UnsafePath, ensure_layout, resolve_under, safe_relative, safe_segment
from .pipeline import STAGE_ORDER, STAGE_VERSION, PipelineContext, SyntheticDataPipeline
from .recipes import LIFECYCLE, RECIPE_SCHEMA_VERSION, RecipeRegistry
from .runtime import (
    FactorySettings,
    FakeSyntheaAdapter,
    GenerationError,
    GenerationSpec,
    SyntheaProcessAdapter,
    preflight,
)
from .schema import apply as apply_schema
from .service import JOB_KIND, SyntheticDataFactory
from .store import FactoryStore
from .validation import RULE_PACK_ID, RULE_PACK_VERSION, validate_dataset

__all__ = [
    "CohortCriteria", "CohortSelection", "select_cohort",
    "DatasetManifest", "verify_manifest", "write_manifest",
    "UnsafePath", "ensure_layout", "resolve_under", "safe_relative", "safe_segment",
    "STAGE_ORDER", "STAGE_VERSION", "PipelineContext", "SyntheticDataPipeline",
    "LIFECYCLE", "RECIPE_SCHEMA_VERSION", "RecipeRegistry",
    "FactorySettings", "FakeSyntheaAdapter", "GenerationError", "GenerationSpec",
    "SyntheaProcessAdapter", "preflight",
    "apply_schema", "JOB_KIND", "SyntheticDataFactory", "FactoryStore",
    "RULE_PACK_ID", "RULE_PACK_VERSION", "validate_dataset",
]
