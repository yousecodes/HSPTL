"""Metadata-first public research connectors for UCKS.

Managed public-source profiles ingest automatically and receive a technical
``machine_screened`` status. This checks record integrity/provenance only; it is
not clinical validation and never grants reuse rights. Non-managed connectors
retain the ordinary ``harvested`` status.
"""
from __future__ import annotations

import json
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

CONNECTORS = {"europe_pmc", "pubmed", "crossref", "clinicaltrials_gov"}
MAX_RESULTS = 100
MAX_RESPONSE_BYTES = 8_000_000
# Conservative allow-list: no NC/ND or unknown licences are fetched as reusable full text.
FULLTEXT_LICENCES = {"cc0", "cc-by", "cc-by-4.0", "cc-by-sa", "cc-by-sa-4.0"}
TIMEOUT = (5, 25)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_text(x) for x in value if x is not None)
    if isinstance(value, dict):
        return " ".join(_text(v) for v in value.values() if v is not None)
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_true_flag(value: Any) -> bool:
    """Normalise provider booleans, including Europe PMC's Y/N strings."""
    if isinstance(value, bool):
        return value
    return _text(value).casefold() in {"1", "true", "yes", "y"}


def _get(url: str, params: dict[str, Any], *, session=requests) -> Any:
    response = session.get(url, params=params, timeout=TIMEOUT,
                           headers={"User-Agent": "HSPTL-UCKS/3.0 (clinical knowledge metadata importer)"},
                           allow_redirects=False, stream=True)
    if 300 <= response.status_code < 400:
        raise ValueError("External connector redirects are not followed")
    response.raise_for_status()
    declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    if declared and int(declared) > MAX_RESPONSE_BYTES:
        raise ValueError("Connector response exceeds 8 MB limit")
    chunks, size = [], 0
    for chunk in response.iter_content(65536):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise ValueError("Connector response exceeds 8 MB limit")
        chunks.append(chunk)
    raw = b"".join(chunks)
    return raw


def _date(value: str) -> str:
    value = str(value or "")
    match = re.search(r"(19|20)\d{2}(-\d{2}(-\d{2})?)?", value)
    return match.group(0) if match else ""


def _europe_pmc(query: str, limit: int, session) -> list[dict[str, Any]]:
    raw = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {
        "query": query, "format": "json", "pageSize": limit, "resultType": "core"}, session=session)
    data = json.loads(raw)
    out = []
    for r in data.get("resultList", {}).get("result", []):
        pmid, pmcid, doi = _text(r.get("pmid")), _text(r.get("pmcid")), _text(r.get("doi"))
        ext = f"PMC:{pmcid}" if pmcid else (f"PMID:{pmid}" if pmid else f"DOI:{doi}")
        abstract = _text(r.get("abstractText"))
        body = "\n\n".join(x for x in [f"# {_text(r.get('title'))}", "## Abstract", abstract] if x)
        if not body.strip("# \n"):
            body = f"# {_text(r.get('title'))}\n\nBibliographic metadata record; abstract not supplied by source."
        out.append({"external_id": ext, "title": _text(r.get("title")) or ext,
                    "body": body, "content_type": "systematic_review" if "systematic review" in _text(r.get("pubTypeList")).lower() else "other",
                    "publication_date": _date(r.get("firstPublicationDate") or r.get("pubYear")),
                    "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else (f"https://europepmc.org/articles/{pmcid}" if pmcid else (f"https://doi.org/{doi}" if doi else "")),
                    "licence": _text(r.get("license")), "provenance": {"connector": "Europe PMC", "pmid": pmid, "pmcid": pmcid, "doi": doi, "publication_types": _text(r.get("pubTypeList")), "publisher_lifecycle_signal": ("retracted" if "retracted publication" in _text(r.get("pubTypeList")).casefold() else ""), "is_open_access": _is_true_flag(r.get("isOpenAccess")), "rights_review_required": True}})
    return out



