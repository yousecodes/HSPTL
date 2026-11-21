"""Bounded FHIR parsing.

FHIR exports are large and untrusted-by-shape. Every read here is capped by a
file-size limit, NDJSON is read line by line with a per-line cap, and a parse
failure is reported as a finding rather than raised into the pipeline so the
run can quarantine the patient instead of crashing the worker.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

DEFAULT_MAX_FILE_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_LINE_BYTES = 4 * 1024 * 1024


class OversizedFile(ValueError):
    pass


class OversizedLine(ValueError):
    pass


@dataclass
class ParsedResource:
    resource: dict[str, Any]
    source_file: str
    full_url: str


@dataclass
class ParseProblem:
    source_file: str
    rule_id: str
    message: str


def _bounded_lines(path: Path, max_line_bytes: int) -> Iterator[str]:
    with path.open("rb") as stream:
        for raw in stream:
            if len(raw) > max_line_bytes:
                raise OversizedLine(
                    f"NDJSON line exceeds the {max_line_bytes} byte limit in {path.name}"
                )
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                yield text


def iter_resources(path: Path, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
                   max_line_bytes: int = DEFAULT_MAX_LINE_BYTES) -> Iterator[dict[str, Any]]:
    """Yield FHIR resources from a .json bundle or an .ndjson file."""
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise OversizedFile(f"File could not be read: {exc}") from exc
    if size > max_file_bytes:
        raise OversizedFile(f"{path.name} exceeds the {max_file_bytes} byte limit")

    suffix = path.suffix.casefold()
    if suffix in {".ndjson", ".jsonl"}:
        for line in _bounded_lines(path, max_line_bytes):
            payload = json.loads(line)
            if isinstance(payload, dict):
                yield payload
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
        for entry in payload.get("entry", []) or []:
            resource = entry.get("resource") if isinstance(entry, dict) else None
            if isinstance(resource, dict):
                yield resource
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
    elif isinstance(payload, dict):
        yield payload


def load_bundles(directory: Path, *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
                 max_line_bytes: int = DEFAULT_MAX_LINE_BYTES
                 ) -> tuple[list[tuple[str, dict[str, Any]]], list[ParseProblem]]:
    """Read every FHIR file in a directory into per-file bundles.

    Synthea writes one file per patient, so a file is the natural quarantine
    unit. A file that fails to parse becomes a problem, never an exception.
    """
    directory = Path(directory)
    bundles: list[tuple[str, dict[str, Any]]] = []
    problems: list[ParseProblem] = []
    if not directory.is_dir():
        problems.append(ParseProblem(str(directory), "F-PARSE-000", "FHIR output directory does not exist."))
        return bundles, problems

    files = sorted([*directory.rglob("*.json"), *directory.rglob("*.ndjson"), *directory.rglob("*.jsonl")])
    for path in files:
        relative = path.relative_to(directory).as_posix()
        try:
            resources = list(iter_resources(path, max_file_bytes=max_file_bytes,
                                            max_line_bytes=max_line_bytes))
        except OversizedFile as exc:
            problems.append(ParseProblem(relative, "F-PARSE-002", str(exc)))
            continue
        except OversizedLine as exc:
            problems.append(ParseProblem(relative, "F-PARSE-003", str(exc)))
            continue
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            problems.append(ParseProblem(relative, "F-PARSE-001", f"Malformed FHIR JSON: {exc}"))
            continue
        if not resources:
            problems.append(ParseProblem(relative, "F-PARSE-004", "File contained no FHIR resources."))
            continue
        bundles.append((relative, {"resourceType": "Bundle", "type": "collection",
                                   "entry": [{"resource": resource} for resource in resources]}))
    return bundles, problems


def bundle_patient_id(bundle: dict[str, Any]) -> str:
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict) and resource.get("resourceType") == "Patient":
            return str(resource.get("id") or "")
    return ""


def bundle_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if isinstance(resource, dict):
            resources.append(resource)
    return resources
