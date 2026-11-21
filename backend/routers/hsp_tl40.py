"""HSPTL 4.0 API: in-process modules sharing the canonical event ledger."""
from __future__ import annotations

from typing import Any
import uuid
import os
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..runtime import PATHS, STORE, INSTITUTIONAL_AUTH, COHORTS
from ..hsptl_core.deterministic_intelligence.engine import DeterministicIntelligenceEngine, Abstention
from ..hsptl_core.hsp_tl40.kernel import EventKernel
from ..hsptl_core.hsp_tl40.proforma import ProformaRuntime, ProformaError, validate_plan, LOGIC_VERSION
from ..hsptl_core.hsp_tl40.guards import Guards
from ..hsptl_core.hsp_tl40.reasoner import Reasoner
from ..hsptl_core.hsp_tl40.composer import Composer
from ..hsptl_core.hsp_tl40.router import Router
from ..hsptl_core.hsp_tl40.plugins import REGISTRY
from ..hsptl_core.hsp_tl40.pulse import PulseBridge
from ..hsptl_core.hsp_tl40.clinical_simulation import ClinicalSimulationRuntime, ScenarioCatalog, SimulationError, SimulationConflict
from ..hsptl_core.hsp_tl40.scenario_authoring import ScenarioAuthoring, ScenarioAuthoringError
from ..hsptl_core.hsp_tl40.terminology_port import TerminologyPort
from ..hsptl_core.hsp_tl40.debugger import debug_proforma
from ..hsptl_core.hsp_tl40.explain import render_explanation
from ..hsptl_core.hsp_tl40.temporal_reasoning import TemporalReasoner, RULESET_ID
from ..hsptl_core.hsp_tl40.event_contracts import event_catalogue
from ..hsptl_core.hsp_tl40.guard_matrix import guard_catalogue
from ..hsptl_core.hsp_tl40.model_library import model_catalogue
from ..hsptl_core.hsp_tl40.standards import (
    fhir_observation, cql_export, cds_hooks_descriptor, cds_hooks_card, xapi_statement,
    scorm_runtime_data, lti_port_descriptor, ports_manifest,
)
from ..hsptl_core.config import APP_VERSION
from ..hsptl_core.institutional import (
    DEFAULT_INSTITUTION, ROLES, InstitutionalError,
)

router = APIRouter(prefix="/api/v4", tags=["HSPTL 4.0"])
ENGINE = DeterministicIntelligenceEngine(PATHS["database"])
KERNEL = EventKernel(ENGINE)
GUARDS = Guards(KERNEL, ENGINE)
LOGIC = ProformaRuntime(KERNEL)
REASONER = Reasoner(ENGINE)
COMPOSER = Composer(ENGINE, KERNEL, GUARDS)
ROUTER = Router(KERNEL, GUARDS, ENGINE)
PULSE = PulseBridge(KERNEL)
TERMINOLOGY = TerminologyPort(snowstorm_url=os.environ.get("HSPTL_SNOWSTORM_URL"),
                              db_path=PATHS["database"], kernel=KERNEL)
SCENARIO_AUTHORING = ScenarioAuthoring(PATHS["root"])
SIMULATION = ClinicalSimulationRuntime(KERNEL, LOGIC, ScenarioCatalog(additional_roots=[SCENARIO_AUTHORING.published]))


class EnactRequest(BaseModel):
    plan: dict[str, Any]
    facts: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=160)
    value: Any = None
    context_patch: dict[str, Any] = Field(default_factory=dict)


class GuardRequest(BaseModel):
    guard_id: str = Field(min_length=1, max_length=120)
    expression: Any
    context: dict[str, Any] = Field(default_factory=dict)
    rule_id: str = "PROFORMA-GUARD-001"


class DebugRequest(BaseModel):
    plan: dict[str, Any]
    facts: dict[str, Any] = Field(default_factory=dict)
    answers: dict[str, Any] = Field(default_factory=dict)


class EntailmentRequest(BaseModel):
    entity_id: str = Field(min_length=1, max_length=160)
    requested_class: str = Field(min_length=1, max_length=160)


class RelationshipRequest(BaseModel):
    subject_id: str
    predicate: str
    object_id: str


class ComposeRequest(BaseModel):
    object_id: str = Field(min_length=1, max_length=160)
    workspace: str = Field(min_length=1, max_length=80)
    template: str
    slots: dict[str, Any]


class RouteRequest(BaseModel):
    object_id: str
    workspace: str
    predicate: Any
    context: dict[str, Any] = Field(default_factory=dict)


class PluginConfigRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class AppraisalEvaluateRequest(BaseModel):
    appraisal_id: str = Field(min_length=1, max_length=160)
    evidence_id: str = Field(min_length=1, max_length=160)
    expression: Any
    context: dict[str, Any] = Field(default_factory=dict)
    table_id: str = "APP-001"
    table_version: str = "1.0.0"


class SimulationStartRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=120)
    seed: int = Field(ge=0, le=4294967295)


class SimulationActionRequest(BaseModel):
    action: dict[str, Any]


class SimulationAdvanceRequest(BaseModel):
    minutes: int = Field(ge=1, le=60)


class SimulationDocumentRequest(BaseModel):
    document_type: str
    content: dict[str, Any]

class SimulationDebriefRequest(BaseModel):
    responses: dict[str, str] = Field(default_factory=dict)

class SimulationCounterfactualRequest(BaseModel):
    omit_action_id: str = Field(min_length=2, max_length=100)

class InstitutionalAuthRequest(BaseModel):
    role: str = Field(default="learner", max_length=40)
    subject_id: str = Field(default="", max_length=160)

