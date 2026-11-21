"""Europe PMC search provider with cursor-based result traversal."""
from __future__ import annotations
import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..models import Candidate
from .base import SourceAdapter
from ..common.http import EPMC, FetchError, http_get
from ..query_builder import query_for


class EuropePMCSource(SourceAdapter):

    name = "europepmc"

    YEAR_SPAN = 3



    def _fetch_window(self, key, yf, yt, args):

        out = []

        q = query_for(key, yf, yt, getattr(args, "knowledge_profile", "case_reports"))

        cursor = "*"

        pages = 0

        while True:

            params = urllib.parse.urlencode({

                "query": q, "format": "json", "resultType": "lite",

                "pageSize": 1000, "cursorMark": cursor})

            try:

                data = json.loads(http_get(EPMC + "/search?" + params))

            except (FetchError, json.JSONDecodeError):

                break

            pages += 1

            results = data.get("resultList", {}).get("result", [])

            for r in results:

                pmcid = r.get("pmcid")

                if not pmcid:

                    continue

                out.append(Candidate(

                    source=self.name,

                    title=r.get("title", "") or "",

                    doi=(r.get("doi") or "").lower(),

                    pmcid=pmcid,

                    year=str(r.get("pubYear") or ""),

                    journal=r.get("journalTitle") or "",
                    publication_type=", ".join((r.get("pubTypeList") or {}).get("pubType", []) if isinstance((r.get("pubTypeList") or {}).get("pubType", []), list) else [str((r.get("pubTypeList") or {}).get("pubType", ""))]),
                    knowledge_profile=getattr(args, "knowledge_profile", "case_reports")))

            if args.max_per_source and len(out) >= args.max_per_source:

                break

            nxt = data.get("nextCursorMark")

            if not results or not nxt or nxt == cursor:

                break

            cursor = nxt

        label = str(yf or "all") + "-" + str(yt or "all")

        print("    [europepmc " + label + "] " + str(len(out)) +

              " candidates in " + str(pages) + " pages", flush=True)

        return out



    def search(self, key, args):

        if args.year_from or args.year_to:

            for c in self._fetch_window(key, args.year_from, args.year_to, args):

                yield c

            return

        try:

            params = urllib.parse.urlencode({"query": query_for(key, None, None, getattr(args, "knowledge_profile", "case_reports")),

                                             "format": "json", "resultType": "lite",

                                             "pageSize": 1})

            total = json.loads(http_get(EPMC + "/search?" + params))["hitCount"]

        except (FetchError, json.JSONDecodeError):

            total = 0

        if total <= 3000:

            print("  [europepmc] " + str(total) + " hits - single window", flush=True)

            for c in self._fetch_window(key, None, None, args):

                yield c

            return

        import datetime

        end_year = datetime.datetime.now().year + 1

        start_year = 1990

        windows = []

        y = start_year

        while y <= end_year:

            windows.append((y, min(y + self.YEAR_SPAN - 1, end_year)))

            y += self.YEAR_SPAN

        print("  [europepmc] " + str(total) + " hits - slicing across " +

              str(len(windows)) + " windows, 4 workers", flush=True)

        all_cands = []

        with ThreadPoolExecutor(max_workers=4) as ex:

            futs = {ex.submit(self._fetch_window, key, yf, yt, args): (yf, yt)

                    for yf, yt in windows}

            for f in as_completed(futs):

                try:

                    all_cands.extend(f.result())

                except Exception as e:

                    print("    [europepmc] window error: " + str(e), flush=True)

        if args.max_per_source:

            all_cands = all_cands[:args.max_per_source]

        for c in all_cands:

            yield c



    def count(self, key, args):

        try:

            params = urllib.parse.urlencode({"query": query_for(key, args.year_from, args.year_to, getattr(args, "knowledge_profile", "case_reports")),

                                             "format": "json", "resultType": "lite",

                                             "pageSize": 1})

            return json.loads(http_get(EPMC + "/search?" + params))["hitCount"]

        except (FetchError, json.JSONDecodeError):

            return 0

