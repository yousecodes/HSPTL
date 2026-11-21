"""Factory settings, prerequisite preflight and the safe Synthea process adapter.

Two rules shape this module:

* Nothing is downloaded. A generation run never fetches a JAR, an
  implementation guide or a terminology package. Artifacts must already exist
  locally with a recorded SHA-256.
* No user input ever reaches a shell. The child process is started with an
  argument list and ``shell=False``; every value that becomes an argument is
  validated or coerced to an integer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

SETTINGS_KEY = "factory"
DEFAULT_MAX_HEAP_MB = 1792
DEFAULT_MIN_FREE_DISK_MB = 2048
MAX_POPULATION_CEILING = 5000


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path, *, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class FactorySettings:
    """Local, non-secret factory configuration.

    Paths are absolute because the user picks them in a local settings screen.
    They are validated as existing files before a job may run; they are never
    interpolated into a shell command.
    """

    synthea_jar: str = ""
    synthea_version: str = ""
    synthea_sha256: str = ""
    java_path: str = ""
    module_dir: str = ""
    config_file: str = ""
    validator_jar: str = ""
    validator_sha256: str = ""
    validator_version: str = ""
    package_cache: str = ""
    max_heap_mb: int = DEFAULT_MAX_HEAP_MB
    min_free_disk_mb: int = DEFAULT_MIN_FREE_DISK_MB
    strict_fhir_required: bool = False
    concurrency: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "FactorySettings":
        raw = raw or {}
        fields = cls.__dataclass_fields__
        kwargs = {key: raw[key] for key in fields if key in raw and not isinstance(raw[key], (dict, list))}
        settings = cls(**kwargs)
        settings.max_heap_mb = _bounded_int(settings.max_heap_mb, 256, 4096, DEFAULT_MAX_HEAP_MB)
        settings.min_free_disk_mb = _bounded_int(settings.min_free_disk_mb, 256, 51200, DEFAULT_MIN_FREE_DISK_MB)
        settings.concurrency = 1
        return settings


def _bounded_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    if isinstance(value, bool):
        return fallback
    return max(low, min(high, number))


def load_settings(conn_factory) -> FactorySettings:
    with conn_factory() as conn:
        row = conn.execute(
            "SELECT value_json FROM synthetic_factory_settings WHERE key=?", (SETTINGS_KEY,)
        ).fetchone()
    if row is None:
        return FactorySettings()
    try:
        return FactorySettings.from_dict(json.loads(row["value_json"]))
    except (ValueError, TypeError, KeyError):
        return FactorySettings()


def save_settings(conn_factory, settings: FactorySettings) -> FactorySettings:
    payload = json.dumps(settings.to_dict(), sort_keys=True, ensure_ascii=False)
    with conn_factory() as conn:
        conn.execute(
            "INSERT INTO synthetic_factory_settings(key, value_json, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
            (SETTINGS_KEY, payload, _now()),
        )
    return settings


@dataclass
class PreflightCheck:
    check_id: str
    ok: bool
    blocking: bool
    detail: str


@dataclass
class PreflightReport:
    checks: list[PreflightCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.ok or not item.blocking for item in self.checks)

    @property
    def blockers(self) -> list[PreflightCheck]:
        return [item for item in self.checks if not item.ok and item.blocking]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [asdict(item) for item in self.checks],
            "blockers": [asdict(item) for item in self.blockers],
        }


def detect_java(java_path: str) -> tuple[bool, str]:
    executable = java_path.strip() or ("java.exe" if os.name == "nt" else "java")
    try:
        result = subprocess.run(
            [executable, "-version"], capture_output=True, text=True, timeout=15, shell=False, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Java could not be executed: {exc}"
    output = (result.stderr or result.stdout or "").strip().splitlines()
    first = output[0] if output else ""
    if result.returncode != 0:
        return False, f"Java returned exit code {result.returncode}: {first[:160]}"
    return True, first[:160]


def free_disk_mb(path: Path) -> int:
    try:
        target = Path(path)
        while not target.exists() and target != target.parent:
            target = target.parent
        return int(shutil.disk_usage(target).free / (1024 * 1024))
    except OSError:
        return 0


def preflight(settings: FactorySettings, storage_root: Path, *,
              population: int, fhir: bool, csv: bool,
              require_validator: bool, generation_running: bool) -> PreflightReport:
    report = PreflightReport()

    jar = Path(settings.synthea_jar).expanduser() if settings.synthea_jar else None
    jar_ok = bool(jar and jar.is_file() and os.access(jar, os.R_OK))
    report.checks.append(PreflightCheck(
        "synthea_jar", jar_ok, True,
        f"Synthea artifact found: {jar}" if jar_ok else "Synthea JAR is not configured or is not a readable file.",
    ))

    if jar_ok and settings.synthea_sha256:
        try:
            actual = sha256_file(jar)  # type: ignore[arg-type]
        except OSError as exc:
            report.checks.append(PreflightCheck("synthea_checksum", False, True, f"Checksum could not be computed: {exc}"))
        else:
            match = actual.casefold() == settings.synthea_sha256.strip().casefold()
            report.checks.append(PreflightCheck(
                "synthea_checksum", match, True,
                "Synthea checksum matches the pinned value." if match
                else "Synthea SHA-256 does not match the pinned checksum.",
            ))
    else:
        report.checks.append(PreflightCheck(
            "synthea_checksum", False, True,
            "A pinned SHA-256 for the Synthea artifact is required; unpinned generators fail closed.",
        ))

    version_ok = bool(settings.synthea_version.strip())
    report.checks.append(PreflightCheck(
        "synthea_version", version_ok, True,
        f"Pinned Synthea version: {settings.synthea_version}" if version_ok
        else "An exact Synthea version or commit identifier is required.",
    ))

    java_ok, java_detail = detect_java(settings.java_path)
    report.checks.append(PreflightCheck("java_runtime", java_ok, True, java_detail))

    if settings.module_dir:
        modules = Path(settings.module_dir).expanduser()
        module_ok = modules.is_dir() and os.access(modules, os.R_OK)
        report.checks.append(PreflightCheck(
            "module_dir", module_ok, True,
            f"Module directory readable: {modules}" if module_ok
            else "Configured Synthea module directory is missing or unreadable.",
        ))
    if settings.config_file:
        config = Path(settings.config_file).expanduser()
        config_ok = config.is_file() and os.access(config, os.R_OK)
        report.checks.append(PreflightCheck(
            "config_file", config_ok, True,
            f"Configuration file readable: {config}" if config_ok
            else "Configured Synthea configuration file is missing or unreadable.",
        ))

    storage_ok = storage_root.is_dir() and os.access(storage_root, os.W_OK)
    report.checks.append(PreflightCheck(
        "storage_root", storage_ok, True,
        f"Managed storage is writable: {storage_root}" if storage_ok
        else "HSPTL-managed synthetic storage is not writable.",
    ))

    available = free_disk_mb(storage_root)
    enough = available >= settings.min_free_disk_mb
    report.checks.append(PreflightCheck(
        "free_disk", enough, True,
        f"{available} MB free; threshold {settings.min_free_disk_mb} MB."
        if enough else f"Only {available} MB free; at least {settings.min_free_disk_mb} MB is required.",
    ))

    population_ok = 1 <= int(population) <= MAX_POPULATION_CEILING
    report.checks.append(PreflightCheck(
        "population", population_ok, True,
        f"Population {population} is within the supported range." if population_ok
        else f"Population must be between 1 and {MAX_POPULATION_CEILING}.",
    ))

    export_ok = bool(fhir or csv)
    report.checks.append(PreflightCheck(
        "export_selection", export_ok, True,
        "At least one export format is selected." if export_ok
        else "Select FHIR R4, CSV, or both.",
    ))

    if require_validator or settings.strict_fhir_required:
        vjar = Path(settings.validator_jar).expanduser() if settings.validator_jar else None
        v_ok = bool(vjar and vjar.is_file() and os.access(vjar, os.R_OK))
        checksum_ok = False
        if v_ok and settings.validator_sha256:
            try:
                checksum_ok = sha256_file(vjar).casefold() == settings.validator_sha256.strip().casefold()  # type: ignore[arg-type]
            except OSError:
                checksum_ok = False
        report.checks.append(PreflightCheck(
            "fhir_validator", v_ok and checksum_ok, True,
            "Pinned HL7 FHIR Validator is available." if (v_ok and checksum_ok)
            else "Strict FHIR conformance was requested but no pinned validator JAR with a matching checksum is configured.",
        ))

    concurrency_ok = not generation_running
    report.checks.append(PreflightCheck(
        "concurrency", concurrency_ok, True,
        "No other generation job is running." if concurrency_ok
        else "Another population generation job is already running; one job at a time is enforced.",
    ))
    return report


@dataclass
class GenerationSpec:
    population: int
    seed: int
    fhir: bool
    csv: bool
    years_of_history: int
    age_min: int = 0
    age_max: int = 105
    gender: str = "any"
    module_dir: str = ""
    config_file: str = ""
    max_heap_mb: int = DEFAULT_MAX_HEAP_MB

    def argument_vector(self, settings: FactorySettings, output_dir: Path) -> list[str]:
        """Deterministic, shell-free argument list for the pinned Synthea build.

        Every value that reaches the vector is an integer or an already-validated
        local path, so a recipe cannot smuggle flags or shell metacharacters.
        """
        args = self.digestible_arguments(settings)
        args.extend(["--exporter.baseDirectory", str(output_dir)])
        return args

    def digestible_arguments(self, settings: FactorySettings) -> list[str]:
        """The argument vector minus the per-run output directory.

        The output path differs between runs by design (each run gets its own
        staging tree), so it is excluded from the reproducibility digest. It is
        still passed to the child process by ``argument_vector``.
        """
        args: list[str] = []
        if settings.java_path.strip():
            args.append(settings.java_path.strip())
        args.extend([f"-Xmx{_bounded_int(self.max_heap_mb, 256, 4096, DEFAULT_MAX_HEAP_MB)}m", "-jar",
                     str(Path(settings.synthea_jar).expanduser())])
        args.extend(["-p", str(int(self.population))])
        args.extend(["-s", str(int(self.seed))])
        args.extend(["-a", f"{int(self.age_min)}-{int(self.age_max)}"])
        if self.gender in {"M", "F"}:
            args.extend(["-g", self.gender])
        module_dir = self.module_dir or settings.module_dir
        if module_dir:
            args.extend(["-d", str(Path(module_dir).expanduser())])
        config_file = self.config_file or settings.config_file
        if config_file:
            args.extend(["-c", str(Path(config_file).expanduser())])
        args.extend(["--exporter.fhir.export", "true" if self.fhir else "false"])
        args.extend(["--exporter.csv.export", "true" if self.csv else "false"])
        args.extend(["--exporter.years_of_history", str(int(self.years_of_history))])
        args.extend(["--exporter.fhir.use_us_core_ig", "false"])
        return args

    def canonical(self) -> dict[str, Any]:
        return {
            "population": int(self.population), "seed": int(self.seed),
            "fhir": bool(self.fhir), "csv": bool(self.csv),
            "years_of_history": int(self.years_of_history),
            "age_min": int(self.age_min), "age_max": int(self.age_max),
            "gender": self.gender,
        }


@dataclass
class GenerationResult:
    generated_patients: int
    returncode: int
    duration_seconds: float
    log_path: str
    cancelled: bool = False


class GenerationError(RuntimeError):
    """Raised when the generator exits non-zero or produces no usable output."""


class GeneratorAdapter(Protocol):
    def generate(self, spec: GenerationSpec, settings: FactorySettings, output_dir: Path,
                 *, log_path: Path, cancel: threading.Event,
                 on_progress: Callable[[str], None] | None = None) -> GenerationResult: ...


class SyntheaProcessAdapter:
    """Runs the pinned Synthea JAR as a child process with bounded output."""

    def __init__(self, *, timeout_seconds: int = 3600, max_log_bytes: int = 4 * 1024 * 1024):
        self.timeout_seconds = timeout_seconds
        self.max_log_bytes = max_log_bytes

    def generate(self, spec: GenerationSpec, settings: FactorySettings, output_dir: Path,
                 *, log_path: Path, cancel: threading.Event,
                 on_progress: Callable[[str], None] | None = None) -> GenerationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        argv = spec.argument_vector(settings, output_dir)
        started = time.monotonic()
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            log.write("ARGV " + json.dumps(argv[1:]) + "\n")
            log.flush()
            try:
                process = subprocess.Popen(
                    argv, stdout=log, stderr=subprocess.STDOUT,
                    shell=False, creationflags=creationflags,
                )
            except OSError as exc:
                raise GenerationError(f"Synthea could not be started: {exc}") from exc
            while True:
                if cancel.is_set():
                    _terminate(process)
                    return GenerationResult(0, process.returncode or -1,
                                            time.monotonic() - started, str(log_path), cancelled=True)
                if process.poll() is not None:
                    break
                if time.monotonic() - started > self.timeout_seconds:
                    _terminate(process)
                    raise GenerationError("Synthea exceeded the configured timeout and was terminated.")
                if on_progress:
                    on_progress("generating")
                time.sleep(0.25)
            returncode = process.returncode
        _truncate(log_path, self.max_log_bytes)
        if returncode != 0:
            raise GenerationError(f"Synthea exited with code {returncode}. See {log_path.name}.")
        return GenerationResult(_count_patient_files(output_dir), returncode,
                                time.monotonic() - started, str(log_path))


def _terminate(process: subprocess.Popen) -> None:
    """Terminate the child and, on Windows, its process group."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, shell=False, check=False)
        else:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    except OSError:
        pass


