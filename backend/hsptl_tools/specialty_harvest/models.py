"""Typed records passed between clinical knowledge provider adapters."""
from __future__ import annotations
import hashlib
import re
from dataclasses import dataclass, field

@dataclass
class Candidate:
    source: str
    title: str = ""
    abstract: str = ""
    doi: str = ""
    pmcid: str = ""
    pmid: str = ""
    year: str = ""
    journal: str = ""
    publication_type: str = ""
    license_uri: str = ""
    content_type: str = "case_report"
    knowledge_profile: str = "case_reports"
    sections: list = field(default_factory=list)

    def dedup_key(self):
        if self.pmcid:
            return "pmc:" + self.pmcid.lower()
        if self.doi:
            return "doi:" + self.doi.lower()
        if self.pmid:
            return "pmid:" + self.pmid.lower()
        if self.source.startswith("exam:"):
            h = hashlib.sha1((self.title or "").encode()).hexdigest()[:12]
            return "exam:" + h
        return "title:" + re.sub(r"\W+", "", (self.title or "").lower())[:120]

    def folder_name(self):
        if self.pmcid:
            return self.pmcid
        if self.doi:
            return "doi_" + re.sub(r"[^a-z0-9]+", "_", self.doi.lower()).strip("_")
        if self.pmid:
            return "pmid_" + self.pmid
        if self.source.startswith("exam:"):
            h = hashlib.sha1((self.title or "").encode()).hexdigest()[:12]
            return "exam_" + h
        return None

