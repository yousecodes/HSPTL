"""The four content labels, applied consistently to every artefact HSPTL holds.

Every piece of content in the platform carries exactly one label:

``GENERATED CONTENT``
    Authored by HSPTL from its own versioned templates and content packs. No
    external source text is reproduced. May still cite external sources.
``IMPORTED CONTENT``
    Brought in from outside HSPTL and retained as received. The raw bytes are
    immutable; anything derived from them is a separate ``DERIVED CONTENT`` item.
``SYNTHETIC CONTENT``
    Produced by a generator (Synthea and similar) and not describing any real
    person. Never a patient record.
``DERIVED CONTENT``
    Computed from one or more parent items: extraction, normalisation,
    summarisation, chunking, transformation. Always carries lineage to its parents.

The four labels are independent of four other dimensions that are often
confused with them: rights status, clinical review status, source validity and
publication status. A label says where content came from, nothing more. In
particular a ``GENERATED CONTENT`` item is not thereby clinically approved, and
an ``IMPORTED CONTENT`` item being free to read is not permission to reuse it.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

LABEL_GENERATED = "GENERATED CONTENT"
LABEL_IMPORTED = "IMPORTED CONTENT"
LABEL_SYNTHETIC = "SYNTHETIC CONTENT"
LABEL_DERIVED = "DERIVED CONTENT"

CONTENT_LABELS: tuple[str, ...] = (
    LABEL_GENERATED,
    LABEL_IMPORTED,
    LABEL_SYNTHETIC,
    LABEL_DERIVED,
)

# Human-readable explanations, surfaced verbatim in the UI so the meaning of a
# label is never left to interpretation.
LABEL_DESCRIPTIONS: dict[str, str] = {
    LABEL_GENERATED: "Authored by HSPTL from versioned templates. No external source text is reproduced.",
    LABEL_IMPORTED: "Imported from an external source and retained as received. Raw bytes are immutable.",
    LABEL_SYNTHETIC: "Produced by a generator. Does not describe any real person and is not a patient record.",
    LABEL_DERIVED: "Computed from parent content. Lineage to every parent is recorded.",
}

# Dimensions that are deliberately separate from the content label. Exposed so
# callers and the UI cannot collapse them into one "trust" score.
INDEPENDENT_DIMENSIONS: tuple[str, ...] = (
    "rights_status",
    "clinical_review_status",
    "source_validity",
    "evidence_certainty",
    "publication_status",
)

# Which labels may legitimately be the parent of which. A generated artefact may
# cite an imported source but may not be *derived* from content whose rights do
# not allow adaptation; the registry enforces that at the rights layer.
ALLOWED_PARENT_LABELS: dict[str, set[str]] = {
    LABEL_GENERATED: set(),  # generated content is authored, never derived
    LABEL_IMPORTED: set(),   # imported content is the raw root
    LABEL_SYNTHETIC: set(),  # generator output is a root
    LABEL_DERIVED: {LABEL_GENERATED, LABEL_IMPORTED, LABEL_SYNTHETIC, LABEL_DERIVED},
}


class LabelError(ValueError):
    """Raised when a label or lineage is inconsistent."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_" + uuid.uuid4().hex


def normalise_label(value: str) -> str:
    """Accept a label in any case/spacing and return the canonical form."""
    text = " ".join(str(value or "").split()).upper()
    for label in CONTENT_LABELS:
        if text == label:
            return label
    # Tolerate the underscore form used in early payloads.
    alias = text.replace("_", " ")
    for label in CONTENT_LABELS:
        if alias == label:
            return label
    raise LabelError(f"Unknown content label: {value!r}")


@dataclass(frozen=True, slots=True)
class LineageRef:
    """One parent of a derived item."""

    item_id: str
    label: str
    role: str = "source"  # source | chunk | normalisation | summary | transformation
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", normalise_label(self.label))
        if not str(self.item_id).strip():
            raise LabelError("A lineage reference requires a parent item id")

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "label": self.label,
                "role": self.role, "content_hash": self.content_hash}


