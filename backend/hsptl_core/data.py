"""Synthea CSV/FHIR data ingestion, indexing and case assembly.

The loader never writes to or modifies source datasets. Every patient key is
namespaced by source folder to avoid collisions when cohorts are combined.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .config import (
    CLINICAL_RESOURCES, DATE_COLUMNS, DISPLAY_COLUMNS, LINK_COLUMNS,
    RESOURCE_NAMES,
)


def clean(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.casefold() in {"nan", "none", "nat", "null", "<na>"}:
        return ""
    return text[:limit]


def normalise_reference(value: Any) -> str | None:
    text = clean(value, 1000)
    if not text:
        return None
    text = text.split("|")[0].split("#")[0].rstrip("/")
    if "/_history/" in text:
        text = text.split("/_history/", 1)[0]
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text or None


def parse_date(value: Any):
    text = clean(value, 120)
    if not text:
        return pd.NaT
    return pd.to_datetime(text, errors="coerce", utc=True)


def patient_name(row: pd.Series | dict[str, Any]) -> str:
    raw = row.get("name", "")
    parsed: Any = raw
    if isinstance(raw, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw)
                break
            except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
                continue
    if isinstance(parsed, dict):
        parsed = [parsed]
    if isinstance(parsed, list) and parsed:
        item = parsed[0]
        if isinstance(item, dict):
            given = item.get("given", [])
            if isinstance(given, str):
                given = [given]
            family = item.get("family", "")
            name = " ".join([str(x) for x in given if x] + ([str(family)] if family else []))
            if name.strip():
                return name.strip()
    return clean(row.get("name"), 100) or "Unnamed synthetic patient"


def row_date(row: pd.Series, resource: str):
    for column in DATE_COLUMNS.get(resource, []):
        if column in row.index:
            value = parse_date(row.get(column))
            if not pd.isna(value):
                return value
    return pd.NaT


def resource_label(row: pd.Series, resource: str, limit: int = 240) -> str:
    values: list[str] = []
    for column in DISPLAY_COLUMNS.get(resource, []):
        if column in row.index:
            value = clean(row.get(column), 150)
            if value and value not in values:
                values.append(value)
        if len(values) >= 4:
            break
    if resource == "Observation":
        raw_value = clean(row.get("valueQuantity.value"))
        unit = clean(row.get("valueQuantity.unit"))
        if raw_value:
            values.append(" ".join(x for x in (raw_value, unit) if x))
    return " · ".join(values)[:limit] if values else "Record present; readable fields unavailable in this export"


def _read_resource_csv(folder: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    name_map = {name.casefold(): name for name in RESOURCE_NAMES}
    name_map["patients"] = "Patient"
    resources: dict[str, pd.DataFrame] = {}
    patients: pd.DataFrame | None = None
    for file in sorted(folder.glob("*.csv")):
        resource = name_map.get(file.stem.casefold())
        if resource is None:
            continue
        try:
            frame = pd.read_csv(file, low_memory=False, dtype={"id": "string"})
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise ValueError(f"Could not read {file.name}: {exc}") from exc
        if resource == "Patient":
            patients = frame
        else:
            resources[resource] = frame
    if patients is None or patients.empty:
        raise FileNotFoundError(f"No usable Patient.csv found in {folder}")
    if "id" not in patients.columns:
        raise ValueError(f"Patient.csv in {folder} has no 'id' column")
    return patients, resources


def _read_fhir_json(folder: Path) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Read standard Synthea FHIR JSON resources or transaction bundles."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    files = list(folder.rglob("*.json"))
    if not files:
        raise FileNotFoundError(f"No Patient.csv or FHIR JSON files found in {folder}")

    def append_resource(resource: Any) -> None:
        if not isinstance(resource, dict):
            return
        kind = resource.get("resourceType")
        if kind not in RESOURCE_NAMES:
            return
        grouped.setdefault(kind, []).append(pd.json_normalize(resource, sep=".").iloc[0].to_dict())

    for file in files:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("resourceType") == "Bundle":
            for entry in payload.get("entry", []):
                append_resource(entry.get("resource") if isinstance(entry, dict) else None)
        else:
            append_resource(payload)
    if not grouped.get("Patient"):
        raise FileNotFoundError(f"No Patient resources found in FHIR JSON folder {folder}")
    patients = pd.DataFrame(grouped.pop("Patient"))
    resources = {name: pd.DataFrame(rows) for name, rows in grouped.items()}
    return patients, resources


@dataclass
class Cohort:
    name: str
    path: Path
    patients: pd.DataFrame
    resources: dict[str, pd.DataFrame]
    keys: list[str] = field(default_factory=list)


@dataclass
class DatasetCatalog:
    cohorts: list[Cohort]
    patients: dict[str, dict[str, Any]]
    by_patient: dict[str, dict[str, pd.DataFrame]]
    resource_tables: dict[str, pd.DataFrame]
    warnings: list[str] = field(default_factory=list)

    @property
    def patient_keys(self) -> list[str]:
        return list(self.patients.keys())

    @property
    def source_names(self) -> list[str]:
        return [cohort.name for cohort in self.cohorts]

    def patient_label(self, key: str) -> str:
        patient = self.patients[key]
        return f"{patient['name']} · {patient['source']} · {patient['id'][:8]}"

    def records_for(self, patient_key: str, resource: str) -> pd.DataFrame:
        frame = self.by_patient.get(patient_key, {}).get(resource)
        return frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame()

    def case(self, patient_key: str, lookback_days: int = 30, lookforward_days: int = 7) -> dict[str, Any]:
        if patient_key not in self.patients:
            raise KeyError("Selected patient is not present in the loaded data sources")
        patient = self.patients[patient_key]
        all_records = {r: self.records_for(patient_key, r) for r in CLINICAL_RESOURCES}
        encounters = all_records.get("Encounter", pd.DataFrame())
        latest = None
        anchor = pd.NaT
        if not encounters.empty:
            dated = encounters.copy()
            dated["_wardx_date"] = dated.apply(lambda row: row_date(row, "Encounter"), axis=1)
            dated = dated[dated["_wardx_date"].notna()]
            if not dated.empty:
                latest = dated.sort_values("_wardx_date").iloc[-1].drop(labels=["_wardx_date"], errors="ignore")
                anchor = row_date(latest, "Encounter")
        if pd.isna(anchor):
            all_dates = []
            for resource, frame in all_records.items():
                if not frame.empty:
                    dates = frame.apply(lambda row: row_date(row, resource), axis=1)
                    all_dates.extend([x for x in dates if not pd.isna(x)])
            if all_dates:
                anchor = max(all_dates)
        episode: dict[str, pd.DataFrame] = {}
        episode_notes: dict[str, str] = {}
        for resource, frame in all_records.items():
            if frame.empty:
                episode[resource], episode_notes[resource] = frame, ""
            elif resource == "AllergyIntolerance":
                episode[resource] = frame
                episode_notes[resource] = "All linked allergy records; not restricted to the episode window."
            elif pd.isna(anchor):
                episode[resource] = frame
                episode_notes[resource] = "No dated encounter anchor; showing all linked records."
            else:
                dates = frame.apply(lambda row: row_date(row, resource), axis=1)
                usable = dates.notna()
                if not usable.any():
                    episode[resource] = frame
                    episode_notes[resource] = "Dates unavailable; showing all linked records."
                else:
                    mask = usable & dates.between(anchor - pd.Timedelta(days=lookback_days), anchor + pd.Timedelta(days=lookforward_days))
                    episode[resource] = frame.loc[mask].copy()
                    episode_notes[resource] = "" if mask.any() else "No records fell within the episode window."
        age = None
        dob = parse_date(patient.get("birthDate"))
        if not pd.isna(dob) and not pd.isna(anchor):
            age = int(anchor.year - dob.year - ((anchor.month, anchor.day) < (dob.month, dob.day)))
        return {
            "key": patient_key, "id": patient["id"], "source": patient["source"],
            "name": patient["name"], "sex": clean(patient.get("gender")) or "Not recorded",
            "dob": clean(patient.get("birthDate")), "age": age,
            "anchor": anchor, "latest_encounter": latest,
            "all": all_records, "episode": episode, "episode_notes": episode_notes,
        }

    def richness(self, patient_key: str) -> dict[str, Any]:
        counts = {r: len(self.by_patient.get(patient_key, {}).get(r, [])) for r in CLINICAL_RESOURCES}
        domains = sum(count > 0 for count in counts.values())
        # Data-density heuristic only. It is not disease severity or case quality.
        score = (
            min(counts.get("Encounter", 0), 8) * 2.5
            + min(counts.get("Condition", 0), 8) * 2.5
            + min(counts.get("Observation", 0), 25) * 0.8
            + min(counts.get("MedicationRequest", 0), 5) * 1.5
            + min(counts.get("Procedure", 0), 6) * 1.5
            + min(counts.get("DiagnosticReport", 0), 5) * 1.5
            + min(counts.get("AllergyIntolerance", 0), 2)
            + domains * 3
        )
        return {"score": round(min(score, 100), 1), "domains": domains, **counts}


def load_catalog(source_dirs: list[Path]) -> DatasetCatalog:
    cohorts: list[Cohort] = []
    patients: dict[str, dict[str, Any]] = {}
    by_patient: dict[str, dict[str, pd.DataFrame]] = {}
    resource_tables: dict[str, list[pd.DataFrame]] = {r: [] for r in CLINICAL_RESOURCES}
    warnings: list[str] = []

    for folder in source_dirs:
        folder = Path(folder).expanduser().resolve()
        if not folder.is_dir():
            warnings.append(f"Skipped missing data folder: {folder}")
            continue
        try:
            if list(folder.glob("*.csv")):
                patient_df, resources = _read_resource_csv(folder)
                input_type = "CSV"
            else:
                patient_df, resources = _read_fhir_json(folder)
                input_type = "FHIR JSON"
        except (OSError, ValueError, FileNotFoundError) as exc:
            warnings.append(str(exc))
            continue
        source_name = (folder.parent.name if folder.name.casefold() in {"analysis_csv", "csv", "fhir", "output"} else folder.name) or "Synthea cohort"
        if any(c.name.casefold() == source_name.casefold() for c in cohorts):
            source_name = f"{source_name} ({len(cohorts) + 1})"
        cohort = Cohort(source_name, folder, patient_df, resources)
        id_to_key: dict[str, str] = {}
        for _, row in patient_df.iterrows():
            pid = clean(row.get("id"))
            if not pid:
                continue
            key = f"{source_name}::{pid}"
            id_to_key[pid] = key
            patient_record = row.to_dict()
            patient_record.update({"id": pid, "key": key, "source": source_name, "name": patient_name(row)})
            patients[key] = patient_record
            by_patient[key] = {}
            cohort.keys.append(key)
        for resource in CLINICAL_RESOURCES:
            frame = resources.get(resource)
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            link_col = LINK_COLUMNS.get(resource)
            if not link_col or link_col not in frame.columns:
                # Allergy exports can vary; use patient.reference only for that resource.
                warnings.append(f"{source_name}: {resource} has no recognised patient link column ({link_col}).")
                continue
            temp = frame.copy()
            temp["_wardx_patient_id"] = temp[link_col].map(normalise_reference)
            temp["_wardx_patient_key"] = temp["_wardx_patient_id"].map(id_to_key)
            temp = temp[temp["_wardx_patient_key"].notna()].copy()
            if temp.empty:
                continue
            resource_tables[resource].append(temp)
            for key, group in temp.groupby("_wardx_patient_key", sort=False):
                by_patient[str(key)][resource] = group.drop(columns=["_wardx_patient_id", "_wardx_patient_key"], errors="ignore").copy()
        cohorts.append(cohort)
        warnings.append(f"Loaded {len(cohort.keys)} patients from {folder} ({input_type}).")

    combined_tables: dict[str, pd.DataFrame] = {}
    for resource, frames in resource_tables.items():
        if frames:
            combined_tables[resource] = pd.concat(frames, ignore_index=True, sort=False)
        else:
            combined_tables[resource] = pd.DataFrame()
    if not patients:
        raise FileNotFoundError("No usable Synthea cohort found. Configure a folder containing Patient.csv or FHIR JSON Patient resources.")
    return DatasetCatalog(cohorts, patients, by_patient, combined_tables, warnings)


def patient_summaries(case: dict[str, Any], resource: str, episode: bool = True, limit: int = 12) -> list[str]:
    frame = case["episode" if episode else "all"].get(resource, pd.DataFrame()).copy()
    if frame.empty:
        return []
    frame["_wardx_date"] = frame.apply(lambda row: row_date(row, resource), axis=1)
    frame = frame.sort_values("_wardx_date", ascending=False, na_position="last")
    output: list[str] = []
    for _, row in frame.head(limit).iterrows():
        stamp = row["_wardx_date"]
        date_text = stamp.strftime("%d %b %Y") if not pd.isna(stamp) else "Date unavailable"
        output.append(f"{date_text} · {resource_label(row, resource)}")
    return output


def measurements_for_case(case: dict[str, Any]) -> pd.DataFrame:
    frame = case["all"].get("Observation", pd.DataFrame())
    columns = ["date", "name", "value", "unit", "raw"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        name = ""
        for col in ["code.text", "code.coding.display", "code.coding", "code"]:
            name = clean(row.get(col), 180) if col in row.index else ""
            if name:
                break
        raw = ""
        for col in ["valueQuantity.value", "valueInteger", "valueDecimal", "valueString", "valueCodeableConcept.text"]:
            raw = clean(row.get(col), 100) if col in row.index else ""
            if raw:
                break
        numeric = pd.to_numeric(raw, errors="coerce")
        stamp = row_date(row, "Observation")
        unit = clean(row.get("valueQuantity.unit")) or clean(row.get("valueQuantity.code"))
        if name and not pd.isna(stamp):
            rows.append({"date": stamp, "name": name, "value": None if pd.isna(numeric) else float(numeric), "unit": unit, "raw": raw})
    return pd.DataFrame(rows, columns=columns)
