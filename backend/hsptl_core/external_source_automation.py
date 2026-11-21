"""Local scheduler for rights-aware, API-key-free external clinical sources.

Managed public-source records are imported automatically without per-record
human approval and receive a machine-screened integrity status. That status is
not clinical validation and never grants reuse/adaptation rights. Europe PMC
full text is automatically fetched only for its explicit CC0/CC-BY/CC-BY-SA
allow-list; other providers remain metadata/abstract imports.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .ucks_connectors import (
    CONNECTORS,
    configure_connector_schedule,
    get_connector_schedule,
    run_due_connectors,
)

logger = logging.getLogger(__name__)

# These profiles use public APIs that do not require keys. Search terms are
# deliberately conservative and can be changed/disabled by an administrator.
DEFAULT_EXTERNAL_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "key": "europe_pmc_recent_open_access",
        "name": "Europe PMC — open-access clinical research (historical backfill + refresh)",
        "connector": "europe_pmc",
        "catalogue_key": "europe_pmc",
        "family": "bibliographic",
        "locator": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        "query": "(OPEN_ACCESS:Y AND HAS_ABSTRACT:Y)",
        "limit": 20,
        "include_full_text": True,
    },
    {
        "key": "pubmed_recent_evidence",
        "name": "PubMed — guidelines, reviews and trials (historical backfill + refresh)",
        "connector": "pubmed",
        "catalogue_key": "pubmed",
        "family": "bibliographic",
        "locator": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "query": '("clinical practice guideline"[Publication Type] OR "systematic review"[Publication Type] OR "randomized controlled trial"[Publication Type])',
        "limit": 20,
    },
    {
        "key": "pubmed_recently_modified_evidence",
        "name": "PubMed — recently modified clinical evidence",
        "connector": "pubmed",
        "catalogue_key": "pubmed",
        "family": "bibliographic",
        "locator": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "query": '("clinical practice guideline"[Publication Type] OR "systematic review"[Publication Type] OR "randomized controlled trial"[Publication Type]) AND ("last 30 days"[mdat])',
        "limit": 20,
    },
    {
        "key": "clinicaltrials_active_studies",
        "name": "ClinicalTrials.gov — active interventional studies",
        "connector": "clinicaltrials_gov",
        "catalogue_key": "clinicaltrials_gov",
        "family": "trial_registry",
        "locator": "https://clinicaltrials.gov/api/v2/studies",
        "query": "interventional AND recruiting",
        "limit": 20,
    },
    {
        "key": "crossref_recent_clinical_metadata",
        "name": "Crossref — clinical evidence bibliography (historical backfill + refresh)",
        "connector": "crossref",
        "catalogue_key": "crossref",
        "family": "bibliographic",
        "locator": "https://api.crossref.org/works",
        "query": "clinical medicine guideline systematic review",
        "limit": 20,
    },
    {
        "key": "crossref_recently_updated_metadata",
        "name": "Crossref — recently updated clinical metadata",
        "connector": "crossref",
        "catalogue_key": "crossref",
        "family": "bibliographic",
        "locator": "https://api.crossref.org/works",
        "query": "clinical medicine guideline systematic review from-update-date:{date_30d_ago} until-update-date:{today}",
        "limit": 20,
    },
    {
        "key": "clinicaltrials_recently_updated",
        "name": "ClinicalTrials.gov — recently updated study records",
        "connector": "clinicaltrials_gov",
        "catalogue_key": "clinicaltrials_gov",
        "family": "trial_registry",
        "locator": "https://clinicaltrials.gov/api/v2/studies",
        "query": "AREA[LastUpdatePostDate]RANGE[{date_30d_ago},{today}]",
        "limit": 20,
    },
)


def expand_query(template: str, now: datetime | None = None) -> str:
    """Expand the small, explicit date-token set used by built-in profiles."""
    current = now or datetime.now(timezone.utc)
    today = current.date()
    year_ago = today - timedelta(days=365)
    values = {
        "today": today.strftime("%Y-%m-%d"),
        "date_365d_ago": year_ago.strftime("%Y-%m-%d"),
        "pubmed_today": today.strftime("%Y/%m/%d"),
        "pubmed_365d_ago": year_ago.strftime("%Y/%m/%d"),
        "date_30d_ago": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "pubmed_30d_ago": (today - timedelta(days=30)).strftime("%Y/%m/%d"),
    }
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result


class ExternalSourceAutomation:
    """Idempotent source provisioning plus a stoppable local scheduler."""

    def __init__(self, repo, source_registry=None, *, poll_seconds: int = 30):
        self.repo = repo
        self.source_registry = source_registry
        self.poll_seconds = max(5, int(poll_seconds))
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._run_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._ensure_state_table()

    def _ensure_state_table(self) -> None:
        with self.repo.store.transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS ucks_external_automation_state (
                id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL DEFAULT 'idle',
                trigger_source TEXT NOT NULL DEFAULT '', last_started TEXT NOT NULL DEFAULT '',
                last_completed TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}',
                last_error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)""")
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.execute("INSERT OR IGNORE INTO ucks_external_automation_state(id,updated_at) VALUES(1,?)", (stamp,))

    def ensure_default_sources(self) -> dict[str, Any]:
        """Create the built-in connectors once; preserve later admin choices."""
        existing = self.repo.list_sources()
        by_profile = {
            str(item.get("config", {}).get("automation_profile", "")): item
            for item in existing if item and item.get("config", {}).get("automation_profile")
        }
        provisioned, unchanged = [], []
        for profile in DEFAULT_EXTERNAL_PROFILES:
            item = by_profile.get(profile["key"])
            if item is None:
                cfg = {
                    "connector": profile["connector"],
                    "automation_profile": profile["key"],
                    "managed_by": "HSPTL external-source automation",
                    "api_key_required": False,
                    "default_query_template": profile["query"],
                }
                item = self.repo.register_source(
                    name=profile["name"], source_type="external_import",
                    locator=profile["locator"], licence="Provider metadata/API terms; item-level review required",
                    reuse_permitted=False, config=cfg,
                )
                provisioned.append(item["id"])
            # Source registry starts restrictive. Registration labels the source
            # family only; it does not grant copy/adaptation rights.
            if self.source_registry is not None:
                try:
                    self.source_registry.register(
                        source_id=item["id"], catalogue_key=profile["catalogue_key"],
                        family=profile["family"],
                    )
                except ValueError:
                    logger.exception("Could not register external source rights metadata")
            schedule = get_connector_schedule(self.repo, item["id"])
            if schedule is None:
                configure_connector_schedule(
                    self.repo, item["id"], enabled=True, query=profile["query"],
                    interval_minutes=1440, result_limit=profile["limit"],
                    include_full_text=bool(profile.get("include_full_text", False)),
                )
                unchanged.append(item["id"])
            else:
                unchanged.append(item["id"])
        return {"provisioned": len(provisioned), "configured": len(unchanged),
                "source_ids": provisioned + unchanged,
                "api_key_required": False,
                "full_text_policy": "Europe PMC only when an explicit CC0/CC-BY/CC-BY-SA licence is detected"}

    def _set_managed_sources_due(self) -> int:
        source_ids = [
            item["id"] for item in self.repo.list_sources()
            if item and item.get("enabled")
            and item.get("config", {}).get("automation_profile")
            and item.get("config", {}).get("connector") in CONNECTORS
        ]
        if not source_ids:
            return 0
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.repo.store.transaction() as conn:
            placeholders = ",".join("?" for _ in source_ids)
            cur = conn.execute(
                f"UPDATE ucks_connector_schedule SET next_run=?,lease_until='' "
                f"WHERE source_id IN ({placeholders}) AND enabled=1",
                (stamp, *source_ids),
            )
        return max(0, cur.rowcount)

    def _save_state(self, *, status: str, trigger_source: str = "scheduler",
                    started: str = "", result: dict[str, Any] | None = None,
                    error: str = "") -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.repo.store.transaction() as conn:
            conn.execute("""UPDATE ucks_external_automation_state SET status=?,trigger_source=?,
                last_started=CASE WHEN ?<>'' THEN ? ELSE last_started END,
                last_completed=CASE WHEN ? IN ('completed','completed_with_errors','failed') THEN ? ELSE last_completed END,
                result_json=?,last_error=?,updated_at=? WHERE id=1""",
                (status, trigger_source, started, started, status, stamp,
                 json.dumps(result or {}, ensure_ascii=False), error[:1000], stamp))


    def _generate_and_publish_new_records(self, connector_result: dict[str, Any]) -> dict[str, Any]:
        """Turn newly imported, rights-eligible source records into provisional learning artefacts.

        Only machine-screened current records with an explicit reusable licence (or
        an explicit rights decision) are passed to full-text generation. Other
        records remain searchable metadata/abstract records and are reported as
        skipped; no rights are inferred from import success.
        """
        from .generation_distribution import GenerationDistribution
        from .workspace_distribution import WorkspaceDistributionAdapter

        source_ids = [item.get("source_id") for item in connector_result.get("results", [])
                      if item.get("status") == "succeeded" and item.get("records_added", 0)]
        if not source_ids:
            return {"considered": 0, "generated": 0, "published": 0, "skipped": 0, "items": []}
        engine = GenerationDistribution(self.repo.store.db_path)
        adapter = WorkspaceDistributionAdapter(self.repo.store)
        with self.repo.store.transaction() as conn:
            marks = ",".join("?" for _ in source_ids)
            rows = conn.execute(
                f"SELECT id,title,content_type,review_status,lifecycle_state,current_version FROM ucks_documents "
                f"WHERE source_id IN ({marks}) AND review_status='machine_screened' "
                "AND lifecycle_state NOT IN ('retracted','superseded') ORDER BY created_at DESC LIMIT 100",
                tuple(source_ids),
            ).fetchall()
        mapping = {
            "case_report": ("clinic", "case_report"),
            "case_series": ("clinic", "conference_brief"),
            "synthetic_case": ("clinic", "case_report"),
            "clinical_note": ("rounds", "tagged_report"),
            "reference_document": ("exam_hall", "topic_summary"),
            "dataset": ("lab", "investigation_guide"),
            "guideline": ("exam_hall", "topic_summary"),
            "systematic_review": ("exam_hall", "topic_summary"),
            "trial": ("exam_hall", "topic_summary"),
            "diagnostic_study": ("exam_hall", "topic_summary"),
            "observational_study": ("exam_hall", "topic_summary"),
        }
        output = {"considered": len(rows), "generated": 0, "published": 0, "skipped": 0, "items": []}
        for row in rows:
            target = mapping.get(row["content_type"])
            if not target:
                output["skipped"] += 1
                output["items"].append({"document_id": row["id"], "status": "skipped", "reason": "content_type_not_mapped"})
                continue
            with engine.connect() as conn:
                existing_rows = conn.execute(
                    "SELECT source_refs_json FROM generated_artifacts WHERE source_refs_json LIKE ?",
                    (f'%{row["id"]}%',),
                ).fetchall()
            already_current = False
            for existing in existing_rows:
                try:
                    refs = json.loads(existing["source_refs_json"] or "[]")
                except (TypeError, json.JSONDecodeError):
                    refs = []
                if any(ref.get("document_id") == row["id"] and
                       int(ref.get("current_version", 0)) == int(row["current_version"])
                       for ref in refs if isinstance(ref, dict)):
                    already_current = True
                    break
            if already_current:
                continue
            workspace, kind = target
            try:
                artifact = engine.generate(workspace=workspace, kind=kind, title=row["title"],
                                           source_documents=[row["id"]], ucks_repo=self.repo)
                route = engine.route(artifact["id"], workspace, "automatically generated learning resources", adapter=adapter)
                output["generated"] += 1
                output["published"] += int(route.get("status") == "delivered")
                output["items"].append({"document_id": row["id"], "artifact_id": artifact["id"],
                                        "workspace": workspace, "kind": kind,
                                        "status": "provisional", "route_status": route.get("status", "delivered")})
            except (ValueError, RuntimeError) as exc:
                output["skipped"] += 1
                output["items"].append({"document_id": row["id"], "status": "skipped",
                                        "reason": str(exc)[:240]})
        return output

    def _reconcile_downstream_artifacts(self) -> dict[str, int]:
        """Quarantine learning artefacts when a cited source changes or is withdrawn.

        A source revision does not silently rewrite an already published learning
        artefact. Instead the old artefact is marked for refresh; confirmed
        retractions/supersessions withdraw it from the learner-facing index.
        This preserves an audit trail while preventing stale material from being
        presented as current.
        """
        from .generation_distribution import GenerationDistribution

        engine = GenerationDistribution(self.repo.store.db_path)
        with engine.connect() as conn:
            artifacts = conn.execute(
                "SELECT id,status,source_refs_json FROM generated_artifacts "
                "WHERE status IN ('provisional','approved','source_update_required','withdrawn')"
            ).fetchall()
        changed = withdrawn = refresh_required = 0
        for artifact in artifacts:
            try:
                refs = json.loads(artifact["source_refs_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            reasons: list[tuple[str, str]] = []
            for ref in refs:
                if not isinstance(ref, dict) or not ref.get("document_id"):
                    continue
                doc = self.repo.get_document(str(ref["document_id"]))
                if not doc:
                    continue
                lifecycle = str(doc.get("lifecycle_state", "current"))
                if lifecycle in {"retracted", "superseded"}:
                    reasons.append((lifecycle, str(doc["id"])))
                elif lifecycle == "corrected" or int(ref.get("current_version", 0) or 0) != int(doc.get("current_version", 1)):
                    reasons.append(("source_update_required", str(doc["id"])))
            if not reasons:
                continue
            is_withdrawal = any(state in {"retracted", "superseded"} for state, _ in reasons)
            target = "withdrawn" if is_withdrawal else "source_update_required"
            if artifact["status"] == target:
                continue
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            detail = {"status": target, "sources": [{"state": state, "document_id": doc_id} for state, doc_id in reasons], "automatic": True}
            with engine.connect() as conn:
                conn.execute("UPDATE generated_artifacts SET status=?,updated_at=? WHERE id=?", (target, now, artifact["id"]))
                conn.execute("UPDATE distribution_routes SET status=?,error=? WHERE artifact_id=? AND status IN ('delivered','source_update_required')",
                             (target, target, artifact["id"]))
                conn.execute("INSERT INTO generation_audit VALUES(?,?,?,?,?)",
                             ("audit_" + __import__("uuid").uuid4().hex, artifact["id"], target, json.dumps(detail, ensure_ascii=False), now))
            with self.repo.store.transaction() as conn:
                conn.execute("UPDATE tagged_content_items SET source_status=?,updated_at=? WHERE content_id=?",
                             (target, now, artifact["id"]))
            changed += 1
            withdrawn += int(is_withdrawal)
            refresh_required += int(not is_withdrawal)
        return {"checked": len(artifacts), "changed": changed, "withdrawn": withdrawn, "refresh_required": refresh_required}

    def run_once(self, *, force: bool = False, trigger_source: str = "manual") -> dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {"status": "already_running", "queued": False}
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._save_state(status="running", trigger_source=trigger_source, started=started)
        try:
            if force:
                self._set_managed_sources_due()
            result = run_due_connectors(self.repo, limit=12)
            result["source_reconciliation"] = self._reconcile_downstream_artifacts()
            result["content_generation"] = self._generate_and_publish_new_records(result)
            failures = sum(1 for item in result.get("results", []) if item.get("status") == "failed")
            status = "completed_with_errors" if failures else "completed"
            self._save_state(status=status, trigger_source=trigger_source,
                             started=started, result=result,
                             error=f"{failures} connector job(s) failed" if failures else "")
            return {"status": status, **result}
        except Exception as exc:  # background cycle must not terminate the host
            logger.exception("External source automation cycle failed")
            self._save_state(status="failed", trigger_source=trigger_source,
                             started=started, error=type(exc).__name__)
            return {"status": "failed", "error": type(exc).__name__}
        finally:
            self._run_lock.release()

    def trigger_refresh(self) -> dict[str, Any]:
        self._wake.set()
        return {"status": "queued", "queued": True,
                "message": "Enabled human-authored public sources have been queued. Records import automatically without per-record approval and are machine-screened for integrity; clinical validity and reuse rights remain separately labelled."}

    def status(self) -> dict[str, Any]:
        with self.repo.store.transaction() as conn:
            row = conn.execute("SELECT * FROM ucks_external_automation_state WHERE id=1").fetchone()
        state = dict(row) if row else {}
        if state.get("result_json"):
            try:
                state["last_result"] = json.loads(state.pop("result_json"))
            except (TypeError, json.JSONDecodeError):
                state["last_result"] = {}
                state.pop("result_json", None)
        schedules = []
        for item in self.repo.list_sources():
            if not item or item.get("config", {}).get("automation_profile"):
                if item:
                    schedules.append({"source_id": item["id"], "name": item["name"],
                                      "connector": item.get("config", {}).get("connector", ""),
                                      "enabled": item.get("enabled", False),
                                      "schedule": get_connector_schedule(self.repo, item["id"])})
        state["profiles"] = schedules
        state["api_key_required"] = False
        state["automatic_review_status"] = "machine_screened"
        state["automatic_import_enabled"] = True
        state["human_approval_required_for_import"] = False
        state["clinical_validity_assessed_automatically"] = False
        state["reuse_rights_granted_automatically"] = False
        state["auto_approve"] = False  # clinical validation is never auto-approved
        state["auto_publish"] = True  # eligible derived artefacts are provisionally distributed
        state["publication_status"] = "provisional"
        state["source_change_propagation"] = "automatic_quarantine_and_refresh_required"
        return state

    def start(self) -> None:
        self.ensure_default_sources()
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._wake.set()  # run due jobs at startup

        def worker() -> None:
            while not self._stop.is_set():
                forced = self._wake.wait(self.poll_seconds)
                self._wake.clear()
                if self._stop.is_set():
                    break
                try:
                    self.run_once(force=forced, trigger_source="startup_or_manual" if forced else "scheduled")
                except Exception:  # noqa: BLE001
                    logger.exception("External source worker survived an unexpected failure")

        self._thread = threading.Thread(target=worker, daemon=True,
                                        name="hsptl-external-source-automation")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
