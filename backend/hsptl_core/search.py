"""Faceted, injection-safe local search over the study library."""
from __future__ import annotations

import re
from typing import Any

MAX_TERMS = 12
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
FACET_COLUMNS = (("category", "category"), ("note_type", "note_type"),
                 ("specialty", "specialty"), ("jurisdiction", "jurisdiction"),
                 ("provenance_status", "provenance"), ("review_status", "review_status"))


def build_match_query(raw: str, *, prefix_last: bool = True) -> str:
    """Quote user terms into an FTS5 AND query. No raw operators pass through."""
    terms = TOKEN.findall(str(raw or ""))[:MAX_TERMS]
    parts = []
    for index, term in enumerate(terms):
        escaped = term.replace('"', '""')
        suffix = "*" if prefix_last and index == len(terms) - 1 and len(term) >= 3 else ""
        parts.append(f'"{escaped}"{suffix}')
    return " AND ".join(parts)


class SearchService:
    def __init__(self, store):
        self.store = store

    def search(self, query: str, *, facets: dict[str, Any] | None = None,
               limit: int = 30, offset: int = 0) -> dict[str, Any]:
        query = " ".join(str(query or "").split())[:300]
        limit, offset = max(1, min(int(limit), 100)), max(0, int(offset))
        facets = facets or {}
        where, params = [], []
        for column, key in FACET_COLUMNS:
            if facets.get(key):
                where.append(f"n.{column}=?")
                params.append(str(facets[key]))
        if facets.get("has_sources"):
            where.append("n.has_sources=1")
        if facets.get("reviewed_before"):
            where.append("(n.review_date='' OR n.review_date<?)")
            params.append(str(facets["reviewed_before"]))
        with self.store.transaction() as conn:
            if self.store.fts_available and query:
                clause = " AND ".join(["study_notes_fts MATCH ?", *where])
                rows = conn.execute(
                    "SELECT n.*, bm25(study_notes_fts) AS rank, "
                    "snippet(study_notes_fts, 1, '[', ']', '...', 18) AS excerpt "
                    "FROM study_notes_fts f JOIN study_notes n ON n.rowid=f.rowid "
                    f"WHERE {clause} ORDER BY rank LIMIT ? OFFSET ?",
                    [build_match_query(query), *params, limit, offset]).fetchall()
            else:
                if query:
                    like = f"%{query}%"
                    where.insert(0, "(n.title LIKE ? OR n.body LIKE ? OR n.source LIKE ?)")
                    params = [like, like, like, *params]
                clause = " AND ".join(where) if where else "1=1"
                rows = conn.execute(
                    "SELECT n.*, 0 AS rank, substr(n.body,1,320) AS excerpt FROM study_notes n "
                    f"WHERE {clause} ORDER BY n.updated_at DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset]).fetchall()
            available: dict[str, list[str]] = {}
            for column, key in FACET_COLUMNS:
                available[key] = [r["v"] for r in conn.execute(
                    f"SELECT DISTINCT {column} v FROM study_notes WHERE {column}<>'' ORDER BY v")]
        return {"query": query,
                "engine": "sqlite_fts5" if self.store.fts_available else "sqlite_like_fallback",
                "available_facets": available, "applied_facets": facets,
                "results": [{
                    "id": r["id"], "category": r["category"], "title": r["title"],
                    "note_type": r["note_type"], "specialty": r["specialty"],
                    "jurisdiction": r["jurisdiction"], "provenance_status": r["provenance_status"],
                    "review_status": r["review_status"], "review_date": r["review_date"],
                    "updated_at": r["updated_at"], "version": r["version"],
                    "excerpt": r["excerpt"], "origin_episode_id": r["origin_episode_id"],
                } for r in rows]}
