"""Licence-aware cache for explicitly requested external sources.

Nothing here fetches on its own. A caller supplies a fetcher and the cache
records what was retrieved, when, and under what licence.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

DEFAULT_TTL_HOURS = 24 * 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


class ExternalSourceCache:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def key(url: str, query: str = "") -> str:
        return hashlib.sha256(f"{url}{chr(0)}{query}".encode()).hexdigest()[:32]

    def get(self, cache_key: str) -> dict[str, Any] | None:
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM external_sources WHERE cache_key=?",
                               (cache_key,)).fetchone()
        if row is None or row["expires_at"] < _iso(_now()):
            return None
        return {"cache_key": row["cache_key"], "url": row["url"], "cached": True,
                "fetched_at": row["fetched_at"], "expires_at": row["expires_at"],
                "open_access": bool(row["open_access"]), "license": row["license"],
                "license_url": row["license_url"], "payload": json.loads(row["payload_json"])}

    def put(self, *, url: str, query: str, payload: dict, kind: str = "article",
            open_access: bool = False, license_text: str = "", license_url: str = "",
            ttl_hours: int = DEFAULT_TTL_HOURS) -> dict[str, Any]:
        cache_key = self.key(url, query)
        blob = json.dumps(payload, ensure_ascii=False)
        with self.store.transaction() as conn:
            conn.execute(
                "INSERT INTO external_sources (cache_key,url,query,kind,open_access,license,"
                "license_url,payload_json,payload_hash,fetched_at,expires_at,status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,'ok') ON CONFLICT(cache_key) DO UPDATE SET "
                "payload_json=excluded.payload_json, payload_hash=excluded.payload_hash, "
                "fetched_at=excluded.fetched_at, expires_at=excluded.expires_at, "
                "license=excluded.license, license_url=excluded.license_url",
                (cache_key, url[:800], query[:300], kind, int(open_access), license_text[:200],
                 license_url[:400], blob, hashlib.sha256(blob.encode()).hexdigest(),
                 _iso(_now()), _iso(_now() + timedelta(hours=ttl_hours))))
        return {"cache_key": cache_key, "url": url, "cached": False, "fetched_at": _iso(_now()),
                "open_access": open_access, "license": license_text, "payload": payload}

    def get_or_fetch(self, *, url: str, query: str, fetcher: Callable[[], dict],
                     kind: str = "article", open_access: bool = False,
                     license_text: str = "", license_url: str = "") -> dict[str, Any]:
        cached = self.get(self.key(url, query))
        if cached:
            return cached
        return self.put(url=url, query=query, payload=fetcher(), kind=kind,
                        open_access=open_access, license_text=license_text,
                        license_url=license_url)
