"""Extracted specialty filters services for the Clinical Knowledge Harvester."""
from __future__ import annotations
from .catalogue import EXCLUDE_KEYWORDS, GLOBAL_EXCLUDES, SPECIALTIES, _OPHTH_SPEC, _OPHTH_VERY




def _has_very_specific(text):
    return any(p.search(text) for p in _OPHTH_VERY)

def _count_specific(text):
    return sum(1 for p in _OPHTH_SPEC if p.search(text))

def _positive_ophthalmology(title, abstract):
    title = title or ""
    abstract = abstract or ""
    if _has_very_specific(title) or _has_very_specific(abstract):
        return True
    if _count_specific(title) == 0:
        return False
    return (_count_specific(title) + _count_specific(abstract)) >= 2

def is_valid_specialty_case(title, key, abstract="", source=""):
    blob = ((title or "") + " " + (abstract or "")).lower()
    if any(ex in blob for ex in GLOBAL_EXCLUDES):
        return False
    if any(ex in blob for ex in EXCLUDE_KEYWORDS.get(key, [])):
        return False
    if source.startswith("exam:"):
        return True
    if key == "ophthalmology" and not _positive_ophthalmology(title, abstract):
        return False
    return True

def _title_matches_specialty(title, abstract, key):
    blob = ((title or "") + " " + (abstract or "")).lower()
    if not blob.strip():
        return False
    for kw in SPECIALTIES[key][2]:
        base = (kw[:-1] if kw.endswith("*") else kw).lower()
        if base in blob:
            return True
    return False

