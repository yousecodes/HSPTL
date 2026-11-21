"""Deterministic normalisation helpers; no clinical inference is performed."""
from __future__ import annotations
from typing import Any

def source_label(value: str | None = None) -> str:
    return str(value or "Synthea FHIR (synthetic, educational only)").strip()

def resource_identity(resource: dict[str, Any]) -> tuple[str, str]:
    return str(resource.get("resourceType") or "Unknown"), str(resource.get("id") or "")
