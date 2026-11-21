"""Bounded, attribution-conscious external data connectors for HSPTL."""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests

USER_AGENT = "HSPTL/1.0 (local clinical education; contact through Europe PMC/Commons standard APIs)"
TIMEOUT = (5, 25)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"})
    return session


def europe_pmc_search(term: str, limit: int = 20, case_reports_only: bool = True) -> list[dict[str, Any]]:
    term = term.strip()
    if not term:
        return []
    if len(term) > 180:
        raise ValueError("Search term is too long (maximum 180 characters).")
    limit = max(1, min(int(limit), 50))
    query = f"({term}) AND OPEN_ACCESS:Y"
    if case_reports_only:
        query += ' AND PUB_TYPE:"case reports"'
    # Europe PMC supports date-sorted search through sort_date:y.
    query += " sort_date:y"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    response = _session().get(
        url,
        params={"query": query, "format": "json", "pageSize": limit, "resultType": "core"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("resultList", {}).get("result", [])
    return rows if isinstance(rows, list) else []


def is_open_access(article: dict[str, Any]) -> bool:
    value = str(article.get("isOpenAccess") or article.get("is_open_access") or "").strip().casefold()
    return value in {"y", "yes", "true", "1"}


def article_url(article: dict[str, Any]) -> str:
    pmcid = str(article.get("pmcid") or "").strip()
    pmid = str(article.get("pmid") or "").strip()
    doi = str(article.get("doi") or "").strip()
    if pmcid:
        return f"https://europepmc.org/articles/{quote(pmcid)}"
    if pmid:
        return f"https://europepmc.org/article/MED/{quote(pmid)}"
    if doi:
        return f"https://doi.org/{quote(doi)}"
    return "https://europepmc.org/"


def pmc_bioc_fulltext(pmcid: str) -> dict[str, Any] | None:
    """Retrieve one article from the PMC OA/author-manuscript BioC endpoint.

    Availability and reuse rights are article-specific. This function is only
    called on explicit user action and does not bulk-download articles.
    """
    pmcid = pmcid.strip().upper()
    if not re.fullmatch(r"PMC\d+", pmcid):
        raise ValueError("A valid PMC identifier such as PMC1234567 is required.")
    url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/{pmcid}/unicode"
    response = _session().get(url, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return None
    return payload[0]


def bioc_plain_text(payload: Any, max_chars: int = 16000) -> str:
    """Extract readable passage text from one PMC BioC JSON article response."""
    roots = payload if isinstance(payload, list) else [payload]
    pieces: list[str] = []
    for root in roots:
        documents = root.get("documents", []) if isinstance(root, dict) else []
        if not documents and isinstance(root, dict) and "passages" in root:
            documents = [root]
        for document in documents:
            passages = document.get("passages", []) if isinstance(document, dict) else []
            for passage in passages:
                if not isinstance(passage, dict):
                    continue
                text = str(passage.get("text") or "").strip()
                if not text:
                    continue
                infons = passage.get("infons", {})
                section = ""
                if isinstance(infons, dict):
                    section = str(infons.get("section_type") or infons.get("type") or "").strip()
                pieces.append((f"[{section}]\n" if section else "") + text)
                if sum(len(x) for x in pieces) >= max_chars:
                    return "\n\n".join(pieces)[:max_chars]
    return "\n\n".join(pieces)[:max_chars]


def dailymed_search(drug_name: str, limit: int = 10) -> list[dict[str, Any]]:
    drug_name = drug_name.strip()
    if not drug_name:
        return []
    if len(drug_name) > 100:
        raise ValueError("Medicine name is too long.")
    url = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
    response = _session().get(url, params={"drug_name": drug_name, "page": 1, "pagesize": max(1, min(limit, 20))}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", []) if isinstance(payload, dict) else []


def dailymed_url(set_id: str) -> str:
    clean_id = re.sub(r"[^a-fA-F0-9-]", "", set_id)
    if not clean_id:
        return "https://dailymed.nlm.nih.gov/"
    return f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={clean_id}"


def save_reference_pdf(filename: str, payload: bytes, target_dir: Path, max_bytes: int = 35 * 1024 * 1024) -> Path:
    if len(payload) > max_bytes:
        raise ValueError(f"PDF exceeds the {max_bytes // (1024 * 1024)} MB import limit.")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not appear to be a PDF.")
    target_dir.mkdir(parents=True, exist_ok=True)
    original = Path(filename).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(original).stem).strip("._-") or "reference"
    digest = hashlib.sha256(payload).hexdigest()[:10]
    target = target_dir / f"{stem}_{digest}.pdf"
    temp = target.with_suffix(".pdf.tmp")
    temp.write_bytes(payload)
    temp.replace(target)
    return target


def extract_pdf_text(path: Path, max_pages: int = 100) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf with: python -m pip install pypdf") from exc
    reader = PdfReader(str(path))
    pieces: list[str] = []
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        if text:
            pieces.append(text)
    return "\n\n".join(pieces)


def find_loinc_csv(path: Path) -> tuple[Path, bool]:
    """Return (CSV path, is_zip_member) for an extracted or zipped LOINC release."""
    if path.is_file() and path.suffix.casefold() == ".zip":
        with zipfile.ZipFile(path) as archive:
            candidates = [name for name in archive.namelist() if Path(name).name.casefold() == "loinc.csv"]
            if not candidates:
                raise FileNotFoundError("Could not find Loinc.csv inside the ZIP archive.")
            # Keep extraction outside the archive in a predictable sibling folder.
            extract_root = path.parent / f"{path.stem}_extracted"
            extract_root.mkdir(parents=True, exist_ok=True)
            member = candidates[0]
            destination = extract_root / "Loinc.csv"
            with archive.open(member) as src, destination.open("wb") as dst:
                dst.write(src.read())
            return destination, False
    if path.is_dir():
        matches = list(path.rglob("Loinc.csv")) + list(path.rglob("loinc.csv"))
        if matches:
            return matches[0], False
    if path.is_file() and path.name.casefold() == "loinc.csv":
        return path, False
    raise FileNotFoundError("Select the Loinc.csv file or the official LOINC ZIP release.")


def search_loinc_csv(path: Path, query: str, limit: int = 30) -> pd.DataFrame:
    csv_path, _ = find_loinc_csv(path)
    query = query.strip().casefold()
    if not query:
        return pd.DataFrame()
    header = pd.read_csv(csv_path, nrows=0).columns.tolist()
    desired = [c for c in ["LOINC_NUM", "LONG_COMMON_NAME", "SHORTNAME", "COMPONENT", "SYSTEM", "PROPERTY", "SCALE_TYP", "METHOD_TYP"] if c in header]
    if not desired:
        raise ValueError("The selected file does not contain expected LOINC fields.")
    # Use chunks to avoid loading the complete terminology into RAM.
    found: list[pd.DataFrame] = []
    for chunk in pd.read_csv(csv_path, usecols=desired, chunksize=100_000, low_memory=False):
        names = [c for c in ["LOINC_NUM", "LONG_COMMON_NAME", "SHORTNAME", "COMPONENT"] if c in chunk.columns]
        mask = pd.Series(False, index=chunk.index)
        for col in names:
            mask |= chunk[col].fillna("").astype(str).str.casefold().str.contains(re.escape(query), regex=True)
        matches = chunk.loc[mask]
        if not matches.empty:
            found.append(matches)
        if sum(len(x) for x in found) >= limit:
            break
    return pd.concat(found, ignore_index=True).head(limit) if found else pd.DataFrame(columns=desired)


def wfdb_records(directory: Path) -> list[str]:
    """List WFDB records found locally without loading their signals."""
    return sorted(path.stem for path in directory.glob("*.hea")) if directory.is_dir() else []


def read_wfdb_record(directory: Path, record_name: str):
    try:
        import wfdb
    except ImportError as exc:
        raise RuntimeError("Install the optional ECG reader with: python -m pip install wfdb") from exc
    if not re.fullmatch(r"[A-Za-z0-9_-]+", record_name):
        raise ValueError("Invalid ECG record identifier.")
    record_path = directory / record_name
    if not record_path.with_suffix(".hea").is_file():
        raise FileNotFoundError(f"WFDB header not found for {record_name}.")
    return wfdb.rdrecord(str(record_path))


def read_wfdb_annotations(directory: Path, record_name: str, extension: str = "atr") -> pd.DataFrame:
    """Read reference annotations for one WFDB record, if supplied by the dataset."""
    try:
        import wfdb
    except ImportError as exc:
        raise RuntimeError("Install the optional ECG reader with: python -m pip install wfdb") from exc
    if not re.fullmatch(r"[A-Za-z0-9_-]+", record_name):
        raise ValueError("Invalid ECG record identifier.")
    record_path = directory / record_name
    if not record_path.with_suffix(f".{extension}").is_file():
        raise FileNotFoundError(f"No .{extension} annotation file was found for {record_name}.")
    annotation = wfdb.rdann(str(record_path), extension)
    return pd.DataFrame({
        "sample": annotation.sample,
        "time_seconds": annotation.sample / float(annotation.fs) if getattr(annotation, "fs", None) else None,
        "symbol": annotation.symbol,
        "aux_note": getattr(annotation, "aux_note", [""] * len(annotation.sample)),
    })


def europe_pmc_fulltext_xml(pmcid: str) -> str | None:
    """Fetch one openly available full-text JATS article through Europe PMC.

    The Europe PMC fullTextXML endpoint is used for individual user-requested
    articles. The article must first be returned as open access by search.
    This is not a bulk-download implementation.
    """
    pmcid = str(pmcid or "").strip().upper()
    if not re.fullmatch(r"PMC\d+", pmcid):
        raise ValueError("A valid PMC identifier such as PMC1234567 is required.")
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    response = _session().get(url, headers={"Accept": "application/xml,text/xml"}, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    text = response.text.strip()
    if not text.startswith("<") or "<article" not in text[:3000].casefold():
        return None
    return text[:2_500_000]


def parse_jats_article(xml_text: str, max_sections: int = 45, max_figures: int = 25) -> dict[str, Any]:
    """Extract structured article metadata, sections and figure captions from JATS XML."""
    import xml.etree.ElementTree as ET

    if not isinstance(xml_text, str) or len(xml_text) > 2_500_000:
        raise ValueError("Article XML is empty or exceeds the 2.5 MB safety limit.")
    root = ET.fromstring(xml_text)

    def local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].casefold()

    def text_of(element) -> str:
        return " ".join("".join(element.itertext()).split()) if element is not None else ""

    def descendants(element, wanted: str):
        return [node for node in element.iter() if local_name(node.tag) == wanted]

    title_node = next(iter(descendants(root, "article-title")), None)
    abstract_node = next(iter(descendants(root, "abstract")), None)
    license_node = next(iter(descendants(root, "license")), None)
    license_text = text_of(license_node)
    license_href = ""
    if license_node is not None:
        for key, value in license_node.attrib.items():
            if key.rsplit("}", 1)[-1].casefold() == "href":
                license_href = value
                break

    body = next(iter(descendants(root, "body")), None)
    sections: list[dict[str, str]] = []
    if body is not None:
        for sec in descendants(body, "sec")[:max_sections]:
            heading_node = next((x for x in list(sec) if local_name(x.tag) == "title"), None)
            heading = text_of(heading_node) or "Article section"
            # Include direct paragraphs and immediate child paragraphs only; avoid
            # repeating nested subsections when the parent text is collected.
            paragraphs = []
            for child in list(sec):
                if local_name(child.tag) == "p":
                    para = text_of(child)
                    if para:
                        paragraphs.append(para)
            if paragraphs:
                sections.append({"heading": heading[:180], "text": "\n\n".join(paragraphs)[:5000]})

    figures: list[dict[str, str]] = []
    for fig in descendants(root, "fig")[:max_figures]:
        label_node = next((x for x in list(fig) if local_name(x.tag) == "label"), None)
        caption_node = next((x for x in list(fig) if local_name(x.tag) == "caption"), None)
        graphic = next(iter(descendants(fig, "graphic")), None)
        href = ""
        if graphic is not None:
            href = next((v for k, v in graphic.attrib.items() if k.rsplit("}", 1)[-1].casefold() == "href"), "")
        figures.append({
            "id": str(fig.attrib.get("id", "")),
            "label": text_of(label_node)[:80],
            "caption": text_of(caption_node)[:800],
            "graphic_href": href[:400],
        })

    return {
        "title": text_of(title_node)[:500],
        "abstract": text_of(abstract_node)[:5000],
        "license_text": license_text[:500],
        "license_url": license_href[:500],
        "sections": sections,
        "figures": figures,
    }


def commons_search_images(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Search Wikimedia Commons and return attribution-bearing free-license media.

    The function only returns thumbnails for Commons files whose metadata declares
    CC BY/CC BY-SA, CC0 or Public Domain. It retains author, license, and source page.
    """
    query = str(query or "").strip()
    if not query:
        return []
    if len(query) > 120:
        raise ValueError("Image search term is too long (maximum 120 characters).")
    limit = max(1, min(int(limit), 12))
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f'{query} filetype:bitmap',
        "gsrnamespace": 6,
        "gsrlimit": limit * 3,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 640,
    }
    headers = {"User-Agent": "HSPTL/1.0 (local medical education; attribution retained)"}
    response = _session().get(
        "https://commons.wikimedia.org/w/api.php", params=params, headers=headers, timeout=TIMEOUT
    )
    response.raise_for_status()
    pages = response.json().get("query", {}).get("pages", {})
    results: list[dict[str, str]] = []
    for page in pages.values():
        imageinfo = (page.get("imageinfo") or [{}])[0]
        meta = imageinfo.get("extmetadata") or {}
        license_name = re.sub(r"<[^>]+>", " ", str((meta.get("LicenseShortName") or {}).get("value", "")))
        license_name = " ".join(license_name.split())
        folded = license_name.casefold()
        permitted = (
            "cc by" in folded or "cc0" in folded or "public domain" in folded
            or "pdm" == folded
        )
        if not permitted or "noncommercial" in folded or "by-nc" in folded or "cc nc" in folded or "by-nd" in folded:
            continue
        def plain_meta(key: str, cap: int = 240) -> str:
            raw = str((meta.get(key) or {}).get("value", ""))
            raw = re.sub(r"<[^>]*>", " ", raw)
            raw = " ".join(raw.replace("&nbsp;", " ").replace("&amp;", "&").split())
            return raw[:cap]
        thumb = str(imageinfo.get("thumburl") or imageinfo.get("url") or "")
        source = str(imageinfo.get("descriptionurl") or "")
        if not thumb or not source:
            continue
        results.append({
            "title": str(page.get("title", "")).removeprefix("File:")[:240],
            "thumbnail_url": thumb,
            "source_url": source,
            "license": license_name,
            "license_url": plain_meta("LicenseUrl", 400),
            "artist": plain_meta("Artist", 240) or plain_meta("Credit", 240) or "Creator not specified",
            "credit": plain_meta("Credit", 240),
        })
        if len(results) >= limit:
            break
    return results
