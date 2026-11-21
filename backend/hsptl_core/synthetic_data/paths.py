"""Path handling for the synthetic data factory.

Every path the factory writes to is resolved beneath the HSPTL-managed storage
root. Callers never pass absolute output paths; they pass a relative segment
that is validated here. This is the single chokepoint that prevents path
traversal, symlink escape and writes outside user data.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# Directory names created under HSPTL_HOME/synthetic_data. They are additive:
# ensure_user_dirs() creates only the roots, deeper paths are created on demand.
SUBDIRS = (
    "runtime/synthea",
    "runtime/fhir_validator",
    "runtime/module_packs",
    "runtime/terminology_cache",
    "staging",
    "datasets",
    "quarantine",
    "recipes",
    "schedules",
    "temp",
)


class UnsafePath(ValueError):
    """Raised when a caller-supplied path would escape the managed root."""


def safe_segment(value: str, *, field: str = "identifier") -> str:
    text = str(value or "").strip()
    if not SAFE_SEGMENT.match(text):
        raise UnsafePath(
            f"{field} must be 1-128 characters of letters, digits, dot, dash or underscore "
            "and must start with a letter or digit"
        )
    return text


def safe_relative(value: str, *, field: str = "path") -> PurePosixPath:
    """Validate a relative POSIX path with no traversal or absolute anchor."""
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        raise UnsafePath(f"{field} must not be empty")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        raise UnsafePath(f"{field} must be relative to HSPTL-managed storage")
    # Reject empty segments and explicit dot segments before PurePosixPath
    # silently collapses them; a caller passing them is a bug worth surfacing.
    raw_parts = text.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise UnsafePath(f"{field} contains an empty, current or parent path segment")
    parts = PurePosixPath(text).parts
    if any(part in {"..", "."} or not SAFE_SEGMENT.match(part) for part in parts):
        raise UnsafePath(f"{field} contains an unsafe path segment")
    return PurePosixPath(*parts)


def resolve_under(root: Path, *segments: str) -> Path:
    """Resolve segments beneath root and prove the result stays inside it.

    ``Path.resolve`` follows symlinks, so a symlink planted inside the managed
    tree cannot be used to read or write elsewhere on disk.
    """
    root_resolved = Path(root).resolve()
    candidate = root_resolved.joinpath(*segments)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    resolved = candidate.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise UnsafePath("resolved path escapes HSPTL-managed storage")
    return resolved


def dataset_dir(root: Path, dataset_id: str) -> Path:
    return resolve_under(root, "datasets", safe_segment(dataset_id, field="dataset_id"))


def staging_dir(root: Path, job_id: str) -> Path:
    return resolve_under(root, "staging", safe_segment(job_id, field="job_id"))


def quarantine_dir(root: Path, dataset_id: str) -> Path:
    return resolve_under(root, "quarantine", safe_segment(dataset_id, field="dataset_id"))


def recipe_dir(root: Path, recipe_id: str, version: str) -> Path:
    return resolve_under(
        root, "recipes",
        safe_segment(recipe_id, field="recipe_id"),
        safe_segment(version, field="recipe version"),
    )


def ensure_layout(root: Path) -> Path:
    """Create the additive factory tree and return its root."""
    base = Path(root) / "synthetic_data"
    base.mkdir(parents=True, exist_ok=True)
    for relative in SUBDIRS:
        (base / relative).mkdir(parents=True, exist_ok=True)
    return base


def quarantine_filename(patient_key: str) -> str:
    """A filesystem-safe name derived from an untrusted FHIR patient identifier.

    ``Patient.id`` comes from generated content and is not trusted as a path
    component. Unsafe characters are replaced and a short hash is appended so
    two distinct identifiers can never collide after sanitisation.
    """
    raw = str(patient_key or "unknown")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")[:80] or "unknown"
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{cleaned}-{suffix}.json"


def safe_artifact_name(source_file: str) -> str:
    """Reduce an untrusted source filename to a safe flat name.

    ``Path(...).name`` still returns ``".."`` for inputs like ``a/..``, so the
    result is validated rather than trusted.
    """
    candidate = Path(str(source_file or "")).name
    if not candidate or candidate in {".", ".."} or not SAFE_SEGMENT.match(candidate):
        digest = hashlib.sha256(str(source_file or "bundle").encode("utf-8")).hexdigest()[:12]
        return f"bundle-{digest}.json"
    return candidate
