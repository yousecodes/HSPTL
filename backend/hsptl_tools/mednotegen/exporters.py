from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def export_json(payload: dict, output: str | Path) -> Path:
    path = Path(output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path

def export_markdown(payload: dict, output_dir: str | Path) -> list[Path]:
    root = Path(output_dir); root.mkdir(parents=True, exist_ok=True); paths=[]
    for case in payload.get("clinic_cases", []):
        lines = [f"# {case['case_code']}", "", "> Synthetic educational case — not a real patient record or clinical advice.", "", case.get("clinical_narrative", ""), "", "## Recorded encounter", f"- Date: {case.get('encounter', {}).get('date') if case.get('encounter') else 'No linked encounter'}", "", "## Observations"]
        obs = case.get("observations", [])
        if not obs: lines.append("- No encounter-linked observations documented in this source.")
        for item in obs:
            val=item.get("value") or {}; lines.append(f"- {item.get('display') or 'Unnamed observation'}: {val.get('value', 'Value not recorded')} {val.get('unit') or ''} ({item.get('provenance',{}).get('resource_id')})")
        lines += ["", "## Examination", "Not documented in the imported source." if case.get("examination",{}).get("status")=="not_documented_in_source" else ""]
        path=root/f"{case['case_code']}.md"; path.write_text("\n".join(lines)+"\n",encoding="utf-8"); paths.append(path)
    for pearl in payload.get("pearl_seeds", []):
        evidence = pearl.get("source_evidence") or []
        lines=[f"# {pearl['title']}", "", "> Draft learning seed from synthetic Synthea data. Human review required.", "", pearl["learning_prompt"], "", pearl["content"], "", "## Source evidence"]
        if evidence:
            for item in evidence:
                lines.append(f"- {item.get('resource_type', 'Resource')}/{item.get('resource_id', 'unknown')} — {item.get('source_file', 'source file not recorded')} — {item.get('recorded_date') or 'date not recorded'}")
        else:
            lines.append("- No source evidence was recorded in this seed.")
        path=root/f"PEARL-{len(paths)+1:04d}.md"; path.write_text("\n".join(lines)+"\n",encoding="utf-8"); paths.append(path)
    return paths
