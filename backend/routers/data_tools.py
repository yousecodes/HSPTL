from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..hsptl_core.config import PACKAGE_DIR
from ..runtime import JOBS, PATHS, STORE, TOOL_EXECUTION
from ..hsptl_tools.provider_health import get_provider_health, get_provider_health_history
from ..hsptl_tools.specialty_harvest.catalogue import catalogue as harvester_catalogue
from ..hsptl_core.ucks_monitoring import governance_snapshot

router = APIRouter(prefix="/api/tools", tags=["data-tools"])

class MedNoteGenRequest(BaseModel):
    fhir_dir: str = Field(min_length=3, max_length=1200)
    output_dir: str | None = Field(default=None, max_length=1200)

class SpecialtyHarvestRequest(BaseModel):
    specialties: list[str] = Field(min_length=1, max_length=20)
    max_cases_per_specialty: int = Field(default=20, ge=1, le=100)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    knowledge_profile: Literal["case_reports", "guidelines", "systematic_reviews", "trials", "observational", "clinical_evidence", "all_open_access"] = "case_reports"

@router.get("/status")
def tools_status() -> dict[str, Any]:
    from ..hsptl_core.ucks import UCKSRepository
    ucks = UCKSRepository(STORE)
    return {
        "mednotegen": {"ready": True, "version": "1.1.0", "mode": "deterministic local FHIR transformation", "execution": "in-process service"},
        "specialty_harvest": {"ready": (PACKAGE_DIR / "hsptl_tools" / "specialty_harvest.py").is_file(),
                              "specialty_count": 20, "default_sources": ["Europe PMC"],
                              "mode": "backward-compatible case-report profile", "execution": "in-process service"},
        "clinical_knowledge_harvester": {"ready": True, "profiles": harvester_catalogue()["knowledge_profiles"],
                              "provider_scope": ["Europe PMC full-text open-access records"],
                              "execution": "modular in-process provider pipeline"},
        "tool_architecture": {"service_layer": True, "durable_jobs": True, "ucks_ingestion_contract": True,
                              "backward_compatible_cli": True, "modular_harvester": True,
                              "knowledge_profiles": True, "provider_health_monitoring": True},
        "clinical_knowledge_harvester": harvester_catalogue(),
        "ucks": ucks.stats(),
        "output_root": str(PATHS["imports"]),
        "jobs": TOOL_EXECUTION.list_jobs(20),
    }

@router.post("/mednotegen/generate")
def queue_mednotegen(payload: MedNoteGenRequest) -> dict[str, str]:
    source = Path(payload.fhir_dir).expanduser().resolve()
    if not source.is_dir():
        raise HTTPException(400, "FHIR directory does not exist")
    if not any(source.glob("*.json")):
        raise HTTPException(400, "No FHIR JSON files were found in the selected directory")
    output = Path(payload.output_dir).expanduser().resolve() if payload.output_dir else (PATHS["imports"] / "mednotegen")
    job_id = TOOL_EXECUTION.enqueue("mednotegen_generate", {"fhir_dir": str(source), "output_dir": str(output)})
    return {"id": job_id, "status": "queued"}

@router.post("/specialty-harvest/run")
def queue_specialty_harvest(payload: SpecialtyHarvestRequest) -> dict[str, str]:
    script = PACKAGE_DIR / "hsptl_tools" / "specialty_harvest.py"
    if not script.is_file():
        raise HTTPException(503, "Specialty Harvest script is missing")
    try:
        from ..hsptl_tools.specialty_harvest import SPECIALTIES
        keys = set(SPECIALTIES)
    except Exception as exc:
        raise HTTPException(500, "Could not inspect Specialty Harvest specialties") from exc
    if len(set(payload.specialties)) != len(payload.specialties) or any(key not in keys for key in payload.specialties):
        raise HTTPException(400, "One or more specialty identifiers are not supported")
    if payload.year_from and payload.year_to and payload.year_from > payload.year_to:
        raise HTTPException(400, "Start year must not be after end year")
    job_id = TOOL_EXECUTION.enqueue("specialty_harvest", payload.model_dump())
    return {"id": job_id, "status": "queued"}

