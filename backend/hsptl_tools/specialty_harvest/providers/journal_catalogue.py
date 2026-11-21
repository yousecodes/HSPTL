"""Curated case-report journal search provider."""
from __future__ import annotations
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..models import Candidate
from .base import SourceAdapter
from ..catalogue import CASE_REPORT_JOURNALS
from ..common.http import FetchError, http_get, ncbi_get
from ..query_builder import _keyword_terms
from ..specialty_filters import _title_matches_specialty
CROSSREF = "https://api.crossref.org/works"


class JournalSource(SourceAdapter):

    name = "journals"



    def __init__(self, journal_keys=None, max_workers=12):

        self.journal_keys = journal_keys or list(CASE_REPORT_JOURNALS)

        self.max_workers = max_workers



    def _pmc_query(self, key, pmc_name, yf, yt):

        title_terms = _keyword_terms(key)[:12]

        clauses = ['"' + pmc_name + '"[Journal]',

                   '("Case Reports"[Publication Type] OR "case report"[Title])']

        if title_terms:

            clauses.append("(" + " OR ".join(

                '"' + t + '"[Title]' if " " in t else t + "[Title]"

                for t in title_terms) + ")")

        if yf or yt:

            clauses.append("(" + str(yf or 1900) + ":" + str(yt or 2100) + "[dp])")

        return " AND ".join(clauses)



    def _crossref_params(self, key, issn, yf, yt):

        q = " ".join(_keyword_terms(key)[:6]) + " case report"

        filt = "type:journal-article,has-full-text:true,issn:" + issn

        if yf:

            filt += ",from-pub-date:" + str(yf) + "-01-01"

        if yt:

            filt += ",until-pub-date:" + str(yt) + "-12-31"

        return {"query.bibliographic": q, "filter": filt}



    def _search_one(self, jkey, key, args):

        if jkey not in CASE_REPORT_JOURNALS:

            return []

        _display, pmc_name, issn, _prefix = CASE_REPORT_JOURNALS[jkey]

        out = []

        q = self._pmc_query(key, pmc_name, args.year_from, args.year_to)

        retstart = 0

        got = 0

        hard_cap = min(args.max_per_source or 100000, 3000)

        while retstart < 10000 and got < hard_cap:

            if args.max_per_source and got >= args.max_per_source:

                break

            try:

                data = json.loads(ncbi_get("esearch.fcgi", {

                    "db": "pmc", "term": q, "retmode": "json",

                    "retmax": 500, "retstart": retstart}))

            except (FetchError, json.JSONDecodeError):

                break

            ids = data.get("esearchresult", {}).get("idlist", [])

            if not ids:

                break

            for uid in ids:

                out.append(Candidate(source="journals:" + jkey, pmcid="PMC" + uid))

                got += 1

                if args.max_per_source and got >= args.max_per_source:

                    break

                if got >= hard_cap:

                    break

            retstart += len(ids)



        cap = getattr(args, "journals_max_per_journal", 200)

        if cap == 0:

            if out:

                print("    [journals:" + jkey + "] " + str(len(out)) + " candidates (PMC only)",

                      flush=True)

            return out



        if not (args.max_per_source and got >= args.max_per_source):

            xg = 0

            cursor = "*"

            while xg < cap:

                p = self._crossref_params(key, issn, args.year_from, args.year_to)

                p.update({"rows": 100, "cursor": cursor,

                          "select": "DOI,title,abstract,issued,container-title"})

                try:

                    data = json.loads(http_get(CROSSREF + "?" + urllib.parse.urlencode(p)))

                except (FetchError, json.JSONDecodeError):

                    break

                msg = data.get("message", {})

                items = msg.get("items", [])

                if not items:

                    break

                for it in items:

                    title = (it.get("title") or [""])[0]

                    abstract = re.sub(r"<[^>]+>", " ", it.get("abstract") or "")

                    if not _title_matches_specialty(title, abstract, key):

                        continue

                    issued = (it.get("issued") or {}).get("date-parts") or [[]]

                    year = str(issued[0][0]) if issued and issued[0] else ""

                    journal = (it.get("container-title") or [""])[0]

                    out.append(Candidate(

                        source="journals:" + jkey, title=title, abstract=abstract,

                        doi=str(it.get("DOI", "")).lower(), year=year, journal=journal))

                    xg += 1

                    if xg >= cap:

                        break

                if xg >= cap:

                    break

                cursor = msg.get("next-cursor")

                if not cursor:

                    break



        if out:

            print("    [journals:" + jkey + "] " + str(len(out)) + " candidates", flush=True)

        return out



    def search(self, key, args):

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:

            futs = {ex.submit(self._search_one, j, key, args): j

                    for j in self.journal_keys if j in CASE_REPORT_JOURNALS}

            for f in as_completed(futs):

                j = futs[f]

                try:

                    for c in f.result():

                        yield c

                except Exception as e:

                    print("    [journals:" + j + "] ERROR: " + str(e), flush=True)



    def count(self, key, args):

        def _one(j):

            _display, pmc_name, _issn, _prefix = CASE_REPORT_JOURNALS[j]

            try:

                data = json.loads(ncbi_get("esearch.fcgi", {

                    "db": "pmc", "term": self._pmc_query(key, pmc_name,

                                                         args.year_from, args.year_to),

                    "retmode": "json", "retmax": 0}))

                return int(data.get("esearchresult", {}).get("count", 0))

            except Exception:

                return 0

        total = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:

            for n in ex.map(_one, [j for j in self.journal_keys if j in CASE_REPORT_JOURNALS]):

                total += n

        return total

