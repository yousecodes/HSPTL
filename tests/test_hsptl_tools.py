from __future__ import annotations

import json
from pathlib import Path

from backend.hsptl_tools.mednotegen.narratives import build_outputs
from backend.hsptl_tools.mednotegen.exporters import export_markdown
from backend.hsptl_core.jobs import JobRunner
from backend.hsptl_core.store import StudyStore


def test_mednotegen_markdown_exports_list_source_evidence(tmp_path: Path):
    resources = [
        {"resourceType": "Patient", "id": "p1", "birthDate": "1980-01-01"},
        {"resourceType": "Encounter", "id": "e1", "subject": {"reference": "Patient/p1"}, "status": "finished"},
        {"resourceType": "Condition", "id": "c1", "subject": {"reference": "Patient/p1"}, "encounter": {"reference": "Encounter/e1"}, "code": {"text": "Hypertension"}},
    ]
    payload = build_outputs(resources)
    files = export_markdown(payload, tmp_path)
    pearl_files = [p for p in files if p.name.startswith("PEARL-")]
    assert pearl_files
    assert "Source evidence" in pearl_files[0].read_text(encoding="utf-8")
    assert "Condition/c1" in pearl_files[0].read_text(encoding="utf-8")


def test_job_runner_runs_requested_job_not_oldest(tmp_path: Path):
    store = StudyStore(tmp_path / "jobs.sqlite3")
    runner = JobRunner(store)
    seen = []
    runner.register("one", lambda payload, checkpoint: seen.append(payload["value"]) or {"ok": True})
    old_id = store.create_job("one", {"value": "older"})
    target_id = store.create_job("one", {"value": "target"})
    assert runner.run_once(target_id) is True
    assert seen == ["target"]
    statuses = {job["id"]: job["status"] for job in store.jobs()}
    assert statuses[target_id] == "completed"
    assert statuses[old_id] == "queued"


