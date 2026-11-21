"""Filesystem-backed read-only catalogue for the versioned PROforma model library."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .proforma import validate_plan

MODEL_ROOT = Path(__file__).with_name("models")


def model_catalogue() -> dict[str, Any]:
    items = []
    for path in sorted(MODEL_ROOT.rglob("*.json")):
        relative = path.relative_to(MODEL_ROOT).as_posix()
        try:
            model = json.loads(path.read_text(encoding="utf-8"))
            validation = validate_plan(model)
            items.append({"path": relative, "id": model.get("id"), "title": model.get("title"),
                          "valid": validation["valid"], "errors": validation["errors"]})
        except Exception as exc:
            items.append({"path": relative, "valid": False, "errors": [str(exc)]})
    return {"logic_language": "HSPTL-PROforma-Subset/1.1", "models": items,
            "executable_languages": ["PROforma"], "model_count": len(items)}


def load_model(relative_path: str) -> dict[str, Any]:
    candidate = (MODEL_ROOT / relative_path).resolve()
    if MODEL_ROOT.resolve() not in candidate.parents or candidate.suffix != ".json":
        raise ValueError("Model path must identify a JSON file inside the PROforma model library.")
    if not candidate.is_file():
        raise KeyError(relative_path)
    model = json.loads(candidate.read_text(encoding="utf-8"))
    validation = validate_plan(model)
    if not validation["valid"]:
        raise ValueError("Invalid PROforma model: " + "; ".join(validation["errors"]))
    return model
