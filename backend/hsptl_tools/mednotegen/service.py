"""Application service for deterministic Synthea FHIR -> HSPTL note generation."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
from .fhir import load_fhir_directory
from .narratives import build_outputs
from .exporters import export_json, export_markdown
from .normalization import source_label as normalize_source_label
from .validation import validate_resources, validate_generated_payload

class MedNoteGenService:
    def __init__(self, ucks_repository_factory: Callable[[], Any] | None = None):
        self.ucks_repository_factory = ucks_repository_factory

    def generate(self, fhir_dir: str | Path, output_dir: str | Path, *, checkpoint=None) -> dict[str, Any]:
        source = Path(fhir_dir).expanduser().resolve()
        if not source.is_dir():
            raise ValueError("Synthea FHIR directory does not exist")
        if not any(source.glob("*.json")):
            raise ValueError("No FHIR JSON files were found in the selected directory")
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        if checkpoint:
            checkpoint({"phase": "reading_fhir", "source": str(source)})
        resources, errors = load_fhir_directory(source)
        validation = validate_resources(resources)
        generated = build_outputs(resources, source_label=normalize_source_label())
        validate_generated_payload(generated)
        json_path = export_json(generated, output / "hsptl_import.json")
        markdown_paths = export_markdown(generated, output / "documents")
        ucks_import: dict[str, int] = {"cases_seen": 0, "cases_added": 0, "pearls_seen": 0, "pearls_added": 0}
        ucks_contract = None
        if self.ucks_repository_factory:
            from ..ingestion import ToolIngestionService
            ucks_contract = ToolIngestionService(self.ucks_repository_factory()).ingest_mednotegen(generated)
            ucks_import = ucks_contract["counts"]
        if checkpoint:
            checkpoint({"phase": "exported_and_indexed", "resources": len(resources),
                        "clinic_cases": len(generated["clinic_cases"]), "ucks": ucks_import})
        return {
            "tool": "MedNoteGen", "resource_count": len(resources),
            "supported_resource_count": validation["supported_resource_count"],
            "clinic_notes": len(generated["clinic_cases"]),
            "draft_pearl_seeds": len(generated["pearl_seeds"]),
            "ucks_ingestion": ucks_import, "ucks_ingestion_contract": ucks_contract,
            "parse_errors": len(errors),
            "parse_error_samples": errors[:10], "json_file": str(json_path),
            "markdown_directory": str(output / "documents"), "markdown_file_count": len(markdown_paths),
            "safety": "All generated records remain synthetic and unreviewed. Missing fields are not inferred."
        }