def test_data_tools_status_and_mednotegen_queue_validation(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as client:
        status = client.get("/api/tools/status")
        assert status.status_code == 200
        assert status.json()["mednotegen"]["ready"] is True
        assert status.json()["specialty_harvest"]["specialty_count"] == 20
        bad = client.post("/api/tools/mednotegen/generate", json={"fhir_dir": str(tmp_path / "missing")})
        assert bad.status_code == 400


def test_specialty_harvester_records_license_and_review_status():
    from backend.hsptl_tools.specialty_harvest import extract_jats_license
    cc_by = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><permissions><license license-type="open-access" xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY 4.0</license-p></license></permissions></article-meta></front></article>'''
    result = extract_jats_license(cc_by)
    assert result["license_uri"].endswith("by/4.0/")
    assert result["license_status"] == "creative_commons_identified_verify_version"
    unknown = extract_jats_license(b"<article><front><article-meta/></front></article>")
    assert unknown["license_status"] == "unknown_requires_manual_review"


def test_tool_execution_service_queues_and_runs_only_registered_tool_jobs(tmp_path: Path):
    from backend.hsptl_tools.execution import ToolExecutionService
    store = StudyStore(tmp_path / "tool-jobs.sqlite3")
    runner = JobRunner(store)
    runner.register("mednotegen_generate", lambda payload, checkpoint: {"done": payload["value"]})
    service = ToolExecutionService(store, runner)
    job_id = service.enqueue("mednotegen_generate", {"value": 7})
    assert service.get_job(job_id)["status"] == "queued"
    assert service.run_once(job_id) is True
    assert service.get_job(job_id)["result"]["done"] == 7
    try:
        service.enqueue("arbitrary", {})
        assert False, "unsupported tool jobs must be rejected"
    except ValueError:
        pass


def test_mednotegen_service_preserves_synthetic_ucks_ingestion_contract(tmp_path: Path):
    from backend.hsptl_tools.mednotegen.service import MedNoteGenService
    from backend.hsptl_core.ucks import UCKSRepository
    source = tmp_path / "fhir"
    source.mkdir()
    (source / "bundle.json").write_text(json.dumps({"resourceType": "Bundle", "entry": [
        {"resource": {"resourceType": "Patient", "id": "p-test", "birthDate": "1980-01-01"}}
    ]}), encoding="utf-8")
    store = StudyStore(tmp_path / "mednote.sqlite3")
    service = MedNoteGenService(lambda: UCKSRepository(store))
    result = service.generate(source, tmp_path / "out")
    assert result["clinic_notes"] == 1
    assert result["ucks_ingestion_contract"]["channel"] == "synthea_mednotegen"
    assert result["ucks_ingestion_contract"]["synthetic"] is True
    assert result["ucks_ingestion_contract"]["review_status"] == "harvested"


def test_specialty_harvest_service_is_in_process_and_validates_before_execution(tmp_path: Path, monkeypatch):
    from backend.hsptl_tools.specialty_harvest import service as harvest_service
    calls = []
    monkeypatch.setattr(harvest_service, "engine_main", lambda argv: calls.append(argv))
    service = harvest_service.SpecialtyHarvestService()
    result = service.run({"specialties": ["cardiology"], "max_cases_per_specialty": 3}, tmp_path / "harvest")
    assert calls and "--only" in calls[0]
    assert result["tool"] == "Specialty Harvest"
    assert result["article_count"] == 0
    try:
        service.run({"specialties": ["not-a-specialty"]}, tmp_path / "bad")
        assert False, "invalid specialty must be rejected"
    except ValueError:
        pass


def test_data_tools_monitoring_exposes_ucks_and_job_counts():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as client:
        response = client.get("/api/tools/monitoring")
        assert response.status_code == 200
        payload = response.json()
        assert "documents" in payload["ucks"]
        assert "clinical_harvester" in payload["ingestion_channels"]


def test_cooperative_tool_cancellation_is_not_requeued(tmp_path: Path):
    store = StudyStore(tmp_path / "cancel.sqlite3")
    runner = JobRunner(store)
    job_id = store.create_job("long_tool", {})
    def handler(payload, checkpoint):
        runner.request_cancel(job_id)
        assert checkpoint({"phase": "working"}) is False
        raise RuntimeError("cancelled at checkpoint")
    runner.register("long_tool", handler)
    runner.run_once(job_id)
    job = next(item for item in store.jobs() if item["id"] == job_id)
    assert job["status"] == "cancelled"


def test_clinical_knowledge_harvester_profiles_generate_distinct_open_access_queries():
    from backend.hsptl_tools.specialty_harvest.query_builder import query_for
    cases = query_for("cardiology", 2020, 2025, "case_reports")
    guidelines = query_for("cardiology", 2020, 2025, "guidelines")
    evidence = query_for("cardiology", 2020, 2025, "clinical_evidence")
    assert 'PUB_TYPE:"Case Reports"' in cases
    assert 'PUB_TYPE:"Guideline"' in guidelines
    assert 'PUB_TYPE:"Systematic Review"' in evidence
    assert 'OPEN_ACCESS:y AND HAS_FT:y' in guidelines
    assert 'PUB_YEAR:[2020 TO 2025]' in evidence
    assert cases != guidelines


def test_harvester_provider_modules_are_decomposed_and_legacy_imports_remain():
    from backend.hsptl_tools.specialty_harvest import EuropePMCSource, CrossrefSource, main
    from backend.hsptl_tools.specialty_harvest.providers.europe_pmc import EuropePMCSource as ModularEuropePMC
    assert EuropePMCSource is ModularEuropePMC
    assert CrossrefSource.name == "crossref"
    assert callable(main)


def test_ucks_governance_snapshot_reports_review_and_rights_queues(tmp_path):
    from backend.hsptl_core.ucks_monitoring import governance_snapshot
    from backend.hsptl_core.ucks import UCKSRepository
    store = StudyStore(tmp_path / "governance.sqlite3")
    repo = UCKSRepository(store)
    source = repo.register_source(name="Governance source", source_type="external_import")
    repo.ingest_document(source_id=source["id"], title="Unreviewed guideline",
                         body="Guideline evidence body.", content_type="guideline")
    snapshot = governance_snapshot(store, repo)
    assert snapshot["documents"]["review_status"]["harvested"] == 1
    assert snapshot["documents"]["content_types"]["guideline"] == 1
    assert snapshot["rights_and_provenance"]["documents_without_declared_licence"] == 1
    assert snapshot["policy"]["automatic_validation"] is False


def test_provider_health_is_not_probed_until_explicit_request(tmp_path):
    from backend.hsptl_tools.provider_health import get_provider_health
    store = StudyStore(tmp_path / "provider-health.sqlite3")
    result = get_provider_health(store, probe=False)
    assert result["probed"] is False
    assert {item["id"] for item in result["items"]} >= {"europe_pmc", "pubmed", "crossref", "clinicaltrials_gov"}
    assert all(item["status"] == "not_probed" for item in result["items"])


def test_data_tools_exposes_provider_health_and_governance_monitoring():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as client:
        health = client.get("/api/tools/providers/health")
        health_history = client.get("/api/tools/providers/health/history")
        governance = client.get("/api/tools/ucks/governance")
        assert health.status_code == 200
        assert health.json()["probed"] is False
        assert health_history.status_code == 200
        assert "items" in health_history.json()
        assert governance.status_code == 200
        payload = governance.json()
        assert "review_status" in payload["documents"]
        assert "governance_queues" in payload
        assert payload["policy"]["automatic_validation"] is False


def test_provider_health_persists_history_and_emits_repeated_failure_alert(tmp_path):
    from backend.hsptl_tools.provider_health import (
        get_provider_health, get_provider_health_history, record_provider_health,
    )
    store = StudyStore(tmp_path / "provider-history.sqlite3")
    record_provider_health(store, "pubmed", status="unhealthy", http_status=503, latency_ms=900, error_code="HTTP_503")
    record_provider_health(store, "pubmed", status="degraded", http_status=429, latency_ms=300, error_code="HTTP_429")
    snapshot = get_provider_health(store)
    pubmed = next(item for item in snapshot["items"] if item["id"] == "pubmed")
    assert pubmed["alert"] == "repeated_provider_failure"
    assert len(pubmed["recent_statuses"]) == 2
    history = get_provider_health_history(store, provider_id="pubmed")
    assert len(history["items"]) == 2


def test_profile_aware_pubmed_and_doaj_queries_are_distinct():
    from backend.hsptl_tools.specialty_harvest.query_builder import pubmed_query_for, doaj_query_for
    guidelines = pubmed_query_for("cardiology", 2020, 2025, "guidelines")
    trials = pubmed_query_for("cardiology", 2020, 2025, "trials")
    assert '"Guideline"[Publication Type]' in guidelines
    assert '"Clinical Trial"[Publication Type]' in trials
    assert "free full text[sb]" in guidelines
    assert guidelines != trials
    from backend.hsptl_tools.specialty_harvest.query_builder import pmc_query_for
    assert "open access[filter]" in pmc_query_for("cardiology", 2020, 2025, "guidelines")
    assert "systematic review" in doaj_query_for("cardiology", None, None, "systematic_reviews")


def test_pubmed_provider_extracts_stable_ids_and_publication_type(monkeypatch):
    import json
    from types import SimpleNamespace
    from backend.hsptl_tools.specialty_harvest.providers import pubmed
    def fake_ncbi(endpoint, params):
        if endpoint == "esearch.fcgi" and params.get("retmax") == 0:
            return json.dumps({"esearchresult": {"count": "1"}}).encode()
        if endpoint == "esearch.fcgi":
            return json.dumps({"esearchresult": {"idlist": ["12345"]}}).encode()
        if endpoint == "esummary.fcgi":
            return json.dumps({"result": {"12345": {"title": "A cardiac guideline", "pubdate": "2024 Jan", "fulljournalname": "Test Journal", "pubtype": ["Guideline"], "articleids": [{"idtype": "doi", "value": "10.1000/example"}, {"idtype": "pmc", "value": "PMC123"}]}}}).encode()
        if endpoint == "efetch.fcgi":
            return b"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><Abstract><AbstractText>Guideline abstract.</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        raise AssertionError(endpoint)
    monkeypatch.setattr(pubmed, "ncbi_get", fake_ncbi)
    args = SimpleNamespace(year_from=2020, year_to=2025, knowledge_profile="guidelines", max_per_source=5)
    records = list(pubmed.PubMedSource().search("cardiology", args))
    assert len(records) == 1
    assert records[0].pmid == "12345"
    assert records[0].pmcid == "PMC123"
    assert records[0].doi == "10.1000/example"
    assert records[0].content_type == "guideline"
    assert records[0].abstract == "Guideline abstract."


def test_harvester_full_text_license_allowlist_is_conservative():
    from backend.hsptl_tools.specialty_harvest.licensing import reuse_allowlisted
    assert reuse_allowlisted({"license_uri": "https://creativecommons.org/licenses/by/4.0/"})
    assert reuse_allowlisted({"license_uri": "https://creativecommons.org/licenses/by-sa/4.0/"})
    assert reuse_allowlisted({"license_uri": "https://creativecommons.org/publicdomain/zero/1.0/"})
    assert not reuse_allowlisted({"license_uri": "https://creativecommons.org/licenses/by-nc/4.0/"})
    assert not reuse_allowlisted({"license_uri": "https://creativecommons.org/licenses/by-nd/4.0/"})
    assert not reuse_allowlisted({"license_uri": ""})


def test_harvester_does_not_persist_full_text_without_allowlisted_jats_license(monkeypatch, tmp_path):
    from backend.hsptl_tools.specialty_harvest import acquisition
    from backend.hsptl_tools.specialty_harvest.models import Candidate
    xml = b'''<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><permissions><license xlink:href="https://publisher.example/terms"><license-p>Publisher terms apply.</license-p></license></permissions></article-meta></front><body><sec><p>Full text must not be retained.</p></sec></body></article>'''
    monkeypatch.setattr(acquisition, "resolve_pmcid_to_jats", lambda *args, **kwargs: xml)
    monkeypatch.setattr(acquisition.time, "sleep", lambda *_: None)
    candidate = Candidate(source="pubmed", title="Clinical article", abstract="Available abstract.",
                          pmcid="PMC999", pmid="999", knowledge_profile="guidelines", content_type="guideline")
    result = acquisition.download_candidate(candidate, tmp_path, 0)
    record = tmp_path / "PMC999"
    assert result == "metadata_only_rights"
    assert not (record / "article.xml").exists()
    assert (record / "meta.json").exists()


def test_ucks_scheduler_runs_feed_connector_and_provider_health_checks(monkeypatch, capsys):
    import runpy
    import sys
    calls = []
    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"ok": True}
    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        return Response()
    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return Response()
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr(sys, "argv", ["run_ucks_scheduler.py", "--base-url", "http://127.0.0.1:8000"])
    namespace = runpy.run_path("scripts/run_ucks_scheduler.py", run_name="ucks_scheduler_test")
    assert namespace["main"]() == 0
    assert [call[0] for call in calls] == ["POST", "POST", "GET"]
    assert calls[-1][1].endswith("/api/tools/providers/health")
    assert calls[-1][2]["params"] == {"probe": "true"}
    assert '"provider_health"' in capsys.readouterr().out


def test_ucks_scheduler_loop_mode_repeats_and_stops_cleanly(monkeypatch, capsys):
    import runpy
    import sys
    class Response:
        def raise_for_status(self):
            return None
        def json(self):
            return {"ok": True}
    calls = []
    monkeypatch.setattr("requests.post", lambda *a, **k: (calls.append(a[0]) or Response()))
    monkeypatch.setattr("requests.get", lambda *a, **k: (calls.append(a[0]) or Response()))
    def stop_after_one_cycle(_seconds):
        raise KeyboardInterrupt
    monkeypatch.setattr("time.sleep", stop_after_one_cycle)
    monkeypatch.setattr(sys, "argv", ["run_ucks_scheduler.py", "--loop", "--interval-minutes", "5"])
    namespace = runpy.run_path("scripts/run_ucks_scheduler.py", run_name="ucks_scheduler_loop_test")
    assert namespace["main"]() == 0
    assert len(calls) == 3
    assert "scheduler stopped" in capsys.readouterr().out


def test_port_config_resolves_default_override_and_rejects_invalid(monkeypatch):
    from backend.hsptl_core.config import (
        DEFAULT_DEV_PORT,
        DEFAULT_PORT,
        resolve_dev_port,
        resolve_port,
    )

    monkeypatch.delenv("HSPTL_PORT", raising=False)
    monkeypatch.delenv("HSPTL_DEV_PORT", raising=False)
    assert resolve_port() == DEFAULT_PORT
    assert resolve_dev_port() == DEFAULT_DEV_PORT
    assert resolve_port(9123) == 9123

    monkeypatch.setenv("HSPTL_PORT", "8123")
    monkeypatch.setenv("HSPTL_DEV_PORT", "5199")
    assert resolve_port() == 8123
    assert resolve_dev_port() == 5199

    # Blank means "unset", not an error.
    monkeypatch.setenv("HSPTL_PORT", "  ")
    assert resolve_port() == DEFAULT_PORT

    for bad in ("abc", "0", "65536", "-1"):
        monkeypatch.setenv("HSPTL_PORT", bad)
        try:
            resolve_port()
        except ValueError as exc:
            assert "HSPTL_PORT" in str(exc)
        else:
            raise AssertionError(f"HSPTL_PORT={bad!r} should have been rejected")


def _check_port_module():
    import runpy

    return runpy.run_path("scripts/check_port.py", run_name="check_port_test")


def _closed_server_in_time_wait(port):
    """Bind, accept, then close so the port lingers in TIME_WAIT."""
    import socket

    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    client = socket.create_connection(("127.0.0.1", port))
    conn, _ = srv.accept()
    conn.close()
    client.close()
    srv.close()


def test_port_probe_accepts_time_wait_port(monkeypatch):
    """A port left in TIME_WAIT must not be reported as a clash.

    uvicorn binds with SO_REUSEADDR, so it starts fine on such a port. A probe
    that binds without SO_REUSEADDR would report a false clash and block a
    perfectly good launch, which is exactly what happened after a quick restart.
    """
    import socket

    mod = _check_port_module()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    _closed_server_in_time_wait(port)

    assert mod["is_listening"]("127.0.0.1", port) is False
    assert mod["port_is_free"]("127.0.0.1", port) is True

    monkeypatch.setenv("HSPTL_PORT", str(port))
    assert mod["main"]([]) == 0


def test_check_port_reports_occupied_port(monkeypatch, capsys):
    import socket

    mod = _check_port_module()
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        listener.listen(5)

        assert mod["port_is_free"]("127.0.0.1", port) is False
        monkeypatch.setenv("HSPTL_PORT", str(port))
        assert mod["main"]([]) == 1
        captured = capsys.readouterr()
        # stdout stays empty so the launcher sees no port and stops.
        assert captured.out == ""
        assert f"127.0.0.1:{port} is used by another program" in captured.err
        assert "netstat -ano" in captured.err
        assert "taskkill /PID" in captured.err
        assert "HSPTL_PORT" in captured.err


def test_check_port_recognises_running_hsptl(monkeypatch, capsys):
    import http.server
    import json
    import socket
    import threading

    mod = _check_port_module()

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"ok": True, "name": "HSPTL"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = http.server.HTTPServer(("127.0.0.1", port), Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert mod["looks_like_hsptl"]("127.0.0.1", port) is True
        monkeypatch.setenv("HSPTL_PORT", str(port))
        assert mod["main"]([]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert f"HSPTL is already running on 127.0.0.1:{port}" in captured.err
        assert f"http://127.0.0.1:{port}" in captured.err
    finally:
        server.shutdown()
        server.server_close()


def test_reserved_port_message_does_not_suggest_killing_a_process():
    """A Windows-reserved port has no process to kill, so never say taskkill."""
    mod = _check_port_module()
    message = mod["_clash_message"](
        8000,
        mod["PortUnavailable"]("access denied", reserved=True),
        listening=False,
        is_hsptl=False,
    )
    assert "reserved" in message
    assert "excludedportrange" in message
    assert "taskkill" not in message


def test_check_port_rejects_invalid_override_without_probing(monkeypatch, capsys):
    mod = _check_port_module()
    monkeypatch.setenv("HSPTL_PORT", "not-a-port")
    assert mod["main"]([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HSPTL_PORT" in captured.err
