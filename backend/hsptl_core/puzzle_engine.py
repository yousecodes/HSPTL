"""Source-aware, quality-gated clinical puzzle discovery and drafting.

Important design constraint: an open-access flag means free-to-read, not
necessarily permission to adapt. Puzzle drafts are generated only when the
article's JATS metadata identifies an adaptation-compatible Creative Commons
licence. Every imported draft requires human review before entering the game.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import requests

USER_AGENT = "HSPTL-ClinicalLearning/2.0.0-rc1 (personal educational use)"
TIMEOUT = (5, 22)
MAX_ARTICLE_BYTES = 8_000_000

# External sources are linked to their own current pages. HSPTL does not scrape,
# copy or re-host proprietary challenge text, questions, photographs or figures.
EXTERNAL_CHALLENGE_SOURCES = [
    {
        "name": "The Clinical Problem Solvers — Virtual Morning Reports",
        "kind": "Frequent interactive clinical case conferences",
        "cadence": "Multiple case conferences most weeks; latest listings vary",
        "url": "https://cps-vmr-publisher.vercel.app/vmr",
        "note": "Search recent cases by chief concern, title or date. Useful for progressive disclosure and diagnostic reasoning. HSPTL links to the provider and does not copy its case text.",
    },
    {
        "name": "NEJM Image Challenge",
        "kind": "Image-based diagnosis challenge",
        "cadence": "Usually weekly; archive updated regularly",
        "url": "https://www.nejm.org/image-challenge",
        "note": "A current visual diagnostic challenge with an archive. View images, answer choices and explanations on the publisher's own site; HSPTL stores a link only.",
    },
    {
        "name": "JAMA Network Clinical Challenge",
        "kind": "Diagnosis and next-step challenge",
        "cadence": "Regularly updated collection",
        "url": "https://jamanetwork.com/collections/44038/clinical-challenge",
        "note": "Case reports commonly ask for the diagnosis or next best test/treatment. Some full text may require access; HSPTL stores a link only.",
    },
    {
        "name": "BMJ Case Reports — Open Access collection",
        "kind": "Open-access case reports across specialties",
        "cadence": "Sorted by most recent; availability varies",
        "url": "https://casereports.bmj.com/pages/collection/open-access",
        "note": "Browse the journal's open-access collection. Check the individual article's licence before reuse; HSPTL does not scrape or re-host this collection.",
    },
    {
        "name": "NEJM Case Challenges",
        "kind": "Longitudinal diagnostic cases",
        "cadence": "Irregular / periodic",
        "url": "https://www.nejm.org/case-challenges",
        "note": "Use the publisher's own challenge interface; no content is copied into HSPTL.",
    },
    {
        "name": "JGIM — Exercises in Clinical Reasoning",
        "kind": "Peer-reviewed stepwise reasoning cases",
        "cadence": "Journal series; not a daily feed",
        "url": "https://link.springer.com/journal/11606",
        "note": "Look for open-access articles that reveal clinical information sequentially and interleave it with clinician reasoning.",
    },
    {
        "name": "AHRQ PSNet WebM&M",
        "kind": "Patient-safety cases and expert commentaries",
        "cadence": "WebM&M cases/commentaries are generally monthly; PSNet updates weekly",
        "url": "https://psnet.ahrq.gov/webmm",
        "note": "Practise diagnostic error analysis, systems thinking and safer decisions. Reuse requires the relevant permission; HSPTL links only.",
    },
]


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml"})
    return session


def search_open_access_case_reports(topic: str, limit: int = 15) -> list[dict[str, Any]]:
    """Search Europe PMC for recent, open-access records indexed as case reports."""
    topic = (topic or "").strip()
    if not topic:
        return []
    if len(topic) > 140:
        raise ValueError("Topic must be 140 characters or fewer.")
    limit = max(1, min(int(limit), 30))
    query = f'({topic}) AND OPEN_ACCESS:Y AND PUB_TYPE:"case reports" sort_date:y'
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    with _session() as session:
        with session.get(
            url,
            params={"query": query, "format": "json", "pageSize": limit, "resultType": "core"},
            timeout=TIMEOUT,
        ) as response:
            response.raise_for_status()
            payload = response.json()
    rows = payload.get("resultList", {}).get("result", [])
    return [row for row in rows if isinstance(row, dict) and str(row.get("isOpenAccess", "")).upper() == "Y"]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _license_from_jats(root: ET.Element) -> tuple[str, str]:
    for node in root.iter():
        if _local_name(node.tag) != "license":
            continue
        href = ""
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1].casefold() in {"href", "xlink:href"}:
                href = str(value)
                break
        text = " ".join("".join(node.itertext()).split())
        combined = f"{href} {text}".casefold()
        if "creativecommons.org/licenses/by" in combined or re.search(r"\bcc by\b", combined):
            if "-nd" in combined or "no derivatives" in combined:
                return "", "No-derivatives licence: automated adaptation is disabled."
            if "-nc" in combined or "noncommercial" in combined or "non-commercial" in combined:
                label = "CC BY-NC" + ("-SA" if "-sa" in combined else "")
            else:
                label = "CC BY" + ("-SA" if "-sa" in combined else "")
            return label, ""
        if "creativecommons.org/publicdomain/zero" in combined or "cc0" in combined:
            return "CC0", ""
        if "public domain" in combined:
            return "Public domain", ""
        if href or text:
            return "Unrecognised / restricted licence", "Licence does not match the supported adaptation licences."
    return "Licence not verified", "JATS licence metadata was absent; reference can be opened, but automated adaptation is disabled."


def fetch_jats_article(pmcid: str) -> tuple[ET.Element | None, str, str]:
    """Fetch one PMC full-text XML document and inspect its actual article licence."""
    pmcid = (pmcid or "").strip().upper()
    if not re.fullmatch(r"PMC\d+", pmcid):
        return None, "Licence not verified", "No valid PMC identifier was available."
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{quote(pmcid)}/fullTextXML"
    session = _session()
    response = session.get(url, timeout=TIMEOUT, stream=True)
    try:
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_ARTICLE_BYTES:
                raise ValueError("Article XML exceeded the 8 MB safety limit.")
            chunks.append(chunk)
        root = ET.fromstring(b"".join(chunks))
        licence, note = _license_from_jats(root)
        return root, licence, note
    finally:
        response.close()
        session.close()


def _section_title(section: ET.Element) -> str:
    for child in list(section):
        if _local_name(child.tag) == "title":
            return " ".join("".join(child.itertext()).split())[:160]
    return ""


def extract_case_paragraphs(root: ET.Element) -> list[tuple[str, str]]:
    """Extract paragraphs only from abstract and clinically relevant case sections."""
    allowed = ("case presentation", "case report", "case description", "patient information",
               "clinical findings", "investigations", "diagnostic assessment", "presentation of case")
    found: list[tuple[str, str]] = []
    for node in root.iter():
        if _local_name(node.tag) == "abstract":
            for paragraph in node.iter():
                if _local_name(paragraph.tag) == "p":
                    text = " ".join("".join(paragraph.itertext()).split())
                    if len(text.split()) >= 10:
                        found.append(("Abstract", text))
    for section in root.iter():
        if _local_name(section.tag) != "sec":
            continue
        heading = _section_title(section)
        if not any(term in heading.casefold() for term in allowed):
            continue
        for paragraph in section.iter():
            if _local_name(paragraph.tag) == "p":
                text = " ".join("".join(paragraph.itertext()).split())
                if len(text.split()) >= 10:
                    found.append((heading or "Case presentation", text))
    # Stable de-duplication prevents repeated abstract/full-text paragraphs.
    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for section, text in found:
        key = re.sub(r"\W+", " ", text.casefold()).strip()
        if key and key not in seen:
            seen.add(key)
            unique.append((section, text))
    return unique


def _sentences(text: str) -> list[str]:
    # Conservative sentence split; abbreviations can be imperfect, so candidates
    # are always shown for review before any puzzle can be saved.
    chunks = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [" ".join(x.split()) for x in chunks if 7 <= len(x.split()) <= 55]


def classify_clue(sentence: str) -> str:
    text = sentence.casefold()
    patterns = {
        "presentation": r"presented|complaint|admitted|developed|reported|history of",
        "timeline": r"\b(days?|weeks?|months?|years?|since|prior to|following|after)\b|\b\d{1,2}-year-old\b",
        "examination": r"examination|physical findings|vital signs|on examination|auscultation|palpation|revealed tenderness",
        "investigation": r"ct\b|mri|ultrasound|radiograph|x-ray|biopsy|histolog|laboratory|blood test|culture|ecg|electrocardiogram|scan|imaging|troponin|haemoglobin|hemoglobin",
        "management": r"treated|therapy|management|underwent|received|administered|intervention|surgery|surgical",
        "outcome": r"follow-up|follow up|improved|resolved|recovered|discharged|outcome|remained stable|died|mortality",
    }
    for label, pattern in patterns.items():
        if re.search(pattern, text):
            return label
    return "clinical context"


def infer_answer_hint(text: str) -> str:
    patterns = [
        r"(?:was ultimately|was subsequently|was finally|was) diagnosed with\s+([^.;,:()]{3,100})",
        r"(?:the )?final diagnosis (?:was|of)\s+([^.;,:()]{3,100})",
        r"diagnosis of\s+([^.;,:()]{3,100})",
        r"consistent with\s+([^.;,:()]{3,100})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            answer = re.sub(r"\s+", " ", match.group(1)).strip(" .;:")
            answer = re.split(r"\b(?:and was|for which|which was|with treatment|was treated|after|before|following)\b", answer, maxsplit=1, flags=re.I)[0].strip()
            if 2 <= len(answer.split()) <= 12:
                return answer[:100]
    return ""



_CLUE_ORDER = {
    "presentation": 0,
    "timeline": 1,
    "examination": 2,
    "investigation": 3,
    "management": 4,
    "outcome": 5,
    "clinical context": 6,
}


def _token_set(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z]{3,}", (text or "").casefold()) if token not in {
        "the", "and", "with", "from", "that", "this", "were", "was", "are", "for", "has", "had", "have", "who", "which", "after", "before", "during", "into", "over", "under", "than", "then", "also", "their", "there", "patient", "patients"
    }}


def _too_similar(candidate: str, chosen: list[str], threshold: float = 0.72) -> bool:
    tokens = _token_set(candidate)
    if not tokens:
        return True
    for existing in chosen:
        other = _token_set(existing)
        if not other:
            continue
        similarity = len(tokens & other) / max(1, len(tokens | other))
        if similarity >= threshold:
            return True
    return False


def _contains_answer_leak(sentence: str, answer_hint: str) -> bool:
    normal_sentence = re.sub(r"\W+", " ", sentence.casefold()).strip()
    normal_answer = re.sub(r"\W+", " ", (answer_hint or "").casefold()).strip()
    if normal_answer and normal_answer in normal_sentence:
        return True
    return bool(re.search(
        r"\b(?:the )?(?:final )?diagnosis (?:was|is|of)|\bdiagnosed (?:with|as)|\bwe conclude that\b|\bthe patient was found to have\b",
        sentence,
        flags=re.IGNORECASE,
    ))


def _clinical_specificity(sentence: str) -> bool:
    return bool(re.search(
        r"\b\d+(?:\.\d+)?\s?(?:mmol|mmhg|mg|mcg|g/dl|g/l|bpm|beats|years?|days?|weeks?|months?|cm|mm|ml|kg)\b|\b\d+(?:\.\d+)?\s?%|\b\d{1,3}-year-old\b|"
        r"\b(?:ecg|electrocardiogram|troponin|creatinine|haemoglobin|hemoglobin|ferritin|crp|ct\b|mri|ultrasound|biopsy|culture|spirometry|oxygen saturation|ejection fraction|blood gas)\b",
        sentence,
        flags=re.IGNORECASE,
    ))


def score_puzzle_structure(
    article: dict[str, Any],
    paragraphs: list[tuple[str, str]],
    clues: list[dict[str, str]],
    answer_hint: str,
) -> dict[str, Any]:
    """Score structural teaching suitability; never claim clinical validity.

    Maximum 100: answer trace 12, clue count 24, category diversity 24,
    source-section diversity 10, objective clinical specificity 14, citation
    metadata 6, source-ordered progression 5, and challenge-interest signals 5.
    Interest signals are textual cues (e.g. unusual presentation or diagnostic
    pitfall), not a clinical judgement that the case is important or rare.
    """
    clue_count = min(6, len(clues))
    categories = {row.get("category", "clinical context") for row in clues}
    sections = {row.get("section", "") for row in clues if row.get("section")}
    specificity_count = sum(_clinical_specificity(row.get("text", "")) for row in clues)
    metadata_count = sum(bool(article.get(field)) for field in ("doi", "authorString", "journalTitle", "pubYear"))
    answer_points = 12 if answer_hint else 0
    clue_points = min(24, clue_count * 4)
    category_points = min(24, len(categories) * 4)
    section_points = min(10, len(sections) * 3)
    specificity_points = min(14, specificity_count * 2)
    metadata_points = min(6, metadata_count * 2)
    ordered = [_CLUE_ORDER.get(row.get("category", "clinical context"), 6) for row in clues]
    progression_points = 5 if len(ordered) >= 4 and ordered == sorted(ordered) and len(set(ordered)) >= 3 else 0

    text = (str(article.get("title", "")) + " " + " ".join(value for _, value in paragraphs)).casefold()
    interest_patterns = {
        "unusual presentation": r"\b(?:rare|unusual|atypical|unexpected)\b",
        "diagnostic pitfall": r"\b(?:pitfall|mimic|masquerad|misdiagnos|delayed diagnosis|diagnostic delay)\w*\b",
        "reasoning challenge": r"\b(?:diagnostic challenge|diagnostic dilemma|difficult to diagnose|missed diagnosis)\b",
        "multisystem features": r"\b(?:multisystem|multi-system|multiple organ|systemic involvement)\b",
        "unexpected course": r"\b(?:paradoxical|refractory|treatment failure|unexpected course)\b",
    }
    interest_signals = [label for label, pattern in interest_patterns.items() if re.search(pattern, text)]
    interest_points = min(5, len(interest_signals))

    score = min(100, answer_points + clue_points + category_points + section_points + specificity_points + metadata_points + progression_points + interest_points)
    return {
        "score": score,
        "components": {
            "answer_trace": answer_points,
            "clue_count": clue_points,
            "category_diversity": category_points,
            "section_diversity": section_points,
            "clinical_specificity": specificity_points,
            "citation_metadata": metadata_points,
            "progression_and_distinctness": progression_points,
            "challenge_interest_signals": interest_points,
        },
        "interest_signals": interest_signals,
        "clue_count": clue_count,
        "category_count": len(categories),
        "section_count": len(sections),
        "specific_clue_count": specificity_count,
    }


def build_puzzle_candidate(article: dict[str, Any]) -> dict[str, Any]:
    """Build a review-required candidate from one explicitly reusable OA article."""
    pmcid = str(article.get("pmcid") or "").strip().upper()
    title = str(article.get("title") or "Untitled case report").strip()
    if str(article.get("isOpenAccess") or "").upper() != "Y":
        return {"eligible": False, "score": 0, "reasons": ["Search record is not explicitly marked open access."], "title": title}
    if not pmcid:
        return {"eligible": False, "score": 0, "reasons": ["No PMC full-text identifier; reference only."], "title": title}
    root, licence, licence_note = fetch_jats_article(pmcid)
    if root is None:
        return {"eligible": False, "score": 0, "reasons": [licence_note], "title": title, "licence": licence}
    if licence not in {"CC BY", "CC BY-SA", "CC BY-NC", "CC BY-NC-SA", "CC0", "Public domain"}:
        return {"eligible": False, "score": 0, "reasons": [licence_note or "Article licence does not permit supported adaptation."], "title": title, "licence": licence}

    paragraphs = extract_case_paragraphs(root)
    sentence_rows: list[dict[str, Any]] = []
    sequence = 0
    for section, paragraph in paragraphs:
        for sentence in _sentences(paragraph):
            sentence_rows.append({"section": section, "text": sentence, "category": classify_clue(sentence), "sequence": sequence})
            sequence += 1

    abstract_text = " ".join(text for section, text in paragraphs if section.casefold() == "abstract")
    answer_hint = infer_answer_hint(abstract_text or " ".join(text for _, text in paragraphs))
    usable_rows = [row for row in sentence_rows if not _contains_answer_leak(row["text"], answer_hint)]

    # Select category-diverse facts, then restore their original source order.
    # This gives progressive breadth without fabricating a new chronology.
    preferred = ["presentation", "timeline", "examination", "investigation", "management", "outcome"]
    selected: list[dict[str, Any]] = []
    selected_text: list[str] = []
    for category in preferred:
        match = next((row for row in usable_rows if row["category"] == category and not _too_similar(row["text"], selected_text)), None)
        if match:
            selected.append(match)
            selected_text.append(match["text"])
    for row in usable_rows:
        if len(selected) >= 6:
            break
        if row not in selected and not _too_similar(row["text"], selected_text):
            selected.append(row)
            selected_text.append(row["text"])
    selected.sort(key=lambda row: row["sequence"])
    clues = [{"text": row["text"], "category": row["category"], "section": row["section"]} for row in selected[:6]]

    structural = score_puzzle_structure(article, paragraphs, clues, answer_hint)
    score = structural["score"]
    clue_count = structural["clue_count"]
    category_count = structural["category_count"]
    section_count = structural["section_count"]
    reasons = []
    if not answer_hint:
        reasons.append("No unambiguous diagnosis phrase was extracted; add and verify the answer manually.")
    if clue_count < 4:
        reasons.append("Fewer than four distinct, useful clinical clues were found.")
    if category_count < 3:
        reasons.append("Clues cover too few distinct clinical domains.")
    if section_count < 2:
        reasons.append("Clues come from fewer than two article sections; review narrative quality carefully.")
    if structural["specific_clue_count"] < 2:
        reasons.append("Few clues contain objective findings, investigations, measurements or clinical signals.")
    reasons.append("Human review is mandatory: verify the answer, factual accuracy, clue sequence and clinical interpretation.")

    authors = str(article.get("authorString") or "Author details unavailable")
    journal = str(article.get("journalTitle") or "Journal unavailable")
    year = str(article.get("pubYear") or "Year unavailable")
    doi = str(article.get("doi") or "")
    pmid = str(article.get("pmid") or "")
    source_url = f"https://europepmc.org/articles/{pmcid}"
    return {
        "eligible": clue_count >= 4 and category_count >= 3 and section_count >= 2 and structural["specific_clue_count"] >= 2 and score >= 58,
        "needs_review": True,
        "score": score,
        "score_components": structural["components"],
        "quality_metrics": {key: structural[key] for key in ("clue_count", "category_count", "section_count", "specific_clue_count")},
        "interest_signals": structural["interest_signals"],
        "title": title,
        "answer_hint": answer_hint,
        "clues": [{"text": row["text"], "category": row["category"], "section": row["section"]} for row in selected[:6]],
        "specialty": ", ".join(str(x.get("descriptorName") or "") for x in (article.get("meshHeadingList", {}).get("meshHeading", []) if isinstance(article.get("meshHeadingList"), dict) else [])[:3] if x.get("descriptorName")) or "General medicine",
        "difficulty": "Intermediate",
        "source": {"title": title, "authors": authors, "journal": journal, "year": year, "doi": doi, "pmid": pmid, "pmcid": pmcid, "url": source_url, "licence": licence},
        "reasons": reasons,
    }


def candidate_to_puzzle(candidate: dict[str, Any], answer: str, explanation: str, takeaways: list[str], question: str = "What is the most likely diagnosis?", question_type: str = "diagnosis", aliases: list[str] | None = None, difficulty: str = "Intermediate") -> dict[str, Any]:
    """Convert an approved candidate to the runtime puzzle schema."""
    if not candidate.get("eligible"):
        raise ValueError("This article did not pass the automatic source-quality gate.")
    answer = (answer or "").strip()
    clues = [str(row.get("text") or "").strip() for row in candidate.get("clues", []) if str(row.get("text") or "").strip()]
    takeaways = [str(x).strip() for x in takeaways if str(x).strip()]
    if len(answer) < 3 or len(clues) < 4 or not takeaways:
        raise ValueError("Enter a verified answer, at least four clues, and one teaching point.")
    payload = candidate["source"]
    identity = "\x1f".join([
        str(payload.get("pmcid", "")),
        str(question_type or "diagnosis").casefold(),
        re.sub(r"\W+", " ", answer.casefold()).strip(),
        re.sub(r"\W+", " ", (question or "").casefold()).strip(),
    ])
    puzzle_id = "oa-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:14]
    attribution = f"{payload.get('authors')} ({payload.get('year')}). {payload.get('title')}. {payload.get('journal')}. {payload.get('licence')}. {payload.get('url')}"
    return {
        "id": puzzle_id,
        "specialty": candidate.get("specialty", "General medicine"),
        "difficulty": difficulty if difficulty in {"Foundation", "Intermediate", "Advanced"} else "Intermediate",
        "answer": answer,
        "question": question.strip() or "What is the most likely diagnosis?",
        "question_type": question_type,
        "aliases": [str(item).strip() for item in (aliases or []) if str(item).strip()][:12],
        "clues": clues[:6],
        "explanation": explanation.strip() or "Review the source article for the diagnostic reasoning and context.",
        "takeaways": takeaways[:5],
        "source_title": payload.get("title", "Open-access case report"),
        "source_url": payload.get("url", ""),
        "source_type": "Open-access case report; human-reviewed adaptation",
        "source_licence": payload.get("licence", ""),
        "attribution": attribution,
        "source_id": payload.get("pmcid", ""),
        "created_from": "Europe PMC",
    }



def select_daily_puzzle(pool: list[dict[str, Any]], day_string: str, attempt_notes: list[dict[str, Any]] | None = None) -> int:
    """Choose a stable daily puzzle while penalising recent repeats.

    This is deterministic for a given day and content pool. It uses a 30-day
    no-repeat preference, recent-specialty diversity, and a deterministic hash
    as the final tie-breaker. If the pool is too small, repetition is allowed
    rather than pretending an infinite unique supply exists.
    """
    import datetime as _dt
    if not pool:
        return 0
    attempts = attempt_notes or []
    recent_ids: set[str] = set()
    recent_specialties: set[str] = set()
    recent_question_types: set[str] = set()
    recent_difficulties: set[str] = set()
    cutoff = _dt.date.fromisoformat(day_string) - _dt.timedelta(days=30)
    for note in attempts:
        try:
            payload = __import__("json").loads(note.get("body") or "{}")
            when = _dt.date.fromisoformat(str(payload.get("date", ""))[:10])
        except (ValueError, TypeError):
            continue
        if when < cutoff:
            continue
        if payload.get("puzzle_id"):
            recent_ids.add(str(payload["puzzle_id"]))
        if payload.get("specialty"):
            recent_specialties.add(str(payload["specialty"]).casefold())
        if payload.get("question_type"):
            recent_question_types.add(str(payload["question_type"]).casefold())
        if payload.get("difficulty"):
            recent_difficulties.add(str(payload["difficulty"]).casefold())
    candidates = [i for i, p in enumerate(pool) if p.get("id") not in recent_ids]
    if not candidates:
        candidates = list(range(len(pool)))

    # Prefer a fresh specialty, then a different challenge type and difficulty.
    # Each preference is soft: if it would empty the pool, retain the prior set.
    for field, recent in (
        ("specialty", recent_specialties),
        ("question_type", recent_question_types),
        ("difficulty", recent_difficulties),
    ):
        if not recent:
            continue
        alternatives = [
            i for i in candidates
            if str(pool[i].get(field) or ("diagnosis" if field == "question_type" else "Intermediate" if field == "difficulty" else "General medicine")).casefold() not in recent
        ]
        if alternatives:
            candidates = alternatives
    import hashlib as _hashlib
    digest = _hashlib.sha256(day_string.encode("utf-8")).hexdigest()
    return candidates[int(digest[:12], 16) % len(candidates)]



def resolve_daily_puzzle_index(pool: list[dict[str, Any]], puzzle_id: str | None, day_string: str, attempt_notes: list[dict[str, Any]] | None = None) -> int:
    """Keep an in-progress puzzle stable; otherwise choose via the daily selector."""
    if not pool:
        raise ValueError("Cannot select a puzzle from an empty pool.")
    if puzzle_id:
        existing = next((index for index, puzzle in enumerate(pool) if puzzle.get("id") == puzzle_id), None)
        if existing is not None:
            return existing
    return select_daily_puzzle(pool, day_string, attempt_notes)

def load_approved_puzzles(store) -> list[dict[str, Any]]:
    """Read user-approved puzzles from the existing SQLite notes table."""
    import json
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for note in store.notes("ApprovedPuzzle"):
        try:
            puzzle = json.loads(note.get("body") or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(puzzle, dict) and puzzle.get("id") and puzzle["id"] not in seen:
            seen.add(puzzle["id"])
            output.append(puzzle)
    return sorted(output, key=lambda p: str(p.get("id")))
