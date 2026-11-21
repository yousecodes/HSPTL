"""Shared source-tree scan for retired product identifiers."""
from __future__ import annotations

from pathlib import Path
import os

EXCLUDED_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", "coverage",
}
BINARY_SUFFIXES = {
    ".zip", ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico",
    ".pdf", ".db", ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".otf",
}
# Split literals keep the scanner from matching its own rule definitions.
PROHIBITED_IDENTIFIERS = ("kli" + "nica", "round" + "md", "road" + "md")


def find_identity_leaks(root: Path) -> list[tuple[Path, str]]:
    """Find prohibited identifiers in distributable paths and UTF-8 text.

    Directory and file names are checked before binary-content exclusions.
    Generated dependency/cache/build directories are pruned, matching the
    release packager's exclusions.
    """
    root = root.resolve()
    leaks: list[tuple[Path, str]] = []

    def path_matches(relative: Path) -> set[str]:
        return {
            token for token in PROHIBITED_IDENTIFIERS
            if any(token in part.casefold() for part in relative.parts)
        }

    for current, directories, filenames in os.walk(root):
        current_path = Path(current)
        kept_directories: list[str] = []
        for directory in directories:
            relative = (current_path / directory).relative_to(root)
            leaks.extend((relative, token) for token in sorted(path_matches(relative)))
            if directory.casefold() not in EXCLUDED_DIRS:
                kept_directories.append(directory)
        directories[:] = kept_directories

        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(root)
            matched_path = path_matches(relative)
            leaks.extend((relative, token) for token in sorted(matched_path))
            if path.is_symlink() or path.suffix.casefold() in BINARY_SUFFIXES:
                continue
            try:
                content = path.read_text(encoding="utf-8").casefold()
            except (UnicodeDecodeError, OSError):
                continue
            leaks.extend(
                (relative, token)
                for token in PROHIBITED_IDENTIFIERS
                if token in content and token not in matched_path
            )
    return leaks
