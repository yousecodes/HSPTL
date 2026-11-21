"""Build encounter-linked Clinic narratives and source-traceable Pearls seeds."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime
import hashlib
from typing import Any
from .fhir import coding_list, coding_text, ref_id, resource_provenance, value_display


def _date(value: Any) -> str | None:
    return str(value)[:10] if value else None

def _period_start(resource: dict) -> str | None:
    period = resource.get("period") or {}
    return _date(period.get("start") or resource.get("effectiveDateTime") or resource.get("issued") or resource.get("authoredOn") or resource.get("onsetDateTime") or resource.get("performedDateTime"))

def _patient_case_code(patient_id: str) -> str:
    digest = hashlib.sha256(patient_id.encode("utf-8")).hexdigest()[:8].upper()
    return f"SYN-{digest}"

def _age_at(birth: str | None, at: str | None) -> int | None:
    if not birth or not at:
        return None
    try:
        b = date.fromisoformat(birth[:10]); d = date.fromisoformat(at[:10])
        return d.year - b.year - ((d.month, d.day) < (b.month, b.day))
    except ValueError:
        return None

def _patient_demographics(patient: dict, encounter_date: str | None) -> dict:
    birth = _date(patient.get("birthDate"))
    return {
        "age_at_encounter": _age_at(birth, encounter_date),
        "birth_date": birth,
        "administrative_gender": patient.get("gender"),
        "deceased": patient.get("deceasedBoolean") if "deceasedBoolean" in patient else patient.get("deceasedDateTime"),
    }

def _reason(enc: dict) -> list[dict]:
    result = []
    for item in enc.get("reasonCode") or []:
        result.append({"text": coding_text(item), "coding": coding_list(item)})
    return result

def _observation(resource: dict) -> dict:
    return {
        "display": coding_text(resource.get("code")),
        "coding": coding_list(resource.get("code")),
        "value": value_display(resource),
        "effective": resource.get("effectiveDateTime") or resource.get("effectivePeriod"),
        "status": resource.get("status"),
        "interpretation": [coding_text(x) for x in resource.get("interpretation") or []],
        "reference_range": resource.get("referenceRange") or [],
        "provenance": resource_provenance(resource),
    }

def _condition(resource: dict) -> dict:
    return {
        "display": coding_text(resource.get("code")),
        "coding": coding_list(resource.get("code")),
        "clinical_status": coding_text(resource.get("clinicalStatus")),
        "verification_status": coding_text(resource.get("verificationStatus")),
        "onset": resource.get("onsetDateTime") or resource.get("onsetPeriod"),
        "abatement": resource.get("abatementDateTime") or resource.get("abatementPeriod"),
        "provenance": resource_provenance(resource),
    }

def _medication(resource: dict, by_id: dict | None = None) -> dict:
    med = resource.get("medicationCodeableConcept") or {}
    if not med and resource.get("medicationReference"):
        medication_id = ref_id(resource.get("medicationReference"))
        referenced = (by_id or {}).get(medication_id)
        if referenced:
            med = referenced.get("code") or {}
    return {
        "display": coding_text(med), "coding": coding_list(med),
        "status": resource.get("status"), "intent": resource.get("intent"),
        "authored_on": _date(resource.get("authoredOn")),
        "dosage_instructions": resource.get("dosageInstruction") or [],
        "provenance": resource_provenance(resource),
    }

def _procedure(resource: dict) -> dict:
    return {
        "display": coding_text(resource.get("code")), "coding": coding_list(resource.get("code")),
        "status": resource.get("status"), "performed": resource.get("performedDateTime") or resource.get("performedPeriod"),
        "reason": [coding_text(x) for x in resource.get("reasonCode") or []],
        "provenance": resource_provenance(resource),
    }

def build_outputs(resources: list[dict], source_label: str = "Synthea FHIR") -> dict:
    by_type: dict[str, list[dict]] = defaultdict(list)
    by_id: dict[str, dict] = {}
    for r in resources:
        rt = r.get("resourceType")
        if rt:
            by_type[rt].append(r)
        if r.get("id"):
            by_id[str(r["id"])] = r
    patients = by_type.get("Patient", [])
    if not patients:
        raise ValueError("FHIR import contains no Patient resources")

    # Resources are assigned to an encounter only when an explicit encounter reference exists.
    patient_resources: dict[str, list[dict]] = defaultdict(list)
    for rt in ("Encounter", "Condition", "Observation", "Procedure", "MedicationRequest", "MedicationStatement", "MedicationAdministration", "AllergyIntolerance", "CarePlan", "DiagnosticReport", "Immunization", "ServiceRequest"):
        for r in by_type.get(rt, []):
            pid = ref_id(r.get("subject") or r.get("patient"))
            if pid:
                patient_resources[pid].append(r)

    clinic_cases, pearl_groups = [], {}
    for patient in patients:
        pid = str(patient.get("id") or "")
        if not pid:
            continue
        owned = patient_resources.get(pid, [])
        encounters = [r for r in owned if r.get("resourceType") == "Encounter"]
        encounters.sort(key=lambda r: (_period_start(r) or "", str(r.get("id", ""))))
        if not encounters:
            # Do not promote a patient-level history into a fabricated encounter.
            encounters = [None]
        for index, enc in enumerate(encounters, 1):
            eid = str(enc.get("id")) if enc else None
            enc_date = _period_start(enc) if enc else None
            def linked(r: dict) -> bool:
                return bool(eid and ref_id(r.get("encounter")) == eid)
            observations = [_observation(r) for r in owned if r.get("resourceType") == "Observation" and linked(r)]
            conditions = [_condition(r) for r in owned if r.get("resourceType") == "Condition" and linked(r)]
            # Patient-level history without an encounter reference stays in the history section.
            history_conditions = [_condition(r) for r in owned if r.get("resourceType") == "Condition" and not r.get("encounter")]
            procedures = [_procedure(r) for r in owned if r.get("resourceType") == "Procedure" and linked(r)]
            medication_resources = [r for r in owned if r.get("resourceType") in ("MedicationRequest", "MedicationStatement", "MedicationAdministration")]
            medications = [_medication(r, by_id) for r in medication_resources if linked(r)]
            history_medications = [_medication(r, by_id) for r in medication_resources if not r.get("encounter")]
            allergies = [r for r in owned if r.get("resourceType") == "AllergyIntolerance"]
            allergy_items = [{"display": coding_text(r.get("code")), "clinical_status": coding_text(r.get("clinicalStatus")), "verification_status": coding_text(r.get("verificationStatus")), "provenance": resource_provenance(r)} for r in allergies]
            care_plans = [{"display": coding_text(r.get("title")) or coding_text(r.get("category")), "status": r.get("status"), "intent": r.get("intent"), "period": r.get("period"), "description": [x.get("detail", {}).get("description") for x in r.get("activity", []) if isinstance(x, dict)], "provenance": resource_provenance(r)} for r in owned if r.get("resourceType") == "CarePlan"]
            case_code = _patient_case_code(pid) + (f"-E{index:02d}" if enc else "-HISTORY")
            reasons = _reason(enc) if enc else []
            narrative_lines = []
            demo = _patient_demographics(patient, enc_date)
            age = demo.get("age_at_encounter")
            if age is not None:
                narrative_lines.append(f"A synthetic patient aged {age} years at the recorded encounter")
            elif demo.get("administrative_gender"):
                narrative_lines.append(f"A synthetic patient recorded with administrative gender {demo['administrative_gender']}")
            if enc:
                et = coding_text(enc.get("type")) or coding_text(enc.get("class")) or "Encounter"
                narrative_lines.append(f"had a recorded {et.lower()} on {enc_date or 'an unspecified date'}.")
            else:
                narrative_lines.append("has patient-level records but no linked Encounter resource; this is not presented as a visit.")
            if reasons:
                reason_text = ", ".join(x["text"] for x in reasons if x.get("text"))
                if reason_text:
                    narrative_lines.append(f"Recorded reason(s): {reason_text}.")
            if observations:
                labels = [o["display"] for o in observations if o.get("display")]
                narrative_lines.append(f"The encounter has {len(observations)} linked observation record(s)" + (f", including {', '.join(labels[:5])}." if labels else "."))
            if conditions:
                labels = [c["display"] for c in conditions if c.get("display")]
                narrative_lines.append(f"Linked condition record(s): {', '.join(labels[:8])}." if labels else f"{len(conditions)} linked condition record(s) are present.")
            if procedures:
                labels = [p["display"] for p in procedures if p.get("display")]
                narrative_lines.append(f"Linked procedure record(s): {', '.join(labels[:6])}." if labels else f"{len(procedures)} linked procedure record(s) are present.")
            if not any((reasons, observations, conditions, procedures, medications)):
                narrative_lines.append("No encounter-linked clinical details were available in the imported resources.")
            case = {
                "schema_version": "1.0", "case_code": case_code, "source": source_label,
                "source_kind": "synthetic_fhir", "review_status": "unreviewed",
                "patient_ref": {"resource_type": "Patient", "resource_id": pid},
                "encounter_ref": {"resource_type": "Encounter", "resource_id": eid} if eid else None,
                "specialty": None, "difficulty": None,
                "demographics": demo,
                "encounter": ({"date": enc_date, "status": enc.get("status"), "class": enc.get("class"), "type": coding_list(enc.get("type")), "reason": reasons, "period": enc.get("period"), "provenance": resource_provenance(enc)} if enc else None),
                "clinical_narrative": " ".join(narrative_lines),
                "history": {"conditions": history_conditions, "medications": history_medications, "allergies": allergy_items, "care_plans": care_plans},
                "examination": {"status": "not_documented_in_source", "findings": []},
                "observations": observations, "procedures": procedures,
                "diagnostic_reports": [{"code": coding_text(r.get("code")), "conclusion": r.get("conclusion"), "provenance": resource_provenance(r)} for r in owned if r.get("resourceType") == "DiagnosticReport" and linked(r)],
                "clinical_reasoning": {"diagnosis": None, "differential": [], "management": None, "status": "not_generated_from_raw_records"},
                "provenance": {"patient": resource_provenance(patient), "encounter": resource_provenance(enc) if enc else None, "linked_resource_count": len(observations)+len(conditions)+len(procedures)+len(medications), "patient_history_resource_count": len(history_conditions)+len(history_medications)+len(allergy_items)+len(care_plans)},
                "safety": {"synthetic": True, "educational_only": True, "missing_data_policy": "Missing findings remain explicitly undocumented; no normal values or diagnoses are inferred."}
            }
            clinic_cases.append(case)
            # Pearl entries are deliberately evidence-indexed study seeds, not medical guidance.
            for condition in conditions:
                if condition.get("display"):
                    _add_pearl(pearl_groups, case_code, "condition", condition["display"], condition["coding"], condition["provenance"], enc_date)
            for obs in observations:
                if obs.get("display") and obs.get("value") is not None:
                    _add_pearl(pearl_groups, case_code, "observation", obs["display"], obs["coding"], obs["provenance"], enc_date, obs.get("value"))
    return {"schema_version": "1.0", "source": source_label, "clinic_cases": clinic_cases, "pearl_seeds": list(pearl_groups.values())}

def _add_pearl(groups: dict, case_code: str, kind: str, title: str, coding: list, provenance: dict, date_value: str | None, value: dict | None = None) -> None:
    identity = next((f"{c.get('system','')}|{c.get('code')}" for c in coding if c.get("code")), title.casefold())
    key = (kind, identity)
    if key not in groups:
        groups[key] = {
            "schema_version": "1.0", "title": title, "note_type": "synthetic_record_learning_seed",
            "status": "draft_requires_review", "record_type": kind, "coding": coding,
            "learning_prompt": f"What do these synthetic records document about {title}?",
            "case_codes": [], "sample_count": 0, "recorded_values": [], "source_evidence": [],
            "content": "Record-derived learning seed only. Add reviewed educational explanation and references before treating this as a reusable medical knowledge Pearl.",
            "clinical_guidance": None, "synthetic": True, "requires_human_review": True
        }
    item = groups[key]
    item["sample_count"] += 1
    if case_code not in item["case_codes"]:
        item["case_codes"].append(case_code)
    item["source_evidence"].append({**provenance, "recorded_date": date_value})
    if value is not None and len(item["recorded_values"]) < 20:
        item["recorded_values"].append({"case_code": case_code, "date": date_value, "value": value})