def _licence_key(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    aliases = {"cc-by-4": "cc-by-4.0", "cc-by-4-0": "cc-by-4.0",
               "cc-by-sa-4": "cc-by-sa-4.0", "cc-by-sa-4-0": "cc-by-sa-4.0",
               "cc-zero": "cc0", "creative-commons-zero": "cc0"}
    return aliases.get(value, value)


def _europe_pmc_fulltext(record: dict[str, Any], session) -> tuple[str, dict[str, Any]]:
    """Fetch PMC XML only when Europe PMC explicitly marks an allow-listed licence."""
    provenance = dict(record.get("provenance") or {})
    pmcid = _text(provenance.get("pmcid"))
    licence = _licence_key(_text(record.get("licence")))
    if not pmcid or not provenance.get("is_open_access") or licence not in FULLTEXT_LICENCES:
        return "", {"full_text_status": "not_fetched_rights_or_identifier"}
    safe_id = re.sub(r"[^A-Za-z0-9]+", "", pmcid)
    if not safe_id.startswith("PMC"):
        return "", {"full_text_status": "invalid_pmcid"}
    raw = _get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{safe_id}/fullTextXML", {}, session=session)
    root = ET.fromstring(raw)
    sections: list[str] = []
    for sec in root.findall(".//body//sec"):
        heading = _text(sec.findtext("title"))
        paragraphs = [_text(" ".join(node.itertext())) for node in sec.findall("./p")]
        content = "\n\n".join(x for x in paragraphs if x)
        if content:
            sections.append((f"## {heading}\n\n" if heading else "") + content)
    if not sections:
        paragraphs = [_text(" ".join(node.itertext())) for node in root.findall(".//body//p")]
        sections = [x for x in paragraphs if x]
    body = "\n\n".join([f"# {record.get('title', '')}", *sections]).strip()
    if len(body) < 300:
        return "", {"full_text_status": "source_xml_had_insufficient_body_text"}
    return body, {"full_text_status": "fetched", "full_text_format": "JATS-XML",
                  "full_text_licence": _text(record.get("licence")), "full_text_pmcid": safe_id}


def _pubmed(query: str, limit: int, session) -> list[dict[str, Any]]:
    search = json.loads(_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", {
        "db": "pubmed", "term": query, "retmode": "json", "retmax": limit, "sort": "date"}, session=session))
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    raw = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", {
        "db": "pubmed", "id": ",".join(ids), "retmode": "xml"}, session=session)
    root = ET.fromstring(raw)
    out = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.findtext(".//PMID"))
        title = _text(" ".join(article.find(".//ArticleTitle").itertext())) if article.find(".//ArticleTitle") is not None else f"PubMed {pmid}"
        abstract = " ".join(_text(" ".join(x.itertext())) for x in article.findall(".//Abstract/AbstractText"))
        date = _text(article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate"))
        body = f"# {title}\n\n## Abstract\n{abstract}" if abstract else f"# {title}\n\nBibliographic metadata record; abstract not supplied by source."
        out.append({"external_id": f"PMID:{pmid}", "title": title, "body": body,
                    "content_type": "other", "publication_date": _date(date),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "licence": "",
                    "provenance": {"connector": "NCBI PubMed E-utilities", "pmid": pmid, "rights_review_required": True}})
    return out


def _crossref(query: str, limit: int, session) -> list[dict[str, Any]]:
    raw = _get("https://api.crossref.org/works", {"query": query, "rows": limit,
               "select": "DOI,title,author,published,published-print,published-online,type,URL,license,relation"}, session=session)
    data = json.loads(raw).get("message", {}).get("items", [])
    out = []
    for r in data:
        doi = _text(r.get("DOI")); title = _text(r.get("title")) or doi
        date_parts = (r.get("published-online") or r.get("published-print") or r.get("published") or {}).get("date-parts", [[]])[0]
        date = "-".join(str(x).zfill(2) if i else str(x) for i, x in enumerate(date_parts[:3]))
        authors = _text([a.get("family", "") + (", " + a.get("given", "") if a.get("given") else "") for a in r.get("author", [])])
        body = f"# {title}\n\nDOI: {doi}\n\nAuthors: {authors or 'Not supplied'}\n\nCrossref bibliographic metadata; abstract not supplied by this connector."
        out.append({"external_id": f"DOI:{doi}", "title": title, "body": body, "content_type": "other",
                    "publication_date": _date(date), "url": _text(r.get("URL")) or (f"https://doi.org/{doi}" if doi else ""),
                    "licence": "", "provenance": {"connector": "Crossref REST API", "doi": doi, "work_type": _text(r.get("type")), "licence_metadata": r.get("license", []), "relation_metadata": r.get("relation", {}), "rights_review_required": True}})
    return out


def _clinicaltrials(query: str, limit: int, session) -> list[dict[str, Any]]:
    raw = _get("https://clinicaltrials.gov/api/v2/studies", {"query.term": query, "pageSize": limit,
               "format": "json", "countTotal": "false"}, session=session)
    studies = json.loads(raw).get("studies", [])
    out = []
    for item in studies:
        p = item.get("protocolSection", {}); ident = p.get("identificationModule", {}); desc = p.get("descriptionModule", {})
        status = p.get("statusModule", {}); design = p.get("designModule", {})
        nct = _text(ident.get("nctId")); title = _text(ident.get("briefTitle") or ident.get("officialTitle"))
        summary = _text(desc.get("briefSummary")); detailed = _text(desc.get("detailedDescription"))
        body = f"# {title}\n\nRegistry identifier: {nct}\n\n## Brief summary\n{summary}\n\n## Detailed description\n{detailed}\n\n## Registry status\n{_text(status.get('overallStatus'))}\n\n## Study design\n{_text(design)}"
        out.append({"external_id": nct, "title": title or nct, "body": body, "content_type": "trial",
                    "publication_date": _date(status.get("studyFirstSubmitDate")), "url": f"https://clinicaltrials.gov/study/{nct}",
                    "licence": "", "provenance": {"connector": "ClinicalTrials.gov API v2", "nct_id": nct,
                    "overall_status": _text(status.get("overallStatus")), "last_update_submitted": _text(status.get("studyFirstPostDateStruct")),
                    "results_first_posted": _text(status.get("resultsFirstPostDateStruct")), "rights_review_required": True}})
    return out


_FETCHERS = {"europe_pmc": _europe_pmc, "pubmed": _pubmed, "crossref": _crossref, "clinicaltrials_gov": _clinicaltrials}
_DEFAULT_FETCHERS = dict(_FETCHERS)


def _europe_pmc_page(query: str, limit: int, session, cursor: str = "") -> dict[str, Any]:
    mark = cursor or "*"
    data = json.loads(_get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {
        "query": query, "format": "json", "pageSize": limit, "resultType": "core",
        "sort_date": "y", "cursorMark": mark}, session=session))
    records = _normalise_europe_pmc(data)
    next_mark = _text(data.get("nextCursorMark"))
    total = int(data.get("hitCount", 0) or 0)
    return {"records": records, "next_cursor": next_mark if next_mark and next_mark != mark else "",
            "total_records": total, "complete": not bool(next_mark and next_mark != mark)}


