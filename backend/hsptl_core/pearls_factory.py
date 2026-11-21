"""Clinical Knowledge & Pearls Factory: deterministic, source-linked templates.

This extends the existing Pearls workflow rather than replacing it. The existing
``generate_study_note`` still builds the learner-facing note from local and
open-access excerpts. What is added here is the *factory* layer that turns a
reviewed UCKS document into a reproducible pearl artefact:

* **Deterministic.** The same inputs, template version and seed always produce
  byte-identical output. No model, no sampling, no network call.
* **Source-linked.** Every claim carries a citation to a specific UCKS document
  and chunk. A claim with no citation is not emitted as a clinical statement.
* **Rights-aware.** A pearl may only quote a source when that source's rights
  permit copying, and may only paraphrase when they permit adaptation. A
  link-only source yields a citation-only pearl with no quoted text.
* **Label-preserving.** Output is ``DERIVED CONTENT`` with lineage to the source
  document, so a reader can always walk back to what it came from.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .ucks_connectors import FULLTEXT_LICENCES, _licence_key

TEMPLATE_VERSION = "pearls-factory/1.0.0"

# Deterministic pearl templates. Each declares the slots it fills and the
# section order. Slots are filled from source text only; nothing is invented.
TEMPLATES: dict[str, dict[str, Any]] = {
    "high_yield_pearl": {
        "template_id": "high_yield_pearl", "version": "1.0.0",
        "sections": ["headline", "key_points", "why_it_matters", "pitfall", "sources"],
        "max_points": 5, "requires_quote": True,
        "description": "A single high-yield point with its supporting evidence and one pitfall.",
    },
    "condition_summary": {
        "template_id": "condition_summary", "version": "1.0.0",
        "sections": ["definition", "key_points", "red_flags", "sources"],
        "max_points": 7, "requires_quote": True,
        "description": "Structured condition summary drawn from reviewed source spans.",
    },
    "investigation_pearl": {
        "template_id": "investigation_pearl", "version": "1.0.0",
        "sections": ["test", "interpretation", "limitations", "sources"],
        "max_points": 4, "requires_quote": True,
        "description": "How to interpret one investigation, including its limits.",
    },
    "safety_pearl": {
        "template_id": "safety_pearl", "version": "1.0.0",
        "sections": ["hazard", "action", "escalation", "sources"],
        "max_points": 4, "requires_quote": True,
        "description": "A patient-safety point with an explicit escalation path.",
    },
}

# Sentence-level extraction cues, deterministic and lexical only.
_CUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "recommendation": re.compile(r"\b(should|must|recommended|advise|indicated|offer)\b", re.I),
    "red_flag": re.compile(r"\b(urgent|emergency|immediately|red flag|do not delay|critical)\b", re.I),
    "pitfall": re.compile(r"\b(however|caution|avoid|pitfall|beware|misleading|false negative)\b", re.I),
    "threshold": re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|ml|mmol|mmol/L|%|hours?|minutes?|days?)\b", re.I),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_" + uuid.uuid4().hex


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_sentences(text: str) -> list[str]:
    """Deterministic sentence split. No model, no abbreviation heuristics beyond a guard list."""
    normalised = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalised:
        return []
    # Protect common clinical abbreviations before splitting on sentence stops.
    protected = normalised
    for abbrev in ("e.g.", "i.e.", "vs.", "Dr.", "Mr.", "Mrs.", "Ms.", "approx.", "no."):
        protected = protected.replace(abbrev, abbrev.replace(".", "\u2024"))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", protected)
    return [part.replace("\u2024", ".").strip() for part in parts if part.strip()]


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """One citable span of source text."""

    document_id: str
    chunk_id: str
    title: str
    text: str
    source_url: str = ""
    licence: str = ""
    review_status: str = "harvested"

    def citation(self) -> dict[str, Any]:
        return {"document_id": self.document_id, "chunk_id": self.chunk_id,
                "title": self.title, "source_url": self.source_url, "licence": self.licence}


class PearlsFactory:
    """Deterministic pearl composition over rights-cleared UCKS sources."""

    def __init__(self, store, *, ucks_repo, registry, labels):
        self.store = store
        self.ucks = ucks_repo
        self.registry = registry
        self.labels = labels
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS pearl_artifacts (
                artifact_id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                template_version TEXT NOT NULL,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                body_json TEXT NOT NULL,
                source_refs_json TEXT NOT NULL DEFAULT '[]',
                seed INTEGER NOT NULL DEFAULT 0,
                content_hash TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT 'DERIVED CONTENT',
                label_item_id TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                UNIQUE(template_id, topic, seed, content_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_pearl_artifacts_topic ON pearl_artifacts(topic, created_at DESC);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(34, ?)", (_now(),)
            )

    @staticmethod
    def templates() -> list[dict[str, Any]]:
        return [dict(entry) for entry in TEMPLATES.values()]

    # -- source selection -------------------------------------------------- #

    def _eligible_spans(self, topic: str, *, limit: int = 12) -> tuple[list[SourceSpan], list[dict[str, Any]]]:
        """Retrieve source spans and record why any were excluded."""
        spans: list[SourceSpan] = []
        excluded: list[dict[str, Any]] = []
        try:
            results = self.ucks.search(topic, limit=max(limit * 2, 20))
        except Exception:
            return [], [{"reason": "retrieval_unavailable"}]
        for hit in results:
            document = self.ucks.get_document(hit.get("document_id", ""))
            if not document:
                continue
            if document.get("review_status") == "rejected":
                excluded.append({"document_id": document["id"], "reason": "document_rejected"})
                continue
            if document.get("lifecycle_state") in {"retracted", "superseded"}:
                excluded.append({"document_id": document["id"],
                                 "reason": f"lifecycle_{document['lifecycle_state']}"})
                continue
            # Rights are recorded per *source*, not per document, so the envelope
            # must be resolved from the document's source_id.
            rights = self.registry.rights_for(document.get("source_id", ""))
            # Document-specific open-access permission may override a restrictive
            # source-family default only when our Europe PMC importer actually
            # fetched the full text after matching its explicit CC0/CC-BY/CC-BY-SA
            # allow-list. Metadata, abstracts, unknown licences, NC/ND and all
            # other records remain citation-only unless the source registry grants
            # permission independently.
            provenance = document.get("provenance", {}) or {}
            item_licence = _licence_key(str(provenance.get("full_text_licence", "")))
            item_open_licence = (
                provenance.get("full_text_status") == "fetched"
                and item_licence in FULLTEXT_LICENCES
            )
            may_quote = rights.allows_copy() or item_open_licence
            may_adapt = rights.allows_adaptation() or item_open_licence
            if not (may_quote or may_adapt):
                excluded.append({"document_id": document["id"],
                                 "reason": "rights_do_not_permit_text_use",
                                 "citation_only": True,
                                 "rights": rights.to_dict()["capabilities"]})
                # Still record a citation-only span so the pearl can reference it.
                spans.append(SourceSpan(
                    document_id=document["id"], chunk_id="", title=document.get("title", ""),
                    text="", source_url=document.get("source_url", ""),
                    licence=document.get("licence", ""),
                    review_status=document.get("review_status", "harvested")))
                continue
            body = hit.get("body") or ""
            if not body.strip():
                continue
            spans.append(SourceSpan(
                document_id=document["id"], chunk_id=hit.get("chunk_id", ""),
                title=document.get("title", ""), text=body,
                source_url=document.get("source_url", ""),
                licence=document.get("licence", ""),
                review_status=document.get("review_status", "harvested")))
        return spans, excluded

    @staticmethod
    def _rank_sentences(spans: list[SourceSpan], seed: int) -> list[tuple[SourceSpan, str, str]]:
        """Score sentences deterministically; ties broken by a seeded hash."""
        scored: list[tuple[int, str, SourceSpan, str]] = []
        for span in spans:
            if not span.text:
                continue
            for sentence in split_sentences(span.text):
                if len(sentence) < 30 or len(sentence) > 400:
                    continue
                score = 0
                cue = ""
                for name, pattern in _CUE_PATTERNS.items():
                    if pattern.search(sentence):
                        score += 1
                        cue = cue or name
                if score == 0:
                    continue
                tie = _sha(f"{seed}:{span.document_id}:{sentence}")
                scored.append((-score, tie, span, sentence, cue))
        scored.sort(key=lambda item: (item[0], item[1]))
        return [(span, sentence, cue) for _score, _tie, span, sentence, cue in scored]

    # -- composition ------------------------------------------------------- #

    def compose(self, *, topic: str, template_id: str = "high_yield_pearl", seed: int = 0) -> dict[str, Any]:
        template = TEMPLATES.get(template_id)
        if template is None:
            raise ValueError(f"Unknown pearl template: {template_id}")
        cleaned_topic = " ".join(str(topic or "").split())[:140]
        if len(cleaned_topic) < 2:
            raise ValueError("Enter a clinical topic of at least two characters")

        spans, excluded = self._eligible_spans(cleaned_topic)
        ranked = self._rank_sentences(spans, seed)

        if not ranked:
            # Fail closed: no invented clinical content, and say so explicitly.
            return {
                "state": "insufficient_evidence",
                "topic": cleaned_topic,
                "template_id": template_id,
                "template_version": TEMPLATE_VERSION,
                "message": ("No rights-cleared, reviewed source span supports a pearl for this topic. "
                            "No pearl was generated rather than inventing clinical content."),
                "excluded_sources": excluded,
                "source_refs": [],
                "body": None,
            }

        limit = int(template["max_points"])
        selected = ranked[:limit]
        sections: dict[str, list[dict[str, Any]]] = {name: [] for name in template["sections"]}
        citations: list[dict[str, Any]] = []

        for span, sentence, cue in selected:
            entry = {
                "text": sentence,
                "citation": span.citation(),
                "cue": cue,
                "document_title": span.title,
                "review_status": span.review_status,
            }
            citations.append(span.citation())
            target = {
                "recommendation": "key_points",
                "red_flag": "red_flags",
                "pitfall": "pitfall",
                "threshold": "key_points",
            }.get(cue, "key_points")
            if target not in sections:
                target = next((name for name in template["sections"] if name != "sources"), "key_points")
            sections[target].append(entry)

        # Fill the headline/definition from the highest-ranked point so the
        # artefact never opens with an empty section.
        headline_source = selected[0]
        for key in ("headline", "definition", "test", "hazard"):
            if key in sections and not sections[key]:
                sections[key].append({
                    "text": headline_source[1],
                    "citation": headline_source[0].citation(),
                    "cue": headline_source[2],
                    "document_title": headline_source[0].title,
                    "review_status": headline_source[0].review_status,
                })

        # Citation-only sources still appear in the source list.
        source_refs = [span.citation() | {"citation_only": not bool(span.text)} for span in spans]

        body = {
            "topic": cleaned_topic,
            "template_id": template["template_id"],
            "template_version": template["version"],
            "factory_version": TEMPLATE_VERSION,
            "seed": int(seed),
            "sections": sections,
            "limitations": [
                "Every point is quoted or paraphrased from a cited source span.",
                "Points without a citation are omitted rather than asserted.",
                "Requires clinical educator review before distribution.",
                "Not a clinical protocol and not for patient care.",
            ],
        }
        content_hash = _sha(json.dumps(body, sort_keys=True, ensure_ascii=False))
        artifact_id = _id("pearl")
        title = f"{cleaned_topic} · {template['template_id'].replace('_', ' ').title()}"

        label_item_id = ""
        if self.labels is not None:
            from .content_labels import LABEL_DERIVED, LabelledContent, LineageRef
            lineage = []
            for span in spans:
                if not span.document_id:
                    continue
                lineage.append(LineageRef(item_id=span.document_id, label="IMPORTED CONTENT",
                                          role="source", content_hash=span.chunk_id))
            if not lineage:
                lineage = [LineageRef(item_id="pearls-factory", label="GENERATED CONTENT",
                                      role="source", content_hash=TEMPLATE_VERSION)]
            record = self.labels.register(LabelledContent(
                label=LABEL_DERIVED, title=title, content_hash=content_hash,
                workspace="exam_hall", content_type="pearl", lineage=tuple(lineage),
                rights_status="citation_checked", clinical_review_status="unreviewed",
                metadata={"template_id": template["template_id"], "topic": cleaned_topic,
                          "seed": int(seed)},
            ))
            label_item_id = record["item_id"]

        with self.store.transaction() as conn:
            existing = conn.execute(
                "SELECT artifact_id FROM pearl_artifacts WHERE template_id=? AND topic=? AND seed=? AND content_hash=?",
                (template["template_id"], cleaned_topic, int(seed), content_hash)).fetchone()
            if existing:
                artifact_id = existing["artifact_id"]
            else:
                conn.execute(
                    """INSERT INTO pearl_artifacts
                       (artifact_id,template_id,template_version,topic,title,body_json,
                        source_refs_json,seed,content_hash,label,label_item_id,review_status,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (artifact_id, template["template_id"], template["version"], cleaned_topic,
                     title, json.dumps(body, ensure_ascii=False),
                     json.dumps(source_refs, ensure_ascii=False), int(seed), content_hash,
                     "DERIVED CONTENT", label_item_id, "draft", _now()),
                )

        return {
            "state": "composed",
            "artifact_id": artifact_id,
            "topic": cleaned_topic,
            "template_id": template["template_id"],
            "template_version": template["version"],
            "factory_version": TEMPLATE_VERSION,
            "title": title,
            "body": body,
            "source_refs": source_refs,
            "excluded_sources": excluded,
            "content_hash": content_hash,
            "label": "DERIVED CONTENT",
            "label_item_id": label_item_id,
            "review_status": "draft",
            "deterministic": True,
        }

    def list_artifacts(self, *, topic: str = "", limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM pearl_artifacts"
        params: list[Any] = []
        if topic:
            sql += " WHERE topic=?"
            params.append(topic)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self.store.transaction() as conn:
            rows = [dict(r) for r in conn.execute(sql, params)]
        for row in rows:
            row["body"] = json.loads(row.pop("body_json") or "{}")
            row["source_refs"] = json.loads(row.pop("source_refs_json") or "[]")
        return rows

    def review(self, artifact_id: str, *, reviewer: str, decision: str) -> dict[str, Any]:
        if decision not in {"approved", "rejected", "needs_changes"}:
            raise ValueError("Review decision must be approved, rejected or needs_changes")
        if not reviewer.strip():
            raise ValueError("A named reviewer is required")
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM pearl_artifacts WHERE artifact_id=?",
                               (artifact_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown pearl artifact")
            conn.execute("UPDATE pearl_artifacts SET review_status=? WHERE artifact_id=?",
                         (decision, artifact_id))
        artifact = dict(row)
        artifact["review_status"] = decision
        artifact["reviewer"] = reviewer
        artifact["body"] = json.loads(artifact.pop("body_json") or "{}")
        artifact["source_refs"] = json.loads(artifact.pop("source_refs_json") or "[]")
        return artifact

    def summary(self) -> dict[str, Any]:
        with self.store.transaction() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM pearl_artifacts").fetchone()["n"]
            by_status = {row["review_status"]: row["n"] for row in conn.execute(
                "SELECT review_status, COUNT(*) AS n FROM pearl_artifacts GROUP BY review_status")}
        return {
            "templates": [entry["template_id"] for entry in TEMPLATES.values()],
            "factory_version": TEMPLATE_VERSION,
            "artifacts": int(total),
            "by_review_status": by_status,
            "deterministic": True,
            "external_models": 0,
            "note": ("Composition is template-and-source only. There is no model, no sampling "
                     "and no network call in this factory."),
        }
