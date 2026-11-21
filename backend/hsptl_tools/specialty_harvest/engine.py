#!/usr/bin/env python3
"""
Clinical Knowledge Harvester - discover specialty-relevant open-access clinical evidence.

Supports case reports, guidelines, systematic reviews, trials and observational
studies through evidence-specific profiles. Legacy exam-curated case workflows remain available.

Default knowledge profile: case_reports; default source preset: exam.
"""
import argparse
import hashlib
import html as _html_mod
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DOAJ = "https://doaj.org/api/search/articles"
CROSSREF = "https://api.crossref.org/works"
UNPAYWALL = "https://api.unpaywall.org/v2"
UA = "Mozilla/5.0 (compatible; specialty-harvester/9.2; personal study use)"
DATA_HOME = Path(os.environ.get("HSPTL_DATA_HOME") or os.environ.get("HSPTL_HOME") or (Path.home() / "HSPTL")).expanduser()
CACHE_DIR = DATA_HOME / "cache"
UNPAYWALL_CACHE_FILE = CACHE_DIR / "specialty_harvest_unpaywall.json"
METADATA_CACHE_FILE = CACHE_DIR / "specialty_harvest_epmc_metadata.json"

BASE = 'PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y AND HAS_FT:y'

from .catalogue import (EXCLUDE_KEYWORDS, GLOBAL_EXCLUDES, OPHTH_VERY_SPECIFIC, OPHTH_SPECIFIC,
                       _OPHTH_VERY, _OPHTH_SPEC, SPECIALTIES, CASE_REPORT_JOURNALS,
                       EXAM_SOURCE_CONFIGS, HINDAWI_JOURNAL_CODES, IMPORTANCE_PATTERNS)

from .common.http import FetchError, RateLimiter as _RateLimiter, epmc_get, http_get, ncbi_get, configure_ncbi_api_key
from .models import Candidate
from .providers.base import SourceAdapter

# ================================================================ FILTERS


# ================================================================ SPECIALTIES

# ================================================================ CASE-REPORT JOURNALS

# ================================================================ EXAM SOURCE CONFIGS

# ================================================================ HTTP




NCBI_API_KEY = ""  # retained for compatibility; active transport state lives in common.http








# ================================================================ CACHES
_UP_CACHE = {}
_UP_CACHE_LOCK = threading.Lock()
_META_CACHE = {}
_META_CACHE_LOCK = threading.Lock()

from .common.cache import load_caches as _cache_load, save_caches as _cache_save, unpaywall_resolve as _cache_unpaywall

def _load_caches():
    _cache_load(UNPAYWALL_CACHE_FILE, METADATA_CACHE_FILE,
                (_UP_CACHE, _UP_CACHE_LOCK), (_META_CACHE, _META_CACHE_LOCK))

def _save_caches():
    _cache_save(CACHE_DIR, UNPAYWALL_CACHE_FILE, METADATA_CACHE_FILE,
                (_UP_CACHE, _UP_CACHE_LOCK), (_META_CACHE, _META_CACHE_LOCK))

def unpaywall_resolve(doi, email):
    return _cache_unpaywall(doi, email, UNPAYWALL, (_UP_CACHE, _UP_CACHE_LOCK), http_get)








# ================================================================ HTML HELPERS






CANONICAL_MAP = [
    (re.compile(r"presentation|clinical presentation|case presentation|case report|case summary", re.I), "presentation"),
    (re.compile(r"history|medical history|past medical", re.I), "history"),
    (re.compile(r"examination|physical exam|ocular exam|clinical examination|exam", re.I), "exam"),
    (re.compile(r"investigation|work-?up|laborator|imaging|diagnostic test|findings|radiographic", re.I), "workup"),
    (re.compile(r"diagnosis|final diagnosis|definitive diagnosis|pathology|impression", re.I), "dx"),
    (re.compile(r"discussion|comment|learning|key points|pearls|teaching", re.I), "discussion"),
    (re.compile(r"treatment|management|therapy|intervention|follow-?up|outcome", re.I), "tx"),
]




