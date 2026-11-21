"""Registers HSPTL data-tool application services with the durable job runner."""
from __future__ import annotations
from pathlib import Path
from typing import Any

def register_tool_jobs(runner, *, paths, store) -> None:
    from .mednotegen.service import MedNoteGenService
    from .specialty_harvest.service import SpecialtyHarvestService
    from ..hsptl_core.ucks import UCKSRepository

    mednote = MedNoteGenService(lambda: UCKSRepository(store))
    harvest = SpecialtyHarvestService(lambda: UCKSRepository(store))

    def mednotegen_generate(payload: dict[str, Any], checkpoint):
        output = payload.get("output_dir") or (paths["imports"] / "mednotegen")
        return mednote.generate(payload.get("fhir_dir", ""), output, checkpoint=checkpoint)

    def specialty_harvest(payload: dict[str, Any], checkpoint):
        return harvest.run(payload, paths["imports"] / "specialty_harvest", checkpoint=checkpoint)

    runner.register("mednotegen_generate", mednotegen_generate)
    runner.register("specialty_harvest", specialty_harvest)
