"""Article-level licence extraction. Identification is not legal clearance."""
from __future__ import annotations
import xml.etree.ElementTree as ET

def extract_jats_license(xml_bytes: bytes) -> dict[str, str]:
    result = {"license_uri": "", "license_type": "", "license_text": "",
              "license_status": "unknown_requires_manual_review"}
    try:
        root = ET.fromstring(xml_bytes)
        xlink = "{http://www.w3.org/1999/xlink}href"
        license_node = root.find(".//{*}permissions/{*}license")
        if license_node is None:
            license_node = root.find(".//{*}license")
        if license_node is None:
            return result
        uri = license_node.attrib.get(xlink) or license_node.attrib.get("href") or ""
        license_type = license_node.attrib.get("license-type") or ""
        text_value = " ".join(" ".join(license_node.itertext()).split())[:1200]
        result.update({"license_uri": uri, "license_type": license_type, "license_text": text_value})
        combined = (uri + " " + license_type + " " + text_value).lower()
        if "creativecommons.org/licenses/by-nc" in combined or "cc by-nc" in combined:
            result["license_status"] = "cc_by_nc_family_verify_terms"
        elif "creativecommons.org/licenses/by" in combined or "cc by" in combined:
            result["license_status"] = "creative_commons_identified_verify_version"
        elif "creativecommons.org/publicdomain" in combined or "cc0" in combined:
            result["license_status"] = "public_domain_or_cc0_verify"
        elif uri or license_type or text_value:
            result["license_status"] = "custom_or_other_license_manual_review"
        return result
    except (ET.ParseError, TypeError, ValueError):
        return result


def reuse_allowlisted(rights: dict[str, str]) -> bool:
    """Conservative technical allow-list for retaining article full text.

    This is not legal advice or a clinical validation decision. The source
    licence and attribution still require human review before redistribution.
    """
    uri = str(rights.get("license_uri") or "").strip().lower()
    kind = str(rights.get("license_type") or "").strip().lower()
    text = str(rights.get("license_text") or "").strip().lower()
    combined = " ".join((uri, kind, text))
    if any(term in combined for term in ("by-nc", "by-nd", "noncommercial", "non-commercial", "no derivatives", "no-derivatives")):
        return False
    if uri.startswith(("https://creativecommons.org/publicdomain/zero/", "http://creativecommons.org/publicdomain/zero/")):
        return True
    if uri.startswith(("https://creativecommons.org/licenses/by/", "http://creativecommons.org/licenses/by/")):
        return True
    if uri.startswith(("https://creativecommons.org/licenses/by-sa/", "http://creativecommons.org/licenses/by-sa/")):
        return True
    return False
