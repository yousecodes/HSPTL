"""NCBI PMC Open Access search provider."""
from __future__ import annotations
import json
from ..models import Candidate
from .base import SourceAdapter
from ..common.http import FetchError, ncbi_get
from ..query_builder import pmc_query_for


class PMCOASource(SourceAdapter):

    name = "pmc"

    PAGE = 1000



    def search(self, key, args):

        q = pmc_query_for(key, args.year_from, args.year_to, getattr(args, "knowledge_profile", "case_reports"))

        retstart = 0

        got = 0

        while retstart < 10000:

            if args.max_per_source and got >= args.max_per_source:

                return

            retmax = min(self.PAGE, 10000 - retstart)

            try:

                data = json.loads(ncbi_get("esearch.fcgi", {

                    "db": "pmc", "term": q, "retmode": "json",

                    "retmax": retmax, "retstart": retstart, "sort": "relevance"}))

            except (FetchError, json.JSONDecodeError):

                return

            ids = data.get("esearchresult", {}).get("idlist", [])

            if not ids:

                return

            for uid in ids:

                yield Candidate(source=self.name, pmcid="PMC" + uid)

                got += 1

                if args.max_per_source and got >= args.max_per_source:

                    return

            retstart += len(ids)



    def count(self, key, args):

        try:

            data = json.loads(ncbi_get("esearch.fcgi", {

                "db": "pmc", "term": pmc_query_for(key, args.year_from, args.year_to),

                "retmode": "json", "retmax": 0}))

            return int(data.get("esearchresult", {}).get("count", 0))

        except (FetchError, json.JSONDecodeError):

            return 0

