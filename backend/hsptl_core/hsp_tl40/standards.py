"""In-process standards adapters and export ports (not separate services)."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import re
import urllib.parse
from typing import Any


FHIR_BASE = "http://hl7.org/fhir/R4"


def fhir_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Map an already sourced Pulse observation to a FHIR R4 Observation."""
    required = ("id", "code", "value", "unit", "effective")
    if not all(observation.get(key) is not None for key in required):
        raise ValueError("FHIR Observation export requires id, code, value, unit and effective time.")
    base = os.environ.get("HSPTL_FHIR_BASE", FHIR_BASE).strip()
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("HSPTL_FHIR_BASE must be an absolute HTTP(S) URL.")
    return {
        "resourceType": "Observation", "id": str(observation["id"]),
        "status": str(observation.get("status", "final")),
        "code": {"coding": [{"system": observation.get("system", ""),
                              "code": str(observation["code"]),
                              "display": str(observation.get("display", ""))}]},
        "effectiveDateTime": str(observation["effective"]),
        "valueQuantity": {"value": observation["value"], "unit": str(observation["unit"]),
                           "system": observation.get("unit_system", "http://unitsofmeasure.org"),
                           "code": str(observation.get("unit_code", observation["unit"]))},
        "meta": {"tag": [{"system": "https://hsptl.local/source", "code": str(observation.get("source", "pulse"))}]},
    }


def cql_export(rule_id: str, expression: str) -> dict[str, Any]:
    """Return a CQL library wrapper; callers supply a reviewed CQL expression."""
    if not rule_id.strip() or not expression.strip():
        raise ValueError("CQL export requires a stable rule id and reviewed expression.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,79}", rule_id.strip()):
        raise ValueError("CQL rule_id must be 2–80 letters, numbers, underscores or hyphens.")
    if len(expression.strip()) > 20_000:
        raise ValueError("CQL expression exceeds the 20,000-character export limit.")
    return {"filename": f"{rule_id}.cql", "content": f"library {rule_id} version '1.0.0'\n\n{expression}\n",
            "validation": "syntax/clinical validation is not performed by this export port"}


def cds_hooks_descriptor(service_id: str, title: str, hook: str) -> dict[str, Any]:
    if not service_id.strip() or not title.strip() or hook not in {"patient-view", "encounter-start", "order-sign", "order-select"}:
        raise ValueError("CDS Hooks descriptor requires an id, title and supported hook.")
    return {"hook": hook, "title": title, "description": "HSPTL educational integration adapter",
            "id": service_id, "prefetch": {}, "usageRequirements": "Educational use only; not clinical decision support."}


def cds_hooks_card(summary: str, detail: str = "", indicator: str = "info") -> dict[str, Any]:
    if indicator not in {"info", "warning", "critical"}:
        raise ValueError("CDS Hooks indicator must be info, warning or critical.")
    if not summary.strip():
        raise ValueError("CDS Hooks card summary is required.")
    return {"summary": summary.strip()[:160],
            "detail": detail.strip()[:3000],
            "indicator": indicator,
            "source": {"label": "HSPTL synthetic educational adapter",
                       "url": "https://hsptl.local/education-only"},
            "suggestions": []}


def xapi_statement(actor: dict[str, Any], verb: str, activity: dict[str, Any],
                   result: dict[str, Any] | None = None) -> dict[str, Any]:
    if not actor or not verb or not activity:
        raise ValueError("xAPI statement requires actor, verb and activity.")
    statement = {"actor": actor, "verb": {"id": verb}, "object": {"id": activity.get("id"),
                  "definition": {"name": activity.get("name", {})}}}
    if result is not None:
        statement["result"] = result
    return statement


def scorm_runtime_data(completion: str, success: str | None = None,
                       score: float | None = None) -> dict[str, str]:
    allowed_completion = {"completed", "incomplete", "not attempted", "unknown"}
    allowed_success = {"passed", "failed", "unknown"}
    if completion not in allowed_completion or (success is not None and success not in allowed_success):
        raise ValueError("Unsupported SCORM completion/success status.")
    data = {"cmi.completion_status": completion}
    if success is not None:
        data["cmi.success_status"] = success
    if score is not None:
        if not 0 <= score <= 100:
            raise ValueError("SCORM score must be between 0 and 100.")
        data["cmi.score.scaled"] = str(score / 100)
    return data


def lti_port_descriptor(issuer: str, client_id: str, deployment_id: str) -> dict[str, Any]:
    if not issuer or not client_id or not deployment_id:
        return {"state": "not_configured", "protocol": "LTI 1.3",
                "required": ["issuer", "client_id", "deployment_id", "OIDC login URL", "JWKS URL", "redirect URIs"]}
    return {"state": "configured_descriptor_only", "protocol": "LTI 1.3",
            "issuer": issuer, "client_id": client_id, "deployment_id": deployment_id,
            "note": "OIDC/JWT launch validation and institutional registration are not implemented by this local port."}


def ports_manifest() -> dict[str, Any]:
    return {"FHIR": {"status": "export_adapter", "version": "R4"},
            "CQL": {"status": "reviewed-expression-export-port", "runtime": "not bundled"},
            "CDS Hooks": {"status": "descriptor-export-port", "clinical service hosting": "not provided"},
            "LTI 1.3": {"status": "configuration port", "launch security": "requires institutional adapter"},
            "xAPI": {"status": "statement adapter"},
            "SCORM": {"status": "runtime data adapter"},
            "default_transport_services": 0}
