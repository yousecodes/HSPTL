"""Extracted query builder services for the Clinical Knowledge Harvester."""
from __future__ import annotations
from .catalogue import SPECIALTIES
from . import engine as _engine

BASE = getattr(_engine, 'BASE')
_PMC_BROAD = getattr(_engine, '_PMC_BROAD')
_PMC_DEFAULT_YEARS = getattr(_engine, '_PMC_DEFAULT_YEARS')
time = getattr(_engine, 'time')



def _keyword_terms(key):
    return [kw[:-1] if kw.endswith("*") else kw for kw in SPECIALTIES[key][2]]

def specialty_clause(key):
    _, meshes, kws = SPECIALTIES[key]
    parts = ["MESH:\"" + m + "\"" for m in meshes]
    parts += ["TITLE:\"" + k + "\"" if " " in k else "TITLE:" + k for k in kws]
    return "(" + " OR ".join(parts) + ")"

PROFILE_PUBLICATION_TYPES = {
    "case_reports": ['Case Reports'],
    "guidelines": ['Guideline', 'Practice Guideline'],
    "systematic_reviews": ['Systematic Review', 'Meta-Analysis'],
    "trials": ['Clinical Trial', 'Randomized Controlled Trial'],
    "observational": ['Observational Study', 'Cohort Study', 'Case-Control Study', 'Diagnostic Test Accuracy Study'],
}


def query_for(key, yf, yt, profile="case_reports"):
    """Build a specialty-scoped, full-text open-access Europe PMC query."""
    profile = profile if profile in {*PROFILE_PUBLICATION_TYPES, "clinical_evidence", "all_open_access"} else "case_reports"
    if profile == "case_reports":
        evidence_clause = 'PUB_TYPE:"Case Reports"'
    else:
        types = (sum(PROFILE_PUBLICATION_TYPES.values(), []) if profile in {"clinical_evidence", "all_open_access"}
                 else PROFILE_PUBLICATION_TYPES[profile])
        evidence_clause = "(" + " OR ".join('PUB_TYPE:"' + value + '"' for value in types) + ")"
    q = specialty_clause(key) + " AND " + evidence_clause + " AND OPEN_ACCESS:y AND HAS_FT:y"
    if yf or yt:
        q += " AND (PUB_YEAR:[" + str(yf or 1900) + " TO " + str(yt or 2100) + "])"
    return q

def publication_types_for_profile(profile="case_reports"):
    profile = profile if profile in {*PROFILE_PUBLICATION_TYPES, "clinical_evidence", "all_open_access"} else "case_reports"
    if profile in {"clinical_evidence", "all_open_access"}:
        return sorted({item for values in PROFILE_PUBLICATION_TYPES.values() for item in values})
    return list(PROFILE_PUBLICATION_TYPES[profile])

def pubmed_query_for(key, yf=None, yt=None, profile="case_reports"):
    terms = ["\"" + m + "\"[MeSH Terms]" for m in SPECIALTIES[key][1]]
    for kw in SPECIALTIES[key][2]:
        if kw.endswith("*"):
            terms.append(kw[:-1] + "[Title/Abstract]")
        else:
            terms.append("\"" + kw + "\"[Title/Abstract]")
    evidence = publication_types_for_profile(profile)
    pub_clause = " OR ".join('"' + value + '"[Publication Type]' for value in evidence)
    parts = ["(" + " OR ".join(terms) + ")", "(" + pub_clause + ")"]
    parts.append("free full text[sb]")
    if yf or yt:
        parts.append("(" + str(yf or 1900) + ":" + str(yt or 2100) + "[dp])")
    return " AND ".join(parts)

def pmc_query_for(key, yf, yt, profile="case_reports"):
    _, meshes, kws = SPECIALTIES[key]
    if not _PMC_BROAD:
        if not (yf or yt):
            this_year = time.localtime().tm_year
            yf = this_year - (_PMC_DEFAULT_YEARS - 1)
            yt = this_year
        if key == "ophthalmology":
            meshes = [m for m in meshes if m != "Eye Diseases"]
            meshes += ["Eyelid Diseases", "Orbital Diseases",
                       "Lacrimal Apparatus Diseases", "Conjunctival Diseases", "Lens Diseases"]
            kws = [kw for kw in kws if kw not in ("eye", "ocular")]
    parts = ["\"" + m + "\"[MeSH Terms]" for m in meshes]
    for kw in kws:
        base = kw[:-1] if kw.endswith("*") else kw
        parts.append("\"" + base + "\"[Title]" if " " in base else base + "[Title]")
    pub_clause = " OR ".join('"' + value + '"[Publication Type]' for value in publication_types_for_profile(profile))
    q = "(" + " OR ".join(parts) + ") AND (" + pub_clause + ") AND open access[filter]"
    if yf or yt:
        q += " AND (" + str(yf or 1900) + ":" + str(yt or 2100) + "[dp])"
    return q

def doaj_query_for(key, yf, yt, profile="case_reports"):
    terms = ["\"" + t + "\"" if " " in t else t for t in _keyword_terms(key)]
    profile_terms = {
        "case_reports": ["case report", "case series"],
        "guidelines": ["guideline", "practice guideline", "consensus statement"],
        "systematic_reviews": ["systematic review", "meta-analysis"],
        "trials": ["clinical trial", "randomized trial", "randomised trial"],
        "observational": ["cohort study", "case-control", "observational study", "diagnostic accuracy"],
    }
    selected = profile_terms.get(profile, sum(profile_terms.values(), []))
    evidence = " OR ".join('bibjson.title:"' + t + '" OR bibjson.abstract:"' + t + '"' for t in selected)
    specialty_terms = " OR ".join(terms)
    q = "(bibjson.title:(" + specialty_terms + ") OR bibjson.abstract:(" + specialty_terms + ")) AND (" + evidence + ")"
    if yf or yt:
        q += " AND bibjson.year:[" + str(yf or 1900) + " TO " + str(yt or 2100) + "]"
    return q

def crossref_query_for(key, profile="case_reports"):
    terms = {
        "case_reports": "case report",
        "guidelines": "clinical practice guideline OR consensus statement",
        "systematic_reviews": "systematic review OR meta-analysis",
        "trials": "clinical trial OR randomized trial",
        "observational": "observational study OR cohort study OR diagnostic accuracy",
    }
    suffix = terms.get(profile, "clinical guideline OR systematic review OR clinical trial OR observational study OR case report")
    return " ".join(_keyword_terms(key)[:8]) + " " + suffix

