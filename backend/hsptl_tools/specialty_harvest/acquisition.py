"""Clinical article acquisition, JATS resolution and batch download services."""
from __future__ import annotations
from . import engine as _engine

CROSSREF = getattr(_engine, 'CROSSREF')
EPMC = getattr(_engine, 'EPMC')
ET = getattr(_engine, 'ET')
FetchError = getattr(_engine, 'FetchError')
HINDAWI_JOURNAL_CODES = getattr(_engine, 'HINDAWI_JOURNAL_CODES')
ThreadPoolExecutor = getattr(_engine, 'ThreadPoolExecutor')
UA = getattr(_engine, 'UA')
_META_CACHE = getattr(_engine, '_META_CACHE')
_META_CACHE_LOCK = getattr(_engine, '_META_CACHE_LOCK')
_html_to_jats = getattr(_engine, '_html_to_jats')
as_completed = getattr(_engine, 'as_completed')
epmc_get = getattr(_engine, 'epmc_get')
extract_jats_license = getattr(_engine, 'extract_jats_license')
http_get = getattr(_engine, 'http_get')
json = getattr(_engine, 'json')
ncbi_get = getattr(_engine, 'ncbi_get')
re = getattr(_engine, 're')
threading = getattr(_engine, 'threading')
time = getattr(_engine, 'time')
unpaywall_resolve = getattr(_engine, 'unpaywall_resolve')
urllib = getattr(_engine, 'urllib')

def _epmc_lookup(ids, id_type, chunk=50, workers=4, label=""):
    out = {}
    ids = list(dict.fromkeys(i for i in ids if i))
    if not ids:
        return out
    chunks = [ids[i:i + chunk] for i in range(0, len(ids), chunk)]
    total = len(chunks)
    lock = threading.Lock()
    done = [0]

    if total > 5:
        print("  [hydrate:" + (label or id_type) + "] " + str(len(ids)) +
              " IDs in " + str(total) + " chunks (" + str(workers) + " workers)",
              flush=True)

    def fetch(batch):
        q = " OR ".join(id_type + ":\"" + x + "\"" for x in batch)
        params = urllib.parse.urlencode({
            "query": q, "format": "json", "resultType": "core",
            "pageSize": min(1000, len(batch) * 2)})
        try:
            data = json.loads(http_get(EPMC + "/search?" + params))
        except FetchError:
            return {}
        result = {}
        for r in data.get("resultList", {}).get("result", []):
            key = (r.get("pmcid") if id_type == "PMCID" else r.get("doi")) or ""
            if key:
                result[key.lower()] = r
        with lock:
            done[0] += 1
            if total > 5 and (done[0] % max(1, total // 5) == 0 or done[0] == total):
                print("    [hydrate:" + (label or id_type) + "] " +
                      str(done[0]) + "/" + str(total) + " chunks", flush=True)
        return result

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fetch, c) for c in chunks]
        for f in as_completed(futs):
            try:
                out.update(f.result())
            except Exception:
                pass
    return out

