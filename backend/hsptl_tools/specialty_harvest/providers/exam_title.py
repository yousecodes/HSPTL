"""Exam-title and teaching-signal search provider."""
from __future__ import annotations
import json
import re
import urllib.parse
from ..models import Candidate
from .base import SourceAdapter
from ..common.http import EPMC, FetchError, http_get
from ..query_builder import _keyword_terms


class ExamTitleSource(SourceAdapter):

    """Search EPMC for exam-style articles by title or abstract cue."""

    name = "examtitle"



    TITLE_CUES = [

        "clinical challenge",

        "diagnose this",

        "image challenge",

        "picture challenge",

        "what is your diagnosis",

        "what is the diagnosis",

        "what is the most likely diagnosis",

        "case challenge",

        "unknown case",

        "diagnostic dilemma",

        "quiz case",

        "spot diagnosis",

        "spot the diagnosis",

        "guess the diagnosis",

        "clinical case challenge",

        "what would you do",

        "how would you manage",

        "self-assessment",

        "self assessment",

        "case of the month",

        "case of the week",

        "image of the month",

        "image of the week",

        "interesting case",

        "challenging case",

        "photo essay",

        "photoessay",

        "images in",

        "pictorial essay",

        "ocular images",

        "ophthalmic images",

        "test your knowledge",

        "diagnostic quiz",

        "clinical quiz",

        "grand rounds",

        "case records",

        "clinicopathologic correlation",

        "clinicopathological correlation",

        "clinical pearls",

        "pearls and pitfalls",

        "teaching case",

        "learning case",

    ]



    ABSTRACT_CUES = [

        "what is your diagnosis",

        "what is the most likely diagnosis",

        "which of the following",

        "most likely diagnosis",

        "correct diagnosis",

    ]



    def _build_query(self, key):

        cues = " OR ".join('TITLE:"' + c + '"' for c in self.TITLE_CUES)

        terms = " OR ".join(

            'TITLE:"' + t + '"' if " " in t else "TITLE:" + t

            for t in _keyword_terms(key)[:20])

        return "(" + cues + ") AND (" + terms + ") AND (PUB_TYPE:\"Case Reports\" OR TITLE:\"case report\") AND OPEN_ACCESS:y AND HAS_FT:y"



    def _build_abstract_query(self, key):

        cues = " OR ".join('ABSTRACT:"' + c + '"' for c in self.ABSTRACT_CUES)

        terms = " OR ".join(

            'TITLE:"' + t + '"' if " " in t else "TITLE:" + t

            for t in _keyword_terms(key)[:20])

        return "(" + cues + ") AND (" + terms + ") AND OPEN_ACCESS:y AND HAS_FT:y"



    def _run_query(self, q, args, source_suffix):

        cursor = "*"

        got = 0

        while True:

            if args.max_per_source and got >= args.max_per_source:

                return

            params = urllib.parse.urlencode({

                "query": q, "format": "json", "resultType": "core",

                "pageSize": 1000, "cursorMark": cursor})

            try:

                data = json.loads(http_get(EPMC + "/search?" + params))

            except (FetchError, json.JSONDecodeError):

                return

            results = data.get("resultList", {}).get("result", [])

            for r in results:

                pmcid = r.get("pmcid")

                if not pmcid:

                    continue

                yield Candidate(

                    source="exam:" + source_suffix,

                    title=r.get("title", "") or "",

                    abstract=r.get("abstractText", "") or "",

                    doi=(r.get("doi") or "").lower(),

                    pmcid=pmcid,

                    year=str(r.get("pubYear") or ""),

                    journal=r.get("journalTitle") or "")

                got += 1

                if args.max_per_source and got >= args.max_per_source:

                    return

            nxt = data.get("nextCursorMark")

            if not results or not nxt or nxt == cursor:

                return

            cursor = nxt



    def search(self, key, args):

        seen = set()

        for c in self._run_query(self._build_query(key), args, "title"):

            if c.dedup_key() in seen:

                continue

            seen.add(c.dedup_key())

            yield c

        for c in self._run_query(self._build_abstract_query(key), args, "abstract"):

            if c.dedup_key() in seen:

                continue

            seen.add(c.dedup_key())

            yield c



    def count(self, key, args):

        return len(list(self.search(key, args)))