def _normalise_europe_pmc(data: dict[str, Any]) -> list[dict[str, Any]]:
    # Shared normaliser keeps the legacy one-page adapter and cursor adapter consistent.
    out = []
    for r in data.get("resultList", {}).get("result", []):
        pmid, pmcid, doi = _text(r.get("pmid")), _text(r.get("pmcid")), _text(r.get("doi"))
        ext = f"PMC:{pmcid}" if pmcid else (f"PMID:{pmid}" if pmid else f"DOI:{doi}")
        abstract = _text(r.get("abstractText"))
        body = "\n\n".join(x for x in [f"# {_text(r.get('title'))}", "## Abstract", abstract] if x)
        if not body.strip("# \n"):
            body = f"# {_text(r.get('title'))}\n\nBibliographic metadata record; abstract not supplied by source."
        out.append({"external_id": ext, "title": _text(r.get("title")) or ext,
            "body": body, "content_type": "systematic_review" if "systematic review" in _text(r.get("pubTypeList")).lower() else "other",
            "publication_date": _date(r.get("firstPublicationDate") or r.get("pubYear")),
            "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else (f"https://europepmc.org/articles/{pmcid}" if pmcid else (f"https://doi.org/{doi}" if doi else "")),
            "licence": _text(r.get("license")), "provenance": {"connector": "Europe PMC", "pmid": pmid, "pmcid": pmcid, "doi": doi, "publication_types": _text(r.get("pubTypeList")), "publisher_lifecycle_signal": ("retracted" if "retracted publication" in _text(r.get("pubTypeList")).casefold() else ""), "is_open_access": _is_true_flag(r.get("isOpenAccess")), "rights_review_required": True}})
    return out


