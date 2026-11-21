"""Phase 4 implementations that are safe to ship disabled.

* branching: deterministic traversal of a clinician-authored graph.
* portability: offline export bundle; import is dry-run only (no sync server).
* tutor: prompt assembly. Performs no network call and generates no content.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .assessment import build_tutor_feedback_prompt
from .policy import BRANCHING_REQUIREMENTS, assert_enabled

BUNDLE_VERSION = 1


class BranchValidationError(ValueError):
    pass


def validate_graph(graph: dict[str, Any]) -> None:
    if not graph.get("reviewer") or not graph.get("review_date"):
        raise BranchValidationError("A branching case requires a named reviewer and review date")
    if graph.get("source_type") != "curated_case":
        raise BranchValidationError("Branching may only run on curated cases, never raw FHIR records")
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    if not nodes or graph.get("start_node") not in nodes:
        raise BranchValidationError("Graph requires nodes and a valid start node")
    for node in nodes.values():
        if not node.get("source_ref"):
            raise BranchValidationError(f"Node {node['id']} has no source reference")
        for option in node.get("options", []):
            if option.get("next") not in nodes:
                raise BranchValidationError(f"Option in {node['id']} points at an unknown node")


def graph_satisfied(graph: dict[str, Any]) -> dict[str, set[str]] | None:
    """Curation metadata is the evidence for the branching requirements.

    Deliberate design choice: an environment flag alone is not enough. The graph
    must also declare a named reviewer, a review date and curated provenance.
    """
    if (graph.get("reviewer") and graph.get("review_date")
            and graph.get("source_type") == "curated_case"):
        return {"branching_simulation": set(BRANCHING_REQUIREMENTS)}
    return None


def _public(node: dict[str, Any]) -> dict[str, Any]:
    return {"id": node["id"], "prompt": node.get("prompt", ""),
            "options": [{"id": o["id"], "label": o["label"]} for o in node.get("options", [])],
            "source_ref": node.get("source_ref"), "terminal": bool(node.get("terminal", False))}


def branch_start(graph: dict[str, Any], satisfied=None) -> dict[str, Any]:
    assert_enabled("branching_simulation", satisfied)
    validate_graph(graph)
    node = next(n for n in graph["nodes"] if n["id"] == graph["start_node"])
    return {"node": _public(node), "path": [node["id"]], "finished": bool(node.get("terminal"))}


def branch_choose(graph: dict[str, Any], state: dict[str, Any], option_id: str,
                  satisfied=None) -> dict[str, Any]:
    assert_enabled("branching_simulation", satisfied)
    validate_graph(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if not state.get("path") or state["path"][-1] not in nodes:
        raise BranchValidationError("The supplied path does not match this graph")
    current = nodes[state["path"][-1]]
    option = next((o for o in current.get("options", []) if o["id"] == option_id), None)
    if option is None:
        raise BranchValidationError("Unknown option for this node")
    node = nodes[option["next"]]
    return {"node": _public(node), "path": [*state["path"], node["id"]],
            "feedback": option.get("feedback", ""),
            "feedback_source": current.get("source_ref"),
            "finished": bool(node.get("terminal"))}


def _checksum(payload: dict[str, Any]) -> str:
    unsigned = {k: v for k, v in payload.items() if k != "checksum"}
    return hashlib.sha256(json.dumps(unsigned, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def export_bundle(store, episodes, exams) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "local_learning_portfolio",
        "contains": "Learner-authored content and source metadata. No credentials, no telemetry.",
        "episodes": episodes.list(limit=200)["items"],
        "notes": store.notes(limit=500),
        "cards": store.cards(include_suspended=True, limit=500),
        "exams": exams.exams(),
    }
    payload["artifacts"] = {e["episode_id"]: episodes.artifacts(e["episode_id"])
                            for e in payload["episodes"]}
    payload["sources"] = {
        e["episode_id"]: {a["artifact_id"]: episodes.sources_for("artifact", a["artifact_id"])
                          for a in payload["artifacts"][e["episode_id"]]}
        for e in payload["episodes"]}
    payload["checksum"] = _checksum(payload)
    return payload


def import_dry_run(bundle: dict[str, Any]) -> dict[str, Any]:
    """Never writes. Write-merge needs an explicit conflict-resolution policy."""
    problems = []
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        problems.append("Unsupported bundle version")
    if bundle.get("checksum") != _checksum(bundle):
        problems.append("Checksum mismatch; the bundle was modified after export")
    return {"valid": not problems, "problems": problems,
            "would_import": {"episodes": len(bundle.get("episodes", [])),
                             "notes": len(bundle.get("notes", [])),
                             "cards": len(bundle.get("cards", []))},
            "note": "Write-merge is intentionally unimplemented until conflict resolution "
                    "and identity mapping are specified (policy: multi_user_sync)."}


class PromptOnlyTutor:
    mode = "prompt_only"
    network_enabled = False

    def prepare(self, *, case_context: str, stage_name: str, questions: list[str],
                answer: str, ratings: dict[str, int], evidence: dict[str, str]) -> dict[str, Any]:
        return {"mode": self.mode,
                "prompt": build_tutor_feedback_prompt(
                    case_context=case_context, stage_name=stage_name, questions=questions,
                    answer=answer, ratings=ratings, evidence=evidence),
                "notice": "Copy this prompt into a tool you have chosen. HSPTL made no network "
                          "request and generated no clinical content. Any output requires human "
                          "verification."}


def get_tutor(satisfied=None) -> PromptOnlyTutor:
    assert_enabled("conversational_tutoring", satisfied)
    return PromptOnlyTutor()