@dataclass(frozen=True, slots=True)
class LabelledContent:
    """A content record with its label and, when derived, its full lineage."""

    label: str
    title: str
    content_hash: str
    workspace: str = ""
    content_type: str = ""
    lineage: tuple[LineageRef, ...] = ()
    rights_status: str = "unknown"
    clinical_review_status: str = "unreviewed"
    source_validity: str = "unassessed"
    evidence_certainty: str = "not_appraised"
    publication_status: str = "unpublished"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        label = normalise_label(self.label)
        object.__setattr__(self, "label", label)
        if not self.content_hash:
            raise LabelError("Every labelled content record requires a content hash")
        if label == LABEL_DERIVED and not self.lineage:
            raise LabelError("DERIVED CONTENT requires at least one lineage reference")
        if label != LABEL_DERIVED and self.lineage:
            raise LabelError(f"{label} must not declare lineage; derive a new item instead")
        allowed = ALLOWED_PARENT_LABELS[label]
        for ref in self.lineage:
            if ref.label not in allowed:
                raise LabelError(f"{label} cannot be derived from {ref.label}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "label_description": LABEL_DESCRIPTIONS[self.label],
            "title": self.title,
            "content_hash": self.content_hash,
            "workspace": self.workspace,
            "content_type": self.content_type,
            "lineage": [ref.to_dict() for ref in self.lineage],
            "rights_status": self.rights_status,
            "clinical_review_status": self.clinical_review_status,
            "source_validity": self.source_validity,
            "evidence_certainty": self.evidence_certainty,
            "publication_status": self.publication_status,
            "metadata": self.metadata,
            "independent_dimensions": list(INDEPENDENT_DIMENSIONS),
        }


def content_hash(text: str) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


