from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from release_identity import find_identity_leaks


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
VERIFY_PYTHON = str(VENV_PYTHON) if VENV_PYTHON.is_file() else sys.executable
CONFIG = ROOT / "backend" / "hsptl_core" / "config.py"
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".hsptl-backup", ".verify-home", "versions", "node_modules", "dist", "build", "coverage",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3", ".db", ".zip"}
def legacy_paths() -> list[tuple[Path, str]]:
    """Return prohibited retired-product identifiers in distributable files."""
    return find_identity_leaks(ROOT)


def included_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if any(part.casefold() in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.casefold() in EXCLUDED_SUFFIXES:
            continue
        if path.name.casefold().startswith(".env"):
            continue
        if path.name.casefold() == "manifest.sha256":
            continue
        if path.name.casefold() == "hsptl_bundle.txt":
            continue
        if path.name.casefold().endswith((".sqlite-wal", ".sqlite-shm", ".sqlite3-wal", ".sqlite3-shm")):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix().casefold())


def app_version() -> str:
    source = CONFIG.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if not match:
        raise ValueError(f"APP_VERSION was not found in {CONFIG.relative_to(ROOT)}")
    return match.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a source ZIP for HSPTL.")
    parser.add_argument("--dry-run", action="store_true", help="List included files without creating an archive.")
    parser.add_argument("--force", action="store_true", help="Allow packaging when legacy files are present.")
    parser.add_argument("--require-verify", action="store_true", help="Run scripts/verify_release.py first.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an archive with the same version name.")
    args = parser.parse_args()

    if args.require_verify:
        result = subprocess.run(
            [VERIFY_PYTHON, str(ROOT / "scripts" / "verify_release.py")],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            print("Packaging stopped: release verification failed.")
            return result.returncode

    blockers = legacy_paths()
    if blockers and not args.force:
        print("Packaging blocked by legacy files/directories:")
        for path, marker in blockers:
            print(f"  {path} ({marker})")
        print("Review and remove them manually, or use --force to override this check.")
        return 2

    try:
        version = app_version()
    except (OSError, ValueError) as exc:
        print(f"Packaging failed: {exc}")
        return 1

    files = included_files()
    if not files:
        print("Packaging failed: no source files were found.")
        return 1

    output_dir = ROOT / "dist"
    safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version)
    archive = output_dir / f"HSPTL-{safe_version}.zip"
    if archive.exists() and not (args.overwrite or args.dry_run):
        print(f"Archive already exists: {archive.relative_to(ROOT)}. Use --overwrite to replace it.")
        return 2

    print(f"HSPTL {version}: {len(files)} source files")
    if args.dry_run:
        for path in files:
            print(path.relative_to(ROOT).as_posix())
        print(f"Would create {archive.relative_to(ROOT)}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines = [
        f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in files
    ]
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for path in files:
            package.write(path, f"HSPTL/{path.relative_to(ROOT).as_posix()}")
        package.writestr(
            "HSPTL/MANIFEST.sha256",
            "\n".join(manifest_lines) + "\n",
        )

    print(f"Created {archive.relative_to(ROOT)}")
    print(f"SHA-256 manifest: {len(manifest_lines)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
