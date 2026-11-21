"""Application settings and safe path discovery for HSPTL."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any

APP_NAME = "HSPTL"
APP_VERSION = "6.0.0"
PACKAGE_DIR = Path(__file__).resolve().parents[1]

# The loopback port is the one setting shared by the Windows launchers, the Vite
# dev proxy and the scheduler helper. HSPTL_PORT overrides it; keep the default
# here so the launchers never hardcode a number of their own.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
PORT_ENV_VAR = "HSPTL_PORT"
DEFAULT_DEV_PORT = 5173
DEV_PORT_ENV_VAR = "HSPTL_DEV_PORT"


def _validate_port(raw: int | str | None, *, name: str, default: int) -> int:
    if isinstance(raw, str):
        raw = raw.strip()
    if raw is None or raw == "":
        return default
    try:
        port = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a whole number, got {raw!r}.") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535, got {port}.")
    return port


def resolve_port(value: int | str | None = None) -> int:
    """Return the configured backend loopback port.

    ``value`` takes precedence; otherwise ``HSPTL_PORT`` is consulted. An
    invalid override raises ``ValueError`` rather than silently falling back,
    so a typo surfaces at launch instead of binding an unexpected port.
    """
    raw = value if value is not None else os.environ.get(PORT_ENV_VAR, "")
    return _validate_port(raw, name=PORT_ENV_VAR, default=DEFAULT_PORT)


def resolve_dev_port(value: int | str | None = None) -> int:
    """Return the configured Vite dev-server port (see ``resolve_port``)."""
    raw = value if value is not None else os.environ.get(DEV_PORT_ENV_VAR, "")
    return _validate_port(raw, name=DEV_PORT_ENV_VAR, default=DEFAULT_DEV_PORT)


_hsptl_home_env = os.environ.get("HSPTL_HOME", "").strip()
_wardx_home_env = os.environ.get("WARDX_HOME", "").strip()
_wardle_home_env = os.environ.get("WARDLE_HOME", "").strip()
_legacy_casedle_home_env = os.environ.get("CASEDLE_HOME", "").strip()
DEFAULT_USER_DIR = Path(_hsptl_home_env).expanduser() if _hsptl_home_env else Path.home() / "HSPTL"
LEGACY_USER_DIRS = [
    Path(_wardx_home_env).expanduser() if _wardx_home_env else Path.home() / "WardX",
    Path(_wardle_home_env).expanduser() if _wardle_home_env else Path.home() / "Wardle",
    Path(_legacy_casedle_home_env).expanduser() if _legacy_casedle_home_env else Path.home() / "Casedle",
]

RESOURCE_NAMES = [
    "Patient", "Encounter", "Condition", "Observation", "MedicationRequest",
    "Procedure", "DiagnosticReport", "AllergyIntolerance", "Immunization",
    "CarePlan", "CareTeam", "Device", "ImagingStudy", "Medication",
    "MedicationAdministration", "Organization", "Practitioner", "PractitionerRole",
    "Location", "Claim", "ExplanationOfBenefit", "DocumentReference", "Provenance",
    "SupplyDelivery",
]
CLINICAL_RESOURCES = [
    "Encounter", "Condition", "Observation", "MedicationRequest", "Procedure",
    "DiagnosticReport", "AllergyIntolerance", "Immunization", "CarePlan",
]
LINK_COLUMNS = {
    resource: ("patient.reference" if resource == "AllergyIntolerance" else "subject.reference")
    for resource in CLINICAL_RESOURCES
}
DATE_COLUMNS = {
    "Encounter": ["period.start", "period.end"],
    "Condition": ["onsetDateTime", "recordedDate", "onsetPeriod.start", "abatementDateTime"],
    "Observation": ["effectiveDateTime", "issued", "effectivePeriod.start"],
    "MedicationRequest": ["authoredOn"],
    "Procedure": ["performedDateTime", "performedPeriod.start", "performedPeriod.end"],
    "DiagnosticReport": ["effectiveDateTime", "issued"],
    "AllergyIntolerance": ["recordedDate", "onsetDateTime"],
    "Immunization": ["occurrenceDateTime"],
    "CarePlan": ["period.start", "created"],
}
DISPLAY_COLUMNS = {
    "Encounter": ["type", "reasonCode", "class.code", "status"],
    "Condition": ["code.text", "clinicalStatus.text", "onsetDateTime", "recordedDate"],
    "Observation": ["code.text", "valueQuantity.value", "valueQuantity.unit", "valueString", "valueCodeableConcept.text", "effectiveDateTime"],
    "MedicationRequest": ["medicationCodeableConcept.text", "medicationReference.display", "authoredOn", "status", "dosageInstruction.text"],
    "Procedure": ["code.text", "performedDateTime", "performedPeriod.start", "status"],
    "DiagnosticReport": ["code.text", "effectiveDateTime", "conclusion", "status"],
    "AllergyIntolerance": ["code.text", "criticality", "category", "recordedDate"],
    "Immunization": ["vaccineCode.text", "occurrenceDateTime", "status"],
    "CarePlan": ["title", "description", "status", "created"],
}

DEFAULT_SOURCE_DIRS = [
    Path.home() / "YouseCodes" / "Synthea" / "output" / "fhir",
    Path.home() / "YouseCodes" / "Synthea" / "analysis_csv",
    Path.cwd() / "analysis_csv",
]


def _copy_missing_tree(source: Path, destination: Path) -> None:
    """Copy legacy user files without overwriting existing HSPTL data."""
    if not source.is_dir():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name in {"casedle.sqlite3", "casedle.sqlite3-wal", "casedle.sqlite3-shm", "wardle.sqlite3", "wardle.sqlite3-wal", "wardle.sqlite3-shm", "wardx.sqlite3", "wardx.sqlite3-wal", "wardx.sqlite3-shm", "hsptl.sqlite3", "hsptl.sqlite3-wal", "hsptl.sqlite3-shm"}:
            continue
        target = destination / item.name
        if target.exists():
            if item.is_dir() and target.is_dir():
                _copy_missing_tree(item, target)
            continue
        try:
            if item.is_dir():
                shutil.copytree(item, target)
            elif item.is_file():
                shutil.copy2(item, target)
        except OSError:
            # Keep startup usable; the untouched legacy folder remains available for manual recovery.
            continue


def _migrate_legacy_user_data(target_root: Path) -> None:
    """Preserve previous WardX/Wardle/Casedle progress and imports on first HSPTL launch.

    The old folder is never deleted. SQLite's backup API is used so committed
    transactions are copied safely even if the legacy DB used WAL journaling.
    """
    sources: list[Path] = []
    for source in LEGACY_USER_DIRS:
        try:
            resolved = source.resolve()
            if resolved != target_root.resolve() and resolved.is_dir() and resolved not in sources:
                sources.append(resolved)
        except OSError:
            continue

    if not sources:
        return

    target_root.mkdir(parents=True, exist_ok=True)
    target_db = target_root / "hsptl.sqlite3"

    for source in sources:
        _copy_missing_tree(source, target_root)
        legacy_candidates = [source / "wardx.sqlite3", source / "wardle.sqlite3", source / "casedle.sqlite3"]
        legacy_db = next((candidate for candidate in legacy_candidates if candidate.is_file()), None)
        if legacy_db is not None and not target_db.exists():
            source_conn = None
            target_conn = None
            try:
                source_conn = sqlite3.connect(str(legacy_db), timeout=10)
                target_conn = sqlite3.connect(str(target_db), timeout=10)
                source_conn.backup(target_conn)
                target_conn.commit()
            except sqlite3.Error:
                try:
                    target_db.unlink(missing_ok=True)
                except OSError:
                    pass
            finally:
                if target_conn is not None:
                    target_conn.close()
                if source_conn is not None:
                    source_conn.close()


def ensure_user_dirs() -> dict[str, Path]:
    root = DEFAULT_USER_DIR
    _migrate_legacy_user_data(root)
    paths = {
        "root": root,
        "database": root / "hsptl.sqlite3",
        "imports": root / "imports",
        "references": root / "references",
        "logs": root / "logs",
        "settings": root / "settings.json",
    }
    for key in ("root", "imports", "references", "logs"):
        paths[key].mkdir(parents=True, exist_ok=True)
    return paths


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or ensure_user_dirs()["settings"]
    defaults: dict[str, Any] = {
        "dataset_dirs": [],
        "reference_dirs": [],
        "theme": "light",
        "last_selected_case": None,
        "last_workspace": "Clinic",
    }
    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            defaults.update(raw)
    except (OSError, json.JSONDecodeError):
        pass
    if not isinstance(defaults.get("dataset_dirs"), list):
        defaults["dataset_dirs"] = []
    if not isinstance(defaults.get("reference_dirs"), list):
        defaults["reference_dirs"] = []
    return defaults


def save_settings(settings: dict[str, Any], path: Path | None = None) -> None:
    settings_path = path or ensure_user_dirs()["settings"]
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temp = settings_path.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(settings_path)


def discover_dataset_dirs(settings: dict[str, Any] | None = None) -> list[Path]:
    settings = settings or load_settings()
    candidates: list[Path] = []
    env_dir = os.environ.get("SYNTHEA_CSV_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir).expanduser())
    for item in settings.get("dataset_dirs", []):
        candidates.append(Path(str(item)).expanduser())
    candidates.extend(DEFAULT_SOURCE_DIRS)
    found: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).casefold()
        if key in seen or not resolved.is_dir():
            continue
        try:
            stems = {p.stem.casefold() for p in resolved.glob("*.csv")}
            has_patient_csv = bool(stems.intersection({"patient", "patients"}))
            has_fhir_patient = False
            if not has_patient_csv:
                # Inspect a bounded sample only; full resource parsing belongs to the importer.
                json_files = resolved.glob("*.json")
                for index, file in enumerate(json_files):
                    if index >= 20:
                        break
                    try:
                        payload = json.loads(file.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if isinstance(payload, dict) and payload.get("resourceType") == "Patient":
                        has_fhir_patient = True
                        break
                    if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
                        if any(isinstance(entry, dict) and isinstance(entry.get("resource"), dict)
                               and entry["resource"].get("resourceType") == "Patient"
                               for entry in payload.get("entry", [])[:500]):
                            has_fhir_patient = True
                            break
        except OSError:
            continue
        if has_patient_csv or has_fhir_patient:
            seen.add(key)
            found.append(resolved)
    return found
