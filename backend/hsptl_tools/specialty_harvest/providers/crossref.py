"""Crossref bibliographic metadata provider."""
from __future__ import annotations
import json
import re
import urllib.parse
from ..models import Candidate
from .base import SourceAdapter
from ..common.http import FetchError, http_get
from ..specialty_filters import _title_matches_specialty
from ..query_builder import crossref_query_for
CROSSREF = "https://api.crossref.org/works"


class CrossrefSource(SourceAdapter):

    name = "crossref"

    HARD_CAP = 3000



    def search(self, key, args):

        q = crossref_query_for(key, getattr(args, "knowledge_profile", "case_reports"))

        cursor = "*"

        got = 0

        pages = 0

        cap = min(args.max_per_source or self.HARD_CAP, self.HARD_CAP)

        print("    [crossref] starting (cap " + str(cap) + ")", flush=True)

        while got < cap:

            pages += 1

            params = urllib.parse.urlencode({

                "query.bibliographic": q,

                "filter": "type:journal-article,has-license:true",

                "rows": 200, "cursor": cursor,

                "mailto": args.unpaywall_email or "research@example.org",

                "select": "DOI,title,abstract,issued,container-title,type,license"})

            try:

                data = json.loads(http_get(CROSSREF + "?" + params))

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

                yield Candidate(

                    source=self.name, title=title, abstract=abstract,

                    doi=str(it.get("DOI", "")).lower(), year=year, journal=journal,
                    publication_type=str(it.get("type") or "journal-article"), content_type="other",
                    license_uri=str(((it.get("license") or [{}])[0]).get("URL") or ""),
                    knowledge_profile=getattr(args, "knowledge_profile", "case_reports"))

                got += 1

                if got >= cap:

                    break

            if pages % 5 == 0 or got >= cap:

                print("    [crossref] " + str(got) + " candidates in " + str(pages) +

                      " pages", flush=True)

            if got >= cap:

                break

            cursor = msg.get("next-cursor")

            if not cursor:

                break

        print("    [crossref] " + str(got) + " candidates in " + str(pages) +

              " pages total", flush=True)



    def count(self, key, args):

        params = urllib.parse.urlencode({

            "query.bibliographic": crossref_query_for(key, getattr(args, "knowledge_profile", "case_reports")),

            "filter": "type:journal-article,has-license:true", "rows": 0})

        try:

            data = json.loads(http_get(CROSSREF + "?" + params))

            return int(data.get("message", {}).get("total-results", 0))

        except Exception:

            return 0

