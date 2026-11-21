"""Single orchestration path for deterministic provisional learning artefacts.

The factory owns content recipes; the distribution engine owns persistence,
content hashes, audit events and lifecycle. Eligible outputs are automatically
routed as provisional educational material, never represented as clinically
validated. Human review remains available after publication.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .content_factory import ContentFactory, DEFAULT_OUTPUT_TYPES
from .generation_distribution import GenerationDistribution


class UnifiedContentPipeline:
    def __init__(self, factory: ContentFactory, distribution: GenerationDistribution, adapter=None):
        self.factory = factory
        self.distribution = distribution
        self.adapter = adapter

    def refresh(self, *, max_units: int = 250) -> dict[str, Any]:
        units = list(self.factory.units.keys())
        if len(units) > max_units:
            raise ValueError(f"Installed content packs exceed the safe automatic-refresh limit of {max_units} topics")
        created = reused = published = 0
        workspace_counts: dict[str, int] = {}
        for unit_id in units:
            for kind in DEFAULT_OUTPUT_TYPES:
                spec = self.factory.build(unit_id, kind, seed=0)
                canonical = {
                    "workspace": spec["workspace"], "kind": spec["kind"],
                    "title": spec["title"].strip(), "body": spec["body"],
                    "source_refs": spec["source_refs"] or [],
                    "template_version": int(spec["template_version"]),
                }
                digest = hashlib.sha256(json.dumps(
                    canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode("utf-8")).hexdigest()
                with self.distribution.connect() as conn:
                    existing = conn.execute(
                        "SELECT id FROM generated_artifacts WHERE content_hash=? LIMIT 1", (digest,)
                    ).fetchone()
                artifact = None
                if existing:
                    reused += 1
                    artifact = self.distribution.get_artifact(existing["id"])
                else:
                    artifact = self.distribution.create_structured_draft(
                        workspace=spec["workspace"], kind=spec["kind"], title=spec["title"],
                        body=spec["body"], source_refs=spec["source_refs"],
                        template_version=spec["template_version"],
                        audit_event="generated_by_unified_content_pipeline",
                    )
                    created += 1
                if self.adapter is not None:
                    if artifact and artifact.get("status") in {"provisional", "approved"}:
                        route = self.distribution.route(artifact["id"], spec["workspace"],
                            "automatically generated learning resources", adapter=self.adapter)
                        published += int(route.get("status") == "delivered")
                workspace_counts[spec["workspace"]] = workspace_counts.get(spec["workspace"], 0) + 1
        catalog = self.factory.catalog()
        total = created + reused
        return {
            "status": "ready", "pack_count": catalog["pack_count"],
            "unit_count": len(units), "requested_outputs": total,
            "created_count": created, "reused_count": reused,
            "draft_count": total, "provisional_count": total,
            "published_count": published, "workspace_counts": workspace_counts,
            "review_required": False, "auto_approved": False,
            "auto_published": True,
            "publication_status": "provisional",
            "pipeline": "unified_deterministic_content_v2",
            "message": (f"Prepared {created} new provisional learning artefacts; {reused} outputs were already current. "
                        f"{published} artefacts were automatically routed to their workspaces. Clinical validation remains separate."),
        }
