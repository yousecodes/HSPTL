"""Safe text extraction for user-supplied UCKS reference files.

Extraction is deliberately text-only: macros, embedded scripts and active content
are never executed. Original files remain the user's responsibility to retain.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree

MAX_FILE_BYTES = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".jsonl", ".docx"}


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_text(filename: str, content: bytes) -> tuple[str, dict]:
    """Return extracted text and non-sensitive extraction metadata."""
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 20 MB UCKS import limit")
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'no extension'}")
    if not content:
        raise ValueError("The uploaded file is empty")
    if suffix in {".txt", ".md"}:
        text = content.decode("utf-8-sig", errors="replace")
        return _clean(text), {"format": suffix[1:], "extraction": "utf-8"}
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig", errors="replace")), delimiter=delimiter))
        text = "\n".join(" | ".join(cell.strip() for cell in row) for row in rows if any(x.strip() for x in row))
        return _clean(text), {"format": suffix[1:], "row_count": len(rows), "extraction": "csv_reader"}
    if suffix in {".json", ".jsonl"}:
        raw = content.decode("utf-8-sig", errors="replace")
        if suffix == ".jsonl":
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]
            text = "\n\n".join(json.dumps(item, ensure_ascii=False, indent=2) for item in records)
            count = len(records)
        else:
            parsed = json.loads(raw)
            text = json.dumps(parsed, ensure_ascii=False, indent=2)
            count = len(parsed) if isinstance(parsed, (list, dict)) else 1
        return _clean(text), {"format": suffix[1:], "record_count": count, "extraction": "json"}
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported")
            pages = [page.extract_text() or "" for page in reader.pages]
            return _clean("\n\n".join(pages)), {"format": "pdf", "page_count": len(pages), "extraction": "pypdf"}
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"PDF text extraction failed: {exc}") from exc
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paragraphs = []
            for paragraph in root.findall(".//w:p", ns):
                value = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
                if value.strip():
                    paragraphs.append(value)
            return _clean("\n\n".join(paragraphs)), {"format": "docx", "paragraph_count": len(paragraphs), "extraction": "ooxml_text"}
        except Exception as exc:
            raise ValueError(f"DOCX text extraction failed: {exc}") from exc
    raise ValueError("Unsupported file type")