class CohortRequest(BaseModel):
    cohort_id: str = Field(default="", max_length=100)
    title: str = Field(min_length=2, max_length=160)
    specialty: str = Field(default="General", max_length=100)
    learner_level: str = Field(default="Mixed", max_length=100)
    privacy_notice: str = Field(default="Local educational use; no patient identifiers.", max_length=3000)
    retention_days: int = Field(default=365, ge=1, le=3650)

class CohortMemberRequest(BaseModel):
    subject_id: str = Field(min_length=1, max_length=160)
    role: str = Field(default="learner", max_length=40)

class FacilitationSessionRequest(BaseModel):
    cohort_id: str = Field(min_length=1, max_length=100)
    scenario_id: str = Field(min_length=1, max_length=100)
    scenario_version: str = Field(min_length=1, max_length=40)
    facilitator_id: str = Field(min_length=1, max_length=160)

class FacilitationEventRequest(BaseModel):
    subject_id: str = Field(min_length=1, max_length=160)
    action: str = Field(min_length=2, max_length=40)
    detail: dict[str, Any] = Field(default_factory=dict)

class AccountCreateRequest(BaseModel):
    subject_id: str = Field(min_length=2, max_length=160)
    display_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(default="learner", max_length=40)
    training_level: str = Field(default="student", max_length=40)

class LoginRequest(BaseModel):
    subject_id: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=256)

class PrivacyPolicyRequest(BaseModel):
    data_scope: str = Field(min_length=2, max_length=160)
    retention_days: int = Field(default=365, ge=1, le=3650)
    consent_status: str = Field(default="acknowledged", max_length=40)
    encryption_at_rest: str = Field(default="deployment_managed", max_length=160)

class SafetyCaseRequest(BaseModel):
    scenario_id: str = Field(min_length=2, max_length=100)
    scenario_version: str = Field(min_length=1, max_length=40)
    hazard: str = Field(min_length=3, max_length=3000)
    safety_requirement: str = Field(min_length=3, max_length=3000)
    control: str = Field(min_length=3, max_length=3000)
    residual_risk: str = Field(min_length=3, max_length=3000)
    evidence_status: str = Field(default="pending", max_length=100)
    clinical_owner: str = Field(min_length=2, max_length=160)

class SafetyCaseReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=2, max_length=160)
    decision: str = Field(min_length=3, max_length=40)
    residual_risk_acceptance: str = Field(default="", max_length=3000)
    note: str = Field(default="", max_length=3000)


class ScenarioPackageRequest(BaseModel):
    scenario: dict[str, Any]


def _principal(admin_token: str | None, session_id: str | None,
               roles: set[str]) -> dict[str, Any]:
    """Resolve one authenticated principal or fail with a typed HTTP error."""
    try:
        return INSTITUTIONAL_AUTH.principal(admin_token=admin_token,
                                            session_id=session_id, roles=roles)
    except PermissionError as exc:
        raise HTTPException(403, {"state": "forbidden", "detail": str(exc)}) from exc
    except InstitutionalError as exc:
        raise HTTPException(401, {"state": "unauthenticated", "detail": str(exc)}) from exc


def _institution(principal: dict[str, Any]) -> str:
    return str(principal.get("institution_id") or DEFAULT_INSTITUTION)


def _governance_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, {"state": "not_found", "detail": str(exc)})
    return HTTPException(422, {"state": "invalid", "detail": str(exc)})


