"""Common tool-to-UCKS ingestion contract."""
from __future__ import annotations
from typing import Any
from ..hsptl_core.ucks_ingestion import ingest_mednotegen_payload, ingest_specialty_harvest

class ToolIngestionService:
    """Route all generator/harvester output through the UCKS ingestion adapters."""
    def __init__(self, repository):
        self.repository = repository
    def ingest_mednotegen(self, payload: dict[str, Any]) -> dict[str, Any]:
        counts = ingest_mednotegen_payload(self.repository, payload)
        return {"channel": "synthea_mednotegen", "status": "completed", "review_status": "harvested",
                "synthetic": True, "counts": counts}
    def ingest_specialty_harvest(self, directory: str) -> dict[str, Any]:
        counts = ingest_specialty_harvest(self.repository, directory)
        return {"channel": "clinical_harvester", "status": "completed", "review_status": "harvested",
                "synthetic": False, "counts": counts}
