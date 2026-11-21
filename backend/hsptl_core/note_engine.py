"""Source-grounded high-yield note builder for HSPTL.

This is a deterministic note-construction engine, not a generative AI model.
It assembles curated local teaching packs, short attributed excerpts from PDFs
and article sections, and a structured study framework. Missing source content
is explicitly left as a prompt for the learner to verify.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

NOTE_TYPES: dict[str, dict[str, Any]] = {
    "Condition": {
        "description": "A concise disease review from mechanisms through management.",
        "sections": [
            ("Core concept", "Definition, clinical syndrome and the central diagnostic idea.", ["definition", "overview", "diagnosis", "clinical syndrome"]),
            ("Epidemiology and risk", "Who is affected and which factors change pre-test probability?", ["epidemiology", "prevalence", "risk", "incidence", "predispos"]),
            ("Pathophysiology", "Connect the underlying mechanism to the clinical findings.", ["pathophysiology", "mechanism", "pathogenesis", "physiology"]),
            ("Presentation", "Typical symptoms, signs, chronology and important variants.", ["presentation", "symptom", "clinical feature", "signs", "manifestation"]),
            ("Red flags and complications", "Identify time-critical features and major complications.", ["complication", "prognosis", "emergency", "severe", "red flag"]),
            ("Differential diagnosis", "Compare plausible alternatives and discriminating clues.", ["differential", "alternative diagnosis", "mimic"]),
            ("Investigations and diagnosis", "Explain which tests answer which clinical question.", ["investigation", "diagnostic", "test", "laboratory", "imaging", "criteria"]),
            ("Management principles", "Separate immediate stabilisation, disease-directed care and follow-up.", ["management", "treatment", "therapy", "intervention", "guideline"]),
            ("Follow-up and prevention", "Monitoring, prevention, counselling and safety-netting.", ["follow-up", "monitor", "prevention", "counselling", "review"]),
            ("Exam pearls", "A short set of high-yield distinctions and common pitfalls.", ["key point", "take-home", "conclusion", "pitfall", "learning point"]),
        ],
    },
    "Clinical presentation": {
        "description": "A practical approach to a presenting symptom or syndrome.",
        "sections": [
            ("First priorities", "Assess stability and address immediate threats before the differential.", ["emergency", "initial assessment", "stabilisation", "triage"]),
            ("Red flags", "Features that require urgent assessment or escalation.", ["red flag", "urgent", "emergency", "life-threatening"]),
            ("Focused history", "Onset, time course, severity, associated symptoms and risk factors.", ["history", "onset", "duration", "associated", "risk factor"]),
            ("Focused examination", "Identify the relevant examination domains and positive/negative findings.", ["examination", "physical findings", "clinical signs"]),
            ("Differential diagnosis", "Organise causes by system, probability and consequence of missing them.", ["differential", "causes", "etiology", "mimic"]),
            ("Initial investigations", "Choose tests that meaningfully change probability or management.", ["investigation", "diagnostic test", "laboratory", "imaging"]),
            ("Disposition and safety-netting", "Decide what determines admission, referral, review or discharge.", ["disposition", "admission", "referral", "follow-up", "safety net"]),
        ],
    },
    "Differential diagnosis": {
        "description": "A comparison-focused note that helps distinguish similar diagnoses.",
        "sections": [
            ("Problem representation", "Compress the key patient features into one discriminating statement.", ["presentation", "clinical features", "problem representation"]),
            ("Leading diagnoses", "List likely possibilities and why they fit.", ["diagnosis", "differential", "clinical features"]),
            ("Dangerous alternatives", "Identify diagnoses that must not be missed.", ["emergency", "complication", "severe", "red flag"]),
            ("Discriminating history and examination", "Which specific details move one diagnosis above another?", ["history", "examination", "finding", "sign"]),
            ("Discriminating tests", "Compare the purpose, strengths and limitations of investigations.", ["investigation", "test", "diagnostic", "sensitivity", "specificity"]),
            ("Common reasoning traps", "Look for anchoring, premature closure and over-reading incidental results.", ["pitfall", "misdiagnosis", "limitation", "false positive"]),
        ],
    },
    "Investigation": {
        "description": "A focused interpretation guide for a test, panel or imaging modality.",
        "sections": [
            ("What the test measures", "Explain the biological or technical signal being measured.", ["measure", "principle", "method", "assay"]),
            ("When to use it", "Indications and the clinical question it answers.", ["indication", "recommend", "when", "suspected"]),
            ("How to interpret it", "Units, thresholds, patterns and contextual interpretation.", ["interpret", "threshold", "reference", "result", "value"]),
            ("Patterns and differentials", "Link patterns to plausible diagnoses without treating them as pathognomonic.", ["pattern", "differential", "associated", "diagnostic"]),
            ("Limitations and confounders", "Pre-analytical factors, false results and clinical limitations.", ["limitation", "false", "confound", "sensitivity", "specificity"]),
            ("What to do next", "Repeat, confirmatory tests, correlation and escalation.", ["repeat", "confirm", "next", "follow-up", "management"]),
        ],
    },
    "Medicine": {
        "description": "A pharmacology note with explicit source checks for dosing and safety.",
        "sections": [
            ("Drug identity and class", "Generic name, class and relevant formulations.", ["drug", "class", "formulation", "indication"]),
            ("Mechanism of action", "Connect the pharmacological target to its effects.", ["mechanism", "pharmacology", "receptor", "inhibit", "agonist"]),
            ("Indications and place in therapy", "When it is used and where it fits in a treatment pathway.", ["indication", "treatment", "recommend", "therapy"]),
            ("Dose and administration", "Record dose only from a current, applicable product/formulary source.", ["dose", "dosage", "administration", "route"]),
            ("Contraindications and precautions", "Identify patients and circumstances where use may be unsafe.", ["contraindication", "precaution", "caution", "avoid"]),
            ("Adverse effects and interactions", "Common and serious adverse effects and clinically important interactions.", ["adverse", "side effect", "interaction", "toxicity"]),
            ("Monitoring and special populations", "Renal/hepatic considerations, pregnancy, age and monitoring.", ["monitor", "renal", "hepatic", "pregnancy", "paediatric", "elderly"]),
        ],
    },
    "OSCE / Procedure": {
        "description": "A structured station or procedure note with safety-critical steps.",
        "sections": [
            ("Purpose and indications", "What is the station/procedure trying to achieve?", ["indication", "purpose", "aim"]),
            ("Preparation and consent", "Identity, explanation, consent, chaperone and equipment.", ["consent", "preparation", "equipment", "chaperone"]),
            ("Systematic approach", "A repeatable sequence with clear transitions.", ["procedure", "step", "technique", "sequence"]),
            ("Safety and contraindications", "Risks, asepsis, monitoring and when to stop.", ["safety", "contraindication", "complication", "aseptic"]),
            ("Interpretation and communication", "Explain findings and communicate the plan.", ["interpret", "explain", "communicate", "result"]),
            ("Aftercare and documentation", "Aftercare, escalation, documentation and follow-up.", ["aftercare", "documentation", "follow-up", "monitor"]),
        ],
    },
}


def _words(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").casefold()) if len(w) > 2}


def find_curated_pack(topic: str, packs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Match a curated pack only on explicit topic keywords or distinctive title terms."""
    normal_topic = " ".join((topic or "").casefold().split())
    if not normal_topic:
        return None
    ranked: list[tuple[float, dict[str, Any]]] = []
    generic = {"acute", "chronic", "disease", "disorder", "clinical", "condition", "adult", "patient", "diagnosis", "management", "the", "and", "for"}
    topic_tokens = _words(normal_topic) - generic
    for pack in packs.values():
        phrases = [str(x).casefold().strip() for x in pack.get("keywords", []) if str(x).strip()]
        title = str(pack.get("title", "")).casefold()
        phrases.append(title.split(":", 1)[0].strip())
        exact = [phrase for phrase in phrases if phrase and phrase in normal_topic]
        if exact:
            ranked.append((1.0 + max(len(_words(phrase)) for phrase in exact) / 100, pack))
            continue
        phrase_tokens = set().union(*(_words(phrase) - generic for phrase in phrases)) if phrases else set()
        overlap = len(topic_tokens & phrase_tokens)
        # Require at least two distinctive shared tokens; a single generic word
        # such as "condition" must never trigger an unrelated curated pack.
        if overlap >= 2:
            score = overlap / max(2, len(topic_tokens))
            ranked.append((score, pack))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 0.5 else None