def hydrate_candidates(cands, chunk=50):
    need = []
    cached = []
    with _META_CACHE_LOCK:
        for c in cands:
            if not (c.title and (c.pmcid or c.doi or c.pmid)):
                need.append(c)
                continue
            ck = (c.pmcid or "").lower() if c.pmcid else ("doi:" + c.doi.lower() if c.doi else "pmid:" + c.pmid.lower())
            if ck in _META_CACHE:
                r = _META_CACHE[ck]
                c.abstract = r.get("abstractText") or c.abstract
                c.year = str(r.get("pubYear") or c.year)
                c.journal = r.get("journalTitle") or c.journal
                pubtypes = (r.get("pubTypeList") or {}).get("pubType", [])
                if isinstance(pubtypes, str): pubtypes = [pubtypes]
                c.publication_type = c.publication_type or ", ".join(str(x) for x in pubtypes)
                cached.append(c)
            else:
                need.append(c)
    if not need:
        return cached
    pmc_ids = [c.pmcid for c in need if c.pmcid]
    doi_ids = [c.doi for c in need if not c.pmcid and c.doi]
    print("  [hydrate] " + str(len(need)) + " candidates need metadata (" +
          str(len(pmc_ids)) + " by PMCID, " + str(len(doi_ids)) + " by DOI)",
          flush=True)
    pmc_meta = _epmc_lookup(pmc_ids, "PMCID", chunk, label="PMCID")
    doi_meta = _epmc_lookup(doi_ids, "DOI", chunk, label="DOI")
    hydrated = list(cached)
    for c in need:
        r = None
        if c.pmcid:
            r = pmc_meta.get(c.pmcid.lower())
        if r is None and c.doi:
            r = doi_meta.get(c.doi.lower())
        if r is not None:
            c.pmcid = r.get("pmcid") or c.pmcid
            c.doi = (r.get("doi") or c.doi).lower()
            c.title = r.get("title") or c.title
            c.abstract = r.get("abstractText") or c.abstract
            c.year = str(r.get("pubYear") or c.year)
            c.journal = r.get("journalTitle") or c.journal
            pubtypes = (r.get("pubTypeList") or {}).get("pubType", [])
            if isinstance(pubtypes, str): pubtypes = [pubtypes]
            c.publication_type = c.publication_type or ", ".join(str(x) for x in pubtypes)
            ck = (c.pmcid or "").lower() if c.pmcid else ("doi:" + c.doi.lower() if c.doi else "pmid:" + c.pmid.lower())
            with _META_CACHE_LOCK:
                _META_CACHE[ck] = r
        if c.title and (c.pmcid or c.doi or c.pmid):
            hydrated.append(c)
    return hydrated

def _try_pmc_html(pmcid, delay):
    """Fetch PMC HTML page and convert to JATS (third fallback)."""
    url = "https://pmc.ncbi.nlm.nih.gov/articles/" + pmcid + "/"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=45) as r:
            html_bytes = r.read()
    except Exception:
        return None
    if delay:
        time.sleep(delay)
    if len(html_bytes) < 2000:
        return None
    if _is_cloudflare_challenge(html_bytes):
        return None
    jats = _html_to_jats(html_bytes, doi_hint="", url_hint=url)
    if jats and b"<sec" in jats:
        return jats
    return None

def resolve_pmcid_to_jats(pmcid, delay, pmc_fallback=True):
    """Try EPMC, NCBI efetch, then PMC HTML page (3 fallbacks)."""
    try:
        xml = epmc_get(EPMC + "/" + pmcid + "/fullTextXML", timeout=60)
        if b"<body" in xml:
            return xml
    except FetchError:
        pass
    if pmc_fallback:
        try:
            uid = pmcid.upper().replace("PMC", "")
            xml = ncbi_get("efetch.fcgi", {"db": "pmc", "id": uid, "retmode": "xml"}, timeout=60)
            if b"<body" in xml:
                return xml
        except FetchError:
            pass
    jats = _try_pmc_html(pmcid, delay)
    if jats:
        return jats
    return None

def _looks_like_jats(data):
    """True if data looks like a JATS article."""
    if not data or len(data) < 200:
        return False
    head = data[:500].lstrip()
    if head.startswith(b"<!DOCTYPE html") or head.startswith(b"<html"):
        return False
    text_lower = data[:2000].lower()
    return b"<article" in text_lower and (b"<body" in text_lower or b"<sec" in text_lower)

def _is_cloudflare_challenge(data):
    """True if data is a Cloudflare challenge page."""
    if not data:
        return False
    head = data[:2000].lower()
    for marker in (b"__cf_chl", b"cf-browser-verification", b"just a moment", b"attention required"):
        if marker in head:
            return True
    return False

def _parse_hindawi_doi(doi):
    """Parse Hindawi DOI -> (year, article_id) or None."""
    m = re.match(r"^10\.1155/(\d{4})/([^/]+)$", doi.strip())
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^10\.1155/([^/]+)$", doi.strip())
    if m:
        return "", m.group(1)
    return None

def _crossref_journal_name(doi):
    """Fetch journal name for a DOI via Crossref."""
    url = CROSSREF + "/" + urllib.parse.quote(doi, safe="/")
    try:
        data = json.loads(http_get(url, timeout=20))
    except (FetchError, json.JSONDecodeError):
        return None
    titles = data.get("message", {}).get("container-title") or []
    return titles[0] if titles else None

