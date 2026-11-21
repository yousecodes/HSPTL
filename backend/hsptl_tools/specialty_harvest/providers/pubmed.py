"""Profile-aware PubMed discovery with metadata-only fallback records."""
from __future__ import annotations
import json
import re
import xml.etree.ElementTree as ET
from ..models import Candidate
from ..common.http import FetchError, ncbi_get
from ..query_builder import pubmed_query_for
from .base import SourceAdapter


def _classify(publication_types: list[str]) -> str:
    text = " ".join(publication_types).lower()
    if "guideline" in text: return "guideline"
    if "systematic review" in text or "meta-analysis" in text: return "systematic_review"
    if "clinical trial" in text or "randomized controlled trial" in text: return "trial"
    if any(term in text for term in ("observational", "cohort", "case-control", "diagnostic test accuracy")):
        return "observational_study"
    if "case reports" in text: return "case_report"
    return "other"


class PubMedSource(SourceAdapter):
    name = "pubmed"
    MAX_RESULTS = 10000
    BATCH_SIZE = 200

    def search(self, key, args):
        query = pubmed_query_for(key, args.year_from, args.year_to,
                                 getattr(args, "knowledge_profile", "case_reports"))
        try:
            first = json.loads(ncbi_get("esearch.fcgi", {"db": "pubmed", "term": query,
                "retmode": "json", "retmax": 0}))
            total = min(int(first.get("esearchresult", {}).get("count", 0)), self.MAX_RESULTS)
        except (FetchError, json.JSONDecodeError, ValueError):
            return
        cap = min(total, int(args.max_per_source or total or self.MAX_RESULTS))
        for start in range(0, cap, self.BATCH_SIZE):
            size = min(self.BATCH_SIZE, cap - start)
            try:
                page = json.loads(ncbi_get("esearch.fcgi", {"db": "pubmed", "term": query,
                    "retmode": "json", "retmax": size, "retstart": start, "sort": "relevance"}))
                ids = page.get("esearchresult", {}).get("idlist", [])
                if not ids: break
                summaries = json.loads(ncbi_get("esummary.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}))
            except (FetchError, json.JSONDecodeError):
                break
            result = summaries.get("result", {})
            abstracts = {}
            try:
                xml_raw = ncbi_get("efetch.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
                root = ET.fromstring(xml_raw)
                for article in root.findall(".//PubmedArticle"):
                    pmid_node = article.find(".//PMID")
                    pmid_value = (pmid_node.text or "").strip() if pmid_node is not None else ""
                    abstract_parts = ["".join(node.itertext()).strip() for node in article.findall(".//Abstract/AbstractText")]
                    abstracts[pmid_value] = "\n\n".join(part for part in abstract_parts if part)
            except (FetchError, ET.ParseError):
                pass
            for pmid in ids:
                item = result.get(pmid) or {}
                title = re.sub(r"\s+", " ", str(item.get("title") or "")).strip().rstrip(".")
                article_ids = item.get("articleids") or []
                id_map = {str(x.get("idtype") or "").lower(): str(x.get("value") or "") for x in article_ids}
                doi = id_map.get("doi", "").lower()
                pmcid = id_map.get("pmc", "")
                pubtypes = item.get("pubtype") or []
                pubdate = str(item.get("pubdate") or "")
                year_match = re.search(r"\b(19|20)\d{2}\b", pubdate)
                yield Candidate(source=self.name, title=title, abstract=abstracts.get(str(pmid), ""), doi=doi,
                    pmcid=pmcid, pmid=str(pmid), year=year_match.group(0) if year_match else "",
                    journal=str(item.get("fulljournalname") or item.get("source") or ""),
                    publication_type=", ".join(map(str, pubtypes)),
                    content_type=_classify(list(map(str, pubtypes))),
                    knowledge_profile=getattr(args, "knowledge_profile", "case_reports"))

    def count(self, key, args):
        try:
            data = json.loads(ncbi_get("esearch.fcgi", {"db": "pubmed",
                "term": pubmed_query_for(key, args.year_from, args.year_to,
                    getattr(args, "knowledge_profile", "case_reports")), "retmode": "json", "retmax": 0}))
            return int(data.get("esearchresult", {}).get("count", 0))
        except (FetchError, json.JSONDecodeError, ValueError):
            return 0