def extract_pdf_pages(path: Path, max_pages: int = 150) -> list[dict[str, Any]]:
    """Extract text page-by-page; scanned pages remain unavailable without OCR."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to import local reference PDFs.") from exc
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages[:max_pages], start=1):
        text = page.extract_text() or ""
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 80:
            pages.append({"page": index, "text": text})
    return pages


def pdf_source_excerpts(path: Path, topic: str, limit: int = 10) -> list[dict[str, str]]:
    """Return short matched excerpts with a page citation; never infer content."""
    terms = _words(topic)
    if not terms:
        return []
    excerpts: list[tuple[float, dict[str, str]]] = []
    for item in extract_pdf_pages(path):
        text = item["text"]
        chunks = re.split(r"(?<=[.!?])\s+", text)
        # Score short windows so that page context is retained without dumping whole pages.
        for start in range(0, len(chunks), 2):
            segment = " ".join(chunks[start:start + 3]).strip()
            if len(segment) < 65:
                continue
            tokens = _words(segment)
            overlap = len(terms & tokens)
            if overlap == 0:
                continue
            score = overlap / max(1, len(terms))
            excerpts.append((score, {
                "text": segment[:520],
                "citation": f"{path.name}, p. {item['page']}",
                "kind": "Local PDF",
                "url": "",
                "section": "PDF text extract",
            }))
    excerpts.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, item in excerpts:
        normal = " ".join(item["text"].casefold().split())
        if normal in seen:
            continue
        seen.add(normal)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def article_source_excerpts(article_payload: dict[str, Any], topic: str, limit: int = 2) -> list[dict[str, str]]:
    """Return at most two brief, attributed extracts per article for local study.

    The hard cap is intentional: callers cannot increase the amount quoted
    from one article by passing a larger limit.
    """
    limit = max(0, min(int(limit), 2))
    terms = _words(topic)
    out: list[tuple[float, dict[str, str]]] = []
    for section in article_payload.get("sections", []):
        title = str(section.get("heading", "Article section"))
        text = str(section.get("text", ""))
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for start in range(0, len(sentences), 2):
            segment = " ".join(sentences[start:start + 2]).strip()
            if len(segment) < 55:
                continue
            # Keep each extracted article quotation deliberately short.
            segment = " ".join(segment.split()[:42])
            overlap = len(terms & _words(title + " " + segment))
            if overlap:
                out.append((overlap / max(1, len(terms)), {
                    "text": segment,
                    "citation": f"{article_payload.get('title', 'Article')} — {title}",
                    "kind": "Open-access article extract",
                    "url": str(article_payload.get("url", "")),
                    "section": title,
                    "license": str(article_payload.get("license_text", "") or article_payload.get("license_url", "")),
                    "license_url": str(article_payload.get("license_url", "")),
                }))
    out.sort(key=lambda item: item[0], reverse=True)
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, item in out:
        normal = " ".join(item["text"].casefold().split())
        if normal in seen:
            continue
        seen.add(normal)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def article_license_allows_excerpt(license_url: str, license_text: str) -> bool:
    """Allow attributed short extracts for CC/CC0 material, excluding ND licences."""
    blob = f"{license_url} {license_text}".casefold().replace(" ", "")
    if not blob or "by-nd" in blob or "noderivatives" in blob or "no-derivatives" in blob:
        return False
    return (
        "creativecommons.org/licenses/" in blob
        or "creativecommons" in blob
        or "ccby" in blob
        or "cc0" in blob
    )


def _section_excerpts(section: tuple[str, str, list[str]], excerpts: Iterable[dict[str, str]], limit: int = 2) -> list[dict[str, str]]:
    _, _, hints = section
    hint_words = _words(" ".join(hints))
    ranked: list[tuple[int, dict[str, str]]] = []
    for excerpt in excerpts:
        text = f"{excerpt.get('section', '')} {excerpt.get('text', '')}"
        score = len(hint_words & _words(text))
        if score:
            ranked.append((score, excerpt))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _, entry in ranked[:limit]]


LEVEL_LENSES = {
    "Preclinical": "Emphasise anatomy, physiology, core mechanisms, terminology and links between mechanisms and findings.",
    "Clinical years": "Emphasise presentation, focused history and examination, differential diagnosis, test selection and management principles.",
    "Final-year / exam revision": "Emphasise prioritisation, dangerous alternatives, discriminating evidence, investigation sequence, escalation and common exam pitfalls.",
    "OSCE / practical": "Emphasise a safe sequence, communication, consent, clinical examination or procedure steps, and clear closure.",
}

JURISDICTION_LENSES = {
    "Egypt": "Prioritise current Egyptian Drug Authority formulary material, the Egyptian National Essential Medicines List and applicable Egyptian Health Council guidance when imported. International recommendations may not match local availability or policy.",
    "UK": "Prioritise the currently applicable UK professional and national guidance when imported. NICE recommendations are UK-contextual and should not be assumed to apply unchanged elsewhere.",
    "WHO / global": "Prioritise WHO publications and global technical guidance where relevant, while checking whether national policy differs.",
    "International": "Compare relevant current guidance across jurisdictions. Do not assume one country's thresholds, medicine availability or referral pathway applies everywhere.",
}


def generate_study_note(
    topic: str,
    note_type: str,
    level: str,
    jurisdiction: str,
    excerpts: list[dict[str, str]] | None = None,
    curated_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sectioned, citation-linked note and explicit gaps to verify.

    It does not generate uncited clinical facts. Where evidence is absent, the
    section remains a learning checklist rather than being filled with guesses.
    """
    topic = " ".join(str(topic or "").split())[:140]
    if len(topic) < 2:
        raise ValueError("Enter a clinical topic of at least two characters.")
    if note_type not in NOTE_TYPES:
        raise ValueError("Unsupported note type.")
    blueprint = NOTE_TYPES[note_type]
    sources = list(excerpts or [])
    if curated_pack:
        curated_title = str(curated_pack.get("source_title") or curated_pack.get("title") or "HSPTL curated teaching pack")
        curated_url = str(curated_pack.get("source_url") or "")
        summary = str(curated_pack.get("summary") or "").strip()
        if summary:
            sources.append({
                "text": summary,
                "citation": curated_title,
                "kind": "HSPTL curated teaching summary",
                "url": curated_url,
                "section": "Summary",
            })
        for question in curated_pack.get("questions", []):
            explanation = str(question.get("explanation") or "").strip()
            if explanation:
                sources.append({
                    "text": explanation,
                    "citation": curated_title,
                    "kind": "HSPTL curated question explanation",
                    "url": curated_url,
                    "section": "Explanation",
                })
            takeaway = str(question.get("takeaway") or "").strip()
            if takeaway:
                sources.append({
                    "text": takeaway,
                    "citation": curated_title,
                    "kind": "HSPTL curated teaching point",
                    "url": curated_url,
                    "section": "Key point",
                })
    sections: list[dict[str, Any]] = []
    for blueprint_section in blueprint["sections"]:
        title, objective, _ = blueprint_section
        matched = _section_excerpts(blueprint_section, sources)
        sections.append({
            "title": title,
            "objective": objective,
            "evidence": matched,
            "status": "source-supported excerpt" if matched else "needs source review",
        })

    curated = None
    if curated_pack:
        curated = {
            "title": str(curated_pack.get("title", "Curated teaching pack")),
            "summary": str(curated_pack.get("summary", "")),
            "tagline": str(curated_pack.get("tagline", "")),
            "takeaways": [str(x) for x in curated_pack.get("questions", [])[:0]],
            "questions": list(curated_pack.get("questions", []))[:8],
            "source_title": str(curated_pack.get("source_title", "")),
            "source_url": str(curated_pack.get("source_url", "")),
            "curated_takeaways": [],
        }
        # Curated learning packs store explanations/takeaways within MCQs;
        # extract their concise take-home statements without inventing claims.
        for question in curated_pack.get("questions", []):
            takeaway = str(question.get("takeaway", "")).strip()
            if takeaway and takeaway not in curated["curated_takeaways"]:
                curated["curated_takeaways"].append(takeaway)
        curated["curated_takeaways"] = curated["curated_takeaways"][:8]

    references: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    for item in sources:
        citation = str(item.get("citation", "Source not specified"))
        url = str(item.get("url", ""))
        key = citation + url
        if key not in seen_refs:
            seen_refs.add(key)
            references.append({
                "citation": citation,
                "url": url,
                "kind": str(item.get("kind", "Source")),
                "license": str(item.get("license", "")),
                "license_url": str(item.get("license_url", "")),
            })

    supported_sections = sum(bool(section["evidence"]) for section in sections)
    recall_prompts = []
    for section in sections:
        if section["evidence"]:
            evidence = section["evidence"][0]
            recall_prompts.append({
                "question": f"Explain the key learning points about {topic}: {section['title'].casefold()}.",
                "answer": evidence["text"],
                "source": evidence["citation"],
                "url": evidence.get("url", ""),
            })
    return {
        "title": f"{topic}: {note_type} study note",
        "topic": topic,
        "note_type": note_type,
        "level": level,
        "jurisdiction": jurisdiction,
        "description": blueprint["description"],
        "level_lens": LEVEL_LENSES.get(level, "Match depth to learner objectives."),
        "jurisdiction_lens": JURISDICTION_LENSES.get(jurisdiction, "Verify the local guideline and formulary context."),
        "case_application": None,
        "sections": sections,
        "curated_pack": curated,
        "references": references,
        "recall_prompts": recall_prompts[:10],
        "evidence_count": len(sources),
        "supported_sections": supported_sections,
        "total_sections": len(sections),
        "generated_mode": "Evidence-linked template assembly; no generative AI was used.",
    }


