"""Constrained path helpers for local data-tool workflows."""
from __future__ import annotations
from pathlib import Path

def existing_directory(value: str | Path, *, label: str = "Directory") -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"{label} does not exist")
    return path

def ensure_output_directory(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path
