"""Conservative medication terminology matching.

Only explicit, curated exact aliases may produce a terminology code. Fuzzy or
jurisdiction-blind guesses are intentionally not supported.
"""
from __future__ import annotations

import re
from typing import Any


def normalise_medication_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.+/-]", " ", str(value or "").casefold())).strip()


def resolve_medication(name: str, mappings: list[dict[str, Any]], jurisdiction: str = "Egypt") -> dict[str, Any]:
    query = normalise_medication_name(name)
    if not query:
        return {"status": "unmatched", "input": name, "code": None, "display": None, "reason": "No medication name was supplied"}
    for item in mappings:
        if str(item.get("jurisdiction", "")).casefold() not in {jurisdiction.casefold(), "global"}:
            continue
        aliases = item.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        if any(normalise_medication_name(alias) == query for alias in aliases):
            code = str(item.get("code", "")).strip()
            display = str(item.get("display", "")).strip()
            if code and display and item.get("source"):
                return {"status": "matched", "input": name, "code": code, "display": display,
                        "system": item.get("system", "RxNorm"), "source": item["source"],
                        "jurisdiction": jurisdiction}
    return {"status": "unmatched", "input": name, "code": None, "display": None,
            "reason": "No verified exact alias is available for this jurisdiction"}


def umls_export_allowed(*, licence_active: bool, requested_sources: list[str],
                        export_permitted_sources: set[str]) -> tuple[bool, str]:
    if not licence_active:
        return False, "An active UMLS licence is required before export."
    blocked = sorted(set(requested_sources) - set(export_permitted_sources))
    if blocked:
        return False, "Export is blocked for source vocabularies without redistribution permission: " + ", ".join(blocked)
    return True, "Export permitted for the explicitly approved source vocabularies."