def _norm_journal_name(s):
    """Normalise journal name for lookup."""
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def _get_hindawi_journal_codes(journal_name):
    """Return candidate journal codes for a journal name."""
    key = _norm_journal_name(journal_name)
    if key in HINDAWI_JOURNAL_CODES:
        return list(HINDAWI_JOURNAL_CODES[key])
    words = [w for w in key.split() if w not in {"of", "the", "and", "for", "in"}]
    if words:
        initials = "".join(w[0] for w in words)
        return [initials, initials[:5]]
    return []

def _try_hindawi_constructed(doi, delay):
    """Try downloads.hindawi.com/journals/{code}/{year}/{id}.xml."""
    parsed = _parse_hindawi_doi(doi)
    if not parsed:
        return None
    year, article_id = parsed
    journal = _crossref_journal_name(doi)
    codes = _get_hindawi_journal_codes(journal) if journal else []
    for fallback in ("criopm", "jop", "joph", "crim", "crneurol", "crgastro"):
        if fallback not in codes:
            codes.append(fallback)
    if not codes:
        return None
    for code in codes:
        if not code:
            continue
        if year:
            urls = ['https://downloads.hindawi.com/journals/' + code + '/' + year + '/' + article_id + '.xml']
        else:
            urls = []
            for y in range(2024, 2009, -1):
                urls.append('https://downloads.hindawi.com/journals/' + code + '/' + str(y) + '/' + article_id + '.xml')
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA,
                    "Accept": "application/xml,text/xml,*/*",
                    "Referer": "https://www.hindawi.com/"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
            except Exception:
                continue
            time.sleep(delay)
            if _is_cloudflare_challenge(data):
                continue
            if not _looks_like_jats(data):
                continue
            doi_bytes = doi.encode()
            if doi_bytes in data[:5000] or doi_bytes in data[-5000:]:
                return data
            if article_id.encode() in data[:5000]:
                return data
    return None

def _doi_to_pmcid(doi):
    """Convert DOI to PMCID via NCBI ID Converter API."""
    url = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
    params = urllib.parse.urlencode({
        "ids": doi, "format": "json",
        "tool": "specialty-harvester", "email": "research@example.org"})
    try:
        data = json.loads(http_get(url + "?" + params, timeout=20))
    except (FetchError, json.JSONDecodeError):
        return None
    records = data.get("records", [])
    if records:
        return records[0].get("pmcid") or None
    return None

def convert_doi_to_jats(doi, delay, unpaywall_email=""):
    """Multi-strategy DOI -> JATS. Constructed Hindawi URL first, HTML fallback."""
    doi = (doi or "").strip()
    if not doi:
        return None
    pmcid = _doi_to_pmcid(doi)
    if pmcid:
        try:
            xml = http_get(EPMC + "/" + pmcid + "/fullTextXML", timeout=45)
            if b"<body" in xml:
                return xml
        except FetchError:
            pass
        time.sleep(delay)
    if doi.startswith("10.1155/"):
        xml = _try_hindawi_constructed(doi, delay)
        if xml:
            return xml
    up = unpaywall_resolve(doi, unpaywall_email) if unpaywall_email else None
    urls = []
    if up and up.get("url"):
        urls.append(up["url"])
    urls.append("https://doi.org/" + doi)
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
            with urllib.request.urlopen(req, timeout=45) as r:
                final_url = r.geturl()
                html_bytes = r.read()
        except Exception:
            continue
        time.sleep(delay)
        jats = _html_to_jats(html_bytes, doi_hint=doi, url_hint=final_url)
        if jats:
            return jats
    return None

