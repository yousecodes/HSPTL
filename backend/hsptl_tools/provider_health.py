"""Bounded provider probes with persisted history and conservative alerting."""
from __future__ import annotations
import time
import requests

PROVIDERS = {
    "europe_pmc": {"label": "Europe PMC", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "params": {"query": "EXT_ID:PMC1", "format": "json", "pageSize": 1}},
    "pubmed": {"label": "PubMed E-utilities", "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", "params": {"db": "pubmed", "term": "cancer", "retmax": 0, "retmode": "json"}},
    "crossref": {"label": "Crossref", "url": "https://api.crossref.org/works", "params": {"rows": 0}},
    "clinicaltrials_gov": {"label": "ClinicalTrials.gov", "url": "https://clinicaltrials.gov/api/v2/studies", "params": {"pageSize": 1}},
    "doaj": {"label": "DOAJ", "url": "https://doaj.org/api/search/articles", "params": {"page": 1, "pageSize": 1}},
    "unpaywall": {"label": "Unpaywall", "url": "https://api.unpaywall.org/v2/10.1038/sdata.2016.18", "params": {"email": "health-check@example.org"}},
}


def initialise_provider_health(store) -> None:
    with store.transaction() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS hsptl_provider_health (
            provider_id TEXT PRIMARY KEY, status TEXT NOT NULL, http_status INTEGER,
            latency_ms INTEGER, checked_at TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS hsptl_provider_health_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, provider_id TEXT NOT NULL, status TEXT NOT NULL,
            http_status INTEGER, latency_ms INTEGER, checked_at TEXT NOT NULL,
            error_code TEXT NOT NULL DEFAULT '')""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_health_history ON hsptl_provider_health_history(provider_id,id DESC)")


def record_provider_health(store, provider_id: str, *, status: str, http_status=None,
                           latency_ms=None, error_code="") -> None:
    if provider_id not in PROVIDERS or status not in {"healthy", "degraded", "unhealthy"}:
        raise ValueError("Invalid provider health observation")
    initialise_provider_health(store)
    with store.transaction() as conn:
        conn.execute("""INSERT INTO hsptl_provider_health(provider_id,status,http_status,latency_ms,checked_at,error_code)
            VALUES(?,?,?, ?,datetime('now'),?) ON CONFLICT(provider_id) DO UPDATE SET
            status=excluded.status,http_status=excluded.http_status,latency_ms=excluded.latency_ms,
            checked_at=excluded.checked_at,error_code=excluded.error_code""",
            (provider_id,status,http_status,latency_ms,error_code))
        conn.execute("""INSERT INTO hsptl_provider_health_history(provider_id,status,http_status,latency_ms,checked_at,error_code)
            VALUES(?,?,?,?,datetime('now'),?)""", (provider_id,status,http_status,latency_ms,error_code))
        conn.execute("""DELETE FROM hsptl_provider_health_history WHERE provider_id=? AND id NOT IN
            (SELECT id FROM hsptl_provider_health_history WHERE provider_id=? ORDER BY id DESC LIMIT 100)""",
            (provider_id,provider_id))


def get_provider_health_history(store, *, provider_id: str = "", limit: int = 50) -> dict:
    initialise_provider_health(store)
    limit=max(1,min(int(limit),200))
    if provider_id and provider_id not in PROVIDERS:
        raise ValueError("Unknown provider")
    with store.transaction() as conn:
        if provider_id:
            rows=[dict(r) for r in conn.execute("SELECT * FROM hsptl_provider_health_history WHERE provider_id=? ORDER BY id DESC LIMIT ?",(provider_id,limit))]
        else:
            rows=[dict(r) for r in conn.execute("SELECT * FROM hsptl_provider_health_history ORDER BY id DESC LIMIT ?",(limit,))]
    return {"items":rows,"limit":limit}


def get_provider_health(store, *, probe: bool = False) -> dict:
    initialise_provider_health(store)
    if probe:
        for provider_id, config in PROVIDERS.items():
            started=time.monotonic(); status="unhealthy"; http_status=None; error_code=""
            try:
                response=requests.get(config["url"],params=config["params"],timeout=(2,3),
                    allow_redirects=False,headers={"User-Agent":"HSPTL-Clinical-Knowledge-Harvester/1.0"})
                http_status=int(response.status_code)
                status="healthy" if 200 <= response.status_code < 300 else ("degraded" if response.status_code in {429,500,502,503,504} else "unhealthy")
                if response.status_code >= 400: error_code=f"HTTP_{response.status_code}"
                response.close()
            except requests.Timeout:
                error_code="timeout"
            except requests.RequestException as exc:
                error_code=type(exc).__name__
            record_provider_health(store,provider_id,status=status,http_status=http_status,
                latency_ms=int((time.monotonic()-started)*1000),error_code=error_code)
    with store.transaction() as conn:
        rows={r["provider_id"]:dict(r) for r in conn.execute("SELECT * FROM hsptl_provider_health")}
        history={pid:[r["status"] for r in conn.execute("SELECT status FROM hsptl_provider_health_history WHERE provider_id=? ORDER BY id DESC LIMIT 3",(pid,))] for pid in PROVIDERS}
    items=[]; alerts=[]
    for provider_id,config in PROVIDERS.items():
        saved=rows.get(provider_id); observations=history.get(provider_id,[])
        consecutive_bad=0
        for value in observations:
            if value in {"degraded","unhealthy"}: consecutive_bad+=1
            else: break
        alert = "repeated_provider_failure" if consecutive_bad >= 2 else ("provider_unhealthy" if saved and saved["status"]=="unhealthy" else "")
        if alert: alerts.append({"provider_id":provider_id,"severity":"warning" if consecutive_bad < 2 else "high","code":alert,"consecutive_nonhealthy":consecutive_bad})
        items.append({"id":provider_id,"name":config["label"],"endpoint":config["url"],
            "status":saved["status"] if saved else "not_probed","http_status":saved["http_status"] if saved else None,
            "latency_ms":saved["latency_ms"] if saved else None,"checked_at":saved["checked_at"] if saved else "",
            "error_code":saved["error_code"] if saved else "","recent_statuses":observations,"alert":alert})
    return {"items":items,"alerts":alerts,"probed":bool(probe),
        "probe_policy":"fixed allow-listed HTTPS endpoints; 2s connect/3s read timeout; redirects disabled",
        "interpretation":"Endpoint reachability only; does not establish query coverage, metadata quality, full-text availability or licensing."}