_XML_ESCAPE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})






# ================================================================ CANDIDATE

# ================================================================ EXAM SOURCE
def _fetch_page(url):
    try:
        return http_get(url, timeout=30).decode("utf-8", "replace")
    except FetchError:
        return ""






# ================================================================ BROAD SOURCES










# ================================================================ QUERY BUILDERS






_PMC_BROAD = False
_PMC_DEFAULT_YEARS = 5








# ================================================================ REGISTRY







# ================================================================ VALIDITY










# ================================================================ HYDRATION




# ================================================================ DOWNLOAD

































from .licensing import extract_jats_license








def _build_exam_jats(c):
    title = c.title or "Exam Case"
    sections = c.sections or [("presentation", [c.abstract or c.title])]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<article>", "  <front>",
             "    <journal-meta>", "      <journal-title-group>",
             "        <journal-title>" + _xml_escape(c.journal or "Exam Case") + "</journal-title>",
             "      </journal-title-group>", "    </journal-meta>", "    <article-meta>",
             "      <title-group><article-title>" + _xml_escape(title) + "</article-title></title-group>",
             "    </article-meta>", "  </front>", "  <body>"]
    for sec_title, paras in sections:
        lines.append("    <sec><title>" + _xml_escape(sec_title) + "</title>")
        for p in paras:
            lines.append("      <p>" + _xml_escape(p) + "</p>")
        lines.append("    </sec>")
    lines += ["  </body>", "</article>"]
    return "\n".join(lines).encode("utf-8")


# ================================================================ HARVEST










# ================================================================ MAIN
# Decomposed clinical harvester services. These imports occur after their shared
# configuration and transport primitives have been initialised.
from .parsers import _strip_tags, _parse_meta, _split_by_headings, _map_sections, _xml_escape, _html_to_jats
from .query_builder import _keyword_terms, specialty_clause, query_for, pmc_query_for, doaj_query_for, crossref_query_for
from .specialty_filters import (_has_very_specific, _count_specific, _positive_ophthalmology,
                                is_valid_specialty_case, _title_matches_specialty)

# Provider implementations live in independent modules. Shared transport, query and
# parsing primitives above remain available as compatibility services.
from .acquisition import (_epmc_lookup, hydrate_candidates, _try_pmc_html, resolve_pmcid_to_jats,
                         _looks_like_jats, _is_cloudflare_challenge, _parse_hindawi_doi,
                         _crossref_journal_name, _norm_journal_name, _get_hindawi_journal_codes,
                         _try_hindawi_constructed, _doi_to_pmcid, convert_doi_to_jats,
                         download_candidate, _efetch_batch, download_pmc_batch)
from .providers.exam_curated import ExamCuratedSource
from .providers.europe_pmc import EuropePMCSource
from .providers.pmc_oa import PMCOASource
from .providers.doaj import DOAJSource
from .providers.crossref import CrossrefSource
from .providers.pubmed import PubMedSource
from .providers.journal_catalogue import JournalSource
from .providers.exam_title import ExamTitleSource


SOURCES = {
    "exam": ExamCuratedSource(),
    "examtitle": ExamTitleSource(),
    "europepmc": EuropePMCSource(),
    "pubmed": PubMedSource(),
    "pmc": PMCOASource(),
    "doaj": DOAJSource(),
    "crossref": CrossrefSource(),
    "journals": JournalSource(),
}
SOURCE_PRESETS = {
    "exam": ["exam", "examtitle", "journals"],
    "minimal": ["europepmc", "journals"],
    "wide": ["europepmc", "pubmed", "journals", "crossref"],
    "all": ["europepmc", "pubmed", "pmc", "journals", "doaj", "crossref", "exam", "examtitle"],
}

from .pipeline import existing_ids, _importance_score, _has_exam_signal, harvest_specialty, _parallel_search




if __name__ == "__main__":
    main()


def main(argv=None):
    """Backward-compatible CLI wrapper."""
    from .cli import main as run
    return run(argv)
