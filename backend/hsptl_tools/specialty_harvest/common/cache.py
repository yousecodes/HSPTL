"""Persistent metadata caches used by provider acquisition services."""
from __future__ import annotations
import json
from . import http

def load_caches(unpaywall_path, metadata_path, up_cache, meta_cache):
    loaded_up={}; loaded_meta={}
    for path, target in ((unpaywall_path,"up"),(metadata_path,"meta")):
        if path.exists():
            try:
                data=json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data,dict):
                    if target=="up": loaded_up=data
                    else: loaded_meta=data
            except (OSError,ValueError,TypeError):
                continue
    with up_cache[1]: up_cache[0].clear(); up_cache[0].update(loaded_up)
    with meta_cache[1]: meta_cache[0].clear(); meta_cache[0].update(loaded_meta)

def save_caches(cache_dir, unpaywall_path, metadata_path, up_cache, meta_cache):
    cache_dir.mkdir(parents=True,exist_ok=True)
    for path, cache in ((unpaywall_path,up_cache),(metadata_path,meta_cache)):
        try:
            with cache[1]: snapshot=dict(cache[0])
            path.write_text(json.dumps(snapshot,ensure_ascii=False),encoding="utf-8")
        except OSError:
            continue

def unpaywall_resolve(doi,email,endpoint,cache,http_get):
    if not doi or not email: return None
    import urllib.parse
    key=doi.lower().strip()
    with cache[1]:
        if key in cache[0]: return cache[0][key] or None
    url=endpoint+"/"+urllib.parse.quote(key)+"?email="+urllib.parse.quote(email)
    try: data=json.loads(http_get(url,accept="application/json"))
    except Exception:
        with cache[1]: cache[0][key]=None
        return None
    record=None
    if data.get("is_oa"):
        best=data.get("best_oa_location") or {}
        record={"url":best.get("url_for_landing_page") or best.get("url"),"pdf":best.get("url_for_pdf")}
    with cache[1]: cache[0][key]=record
    return record
