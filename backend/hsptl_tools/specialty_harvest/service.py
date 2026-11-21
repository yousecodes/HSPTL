"""Application service for the Specialty Harvest engine."""
from __future__ import annotations
import contextlib
import io
from pathlib import Path
from typing import Any
from .engine import SPECIALTIES, main as engine_main

class _CheckpointWriter(io.TextIOBase):
    def __init__(self, checkpoint, specialties):
        self.checkpoint = checkpoint
        self.specialties = specialties
        self.buffer = ""
        self.tail: list[str] = []
    def write(self, value: str) -> int:
        self.buffer += value
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip()
            if not line:
                continue
            self.tail.append(line)
            self.tail = self.tail[-100:]
            if self.checkpoint and not self.checkpoint({"phase": "harvesting", "last_message": line,
                                                         "specialties": self.specialties}):
                raise RuntimeError("Specialty Harvest cancelled")
        return len(value)
    def flush(self):
        if self.buffer:
            self.write("\n")

class SpecialtyHarvestService:
    def __init__(self, ucks_repository_factory=None):
        self.ucks_repository_factory = ucks_repository_factory

    def run(self, payload: dict[str, Any], output_dir: str | Path, *, checkpoint=None) -> dict[str, Any]:
        specialties = list(payload.get("specialties") or [])
        if not specialties or any(key not in SPECIALTIES for key in specialties):
            raise ValueError("Choose one or more supported specialties")
        if len(set(specialties)) != len(specialties):
            raise ValueError("Duplicate specialty identifiers are not supported")
        max_cases = max(1, min(int(payload.get("max_cases_per_specialty", 20)), 100))
        profile = str(payload.get("knowledge_profile") or "case_reports")
        allowed_profiles = {"case_reports", "guidelines", "systematic_reviews", "trials", "observational", "clinical_evidence", "all_open_access"}
        if profile not in allowed_profiles:
            raise ValueError("Unsupported clinical knowledge profile")
        year_from, year_to = payload.get("year_from"), payload.get("year_to")
        if year_from and year_to and int(year_from) > int(year_to):
            raise ValueError("Start year must not be after end year")
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        args = ["--only", *specialties, "--sources", "europepmc", "pubmed", "pmc", "crossref", "doaj", "--knowledge-profile", profile, "--per-specialty", str(max_cases),
                "--max-per-source", str(max_cases), "--out", str(output)]
        if year_from: args += ["--year-from", str(int(year_from))]
        if year_to: args += ["--year-to", str(int(year_to))]
        if checkpoint: checkpoint({"phase": "searching_open_access", "specialties": specialties, "output": str(output)})
        writer = _CheckpointWriter(checkpoint, specialties)
        with contextlib.redirect_stdout(writer):
            engine_main(args)
        writer.flush()
        total = sum(1 for item in output.rglob("article.xml"))
        metadata_files = list(output.rglob("meta.json"))
        metadata = len(metadata_files)
        metadata_only = sum(1 for item in metadata_files if not (item.parent / "article.xml").is_file())
        ucks_import = {"seen": 0, "added": 0, "failed": 0}
        ucks_contract = None
        if self.ucks_repository_factory:
            from ..ingestion import ToolIngestionService
            ucks_contract = ToolIngestionService(self.ucks_repository_factory()).ingest_specialty_harvest(str(output))
            ucks_import = ucks_contract["counts"]
        if checkpoint: checkpoint({"phase": "indexed_in_ucks", "ucks": ucks_import})
        return {"tool": "Specialty Harvest", "specialties": specialties,
                "article_count": total, "metadata_count": metadata, "metadata_only_count": metadata_only,
                "ucks_ingestion": ucks_import,
                "ucks_ingestion_contract": ucks_contract,
                "output_directory": str(output), "source_preset": "Europe PMC, PubMed free-full-text search, PMC OA, licence-declared Crossref metadata and DOAJ; full text when available, metadata/abstract fallback otherwise",
                "knowledge_profile": profile,
                "stdout_tail": writer.tail[-25:],
                "safety": "Harvested articles are unreviewed source material. Article-level licence terms must be verified before reuse or redistribution; clinical review is required before case conversion."}