def note_to_markdown(note: dict[str, Any]) -> str:
    lines = [
        f"# {note['title']}",
        f"**Level:** {note['level']}  \n**Jurisdiction:** {note['jurisdiction']}",
        f"\n> {note['generated_mode']}",
        "\n## Learning focus",
        f"**Level:** {note.get('level_lens', 'Match depth to learner objectives.')}",
        f"**Jurisdiction:** {note.get('jurisdiction_lens', 'Verify applicable local guidance.')}",
        f"**Evidence coverage:** {note['supported_sections']} of {note['total_sections']} sections contain matched source material.",
        "\n## How to use this note",
        "Try to recall each section before opening the evidence. Excerpts are attributed source material; they are not independently appraised or converted into a guideline recommendation by HSPTL.",
    ]
    curated = note.get("curated_pack")
    if curated:
        lines.extend(["\n## Curated teaching summary", curated.get("summary", "")])
        if curated.get("curated_takeaways"):
            lines.append("\n### Take-home points")
            lines.extend(f"- {item}" for item in curated["curated_takeaways"])
    lines.append("\n## Study framework")
    for section in note.get("sections", []):
        lines.extend([f"\n### {section['title']}", f"**Learning focus:** {section['objective']}"])
        if section["evidence"]:
            for evidence in section["evidence"]:
                lines.append(f"\n> {evidence['text']}\n> \n> — {evidence['citation']}")
        else:
            lines.append("\n- Evidence not found in the selected sources. Complete this section from an appropriate current reference; do not assume missing information is negative or normal.")
    case_application = note.get("case_application")
    if case_application:
        lines.append("\n## Synthetic case application")
        lines.append(f"**Source:** {case_application.get('source', 'Synthea synthetic record')}")
        lines.append(case_application.get("summary", ""))
        if case_application.get("recorded_conditions"):
            lines.append("\n**Recorded condition entries:** " + "; ".join(case_application["recorded_conditions"]))
        if case_application.get("events"):
            lines.append("\n**Recent documented events:**")
            lines.extend(f"- {event}" for event in case_application["events"][:8])
        lines.append("\nThis is synthetic record context. Missing history, examination, diagnoses or outcomes are not inferred.")
    if note.get("recall_prompts"):
        lines.append("\n## Source-linked retrieval prompts")
        for index, prompt in enumerate(note["recall_prompts"], 1):
            lines.append(f"\n**Q{index}. {prompt['question']}**")
            lines.append(f"\n**Evidence to recall:** {prompt['answer']}\n\nSource: {prompt['source']}")
    if curated and curated.get("questions"):
        lines.append("\n## Active recall MCQs")
        for index, question in enumerate(curated["questions"], 1):
            options = question.get("options", [])
            answer_index = question.get("answer")
            answer = options[answer_index] if isinstance(answer_index, int) and answer_index < len(options) else "See source explanation"
            lines.append(f"\n**Q{index}. {question.get('question', '')}**")
            lines.extend(f"- {option}" for option in options)
            lines.append(f"\n**Answer:** {answer}\n\n{question.get('explanation', '')}")
    lines.append("\n## References")
    for ref in note.get("references", []):
        if ref.get("url"):
            licence_note = f" · Licence: {ref['license']}" if ref.get("license") else ""
            if ref.get("license_url"):
                licence_note += f" ([licence details]({ref['license_url']}))"
            lines.append(f"- [{ref['citation']}]({ref['url']}) ({ref['kind']}){licence_note}")
        else:
            licence_note = f" · Licence: {ref['license']}" if ref.get("license") else ""
            if ref.get("license_url"):
                licence_note += f" ([licence details]({ref['license_url']}))"
            lines.append(f"- {ref['citation']} ({ref['kind']}){licence_note}")
    lines.append("\n## Limitations\nThis is a study aid assembled from the selected sources and structured prompts. It is not an independently generated clinical guideline or clinical decision support, does not independently verify the sources, and must not be used to make patient-care decisions. Check source date, jurisdiction, population and recommendations before use.")
    return "\n".join(lines).strip() + "\n"


def build_external_tutor_prompt(note: dict[str, Any], markdown: str) -> str:
    return f"""You are a medical education tutor. Review the following source-linked HSPTL study note.

Tasks:
1. Identify unsupported or outdated statements and distinguish them from source-supported information.
2. Check for important omissions at the learner level: {note['level']}.
3. Explain complex mechanisms in a clinically useful way.
4. Create five application questions and three short-answer questions with answers.
5. Highlight jurisdiction-specific recommendations for: {note['jurisdiction']}.
6. Do not invent citations, doses, guideline recommendations or normal ranges. State when evidence is insufficient.

NOTE:
{markdown}
"""