def _truncate(path: Path, limit: int) -> None:
    try:
        if path.stat().st_size > limit:
            with path.open("rb") as stream:
                stream.seek(-limit, os.SEEK_END)
                tail = stream.read()
            path.write_bytes(b"[log truncated to the final bytes]\n" + tail)
    except OSError:
        pass


def _count_patient_files(output_dir: Path) -> int:
    return sum(1 for _ in output_dir.rglob("*.json"))


class FakeSyntheaAdapter:
    """Deterministic stand-in used by tests and the setup smoke test.

    It writes FHIR R4 transaction-free Bundles that follow Synthea's file-per-
    patient layout, so the real pipeline stages are exercised without Java.
    """

    def __init__(self, patients: list[dict[str, Any]] | None = None, *, fail_with: str = "",
                 empty: bool = False, honour_cancel: bool = False):
        self.patients = patients
        self.fail_with = fail_with
        self.empty = empty
        self.honour_cancel = honour_cancel

    def generate(self, spec: GenerationSpec, settings: FactorySettings, output_dir: Path,
                 *, log_path: Path, cancel: threading.Event,
                 on_progress: Callable[[str], None] | None = None) -> GenerationResult:
        started = time.monotonic()
        output_dir.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if self.honour_cancel and cancel.is_set():
            log_path.write_text("cancelled before generation\n", encoding="utf-8")
            return GenerationResult(0, -1, 0.0, str(log_path), cancelled=True)
        if self.fail_with:
            log_path.write_text(f"simulated failure: {self.fail_with}\n", encoding="utf-8")
            raise GenerationError(f"Simulated Synthea failure: {self.fail_with}")
        if self.empty:
            log_path.write_text("generator produced no output\n", encoding="utf-8")
            return GenerationResult(0, 0, 0.0, str(log_path))
        if self.patients is None:
            from .fixtures import synthetic_patient_bundle
            bundles = [synthetic_patient_bundle(index, seed=spec.seed) for index in range(spec.population)]
        else:
            bundles = self.patients
        fhir_dir = output_dir / "fhir"
        fhir_dir.mkdir(parents=True, exist_ok=True)
        for bundle in bundles:
            patient_id = _bundle_patient_id(bundle)
            (fhir_dir / f"{patient_id}.json").write_text(
                json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        if spec.csv:
            csv_dir = output_dir / "csv"
            csv_dir.mkdir(parents=True, exist_ok=True)
            (csv_dir / "patients.csv").write_text(
                "Id,BIRTHDATE,GENDER\n" + "".join(
                    f"{_bundle_patient_id(b)},{_bundle_patient_birth(b)},unknown\n" for b in bundles
                ),
                encoding="utf-8",
            )
        log_path.write_text(f"fake generator wrote {len(bundles)} bundles\n", encoding="utf-8")
        return GenerationResult(len(bundles), 0, time.monotonic() - started, str(log_path))


def _bundle_patient_id(bundle: dict[str, Any]) -> str:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            return str(resource.get("id", "unknown"))
    return "unknown"


def _bundle_patient_birth(bundle: dict[str, Any]) -> str:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            return str(resource.get("birthDate", ""))
    return ""
