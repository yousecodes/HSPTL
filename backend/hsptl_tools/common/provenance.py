"""Small shared provenance contracts for tool-generated and imported records."""
from __future__ import annotations
from typing import Any

def synthetic_provenance(generator: str, source_label: str, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"generator": generator, "source_label": source_label, "synthetic": True,
            "source_evidence": list(evidence or [])}

def harvested_provenance(tool: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"harvester": tool, "metadata": dict(metadata or {}), "review_required": True}
