"""Read-only Local Folder Source Manager.

Safety model, in order of enforcement:

1. **Allowlisted roots only.** A scan target is a ``root_id`` that already exists
   in the local registry. No HTTP endpoint accepts a filesystem path for reading;
   adding a root is an explicit local administration action.
2. **Containment.** Every candidate is resolved with ``realpath`` and must remain
   beneath the resolved root. Symlinks are never followed during the walk, and a
   symlinked file that resolves outside the root is refused rather than read.
3. **No special files.** Devices, FIFOs, sockets, junctions/reparse points and
   hardlinked files are skipped or flagged, never opened.
4. **Bounded reads.** Size is checked from ``stat`` before any bytes are read, so
   an oversized or sparse file cannot exhaust memory. Archive expansion is
   capped by entry count, total uncompressed size and compression ratio.
5. **No execution.** Only text extraction runs. Macros, embedded scripts, HTML
   and document attachments are never executed or followed.
6. **Identifier screening.** Extracted text is screened for direct identifiers
   and quarantined rather than imported when any are found.

Everything is read-only: the manager never writes to, renames or deletes
anything inside a configured root.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .ucks_files import SUPPORTED_EXTENSIONS, extract_text

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_SCAN = 5_000
MAX_TOTAL_BYTES_PER_SCAN = 512 * 1024 * 1024
MAX_PATH_DEPTH = 24
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar"}
# Archive safety caps, applied only if archive handling is explicitly enabled.
MAX_ARCHIVE_ENTRIES = 500
MAX_ARCHIVE_UNCOMPRESSED = 64 * 1024 * 1024
MAX_ARCHIVE_RATIO = 100

SKIP_NAMES = {".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
              "System Volume Information", "$RECYCLE.BIN", ".Trash", ".DS_Store"}

# Extensions that can carry active content. Never opened, never extracted.
ACTIVE_CONTENT_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".dotm", ".xlam", ".exe", ".dll",
                             ".js", ".jse", ".vbs", ".vbe", ".wsf", ".wsh", ".hta", ".scr",
                             ".ps1", ".bat", ".cmd", ".com", ".pif", ".msi", ".lnk", ".url",
                             ".html", ".htm", ".xhtml", ".svg", ".swf", ".jar"}


class LocalSourceError(ValueError):
    """Raised when a local-source operation is refused for safety."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_" + uuid.uuid4().hex


# --------------------------------------------------------------------------- #
# Identifier screening
# --------------------------------------------------------------------------- #

def _nhs_number_valid(candidate: str) -> bool:
    """Modulus-11 check digit for a 10-digit NHS number."""
    digits = [int(ch) for ch in candidate]
    if len(digits) != 10:
        return False
    total = sum(digits[i] * (10 - i) for i in range(9))
    check = 11 - (total % 11)
    if check == 11:
        check = 0
    if check == 10:
        return False
    return check == digits[9]


_IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("nhs_number", re.compile(r"\b(\d{3})[ -]?(\d{3})[ -]?(\d{4})\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")),
    ("uk_postcode", re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b")),
    ("phone_uk", re.compile(r"\b(?:\+44\s?|0)(?:\d[\s-]?){9,10}\b")),
    ("mrn", re.compile(r"\b(?:MRN|Hospital\s*(?:No|Number)|Patient\s*ID)\s*[:#]?\s*[A-Z0-9]{4,12}\b", re.I)),
    ("dob_label", re.compile(r"\b(?:DOB|Date\s+of\s+Birth)\s*[:]?\s*\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b", re.I)),
    ("nino", re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b")),
    ("address_line", re.compile(r"\b\d{1,4}\s+[A-Z][a-z]+\s+(?:Road|Street|Avenue|Lane|Close|Drive|Way|Court|Place)\b")),
)


def screen_for_identifiers(text: str) -> dict[str, Any]:
    """Detect direct identifiers in extracted text.

    Returns the findings and a verdict. NHS numbers are checksum-verified so a
    ten-digit lab value is not mistaken for an identifier. Any match blocks the
    import: HSPTL has no institutional de-identification workflow, so the safe
    action is to quarantine rather than guess.
    """
    findings: list[dict[str, Any]] = []
    for kind, pattern in _IDENTIFIER_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            if kind == "nhs_number":
                digits = re.sub(r"\D", "", raw)
                if not _nhs_number_valid(digits):
                    continue
                raw = digits
            findings.append({
                "kind": kind,
                "match_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
                "position": match.start(),
            })
    kinds = sorted({item["kind"] for item in findings})
    return {
        "verdict": "quarantine" if findings else "clear",
        "finding_count": len(findings),
        "kinds": kinds,
        "findings": findings[:50],
        "note": ("Direct identifiers found. HSPTL has no approved de-identification workflow, "
                 "so the file is quarantined and not imported.") if findings else
                "No direct identifiers detected by pattern screening. Screening is not de-identification.",
    }


# --------------------------------------------------------------------------- #
# Containment helpers
# --------------------------------------------------------------------------- #

def _is_inside(root: Path, candidate: Path) -> bool:
    try:
        root_resolved = root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    if candidate_resolved == root_resolved:
        return True
    try:
        candidate_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _is_reparse_point(entry: os.DirEntry[str]) -> bool:
    """Detect Windows junctions/reparse points without following them."""
    try:
        is_junction = getattr(entry, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
    except OSError:
        return True
    try:
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    file_attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(file_attributes & reparse_flag)


def _hardlink_count(path: Path, stat_result: os.stat_result) -> int | None:
    """Return a trustworthy hard-link count, including on Windows.

    POSIX exposes the count directly through ``st_nlink``. On Windows, query
    the file handle as well so filesystems/runtime combinations that report a
    lossy ``DirEntry.stat`` result cannot silently bypass the source-scan guard.
    A failed Windows metadata query is treated as unknown and the caller fails
    closed rather than opening the file.
    """
    stat_count = int(getattr(stat_result, "st_nlink", 1) or 1)
    if os.name != "nt":
        return stat_count

    try:
        import ctypes
        from ctypes import wintypes

        class _FileTime(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD),
            ]

        class _ByHandleFileInformation(ctypes.Structure):
            _fields_ = [
                ("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", _FileTime),
                ("ftLastAccessTime", _FileTime),
                ("ftLastWriteTime", _FileTime),
                ("dwVolumeSerialNumber", wintypes.DWORD),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("nNumberOfLinks", wintypes.DWORD),
                ("nFileIndexHigh", wintypes.DWORD),
                ("nFileIndexLow", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        get_info = kernel32.GetFileInformationByHandle
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation)]
        get_info.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        # FILE_READ_ATTRIBUTES; permit concurrent readers/writers/deletion;
        # OPEN_EXISTING; OPEN_REPARSE_POINT prevents following a swapped link.
        handle = create_file(
            str(path), 0x80, 0x1 | 0x2 | 0x4, None, 3, 0x00200000, None,
        )
        if handle == ctypes.c_void_p(-1).value:
            return None
        try:
            details = _ByHandleFileInformation()
            if not get_info(handle, ctypes.byref(details)):
                return None
            return max(stat_count, int(details.nNumberOfLinks))
        finally:
            close_handle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def validate_root(path: str | Path) -> Path:
    """Validate a candidate allowlisted root before it is ever registered."""
    try:
        candidate = Path(path).expanduser()
    except (TypeError, ValueError) as exc:
        raise LocalSourceError("The supplied path is not a usable filesystem path") from exc
    if not candidate.is_absolute():
        raise LocalSourceError("A source root must be an absolute path")
    if candidate.is_symlink():
        raise LocalSourceError("A source root must not itself be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise LocalSourceError("The source root does not exist or cannot be resolved") from exc
    if not resolved.is_dir():
        raise LocalSourceError("A source root must be a directory")
    if resolved == Path(resolved.anchor):
        raise LocalSourceError("A filesystem root cannot be used as a source root")
    # Refusing the home directory and system directories prevents an accidental
    # blanket scan of unrelated personal or operating-system files.
    home = Path.home().resolve()
    if resolved == home:
        raise LocalSourceError("The user home directory cannot be used as a source root; choose a subfolder")
    for forbidden in (Path("/etc"), Path("/usr"), Path("/bin"), Path("/sbin"),
                      Path("/var"), Path("/boot"), Path("/proc"), Path("/sys"), Path("/dev")):
        if resolved == forbidden:
            raise LocalSourceError(f"{forbidden} cannot be used as a source root")
    return resolved


@dataclass(slots=True)
class ScanCandidate:
    relative_path: str
    absolute_path: Path
    size_bytes: int
    extension: str
    verdict: str = "pending"  # accepted | skipped | quarantined | refused
    reason: str = ""
    sha256: str = ""
    extracted_chars: int = 0
    identifier_screening: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "extension": self.extension,
            "verdict": self.verdict,
            "reason": self.reason,
            "sha256": self.sha256,
            "extracted_chars": self.extracted_chars,
            "identifier_screening": self.identifier_screening,
        }


def _archive_is_safe(path: Path) -> tuple[bool, str]:
    """Bounded archive inspection. Never extracts; reads the central directory only."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return False, "archive_unreadable"
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        return False, f"archive_entry_count_exceeds_{MAX_ARCHIVE_ENTRIES}"
    total_uncompressed = sum(info.file_size for info in infos)
    total_compressed = sum(max(info.compress_size, 1) for info in infos)
    if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED:
        return False, "archive_uncompressed_size_exceeds_limit"
    if total_compressed and total_uncompressed / total_compressed > MAX_ARCHIVE_RATIO:
        return False, "archive_compression_ratio_suggests_bomb"
    for info in infos:
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            return False, "archive_entry_escapes_root"
    return True, "archive_within_bounds"


def walk_root(root: Path, *, max_files: int = MAX_FILES_PER_SCAN,
              allow_archives: bool = False) -> tuple[list[ScanCandidate], list[dict[str, Any]]]:
    """Enumerate candidates beneath a validated root without following links.

    Returns the candidates and a list of refusals, so the caller can report what
    was deliberately not read rather than silently ignoring it.
    """
    candidates: list[ScanCandidate] = []
    refusals: list[dict[str, Any]] = []
    total_bytes = 0

    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if depth > MAX_PATH_DEPTH:
            refusals.append({"path": str(directory), "reason": "max_depth_exceeded"})
            continue
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            refusals.append({"path": str(directory), "reason": f"unreadable_directory: {exc.errno}"})
            continue
        for entry in sorted(entries, key=lambda e: e.name):
            name = entry.name
            if name in SKIP_NAMES:
                continue
            try:
                if entry.is_symlink() or _is_reparse_point(entry):
                    refusals.append({"path": entry.path, "reason": "symlink_or_reparse_point_not_followed"})
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append((Path(entry.path), depth + 1))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    refusals.append({"path": entry.path, "reason": "not_a_regular_file"})
                    continue
                info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                refusals.append({"path": entry.path, "reason": f"stat_failed: {exc.errno}"})
                continue

            absolute = Path(entry.path)
            if not _is_inside(root, absolute):
                refusals.append({"path": entry.path, "reason": "resolves_outside_root"})
                continue
            link_count = _hardlink_count(absolute, info)
            if link_count is None:
                refusals.append({"path": entry.path, "reason": "file_link_count_unavailable"})
                continue
            if link_count > 1:
                # A hardlink can alias a file outside the root.
                refusals.append({"path": entry.path, "reason": "hardlinked_file_not_read"})
                continue

            extension = absolute.suffix.lower()
            relative = str(absolute.relative_to(root))
            if extension in ACTIVE_CONTENT_EXTENSIONS:
                candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                "refused", "active_content_never_opened"))
                continue
            if extension in ARCHIVE_EXTENSIONS:
                if not allow_archives:
                    candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                    "refused", "archive_handling_disabled"))
                    continue
                safe, reason = _archive_is_safe(absolute)
                if not safe:
                    candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                    "refused", reason))
                    continue
                candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                "refused", "archive_validated_but_extraction_not_performed"))
                continue
            if extension not in SUPPORTED_EXTENSIONS:
                candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                "skipped", "unsupported_extension"))
                continue
            if info.st_size > MAX_FILE_BYTES:
                candidates.append(ScanCandidate(relative, absolute, info.st_size, extension,
                                                "refused", "file_exceeds_size_limit"))
                continue
            total_bytes += info.st_size
            if total_bytes > MAX_TOTAL_BYTES_PER_SCAN:
                refusals.append({"path": str(absolute), "reason": "scan_total_byte_budget_exhausted"})
                stack.clear()
                break
            candidates.append(ScanCandidate(relative, absolute, info.st_size, extension))
            if len(candidates) >= max_files:
                refusals.append({"path": str(root), "reason": "max_files_per_scan_reached"})
                stack.clear()
                break
    return candidates, refusals


def read_candidate(candidate: ScanCandidate) -> dict[str, Any]:
    """Read and screen one candidate. Never writes to the source file."""
    if candidate.verdict in {"refused", "skipped"}:
        return candidate.to_dict()
    try:
        # Re-check size immediately before reading to narrow the race window.
        if candidate.absolute_path.stat().st_size > MAX_FILE_BYTES:
            candidate.verdict, candidate.reason = "refused", "file_grew_beyond_size_limit"
            return candidate.to_dict()
        content = candidate.absolute_path.read_bytes()
    except OSError as exc:
        candidate.verdict, candidate.reason = "skipped", f"read_failed: {exc.errno}"
        return candidate.to_dict()
    candidate.sha256 = hashlib.sha256(content).hexdigest()
    try:
        text, _metadata = extract_text(candidate.absolute_path.name, content)
    except ValueError as exc:
        candidate.verdict, candidate.reason = "skipped", f"extraction_failed: {exc}"
        return candidate.to_dict()
    screening = screen_for_identifiers(text)
    candidate.identifier_screening = screening
    candidate.extracted_chars = len(text)
    if screening["verdict"] == "quarantine":
        candidate.verdict, candidate.reason = "quarantined", "direct_identifiers_detected"
        return candidate.to_dict()
    if not text.strip():
        candidate.verdict, candidate.reason = "skipped", "no_extractable_text"
        return candidate.to_dict()
    candidate.verdict, candidate.reason = "accepted", "text_extracted"
    return candidate.to_dict()


class LocalSourceManager:
    """Registry, scanner and scheduler for allowlisted local folders."""

    JOB_KIND = "local_source_rescan"

    def __init__(self, store, *, labels=None, registry=None):
        self.store = store
        self.labels = labels
        self.registry = registry
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS local_source_roots (
                root_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                path TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                recursive INTEGER NOT NULL DEFAULT 1,
                allow_archives INTEGER NOT NULL DEFAULT 0,
                include_pattern TEXT NOT NULL DEFAULT '',
                registered_by TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(path)
            );
            CREATE TABLE IF NOT EXISTS local_source_scans (
                scan_id TEXT PRIMARY KEY,
                root_id TEXT NOT NULL REFERENCES local_source_roots(root_id),
                status TEXT NOT NULL,
                trigger TEXT NOT NULL DEFAULT 'manual',
                files_seen INTEGER NOT NULL DEFAULT 0,
                accepted INTEGER NOT NULL DEFAULT 0,
                quarantined INTEGER NOT NULL DEFAULT 0,
                refused INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                total_bytes INTEGER NOT NULL DEFAULT 0,
                findings_json TEXT NOT NULL DEFAULT '{}',
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_local_scans_root ON local_source_scans(root_id, started_at DESC);
            CREATE TABLE IF NOT EXISTS local_source_files (
                file_id TEXT PRIMARY KEY,
                root_id TEXT NOT NULL REFERENCES local_source_roots(root_id),
                relative_path TEXT NOT NULL,
                sha256 TEXT NOT NULL DEFAULT '',
                size_bytes INTEGER NOT NULL DEFAULT 0,
                verdict TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                label TEXT NOT NULL DEFAULT 'IMPORTED CONTENT',
                label_item_id TEXT NOT NULL DEFAULT '',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                UNIQUE(root_id, relative_path)
            );
            CREATE INDEX IF NOT EXISTS idx_local_files_verdict ON local_source_files(verdict, last_seen DESC);
            CREATE TABLE IF NOT EXISTS local_source_schedule (
                root_id TEXT PRIMARY KEY REFERENCES local_source_roots(root_id),
                enabled INTEGER NOT NULL DEFAULT 0,
                interval_minutes INTEGER NOT NULL DEFAULT 1440,
                next_run TEXT NOT NULL DEFAULT '',
                last_attempt TEXT NOT NULL DEFAULT '',
                lease_until TEXT NOT NULL DEFAULT '',
                consecutive_failures INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_local_schedule_due ON local_source_schedule(enabled, next_run);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(32, ?)", (_now(),)
            )

    # -- roots ------------------------------------------------------------ #

    def register_root(self, *, path: str, label: str, registered_by: str,
                      recursive: bool = True, allow_archives: bool = False,
                      include_pattern: str = "") -> dict[str, Any]:
        """Add an allowlisted root. Validation happens before anything is stored."""
        if not registered_by.strip():
            raise LocalSourceError("A named administrator is required to add a source root")
        resolved = validate_root(path)
        now = _now()
        root_id = _id("lsroot")
        with self.store.transaction() as conn:
            existing = conn.execute("SELECT root_id FROM local_source_roots WHERE path=?",
                                    (str(resolved),)).fetchone()
            if existing:
                return self.get_root(existing["root_id"])  # type: ignore[return-value]
            conn.execute(
                """INSERT INTO local_source_roots
                   (root_id,label,path,enabled,recursive,allow_archives,include_pattern,
                    registered_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (root_id, label.strip()[:200], str(resolved), 1, int(recursive),
                 int(allow_archives), include_pattern[:200], registered_by[:160], now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO local_source_schedule(root_id,enabled,interval_minutes,next_run,updated_at)"
                " VALUES(?,?,?,?,?)", (root_id, 0, 1440, "", now),
            )
        return self.get_root(root_id)  # type: ignore[return-value]

    def get_root(self, root_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM local_source_roots WHERE root_id=?", (root_id,)).fetchone()
            if row is None:
                return None
            schedule = conn.execute("SELECT * FROM local_source_schedule WHERE root_id=?",
                                    (root_id,)).fetchone()
        record = dict(row)
        for key in ("enabled", "recursive", "allow_archives"):
            record[key] = bool(record[key])
        record["schedule"] = dict(schedule) if schedule else None
        if record["schedule"]:
            record["schedule"]["enabled"] = bool(record["schedule"]["enabled"])
        return record

    def list_roots(self) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            ids = [row["root_id"] for row in conn.execute(
                "SELECT root_id FROM local_source_roots ORDER BY label")]
        return [item for item in (self.get_root(rid) for rid in ids) if item]

    def set_enabled(self, root_id: str, enabled: bool) -> dict[str, Any]:
        with self.store.transaction() as conn:
            conn.execute("UPDATE local_source_roots SET enabled=?, updated_at=? WHERE root_id=?",
                         (int(enabled), _now(), root_id))
        record = self.get_root(root_id)
        if record is None:
            raise LocalSourceError("Unknown local source root")
        return record

    # -- scheduling ------------------------------------------------------- #

    def configure_schedule(self, root_id: str, *, enabled: bool, interval_minutes: int = 1440) -> dict[str, Any]:
        interval = max(15, min(int(interval_minutes), 10080))
        now = _now()
        next_run = now if enabled else ""
        with self.store.transaction() as conn:
            if conn.execute("SELECT 1 FROM local_source_roots WHERE root_id=?", (root_id,)).fetchone() is None:
                raise LocalSourceError("Unknown local source root")
            conn.execute(
                """INSERT INTO local_source_schedule(root_id,enabled,interval_minutes,next_run,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(root_id) DO UPDATE SET enabled=excluded.enabled,
                     interval_minutes=excluded.interval_minutes, next_run=excluded.next_run,
                     updated_at=excluded.updated_at""",
                (root_id, int(enabled), interval, next_run, now),
            )
        return self.get_root(root_id)  # type: ignore[return-value]

    def claim_due_roots(self, *, lease_seconds: int = 300, limit: int = 20) -> list[str]:
        """Lease-based claim so two workers cannot rescan the same root at once."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat(timespec="seconds")
        lease_until = (now.timestamp() + lease_seconds)
        claimed: list[str] = []
        with self.store.transaction() as conn:
            rows = conn.execute(
                """SELECT s.root_id FROM local_source_schedule s
                   JOIN local_source_roots r ON r.root_id=s.root_id
                   WHERE s.enabled=1 AND r.enabled=1
                     AND (s.next_run='' OR s.next_run<=?)
                     AND (s.lease_until='' OR s.lease_until<=?)
                   ORDER BY s.next_run LIMIT ?""",
                (now_iso, now_iso, max(1, min(int(limit), 100))),
            ).fetchall()
            for row in rows:
                from datetime import timedelta
                until = (now + timedelta(seconds=lease_seconds)).isoformat(timespec="seconds")
                conn.execute(
                    "UPDATE local_source_schedule SET lease_until=?, last_attempt=? WHERE root_id=?",
                    (until, now_iso, row["root_id"]),
                )
                claimed.append(row["root_id"])
        return claimed

    def complete_schedule(self, root_id: str, *, success: bool, interval_minutes: int | None = None) -> dict[str, Any]:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM local_source_schedule WHERE root_id=?", (root_id,)).fetchone()
            if row is None:
                raise LocalSourceError("Unknown local source schedule")
            interval = int(interval_minutes or row["interval_minutes"] or 1440)
            failures = 0 if success else int(row["consecutive_failures"]) + 1
            # Back off on repeated failure instead of hammering a broken path.
            delay = interval if success else min(interval * (2 ** min(failures, 6)), 10080)
            next_run = (now + timedelta(minutes=delay)).isoformat(timespec="seconds")
            conn.execute(
                """UPDATE local_source_schedule SET next_run=?, lease_until='',
                   consecutive_failures=?, updated_at=? WHERE root_id=?""",
                (next_run, failures, now.isoformat(timespec="seconds"), root_id),
            )
        return self.get_root(root_id)  # type: ignore[return-value]

    # -- scanning --------------------------------------------------------- #

    def scan(self, root_id: str, *, trigger: str = "manual", persist: bool = True) -> dict[str, Any]:
        """Read-only scan of one allowlisted root."""
        root_record = self.get_root(root_id)
        if root_record is None:
            raise LocalSourceError("Unknown local source root")
        if not root_record["enabled"] and trigger != "manual":
            raise LocalSourceError("This source root is disabled")
        root_path = Path(root_record["path"])
        if not _is_inside(root_path, root_path) or not root_path.is_dir():
            raise LocalSourceError("The configured source root is no longer available")

        candidates, refusals = walk_root(
            root_path,
            allow_archives=bool(root_record["allow_archives"]),
        )
        results = [read_candidate(candidate) for candidate in candidates]
        accepted = [r for r in results if r["verdict"] == "accepted"]
        quarantined = [r for r in results if r["verdict"] == "quarantined"]
        refused = [r for r in results if r["verdict"] == "refused"]
        skipped = [r for r in results if r["verdict"] == "skipped"]

        scan_id = _id("lsscan")
        started = _now()
        findings = {
            "identifier_kinds": sorted({k for r in quarantined
                                        for k in (r.get("identifier_screening") or {}).get("kinds", [])}),
            "refusals": refusals[:200],
            "refusal_count": len(refusals),
            "accepted_paths": [r["relative_path"] for r in accepted][:200],
            "quarantined_paths": [r["relative_path"] for r in quarantined][:200],
        }
        if persist:
            with self.store.transaction() as conn:
                conn.execute(
                    """INSERT INTO local_source_scans
                       (scan_id,root_id,status,trigger,files_seen,accepted,quarantined,refused,skipped,
                        total_bytes,findings_json,started_at,completed_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (scan_id, root_id, "completed", trigger, len(results), len(accepted),
                     len(quarantined), len(refused), len(skipped),
                     sum(int(r["size_bytes"]) for r in results),
                     json.dumps(findings, ensure_ascii=False), started, _now()),
                )
                for result in results:
                    conn.execute(
                        """INSERT INTO local_source_files
                           (file_id,root_id,relative_path,sha256,size_bytes,verdict,reason,label,
                            label_item_id,first_seen,last_seen)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(root_id, relative_path) DO UPDATE SET
                             sha256=excluded.sha256, size_bytes=excluded.size_bytes,
                             verdict=excluded.verdict, reason=excluded.reason,
                             last_seen=excluded.last_seen""",
                        (_id("lsfile"), root_id, result["relative_path"], result["sha256"],
                         int(result["size_bytes"]), result["verdict"], result["reason"],
                         "IMPORTED CONTENT", "", started, _now()),
                    )
            self._label_scan_results(root_id, results)

        return {
            "scan_id": scan_id,
            "root_id": root_id,
            "root_path": str(root_path),
            "status": "completed",
            "trigger": trigger,
            "counts": {
                "seen": len(results),
                "accepted": len(accepted),
                "quarantined": len(quarantined),
                "refused": len(refused),
                "skipped": len(skipped),
                "refusals_outside_candidates": len(refusals),
            },
            "findings": findings,
            "files": results,
            "note": ("Scanning is read-only. Nothing in the source folder is modified, moved or deleted."),
        }

    def _label_scan_results(self, root_id: str, results: list[dict[str, Any]]) -> None:
        """Give every accepted file an IMPORTED CONTENT label with provenance."""
        if self.labels is None:
            return
        from .content_labels import LABEL_IMPORTED, LabelledContent, content_hash
        for result in results:
            if result["verdict"] != "accepted" or not result["sha256"]:
                continue
            try:
                self.labels.register(LabelledContent(
                    label=LABEL_IMPORTED,
                    title=result["relative_path"],
                    content_hash=content_hash(result["sha256"]),
                    workspace="local_sources",
                    content_type=result["extension"].lstrip(".") or "other",
                    rights_status="unknown",
                    metadata={"root_id": root_id, "relative_path": result["relative_path"],
                              "size_bytes": result["size_bytes"],
                              "screened_for_identifiers": True},
                ))
            except Exception:
                # Labelling must never abort a scan; the scan result itself records the file.
                continue

    # -- reads ------------------------------------------------------------ #

    def latest_scan(self, root_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM local_source_scans WHERE root_id=? ORDER BY started_at DESC LIMIT 1",
                (root_id,),
            ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["findings"] = json.loads(record.pop("findings_json") or "{}")
        return record

    def files(self, *, root_id: str = "", verdict: str = "", limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT * FROM local_source_files WHERE 1=1"
        params: list[Any] = []
        if root_id:
            sql += " AND root_id=?"
            params.append(root_id)
        if verdict:
            sql += " AND verdict=?"
            params.append(verdict)
        sql += " ORDER BY last_seen DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))
        with self.store.transaction() as conn:
            return [dict(row) for row in conn.execute(sql, params)]

    def summary(self) -> dict[str, Any]:
        with self.store.transaction() as conn:
            roots = conn.execute("SELECT COUNT(*) AS n FROM local_source_roots").fetchone()["n"]
            scans = conn.execute("SELECT COUNT(*) AS n FROM local_source_scans").fetchone()["n"]
            verdicts = {row["verdict"]: row["n"] for row in conn.execute(
                "SELECT verdict, COUNT(*) AS n FROM local_source_files GROUP BY verdict")}
            scheduled = conn.execute(
                "SELECT COUNT(*) AS n FROM local_source_schedule WHERE enabled=1").fetchone()["n"]
        return {
            "roots": int(roots),
            "scheduled_roots": int(scheduled),
            "scans": int(scans),
            "files_by_verdict": verdicts,
            "quarantined": int(verdicts.get("quarantined", 0)),
            "safety": {
                "read_only": True,
                "follows_symlinks": False,
                "opens_active_content": False,
                "max_file_bytes": MAX_FILE_BYTES,
                "max_files_per_scan": MAX_FILES_PER_SCAN,
                "arbitrary_paths_over_http": False,
            },
        }


def register_rescan_job(jobs, manager: LocalSourceManager) -> None:
    """Register the scheduled rescan on the existing durable JobRunner."""

    def rescan(payload: dict, checkpoint) -> dict:
        claimed = manager.claim_due_roots()
        checkpoint({"phase": "rescan_started", "roots": len(claimed)})
        completed, failed = [], []
        for root_id in claimed:
            try:
                result = manager.scan(root_id, trigger="schedule")
                manager.complete_schedule(root_id, success=True)
                completed.append({"root_id": root_id, "counts": result["counts"]})
            except Exception as exc:  # noqa: BLE001 - one bad root must not stop the sweep
                manager.complete_schedule(root_id, success=False)
                failed.append({"root_id": root_id, "error": type(exc).__name__})
        return {"scanned": len(completed), "failed": len(failed),
                "completed": completed, "failures": failed}

    jobs.register(LocalSourceManager.JOB_KIND, rescan)
