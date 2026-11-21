from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3
import threading

from fastapi.testclient import TestClient

from backend.hsptl_core.puzzle_engine import build_puzzle_candidate
from backend.hsptl_core.store import StudyStore
from backend.main import app


def test_backup_endpoint_returns_a_valid_sqlite_database(tmp_path, monkeypatch):
    from backend.main import PATHS, STORE

    monkeypatch.setitem(PATHS, "root", tmp_path)
    STORE.save_note("Coverage test", "Backup endpoint", "Committed test record")

    with TestClient(app) as client:
        response = client.post("/api/system/backup")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/vnd.sqlite3")
    backup_path = tmp_path / "downloaded-backup.sqlite3"
    backup_path.write_bytes(response.content)
    connection = sqlite3.connect(backup_path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        row = connection.execute(
            "SELECT body FROM study_notes WHERE category=? AND title=?",
            ("Coverage test", "Backup endpoint"),
        ).fetchone()
    finally:
        connection.close()
    assert row == ("Committed test record",)


def test_data_connect_rejects_a_malformed_csv_folder(tmp_path, monkeypatch):
    from backend.main import PATHS

    source = tmp_path / "malformed"
    source.mkdir()
    (source / "Patient.csv").write_text('id,gender\n"unterminated,male\n', encoding="utf-8")
    monkeypatch.setitem(PATHS, "imports", tmp_path)

    with TestClient(app) as client:
        response = client.post("/api/data/connect", json={"path": str(source)})

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Could not load that dataset")


def test_frontend_fallback_rejects_encoded_path_traversal(tmp_path, monkeypatch):
    import backend.main as backend_main

    frontend_dist = tmp_path / "frontend-dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html>safe fallback</html>", encoding="utf-8")
    monkeypatch.setattr(backend_main, "FRONTEND_DIST", frontend_dist)

    with TestClient(app) as client:
        response = client.get("/..%2F..%2Fetc%2Fpasswd")

    assert response.status_code == 404
    assert "safe fallback" not in response.text


def test_study_store_supports_concurrent_reads_and_writes_in_wal_mode(tmp_path):
    store = StudyStore(tmp_path / "concurrent.sqlite3")
    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].casefold() == "wal"

    workers = 4
    writes_per_worker = 10
    start = threading.Barrier(workers)

    def write_and_read(worker_id: int) -> int:
        start.wait(timeout=10)
        for item_id in range(writes_per_worker):
            title = f"{worker_id}-{item_id}"
            store.save_note("Concurrent", title, f"content {title}")
            assert store.notes("Concurrent", limit=5)
        return writes_per_worker

    with ThreadPoolExecutor(max_workers=workers) as executor:
        completed = list(executor.map(write_and_read, range(workers)))

    notes = store.notes("Concurrent")
    assert sum(completed) == workers * writes_per_worker
    assert len(notes) == workers * writes_per_worker
    assert len({note["title"] for note in notes}) == workers * writes_per_worker


def test_puzzle_license_gate_rejects_cc_by_nd_article(monkeypatch):
    import backend.hsptl_core.puzzle_engine as puzzle_engine

    article_xml = b"""\
    <article xmlns:xlink="http://www.w3.org/1999/xlink">
      <front><article-meta><permissions>
        <license xlink:href="https://creativecommons.org/licenses/by-nd/4.0/">
          <license-p>CC BY-ND 4.0</license-p>
        </license>
      </permissions></article-meta></front>
    </article>
    """

    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield article_xml

        def close(self):
            pass

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(puzzle_engine, "_session", FakeSession)
    candidate = build_puzzle_candidate({
        "pmcid": "PMC1234567",
        "title": "Restricted adaptation test",
        "isOpenAccess": "Y",
    })

    assert candidate["eligible"] is False
    assert candidate["licence"] == ""
    assert any("No-derivatives" in reason for reason in candidate["reasons"])