class ContentLabelRegistry:
    """Durable label + lineage store.

    Large bodies stay file-backed elsewhere; this table holds the identity,
    label, hash and lineage edges only. Lineage is stored as explicit rows so a
    derived item can be traced back through every parent to its raw source.
    """

    def __init__(self, store):
        self.store = store
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_label_items (
                item_id TEXT PRIMARY KEY,
                label TEXT NOT NULL CHECK(label IN (
                    'GENERATED CONTENT','IMPORTED CONTENT','SYNTHETIC CONTENT','DERIVED CONTENT')),
                title TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL,
                workspace TEXT NOT NULL DEFAULT '',
                content_type TEXT NOT NULL DEFAULT '',
                rights_status TEXT NOT NULL DEFAULT 'unknown',
                clinical_review_status TEXT NOT NULL DEFAULT 'unreviewed',
                source_validity TEXT NOT NULL DEFAULT 'unassessed',
                evidence_certainty TEXT NOT NULL DEFAULT 'not_appraised',
                publication_status TEXT NOT NULL DEFAULT 'unpublished',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_label_items_label ON content_label_items(label, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_label_items_workspace ON content_label_items(workspace, label);
            CREATE TABLE IF NOT EXISTS content_lineage (
                child_item_id TEXT NOT NULL REFERENCES content_label_items(item_id),
                parent_item_id TEXT NOT NULL,
                parent_label TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'source',
                parent_content_hash TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                PRIMARY KEY(child_item_id, parent_item_id, role)
            );
            CREATE INDEX IF NOT EXISTS idx_lineage_parent ON content_lineage(parent_item_id);
            """)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(30, ?)", (_now(),)
            )

    def register(self, item: LabelledContent) -> dict[str, Any]:
        item_id = _id("lbl")
        now = _now()
        with self.store.transaction() as conn:
            conn.execute(
                """INSERT INTO content_label_items
                   (item_id,label,title,content_hash,workspace,content_type,rights_status,
                    clinical_review_status,source_validity,evidence_certainty,publication_status,
                    metadata_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item_id, item.label, item.title, item.content_hash, item.workspace,
                 item.content_type, item.rights_status, item.clinical_review_status,
                 item.source_validity, item.evidence_certainty, item.publication_status,
                 json.dumps(item.metadata, ensure_ascii=False), now),
            )
            for ref in item.lineage:
                conn.execute(
                    """INSERT OR REPLACE INTO content_lineage
                       (child_item_id,parent_item_id,parent_label,role,parent_content_hash,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (item_id, ref.item_id, ref.label, ref.role, ref.content_hash, now),
                )
        return self.get(item_id)  # type: ignore[return-value]

    def get(self, item_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM content_label_items WHERE item_id=?", (item_id,)).fetchone()
            if row is None:
                return None
            lineage = conn.execute(
                "SELECT * FROM content_lineage WHERE child_item_id=? ORDER BY role, parent_item_id",
                (item_id,),
            ).fetchall()
        record = dict(row)
        record["metadata"] = json.loads(record.pop("metadata_json") or "{}")
        record["label_description"] = LABEL_DESCRIPTIONS.get(record["label"], "")
        record["lineage"] = [
            {"item_id": r["parent_item_id"], "label": r["parent_label"],
             "role": r["role"], "content_hash": r["parent_content_hash"]}
            for r in lineage
        ]
        record["independent_dimensions"] = list(INDEPENDENT_DIMENSIONS)
        return record

    def children(self, parent_item_id: str) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            rows = conn.execute(
                "SELECT child_item_id FROM content_lineage WHERE parent_item_id=? ORDER BY created_at",
                (parent_item_id,),
            ).fetchall()
        return [item for item in (self.get(r["child_item_id"]) for r in rows) if item]

    def lineage_chain(self, item_id: str, *, max_depth: int = 12) -> dict[str, Any]:
        """Walk every parent edge back to the roots.

        Returns the ordered chain plus a ``complete`` flag. A chain that hits the
        depth limit or a missing parent is reported incomplete rather than
        silently presented as full provenance.
        """
        seen: set[str] = set()
        chain: list[dict[str, Any]] = []
        complete = True
        frontier = [(item_id, 0)]
        while frontier:
            current, depth = frontier.pop(0)
            if current in seen:
                continue
            seen.add(current)
            record = self.get(current)
            if record is None:
                complete = False
                continue
            chain.append({"item_id": current, "label": record["label"],
                          "title": record["title"], "depth": depth,
                          "content_hash": record["content_hash"]})
            if depth >= max_depth:
                complete = False
                continue
            for ref in record["lineage"]:
                frontier.append((ref["item_id"], depth + 1))
        return {
            "root_item_id": item_id,
            "chain": chain,
            "complete": complete,
            "root_labels": sorted({node["label"] for node in chain if node["depth"] > 0}),
            "item_count": len(chain),
        }

    def summary(self) -> dict[str, Any]:
        with self.store.transaction() as conn:
            counts = {row["label"]: row["n"] for row in conn.execute(
                "SELECT label, COUNT(*) AS n FROM content_label_items GROUP BY label")}
            derived = conn.execute(
                "SELECT COUNT(*) AS n FROM content_label_items WHERE label='DERIVED CONTENT'"
            ).fetchone()["n"]
            orphan_derived = conn.execute(
                "SELECT COUNT(*) AS n FROM content_label_items i WHERE i.label='DERIVED CONTENT' "
                "AND NOT EXISTS (SELECT 1 FROM content_lineage l WHERE l.child_item_id=i.item_id)"
            ).fetchone()["n"]
        return {
            "labels": list(CONTENT_LABELS),
            "descriptions": dict(LABEL_DESCRIPTIONS),
            "counts": {label: int(counts.get(label, 0)) for label in CONTENT_LABELS},
            "derived_total": int(derived),
            "derived_without_lineage": int(orphan_derived),
            "independent_dimensions": list(INDEPENDENT_DIMENSIONS),
            "integrity": "ok" if orphan_derived == 0 else "derived_content_missing_lineage",
        }


def label_for_import(source_type: str) -> str:
    """Map an existing UCKS source type onto one of the four labels.

    ``synthea_mednotegen`` and ``clinical_harvester`` produce synthetic
    material; everything else arrives from outside and is imported.
    """
    kind = str(source_type or "").strip().lower()
    if kind in {"synthea_mednotegen", "synthetic", "generator"}:
        return LABEL_SYNTHETIC
    if kind in {"generated", "template", "content_factory"}:
        return LABEL_GENERATED
    return LABEL_IMPORTED


def describe_labels() -> dict[str, Any]:
    """Catalogue used by the API and the UI legend."""
    return {
        "labels": [
            {"id": label, "description": LABEL_DESCRIPTIONS[label],
             "may_have_parents": bool(ALLOWED_PARENT_LABELS[label])}
            for label in CONTENT_LABELS
        ],
        "independent_dimensions": list(INDEPENDENT_DIMENSIONS),
        "note": ("A label records where content came from. It is not a rights decision, "
                 "a clinical approval or a publication status."),
    }