@router.get("/architecture")
def architecture() -> dict[str, Any]:
    return {
        "version": APP_VERSION, "architecture": "modular_monolith", "ai_models": 0,
        "services_added": 0, "logic_language": LOGIC_VERSION,
        "modules": ["Kernel", "Reasoner", "Logic", "Composer", "Router", "Guards", "Explain", "SimulationRuntime"],
        "client": {"applications": 1, "workspace_skins": 6, "plugin_runtime": "in_process_module_registry"},
        "invariants": {
            "canonical_event_log": "one append-only SHA-256 linked ledger",
            "executable_logic": "PROforma subset is the single executable predicate/task language",
            "unknown": "fail-closed abstention and visible escalation",
            "clinical_lineage": "assertion -> evidence -> appraisal -> source event",
            "skins": "presentation/configuration only",
            "derived_state": ["competencies", "gaps", "conflicts", "mastery", "review_dates"],
        },
        "guard_layers": 4, "fixture_imports_are_runtime_infrastructure": False,
        "reasoning": {"argumentation": "PROforma native weighted arguments; preference is indicative",
                      "smt": "in-process Z3 library; CNF, consistency, differential and counterfactual methods",
                      "asp": "in-process Clingo library; versioned rule data; " + RULESET_ID,
                      "explanation": "one derivation trace with clinical, pedagogical and negative renderings"},
        "boundaries": {"owl": "finite positive taxonomy subset; not full OWL-DL",
                       "proforma": "bounded executable subset; not certified full-language conformance",
                       "pulse": PULSE.get_state()["status"]},
        "institutional": {
            "authentication": "local_password_sessions_and_shared_admin_token",
            "rbac_roles": sorted(ROLES),
            "tenancy": "institution_scoped_rows_in_one_local_sqlite_database",
            "enterprise_sso_mfa": "not_implemented",
            "encryption_at_rest": "deployment_responsibility",
        },
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {"kernel": KERNEL.status(), "module_count": 7,
            "logic_language": LOGIC_VERSION, "pulse": PULSE.get_state(),
            "ai_models": 0, "new_services": 0, "version": APP_VERSION}


@router.post("/institution/authenticate")
def institutional_authenticate(payload: InstitutionalAuthRequest,
                               x_hsptl_admin_token: str | None = Header(default=None)):
    return INSTITUTIONAL_AUTH.verify(x_hsptl_admin_token, payload.role, payload.subject_id)


@router.post("/institution/accounts")
def institutional_create_account(payload: AccountCreateRequest,
                                 x_hsptl_admin_token: str | None = Header(default=None),
                                 x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    try:
        return INSTITUTIONAL_AUTH.create_account(payload.subject_id, payload.display_name,
                                                 payload.password, payload.role,
                                                 _institution(principal), payload.training_level)
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.post("/institution/login")
def institutional_login(payload: LoginRequest):
    try:
        return INSTITUTIONAL_AUTH.login(payload.subject_id, payload.password)
    except InstitutionalError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post("/institution/logout")
def institutional_logout(x_hsptl_session: str | None = Header(default=None)):
    if not x_hsptl_session:
        raise HTTPException(401, "A session is required.")
    return INSTITUTIONAL_AUTH.logout(x_hsptl_session)


@router.get("/institution/session")
def institutional_session(x_hsptl_session: str | None = Header(default=None)):
    """Describe the current session without exposing any tenant data."""
    principal = _principal(None, x_hsptl_session, set(ROLES))
    return {"state": "authenticated", "subject_id": principal["subject_id"],
            "institution_id": principal["institution_id"], "role": principal["role"],
            "training_level": principal.get("training_level", "unspecified"),
            "scope": principal.get("scope", "local_rbac_session")}


@router.get("/institution/cohorts")
def institutional_cohorts(x_hsptl_admin_token: str | None = Header(default=None),
                          x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    items = COHORTS.list_cohorts(_institution(principal))
    return {"items": items, "count": len(items), "scope": "institution_scoped_governance_api",
            "institution_id": _institution(principal),
            "authentication": "local session or shared deployment token"}


@router.post("/institution/cohorts")
def institutional_create_cohort(payload: CohortRequest,
                                x_hsptl_admin_token: str | None = Header(default=None),
                                x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    try:
        return COHORTS.create_cohort(payload.model_dump(), _institution(principal))
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.post("/institution/cohorts/{cohort_id}/members")
def institutional_add_member(cohort_id: str, payload: CohortMemberRequest,
                             x_hsptl_admin_token: str | None = Header(default=None),
                             x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    try:
        return COHORTS.add_member(cohort_id, payload.subject_id, payload.role,
                                  _institution(principal))
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.get("/institution/cohorts/{cohort_id}/members")
def institutional_cohort_members(cohort_id: str,
                                 x_hsptl_admin_token: str | None = Header(default=None),
                                 x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    try:
        COHORTS.get_cohort(cohort_id, _institution(principal))
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    return {"items": COHORTS.list_members(cohort_id, _institution(principal)),
            "cohort_id": cohort_id}


@router.post("/institution/sessions")
def institutional_create_session(payload: FacilitationSessionRequest,
                                 x_hsptl_admin_token: str | None = Header(default=None),
                                 x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    try:
        session = COHORTS.create_session(payload.model_dump(), _institution(principal))
        event = KERNEL.append("platform.facilitation.session_created", {
            "session_id": session["session_id"], "cohort_id": session["cohort_id"],
            "scenario_id": session["scenario_id"], "scenario_version": session["scenario_version"],
            "facilitator_id": session["facilitator_id"], "status": session["status"],
            "institution_id": session["institution_id"],
        })
        return {**session, "event_id": event["event_id"]}
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.post("/institution/sessions/{session_id}/events")
def institutional_facilitation_event(session_id: str, payload: FacilitationEventRequest,
                                     x_hsptl_admin_token: str | None = Header(default=None),
                                     x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    try:
        event = COHORTS.record_event(session_id, payload.subject_id, payload.action,
                                     payload.detail, _institution(principal))
        recorded = KERNEL.append("platform.facilitation.event_recorded", {
            "session_id": session_id, "subject_id": payload.subject_id[:160],
            "action": payload.action, "detail": payload.detail,
            "institution_id": _institution(principal),
        })
        return {**event, "kernel_event_id": recorded["event_id"]}
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.get("/institution/sessions")
def institutional_sessions(cohort_id: str = "",
                           x_hsptl_admin_token: str | None = Header(default=None),
                           x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"facilitator", "admin"})
    return {"items": COHORTS.list_sessions(cohort_id, _institution(principal)),
            "cohort_id": cohort_id}


@router.post("/institution/privacy/policy")
def institutional_privacy_policy(payload: PrivacyPolicyRequest,
                                 x_hsptl_admin_token: str | None = Header(default=None),
                                 x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    try:
        return COHORTS.set_privacy_policy(payload.data_scope, payload.retention_days,
                                          payload.consent_status, payload.encryption_at_rest,
                                          _institution(principal))
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.get("/institution/privacy/policies")
def institutional_privacy_policies(x_hsptl_admin_token: str | None = Header(default=None),
                                   x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    items = COHORTS.privacy_policies(_institution(principal))
    return {"items": items, "count": len(items), "institution_id": _institution(principal)}


@router.post("/institution/privacy/purge-expired-sessions")
def institutional_purge_expired_sessions(x_hsptl_admin_token: str | None = Header(default=None),
                                         x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    return COHORTS.purge_expired_sessions(_institution(principal))


@router.post("/institution/privacy/purge-retention")
def institutional_purge_retention(x_hsptl_admin_token: str | None = Header(default=None),
                                  x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    return COHORTS.purge_expired_cohort_data(_institution(principal))


@router.get("/institution/privacy/purge-audit")
def institutional_purge_audit(x_hsptl_admin_token: str | None = Header(default=None),
                              x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    return {"items": COHORTS.purge_audit(_institution(principal))}


@router.post("/institution/recovery/backup")
def institutional_recovery_backup(x_hsptl_admin_token: str | None = Header(default=None),
                                  x_hsptl_session: str | None = Header(default=None)):
    _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    try:
        backup_dir = PATHS["root"] / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = backup_dir / f"hsptl-{APP_VERSION}-{stamp}.sqlite3"
        STORE.backup_to(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return {"backup": str(destination), "sha256": digest,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "scope": "committed SQLite database", "restore_method":
                    "Stop HSPTL, replace hsptl.sqlite3 with a verified backup, and restart. Recovery should be performed from an administrator-maintained copy."}
    except (OSError, ValueError) as exc:
        raise HTTPException(500, f"Backup could not be created: {exc}") from exc


@router.get("/institution/recovery/backups")
def institutional_recovery_backups(x_hsptl_admin_token: str | None = Header(default=None),
                                   x_hsptl_session: str | None = Header(default=None)):
    _principal(x_hsptl_admin_token, x_hsptl_session, {"admin"})
    backup_dir = PATHS["root"] / "backups"
    items = []
    if backup_dir.is_dir():
        for path in sorted(backup_dir.glob("*.sqlite3"), reverse=True)[:20]:
            items.append({"backup": str(path), "bytes": path.stat().st_size,
                          "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"items": items, "count": len(items)}


@router.get("/standards/manifest")
def standards_manifest():
    return ports_manifest() | {
        "terminology": {
            "embedded_exact_match": "active",
            "snowstorm": "configured" if TERMINOLOGY.snowstorm_url else "not_configured",
            "environment": "HSPTL_SNOWSTORM_URL",
        },
        "configuration": {
            "fhir_base": os.environ.get("HSPTL_FHIR_BASE", "http://hl7.org/fhir/R4"),
            "cql_review_required": True,
            "cds_hooks_hosted_service": False,
        },
    }


@router.post("/standards/terminology/lookup")
def standards_terminology_lookup(payload: dict[str, Any]):
    term = str(payload.get("term", "")).strip()
    return TERMINOLOGY.lookup(term)


@router.get("/standards/simulation-runs/{run_id}/fhir")
def standards_simulation_fhir(run_id: str):
    try:
        run = SIMULATION.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    observations = []
    loinc_map = {
        "heart_rate": ("8867-4", "Heart rate"),
        "respiratory_rate": ("9279-1", "Respiratory rate"),
        "spo2": ("2708-6", "Oxygen saturation"),
        "blood_pressure": ("85354-9", "Blood pressure panel"),
        "temperature": ("8310-5", "Body temperature"),
    }
    for key, observation in run["observations"].items():
        code, display = loinc_map.get(key, ("", str(observation.get("display", key))))
        if not code:
            continue
        try:
            value = observation["value"]
            numeric = float(str(value).replace("%", "").replace("°C", "").strip())
        except (TypeError, ValueError):
            continue
        observations.append(fhir_observation({
            "id": f"{run_id}-{key}",
            "code": code,
            "display": display,
            "value": numeric,
            "unit": str(observation.get("unit", "")),
            "effective": f"T+{run['simulation_time_min']}m",
            "source": "hsptl-synthetic-simulation",
            "status": "preliminary",
        }))
    return {"resourceType": "Bundle", "type": "collection",
            "meta": {"tag": [{"system": "https://hsptl.local/education",
                              "code": "synthetic-teaching-data"}]},
            "entry": [{"resource": item} for item in observations],
            "limitations": ["Synthetic teaching export; not for real-patient care.",
                            "No medication or treatment recommendation is exported.",
                            "Effective times are simulation-relative integers, not clinical timestamps."]}


@router.post("/standards/cql/export")
def standards_cql_export(payload: dict[str, Any]):
    try:
        return cql_export(str(payload.get("rule_id", "")), str(payload.get("expression", "")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/standards/cds-hooks/descriptor")
def standards_cds_descriptor(payload: dict[str, Any]):
    try:
        return cds_hooks_descriptor(str(payload.get("service_id", "")),
                                    str(payload.get("title", "")),
                                    str(payload.get("hook", "")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/standards/cds-hooks/card")
def standards_cds_card(payload: dict[str, Any]):
    try:
        return cds_hooks_card(str(payload.get("summary", "")),
                              str(payload.get("detail", "")),
                              str(payload.get("indicator", "info")))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/institution/calibration/export")
def institutional_calibration_export(x_hsptl_admin_token: str | None = Header(default=None),
                                    x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"admin", "reviewer"})
    institution_id = _institution(principal)
    quiz_events = KERNEL.events(limit=10000)
    rows = []
    for event in quiz_events:
        payload = event.get("payload", {})
        if (event["event_type"] == "platform.learning.quiz_submitted"
                and payload.get("institution_id", DEFAULT_INSTITUTION) == institution_id):
            rows.append({
                "attempt_id": payload.get("attempt_id"),
                "unit_id": payload.get("unit_id"),
                "pack_version": payload.get("pack_version"),
                "score": payload.get("score"),
                "maximum": payload.get("maximum"),
                "responses": payload.get("responses", []),
                "objective_results": payload.get("objective_results", []),
                "submitted_at": payload.get("submitted_at"),
            })
    return {
        "format": "hsptl-psychometric-calibration-v1",
        "purpose": "Institutional research export only; not live calibrated psychometrics.",
        "row_count": len(rows),
        "minimum_representative_sample": "Not established",
        "calibration_status": "blocked_until_representative_reviewed_dataset" if len(rows) < 500 else "dataset_threshold_met_pending_independent_validation",
        "activation_allowed": False,
        "minimum_rows_for_review": 500,
        "review_requirements": [
            "representative learner sample",
            "item and rater analysis",
            "subgroup fairness review",
            "external psychometric validation",
            "institutional approval",
        ],
        "learner_ids_excluded": True,
        "institution_id": institution_id,
        "scope": "authenticated institution export",
        "rows": rows,
    }


@router.post("/institution/safety-cases")
def institutional_create_safety_case(payload: SafetyCaseRequest,
                                     x_hsptl_admin_token: str | None = Header(default=None),
                                     x_hsptl_session: str | None = Header(default=None)):
    try:
        principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"reviewer", "admin"})
        return COHORTS.create_safety_case(payload.model_dump(), _institution(principal))
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc


@router.get("/institution/safety-cases")
def institutional_safety_cases(scenario_id: str = "",
                               x_hsptl_admin_token: str | None = Header(default=None),
                               x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"reviewer", "admin"})
    items = COHORTS.list_safety_cases(scenario_id, _institution(principal))
    return {"items": items, "count": len(items), "scenario_id": scenario_id,
            "institution_id": _institution(principal)}


@router.post("/institution/safety-cases/{case_id}/review")
def institutional_review_safety_case(case_id: str, payload: SafetyCaseReviewRequest,
                                     x_hsptl_admin_token: str | None = Header(default=None),
                                     x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"reviewer", "admin"})
    try:
        review = COHORTS.review_safety_case(case_id, payload.reviewer_id, payload.decision,
                                            payload.residual_risk_acceptance,
                                            payload.note, _institution(principal))
    except InstitutionalError as exc:
        raise _governance_error(exc) from exc
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    KERNEL.append("platform.safety.case_reviewed", {
        "case_id": case_id, "reviewer_id": review["reviewer_id"],
        "decision": review["decision"], "institution_id": _institution(principal),
    })
    return review


@router.get("/institution/safety-cases/reviews")
def institutional_safety_case_reviews(case_id: str = "",
                                      x_hsptl_admin_token: str | None = Header(default=None),
                                      x_hsptl_session: str | None = Header(default=None)):
    principal = _principal(x_hsptl_admin_token, x_hsptl_session, {"reviewer", "admin"})
    return {"items": COHORTS.safety_case_reviews(case_id, _institution(principal)),
            "case_id": case_id, "institution_id": _institution(principal)}


@router.get("/institution/governance/readiness")
def institutional_governance_readiness() -> dict[str, Any]:
    """Public, non-sensitive statement of what this deployment can and cannot do."""
    return {
        "authentication": "configured" if INSTITUTIONAL_AUTH.configured() else "not_configured",
        "password_accounts": "available",
        "rbac_session_roles": sorted(ROLES),
        "rbac_enforced_endpoints": "all /api/v4/institution/* governance routes",
        "loopback_only": True,
        "cohort_governance": "available",
        "tenant_scoping": "institution_id column on every governance table",
        "clinical_approval": "external_not_completed",
        "safety_case_review": "local_record_only_pending_external_approval",
        "formal_assessment": "blocked",
        "backup_endpoint": "available",
        "retention_controls": "per_cohort_retention_with_audited_purge",
        "privacy_scope": "local synthetic educational use; no verified real-patient deployment",
        "enterprise_identity": "not_configured",
        "enterprise_sso_mfa": "not_implemented",
        "enterprise_encryption_at_rest": "deployment_responsibility",
        "production_multi_tenancy": "not_implemented",
        "clinical_safety_owner": "not_assigned",
        "psychometric_calibration": "blocked_until_representative_reviewed_dataset",
        "limitations": [
            "Shared HSPTL_ADMIN_TOKEN is a local governance credential, not MFA or SSO.",
            "Institution scoping isolates rows in one local SQLite file; it is not a hardened multi-tenant service.",
            "Clinical review credentials do not independently verify reviewer qualifications.",
            "Safety-case decisions are local records; external clinical approval is still required.",
            "Psychometric parameters must not be interpreted as validated competence measures.",
        ],
    }


@router.get("/event-catalogue")
def event_catalogue_route():
    return event_catalogue()


@router.get("/events")
def events(after: int = 0, limit: int = 200, platform_only: bool = False):
    return {"items": KERNEL.platform_events(after=after, limit=limit) if platform_only
            else KERNEL.events(after=after, limit=limit)}


@router.post("/replay")
def replay(through_seq: int | None = None):
    try:
        result = KERNEL.replay(through_seq)
    except Exception as exc:
        raise HTTPException(409, {"state": "abstain", "guard": "G-EVENT-001", "reason": str(exc)}) from exc
    return {"events_replayed": result["events_replayed"], "verified": result["verified"],
            "projection_hash": result["projection_hash"], "status": KERNEL.status()}


@router.get("/logic/models")
def logic_models():
    return model_catalogue()


@router.get("/logic/catalogue")
def logic_catalogue():
    return {"language": LOGIC_VERSION, "root_task": "plan",
            "task_types": ["plan", "decision", "action", "inquiry"],
            "predicate_operators": ["and", "or", "not", "implies", "eq", "neq", "in", "contains",
                                    "gt", "gte", "lt", "lte", "exists", "set_includes"],
            "decision_model": "native weighted PROforma arguments; for/against; additive force; no automatic selection",
            "temporal_prerequisites": "requires_before is checked by the in-process Clingo rule bundle",
            "unsupported_policy": "unknown => abstain",
            "execution": "Plans contain ordered decisions, actions and inquiries; no arbitrary code execution."}


@router.post("/logic/validate")
def logic_validate(payload: dict[str, Any]):
    return validate_plan(payload)


@router.post("/logic/enactments")
def logic_enact(payload: EnactRequest):
    try:
        return LOGIC.enact(payload.plan, facts=payload.facts, metadata=payload.metadata)
    except ProformaError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/logic/enactments/{enactment_id}")
def logic_get(enactment_id: str):
    return _call(LOGIC.get, enactment_id)


@router.post("/logic/enactments/{enactment_id}/step")
def logic_step(enactment_id: str, payload: StepRequest):
    try:
        return LOGIC.step(enactment_id, payload.task_id, value=payload.value,
                          context_patch=payload.context_patch)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ProformaError as exc:
        try:
            snapshot = LOGIC.get(enactment_id)
        except KeyError:
            snapshot = {"state": None, "availability": {}}
        raise HTTPException(409, {"state": snapshot.get("state"),
                                  "availability": snapshot.get("availability"),
                                  "reason": str(exc)}) from exc


@router.post("/logic/debug")
def logic_debug(payload: DebugRequest):
    return debug_proforma(payload.plan, payload.facts, payload.answers)


@router.post("/logic/smt/argument-consistency")
def logic_argument_consistency(payload: dict[str, Any]):
    return LOGIC.smt.check_argument_consistency(payload.get("arguments", []), payload.get("context", {}))


@router.post("/logic/smt/differentials")
def logic_differentials(payload: dict[str, Any]):
    return LOGIC.smt.enumerate_differentials(payload.get("hypotheses", []),
        payload.get("findings", []), payload.get("context", {}))


@router.post("/logic/smt/counterfactual")
def logic_counterfactual(payload: dict[str, Any]):
    return LOGIC.smt.counterfactual_single_finding(payload.get("decision", {}),
        payload.get("context", {}), payload.get("proposed_findings", []))


@router.post("/logic/explanations/render")
def logic_render_explanation(payload: dict[str, Any]):
    try:
        return render_explanation(payload.get("derivation", {}), payload.get("audience", "clinical"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/logic/temporal/analyze")
def logic_temporal_analyze(payload: dict[str, Any]):
    enactment_id = str(payload.get("enactment_id", ""))
    plan = payload.get("plan", {})
    if not enactment_id or not isinstance(plan, dict):
        raise HTTPException(422, "enactment_id and plan are required.")
    return LOGIC.temporal_reasoner.analyze(KERNEL.events(limit=10000), plan, enactment_id)


@router.get("/guards/catalogue")
def guards_catalogue():
    return guard_catalogue()


@router.post("/guards/evaluate")
def guard_evaluate(payload: GuardRequest):
    return GUARDS.decide(payload.guard_id, payload.expression, payload.context,
                         rule_id=payload.rule_id).as_dict()


@router.post("/guards/smt")
def guard_smt(payload: dict[str, Any]):
    return GUARDS.optional_solver(payload, required=bool(payload.get("required", True))).as_dict()


@router.post("/appraisal/evaluate")
def appraisal_evaluate(payload: AppraisalEvaluateRequest):
    result = GUARDS.decide("G-APP-001", payload.expression, payload.context,
                           rule_id="PROFORMA-APPRAISAL-001")
    try:
        recorded = ENGINE.record_appraisal(payload.appraisal_id, payload.evidence_id,
            result.decision, payload.table_id, payload.table_version,
            {"language": LOGIC_VERSION, "guard": result.as_dict()})
    except Abstention as exc:
        raise HTTPException(409, {"state": "abstain", "guard": exc.guard,
                                  "reason": exc.reason, "event_id": exc.event_id}) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"decision": result.decision, "appraisal": recorded,
            "derivation": result.as_dict()}


@router.get("/reasoner/catalogue")
def reasoner_catalogue():
    return REASONER.catalogue()


@router.post("/reasoner/entail")
def reasoner_entail(payload: EntailmentRequest):
    return REASONER.entails_type(payload.entity_id, payload.requested_class)


@router.post("/reasoner/relationship")
def reasoner_relationship(payload: RelationshipRequest):
    return REASONER.relationship(payload.subject_id, payload.predicate, payload.object_id)


@router.post("/reasoner/competencies")
def reasoner_competencies(payload: dict[str, Any]):
    return REASONER.entailed_competencies(payload.get("learning_object_ids", []))


@router.post("/reasoner/conflicts")
def reasoner_conflicts(payload: dict[str, Any]):
    result = REASONER.detect_conflict(str(payload.get("proposition_key", "")),
        str(payload.get("scope_key", "")), str(payload.get("evidence_a", "")),
        str(payload.get("evidence_b", "")), str(payload.get("polarity_a", "")),
        str(payload.get("polarity_b", "")))
    if result["state"] == "abstain":
        raise HTTPException(409, result)
    return result


@router.get("/composer/templates")
def composer_templates():
    return COMPOSER.catalogue()


@router.get("/composer/graph")
def composer_graph():
    return COMPOSER.graph_projection()


@router.post("/composer/compose")
def composer_compose(payload: ComposeRequest):
    result = _call(COMPOSER.compose, payload.object_id, payload.workspace, payload.template, payload.slots)
    if result.get("state") != "pass":
        raise HTTPException(409, result)
    return result


@router.post("/router/eligibility")
def router_eligibility(payload: dict[str, Any]):
    return ROUTER.eligibility(payload.get("predicate"), payload.get("context", {}))


@router.post("/router/route")
def router_route(payload: RouteRequest):
    result = ROUTER.route(payload.object_id, payload.workspace, payload.predicate, payload.context)
    if result.get("state") != "pass":
        raise HTTPException(409, result)
    return result


@router.post("/router/topological-order")
def router_order(payload: dict[str, Any]):
    result = ROUTER.topological_order(payload.get("prerequisites", {}))
    if result["state"] != "pass":
        raise HTTPException(409, result)
    return result


@router.post("/router/irt/estimate")
def router_irt(payload: dict[str, Any]):
    result = ROUTER.estimate_irt(payload.get("responses", []))
    if result["state"] != "pass":
        raise HTTPException(409, result)
    return result


@router.post("/router/reasoned-sequence")
def router_reasoned_sequence(payload: dict[str, Any]):
    return ROUTER.reasoned_sequence(
        payload.get("candidates", []), responses=payload.get("responses", []),
        completed_prerequisites=payload.get("completed_prerequisites", []),
        calibration_history=payload.get("calibration_history", []),
        today=payload.get("today"),
        target_success_probability=payload.get("target_success_probability", 0.65),
        brier_threshold=payload.get("brier_threshold", 0.20))


@router.post("/router/fsrs/next-review")
def router_fsrs(payload: dict[str, Any]):
    result = ROUTER.fsrs_next_review(payload.get("card", {}), payload.get("grade", "Good"),
                                     today=payload.get("today"))
    if result["state"] != "pass":
        raise HTTPException(409, result)
    return result


@router.post("/analytics/gaps")
def analytics_gaps(payload: dict[str, Any]):
    return ROUTER.coverage_gaps(payload.get("required", []), payload.get("covered", []))


@router.post("/analytics/mastery/events")
def mastery_event(payload: dict[str, Any]):
    return _call(ROUTER.record_mastery_signal, str(payload.get("competency_id", "")),
        str(payload.get("learner_id", "")), str(payload.get("signal", "")),
        str(payload.get("evidence_ref", "")), str(payload.get("reviewer", "")))


@router.get("/analytics/mastery")
def analytics_mastery(learner_id: str | None = None):
    return ROUTER.mastery_fold(learner_id)


@router.get("/workspaces/skins")
def workspace_skins():
    return REGISTRY.manifest()


@router.put("/workspaces/{workspace}/plugins/config")
def configure_plugin(workspace: str, payload: PluginConfigRequest):
    try:
        config = REGISTRY.configure(workspace, payload.config)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    event = KERNEL.append("platform.plugin.configured", {"workspace": workspace, "config": config})
    return {"workspace": workspace, "config": config, "event": event}


@router.get("/simulation/scenario-authoring/template")
def simulation_scenario_template():
    scenario = SIMULATION.catalog.load("asthma-moderate-adult-001")
    scenario = {**scenario, "scenario_id": "educator-scenario-" + uuid.uuid4().hex[:10], "version": "1.0.0",
                "title": "New educator scenario draft", "clinical_review_status": "draft_pending_clinical_review"}
    scenario.pop("clinical_review", None)
    scenario.pop("authoring", None)
    return {"scenario": scenario, "note": "Edit the JSON package, validate it, then save it as a draft. Publishing requires a separate clinical-review credential."}


@router.get("/simulation/scenario-authoring/drafts")
def simulation_scenario_drafts():
    return {"items": SCENARIO_AUTHORING.list_drafts(), "count": len(SCENARIO_AUTHORING.list_drafts()),
            "storage": "local_user_data", "status": "drafts_not_in_learner_catalogue"}


@router.get("/simulation/scenario-authoring/drafts/{scenario_id}")
def simulation_scenario_draft_detail(scenario_id: str):
    try:
        return {"scenario": SCENARIO_AUTHORING.get_draft(scenario_id)}
    except KeyError as exc:
        raise HTTPException(404, "Scenario draft not found") from exc
    except ScenarioAuthoringError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/scenario-authoring/validate")
def simulation_scenario_validate(payload: ScenarioPackageRequest):
    return SCENARIO_AUTHORING.validate(payload.scenario)


@router.post("/simulation/scenario-authoring/trace-matrix")
def simulation_scenario_trace_matrix(payload: ScenarioPackageRequest):
    try:
        return SCENARIO_AUTHORING.trace_matrix(payload.scenario)
    except ScenarioAuthoringError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/scenario-authoring/drafts", status_code=201)
def simulation_scenario_save_draft(payload: ScenarioPackageRequest):
    try:
        result = SCENARIO_AUTHORING.save_draft(payload.scenario)
        event = KERNEL.append("platform.scenario.draft_saved", {
            "scenario_id": result["scenario_id"], "version": result["version"],
            "scenario_digest": result["scenario_digest"], "author": "local-user",
            "review_status": result["clinical_review_status"]})
        return {**result, "event_id": event["event_id"]}
    except ScenarioAuthoringError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/scenario-authoring/drafts/{scenario_id}/publish")
def simulation_scenario_publish(scenario_id: str, x_hsptl_clinical_reviewer_token: str | None = Header(default=None)):
    try:
        result = SCENARIO_AUTHORING.publish(scenario_id, x_hsptl_clinical_reviewer_token)
        event = KERNEL.append("platform.scenario.published", {
            "scenario_id": result["scenario_id"], "version": result["version"],
            "scenario_digest": result["scenario_digest"], "reviewer": result["reviewer_id"],
            "reviewed_at": result["reviewed_at"]})
        return {**result, "event_id": event["event_id"]}
    except PermissionError as exc:
        raise HTTPException(401 if "Valid clinical reviewer" in str(exc) else 503, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "Scenario draft not found") from exc
    except ScenarioAuthoringError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/simulation/scenarios")
def simulation_scenarios():
    return SIMULATION.list_scenarios()


@router.get("/simulation/scenarios/{scenario_id}")
def simulation_scenario(scenario_id: str):
    try:
        scenario = SIMULATION.catalog.load(scenario_id)
        return SIMULATION.catalog.public_summary(scenario)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs")
def simulation_start(payload: SimulationStartRequest):
    try:
        return SIMULATION.start_run(payload.scenario_id, payload.seed)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except (SimulationError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/simulation/runs/{run_id}")
def simulation_get_run(run_id: str):
    try:
        return SIMULATION.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc


@router.post("/simulation/runs/{run_id}/pulse/step")
def simulation_pulse_step(run_id: str):
    try:
        bridge = PulseBridge(KERNEL, SIMULATION.pulse_provider(run_id))
        return bridge.step()
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc


@router.post("/simulation/runs/{run_id}/actions")
def simulation_action(run_id: str, payload: SimulationActionRequest):
    try:
        bridge = PulseBridge(KERNEL, SIMULATION.pulse_provider(run_id))
        result = bridge.applyAction(payload.action)
        if not result.get("applied"):
            raise HTTPException(409, {"state": "rejected", "reason": result.get("reason"),
                                      "simulation_event": result.get("provider_event"),
                                      "pulse_audit_event": result.get("event"),
                                      "proof_trace": result.get("proof_trace", [])})
        return result
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs/{run_id}/advance")
def simulation_advance(run_id: str, payload: SimulationAdvanceRequest):
    try:
        return SIMULATION.advance_time(run_id, payload.minutes)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs/{run_id}/documents")
def simulation_save_document(run_id: str, payload: SimulationDocumentRequest):
    try:
        return SIMULATION.save_document(run_id, payload.document_type, payload.content)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs/{run_id}/assessment")
def simulation_assessment(run_id: str):
    try:
        return SIMULATION.derive_assessment(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/simulation/runs/{run_id}/replay")
def simulation_replay(run_id: str):
    try:
        return SIMULATION.replay(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc


@router.post("/simulation/runs/{run_id}/debrief")
def simulation_debrief(run_id: str, payload: SimulationDebriefRequest):
    try:
        return SIMULATION.save_debrief(run_id, payload.responses)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs/{run_id}/counterfactual")
def simulation_counterfactual(run_id: str, payload: SimulationCounterfactualRequest):
    try:
        return SIMULATION.counterfactual(run_id, payload.omit_action_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/simulation/runs/{run_id}/complete")
def simulation_complete(run_id: str):
    try:
        return SIMULATION.complete(run_id)
    except KeyError as exc:
        raise HTTPException(404, {"state": "not_found", "detail": str(exc)}) from exc
    except SimulationError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/pulse/state")
def pulse_state():
    return PULSE.getState()


@router.post("/pulse/step")
def pulse_step():
    return PULSE.step()


@router.post("/pulse/actions")
def pulse_action(payload: dict[str, Any]):
    action = payload.get("action")
    if not isinstance(action, dict) or not action:
        raise HTTPException(422, "A Pulse action object is required.")
    result = PULSE.applyAction(action)
    if not result.get("applied"):
        raise HTTPException(409, {"state": "abstain", **result})
    return result


@router.get("/ports")
def ports():
    return {**ports_manifest(), "terminology": {
        "default": "embedded_concept_index", "snowstorm": "optional_full_ECL_port",
        "snowstorm_configured": bool(TERMINOLOGY.snowstorm_url),
        "snowstorm_environment": "HSPTL_SNOWSTORM_URL"}}


@router.post("/terminology/lookup")
def terminology_lookup(payload: dict[str, Any]):
    return TERMINOLOGY.lookup(str(payload.get("term", "")))


@router.post("/terminology/ecl")
def terminology_ecl(payload: dict[str, Any]):
    return TERMINOLOGY.query_ecl(str(payload.get("expression", "")))


@router.post("/standards/fhir/observation")
def standards_fhir(payload: dict[str, Any]):
    return _call(fhir_observation, payload)


@router.post("/standards/cql/export")
def standards_cql(payload: dict[str, Any]):
    return _call(cql_export, str(payload.get("rule_id", "")), str(payload.get("expression", "")))


@router.post("/standards/cds-hooks/descriptor")
def standards_cds(payload: dict[str, Any]):
    return _call(cds_hooks_descriptor, str(payload.get("service_id", "")),
                 str(payload.get("title", "")), str(payload.get("hook", "")))


@router.post("/standards/xapi/statement")
def standards_xapi(payload: dict[str, Any]):
    return _call(xapi_statement, payload.get("actor", {}), str(payload.get("verb", "")),
                 payload.get("activity", {}), payload.get("result"))


@router.post("/standards/scorm/runtime")
def standards_scorm(payload: dict[str, Any]):
    return _call(scorm_runtime_data, str(payload.get("completion", "unknown")),
                 payload.get("success"), payload.get("score"))


@router.post("/standards/lti/descriptor")
def standards_lti(payload: dict[str, Any]):
    return lti_port_descriptor(str(payload.get("issuer", "")), str(payload.get("client_id", "")),
                               str(payload.get("deployment_id", "")))
