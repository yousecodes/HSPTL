"""Directory of Open Access Journals metadata provider."""
from __future__ import annotations
import json
import re
import urllib.parse
from ..models import Candidate
from .base import SourceAdapter
from ..common.http import DOAJ_URL, FetchError, http_get
from ..query_builder import doaj_query_for
DOAJ = DOAJ_URL


class DOAJSource(SourceAdapter):

    name = "doaj"

    MAX_PAGES = 10



    def search(self, key, args):

        q = doaj_query_for(key, args.year_from, args.year_to, getattr(args, "knowledge_profile", "case_reports"))

        page = 1

        got = 0

        while page <= self.MAX_PAGES:

            if args.max_per_source and got >= args.max_per_source:

                return

            url = DOAJ + "/" + urllib.parse.quote(q, safe="") + "?page=" + str(page) + "&pageSize=100"

            try:

                data = json.loads(http_get(url))

            except (FetchError, json.JSONDecodeError):

                return

            results = data.get("results", [])

            if not results:

                return

            for r in results:

                b = r.get("bibjson") or {}

                doi = ""

                for ident in b.get("identifier", []) or []:

                    if str(ident.get("type", "")).lower() == "doi":

                        doi = str(ident.get("id", "")).lower()

                        break

                year = str(b.get("year") or "")

                journal = (b.get("journal") or {}).get("title") or ""
                license_value = b.get("license") or {}
                if isinstance(license_value, list):
                    license_value = next((x for x in license_value if isinstance(x, dict)), {})
                if not isinstance(license_value, dict):
                    license_value = {}

                yield Candidate(

                    source=self.name,

                    title=b.get("title") or "",

                    abstract=re.sub(r"<[^>]+>", " ", b.get("abstract") or ""),

                    doi=doi, year=year, journal=journal,
                    publication_type=str(b.get("type") or ""),
                    content_type="other", license_uri=str(license_value.get("url") or license_value.get("title") or ""),
                    knowledge_profile=getattr(args, "knowledge_profile", "case_reports"))

                got += 1

                if args.max_per_source and got >= args.max_per_source:

                    return

            if len(results) < 100:

                return

            page += 1



    def count(self, key, args):

        try:

            url = DOAJ + "/" + urllib.parse.quote(doaj_query_for(key, args.year_from, args.year_to, getattr(args, "knowledge_profile", "case_reports")), safe="") + "?page=1&pageSize=1"

            return int(json.loads(http_get(url)).get("total", 0))

        except (FetchError, json.JSONDecodeError, ValueError, KeyError):

            return 0

