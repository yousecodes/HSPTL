"""Optional local-only synthesis through an Ollama-compatible endpoint.

No cloud provider, API key, telemetry, or remote fallback is used. The caller
must still validate every generated citation against retrieved source spans.
"""
from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlsplit

import requests


class LocalModelUnavailable(RuntimeError):
    pass


class OllamaLocalGenerator:
    """Small-model adapter suitable for optional local installs (e.g. 1.5B–3B)."""

    def __init__(self, *, endpoint: str | None = None, model: str | None = None,
                 timeout: int | None = None, session=requests):
        self.endpoint = (endpoint or os.getenv("HSPTL_LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:11434")).rstrip("/")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise ValueError("Local model endpoint must be an unauthenticated HTTP loopback URL")
        self.model = model or os.getenv("HSPTL_LOCAL_MODEL", "qwen2.5:1.5b")
        self.timeout = max(10, min(int(timeout or os.getenv("HSPTL_LOCAL_MODEL_TIMEOUT", "90")), 240))
        self.session = session

    def generate(self, *, title: str, kind: str, required_sections: list[str], spans: list[dict[str, Any]]) -> dict[str, Any]:
        # Keep the prompt inside a 4K-token context for small local models.
        compact = [{"chunk_id": s["chunk_id"], "document_id": s["document_id"],
                    "source_url": s.get("source_url", ""), "text": s["text"][:1200]}
                   for s in spans[:6]]
        prompt = (
            "Create a cautious clinical-learning artefact using ONLY the supplied source excerpts. "
            "Do not add clinical facts, recommendations, doses, thresholds, or interpretations not "
            "supported by an excerpt. If evidence is insufficient, state that limitation. This is "
            "educational material, not patient-specific advice. Return JSON only with keys sections, "
            "assessment_items, limitations. sections must contain every required heading exactly; "
            "each section has claims, and every claim has text and citations. Each citation must "
            "contain chunk_id and an exact verbatim quote of at least 12 characters from that chunk. "
            "For question_set, viva_set, or osce_station, include assessment_items with question, "
            "answer, and citations. Never invent a citation or quote.\n\n"
            f"Title: {title}\nOutput kind: {kind}\nRequired headings: {json.dumps(required_sections)}\n"
            f"Source excerpts: {json.dumps(compact, ensure_ascii=False)}"
        )
        try:
            response = self.session.post(
                self.endpoint + "/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": "json",
                      "options": {"temperature": 0.1, "num_ctx": 4096}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            raw = payload.get("response", "")
            result = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(result, dict):
                raise ValueError("Local model response was not a JSON object")
            return result
        except Exception as exc:
            raise LocalModelUnavailable(f"Local model unavailable or invalid response: {type(exc).__name__}") from exc


def local_model_enabled() -> bool:
    return os.getenv("HSPTL_LOCAL_MODEL_ENABLED", "0").strip().casefold() in {"1", "true", "yes", "on"}