@router.post("/jobs/{job_id}/run")
def run_tool_job(job_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        job = TOOL_EXECUTION.get_job(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        if job.get("status") == "failed":
            STORE.update_job(job_id, status="queued", error_code="")
        if job.get("status") not in {"queued", "failed"}:
            raise HTTPException(409, "Only a queued or failed job can be run")
        background_tasks.add_task(TOOL_EXECUTION.run_once, job_id)
        updated = TOOL_EXECUTION.get_job(job_id)
        return {"ran": True, "job": updated}
    except KeyError as exc:
        raise HTTPException(404, "Job not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@router.get("/monitoring")
def tools_monitoring() -> dict[str, Any]:
    from ..hsptl_core.ucks import UCKSRepository
    repository = UCKSRepository(STORE)
    jobs = TOOL_EXECUTION.list_jobs(100)
    counts: dict[str, int] = {}
    for job in jobs:
        status = str(job.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {"jobs": jobs, "job_counts": counts, "ucks": repository.stats(),
            "sources": repository.list_sources(),
            "ingestion_channels": ["clinical_harvester", "synthea_mednotegen", "external_import", "online_feed"]}

@router.post("/jobs/{job_id}/cancel")
def cancel_tool_job(job_id: str) -> dict[str, bool]:
    try:
        return {"cancel_requested": TOOL_EXECUTION.cancel(job_id)}
    except KeyError as exc:
        raise HTTPException(404, "Job not found") from exc

@router.get("/harvested-cases")
def harvested_cases(specialty: str | None = None, limit: int = 100) -> dict[str, Any]:
    root = PATHS["imports"] / "specialty_harvest"
    if not root.is_dir():
        return {"count": 0, "items": []}
    selected = [root / specialty] if specialty else [p for p in root.iterdir() if p.is_dir()]
    items = []
    for folder in selected:
        if not folder.is_dir() or folder.parent != root:
            continue
        for metadata_file in folder.glob("*/meta.json"):
            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            pmcid = metadata.get("pmcid") or ""
            doi = metadata.get("doi") or ""
            pmid = metadata.get("pmid") or ""
            url = (f"https://europepmc.org/articles/{pmcid}" if pmcid else
                   (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else
                    (f"https://doi.org/{doi}" if doi else "")))
            items.append({
                "specialty": folder.name, "title": metadata.get("title") or metadata_file.parent.name,
                "year": metadata.get("year") or "", "journal": metadata.get("journal") or "",
                "pmcid": pmcid, "pmid": pmid, "doi": doi, "url": url,
                "source": metadata.get("discovered_via", ""),
                "content_type": metadata.get("content_type", "other"),
                "knowledge_profile": metadata.get("knowledge_profile", "case_reports"),
                "full_text_available": bool(metadata.get("full_text_available", (metadata_file.parent / "article.xml").is_file())),
                "license_status": metadata.get("license_status", "unknown_requires_manual_review"),
                "license_uri": metadata.get("license_uri", ""),
                "review_status": metadata.get("review_status", "harvested_unreviewed"),
            })
    items.sort(key=lambda item: (item["specialty"], item["year"], item["title"]), reverse=True)
    return {"count": len(items), "items": items[:max(1, min(limit, 500))]}


@router.get("/harvester/catalogue")
def clinical_harvester_catalogue():
    return harvester_catalogue()

@router.get("/providers/health")
def providers_health(probe: bool = False):
    """Return cached provider health; probe=true performs bounded HTTPS checks."""
    return get_provider_health(STORE, probe=probe)

@router.get("/providers/health/history")
def providers_health_history(provider_id: str = "", limit: int = 50):
    try:
        return get_provider_health_history(STORE, provider_id=provider_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.get("/ucks/governance")
def ucks_governance(limit: int = 20):
    from ..hsptl_core.ucks import UCKSRepository
    return governance_snapshot(STORE, UCKSRepository(STORE), limit=limit)
