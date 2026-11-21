"""Dataset provenance manifests.

A manifest is canonical JSON plus a detached SHA-256 over that canonical form.
It records what was run, with which pinned inputs, and what came out. It never
contains secrets and never contains patient resource payloads -- only counts,
digests, versions and relative paths.

The manifest is written once when a dataset is registered and is not rewritten
afterwards, so provenance stays auditable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = "hsptl.synthetic.manifest/1.0"
SOFTWARE_VERSION = "HSPTL 6.0.0"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path, *, chunk: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(chunk), b""):
            hasher.update(block)
    return hasher.hexdigest()


@dataclass
class ArtifactRecord:
    relative_path: str
    kind: str
    byte_size: int
    sha256: str
    immutable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path, "kind": self.kind,
            "byte_size": self.byte_size, "sha256": self.sha256,
            "immutable": self.immutable,
        }


@dataclass
class DatasetManifest:
    dataset_id: str
    job_id: str
    run_id: str
    recipe_id: str
    recipe_version: str
    recipe_digest: str
    idempotency_key: str
    synthea_version: str
    synthea_sha256: str
    java_version: str
    seed: str
    command_digest: str
    module_pack: str
    module_pack_version: str
    module_hashes: dict[str, str] = field(default_factory=dict)
    fhir_version: str = "4.0.1"
    profile_packages: list[str] = field(default_factory=list)
    exports: dict[str, Any] = field(default_factory=dict)
    years_of_history: int = 0
    cohort: dict[str, Any] = field(default_factory=dict)
    validator_id: str = ""
    validator_version: str = ""
    validator_sha256: str = ""
    validator_parameters: dict[str, Any] = field(default_factory=dict)
    terminology_versions: dict[str, str] = field(default_factory=dict)
    mapping_set_version: str = ""
    rule_pack_id: str = ""
    rule_pack_version: str = ""
    generation_started_at: str = ""
    generation_finished_at: str = ""
    counts: dict[str, Any] = field(default_factory=dict)
    resource_counts: dict[str, int] = field(default_factory=dict)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    validation_totals: dict[str, Any] = field(default_factory=dict)
    quarantine_totals: dict[str, Any] = field(default_factory=dict)
    import_result: dict[str, Any] = field(default_factory=dict)
    import_idempotency_key: str = ""
    software_version: str = SOFTWARE_VERSION
    schema_version: str = MANIFEST_SCHEMA_VERSION
    normalizations: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "software_version": self.software_version,
            "dataset_id": self.dataset_id,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "recipe": {
                "recipe_id": self.recipe_id, "version": self.recipe_version,
                "content_digest": self.recipe_digest,
            },
            "idempotency_key": self.idempotency_key,
            "generator": {
                "name": "synthea", "version": self.synthea_version,
                "sha256": self.synthea_sha256, "java_version": self.java_version,
                "seed": self.seed, "command_digest": self.command_digest,
            },
            "modules": {
                "module_pack": self.module_pack, "module_pack_version": self.module_pack_version,
                "module_hashes": self.module_hashes,
            },
            "fhir": {
                "version": self.fhir_version, "profile_packages": self.profile_packages,
            },
            "exports": self.exports,
            "years_of_history": self.years_of_history,
            "cohort": self.cohort,
            "validation": {
                "validator_id": self.validator_id, "validator_version": self.validator_version,
                "validator_sha256": self.validator_sha256,
                "validator_parameters": self.validator_parameters,
                "rule_pack_id": self.rule_pack_id, "rule_pack_version": self.rule_pack_version,
                "terminology_versions": self.terminology_versions,
                "mapping_set_version": self.mapping_set_version,
            },
            "generation": {
                "started_at": self.generation_started_at,
                "finished_at": self.generation_finished_at,
            },
            "counts": self.counts,
            "resource_counts": self.resource_counts,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "validation_totals": self.validation_totals,
            "quarantine_totals": self.quarantine_totals,
            "import_result": self.import_result,
            "import_idempotency_key": self.import_idempotency_key,
            "normalizations": self.normalizations,
            "limitations": self.limitations,
        }

    def digest(self) -> str:
        return digest(self.to_dict())

    def reproducibility_record(self) -> dict[str, Any]:
        """The subset of a manifest that must be identical for identical inputs.

        Identity fields (run, job, dataset) and wall-clock timestamps differ
        between two runs by design. Absolute local paths also differ between
        machines while describing the same pinned artifact, so the generator is
        identified by version and content hash rather than by its location.
        """
        return {
            "schema_version": self.schema_version,
            "recipe": {
                "recipe_id": self.recipe_id, "version": self.recipe_version,
                "content_digest": self.recipe_digest,
            },
            "generator": {
                "name": "synthea", "version": self.synthea_version,
                "sha256": self.synthea_sha256.casefold(), "seed": self.seed,
            },
            "modules": {
                "module_pack": self.module_pack,
                "module_pack_version": self.module_pack_version,
                "module_hashes": self.module_hashes,
            },
            "fhir": {"version": self.fhir_version, "profile_packages": self.profile_packages},
            "exports": self.exports,
            "years_of_history": self.years_of_history,
            "cohort": self.cohort,
            "validation": {
                "validator_id": self.validator_id, "validator_version": self.validator_version,
                "validator_sha256": self.validator_sha256,
                "rule_pack_id": self.rule_pack_id, "rule_pack_version": self.rule_pack_version,
                "terminology_versions": self.terminology_versions,
                "mapping_set_version": self.mapping_set_version,
            },
            "counts": self.counts,
            "resource_counts": self.resource_counts,
            "artifacts": [
                {"relative_path": artifact.relative_path, "kind": artifact.kind,
                 "byte_size": artifact.byte_size, "sha256": artifact.sha256}
                for artifact in self.artifacts
            ],
            "normalizations": [
                {key: value for key, value in item.items() if key != "timestamp"}
                for item in self.normalizations
            ],
            "severity_counts": self.validation_totals.get("severity_counts", {}),
            "dimension_counts": self.validation_totals.get("dimension_counts", {}),
            "quarantine_totals": self.quarantine_totals,
        }

    def content_digest(self) -> str:
        return digest(self.reproducibility_record())


def write_manifest(manifest: DatasetManifest, path: Path) -> dict[str, Any]:
    """Write canonical manifest JSON and its detached digest sidecar.

    Two digests are recorded: ``manifest_digest`` covers the whole document
    including run identity, and ``content_digest`` covers only reproducible
    content so two identical-input runs can be compared directly.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.to_dict()
    content_digest = manifest.content_digest()
    payload["content_digest"] = content_digest
    canonical = canonical_json(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    manifest_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.with_suffix(".sha256").write_text(
        f"{manifest_digest}  {path.name}\n", encoding="utf-8"
    )
    return {"manifest_digest": manifest_digest, "content_digest": content_digest,
            "path": str(path)}


def verify_manifest(path: Path) -> tuple[bool, str]:
    """Prove a manifest on disk still matches its recorded digest."""
    path = Path(path)
    sidecar = path.with_suffix(".sha256")
    if not path.is_file() or not sidecar.is_file():
        return False, "Manifest or digest sidecar is missing."
    recorded = sidecar.read_text(encoding="utf-8").split()[0].strip()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"Manifest is unreadable: {exc}"
    actual = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    if actual != recorded:
        return False, "Manifest content does not match its recorded digest."
    return True, "Manifest digest verified."
