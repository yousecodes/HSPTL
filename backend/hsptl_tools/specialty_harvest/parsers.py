"""Extracted parsers services for the Clinical Knowledge Harvester."""
from __future__ import annotations
from . import engine as _engine

CANONICAL_MAP = getattr(_engine, 'CANONICAL_MAP')
_XML_ESCAPE = getattr(_engine, '_XML_ESCAPE')
_html_mod = getattr(_engine, '_html_mod')
re = getattr(_engine, 're')



def _strip_tags(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html_mod.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def _parse_meta(html_str):
    meta = {}
    for m in re.finditer(r"<meta\s+([^>]+?)\s*/?>", html_str, re.I):
        attrs = {}
        for am in re.finditer(
                r"""([a-zA-Z_:][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
                m.group(1)):
            attrs[am.group(1).lower()] = am.group(2) or am.group(3) or am.group(4) or ""
        name = (attrs.get("name") or attrs.get("property") or "").lower()
        if name and attrs.get("content"):
            meta[name] = attrs["content"]
    return meta

def _split_by_headings(html):
    pat = re.compile(r"<h([2-4])[^>]*>(.*?)</h\1>", re.I | re.S)
    matches = list(pat.finditer(html))
    out = []
    for i, m in enumerate(matches):
        title = _strip_tags(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        chunk = html[start:end]
        paras = [_strip_tags(p.group(1)) for p in re.finditer(r"<p[^>]*>(.*?)</p>", chunk, re.I | re.S)]
        paras = [p for p in paras if len(p) >= 40]
        if paras:
            out.append((title, paras))
    return out

def _map_sections(pairs):
    seen = set()
    sections = []
    for raw_title, paras in pairs:
        canonical = None
        for pat, name in CANONICAL_MAP:
            if pat.search(raw_title or ""):
                canonical = name
                break
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        sections.append((canonical, paras))
    return sections

def _xml_escape(s):
    return (s or "").translate(_XML_ESCAPE)

def _html_to_jats(html_bytes, doi_hint="", url_hint=""):
    if isinstance(html_bytes, bytes):
        html_str = html_bytes.decode("utf-8", errors="replace")
    else:
        html_str = html_bytes
    html_str = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_str, flags=re.I | re.S)
    html_str = re.sub(r"<style\b[^>]*>.*?</style>", " ", html_str, flags=re.I | re.S)

    meta = _parse_meta(html_str)
    title = ""
    for k in ("citation_title", "dc.title", "og:title", "twitter:title"):
        if meta.get(k):
            title = meta[k]
            break
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.I | re.S)
        if m:
            title = _strip_tags(m.group(1))

    abstract = ""
    for k in ("citation_abstract", "dc.description", "og:description", "description"):
        if meta.get(k):
            abstract = _strip_tags(meta[k])
            break

    journal = (meta.get("citation_journal_title") or meta.get("dc.source") or "")
    date_str = (meta.get("citation_publication_date") or meta.get("citation_date") or "")
    ym = re.search(r"\b(?:19|20)\d{2}\b", date_str)
    year = ym.group(0) if ym else ""

    doi = meta.get("citation_doi") or doi_hint or ""
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi, flags=re.I).strip()

    pairs = _split_by_headings(html_str)
    sections = _map_sections(pairs)
    if not sections:
        return None

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<article>", "  <front>",
             "    <journal-meta>", "      <journal-title-group>",
             "        <journal-title>" + _xml_escape(journal or "Case") + "</journal-title>",
             "      </journal-title-group>", "    </journal-meta>", "    <article-meta>"]
    if doi:
        lines.append('      <article-id pub-id-type="doi">' + _xml_escape(doi) + "</article-id>")
    if year:
        lines.append("      <pub-date><year>" + _xml_escape(year) + "</year></pub-date>")
    lines.append("      <title-group><article-title>" + _xml_escape(title) + "</article-title></title-group>")
    if abstract:
        lines.append("      <abstract>")
        lines.append("        <sec><title>Abstract</title>")
        for para in re.split(r"(?<=\.)\s+(?=[A-Z])", abstract)[:8]:
            if para.strip():
                lines.append("          <p>" + _xml_escape(para.strip()) + "</p>")
        lines.append("        </sec>")
        lines.append("      </abstract>")
    lines.append("    </article-meta>")
    lines.append("  </front>")
    lines.append("  <body>")
    for sec_title, paras in sections:
        lines.append("    <sec>")
        lines.append("      <title>" + _xml_escape(sec_title) + "</title>")
        for p in paras:
            lines.append("      <p>" + _xml_escape(p) + "</p>")
        lines.append("    </sec>")
    lines.append("  </body>")
    lines.append("</article>")
    return "\n".join(lines).encode("utf-8")