def download_candidate(c, folder, delay, pmc_fallback=True, convert_fallback=True,
                       unpaywall_email=""):
    fn = c.folder_name()
    if not fn:
        raise FetchError("no identifier")
    d = folder / fn
    if (d / "article.xml").exists():
        return "skip"
    xml = None
    jats_source = "pmc"
    if c.pmcid:
        xml = resolve_pmcid_to_jats(c.pmcid, delay, pmc_fallback)
    if not xml and convert_fallback and c.doi:
        xml = convert_doi_to_jats(c.doi, delay, unpaywall_email)
        jats_source = "html-converted"
    if not xml:
        raise FetchError("no JATS")
    time.sleep(delay)
    d.mkdir(parents=True, exist_ok=True)
    rights = extract_jats_license(xml)
    from .licensing import reuse_allowlisted
    if not reuse_allowlisted(rights):
        d.mkdir(parents=True, exist_ok=True)
        metadata = {"pmcid": c.pmcid or "", "pmid": c.pmid or "", "doi": c.doi,
            "title": c.title, "abstractText": c.abstract, "year": c.year, "journal": c.journal,
            "publication_type": c.publication_type, "content_type": c.content_type,
            "knowledge_profile": c.knowledge_profile, "discovered_via": c.source,
            "jats_source": "blocked_unverified_rights", "full_text_available": False,
            "provider_license_uri": c.license_uri, **rights,
            "license_uri": rights.get("license_uri") or c.license_uri,
            "license_status": rights.get("license_status") or "unknown_requires_manual_review",
            "review_status": "harvested_unreviewed"}
        (d / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return "metadata_only_rights"
    (d / "article.xml").write_bytes(xml)
    (d / "meta.json").write_text(json.dumps({
        "pmcid": c.pmcid or "", "pmid": c.pmid or "", "doi": c.doi, "title": c.title,
        "abstractText": c.abstract, "year": c.year, "journal": c.journal,
        "publication_type": c.publication_type, "content_type": c.content_type,
        "provider_license_uri": c.license_uri, "license_uri": c.license_uri,
        "license_status": "provider_metadata_requires_verification" if c.license_uri else "unknown_requires_manual_review",
        "knowledge_profile": c.knowledge_profile,
        "discovered_via": c.source, "jats_source": jats_source, "full_text_available": True,
        **rights,
        "license_uri": (rights.get("license_uri") or c.license_uri),
        "license_status": "allowlisted_full_text_pending_human_review",
        "review_status": "harvested_unreviewed"}, ensure_ascii=False))
    return "ok"

def _efetch_batch(pmcids, timeout=180):
    """Fetch JATS for up to 200 PMCIDs in one EFetch call.

    Handles both "123456" and "PMC123456" formats in article-id.
    Reports parse/HTTP errors instead of silently returning {}.
    """
    ids = [p.upper().replace("PMC", "") for p in pmcids]
    try:
        xml = ncbi_get("efetch.fcgi", {
            "db": "pmc", "id": ",".join(ids), "retmode": "xml"}, timeout=timeout)
    except FetchError as e:
        print("    [batch] HTTP error: " + str(e)[:120], flush=True)
        return {}

    if not xml or len(xml) < 100:
        print("    [batch] response too short (" + str(len(xml or b"")) + " bytes)",
              flush=True)
        return {}

    head = xml[:300] if isinstance(xml, bytes) else xml[:300].encode()
    head_stripped = head.lstrip()
    if not head_stripped.startswith(b"<") and b"<?xml" not in head[:200]:
        preview = head.decode("utf-8", "replace")[:150]
        print("    [batch] non-XML response: " + preview, flush=True)
        return {}

    out = {}
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print("    [batch] XML parse error: " + str(e) +
              " (response " + str(len(xml)) + " bytes)", flush=True)
        return {}

    for art in root.iter():
        tag = art.tag if isinstance(art.tag, str) else ""
        if tag.rsplit("}", 1)[-1] != "article":
            continue
        pmcid = None
        for aid in art.iter():
            atag = aid.tag if isinstance(aid.tag, str) else ""
            if atag.rsplit("}", 1)[-1] == "article-id" and aid.get("pub-id-type") == "pmc":
                raw = (aid.text or "").strip()
                if raw.upper().startswith("PMC"):
                    raw = raw[3:]
                pmcid = "PMC" + raw
                break
        if not pmcid:
            continue
        art_xml = ET.tostring(art, encoding="unicode").encode("utf-8")
        if b"<body" not in art_xml:
            continue
        out[pmcid.upper()] = art_xml
    return out

def download_pmc_batch(cands, folder, args, batch_size=200):
    """Download PMC candidates via EPMC + NCBI, with rate limiting and diagnostics."""
    ok = 0
    errs = []
    pending = [c for c in cands if not (folder / c.pmcid / "article.xml").exists()]
    if not pending:
        return 0, 0, []

    total = len(pending)
    workers = getattr(args, "pmc_workers", 4)
    delay = getattr(args, "delay", 0.05)
    print("    [pmc] downloading " + str(total) + " articles (" + str(workers) +
          " workers, " + str(delay) + "s delay)", flush=True)

    error_types = {}
    lock = threading.Lock()
    completed = [0]
    recent_fails = [0]

    def fetch_one(c):
        try:
            xml = resolve_pmcid_to_jats(c.pmcid, delay, pmc_fallback=True)
            if not xml:
                return (c, None, "no-body")
            return (c, xml, None)
        except FetchError as e:
            msg = str(e)[:60]
            if "HTTP 429" in msg or "HTTP 503" in msg:
                return (c, None, "rate-limit")
            return (c, None, "http:" + msg)
        except Exception as e:
            return (c, None, type(e).__name__)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, c): c for c in pending}
        for f in as_completed(futs):
            c, xml, err = f.result()
            if xml:
                d = folder / c.pmcid
                d.mkdir(parents=True, exist_ok=True)
                rights = extract_jats_license(xml)
                from .licensing import reuse_allowlisted
                if not reuse_allowlisted(rights):
                    (d / "meta.json").write_text(json.dumps({
                        "pmcid": c.pmcid, "pmid": c.pmid or "", "doi": c.doi, "title": c.title,
                        "abstractText": c.abstract, "year": c.year, "journal": c.journal,
                        "publication_type": c.publication_type, "content_type": c.content_type,
                        "knowledge_profile": c.knowledge_profile, "discovered_via": c.source,
                        "jats_source": "blocked_unverified_rights", "full_text_available": False,
                        "provider_license_uri": c.license_uri, **rights,
                        "license_uri": rights.get("license_uri") or c.license_uri,
                        "license_status": rights.get("license_status") or "unknown_requires_manual_review",
                        "review_status": "harvested_unreviewed"}, ensure_ascii=False))
                    ok += 1
                else:
                    (d / "article.xml").write_bytes(xml)
                    (d / "meta.json").write_text(json.dumps({
                        "pmcid": c.pmcid, "pmid": c.pmid or "", "doi": c.doi, "title": c.title,
                        "abstractText": c.abstract, "year": c.year,
                        "journal": c.journal, "publication_type": c.publication_type,
                        "content_type": c.content_type, "knowledge_profile": c.knowledge_profile, "discovered_via": c.source,
                        "jats_source": "epmc", "full_text_available": True, **rights,
                        "license_uri": (rights.get("license_uri") or c.license_uri),
                        "license_status": "allowlisted_full_text_pending_human_review",
                        "review_status": "harvested_unreviewed"}, ensure_ascii=False))
                    ok += 1
                    with lock:
                        recent_fails[0] = 0
            else:
                errs.append(c.pmcid + ": " + (err or "unknown"))
                with lock:
                    error_types[err] = error_types.get(err, 0) + 1
                    recent_fails[0] += 1
            with lock:
                completed[0] += 1
                n = completed[0]
                if n % 100 == 0 or n == total:
                    rate = recent_fails[0]
                    rate_pct = int(100 * rate / min(n, 100)) if n else 0
                    print("    [pmc] " + str(n) + "/" + str(total) +
                          " ok=" + str(ok) + " failed=" + str(len(errs)) +
                          " (recent fail rate " + str(rate_pct) + "%)", flush=True)

    if error_types:
        print("    [pmc] failure breakdown:", flush=True)
        for etype, count in sorted(error_types.items(), key=lambda x: -x[1])[:5]:
            print("      " + etype + ": " + str(count), flush=True)
    for e in errs[:3]:
        print("    ! " + e, flush=True)
    return ok, total - ok, errs

