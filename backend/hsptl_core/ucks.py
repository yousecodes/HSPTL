"""Unified Clinical Knowledge System (UCKS) foundation.

Additive, local-first registry for source provenance, immutable document versions
and lexical FTS5 chunks. Legacy vector repository methods remain for explicitly
injected compatibility/test providers; HSPTL 4.0 HTTP/UI paths do not instantiate
embedding providers or expose model-based retrieval.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class UCKSRepository:
    SOURCE_TYPES = {"clinical_harvester", "synthea_mednotegen", "external_import", "online_feed"}
    REVIEW_STATES = {"harvested", "machine_screened", "reviewed", "validated", "rejected"}
    CONTENT_TYPES = {
        "case_report", "case_series", "trial", "systematic_review", "guideline",
        "observational_study", "diagnostic_study", "dataset", "clinical_note",
        "synthetic_case", "reference_document", "other"
    }

    def __init__(self, store):
        self.store = store
        self._initialise()

    def _initialise(self) -> None:
        with self.store.transaction() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS ucks_sources (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL,
                locator TEXT NOT NULL DEFAULT '', licence TEXT NOT NULL DEFAULT '',
                reuse_permitted INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
                config_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ucks_documents (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES ucks_sources(id),
                external_id TEXT NOT NULL DEFAULT '', title TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'other', specialty TEXT NOT NULL DEFAULT '',
                jurisdiction TEXT NOT NULL DEFAULT '', publication_date TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '', licence TEXT NOT NULL DEFAULT '',
                provenance_json TEXT NOT NULL DEFAULT '{}', review_status TEXT NOT NULL DEFAULT 'harvested',
                current_version INTEGER NOT NULL DEFAULT 1, content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(source_id, external_id, content_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_docs_type ON ucks_documents(content_type, specialty);
            CREATE INDEX IF NOT EXISTS idx_ucks_docs_review ON ucks_documents(review_status, updated_at);
            CREATE TABLE IF NOT EXISTS ucks_document_versions (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
                version INTEGER NOT NULL, body TEXT NOT NULL, content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(document_id, version)
            );
            CREATE TABLE IF NOT EXISTS ucks_chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
                version INTEGER NOT NULL, ordinal INTEGER NOT NULL, heading TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL, token_estimate INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}', content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(document_id, version, ordinal)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_chunks_doc ON ucks_chunks(document_id, version);
            CREATE TABLE IF NOT EXISTS ucks_embeddings (
                id TEXT PRIMARY KEY, chunk_id TEXT NOT NULL REFERENCES ucks_chunks(id),
                provider TEXT NOT NULL, model TEXT NOT NULL, dimensions INTEGER NOT NULL,
                vector_blob BLOB NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(chunk_id, provider, model)
            );
            CREATE TABLE IF NOT EXISTS ucks_ingestion_jobs (
                id TEXT PRIMARY KEY, source_id TEXT REFERENCES ucks_sources(id),
                status TEXT NOT NULL, records_seen INTEGER NOT NULL DEFAULT 0,
                records_added INTEGER NOT NULL DEFAULT 0, errors_json TEXT NOT NULL DEFAULT '[]',
                started_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS ucks_chunks_fts USING fts5(
                chunk_id UNINDEXED, title, heading, body
            );
            CREATE TABLE IF NOT EXISTS ucks_feed_state (
                source_id TEXT PRIMARY KEY REFERENCES ucks_sources(id),
                etag TEXT NOT NULL DEFAULT '', last_modified TEXT NOT NULL DEFAULT '',
                last_checked TEXT NOT NULL DEFAULT '', last_status TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS ucks_graph_nodes (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, node_type TEXT NOT NULL,
                terminology_system TEXT NOT NULL DEFAULT '', terminology_code TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
                UNIQUE(node_type, terminology_system, terminology_code, label)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_graph_node_label ON ucks_graph_nodes(label);
            CREATE TABLE IF NOT EXISTS ucks_graph_edges (
                id TEXT PRIMARY KEY, subject_id TEXT NOT NULL REFERENCES ucks_graph_nodes(id),
                predicate TEXT NOT NULL, object_id TEXT NOT NULL REFERENCES ucks_graph_nodes(id),
                document_id TEXT REFERENCES ucks_documents(id), evidence_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, UNIQUE(subject_id,predicate,object_id,document_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_graph_edges_subject ON ucks_graph_edges(subject_id,predicate);
            CREATE INDEX IF NOT EXISTS idx_ucks_graph_edges_object ON ucks_graph_edges(object_id,predicate);
            CREATE TABLE IF NOT EXISTS ucks_entity_proposals (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
                chunk_id TEXT, surface TEXT NOT NULL, normalized_label TEXT NOT NULL,
                entity_type TEXT NOT NULL, terminology_system TEXT NOT NULL DEFAULT '',
                terminology_code TEXT NOT NULL DEFAULT '', polarity TEXT NOT NULL DEFAULT 'present',
                context TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
                extraction_method TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '',
                UNIQUE(document_id, normalized_label, entity_type, polarity, context)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_entity_review ON ucks_entity_proposals(status, entity_type);
            CREATE TABLE IF NOT EXISTS ucks_relationship_proposals (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES ucks_documents(id),
                chunk_id TEXT, subject_label TEXT NOT NULL, subject_type TEXT NOT NULL,
                predicate TEXT NOT NULL, object_label TEXT NOT NULL, object_type TEXT NOT NULL,
                context TEXT NOT NULL, assertion_status TEXT NOT NULL DEFAULT 'asserted',
                status TEXT NOT NULL DEFAULT 'pending', extraction_method TEXT NOT NULL,
                created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '',
                graph_edge_id TEXT NOT NULL DEFAULT '',
                UNIQUE(document_id, subject_label, predicate, object_label, context)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_relationship_review
                ON ucks_relationship_proposals(status, predicate);
            CREATE TABLE IF NOT EXISTS ucks_terminology_concepts (
                id TEXT PRIMARY KEY, system TEXT NOT NULL, code TEXT NOT NULL, display TEXT NOT NULL,
                version TEXT NOT NULL, publisher TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '',
                licence TEXT NOT NULL, reuse_permitted INTEGER NOT NULL DEFAULT 0,
                redistribution_permitted INTEGER NOT NULL DEFAULT 0, jurisdiction TEXT NOT NULL DEFAULT 'global',
                aliases_json TEXT NOT NULL DEFAULT '[]', review_status TEXT NOT NULL DEFAULT 'unreviewed',
                import_name TEXT NOT NULL, source_reference TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '',
                UNIQUE(system,code,version)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_term_concepts ON ucks_terminology_concepts(system,review_status);
            CREATE TABLE IF NOT EXISTS ucks_terminology_candidates (
                id TEXT PRIMARY KEY, entity_proposal_id TEXT NOT NULL REFERENCES ucks_entity_proposals(id),
                concept_id TEXT NOT NULL REFERENCES ucks_terminology_concepts(id),
                match_method TEXT NOT NULL, match_score REAL NOT NULL,
                review_status TEXT NOT NULL DEFAULT 'pending', concept_review_status TEXT NOT NULL DEFAULT 'unreviewed',
                created_at TEXT NOT NULL, reviewed_at TEXT NOT NULL DEFAULT '',
                UNIQUE(entity_proposal_id,concept_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_term_candidate_review ON ucks_terminology_candidates(review_status);
            CREATE TABLE IF NOT EXISTS ucks_feed_schedule (
                source_id TEXT PRIMARY KEY REFERENCES ucks_sources(id),
                enabled INTEGER NOT NULL DEFAULT 0, interval_minutes INTEGER NOT NULL DEFAULT 360,
                next_run TEXT NOT NULL DEFAULT '', last_attempt TEXT NOT NULL DEFAULT '',
                lease_until TEXT NOT NULL DEFAULT '', consecutive_failures INTEGER NOT NULL DEFAULT 0,
                last_duration_ms INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_feed_due ON ucks_feed_schedule(enabled,next_run);
            CREATE TABLE IF NOT EXISTS ucks_feed_audit (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES ucks_sources(id),
                outcome TEXT NOT NULL, records_seen INTEGER NOT NULL DEFAULT 0,
                records_added INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL, completed_at TEXT NOT NULL, duration_ms INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ucks_feed_audit_source ON ucks_feed_audit(source_id,started_at);
            """)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(ucks_documents)")}
            if "lifecycle_state" not in columns:
                conn.execute("ALTER TABLE ucks_documents ADD COLUMN lifecycle_state TEXT NOT NULL DEFAULT 'current'")
            if "supersedes_document_id" not in columns:
                conn.execute("ALTER TABLE ucks_documents ADD COLUMN supersedes_document_id TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ucks_lifecycle ON ucks_documents(lifecycle_state, updated_at)")
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(21, ?)", (_now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(22, ?)", (_now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(23, ?)", (_now(),))
            conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(24, ?)", (_now(),))

    @staticmethod
    def _chunk(body: str, max_chars: int = 1800) -> list[str]:
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs or [body.strip()]:
            if paragraph.startswith("#") and current:
                chunks.append(current)
                current = ""
            while len(paragraph) > max_chars:
                cut = paragraph.rfind(" ", 0, max_chars)
                cut = cut if cut > max_chars // 2 else max_chars
                piece, paragraph = paragraph[:cut].strip(), paragraph[cut:].strip()
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
            if current and len(current) + len(paragraph) + 1 > max_chars:
                chunks.append(current)
                current = paragraph
            else:
                current = (current + "\\n" + paragraph).strip()
        if current:
            chunks.append(current)
        return chunks

    def register_source(self, *, name: str, source_type: str, locator: str = "",
                        licence: str = "", reuse_permitted: bool = False,
                        config: dict[str, Any] | None = None) -> dict[str, Any]:
        if source_type not in self.SOURCE_TYPES:
            raise ValueError("Unsupported UCKS source type")
        now, source_id = _now(), _id("src")
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO ucks_sources
                (id,name,source_type,locator,licence,reuse_permitted,config_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (source_id, name.strip(), source_type, locator.strip(), licence.strip(),
                 int(reuse_permitted), json.dumps(config or {}, ensure_ascii=False), now, now))
            cfg = config or {}
            auto_sync = bool(cfg.get("auto_sync", False)) and source_type == "online_feed"
            interval = max(15, min(int(cfg.get("sync_interval_minutes", 360)), 10080))
            next_run = datetime.now(timezone.utc).isoformat(timespec="seconds") if auto_sync else ""
            conn.execute("INSERT INTO ucks_feed_schedule(source_id,enabled,interval_minutes,next_run,updated_at) VALUES(?,?,?,?,?)",
                         (source_id, int(auto_sync), interval, next_run, now))
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["config"] = json.loads(item.pop("config_json"))
        item["reuse_permitted"] = bool(item["reuse_permitted"])
        item["enabled"] = bool(item["enabled"])
        return item

    def list_sources(self) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            ids = [r["id"] for r in conn.execute("SELECT id FROM ucks_sources ORDER BY name")]
        return [self.get_source(x) for x in ids]

    def ingest_document(self, *, source_id: str, title: str, body: str,
                        content_type: str = "other", external_id: str = "",
                        specialty: str = "", jurisdiction: str = "",
                        publication_date: str = "", source_url: str = "",
                        licence: str = "", provenance: dict[str, Any] | None = None,
                        review_status: str = "harvested") -> dict[str, Any]:
        if content_type not in self.CONTENT_TYPES:
            raise ValueError("Unsupported UCKS content type")
        if review_status not in self.REVIEW_STATES:
            raise ValueError("Unsupported review status")
        if not title.strip() or not body.strip():
            raise ValueError("Document title and body are required")
        source = self.get_source(source_id)
        if not source:
            raise ValueError("Unknown UCKS source")
        if review_status == "validated":
            raise ValueError("Imported content cannot be self-promoted to validated")
        digest, now = _hash(body), _now()
        doc_id = _id("doc")
        chunks = self._chunk(body)
        with self.store.transaction() as conn:
            existing = conn.execute("""SELECT id FROM ucks_documents
                WHERE source_id=? AND external_id=? AND content_hash=?""",
                (source_id, external_id, digest)).fetchone()
            if existing:
                duplicate = self.get_document(existing["id"])
                duplicate["created"] = False
                return duplicate
            conn.execute("""INSERT INTO ucks_documents
                (id,source_id,external_id,title,content_type,specialty,jurisdiction,
                 publication_date,source_url,licence,provenance_json,review_status,
                 current_version,content_hash,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (doc_id, source_id, external_id, title.strip(), content_type, specialty,
                 jurisdiction, publication_date, source_url, licence,
                 json.dumps(provenance or {}, ensure_ascii=False), review_status, 1,
                 digest, now, now))
            conn.execute("""INSERT INTO ucks_document_versions
                (id,document_id,version,body,content_hash,created_at) VALUES(?,?,?,?,?,?)""",
                (_id("ver"), doc_id, 1, body, digest, now))
            for ordinal, chunk in enumerate(chunks):
                chunk_id = _id("chk")
                conn.execute("""INSERT INTO ucks_chunks
                    (id,document_id,version,ordinal,heading,body,token_estimate,
                     metadata_json,content_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (chunk_id, doc_id, 1, ordinal, "", chunk, max(1, len(chunk.split())),
                     "{}", _hash(chunk), now))
                conn.execute("INSERT INTO ucks_chunks_fts(chunk_id,title,heading,body) VALUES(?,?,?,?)",
                             (chunk_id, title, "", chunk))
        created = self.get_document(doc_id)
        created["created"] = True
        return created

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_documents WHERE id=?", (document_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            item["provenance"] = json.loads(item.pop("provenance_json"))
            item["chunk_count"] = conn.execute(
                "SELECT COUNT(*) FROM ucks_chunks WHERE document_id=? AND version=?",
                (document_id, item["current_version"])).fetchone()[0]
        return item

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [x for x in re.findall(r"[\w-]+", query) if len(x) > 1]
        if not terms:
            return []
        match = " AND ".join('"' + x.replace('"', '""') + '"' for x in terms[:12])
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT c.id AS chunk_id,c.document_id,c.ordinal,c.heading,
                    c.body,d.title,d.content_type,d.specialty,d.jurisdiction,d.review_status,d.source_url,
                    d.licence,d.publication_date,d.source_id,d.provenance_json,d.lifecycle_state,s.name AS source_name,
                    bm25(ucks_chunks_fts) AS score
                FROM ucks_chunks_fts f JOIN ucks_chunks c ON c.id=f.chunk_id
                JOIN ucks_documents d ON d.id=c.document_id
                JOIN ucks_sources s ON s.id=d.source_id
                WHERE ucks_chunks_fts MATCH ? ORDER BY score LIMIT ?""",
                (match, max(1, min(limit, 50)))).fetchall()
        return [dict(r) for r in rows]

    WORKSPACE_CONTENT_TYPES = {
        "clinic": {"case_report", "case_series", "observational_study", "diagnostic_study", "guideline", "systematic_review", "synthetic_case"},
        "rounds": {"case_report", "case_series", "clinical_note", "synthetic_case", "reference_document"},
        "lab": {"diagnostic_study", "observational_study", "guideline", "systematic_review", "dataset", "case_report"},
        "ward": {"guideline", "systematic_review", "trial", "observational_study", "clinical_note", "case_report"},
        "exam_hall": {"systematic_review", "guideline", "trial", "diagnostic_study", "case_report", "case_series"},
        "portfolio": set(CONTENT_TYPES),
    }

    def workspace_retrieve(self, workspace: str, query: str, *, limit: int = 10,
                            specialty: str = "", jurisdiction: str = "",
                            review_status: str = "", provider=None,
                            terminology_system: str = "") -> list[dict[str, Any]]:
        """Workspace-aware retrieval; the product route supplies no vector provider.

        Portfolio is the governance workspace and may inspect rejected records;
        learning workspaces never return rejected material. Retrieval ranking is
        not a clinical validity or recommendation score.
        """
        workspace = workspace.strip().lower()
        if workspace not in self.WORKSPACE_CONTENT_TYPES:
            raise ValueError("Unsupported UCKS workspace")
        if not query.strip():
            return []
        content_types = self.WORKSPACE_CONTENT_TYPES[workspace]
        expansion = self.terminology_graph_expansion(query, system=terminology_system)
        variants = [query] + expansion["expanded_terms"]
        full = []
        seen_full: set[str] = set()
        for variant in variants:
            for row in self.search(variant, limit=50):
                if row["chunk_id"] not in seen_full:
                    seen_full.add(row["chunk_id"])
                    full.append(row)
        vector = self.vector_search(query, provider, limit=50) if provider else []
        fused: dict[str, dict[str, Any]] = {}
        for method, rows in (("full_text", full), ("vector", vector)):
            for rank, row in enumerate(rows, start=1):
                item = fused.setdefault(row["chunk_id"], dict(row))
                item["retrieval_methods"] = sorted(set(item.get("retrieval_methods", [])) | {method})
                item["retrieval_score"] = item.get("retrieval_score", 0.0) + 1.0 / (60 + rank)
        results = []
        allowed_states = ({review_status} if review_status else
                          ({"harvested", "machine_screened", "reviewed", "validated", "rejected"} if workspace == "portfolio"
                           else {"harvested", "machine_screened", "reviewed", "validated"}))
        if workspace != "portfolio":
            allowed_states.discard("rejected")
        for item in fused.values():
            if item.get("lifecycle_state", "current") in {"retracted", "superseded"}:
                continue
            if item.get("content_type") not in content_types:
                continue
            if item.get("review_status") not in allowed_states:
                continue
            if specialty and item.get("specialty", "").casefold() != specialty.casefold():
                continue
            if jurisdiction and item.get("jurisdiction", "").casefold() != jurisdiction.casefold():
                continue
            # Keep a distinct, explicit status label; retrieval never upgrades it.
            item["evidence_status"] = item.get("review_status", "harvested")
            item["is_validated"] = item["evidence_status"] == "validated"
            raw_provenance = item.pop("provenance_json", "{}")
            try:
                item["provenance"] = json.loads(raw_provenance or "{}")
            except (TypeError, json.JSONDecodeError):
                item["provenance"] = {}
            item["retrieval_score"] = round(float(item["retrieval_score"]), 8)
            item["terminology_expansion"] = expansion["expanded_terms"]
            item["graph_evidence"] = self._document_graph_evidence(
                item.get("document_id", ""), expansion["matched_node_ids"])
            results.append(item)
        results.sort(key=lambda row: row["retrieval_score"], reverse=True)
        return results[:max(1, min(limit, 50))]

    def terminology_graph_expansion(self, query: str, *, system: str = "") -> dict[str, Any]:
        """Expand a query only through reviewed terminology mappings and accepted graph edges."""
        if system and system not in {"SNOMEDCT", "LOINC", "ICD10CM", "RxNorm"}:
            raise ValueError("Unsupported terminology system")
        tokens = [t.casefold() for t in re.findall(r"[\w-]+", query) if len(t) > 1]
        if not tokens:
            return {"expanded_terms": [], "matched_node_ids": [], "matched_concepts": []}
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT n.id,n.label,n.terminology_system,n.terminology_code,
                    c.display,c.version,c.system
                FROM ucks_graph_nodes n JOIN ucks_terminology_concepts c
                  ON c.system=n.terminology_system AND c.code=n.terminology_code
                WHERE c.review_status='approved' AND c.reuse_permitted=1
                  AND n.terminology_code<>''""").fetchall()
            matched = []
            for row in rows:
                if system and row["system"] != system:
                    continue
                label = row["label"].casefold()
                code = row["terminology_code"].casefold()
                if any(token == code or token in label or token in code for token in tokens):
                    matched.append(dict(row))
            if not matched:
                return {"expanded_terms": [], "matched_node_ids": [], "matched_concepts": []}
            ids = [r["id"] for r in matched]
            marks = ",".join("?" for _ in ids)
            edges = conn.execute(f"""SELECT e.subject_id,e.predicate,e.object_id,
                    a.label AS subject_label,b.label AS object_label
                FROM ucks_graph_edges e JOIN ucks_graph_nodes a ON a.id=e.subject_id
                JOIN ucks_graph_nodes b ON b.id=e.object_id
                WHERE e.subject_id IN ({marks}) OR e.object_id IN ({marks})""", (*ids, *ids)).fetchall()
        terms: list[str] = []
        for row in matched:
            if row["label"] not in terms:
                terms.append(row["label"])
        for edge in edges:
            for label in (edge["subject_label"], edge["object_label"]):
                if label not in terms:
                    terms.append(label)
        return {"expanded_terms": terms[:12], "matched_node_ids": ids,
                "matched_concepts": [{"system": r["system"], "code": r["terminology_code"],
                                       "display": r["display"], "version": r["version"]}
                                      for r in matched[:20]]}

    def _document_graph_evidence(self, document_id: str, matched_node_ids: list[str]) -> list[dict[str, Any]]:
        if not document_id or not matched_node_ids:
            return []
        marks = ",".join("?" for _ in matched_node_ids)
        with self.store.transaction() as conn:
            rows = conn.execute(f"""SELECT e.id,e.predicate,e.evidence_note,e.document_id,
                    a.label AS subject,b.label AS object
                FROM ucks_graph_edges e JOIN ucks_graph_nodes a ON a.id=e.subject_id
                JOIN ucks_graph_nodes b ON b.id=e.object_id
                WHERE e.document_id=? AND (e.subject_id IN ({marks}) OR e.object_id IN ({marks}))
                ORDER BY e.created_at DESC LIMIT 20""", (document_id, *matched_node_ids, *matched_node_ids)).fetchall()
        return [dict(row) for row in rows]

    def graph_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search reviewed terminology-linked concepts and return graph/evidence context."""
        expansion = self.terminology_graph_expansion(query)
        results = []
        for node_id in expansion["matched_node_ids"][:max(1, min(limit, 50))]:
            graph = self.graph_neighbours(node_id, depth=1, limit=50)
            node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
            if node:
                results.append({"concept": node, "neighbours": [n for n in graph["nodes"] if n["id"] != node_id],
                                "relationships": graph["edges"]})
        return results

    def index_embeddings(self, provider, *, limit: int = 100) -> dict[str, int | str]:
        """Index previously unembedded chunks using a real configured provider."""
        from .ucks_embeddings import pack_vector
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT c.id,c.body FROM ucks_chunks c
                LEFT JOIN ucks_embeddings e ON e.chunk_id=c.id AND e.provider=? AND e.model=?
                WHERE e.id IS NULL ORDER BY c.created_at,c.ordinal LIMIT ?""",
                (provider.name, provider.model, max(1, min(limit, 1000)))).fetchall()
        if not rows:
            return {"provider": provider.name, "model": provider.model, "indexed": 0}
        vectors = provider.embed([row["body"] for row in rows])
        if len(vectors) != len(rows):
            raise ValueError("Embedding provider returned an unexpected vector count")
        indexed = 0
        with self.store.transaction() as conn:
            for row, vector in zip(rows, vectors):
                blob = pack_vector(vector)
                conn.execute("""INSERT OR REPLACE INTO ucks_embeddings
                    (id,chunk_id,provider,model,dimensions,vector_blob,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (_id("emb"), row["id"], provider.name, provider.model, len(vector), blob, _now()))
                indexed += 1
        return {"provider": provider.name, "model": provider.model, "indexed": indexed}

    def vector_search(self, query: str, provider, *, limit: int = 10) -> list[dict[str, Any]]:
        from .ucks_embeddings import cosine, unpack_vector
        query_vector = provider.embed([query])[0]
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT c.id AS chunk_id,c.document_id,c.ordinal,c.heading,c.body,
                d.title,d.content_type,d.specialty,d.jurisdiction,d.review_status,d.source_url,d.licence,
                d.publication_date,d.source_id,d.provenance_json,s.name AS source_name,
                e.dimensions,e.vector_blob FROM ucks_embeddings e
                JOIN ucks_chunks c ON c.id=e.chunk_id JOIN ucks_documents d ON d.id=c.document_id
                JOIN ucks_sources s ON s.id=d.source_id
                WHERE e.provider=? AND e.model=?""", (provider.name, provider.model)).fetchall()
        ranked = []
        for row in rows:
            item = dict(row)
            score = cosine(query_vector, unpack_vector(item.pop("vector_blob"), item.pop("dimensions")))
            item["score"] = score
            ranked.append(item)
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:max(1, min(limit, 50))]


    LIFECYCLE_STATES = {"current", "superseded", "corrected", "retracted"}

    def revise_document(self, document_id: str, *, title: str, body: str,
                        provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a new immutable version and supersede the previous version."""
        if not title.strip() or not body.strip():
            raise ValueError("Document title and body are required")
        original = self.get_document(document_id)
        if not original:
            raise ValueError("Unknown UCKS document")
        digest = _hash(body)
        now = _now()
        chunks = self._chunk(body)
        with self.store.transaction() as conn:
            current = conn.execute("SELECT current_version,content_hash FROM ucks_documents WHERE id=?",
                                   (document_id,)).fetchone()
            if current["content_hash"] == digest:
                return self.get_document(document_id)
            version = int(current["current_version"]) + 1
            conn.execute("""INSERT INTO ucks_document_versions
                (id,document_id,version,body,content_hash,created_at) VALUES(?,?,?,?,?,?)""",
                (_id("ver"), document_id, version, body, digest, now))
            for ordinal, chunk in enumerate(chunks):
                chunk_id = _id("chk")
                conn.execute("""INSERT INTO ucks_chunks
                    (id,document_id,version,ordinal,heading,body,token_estimate,metadata_json,content_hash,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (chunk_id, document_id, version, ordinal, "", chunk, max(1, len(chunk.split())),
                     "{}", _hash(chunk), now))
                conn.execute("INSERT INTO ucks_chunks_fts(chunk_id,title,heading,body) VALUES(?,?,?,?)",
                             (chunk_id, title.strip(), "", chunk))
            conn.execute("""UPDATE ucks_documents SET title=?,current_version=?,content_hash=?,
                provenance_json=?,updated_at=? WHERE id=?""",
                (title.strip(), version, digest, json.dumps(provenance or original["provenance"], ensure_ascii=False),
                 now, document_id))
        return self.get_document(document_id)

    def set_lifecycle_state(self, document_id: str, state: str, *,
                            superseding_document_id: str = "") -> dict[str, Any]:
        if state not in self.LIFECYCLE_STATES:
            raise ValueError("Unsupported lifecycle state")
        if not self.get_document(document_id):
            raise ValueError("Unknown UCKS document")
        if state == "superseded" and superseding_document_id:
            replacement = self.get_document(superseding_document_id)
            if not replacement or replacement["id"] == document_id:
                raise ValueError("Invalid superseding document")
        elif superseding_document_id:
            raise ValueError("A superseding document is only valid for superseded records")
        with self.store.transaction() as conn:
            conn.execute("""UPDATE ucks_documents SET lifecycle_state=?,supersedes_document_id=?,updated_at=?
                WHERE id=?""", (state, superseding_document_id, _now(), document_id))
        return self.get_document(document_id)

    def lifecycle_queue(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT id,title,source_id,source_url,review_status,lifecycle_state,
                supersedes_document_id,publication_date,updated_at FROM ucks_documents
                WHERE lifecycle_state!='current' ORDER BY updated_at DESC LIMIT ?""",
                (max(1, min(limit, 500)),)).fetchall()
        return [dict(row) for row in rows]

    def feed_state(self, source_id: str) -> dict[str, Any]:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_feed_state WHERE source_id=?", (source_id,)).fetchone()
        return dict(row) if row else {"source_id": source_id, "etag": "", "last_modified": ""}

    def update_feed_state(self, source_id: str, *, etag: str = "", last_modified: str = "",
                          status: str = "", error: str = "") -> None:
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO ucks_feed_state
                (source_id,etag,last_modified,last_checked,last_status,last_error)
                VALUES(?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
                etag=excluded.etag,last_modified=excluded.last_modified,
                last_checked=excluded.last_checked,last_status=excluded.last_status,
                last_error=excluded.last_error""",
                (source_id, etag, last_modified, _now(), status, error[:1000]))

    def configure_feed_schedule(self, source_id: str, *, enabled: bool, interval_minutes: int = 360) -> dict[str, Any]:
        source = self.get_source(source_id)
        if not source or source.get("source_type") != "online_feed":
            raise ValueError("A registered online_feed source is required")
        interval = max(15, min(int(interval_minutes), 10080))
        now = datetime.now(timezone.utc)
        next_run = now.isoformat(timespec="seconds") if enabled else ""
        with self.store.transaction() as conn:
            conn.execute("""INSERT INTO ucks_feed_schedule(source_id,enabled,interval_minutes,next_run,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET enabled=excluded.enabled,
                interval_minutes=excluded.interval_minutes,next_run=excluded.next_run,lease_until='',updated_at=excluded.updated_at""",
                (source_id, int(enabled), interval, next_run, _now()))
        return self.feed_schedule(source_id)

    def feed_schedule(self, source_id: str) -> dict[str, Any]:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_feed_schedule WHERE source_id=?", (source_id,)).fetchone()
        return dict(row) if row else {"source_id": source_id, "enabled": 0, "interval_minutes": 360, "next_run": ""}

    def feed_health(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT s.id AS source_id,s.name,s.enabled AS source_enabled,
                fs.enabled AS schedule_enabled,fs.interval_minutes,fs.next_run,fs.last_attempt,
                fs.consecutive_failures,fs.last_duration_ms,st.last_status,st.last_checked,st.last_error
                FROM ucks_sources s LEFT JOIN ucks_feed_schedule fs ON fs.source_id=s.id
                LEFT JOIN ucks_feed_state st ON st.source_id=s.id WHERE s.source_type='online_feed'
                ORDER BY s.name LIMIT ?""", (max(1,min(limit,500)),)).fetchall()
        return [dict(r) for r in rows]

    def claim_due_feeds(self, *, lease_seconds: int = 180, limit: int = 20) -> list[str]:
        now = datetime.now(timezone.utc)
        now_s = now.isoformat(timespec="seconds")
        lease = (now + timedelta(seconds=max(30, min(lease_seconds, 900)))).isoformat(timespec="seconds")
        with self.store.transaction() as conn:
            rows = conn.execute("""SELECT fs.source_id FROM ucks_feed_schedule fs
                JOIN ucks_sources src ON src.id=fs.source_id
                WHERE fs.enabled=1 AND src.enabled=1 AND fs.next_run!='' AND fs.next_run<=?
                AND (fs.lease_until='' OR fs.lease_until<?)
                ORDER BY fs.next_run LIMIT ?""", (now_s, now_s, max(1,min(limit,100)))).fetchall()
            ids = [r["source_id"] for r in rows]
            for source_id in ids:
                conn.execute("UPDATE ucks_feed_schedule SET lease_until=?,last_attempt=?,updated_at=? WHERE source_id=?",
                             (lease, now_s, now_s, source_id))
        return ids

    def complete_feed_schedule(self, source_id: str, *, outcome: str, records_seen: int = 0,
                               records_added: int = 0, error: str = "", duration_ms: int = 0) -> dict[str, Any]:
        if outcome not in {"ok", "not_modified", "error"}:
            raise ValueError("Unsupported feed outcome")
        now = datetime.now(timezone.utc)
        now_s = now.isoformat(timespec="seconds")
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_feed_schedule WHERE source_id=?", (source_id,)).fetchone()
            if not row:
                raise ValueError("Feed schedule not found")
            failures = int(row["consecutive_failures"] or 0) + 1 if outcome == "error" else 0
            interval = int(row["interval_minutes"])
            delay = min(interval * (2 ** min(failures, 8)), 1440) if outcome == "error" else interval
            next_run = (now + timedelta(minutes=delay)).isoformat(timespec="seconds") if row["enabled"] else ""
            conn.execute("""UPDATE ucks_feed_schedule SET next_run=?,lease_until='',consecutive_failures=?,
                last_duration_ms=?,updated_at=? WHERE source_id=?""",
                (next_run, failures, max(0,int(duration_ms)), now_s, source_id))
            conn.execute("""INSERT INTO ucks_feed_audit(id,source_id,outcome,records_seen,records_added,error,
                started_at,completed_at,duration_ms) VALUES(?,?,?,?,?,?,?,?,?)""",
                (_id("feedrun"),source_id,outcome,max(0,int(records_seen)),max(0,int(records_added)),
                 error[:1000],row["last_attempt"] or now_s,now_s,max(0,int(duration_ms))))
        return self.feed_schedule(source_id)

    def feed_audit(self, *, source_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self.store.transaction() as conn:
            if source_id:
                rows = conn.execute("SELECT * FROM ucks_feed_audit WHERE source_id=? ORDER BY started_at DESC LIMIT ?",
                                    (source_id,max(1,min(limit,500)))).fetchall()
            else:
                rows = conn.execute("SELECT * FROM ucks_feed_audit ORDER BY started_at DESC LIMIT ?",
                                    (max(1,min(limit,500)),)).fetchall()
        return [dict(r) for r in rows]

    GRAPH_NODE_TYPES = {"condition", "symptom", "finding", "investigation", "treatment", "drug", "procedure", "complication", "specialty", "anatomy", "organism", "case", "evidence"}
    GRAPH_PREDICATES = {"presents_with", "associated_with", "investigated_by", "treated_with", "causes", "complicated_by", "contraindicated_in", "located_in", "classified_as", "supported_by", "differential_for"}

    def upsert_graph_node(self, *, label: str, node_type: str, terminology_system: str = "", terminology_code: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        label = label.strip()
        if not label or len(label) > 300 or node_type not in self.GRAPH_NODE_TYPES:
            raise ValueError("A valid graph label and supported node_type are required")
        with self.store.transaction() as conn:
            row = conn.execute("SELECT id FROM ucks_graph_nodes WHERE node_type=? AND terminology_system=? AND terminology_code=? AND label=?", (node_type, terminology_system, terminology_code, label)).fetchone()
            if row:
                node_id = row["id"]
                conn.execute("UPDATE ucks_graph_nodes SET metadata_json=? WHERE id=?", (json.dumps(metadata or {}, ensure_ascii=False), node_id))
            else:
                node_id = _id("kn")
                conn.execute("INSERT INTO ucks_graph_nodes(id,label,node_type,terminology_system,terminology_code,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)", (node_id,label,node_type,terminology_system,terminology_code,json.dumps(metadata or {},ensure_ascii=False),_now()))
            result = conn.execute("SELECT * FROM ucks_graph_nodes WHERE id=?", (node_id,)).fetchone()
        item = dict(result); item["metadata"] = json.loads(item.pop("metadata_json")); return item

    def add_graph_edge(self, *, subject_id: str, predicate: str, object_id: str, document_id: str = "", evidence_note: str = "") -> dict[str, Any]:
        if predicate not in self.GRAPH_PREDICATES or subject_id == object_id:
            raise ValueError("Unsupported relationship or self-referential edge")
        with self.store.transaction() as conn:
            if not conn.execute("SELECT 1 FROM ucks_graph_nodes WHERE id=?", (subject_id,)).fetchone() or not conn.execute("SELECT 1 FROM ucks_graph_nodes WHERE id=?", (object_id,)).fetchone():
                raise ValueError("Unknown graph node")
            if document_id and not conn.execute("SELECT 1 FROM ucks_documents WHERE id=?", (document_id,)).fetchone():
                raise ValueError("Unknown evidence document")
            edge_id = _id("ke")
            conn.execute("INSERT OR IGNORE INTO ucks_graph_edges(id,subject_id,predicate,object_id,document_id,evidence_note,created_at) VALUES(?,?,?,?,?,?,?)", (edge_id,subject_id,predicate,object_id,document_id,evidence_note[:1000],_now()))
            row = conn.execute("SELECT * FROM ucks_graph_edges WHERE subject_id=? AND predicate=? AND object_id=? AND document_id=?", (subject_id,predicate,object_id,document_id)).fetchone()
        return dict(row)

    def graph_neighbours(self, node_id: str, *, depth: int = 1, limit: int = 100) -> dict[str, Any]:
        depth = max(1, min(depth, 3)); limit = max(1, min(limit, 200))
        with self.store.transaction() as conn:
            start = conn.execute("SELECT * FROM ucks_graph_nodes WHERE id=?", (node_id,)).fetchone()
            if not start: raise ValueError("Unknown graph node")
            seen = {node_id}; frontier = [node_id]; nodes = [dict(start)]; edges = []
            for _ in range(depth):
                if not frontier or len(edges) >= limit: break
                marks = ",".join("?" for _ in frontier)
                rows = conn.execute(f"SELECT * FROM ucks_graph_edges WHERE subject_id IN ({marks}) OR object_id IN ({marks}) LIMIT ?", (*frontier,*frontier,limit-len(edges))).fetchall()
                frontier_next = []
                for edge in rows:
                    e = dict(edge); edges.append(e)
                    other = e["object_id"] if e["subject_id"] in frontier else e["subject_id"]
                    if other not in seen:
                        seen.add(other); frontier_next.append(other)
                if frontier_next:
                    marks2 = ",".join("?" for _ in frontier_next)
                    nodes.extend(dict(r) for r in conn.execute(f"SELECT * FROM ucks_graph_nodes WHERE id IN ({marks2})", frontier_next).fetchall())
                frontier = frontier_next
        for node in nodes: node["metadata"] = json.loads(node.pop("metadata_json"))
        return {"nodes": nodes, "edges": edges, "depth": depth}

    def search_graph_nodes(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        terms = [x for x in re.findall(r"[\w-]+", query) if len(x) > 1]
        if not terms: return []
        where = " AND ".join("lower(label) LIKE ?" for _ in terms)
        with self.store.transaction() as conn:
            rows = conn.execute(f"SELECT * FROM ucks_graph_nodes WHERE {where} ORDER BY label LIMIT ?", (*[f"%{x.lower()}%" for x in terms], max(1,min(limit,100)))).fetchall()
        result=[]
        for row in rows:
            item=dict(row); item["metadata"]=json.loads(item.pop("metadata_json")); result.append(item)
        return result

    def stats(self) -> dict[str, Any]:
        with self.store.transaction() as conn:
            def count(table: str) -> int:
                return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            return {
                "sources": count("ucks_sources"), "documents": count("ucks_documents"),
                "versions": count("ucks_document_versions"), "chunks": count("ucks_chunks"),
                "embeddings": count("ucks_embeddings"), "ingestion_jobs": count("ucks_ingestion_jobs"),
                "online_feeds": count("ucks_feed_state"),
                "scheduled_online_feeds": int(conn.execute("SELECT COUNT(*) FROM ucks_feed_schedule WHERE enabled=1").fetchone()[0]),
                "feed_sync_audit_entries": count("ucks_feed_audit"),
                "knowledge_graph_nodes": count("ucks_graph_nodes"), "knowledge_graph_edges": count("ucks_graph_edges"),
                "entity_proposals": count("ucks_entity_proposals"),
                "relationship_proposals": count("ucks_relationship_proposals"),
                "legacy_embedding_rows": count("ucks_embeddings"),
                "vector_status": "available" if count("ucks_embeddings") else "not_indexed",
                "retrieval_modes": ["full_text", "vector"] if count("ucks_embeddings") else ["full_text"],
            }
