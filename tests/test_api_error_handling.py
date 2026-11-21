from __future__ import annotations

import sqlite3

import requests
from fastapi.testclient import TestClient

import backend.main as backend_main


def _raise_timeout(*args, **kwargs):
    raise requests.Timeout("upstream timed out")


def test_unhandled_sqlite_errors_return_logged_structured_500(monkeypatch):
    logged: list[str] = []

    def fail_stats():
        raise sqlite3.OperationalError("private database detail")

    monkeypatch.setattr(backend_main.STORE, "stats", fail_stats)
    monkeypatch.setattr(backend_main.logger, "exception", lambda message, *args, **kwargs: logged.append(message))

    with TestClient(backend_main.app, raise_server_exceptions=False) as client:
        response = client.get("/api/bootstrap")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Database operation failed",
        "code": "database_error",
    }
    assert "private database detail" not in response.text
    assert any("Unhandled SQLite error" in message for message in logged)


def test_unexpected_errors_return_logged_sanitized_500(monkeypatch):
    logged: list[str] = []

    def fail_stats():
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(backend_main.STORE, "stats", fail_stats)
    monkeypatch.setattr(backend_main.logger, "exception", lambda message, *args, **kwargs: logged.append(message))

    with TestClient(backend_main.app, raise_server_exceptions=False) as client:
        response = client.get("/api/bootstrap")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected server error occurred",
        "code": "internal_error",
    }
    assert "private implementation detail" not in response.text
    assert any("Unhandled API error" in message for message in logged)


def test_europe_pmc_network_errors_return_logged_502(monkeypatch):
    logged: list[str] = []
    monkeypatch.setattr(backend_main, "europe_pmc_search", _raise_timeout)
    monkeypatch.setattr(backend_main.logger, "exception", lambda message, *args, **kwargs: logged.append(message))

    with TestClient(backend_main.app) as client:
        response = client.get("/api/specialties/cardiology/articles", params={"q": "heart failure"})
        note_response = client.post("/api/pearls/generate", json={
            "topic": "Heart failure",
            "use_local_pdfs": False,
            "use_open_access": True,
        })

    assert response.status_code == 502
    assert response.json()["detail"] == "Europe PMC search is temporarily unavailable"
    assert "Europe PMC article search failed" in logged
    assert note_response.status_code == 502
    assert "Pearls note generation could not reach Europe PMC" in logged


def test_commons_network_errors_return_logged_502(monkeypatch):
    logged: list[str] = []
    monkeypatch.setattr(backend_main, "commons_search_images", _raise_timeout)
    monkeypatch.setattr(backend_main.logger, "exception", lambda message, *args, **kwargs: logged.append(message))

    with TestClient(backend_main.app) as client:
        response = client.get("/api/specialties/cardiology/images", params={"q": "heart"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Wikimedia Commons search is temporarily unavailable"
    assert "Wikimedia Commons image search failed" in logged


def test_malformed_jats_is_logged_and_skipped(monkeypatch):
    warnings: list[tuple[str, bool]] = []
    monkeypatch.setattr(backend_main, "europe_pmc_search", lambda *args, **kwargs: [
        {"pmcid": "PMC1234567", "isOpenAccess": "Y", "title": "Test article"},
    ])
    monkeypatch.setattr(backend_main, "europe_pmc_fulltext_xml", lambda pmcid: "<article><body></article>")
    monkeypatch.setattr(
        backend_main.logger,
        "warning",
        lambda message, *args, **kwargs: warnings.append((message, kwargs.get("exc_info", False))),
    )

    with TestClient(backend_main.app) as client:
        response = client.post("/api/pearls/generate", json={
            "topic": "Respiratory approach",
            "use_local_pdfs": False,
            "use_open_access": True,
        })

    assert response.status_code == 200
    assert response.json()["local_reference_count"] == 0
    assert any("Skipped malformed JATS article" in message and exc_info for message, exc_info in warnings)
