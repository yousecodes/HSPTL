"""Shared rate-limited HTTP transport for clinical literature providers."""
from __future__ import annotations
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
DOAJ_URL = "https://doaj.org/api/search/articles"
CROSSREF_URL = "https://api.crossref.org/works"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UA = "Mozilla/5.0 (compatible; HSPTL-Clinical-Knowledge-Harvester/1.0; research use)"
NCBI_API_KEY = ""

class FetchError(Exception):
    """A bounded provider request failed after retry policy was applied."""

class RateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval=1.0/max(requests_per_second,0.1)
        self.lock=threading.Lock(); self.last=0.0
    def wait(self):
        with self.lock:
            now=time.monotonic(); delta=self.last+self.min_interval-now
            if delta>0: time.sleep(delta)
            self.last=time.monotonic()

_NCBI_LIMITER=RateLimiter(3)
_EPMC_LIMITER=RateLimiter(4)

def configure_ncbi_api_key(value: str = ""):
    global NCBI_API_KEY, _NCBI_LIMITER
    NCBI_API_KEY=str(value or "").strip()
    _NCBI_LIMITER=RateLimiter(9 if NCBI_API_KEY else 3)

def http_get(url, retries=4, timeout=30, accept=None):
    last=""; headers={"User-Agent":UA}
    if accept: headers["Accept"]=accept
    for attempt in range(max(1,min(int(retries),6))):
        try:
            req=urllib.request.Request(url,headers=headers)
            with urllib.request.urlopen(req,timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            last="HTTP "+str(exc.code)
            if exc.code in (400,401,403,404,410): raise FetchError(last+" "+url) from exc
            if exc.code==429: time.sleep(min(30*(attempt+1),120)); continue
        except Exception as exc:
            last=type(exc).__name__
        time.sleep(min(2*2**attempt,30))
    raise FetchError(last+" "+url)

def epmc_get(url, **kwargs):
    _EPMC_LIMITER.wait(); return http_get(url,**kwargs)

def ncbi_get(endpoint, params, timeout=None):
    _NCBI_LIMITER.wait(); values=dict(params)
    if NCBI_API_KEY: values["api_key"]=NCBI_API_KEY
    values.setdefault("tool","hsptl-clinical-knowledge-harvester")
    values.setdefault("email","research@example.org")
    url=NCBI+"/"+endpoint+"?"+urllib.parse.urlencode(values)
    return http_get(url,timeout=timeout) if timeout else http_get(url)

def fetch_page(url):
    try:
        return http_get(url, timeout=30).decode("utf-8", "replace")
    except FetchError:
        return ""
