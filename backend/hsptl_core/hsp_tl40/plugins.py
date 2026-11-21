"""In-process workspace skin and customization plugin registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class WorkspaceModule:
    module_id: str
    workspace: str
    contributes: tuple[str, ...]
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkspaceSkin:
    workspace: str
    label: str
    presentation: dict[str, str]
    modules: tuple[str, ...]
    routing_profile: str


class PluginRegistry:
    """Static, trusted module registry; plugins execute in the host process."""
    def __init__(self) -> None:
        self._modules: dict[str, WorkspaceModule] = {}
        self._skins: dict[str, WorkspaceSkin] = {}
        self._config: dict[str, dict[str, Any]] = {}

    def register_module(self, module: WorkspaceModule) -> None:
        if module.module_id in self._modules:
            raise ValueError(f"Module already registered: {module.module_id}")
        self._modules[module.module_id] = module

    def register_skin(self, skin: WorkspaceSkin) -> None:
        if skin.workspace in self._skins:
            raise ValueError(f"Skin already registered: {skin.workspace}")
        unknown = set(skin.modules) - set(self._modules)
        if unknown:
            raise ValueError(f"Skin references unknown modules: {sorted(unknown)}")
        self._skins[skin.workspace] = skin
        self._config[skin.workspace] = {}

    @staticmethod
    def _matches_type(value: Any, expected: str) -> bool:
        return {
            "string": lambda x: isinstance(x, str),
            "array": lambda x: isinstance(x, list),
            "object": lambda x: isinstance(x, dict),
            "boolean": lambda x: isinstance(x, bool),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        }.get(expected, lambda x: False)(value)

    def configure(self, workspace: str, config: dict[str, Any]) -> dict[str, Any]:
        if workspace not in self._skins:
            raise KeyError(workspace)
        # Config is presentation/interaction only. Keys that resemble facts or
        # clinical rules are explicitly prohibited at this plugin boundary.
        forbidden = {"clinical_facts", "diagnoses", "evidence", "appraisal_rules", "routing_predicates", "preconditions"}
        if forbidden.intersection(config):
            raise ValueError("Workspace plugins cannot own clinical facts or executable clinical rules.")
        schemas = [self._modules[module_id].config_schema for module_id in self._skins[workspace].modules]
        schemas = [schema for schema in schemas if schema]
        if schemas:
            properties: dict[str, Any] = {}
            required: set[str] = set()
            for schema in schemas:
                properties.update(schema.get("properties", {}))
                required.update(schema.get("required", []))
            unknown = set(config) - set(properties)
            if unknown:
                raise ValueError(f"Unsupported presentation config keys: {sorted(unknown)}")
            missing = required - (set(self._config[workspace]) | set(config))
            if missing:
                raise ValueError(f"Required presentation config keys are missing: {sorted(missing)}")
            for key, value in config.items():
                spec = properties[key]
                if not self._matches_type(value, spec.get("type", "")):
                    raise ValueError(f"Presentation config {key!r} must be {spec.get('type')}.")
                if "enum" in spec and value not in spec["enum"]:
                    raise ValueError(f"Presentation config {key!r} must be one of {spec['enum']}.")
                if spec.get("maxItems") is not None and isinstance(value, list) and len(value) > spec["maxItems"]:
                    raise ValueError(f"Presentation config {key!r} exceeds maxItems.")
        self._config[workspace] = {**self._config[workspace], **config}
        return self._config[workspace]

    def manifest(self) -> dict[str, Any]:
        return {
            "skins": {key: {"workspace": skin.workspace, "label": skin.label,
                            "presentation": dict(skin.presentation),
                            "modules": list(skin.modules), "routing_profile": skin.routing_profile,
                            "config": dict(self._config[key])}
                      for key, skin in self._skins.items()},
            "modules": {key: {"workspace": module.workspace, "contributes": list(module.contributes),
                              "config_schema": module.config_schema}
                        for key, module in self._modules.items()},
            "deployables_added": 0,
        }


def build_default_registry() -> PluginRegistry:
    registry = PluginRegistry()
    modules = [
        WorkspaceModule("case-reasoning", "clinic", ("case-enactment", "debrief"), {
            "properties": {"focus": {"type": "string", "maxLength": 120}, "section_labels": {"type": "object"}},
            "additionalProperties": False}),
        WorkspaceModule("evidence-teaching", "rounds", ("viva", "reports", "procedure-prep"), {
            "properties": {"focus": {"type": "string", "maxLength": 120}, "section_labels": {"type": "object"}},
            "additionalProperties": False}),
        WorkspaceModule("pulse-renderers", "lab", ("vitals", "spotters", "osce"), {
            "properties": {"display_units": {"type": "string", "enum": ["SI", "US"]},
                           "visible_observations": {"type": "array", "maxItems": 64}},
            "additionalProperties": False}),
        WorkspaceModule("proforma-workflows", "ward", ("on-call", "handover", "consult", "progression"), {
            "properties": {"focus": {"type": "string", "maxLength": 120}, "section_labels": {"type": "object"}},
            "additionalProperties": False}),
        WorkspaceModule("assessment-engine", "exam", ("question-delivery", "irt", "review-scheduling"), {
            "properties": {"exam_presentation": {"type": "string", "enum": ["focused", "accessible", "compact"]},
                           "section_labels": {"type": "object"}},
            "additionalProperties": False}),
        WorkspaceModule("portfolio-tools", "portfolio", ("profile", "progress", "data-tools", "governance"), {
            "properties": {"focus": {"type": "string", "maxLength": 120}, "section_labels": {"type": "object"}},
            "additionalProperties": False}),
        WorkspaceModule("shared-event-api", "*", ("event-projection", "plugin-config", "explainability")),
    ]
    for module in modules:
        registry.register_module(module)
    skins = [
        WorkspaceSkin("clinic", "Clinic", {"density": "clinical", "canvas": "case", "accent": "blue"},
                      ("case-reasoning", "shared-event-api"), "clinic-case-route"),
        WorkspaceSkin("rounds", "Rounds", {"density": "editorial", "canvas": "reading", "accent": "slate"},
                      ("evidence-teaching", "shared-event-api"), "rounds-teaching-route"),
        WorkspaceSkin("lab", "Lab", {"density": "focused", "canvas": "diagnostic", "accent": "teal"},
                      ("pulse-renderers", "shared-event-api"), "lab-practical-route"),
        WorkspaceSkin("ward", "Ward", {"density": "operational", "canvas": "workflow", "accent": "amber"},
                      ("proforma-workflows", "shared-event-api"), "ward-proforma-route"),
        WorkspaceSkin("exam", "Exam Hall", {"density": "minimal", "canvas": "assessment", "accent": "indigo"},
                      ("assessment-engine", "shared-event-api"), "exam-irt-route"),
        WorkspaceSkin("portfolio", "Portfolio", {"density": "dashboard", "canvas": "portfolio", "accent": "neutral"},
                      ("portfolio-tools", "shared-event-api"), "portfolio-governance-route"),
    ]
    for skin in skins:
        registry.register_skin(skin)
    return registry


REGISTRY = build_default_registry()
