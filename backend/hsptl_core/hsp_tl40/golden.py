"""Golden-corpus and replay-diff helpers for deterministic regression tests."""
from __future__ import annotations

import json
from typing import Any

VOLATILE_KEYS = {"created_at", "occurred_at", "event_id", "event_hash", "previous_hash"}


def stable_projection(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: stable_projection(item) for key, item in sorted(value.items()) if key not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [stable_projection(item) for item in value]
    return value


def replay_diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare stable replay projection trees and report exact JSON paths."""
    a, b = stable_projection(left), stable_projection(right)
    changes: list[dict[str, Any]] = []

    def walk(x: Any, y: Any, path: str) -> None:
        if type(x) is not type(y):
            changes.append({"path": path or "$", "left": x, "right": y})
            return
        if isinstance(x, dict):
            for key in sorted(set(x) | set(y)):
                if key not in x: changes.append({"path": f"{path}.{key}", "left": None, "right": y[key]})
                elif key not in y: changes.append({"path": f"{path}.{key}", "left": x[key], "right": None})
                else: walk(x[key], y[key], f"{path}.{key}")
        elif isinstance(x, list):
            if len(x) != len(y): changes.append({"path": f"{path}.length", "left": len(x), "right": len(y)})
            for index, (item_x, item_y) in enumerate(zip(x, y)):
                walk(item_x, item_y, f"{path}[{index}]")
        elif x != y:
            changes.append({"path": path or "$", "left": x, "right": y})

    walk(a, b, "")
    return {"equal": not changes, "change_count": len(changes), "changes": changes}


def run_replay_diff(kernel) -> dict[str, Any]:
    first = kernel.replay()
    second = kernel.replay()
    diff = replay_diff(first["projection"], second["projection"])
    return {"verified": bool(first.get("verified") and second.get("verified")),
            "projection_hash_first": first.get("projection_hash"),
            "projection_hash_second": second.get("projection_hash"),
            "diff": diff}
