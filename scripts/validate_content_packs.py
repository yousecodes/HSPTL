#!/usr/bin/env python3
"""Validate every installed HSPTL content pack and all derived formats."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.hsptl_core.content_factory import ContentFactory  # noqa: E402
from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402

OUTPUTS = ("case_report", "case_debrief", "question_set", "topic_summary", "viva_set", "osce_station")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> int:
    pack_dir = ROOT / "backend" / "content_packs"
    paths = sorted(pack_dir.glob("*_v*.json"))
    schema_path = pack_dir / "content_pack.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if not paths:
        print("ERROR: no versioned content packs found")
        return 1
    units_total = outputs_total = questions_total = 0
    for path in paths:
        try:
            pack_data = json.loads(path.read_text(encoding="utf-8"))
            errors = sorted(schema_validator.iter_errors(pack_data), key=lambda error: list(error.absolute_path))
            if errors:
                first = errors[0]
                location = "/".join(str(part) for part in first.absolute_path) or "<root>"
                raise ValueError(f"schema {location}: {first.message}")
            factory = ContentFactory(path)
            catalog = factory.catalog()
            for unit in catalog["units"]:
                units_total += 1
                questions_total += unit["quiz_count"]
                for kind in OUTPUTS:
                    first = factory.build(unit["unit_id"], kind, seed=2026)
                    second = factory.build(unit["unit_id"], kind, seed=2026)
                    if first["body"].get("validation", {}).get("valid") is not True:
                        raise ValueError(f"{unit['unit_id']} / {kind}: invalid output")
                    if digest(first) != digest(second):
                        raise ValueError(f"{unit['unit_id']} / {kind}: output is not deterministic")
                    if kind == "question_set":
                        for item in first["body"].get("assessment_items", []):
                            if item["answer"] not in item["options"]:
                                raise ValueError(f"{unit['unit_id']}: seeded MCQ answer was lost")
                    outputs_total += 1
            print(f"PASS {path.name}: {catalog['unit_count']} units, {catalog['question_count']} questions, {catalog['unit_count'] * len(OUTPUTS)} deterministic output recipes")
        except Exception as exc:  # CLI should provide one actionable failure line per pack.
            print(f"FAIL {path.name}: {exc}")
            return 1
    print(f"VALIDATED {len(paths)} pack(s), {units_total} unit(s), {questions_total} retrieval question(s), {outputs_total} derived output(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
