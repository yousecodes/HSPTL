"""SourceRef: one provenance value object for facts, notes, questions and cards.

Records where a claim came from and what may be done with it. It never asserts
that the clinical content is correct.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Iterable

from .note_engine import article_license_allows_excerpt

MAX_REFS = 40
_SEP = chr(0)


class SourceKind(StrEnum):
    FHIR_FACT = "fhir_fact"
    PDF = "pdf"
    ARTICLE = "article"
    CURATED_PACK = "curated_pack"
    LEARNER_AUTHORED = "learner_authored"
    EXTERNAL_LINK = "external_link"


class TrustState(StrEnum):
    SOURCE_DOCUMENTED = "source_documented"
    LEARNER_AUTHORED = "learner_authored"
    CURATED = "curated"
    EXTERNAL = "external"


def _text(value: Any, limit: int = 400) -> str:
    return "" if value is None else " ".join(str(value).split())[:limit]


@dataclass(frozen=True, slots=True)
class SourceRef:
    kind: SourceKind
    locator: str
    title: str = ""
    citation: str = ""
    retrieved_at: str = ""
    jurisdiction: str = ""
    license: str = ""
    verified: bool = False
    review_date: str = ""
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", SourceKind(self.kind))
        for name, limit in (("locator", 600), ("title", 300), ("citation", 500),
                            ("retrieved_at", 40), ("jurisdiction", 60), ("license", 200),
                            ("review_date", 20), ("snapshot_hash", 64)):
            object.__setattr__(self, name, _text(getattr(self, name), limit))
        if not self.locator:
            if self.kind is SourceKind.LEARNER_AUTHORED:
                object.__setattr__(self, "locator", "learner:authored")
            else:
                raise ValueError(f"A {self.kind.value} source reference requires a locator")
        if self.verified:
            if self.kind is SourceKind.LEARNER_AUTHORED:
                raise ValueError("Learner-authored content cannot be marked verified")
            if not self.review_date:
                raise ValueError("Verified sources require a review date")

    @property
    def ref_id(self) -> str:
        raw = _SEP.join((self.kind.value, self.locator, self.snapshot_hash))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @property
    def trust_state(self) -> TrustState:
        if self.kind is SourceKind.LEARNER_AUTHORED:
            return TrustState.LEARNER_AUTHORED
        if self.kind is SourceKind.FHIR_FACT:
            return TrustState.SOURCE_DOCUMENTED
        if self.kind is SourceKind.CURATED_PACK:
            return TrustState.CURATED
        return TrustState.EXTERNAL

    @property
    def excerpt_permitted(self) -> bool:
        if self.kind in {SourceKind.LEARNER_AUTHORED, SourceKind.FHIR_FACT,
                         SourceKind.CURATED_PACK}:
            return True
        if self.kind is SourceKind.EXTERNAL_LINK:
            return False  # link only; never excerpt
        return article_license_allows_excerpt("", self.license)

    def needs_review(self, today: date | None = None, max_age_days: int = 730) -> bool:
        if self.kind in {SourceKind.LEARNER_AUTHORED, SourceKind.FHIR_FACT}:
            return False
        if not self.review_date:
            return True
        try:
            reviewed = date.fromisoformat(self.review_date[:10])
        except ValueError:
            return True
        return ((today or date.today()) - reviewed).days > max_age_days

    def to_dict(self) -> dict[str, Any]:
        return {"ref_id": self.ref_id, "kind": self.kind.value, "locator": self.locator,
                "title": self.title, "citation": self.citation,
                "retrieved_at": self.retrieved_at, "jurisdiction": self.jurisdiction,
                "license": self.license, "verified": self.verified,
                "review_date": self.review_date, "snapshot_hash": self.snapshot_hash,
                "trust_state": self.trust_state.value,
                "excerpt_permitted": self.excerpt_permitted}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SourceRef":
        return cls(kind=SourceKind(str(raw.get("kind", "external_link"))),
                   locator=raw.get("locator", ""), title=raw.get("title", ""),
                   citation=raw.get("citation", ""), retrieved_at=raw.get("retrieved_at", ""),
                   jurisdiction=raw.get("jurisdiction", ""), license=raw.get("license", ""),
                   verified=bool(raw.get("verified", False)),
                   review_date=raw.get("review_date", ""),
                   snapshot_hash=raw.get("snapshot_hash", ""))


def normalise_refs(raw: Iterable[Any] | None) -> list[SourceRef]:
    out: dict[str, SourceRef] = {}
    for item in raw or []:
        ref = item if isinstance(item, SourceRef) else SourceRef.from_dict(item)
        out.setdefault(ref.ref_id, ref)
        if len(out) >= MAX_REFS:
            break
    return list(out.values())


def fhir_fact_ref(fact: dict[str, Any]) -> SourceRef:
    locator = (f"{fact.get('source_file', '')}#"
               f"{fact.get('resource_type', 'Resource')}/{fact.get('source_resource_id', '')}")
    return SourceRef(kind=SourceKind.FHIR_FACT, locator=locator,
                     title=_text(fact.get("code_text") or fact.get("resource_type"), 200),
                     citation=(f"Imported FHIR {fact.get('resource_type')} - "
                               f"{fact.get('effective_at') or 'date not recorded'}"),
                     retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def learner_ref(label: str = "Learner-authored entry") -> SourceRef:
    return SourceRef(kind=SourceKind.LEARNER_AUTHORED, locator="learner:authored",
                     title=_text(label, 200), citation=_text(label, 200))
