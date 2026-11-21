"""Non-invasive capability discovery for optional HSPTL integrations.

This module deliberately checks package availability without importing optional
packages or loading model weights. Core workflows never depend on these checks.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path
from typing import Any


OPTIONAL_MODULES: dict[str, tuple[str, str]] = {
    "presidio": ("presidio_analyzer", "Privacy scanning assistance"),
}


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _fiji_status() -> dict[str, Any]:
    configured = os.environ.get("HSPTL_FIJI_PATH", "").strip()
    candidates = [Path(configured).expanduser()] if configured else []
    for executable in ("ImageJ-win64.exe", "ImageJ.exe", "fiji", "ImageJ"):
        found = shutil.which(executable)
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.exists():
            return {"status": "available", "installed": True, "path_configured": True,
                    "detail": "Fiji/ImageJ is available as an independent specialist tool."}
    return {"status": "not_installed", "installed": False, "path_configured": False,
            "detail": "Fiji is optional; other HSPTL departments work without it."}


def capability_report(fts5_available: bool = True) -> dict[str, Any]:
    optional: dict[str, Any] = {}
    for key, (module_name, description) in OPTIONAL_MODULES.items():
        installed = _module_available(module_name)
        optional[key] = {
            "status": "available" if installed else "not_installed",
            "installed": installed,
            "module": module_name,
            "description": description,
        }
    optional["fiji"] = _fiji_status()
    optional["rxnorm"] = {
        "status": "not_configured", "installed": False,
        "description": "Medication terminology lookup is unavailable until an approved local source is configured. Unmatched medicines remain unmatched.",
    }
    optional["umls"] = {
        "status": "license_required", "installed": False,
        "description": "UMLS-derived content requires an active licence and export-policy validation.",
    }
    return {
        "core": {"status": "available", "features": [
            "clinic", "osce_text", "specialties", "pearls", "exam_authoring",
            "sqlite_storage", "local_search", "deterministic_fhir_import", "progress",
        ], "search_engine": "sqlite_fts5" if fts5_available else "sqlite_like_fallback"},
        "optional": optional,
        "policy": {
            "optional_dependencies_imported_at_startup": False,
            "model_weights_loaded_at_startup": False,
            "presidio_is_complete_deidentification": False,
            "ragas_in_normal_runtime": False,
            "ai_models_enabled": False,
            "embedding_models_enabled": False,
            "model_weights_loaded": False,
        },
    }
