"""Fact-bounded generated educational case reports from Synthea records.

The report renderer intentionally does not invent symptoms, examinations,
interpretations, interventions or outcomes absent from the source extract.
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from .data import clean, row_date, resource_label

REPORT_RESOURCES = (
    "Encounter", "Condition", "Observation", "DiagnosticReport",
    "Procedure", "MedicationRequest", "AllergyIntolerance",
)


def condition_names(case: dict[str, Any], limit: int = 8) -> list[str]:
    frame = case.get("episode", {}).get("Condition", pd.DataFrame())
    if frame is None or frame.empty:
        return []
    names: list[str] = []
    for _, row in frame.iterrows():
        name = ""
        for col in ("code.text", "code.coding.display", "code.coding[0].display"):
            name = clean(row.get(col), 180)
            if name:
                break
        if name and name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _timeline(case: dict[str, Any], limit: int = 24) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for resource in REPORT_RESOURCES:
        frame = case.get("episode", {}).get(resource, pd.DataFrame())
        if frame is None or frame.empty:
            continue
        for _, row in frame.iterrows():
            stamp = row_date(row, resource)
            if pd.isna(stamp):
                continue
            description = resource_label(row, resource, limit=190)
            if description and description != "Record present; readable fields unavailable in this export":
                events.append({
                    "date": stamp.strftime("%Y-%m-%d"),
                    "resource": resource,
                    "description": description,
                    "sort": stamp,
                })
    events.sort(key=lambda event: event["sort"])
    for event in events:
        event.pop("sort", None)
    return events[-limit:]


def build_case_report(
    case: dict[str, Any],
    *,
    format_date: Callable[[Any], str] | None = None,
) -> dict[str, Any]:
    """Create a concise structured report using the selected case's own records."""
    format_date = format_date or (lambda value: str(value) if value is not None else "Not available")
    conditions = condition_names(case)
    age = case.get("age")
    age_label = f"{age}-year-old" if age is not None else "patient of unrecorded age"
    sex = clean(case.get("sex"), 40).lower()
    sex_label = sex if sex else "sex not recorded"
    if conditions:
        problem = ", ".join(conditions[:2])
        title = f"Synthetic case: {age_label} {sex_label} with recorded {problem}"
    else:
        title = f"Synthetic longitudinal case: {age_label} {sex_label}"

    counts = {}
    summaries: dict[str, list[str]] = {}
    for resource in REPORT_RESOURCES:
        frame = case.get("episode", {}).get(resource, pd.DataFrame())
        counts[resource] = len(frame) if frame is not None else 0
        items = []
        if frame is not None and not frame.empty:
            dated = frame.copy()
            dated["_report_date"] = dated.apply(lambda row: row_date(row, resource), axis=1)
            dated = dated.sort_values("_report_date", ascending=True, na_position="last")
            for _, row in dated.tail(10).iterrows():
                label = resource_label(row, resource, limit=220)
                stamp = row.get("_report_date")
                stamp_text = stamp.strftime("%d %b %Y") if not pd.isna(stamp) else "Date not available"
                if label and label != "Record present; readable fields unavailable in this export":
                    items.append(f"{stamp_text} · {label}")
        summaries[resource] = items

    anchor = case.get("anchor")
    latest_encounter = case.get("latest_encounter")
    encounter_status = clean(latest_encounter.get("status")) if isinstance(latest_encounter, dict) else ""
    # latest_encounter is a pandas Series in DatasetCatalog.case; handle either shape.
    if latest_encounter is not None and not isinstance(latest_encounter, dict):
        try:
            encounter_status = clean(latest_encounter.get("status"))
        except AttributeError:
            encounter_status = ""

    demographics = {
        "age": age_label,
        "sex": sex_label,
        "date_of_birth": clean(case.get("dob")) or "Not recorded",
        "latest_encounter": format_date(anchor),
        "source_cohort": clean(case.get("source")) or "Unknown cohort",
        "recorded_conditions": conditions,
        "encounter_status": encounter_status or "Not available",
    }
    limitations = [
        "This report is generated from a synthetic Synthea record, not a real patient or published case report.",
        "The report includes only fields linked and available in the selected data extract.",
        "Missing information is not a negative finding; a missing value must not be interpreted as normal.",
        "A coded condition is a source-recorded entry, not independent proof of a clinical diagnosis.",
        "Historical medication requests do not establish current medication use.",
        "No treatment response, recovery or outcome is inferred when it is not explicitly documented.",
    ]
    return {
        "title": title,
        "abstract": (
            f"This machine-generated educational report summarises a synthetic {age_label} {sex_label}. "
            f"The episode extract contains {counts['Encounter']} encounter records, "
            f"{counts['Condition']} condition records, {counts['Observation']} observations, "
            f"{counts['Procedure']} procedures and {counts['MedicationRequest']} medication requests. "
            "The available records are summarised without inferring unrecorded clinical findings."
        ),
        "demographics": demographics,
        "case_presentation": (
            "The available source extract does not necessarily contain a presenting complaint or a complete history. "
            "The documented record elements are listed below; no additional symptoms or examination findings have been created."
        ),
        "summaries": summaries,
        "timeline": _timeline(case),
        "counts": counts,
        "limitations": limitations,
        "discussion_questions": [
            "Which clinical facts are directly documented, and which are still unknown?",
            "What focused history and examination would be needed before interpreting the coded condition?",
            "Which available observation or investigation could change your differential, and what is missing?",
            "What dangerous alternative diagnosis should be considered for this presentation, and what feature would trigger escalation?",
        ],
        "source_label": f"{clean(case.get('source')) or 'Synthea'} · synthetic EHR extract",
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """Render an exportable report while keeping its synthetic provenance explicit."""
    lines = [
        f"# {report['title']}",
        "",
        f"> {report['source_label']}. Educational synthetic report; not a published case report.",
        "",
        "## Abstract",
        report["abstract"],
        "",
        "## Patient information",
    ]
    for key, value in report["demographics"].items():
        if key == "recorded_conditions":
            value = ", ".join(value) if value else "No linked condition entries in episode extract"
        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    lines += ["", "## Case presentation", report["case_presentation"], ""]
    heading_map = {
        "Encounter": "Encounter records",
        "Condition": "Recorded conditions",
        "Observation": "Observations and investigation values",
        "DiagnosticReport": "Diagnostic reports",
        "Procedure": "Procedures",
        "MedicationRequest": "Medication requests",
        "AllergyIntolerance": "Allergy records",
    }
    for resource, heading in heading_map.items():
        lines += [f"## {heading}"]
        items = report["summaries"].get(resource, [])
        lines.extend([f"- {item}" for item in items] or ["- No readable linked entries in this episode extract."])
        lines.append("")
    lines += ["## Timeline"]
    lines.extend([
        f"- {item['date']} · **{item['resource']}** · {item['description']}"
        for item in report["timeline"]
    ] or ["- No dated events were available for the timeline."])
    lines += ["", "## Discussion questions"]
    lines.extend([f"{i}. {question}" for i, question in enumerate(report["discussion_questions"], 1)])
    lines += ["", "## Limitations and provenance"]
    lines.extend([f"- {item}" for item in report["limitations"]])
    return "\n".join(lines).strip() + "\n"
