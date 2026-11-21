"""Adapters that connect existing HSPTL generators/harvesters to UCKS.

Imported records retain source identifiers and remain unreviewed. This module
never asserts that harvested material is licensed for redistribution.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .integrations import parse_jats_article
from .ucks import UCKSRepository


def _source(repo: UCKSRepository, *, name: str, source_type: str,
            locator: str, licence: str = "", reuse_permitted: bool = False) -> str:
    for item in repo.list_sources():
        if item["name"] == name and item["source_type"] == source_type and item["locator"] == locator:
            return item["id"]
    return repo.register_source(name=name, source_type=source_type, locator=locator,
                                licence=licence, reuse_permitted=reuse_permitted)["id"]


def ingest_mednotegen_payload(repo: UCKSRepository, payload: dict[str, Any], *,
                              source_label: str = "Synthea FHIR (synthetic, educational only)") -> dict[str, int]:
    """Import MedNoteGen JSON objects without turning synthetic notes into real cases."""
    source_id = _source(repo, name="MedNoteGen / Synthea", source_type="synthea_mednotegen",
                        locator=source_label, licence="Synthetic educational data")
    added_cases = added_pearls = 0
    for case in payload.get("clinic_cases", []):
        code = str(case.get("case_code") or "Synthetic case")
        narrative = str(case.get("clinical_narrative") or "").strip()
        sections = [f"# {code}", "", "> Synthetic educational case; not a real patient record.", "", narrative]
        encounter = case.get("encounter") or {}
        sections += ["", "## Recorded encounter", f"Date: {encounter.get('date') or 'Not recorded'}", "", "## Observations"]
        observations = case.get("observations") or []
        if not observations:
            sections.append("No encounter-linked observations documented in this source.")
        for obs in observations:
            value = obs.get("value") or {}
            prov = obs.get("provenance") or {}
            sections.append(f"- {obs.get('display') or 'Observation'}: {value.get('value', 'Not recorded')} {value.get('unit') or ''}; source resource {prov.get('resource_id') or 'not recorded'}")
        body = "\n".join(sections).strip()
        if not narrative and not observations:
            continue
        result = repo.ingest_document(
            source_id=source_id, title=code, body=body, content_type="synthetic_case",
            external_id=code, specialty=str(case.get("specialty") or ""),
            publication_date=str(encounter.get("date") or ""),
            provenance={"generator": "MedNoteGen", "source_label": source_label,
                        "synthetic": True, "case_code": code,
                        "source_evidence": case.get("source_evidence") or []},
        )
        added_cases += int(result.get("created", False))
    for index, pearl in enumerate(payload.get("pearl_seeds", []), 1):
        title = str(pearl.get("title") or f"Synthetic Pearl seed {index}")
        body = "\n\n".join(x for x in [str(pearl.get("learning_prompt") or ""),
                                             str(pearl.get("content") or "")] if x).strip()
        if not body:
            continue
        result = repo.ingest_document(
            source_id=source_id, title=title, body=body, content_type="other",
            external_id=str(pearl.get("id") or f"pearl-{index}"),
            provenance={"generator": "MedNoteGen", "synthetic": True,
                        "source_evidence": pearl.get("source_evidence") or [],
                        "draft_learning_seed": True},
        )
        added_pearls += int(result.get("created", False))
    return {"cases_seen": len(payload.get("clinic_cases", [])), "cases_added": added_cases,
            "pearls_seen": len(payload.get("pearl_seeds", [])), "pearls_added": added_pearls}


def _article_text(parsed: dict[str, Any]) -> str:
    parts = [f"# {parsed.get('title') or 'Untitled article'}"]
    if parsed.get("abstract"):
        parts += ["", "## Abstract", parsed["abstract"]]
    for section in parsed.get("sections", []):
        heading = re.sub(r"\s+", " ", str(section.get("heading") or "Article section"))
        text = str(section.get("text") or "").strip()
        if text:
            parts += ["", f"## {heading}", text]
    if len(parts) == 1:
        raise ValueError("JATS article contains no extractable abstract or body sections")
    return "\n\n".join(parts)


def ingest_specialty_harvest(repo: UCKSRepository, directory: str | Path) -> dict[str, int]:
    """Import JATS plus explicitly labelled metadata/abstract records; rights and review remain pending."""
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Specialty Harvest directory does not exist")
    existing_harvester = next((item for item in repo.list_sources()
        if item["name"] == "HSPTL Clinical Knowledge Harvester" and item["source_type"] == "clinical_harvester"), None)
    source_id = (existing_harvester["id"] if existing_harvester else
        _source(repo, name="HSPTL Clinical Knowledge Harvester", source_type="clinical_harvester",
                locator="Europe PMC, PubMed, PMC OA, Crossref and DOAJ", reuse_permitted=False))
    seen = added = failed = full_text = metadata_only = 0
    for meta_path in sorted(root.rglob("meta.json")):
        seen += 1
        try:
            folder = meta_path.parent
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            article_path = folder / "article.xml"
            parsed = parse_jats_article(article_path.read_text(encoding="utf-8", errors="replace")) if article_path.is_file() else {}
            title = str(meta.get("title") or parsed.get("title") or folder.name)
            if article_path.is_file():
                body = _article_text(parsed)
                full_text += 1
            else:
                abstract = str(meta.get("abstractText") or "").strip()
                if not abstract:
                    raise ValueError("metadata-only record has no abstract or article text")
                body = f"# {title}\n\n## Abstract\n\n{abstract}\n\n> Metadata/abstract record only; full text was not acquired."
                metadata_only += 1
            doi = str(meta.get("doi") or "")
            pmcid = str(meta.get("pmcid") or "")
            pmid = str(meta.get("pmid") or "")
            specialty = folder.parent.name if folder.parent != root else ""
            source_url = (f"https://doi.org/{doi}" if doi else
                          f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else
                          f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            licence = str(meta.get("license_uri") or meta.get("license_type") or meta.get("license_text") or "")
            external_id = doi or pmcid or pmid or str(meta_path.relative_to(root))
            result = repo.ingest_document(
                source_id=source_id, title=title, body=body,
                content_type=(meta.get("content_type") if meta.get("content_type") in repo.CONTENT_TYPES else ("case_report" if meta.get("knowledge_profile", "case_reports") == "case_reports" else "other")),
                external_id=external_id, specialty=specialty, publication_date=str(meta.get("year") or ""),
                source_url=source_url, licence=licence,
                provenance={"harvester": "HSPTL Clinical Knowledge Harvester", "metadata": meta,
                    "local_file": str(meta_path.relative_to(root)), "full_text_available": article_path.is_file(),
                    "metadata_only": not article_path.is_file(), "license_review_required": True,
                    "clinical_review_required": True, "publication_type": meta.get("publication_type", ""),
                    "knowledge_profile": meta.get("knowledge_profile", "case_reports"),
                    "identifiers": {"doi": doi, "pmcid": pmcid, "pmid": pmid}},
            )
            added += int(result.get("created", False))
        except (OSError, ValueError, ET.ParseError, json.JSONDecodeError):
            failed += 1
    return {"articles_seen": seen, "articles_added": added, "articles_failed": failed}