def _pubmed_page(query: str, limit: int, session, cursor: str = "") -> dict[str, Any]:
    offset = max(0, int(cursor or 0))
    search = json.loads(_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", {
        "db": "pubmed", "term": query, "retmode": "json", "retmax": limit, "retstart": offset, "sort": "date"}, session=session))
    result = search.get("esearchresult", {})
    ids = result.get("idlist", [])
    total = int(result.get("count", 0) or 0)
    records = []
    if ids:
        root = ET.fromstring(_get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", {
            "db": "pubmed", "id": ",".join(ids), "retmode": "xml"}, session=session))
        for article in root.findall(".//PubmedArticle"):
            pmid = _text(article.findtext(".//PMID"))
            title_node = article.find(".//ArticleTitle")
            title = _text(" ".join(title_node.itertext())) if title_node is not None else f"PubMed {pmid}"
            abstract = " ".join(_text(" ".join(x.itertext())) for x in article.findall(".//Abstract/AbstractText"))
            date = _text(article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate"))
            body = f"# {title}\n\n## Abstract\n{abstract}" if abstract else f"# {title}\n\nBibliographic metadata record; abstract not supplied by source."
            publication_types = [ _text(" ".join(node.itertext())) for node in article.findall(".//PublicationTypeList/PublicationType") ]
            pub_types_text = " ".join(publication_types).casefold()
            records.append({"external_id": f"PMID:{pmid}", "title": title, "body": body, "content_type": "other",
                "publication_date": _date(date), "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "licence": "",
                "provenance": {"connector": "NCBI PubMed E-utilities", "pmid": pmid,
                    "publication_types": publication_types,
                    "publisher_lifecycle_signal": ("retracted" if "retracted publication" in pub_types_text else ""),
                    "rights_review_required": True}})
    next_offset = offset + len(ids)
    complete = not ids or next_offset >= total
    return {"records": records, "next_cursor": "" if complete else str(next_offset), "total_records": total, "complete": complete}


def _crossref_page(query: str, limit: int, session, cursor: str = "") -> dict[str, Any]:
    offset = max(0, int(cursor or 0))
    date_tokens = {}
    for key in ("from-pub-date", "until-pub-date"):
        match = re.search(rf"\b{key}:(\d{{4}}-\d{{2}}-\d{{2}})", query)
        if match:
            date_tokens[key] = match.group(1)
    search_query = re.sub(r"\b(?:from-pub-date|until-pub-date):\d{4}-\d{2}-\d{2}", "", query).strip()
    params = {"query": search_query, "rows": limit, "offset": offset,
        "select": "DOI,title,author,published,published-print,published-online,type,URL,license,relation",
        "sort": "published", "order": "desc"}
    if date_tokens:
        filters = []
        if "from-pub-date" in date_tokens:
            filters.append("from-pub-date:" + date_tokens["from-pub-date"])
        if "until-pub-date" in date_tokens:
            filters.append("until-pub-date:" + date_tokens["until-pub-date"])
        params["filter"] = ",".join(filters)
    raw = _get("https://api.crossref.org/works", params, session=session)
    message = json.loads(raw).get("message", {})
    items = message.get("items", [])
    records = _normalise_crossref(items)
    total = int(message.get("total-results", 0) or 0)
    next_offset = offset + len(items)
    complete = not items or next_offset >= total
    return {"records": records, "next_cursor": "" if complete else str(next_offset), "total_records": total, "complete": complete}


def _normalise_crossref(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in items:
        doi = _text(r.get("DOI")); title = _text(r.get("title")) or doi
        date_parts = (r.get("published-online") or r.get("published-print") or r.get("published") or {}).get("date-parts", [[]])[0]
        date = "-".join(str(x).zfill(2) if i else str(x) for i, x in enumerate(date_parts[:3]))
        authors = _text([a.get("family", "") + (", " + a.get("given", "") if a.get("given") else "") for a in r.get("author", [])])
        body = f"# {title}\n\nDOI: {doi}\n\nAuthors: {authors or 'Not supplied'}\n\nCrossref bibliographic metadata; abstract not supplied by this connector."
        out.append({"external_id": f"DOI:{doi}", "title": title, "body": body, "content_type": "other",
            "publication_date": _date(date), "url": _text(r.get("URL")) or (f"https://doi.org/{doi}" if doi else ""),
            "licence": "", "provenance": {"connector": "Crossref REST API", "doi": doi, "work_type": _text(r.get("type")), "licence_metadata": r.get("license", []), "relation_metadata": r.get("relation", {}), "rights_review_required": True}})
    return out


def _clinicaltrials_page(query: str, limit: int, session, cursor: str = "") -> dict[str, Any]:
    params = {"query.term": query, "pageSize": limit, "format": "json", "countTotal": "true",
              "sort": "LastUpdatePostDate:desc"}
    if cursor:
        params["pageToken"] = cursor
    data = json.loads(_get("https://clinicaltrials.gov/api/v2/studies", params, session=session))
    records = []
    for item in data.get("studies", []):
        p = item.get("protocolSection", {}); ident = p.get("identificationModule", {}); desc = p.get("descriptionModule", {})
        status = p.get("statusModule", {}); design = p.get("designModule", {})
        nct = _text(ident.get("nctId")); title = _text(ident.get("briefTitle") or ident.get("officialTitle"))
        summary = _text(desc.get("briefSummary")); detailed = _text(desc.get("detailedDescription"))
        body = f"# {title}\n\nRegistry identifier: {nct}\n\n## Brief summary\n{summary}\n\n## Detailed description\n{detailed}\n\n## Registry status\n{_text(status.get('overallStatus'))}\n\n## Study design\n{_text(design)}"
        records.append({"external_id": nct, "title": title or nct, "body": body, "content_type": "trial",
            "publication_date": _date(status.get("studyFirstSubmitDate")), "url": f"https://clinicaltrials.gov/study/{nct}", "licence": "",
            "provenance": {"connector": "ClinicalTrials.gov API v2", "nct_id": nct, "overall_status": _text(status.get("overallStatus")),
                "last_update_submitted": _text(status.get("studyFirstPostDateStruct")), "results_first_posted": _text(status.get("resultsFirstPostDateStruct")), "rights_review_required": True}})
    next_token = _text(data.get("nextPageToken"))
    total = int(data.get("totalCount", 0) or 0)
    return {"records": records, "next_cursor": next_token, "total_records": total, "complete": not bool(next_token)}


_PAGE_FETCHERS = {"europe_pmc": _europe_pmc_page, "pubmed": _pubmed_page,
                  "crossref": _crossref_page, "clinicaltrials_gov": _clinicaltrials_page}


def _ensure_connector_tables(repo) -> None:
    with repo.store.transaction() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ucks_connector_runs (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES ucks_sources(id),
            connector TEXT NOT NULL, query_text TEXT NOT NULL, outcome TEXT NOT NULL,
            records_seen INTEGER NOT NULL DEFAULT 0, records_added INTEGER NOT NULL DEFAULT 0,
            error TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_connector_runs ON ucks_connector_runs(source_id,started_at)")


def list_connector_runs(repo, source_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
    _ensure_connector_tables(repo)
    with repo.store.transaction() as conn:
        rows = conn.execute("SELECT * FROM ucks_connector_runs WHERE (?='' OR source_id=?) ORDER BY started_at DESC LIMIT ?",
                            (source_id, source_id, max(1, min(int(limit), 200)))).fetchall()
    return [dict(row) for row in rows]


def _ensure_connector_checkpoints(repo) -> None:
    with repo.store.transaction() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ucks_connector_checkpoints (
            source_id TEXT NOT NULL REFERENCES ucks_sources(id), query_hash TEXT NOT NULL,
            connector TEXT NOT NULL, cursor TEXT NOT NULL DEFAULT '', sync_runs_completed INTEGER NOT NULL DEFAULT 0,
            records_seen INTEGER NOT NULL DEFAULT 0, records_added INTEGER NOT NULL DEFAULT 0,
            last_external_id TEXT NOT NULL DEFAULT '', last_success TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL, PRIMARY KEY(source_id, query_hash))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_connector_checkpoint_updated ON ucks_connector_checkpoints(updated_at)")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ucks_connector_checkpoints)").fetchall()}
        for name, declaration in (("total_records", "INTEGER NOT NULL DEFAULT 0"),
                                  ("pages_completed", "INTEGER NOT NULL DEFAULT 0"),
                                  ("pagination_complete", "INTEGER NOT NULL DEFAULT 0"),
                                  ("page_size", "INTEGER NOT NULL DEFAULT 0"),
                                  ("last_page_at", "TEXT NOT NULL DEFAULT ''")):
            if name not in columns:
                conn.execute(f"ALTER TABLE ucks_connector_checkpoints ADD COLUMN {name} {declaration}")


def get_connector_checkpoint(repo, source_id: str, query: str) -> dict[str, Any] | None:
    _ensure_connector_checkpoints(repo)
    key = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT * FROM ucks_connector_checkpoints WHERE source_id=? AND query_hash=?", (source_id, key)).fetchone()
    return dict(row) if row else None


def reset_connector_checkpoint(repo, source_id: str, query: str) -> dict[str, Any]:
    _ensure_connector_checkpoints(repo)
    key = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with repo.store.transaction() as conn:
        conn.execute("DELETE FROM ucks_connector_checkpoints WHERE source_id=? AND query_hash=?", (source_id, key))
    return {"source_id": source_id, "query_hash": key, "cursor": "", "sync_runs_completed": 0, "updated_at": now}



def _ensure_identifier_table(repo) -> None:
    with repo.store.transaction() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ucks_document_identifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
            source_id TEXT NOT NULL REFERENCES ucks_sources(id), identifier_type TEXT NOT NULL,
            identifier_value TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(document_id, identifier_type, identifier_value))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_identifier_lookup ON ucks_document_identifiers(identifier_type,identifier_value)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_identifier_document ON ucks_document_identifiers(document_id)")


def _normalise_identifier(kind: str, value: Any) -> tuple[str, str] | None:
    text = _text(value).strip()
    if not text:
        return None
    kind = kind.lower().strip()
    if kind == "doi":
        text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
        text = re.sub(r"^doi:\s*", "", text, flags=re.I).strip().lower().rstrip(".,; ")
        if not re.match(r"^10\.\d{4,9}/\S+$", text):
            return None
    elif kind == "pmid":
        text = re.sub(r"^PMID:\s*", "", text, flags=re.I).strip()
        if not text.isdigit(): return None
    elif kind == "pmcid":
        text = re.sub(r"^PMC", "", text, flags=re.I).strip()
        if not text.isdigit(): return None
        text = "PMC" + text
    elif kind == "nct":
        text = text.upper().strip()
        if not re.match(r"^NCT\d{8}$", text): return None
    else:
        return None
    return kind, text


def _record_identifiers(record: dict[str, Any]) -> list[tuple[str, str]]:
    provenance = record.get("provenance") or {}
    candidates = [("doi", provenance.get("doi")), ("pmid", provenance.get("pmid")),
                  ("pmcid", provenance.get("pmcid")), ("nct", provenance.get("nct_id"))]
    external = _text(record.get("external_id"))
    for prefix, kind in (("DOI:", "doi"), ("PMID:", "pmid"), ("PMC:", "pmcid")):
        if external.upper().startswith(prefix): candidates.append((kind, external[len(prefix):]))
    if re.match(r"^NCT\d{8}$", external, re.I): candidates.append(("nct", external))
    found = []
    for kind, value in candidates:
        item = _normalise_identifier(kind, value)
        if item and item not in found: found.append(item)
    return found


def _index_record_identifiers(repo, document_id: str, source_id: str, record: dict[str, Any]) -> None:
    identifiers = _record_identifiers(record)
    if not identifiers: return
    _ensure_identifier_table(repo)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with repo.store.transaction() as conn:
        for kind, value in identifiers:
            conn.execute("INSERT OR IGNORE INTO ucks_document_identifiers(document_id,source_id,identifier_type,identifier_value,created_at) VALUES(?,?,?,?,?)",
                         (document_id, source_id, kind, value, now))


def find_identifier_matches(repo, identifier_type: str, identifier_value: str) -> list[dict[str, Any]]:
    key = _normalise_identifier(identifier_type, identifier_value)
    if not key: raise ValueError("Unsupported or invalid clinical identifier")
    _ensure_identifier_table(repo)
    with repo.store.transaction() as conn:
        rows = conn.execute("""SELECT i.document_id,i.source_id,i.identifier_type,i.identifier_value,
            d.title,d.external_id,d.source_url,d.review_status,d.lifecycle_state,d.updated_at,s.name AS source_name
            FROM ucks_document_identifiers i JOIN ucks_documents d ON d.id=i.document_id
            JOIN ucks_sources s ON s.id=i.source_id
            WHERE i.identifier_type=? AND i.identifier_value=? ORDER BY d.updated_at DESC""", key).fetchall()
    return [dict(row) for row in rows]


def list_document_identifiers(repo, document_id: str) -> list[dict[str, Any]]:
    _ensure_identifier_table(repo)
    with repo.store.transaction() as conn:
        rows = conn.execute("SELECT identifier_type,identifier_value,source_id,created_at FROM ucks_document_identifiers WHERE document_id=? ORDER BY identifier_type,identifier_value", (document_id,)).fetchall()
    return [dict(row) for row in rows]

def _automated_screen_record(record: dict[str, Any], connector: str) -> dict[str, Any]:
    """Apply bounded integrity checks before managed records enter the library.

    Passing these checks means only that the record is structurally usable and
    attributable to a supported provider. It does not assess medical accuracy,
    evidence certainty, licence scope or fitness for patient-care decisions.
    """
    external_id = _text(record.get("external_id"))
    title = _text(record.get("title"))
    body = _text(record.get("body"))
    url = _text(record.get("url"))
    parsed = urlsplit(url)
    checks = {
        "supported_connector": connector in CONNECTORS,
        "stable_external_identifier": bool(external_id) and len(external_id) <= 500,
        "title_present": bool(title) and len(title) <= 500,
        "body_present_and_bounded": bool(body) and len(body) <= 2_000_000,
        "secure_source_url": parsed.scheme == "https" and bool(parsed.netloc),
    }
    passed = all(checks.values())
    return {
        "status": "machine_screened" if passed else "screening_incomplete",
        "passed": passed,
        "checks": checks,
        "clinical_validity_assessed": False,
        "evidence_certainty_assessed": False,
        "reuse_permission_granted": False,
        "human_approval_required_for_import": False,
    }


def sync_connector(repo, source_id: str, query: str, limit: int = 25, *, include_full_text: bool = False,
                   max_pages_per_run: int = 1, session=requests) -> dict[str, Any]:
    source = repo.get_source(source_id)
    if not source:
        raise ValueError("Unknown UCKS source")
    cfg = source.get("config", {})
    connector = str(cfg.get("connector", ""))
    managed_automatic_import = bool(cfg.get("automation_profile"))
    imported_review_status = "machine_screened" if managed_automatic_import else "harvested"
    if connector not in CONNECTORS:
        raise ValueError("Source must declare a supported connector in config.connector")
    if not source.get("enabled"):
        raise ValueError("UCKS source is disabled")
    if not query.strip() or len(query) > 500:
        raise ValueError("A non-empty query of at most 500 characters is required")
    limit = max(1, min(int(limit), MAX_RESULTS))
    _ensure_connector_tables(repo)
    _ensure_connector_checkpoints(repo)
    query_hash = hashlib.sha256(query.strip().encode("utf-8")).hexdigest()
    run_id = f"run_{int(time.time() * 1000)}_{source_id[-8:]}"
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    records_seen = added = skipped = pages_completed = 0
    records: list[dict[str, Any]] = []
    page: dict[str, Any] = {"records": [], "next_cursor": "", "total_records": 0, "complete": True}
    outcome, error = "succeeded", ""
    try:
        checkpoint = get_connector_checkpoint(repo, source_id, query)
        custom_fetcher = _FETCHERS.get(connector) is not _DEFAULT_FETCHERS[connector]
        page_budget = 1 if custom_fetcher else max(1, min(int(max_pages_per_run), 100))
        cursor = (checkpoint or {}).get("cursor", "")
        seen_cursors: set[str] = set()
        for _page_number in range(page_budget):
            if custom_fetcher:
                page_records = _FETCHERS[connector](query.strip(), limit, session)
                page = {"records": page_records, "next_cursor": "", "total_records": len(page_records), "complete": True}
            else:
                page = _PAGE_FETCHERS[connector](query.strip(), limit, session, cursor)
                page_records = page.get("records", [])
            pages_completed += 1
            records_seen += len(page_records)
            records.extend(page_records)
            for record in page_records:
                screening = _automated_screen_record(record, connector) if managed_automatic_import else {
                    "status": "harvested", "passed": True, "clinical_validity_assessed": False,
                    "reuse_permission_granted": False, "human_approval_required_for_import": False,
                }
                if managed_automatic_import and not screening["passed"]:
                    skipped += 1
                    continue
                body = record["body"]
                fulltext_meta: dict[str, Any] = {"full_text_status": "not_requested"}
                if include_full_text and connector == "europe_pmc":
                    full_body, fulltext_meta = _europe_pmc_fulltext(record, session)
                    if full_body:
                        body = full_body
                provenance = {**record["provenance"], **fulltext_meta, "query": query,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "automated_screening": screening,
                    "clinical_review_required_for_patient_care_or_clinical_validation": True,
                    "licence_review_required_for_reuse": True,
                    "connector_metadata_only": connector == "crossref"}
                # Same source identifier + changed body creates an immutable revision, not a duplicate document.
                with repo.store.transaction() as conn:
                    existing = conn.execute("SELECT id FROM ucks_documents WHERE source_id=? AND external_id=? ORDER BY updated_at DESC LIMIT 1",
                                            (source_id, record["external_id"])).fetchone()
                if existing:
                    current = repo.get_document(existing["id"])
                    if current and current.get("content_hash") != hashlib.sha256(body.encode("utf-8")).hexdigest():
                        merged = {**current.get("provenance", {}), **provenance, "previous_version": current.get("current_version")}
                        repo.revise_document(existing["id"], title=record["title"], body=body, provenance=merged)
                        added += 1
                    if managed_automatic_import:
                        # Idempotently migrate pre-existing harvested records, but never
                        # upgrade clinical validation or an explicit rejection.
                        with repo.store.transaction() as conn:
                            conn.execute("""UPDATE ucks_documents SET review_status='machine_screened'
                                WHERE id=? AND review_status IN ('harvested','machine_screened')""",
                                (existing["id"],))
                    _index_record_identifiers(repo, existing["id"], source_id, record)
                    if str(record.get("provenance", {}).get("publisher_lifecycle_signal", "")).casefold() == "retracted":
                        repo.set_lifecycle_state(existing["id"], "retracted")
                    continue
                result = repo.ingest_document(source_id=source_id, title=record["title"], body=body,
                    content_type=record["content_type"], external_id=record["external_id"],
                    publication_date=record["publication_date"], source_url=record["url"],
                    licence=record["licence"], provenance=provenance,
                    review_status=imported_review_status)
                added += int(result.get("created", False))
                if result.get("id"):
                    _index_record_identifiers(repo, result["id"], source_id, record)
                    if str(record.get("provenance", {}).get("publisher_lifecycle_signal", "")).casefold() == "retracted":
                        repo.set_lifecycle_state(result["id"], "retracted")
            if page.get("complete", True) or not page.get("next_cursor"):
                break
            next_cursor = str(page.get("next_cursor", ""))
            if next_cursor == cursor or next_cursor in seen_cursors:
                raise RuntimeError("Provider pagination cursor did not advance")
            seen_cursors.add(cursor)
            cursor = next_cursor

    except Exception as exc:
        outcome, error = "failed", type(exc).__name__
        raise
    finally:
        completed_at = datetime.now(timezone.utc).isoformat()
        duration = int((time.monotonic()-started)*1000)
        with repo.store.transaction() as conn:
            conn.execute("""INSERT INTO ucks_connector_runs
                (id,source_id,connector,query_text,outcome,records_seen,records_added,error,started_at,completed_at,duration_ms)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (run_id, source_id, connector, query, outcome, records_seen, added, error,
                 started_at, completed_at, duration))
    if outcome == "succeeded":
        now_checkpoint = datetime.now(timezone.utc).isoformat(timespec="seconds")
        last_id = records[-1].get("external_id", "") if records else ""
        with repo.store.transaction() as conn:
            conn.execute("""INSERT INTO ucks_connector_checkpoints
                (source_id,query_hash,connector,cursor,sync_runs_completed,records_seen,records_added,last_external_id,last_success,updated_at,total_records,pages_completed,pagination_complete,page_size,last_page_at)
                VALUES(?,?,?,?,1,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id,query_hash) DO UPDATE SET
                connector=excluded.connector,cursor=excluded.cursor,sync_runs_completed=ucks_connector_checkpoints.sync_runs_completed+1,
                records_seen=ucks_connector_checkpoints.records_seen+excluded.records_seen,
                records_added=ucks_connector_checkpoints.records_added+excluded.records_added,
                last_external_id=excluded.last_external_id,last_success=excluded.last_success,updated_at=excluded.updated_at,
                total_records=excluded.total_records,pages_completed=ucks_connector_checkpoints.pages_completed+excluded.pages_completed,
                pagination_complete=excluded.pagination_complete,page_size=excluded.page_size,last_page_at=excluded.last_page_at""",
                (source_id,query_hash,connector,page.get("next_cursor", ""),records_seen,added,last_id,now_checkpoint,now_checkpoint,
                 int(page.get("total_records", 0)),pages_completed,int(bool(page.get("complete", True))),limit,now_checkpoint))
    return {"run_id": run_id, "source_id": source_id, "connector": connector,
            "records_seen": records_seen, "records_added": added, "records_skipped_by_screen": skipped,
            "checkpoint": get_connector_checkpoint(repo, source_id, query),
            "duplicates": max(0, records_seen-added-skipped), "duration_ms": duration,
            "review_status": imported_review_status, "full_text_requested": bool(include_full_text),
            "human_approval_required_for_import": False,
            "pagination": {"total_records": int(page.get("total_records", records_seen)),
                "page_records": records_seen, "pages_completed_this_run": pages_completed,
                "next_cursor_available": bool(page.get("next_cursor")),
                "complete": bool(page.get("complete", True)), "provider_cursor_type":
                    {"europe_pmc": "cursorMark", "pubmed": "retstart offset", "crossref": "offset", "clinicaltrials_gov": "nextPageToken"}[connector]},
            "full_text_licence_policy": "CC0/CC-BY/CC-BY-SA allow-list; others metadata/abstract only"}



def _ensure_connector_schedule(repo) -> None:
    with repo.store.transaction() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS ucks_connector_schedule (
            source_id TEXT PRIMARY KEY REFERENCES ucks_sources(id),
            enabled INTEGER NOT NULL DEFAULT 0, query_text TEXT NOT NULL,
            result_limit INTEGER NOT NULL DEFAULT 25, include_full_text INTEGER NOT NULL DEFAULT 0,
            interval_minutes INTEGER NOT NULL DEFAULT 360, next_run TEXT NOT NULL DEFAULT '',
            lease_until TEXT NOT NULL DEFAULT '', consecutive_failures INTEGER NOT NULL DEFAULT 0,
            last_attempt TEXT NOT NULL DEFAULT '', last_success TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_connector_schedule_due ON ucks_connector_schedule(enabled,next_run)")


def configure_connector_schedule(repo, source_id: str, *, enabled: bool, query: str,
                                  interval_minutes: int = 360, result_limit: int = 25,
                                  include_full_text: bool = False) -> dict[str, Any]:
    source = repo.get_source(source_id)
    if not source or source.get("config", {}).get("connector") not in CONNECTORS:
        raise ValueError("A registered connector source is required")
    if not query.strip() or len(query) > 500:
        raise ValueError("A non-empty query of at most 500 characters is required")
    interval = max(15, min(int(interval_minutes), 10080))
    limit = max(1, min(int(result_limit), MAX_RESULTS))
    now = datetime.now(timezone.utc)
    next_run = now.isoformat(timespec="seconds") if enabled else ""
    _ensure_connector_schedule(repo)
    with repo.store.transaction() as conn:
        conn.execute("""INSERT INTO ucks_connector_schedule
            (source_id,enabled,query_text,result_limit,include_full_text,interval_minutes,next_run,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
            enabled=excluded.enabled,query_text=excluded.query_text,result_limit=excluded.result_limit,
            include_full_text=excluded.include_full_text,interval_minutes=excluded.interval_minutes,
            next_run=excluded.next_run,lease_until='',updated_at=excluded.updated_at""",
            (source_id,int(enabled),query.strip(),limit,int(include_full_text),interval,next_run,now.isoformat()))
    return get_connector_schedule(repo, source_id)


def get_connector_schedule(repo, source_id: str = "") -> Any:
    _ensure_connector_schedule(repo)
    with repo.store.transaction() as conn:
        if source_id:
            rows = conn.execute("SELECT * FROM ucks_connector_schedule WHERE source_id=?", (source_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM ucks_connector_schedule ORDER BY source_id").fetchall()
    return dict(rows[0]) if source_id and rows else (None if source_id else [dict(r) for r in rows])


def claim_due_connectors(repo, *, limit: int = 20, lease_seconds: int = 300) -> list[dict[str, Any]]:
    _ensure_connector_schedule(repo)
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    lease = (now + __import__("datetime").timedelta(seconds=max(30,min(lease_seconds,1800)))).isoformat(timespec="seconds")
    with repo.store.transaction() as conn:
        rows = conn.execute("""SELECT sc.* FROM ucks_connector_schedule sc
            JOIN ucks_sources src ON src.id=sc.source_id
            WHERE sc.enabled=1 AND src.enabled=1 AND sc.next_run!='' AND sc.next_run<=?
            AND (sc.lease_until='' OR sc.lease_until<?) ORDER BY sc.next_run LIMIT ?""",
            (stamp,stamp,max(1,min(int(limit),100)))).fetchall()
        claimed = [dict(row) for row in rows]
        for row in claimed:
            conn.execute("UPDATE ucks_connector_schedule SET lease_until=?,last_attempt=?,updated_at=? WHERE source_id=?",
                         (lease,stamp,stamp,row["source_id"]))
    return claimed


def complete_connector_schedule(repo, source_id: str, *, success: bool, error: str = "") -> dict[str, Any]:
    _ensure_connector_schedule(repo)
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec="seconds")
    with repo.store.transaction() as conn:
        row = conn.execute("SELECT * FROM ucks_connector_schedule WHERE source_id=?", (source_id,)).fetchone()
        if not row:
            raise ValueError("Connector schedule not found")
        failures = 0 if success else int(row["consecutive_failures"] or 0) + 1
        delay = int(row["interval_minutes"]) if success else min(int(row["interval_minutes"]) * (2 ** min(failures, 8)), 1440)
        next_run = (now + __import__("datetime").timedelta(minutes=delay)).isoformat(timespec="seconds") if row["enabled"] else ""
        conn.execute("""UPDATE ucks_connector_schedule SET next_run=?,lease_until='',consecutive_failures=?,
            last_success=CASE WHEN ? THEN ? ELSE last_success END,last_error=?,updated_at=? WHERE source_id=?""",
            (next_run,failures,int(success),stamp,error[:1000],stamp,source_id))
        result = conn.execute("SELECT * FROM ucks_connector_schedule WHERE source_id=?", (source_id,)).fetchone()
    return dict(result)


def run_due_connectors(repo, *, limit: int = 20) -> dict[str, Any]:
    claimed = claim_due_connectors(repo, limit=limit)
    results = []
    for job in claimed:
        sid = job["source_id"]
        try:
            # Built-in source profiles use rolling date tokens so each daily
            # run searches a current window instead of walking a stale cursor.
            from .external_source_automation import expand_query
            query = expand_query(job["query_text"])
            result = sync_connector(repo, sid, query, job["result_limit"],
                                    include_full_text=bool(job["include_full_text"]),
                                    max_pages_per_run=10)
            complete_connector_schedule(repo, sid, success=True)
            results.append({"source_id": sid, "status": "succeeded", **result})
        except Exception as exc:
            complete_connector_schedule(repo, sid, success=False, error=type(exc).__name__)
            results.append({"source_id": sid, "status": "failed", "error": type(exc).__name__})
    return {"claimed": len(claimed), "results": results,
            "notice": "Managed source records are automatically machine-screened on import; this is not clinical validation and does not grant reuse rights."}
