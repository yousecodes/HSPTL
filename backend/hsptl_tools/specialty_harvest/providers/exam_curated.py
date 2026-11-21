"""Specialty-specific curated exam-journal provider."""
from __future__ import annotations
import re
from ..models import Candidate
from .base import SourceAdapter
from ..catalogue import EXAM_SOURCE_CONFIGS
from ..common.http import fetch_page as _fetch_page
from ..parsers import _map_sections, _parse_meta, _split_by_headings, _strip_tags
from ..specialty_filters import _title_matches_specialty


class ExamCuratedSource(SourceAdapter):

    name = "exam"



    def __init__(self, max_per_source=40):

        self.max_per_source = max_per_source



    def _article(self, url, journal, source_tag, key, title_hint=""):

        html = _fetch_page(url)

        if not html:

            return None

        meta = _parse_meta(html)

        title = meta.get("citation_title") or title_hint or ""

        if not title:

            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)

            title = _strip_tags(m.group(1)) if m else ""

        title = re.sub(r"\s*[|\-–]\s*(?:Medscape|Review of Ophthalmology|EyeRounds|DJO|GMS|Radiopaedia).*$", "", title, flags=re.I).strip()

        if not title or not _title_matches_specialty(title, "", key):

            return None

        pairs = _split_by_headings(html)

        sections = _map_sections(pairs)

        if not sections:

            paras = [_strip_tags(p.group(1)) for p in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)]

            paras = [p for p in paras if len(p) >= 120]

            if paras:

                sections = [("presentation", paras[:4])]

        if not sections:

            return None

        return Candidate(

            source="exam:" + source_tag, title=title, journal=journal,

            sections=sections, abstract=sections[0][1][0] if sections[0][1] else "")



    def _fetch_eyerounds(self, cfg, key):

        idx = _fetch_page("https://eyerounds.org/cases.htm")

        if not idx:

            return

        count = 0

        for m in re.finditer(r'\[([^\]]+)\]\((cases/[^)]+\.htm)\)', idx):

            if count >= self.max_per_source:

                break

            title = m.group(1).strip().rstrip(":")

            c = self._article("https://eyerounds.org/" + m.group(2),

                              "EyeRounds", "eyerounds", key, title_hint=title)

            if c:

                yield c

                count += 1



    def _fetch_djo(self, cfg, key):

        for page in ("https://djo.harvard.edu/index.php/djo/issue/current",

                     "https://djo.harvard.edu/index.php/djo/search/search?query=case+report"):

            idx = _fetch_page(page)

            if not idx:

                continue

            count = 0

            seen = set()

            for m in re.finditer(

                    r'href="(https://djo\.harvard\.edu/index\.php/djo/article/view/\d+)"[^>]*>([^<]{5,200})<',

                    idx):

                if count >= self.max_per_source:

                    break

                url, title = m.group(1), _strip_tags(m.group(2))

                if url in seen or not title:

                    continue

                seen.add(url)

                c = self._article(url, "Digital Journal of Ophthalmology", "djo", key, title_hint=title)

                if c:

                    yield c

                    count += 1



    def _fetch_gms(self, cfg, key):

        idx = _fetch_page("https://www.egms.de/dynamic/en/journals/oc/index.htm")

        if not idx:

            return

        count = 0

        seen = set()

        for m in re.finditer(

                r'href="(/static/en/journals/oc/[^"]+/oc\d+\.shtml)"[^>]*>([^<]{5,200})<', idx):

            if count >= self.max_per_source:

                break

            url = "https://www.egms.de" + m.group(1)

            if url in seen:

                continue

            seen.add(url)

            c = self._article(url, "GMS Ophthalmology Cases", "gms", key,

                              title_hint=_strip_tags(m.group(2)))

            if c:

                yield c

                count += 1



    def _fetch_wills(self, cfg, key):

        home = _fetch_page("https://www.reviewofophthalmology.com/")

        if not home:

            return

        count = 0

        seen = set()

        for m in re.finditer(r'href="(/article/[^"]*wills[^"]*)"[^>]*>([^<]{5,200})<', home, re.I):

            if count >= self.max_per_source:

                break

            url = "https://www.reviewofophthalmology.com" + m.group(1)

            if url in seen:

                continue

            seen.add(url)

            c = self._article(url, "Review of Ophthalmology", "wills", key,

                              title_hint=_strip_tags(m.group(2)))

            if c:

                yield c

                count += 1



    def _fetch_medscape(self, cfg, key):

        slug = cfg.get("specialty_slug", "")

        if not slug:

            return

        urls = ["https://www.medscape.com/" + slug + "/cases",

                "https://www.medscape.com/index/list_11724_9"]

        count = 0

        seen = set()

        for url in urls:

            html = _fetch_page(url)

            if not html:

                continue

            for m in re.finditer(

                    r'href="(https://www\.medscape\.com/viewarticle/\d+)"[^>]*>([^<]{5,200})<', html):

                if count >= self.max_per_source:

                    return

                art_url, title = m.group(1), _strip_tags(m.group(2))

                if art_url in seen or not title:

                    continue

                seen.add(art_url)

                c = self._article(art_url, "Medscape", "medscape", key, title_hint=title)

                if c:

                    yield c

                    count += 1



    def _fetch_radiopaedia(self, cfg, key):

        systems = cfg.get("systems", ["neuro", "chest", "abdo", "msk"])

        count = 0

        seen = set()

        for system in systems:

            if count >= self.max_per_source:

                return

            html = _fetch_page("https://radiopaedia.org/cases?system=" + system)

            if not html:

                continue

            for m in re.finditer(r'href="(/cases/[a-z0-9\-]+-\d+)"[^>]*>([^<]{5,200})<', html):

                if count >= self.max_per_source:

                    return

                href = "https://radiopaedia.org" + m.group(1)

                if href in seen:

                    continue

                seen.add(href)

                title = _strip_tags(m.group(2))

                c = self._article(href, "Radiopaedia", "radiopaedia", key, title_hint=title)

                if c:

                    yield c

                    count += 1



    def _fetch_dermnet(self, cfg, key):

        for page in ("https://dermnetnz.org/cme/case-reports",

                     "https://dermnetnz.org/topics"):

            html = _fetch_page(page)

            if not html:

                continue

            count = 0

            seen = set()

            for m in re.finditer(r'href="(/topics/[a-z0-9\-]+)"[^>]*>([^<]{5,200})<', html):

                if count >= self.max_per_source:

                    break

                url = "https://dermnetnz.org" + m.group(1)

                if url in seen:

                    continue

                seen.add(url)

                c = self._article(url, "DermNet NZ", "dermnet", key,

                                  title_hint=_strip_tags(m.group(2)))

                if c:

                    yield c

                    count += 1



    def _fetch_cdc_eid(self, cfg, key):

        idx = _fetch_page("https://wwwnc.cdc.gov/eid/page/cme")

        if not idx:

            return

        count = 0

        seen = set()

        for m in re.finditer(r'href="(/eid/article/\d+/\d+/\d+-\d+_article)"[^>]*>([^<]{5,200})<', idx):

            if count >= self.max_per_source:

                break

            url = "https://wwwnc.cdc.gov" + m.group(1)

            if url in seen:

                continue

            seen.add(url)

            c = self._article(url, "CDC Emerging Infectious Diseases", "cdc-eid", key,

                              title_hint=_strip_tags(m.group(2)))

            if c:

                yield c

                count += 1



    def _fetch_aliem(self, cfg, key):

        html = _fetch_page("https://www.aliem.com/category/clinical/case/")

        if not html:

            return

        count = 0

        seen = set()

        for m in re.finditer(r'href="(https://www\.aliem\.com/[^"/]+/)"[^>]*>([^<]{5,200})<', html):

            if count >= self.max_per_source:

                break

            url, title = m.group(1), _strip_tags(m.group(2))

            if url in seen or not title or "category" in url:

                continue

            seen.add(url)

            c = self._article(url, "ALiEM", "aliem", key, title_hint=title)

            if c:

                yield c

                count += 1



    def _get_fetcher(self, cfg):

        kind = cfg.get("kind", "")

        if kind == "eyerounds": return self._fetch_eyerounds

        if kind == "djo": return self._fetch_djo

        if kind == "gms": return self._fetch_gms

        if kind == "wills": return self._fetch_wills

        if kind == "medscape": return self._fetch_medscape

        if kind == "radiopaedia": return self._fetch_radiopaedia

        if kind == "dermnet": return self._fetch_dermnet

        if kind == "cdc-eid": return self._fetch_cdc_eid

        if kind == "aliem": return self._fetch_aliem

        return None



    def search(self, key, args):

        configs = EXAM_SOURCE_CONFIGS.get(key, [])

        if not configs:

            print("  [exam] no dedicated free exam sources for " + key +

                  "; falling back to journals only", flush=True)

            return

        for cfg in configs:

            fetcher = self._get_fetcher(cfg)

            if not fetcher:

                continue

            try:

                count = 0

                for c in fetcher(cfg, key):

                    yield c

                    count += 1

                if count:

                    print("    [exam:" + cfg["name"] + "] " + str(count) + " cases", flush=True)

            except Exception as e:

                print("    [exam:" + cfg["name"] + "] " + type(e).__name__ + ": " + str(e), flush=True)



    def count(self, key, args):

        return len(list(self.search(key, args)))

