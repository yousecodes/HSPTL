"""Versioned, declarative generation recipes.

A recipe is data, never code. It carries no executable expressions, so a user
cannot turn a recipe into a shell command. Recipes follow the lifecycle

    draft -> technical_validated -> clinical_reviewed -> active -> retired

Only ``active`` recipes may run unattended. The built-in families ship as
``draft`` on purpose: shipping them as clinically approved would be a claim this
project cannot support. A built-in recipe becomes ``active`` only after an
authenticated reviewer activates it through the API.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

LIFECYCLE = ("draft", "technical_validated", "clinical_reviewed", "active", "retired")
_ALLOWED_TRANSITIONS = {
    "draft": {"technical_validated"},
    "technical_validated": {"clinical_reviewed"},
    "clinical_reviewed": {"active"},
    "active": {"retired"},
    "retired": set(),
}

RECIPE_SCHEMA_VERSION = "hsptl.synthetic.recipe/1.0"
DEFAULT_FHIR_VERSION = "4.0.1"

# Code criteria are explicit and versioned. Nothing is inferred from display text.
CODE_SYSTEMS = {
    "snomed": "http://snomed.info/sct",
    "loinc": "http://loinc.org",
    "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "icd10cm": "http://hl7.org/fhir/sid/icd-10-cm",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_digest(body: Any) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _criteria(system: str, codes: list[str], *, description: str) -> dict[str, Any]:
    return {
        "version": "cohort/1.0",
        "system": CODE_SYSTEMS[system],
        "system_key": system,
        "codes": codes,
        "match": "any",
        "resource_types": ["Condition"],
        "description": description,
    }


def _recipe(
    recipe_id: str,
    title: str,
    description: str,
    *,
    purpose: str,
    criteria: dict[str, Any] | None,
    required_resources: list[str],
    population: int,
    max_population: int,
    csv: bool,
    history_years: int,
    severity_policy: str = "quarantine",
    review_note: str,
) -> dict[str, Any]:
    return {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "recipe_id": recipe_id,
        "version": "1.0.0",
        "title": title,
        "description": description,
        "owner": "hsptl-builtin",
        "status": "draft",
        "intended_use": purpose,
        "review_note": review_note,
        "generator": {
            "name": "synthea",
            "version_pin_required": True,
            "module_pack": "builtin-default",
            "module_pack_version": "1.0.0",
        },
        "population": {
            "default": population,
            "minimum": 1,
            "maximum": max_population,
            "max_overgeneration_multiplier": 3.0,
        },
        "demographics": {"age_min": 0, "age_max": 105, "gender": "any", "geography": ""},
        "cohort": criteria,
        "exports": {
            "fhir_version": DEFAULT_FHIR_VERSION,
            "fhir": True,
            "csv": csv,
            "years_of_history": history_years,
            "us_core_profiles": False,
        },
        "validation": {
            "rule_pack_id": "hsptl-core",
            "rule_pack_version": "1.0.0",
            "required_resources": required_resources,
            "strict_fhir_required": False,
            "terminology_mapping_set": "hsptl-mapping/1.0.0",
            "plausibility_severity_policy": severity_policy,
        },
        "limits": {"max_output_bytes": 512 * 1024 * 1024, "max_patients": max_population},
        "provenance": {"created_at": "2026-11-20", "generator": "hsptl-builtin-registry"},
    }


BUILTIN_RECIPES: list[dict[str, Any]] = [
    _recipe(
        "general-mixed-population",
        "General mixed population",
        "Unfiltered Synthea population for technical fixtures and volume testing.",
        purpose="Technical fixtures; no disease targeting.",
        criteria=None,
        required_resources=["Patient", "Encounter"],
        population=10, max_population=500, csv=True, history_years=5,
        review_note="Structural/technical recipe. Not a clinical teaching cohort.",
    ),
    _recipe(
        "asthma-cohort",
        "Asthma cohort",
        "Patients with a coded asthma condition, for respiratory teaching fixtures.",
        purpose="Respiratory case fixtures; requires clinical module review.",
        criteria=_criteria("snomed", ["195967001"], description="Asthma (SNOMED CT 195967001)"),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"],
        population=20, max_population=200, csv=True, history_years=5,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "diabetes-cohort",
        "Diabetes cohort",
        "Patients with coded type 2 diabetes, for endocrine teaching fixtures.",
        purpose="Endocrine case fixtures; requires clinical module review.",
        criteria=_criteria("snomed", ["44054006"], description="Type 2 diabetes mellitus (SNOMED CT 44054006)"),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"],
        population=20, max_population=200, csv=True, history_years=5,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "hypertension-cohort",
        "Hypertension cohort",
        "Patients with coded essential hypertension, for cardiovascular fixtures.",
        purpose="Cardiovascular case fixtures; requires clinical module review.",
        criteria=_criteria("snomed", ["59621000"], description="Essential hypertension (SNOMED CT 59621000)"),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"],
        population=20, max_population=200, csv=True, history_years=5,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "pneumonia-cohort",
        "Pneumonia cohort",
        "Patients with coded pneumonia, for acute infection fixtures.",
        purpose="Acute infection fixtures; requires clinical module review.",
        criteria=_criteria("snomed", ["233604007"], description="Pneumonia (SNOMED CT 233604007)"),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "DiagnosticReport"],
        population=20, max_population=200, csv=True, history_years=5,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "heart-failure-cohort",
        "Heart failure cohort",
        "Patients with coded heart failure, for cardiology fixtures.",
        purpose="Cardiology case fixtures; requires clinical module review.",
        criteria=_criteria("snomed", ["84114007"], description="Heart failure (SNOMED CT 84114007)"),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"],
        population=20, max_population=200, csv=True, history_years=5,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "multimorbidity-polypharmacy",
        "Multimorbidity and polypharmacy",
        "Patients carrying several chronic conditions and multiple medications.",
        purpose="Complex-care fixtures; requires clinical module review.",
        criteria=_criteria(
            "snomed",
            ["44054006", "59621000", "84114007"],
            description="Any of diabetes, hypertension or heart failure (polypharmacy screen applied at selection)",
        ),
        required_resources=["Patient", "Encounter", "Condition", "Observation", "MedicationRequest"],
        population=15, max_population=150, csv=True, history_years=8,
        review_note="Cohort criteria defined; clinical module review pending.",
    ),
    _recipe(
        "fhir-csv-integration-fixtures",
        "FHIR and CSV integration fixtures",
        "Minimal dataset for exercising the FHIR and CSV import paths.",
        purpose="Import-path integration testing only.",
        criteria=None,
        required_resources=["Patient", "Encounter", "Observation"],
        population=5, max_population=50, csv=True, history_years=2,
        review_note="Technical recipe for import testing. Never a teaching cohort.",
    ),
]


def validate_recipe_body(body: dict[str, Any]) -> list[str]:
    """Return a list of schema problems. An empty list means structurally valid."""
    problems: list[str] = []
    if not isinstance(body, dict):
        return ["Recipe body must be a JSON object."]
    for key in ("recipe_id", "version", "title", "intended_use"):
        if not isinstance(body.get(key), str) or not body.get(key, "").strip():
            problems.append(f"Recipe requires a non-empty {key}.")
    if body.get("schema_version") != RECIPE_SCHEMA_VERSION:
        problems.append(f"Recipe schema_version must be {RECIPE_SCHEMA_VERSION}.")
    population = body.get("population")
    if not isinstance(population, dict):
        problems.append("Recipe requires a population object.")
    else:
        default = population.get("default")
        maximum = population.get("maximum")
        if not isinstance(default, int) or isinstance(default, bool) or default < 1:
            problems.append("population.default must be a positive integer.")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            problems.append("population.maximum must be a positive integer.")
        elif isinstance(default, int) and default > maximum:
            problems.append("population.default must not exceed population.maximum.")
    cohort = body.get("cohort")
    if cohort is not None:
        if not isinstance(cohort, dict):
            problems.append("cohort must be an object or null.")
        else:
            if cohort.get("system") not in CODE_SYSTEMS.values():
                problems.append("cohort.system must be a known code system URI.")
            codes = cohort.get("codes")
            if not isinstance(codes, list) or not codes or not all(isinstance(c, str) and c for c in codes):
                problems.append("cohort.codes must be a non-empty list of code strings.")
    exports = body.get("exports")
    if not isinstance(exports, dict):
        problems.append("Recipe requires an exports object.")
    else:
        if exports.get("fhir_version") != DEFAULT_FHIR_VERSION:
            problems.append(f"Only FHIR R4 ({DEFAULT_FHIR_VERSION}) is supported.")
        years = exports.get("years_of_history")
        if not isinstance(years, int) or isinstance(years, bool) or not 0 <= years <= 120:
            problems.append("exports.years_of_history must be an integer between 0 and 120.")
    if not isinstance(body.get("validation"), dict):
        problems.append("Recipe requires a validation object.")
    for forbidden in ("script", "command", "python", "shell", "code"):
        if forbidden in body:
            problems.append(f"Recipes must not carry executable content ({forbidden}).")
    return problems


class RecipeRegistry:
    """SQLite-backed recipe store. Built-ins are seeded once and never overwritten."""

    def __init__(self, conn_factory):
        self._connect = conn_factory

    def seed_builtins(self) -> int:
        created = 0
        now = _now()
        with self._connect() as conn:
            for body in BUILTIN_RECIPES:
                digest = canonical_digest(body)
                existing = conn.execute(
                    "SELECT content_digest FROM synthetic_recipes WHERE recipe_id=? AND version=?",
                    (body["recipe_id"], body["version"]),
                ).fetchone()
                if existing is not None:
                    continue
                conn.execute(
                    "INSERT INTO synthetic_recipes(recipe_id, version, title, description, status, "
                    "owner, builtin, body_json, content_digest, created_at, updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (body["recipe_id"], body["version"], body["title"], body["description"],
                     body["status"], body["owner"], 1,
                     json.dumps(body, sort_keys=True, ensure_ascii=False), digest, now, now),
                )
                created += 1
        return created

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT recipe_id, version, title, description, status, owner, builtin, "
                "content_digest, reviewer, reviewed_at, updated_at FROM synthetic_recipes "
                "ORDER BY builtin DESC, title, version"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, recipe_id: str, version: str | None = None) -> dict[str, Any] | None:
        with self._connect() as conn:
            if version:
                row = conn.execute(
                    "SELECT * FROM synthetic_recipes WHERE recipe_id=? AND version=?",
                    (recipe_id, version),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM synthetic_recipes WHERE recipe_id=? ORDER BY version DESC LIMIT 1",
                    (recipe_id,),
                ).fetchone()
        if row is None:
            return None
        record = dict(row)
        record["body"] = json.loads(record.pop("body_json"))
        return record

    def create(self, body: dict[str, Any], *, owner: str = "local") -> dict[str, Any]:
        problems = validate_recipe_body(body)
        if problems:
            raise ValueError("; ".join(problems))
        now = _now()
        digest = canonical_digest(body)
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM synthetic_recipes WHERE recipe_id=? AND version=?",
                (body["recipe_id"], body["version"]),
            ).fetchone()
            if exists:
                raise ValueError("A recipe with that id and version already exists.")
            conn.execute(
                "INSERT INTO synthetic_recipes(recipe_id, version, title, description, status, "
                "owner, builtin, body_json, content_digest, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (body["recipe_id"], body["version"], body["title"], body.get("description", ""),
                 "draft", owner, 0, json.dumps(body, sort_keys=True, ensure_ascii=False),
                 digest, now, now),
            )
        return self.get(body["recipe_id"], body["version"])  # type: ignore[return-value]

    def transition(self, recipe_id: str, version: str, target: str, *,
                   reviewer: str = "") -> dict[str, Any]:
        if target not in LIFECYCLE:
            raise ValueError(f"Unknown recipe status: {target}")
        record = self.get(recipe_id, version)
        if record is None:
            raise ValueError("Recipe not found.")
        current = record["status"]
        if target not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError(f"Cannot move a {current} recipe to {target}.")
        if target in {"clinical_reviewed", "active"} and not reviewer.strip():
            raise ValueError("A reviewer identity is required for clinical review and activation.")
        now = _now()
        # ``version`` may be empty, in which case ``get`` resolved the latest
        # version. The UPDATE must target that resolved version, not the input.
        with self._connect() as conn:
            conn.execute(
                "UPDATE synthetic_recipes SET status=?, reviewer=?, reviewed_at=?, updated_at=? "
                "WHERE recipe_id=? AND version=?",
                (target, reviewer[:160], now if reviewer else record["reviewed_at"],
                 now, recipe_id, record["version"]),
            )
        return self.get(recipe_id, record["version"])  # type: ignore[return-value]

    def active_recipes(self) -> list[dict[str, Any]]:
        return [r for r in self.list() if r["status"] == "active"]
