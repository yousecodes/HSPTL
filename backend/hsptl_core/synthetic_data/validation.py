"""Layered, deterministic validation for synthetic FHIR datasets.

The engine keeps six dimensions separate on purpose: structural shape,
referential integrity, chronology, terminology coverage, clinical plausibility
and educational completeness. There is no single "quality score" because a hard
structural failure must never be averaged away by a good completeness number.

Two safety rules are enforced throughout:

* An abnormal clinical value is legitimate content. Plausibility rules check
  internal consistency and data shape, not "is this value normal".
* Nothing here mutates a resource. Findings describe; they never rewrite.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from .fhir_parse import bundle_patient_id, bundle_resources

RULE_PACK_ID = "hsptl-core"
RULE_PACK_VERSION = "1.0.0"

SEVERITIES = ("info", "warning", "quarantine", "error")

# Clinical resources that must name a Patient via subject/patient.
PATIENT_LINKED = {
    "Encounter", "Condition", "Observation", "MedicationRequest", "Procedure",
    "DiagnosticReport", "AllergyIntolerance", "Immunization", "CarePlan",
    "MedicationAdministration", "Specimen", "ServiceRequest",
}

FHIR_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
FHIR_DATETIME = re.compile(
    r"^\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$"
)

KNOWN_SYSTEMS = {
    "http://snomed.info/sct",
    "http://loinc.org",
    "http://www.nlm.nih.gov/research/umls/rxnorm",
    "http://hl7.org/fhir/sid/icd-10-cm",
    "http://hl7.org/fhir/sid/icd-9-cm",
    "http://terminology.hl7.org/CodeSystem/v3-ActCode",
    "http://terminology.hl7.org/CodeSystem/condition-clinical",
    "http://terminology.hl7.org/CodeSystem/condition-ver-status",
    "http://terminology.hl7.org/CodeSystem/observation-category",
    "http://unitsofmeasure.org",
    "http://terminology.hl7.org/CodeSystem/v2-0203",
    "http://hl7.org/fhir/observation-status",
    "http://hl7.org/fhir/encounter-status",
    "http://hl7.org/fhir/medication-request-status",
    "http://hl7.org/fhir/medication-request-intent",
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
    "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
    "http://hl7.org/fhir/sid/ndc",
    "http://hl7.org/fhir/sid/cvx",
    "http://terminology.hl7.org/CodeSystem/immunization-status",
}


@dataclass
class Finding:
    dimension: str
    rule_id: str
    severity: str
    message: str
    patient_key: str = ""
    resource_type: str = ""
    rule_version: str = RULE_PACK_VERSION
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension, "rule_id": self.rule_id, "severity": self.severity,
            "message": self.message, "patient_key": self.patient_key,
            "resource_type": self.resource_type, "rule_version": self.rule_version,
            "detail": self.detail,
        }


@dataclass
class PatientResult:
    """Per-patient verdict. Quarantine is decided at this granularity."""
    patient_key: str
    source_file: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(finding.severity in {"quarantine", "error"} for finding in self.findings)

    @property
    def block_reasons(self) -> list[str]:
        return sorted({finding.rule_id for finding in self.findings
                       if finding.severity in {"quarantine", "error"}})


@dataclass
class ValidationReport:
    patients: list[PatientResult] = field(default_factory=list)
    dataset_findings: list[Finding] = field(default_factory=list)
    resource_counts: dict[str, int] = field(default_factory=dict)
    strict_conformance: bool = False
    validator_id: str = "local-shape-checks"
    validator_version: str = RULE_PACK_VERSION
    validator_diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def all_findings(self) -> list[Finding]:
        collected: list[Finding] = list(self.dataset_findings)
        for patient in self.patients:
            collected.extend(patient.findings)
        return collected

    def severity_counts(self) -> dict[str, int]:
        counts = {severity: 0 for severity in SEVERITIES}
        for finding in self.all_findings():
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def dimension_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.all_findings():
            counts[finding.dimension] = counts.get(finding.dimension, 0) + 1
        return counts

    def accepted(self) -> list[PatientResult]:
        return [patient for patient in self.patients if not patient.blocked]

    def quarantined(self) -> list[PatientResult]:
        return [patient for patient in self.patients if patient.blocked]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_pack_id": RULE_PACK_ID,
            "rule_pack_version": RULE_PACK_VERSION,
            "strict_conformance": self.strict_conformance,
            "validator_id": self.validator_id,
            "validator_version": self.validator_version,
            "resource_counts": self.resource_counts,
            "severity_counts": self.severity_counts(),
            "dimension_counts": self.dimension_counts(),
            "patients_total": len(self.patients),
            "patients_accepted": len(self.accepted()),
            "patients_quarantined": len(self.quarantined()),
            "dataset_findings": [finding.to_dict() for finding in self.dataset_findings],
            "validator_diagnostics": self.validator_diagnostics[:200],
            "findings": [finding.to_dict() for finding in self.all_findings()],
        }


# --------------------------------------------------------------------------- #
# Structural validation
# --------------------------------------------------------------------------- #

def _valid_date(value: Any, pattern: re.Pattern[str]) -> bool:
    if not isinstance(value, str) or not pattern.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        # Partial dates such as "1970" or "1970-04" are legal FHIR.
        return bool(re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", value))
    return True


def validate_structure(bundle: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    resources = bundle_resources(bundle)

    seen_ids: dict[str, str] = {}
    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not isinstance(resource_type, str) or not resource_type:
            findings.append(Finding("structural", "F-STRUCT-001", "error",
                                    "Resource is missing resourceType.", patient_key))
            continue
        if not isinstance(resource_id, str) or not resource_id:
            findings.append(Finding("structural", "F-STRUCT-002", "error",
                                    f"{resource_type} is missing a stable id.",
                                    patient_key, resource_type))
            continue
        previous = seen_ids.get(resource_id)
        if previous is not None:
            findings.append(Finding(
                "structural", "F-STRUCT-003", "error",
                f"Resource id {resource_id} is used by both {previous} and {resource_type}.",
                patient_key, resource_type, detail={"resource_id": resource_id},
            ))
        else:
            seen_ids[resource_id] = resource_type

    types_present = {resource.get("resourceType") for resource in resources}
    if "Patient" not in types_present:
        findings.append(Finding("structural", "F-STRUCT-004", "error",
                                "Bundle contains clinical resources but no Patient.",
                                patient_key))

    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    if len(patients) > 1:
        findings.append(Finding("structural", "F-STRUCT-005", "warning",
                                f"Bundle contains {len(patients)} Patient resources.",
                                patient_key, "Patient"))
    for patient in patients:
        birth = patient.get("birthDate")
        if birth is not None and not _valid_date(birth, FHIR_DATE):
            findings.append(Finding("structural", "F-STRUCT-006", "error",
                                    "Patient.birthDate is not a valid FHIR date.",
                                    patient_key, "Patient"))
        if not patient.get("gender"):
            findings.append(Finding("structural", "F-STRUCT-007", "warning",
                                    "Patient.gender is absent.", patient_key, "Patient"))

    for resource in resources:
        if resource.get("resourceType") == "Observation":
            findings.extend(_validate_quantity(resource, patient_key))
    findings.extend(_validate_profiles(bundle, patient_key))
    return findings


# Profiles this local rule pack can actually verify. Anything else is reported
# as unverified rather than assumed conformant.
VERIFIABLE_PROFILES = {
    "http://hl7.org/fhir/StructureDefinition/Patient",
    "http://hl7.org/fhir/StructureDefinition/Encounter",
    "http://hl7.org/fhir/StructureDefinition/Observation",
    "http://hl7.org/fhir/StructureDefinition/Condition",
}


def _validate_profiles(bundle: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    declared: set[str] = set()

    def collect(meta: Any) -> None:
        if isinstance(meta, dict):
            for profile in meta.get("profile", []) or []:
                if isinstance(profile, str) and profile:
                    declared.add(profile)

    collect(bundle.get("meta"))
    for resource in bundle_resources(bundle):
        collect(resource.get("meta"))

    unverified = sorted(profile for profile in declared if profile not in VERIFIABLE_PROFILES)
    if unverified:
        findings.append(Finding(
            "structural", "F-STRUCT-020", "warning",
            f"{len(unverified)} declared profile(s) cannot be verified by the local rule pack. "
            "Profile conformance is not claimed; configure a pinned HL7 validator for strict checking.",
            patient_key, detail={"unverified_profiles": unverified[:20]},
        ))
    return findings


def _validate_quantity(observation: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    quantity = observation.get("valueQuantity")
    if quantity is None:
        return findings
    if not isinstance(quantity, dict):
        return [Finding("structural", "F-STRUCT-010", "error",
                        "Observation.valueQuantity must be an object.",
                        patient_key, "Observation")]
    value = quantity.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        findings.append(Finding("structural", "F-STRUCT-011", "error",
                                "Observation.valueQuantity.value must be numeric.",
                                patient_key, "Observation"))
    if not isinstance(quantity.get("unit"), str) or not quantity.get("unit"):
        findings.append(Finding("structural", "F-STRUCT-012", "warning",
                                "Observation.valueQuantity.unit is missing.",
                                patient_key, "Observation"))
    return findings


# --------------------------------------------------------------------------- #
# Referential integrity
# --------------------------------------------------------------------------- #

def validate_references(bundle: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    resources = bundle_resources(bundle)
    known: dict[str, set[str]] = {}
    for resource in resources:
        resource_type = str(resource.get("resourceType") or "")
        resource_id = str(resource.get("id") or "")
        if resource_type and resource_id:
            known.setdefault(resource_type, set()).add(resource_id)

    patient_ids = known.get("Patient", set())
    if len(patient_ids) > 1:
        findings.append(Finding("reference", "F-REF-005", "warning",
                                "Bundle contains more than one Patient; patient-bundle quarantine is ambiguous.",
                                patient_key))

    for resource in resources:
        resource_type = str(resource.get("resourceType") or "")
        reference = _patient_reference(resource)
        if resource_type in PATIENT_LINKED:
            if not reference:
                findings.append(Finding("reference", "F-REF-001", "error",
                                        f"{resource_type} has no subject or patient reference.",
                                        patient_key, resource_type))
            else:
                target = _reference_id(reference)
                if not target:
                    findings.append(Finding("reference", "F-REF-002", "error",
                                            f"{resource_type} reference is not a resolvable local reference.",
                                            patient_key, resource_type))
                elif target not in patient_ids:
                    findings.append(Finding(
                        "reference", "F-REF-003", "error",
                        f"{resource_type} references Patient/{target}, which is not in this bundle.",
                        patient_key, resource_type, detail={"reference": reference},
                    ))
        encounter = resource.get("encounter")
        if isinstance(encounter, dict) and encounter.get("reference"):
            target = _reference_id(str(encounter["reference"]))
            if target and target not in known.get("Encounter", set()):
                findings.append(Finding(
                    "reference", "F-REF-004", "warning",
                    f"{resource_type} references Encounter/{target}, which is not in this bundle.",
                    patient_key, resource_type,
                ))

    full_urls: dict[str, str] = {}
    for entry in bundle.get("entry", []) or []:
        full_url = entry.get("fullUrl") if isinstance(entry, dict) else None
        if not isinstance(full_url, str) or not full_url:
            continue
        if full_url in full_urls:
            findings.append(Finding("reference", "F-REF-006", "error",
                                    f"Bundle.fullUrl {full_url} is used more than once.",
                                    patient_key, detail={"full_url": full_url}))
        full_urls[full_url] = full_url
    return findings


def _patient_reference(resource: dict[str, Any]) -> str:
    if resource.get("resourceType") == "AllergyIntolerance":
        patient = resource.get("patient")
        if isinstance(patient, dict) and patient.get("reference"):
            return str(patient["reference"])
    subject = resource.get("subject")
    if isinstance(subject, dict) and subject.get("reference"):
        return str(subject["reference"])
    patient = resource.get("patient")
    if isinstance(patient, dict) and patient.get("reference"):
        return str(patient["reference"])
    return ""


def _reference_id(reference: str) -> str:
    text = reference.strip()
    if text.startswith("urn:uuid:"):
        return ""
    if "/" not in text:
        return ""
    kind, _, identifier = text.rpartition("/")
    if not identifier:
        return ""
    if kind.split("/")[-1] not in {"Patient", "Encounter", "Practitioner", "Organization", "Location"}:
        return ""
    return identifier


# --------------------------------------------------------------------------- #
# Chronology
# --------------------------------------------------------------------------- #

def _parse_instant(value: Any) -> datetime | None:
    """Parse a FHIR date or dateTime into an aware UTC datetime.

    FHIR allows partial dates (``1970``, ``1970-04``) and local times with no
    offset. Normalising everything to aware UTC keeps comparisons total; a
    naive value is read as UTC rather than dropped.
    """
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if re.fullmatch(r"\d{4}", text):
        text = f"{text}-01-01"
    elif re.fullmatch(r"\d{4}-\d{2}", text):
        text = f"{text}-01"
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        from datetime import timezone
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def validate_chronology(bundle: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    resources = bundle_resources(bundle)

    birth: datetime | None = None
    for resource in resources:
        if resource.get("resourceType") == "Patient":
            birth = _parse_instant(resource.get("birthDate"))
            break

    for resource in resources:
        resource_type = str(resource.get("resourceType") or "")
        if resource_type == "Encounter":
            period = resource.get("period")
            if isinstance(period, dict):
                start = _parse_instant(period.get("start"))
                end = _parse_instant(period.get("end"))
                if start and end and end < start:
                    findings.append(Finding(
                        "chronology", "F-CHRON-001", "error",
                        "Encounter period ends before it starts.", patient_key, resource_type,
                        detail={"start": period.get("start"), "end": period.get("end")},
                    ))
        elif resource_type == "Condition":
            onset = _parse_instant(resource.get("onsetDateTime"))
            abatement = _parse_instant(resource.get("abatementDateTime"))
            if onset and abatement and abatement < onset:
                findings.append(Finding("chronology", "F-CHRON-002", "error",
                                        "Condition abatement precedes onset.",
                                        patient_key, resource_type))
            if birth and onset and onset < birth:
                findings.append(Finding("chronology", "F-CHRON-003", "error",
                                        "Condition onset precedes the patient's birth date.",
                                        patient_key, resource_type))
        elif resource_type == "Observation":
            effective = _parse_instant(resource.get("effectiveDateTime"))
            issued = _parse_instant(resource.get("issued"))
            if effective and issued and issued < effective:
                findings.append(Finding("chronology", "F-CHRON-004", "warning",
                                        "Observation issued timestamp precedes the effective time.",
                                        patient_key, resource_type))
            if birth and effective and effective < birth:
                findings.append(Finding("chronology", "F-CHRON-005", "error",
                                        "Observation effective time precedes the patient's birth date.",
                                        patient_key, resource_type))
        elif resource_type == "MedicationRequest":
            authored = _parse_instant(resource.get("authoredOn"))
            validity = resource.get("dispenseRequest", {})
            if isinstance(validity, dict):
                period = validity.get("validityPeriod")
                if isinstance(period, dict):
                    start = _parse_instant(period.get("start"))
                    end = _parse_instant(period.get("end"))
                    if start and end and end < start:
                        findings.append(Finding("chronology", "F-CHRON-006", "error",
                                                "MedicationRequest validity period is reversed.",
                                                patient_key, resource_type))
                    if authored and start and start < authored:
                        findings.append(Finding("chronology", "F-CHRON-007", "warning",
                                                "MedicationRequest validity starts before it was authored.",
                                                patient_key, resource_type))
        elif resource_type == "Procedure":
            period = resource.get("performedPeriod")
            if isinstance(period, dict):
                start = _parse_instant(period.get("start"))
                end = _parse_instant(period.get("end"))
                if start and end and end < start:
                    findings.append(Finding("chronology", "F-CHRON-008", "error",
                                            "Procedure performedPeriod is reversed.",
                                            patient_key, resource_type))
    return findings


# --------------------------------------------------------------------------- #
# Terminology
# --------------------------------------------------------------------------- #

def validate_terminology(bundle: dict[str, Any], patient_key: str,
                         *, mapping_set: str = "hsptl-mapping/1.0.0") -> list[Finding]:
    """Report unmapped codes without touching them.

    An unmapped code is a warning plus a stable review record. Display-text
    similarity is never used to guess a replacement code.
    """
    findings: list[Finding] = []
    unmapped: set[str] = set()
    for resource in bundle_resources(bundle):
        resource_type = str(resource.get("resourceType") or "")
        for coding in _codings(resource):
            system = coding.get("system")
            code = coding.get("code")
            if not isinstance(system, str) or not system:
                continue
            if not isinstance(code, str) or not code:
                findings.append(Finding("terminology", "F-TERM-002", "warning",
                                        f"{resource_type} coding has no code value.",
                                        patient_key, resource_type))
                continue
            if system not in KNOWN_SYSTEMS:
                unmapped.add(f"{system}|{code}")
    if unmapped:
        findings.append(Finding(
            "terminology", "F-TERM-001", "warning",
            f"{len(unmapped)} code(s) use a system outside the local mapping set; "
            "they are preserved unchanged and queued for mapping review.",
            patient_key, detail={"mapping_set": mapping_set, "unmapped": sorted(unmapped)[:50]},
        ))
    return findings


def _codings(resource: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for key in ("code", "category", "clinicalStatus", "verificationStatus", "vaccineCode",
                "medicationCodeableConcept"):
        value = resource.get(key)
        if isinstance(value, dict):
            for coding in value.get("coding", []) or []:
                if isinstance(coding, dict):
                    yield coding
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for coding in item.get("coding", []) or []:
                        if isinstance(coding, dict):
                            yield coding


# --------------------------------------------------------------------------- #
# Clinical plausibility (internal consistency only)
# --------------------------------------------------------------------------- #

# Reviewed reference bounds by observation LOINC code. These describe plausible
# *recordable* ranges, not "normal" ranges, so a genuinely abnormal value is not
# rejected. A value outside these bounds is a warning, never a mutation.
PLAUSIBILITY_BOUNDS = {
    "8867-4": ("Heart rate", 0.0, 400.0, "/min"),
    "9279-1": ("Respiratory rate", 0.0, 100.0, "/min"),
    "8310-5": ("Body temperature", 20.0, 47.0, "Cel"),
    "8480-6": ("Systolic blood pressure", 0.0, 400.0, "mm[Hg]"),
    "8462-4": ("Diastolic blood pressure", 0.0, 300.0, "mm[Hg]"),
    "2708-6": ("Oxygen saturation", 0.0, 100.0, "%"),
    "29463-7": ("Body weight", 0.1, 700.0, "kg"),
    "8302-2": ("Body height", 10.0, 280.0, "cm"),
}


def validate_plausibility(bundle: dict[str, Any], patient_key: str) -> list[Finding]:
    findings: list[Finding] = []
    for resource in bundle_resources(bundle):
        if resource.get("resourceType") != "Observation":
            continue
        quantity = resource.get("valueQuantity")
        if not isinstance(quantity, dict):
            continue
        value = quantity.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        code = _first_code(resource.get("code"))
        bounds = PLAUSIBILITY_BOUNDS.get(code or "")
        if bounds is None:
            findings.append(Finding(
                "plausibility", "F-PLAUS-002", "info",
                "No reviewed reference bound exists for this observation code; "
                "the engine abstains rather than making an unsupported clinical claim.",
                patient_key, "Observation", detail={"code": code or ""},
            ))
            continue
        label, low, high, expected_unit = bounds
        if not low <= float(value) <= high:
            findings.append(Finding(
                "plausibility", "F-PLAUS-001", "warning",
                f"{label} value {value} is outside the recordable range "
                f"{low}-{high} {expected_unit}; retained unchanged for review.",
                patient_key, "Observation",
                detail={"code": code, "value": value, "low": low, "high": high,
                        "expected_unit": expected_unit},
            ))
        unit = quantity.get("unit") or quantity.get("code")
        if isinstance(unit, str) and unit and unit != expected_unit:
            findings.append(Finding(
                "plausibility", "F-PLAUS-003", "info",
                f"{label} uses unit '{unit}'; the reviewed reference set expects "
                f"'{expected_unit}'. Values were not converted.",
                patient_key, "Observation", detail={"code": code, "unit": unit},
            ))
    return findings


def _first_code(concept: Any) -> str | None:
    if not isinstance(concept, dict):
        return None
    for coding in concept.get("coding", []) or []:
        if isinstance(coding, dict) and coding.get("code"):
            return str(coding["code"])
    return None


# --------------------------------------------------------------------------- #
# Educational completeness (recipe-relative)
# --------------------------------------------------------------------------- #

def validate_completeness(bundle: dict[str, Any], patient_key: str,
                          *, required_resources: list[str],
                          cohort_codes: set[str] | None) -> list[Finding]:
    findings: list[Finding] = []
    resources = bundle_resources(bundle)
    present = {str(resource.get("resourceType") or "") for resource in resources}
    for required in required_resources:
        if required not in present:
            findings.append(Finding(
                "completeness", "F-COMPL-001", "warning",
                f"Recipe expects a {required} resource; this patient bundle has none.",
                patient_key, required,
            ))
    if cohort_codes:
        matched = False
        for resource in resources:
            if resource.get("resourceType") != "Condition":
                continue
            code = _first_code(resource.get("code"))
            if code and code in cohort_codes:
                matched = True
                break
        if not matched:
            findings.append(Finding(
                "completeness", "F-COMPL-002", "info",
                "Patient does not carry a cohort criterion code; valid for a general dataset, "
                "not selected for a targeted cohort.",
                patient_key, "Condition",
            ))
    return findings


# --------------------------------------------------------------------------- #
# Official validator adapter
# --------------------------------------------------------------------------- #

def run_hl7_validator(bundle_path, settings, *, timeout_seconds: int = 600) -> dict[str, Any]:
    """Invoke a pinned HL7 FHIR Validator CLI and preserve its OperationOutcome.

    Returns a dict with ``available``, ``ok``, ``diagnostics`` and ``raw``. When
    no validator is configured the caller must label conformance as limited.
    """
    import os
    import subprocess
    from pathlib import Path

    jar = Path(settings.validator_jar).expanduser() if getattr(settings, "validator_jar", "") else None
    if not jar or not jar.is_file():
        return {"available": False, "ok": False, "diagnostics": [],
                "raw": "No pinned HL7 FHIR Validator is configured."}
    argv = ["java", "-jar", str(jar), str(Path(bundle_path)), "-version", "4.0.1", "-output", "json"]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_seconds,
                                shell=False, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": True, "ok": False, "diagnostics": [],
                "raw": f"Validator could not run: {exc}"}
    diagnostics: list[dict[str, Any]] = []
    ok = result.returncode == 0
    try:
        payload = json.loads(result.stdout)
        for issue in payload.get("issue", []) or []:
            diagnostics.append({
                "severity": issue.get("severity", "error"),
                "code": issue.get("code", ""),
                "diagnostics": issue.get("diagnostics", ""),
            })
            if issue.get("severity") in {"error", "fatal"}:
                ok = False
    except (json.JSONDecodeError, AttributeError):
        diagnostics.append({"severity": "information", "code": "non-json",
                            "diagnostics": (result.stdout or result.stderr or "")[:2000]})
    return {"available": True, "ok": ok, "diagnostics": diagnostics,
            "raw": (result.stdout or "")[:20000], "returncode": result.returncode}


# --------------------------------------------------------------------------- #
# Engine entry point
# --------------------------------------------------------------------------- #

def validate_dataset(bundles: list[tuple[str, dict[str, Any]]], *,
                     required_resources: list[str] | None = None,
                     cohort_codes: set[str] | None = None,
                     strict_conformance: bool = False,
                     validator_id: str = "local-shape-checks",
                     validator_version: str = RULE_PACK_VERSION) -> ValidationReport:
    """Run every dimension over a list of (source_file, bundle) pairs."""
    report = ValidationReport(strict_conformance=strict_conformance,
                              validator_id=validator_id, validator_version=validator_version)
    resource_counts: dict[str, int] = {}
    seen_patients: dict[str, str] = {}

    for source_file, bundle in bundles:
        patient_key = bundle_patient_id(bundle) or f"unidentified:{source_file}"
        result = PatientResult(patient_key=patient_key, source_file=source_file)
        for resource in bundle_resources(bundle):
            resource_type = str(resource.get("resourceType") or "Unknown")
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1

        if patient_key in seen_patients:
            report.dataset_findings.append(Finding(
                "reference", "F-REF-007", "error",
                f"Patient {patient_key} appears in both {seen_patients[patient_key]} and {source_file}.",
                patient_key, "Patient",
            ))
        else:
            seen_patients[patient_key] = source_file

        result.findings.extend(validate_structure(bundle, patient_key))
        result.findings.extend(validate_references(bundle, patient_key))
        result.findings.extend(validate_chronology(bundle, patient_key))
        result.findings.extend(validate_terminology(bundle, patient_key))
        result.findings.extend(validate_plausibility(bundle, patient_key))
        result.findings.extend(validate_completeness(
            bundle, patient_key,
            required_resources=required_resources or [],
            cohort_codes=cohort_codes,
        ))
        report.patients.append(result)

    if not bundles:
        report.dataset_findings.append(Finding(
            "structural", "F-STRUCT-000", "error",
            "The generation produced no parseable patient bundles.",
        ))
    report.resource_counts = resource_counts
    return report
