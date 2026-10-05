from __future__ import annotations

import numpy as np
import pytest
import sqlite_vec
from fastapi.testclient import TestClient

from tributary import api, cluster, embeddings
from tributary import db as db_mod
from tributary.api import create_app


def unit(*values) -> bytes:
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    vector /= np.linalg.norm(vector)
    return sqlite_vec.serialize_float32(vector.tolist())


@pytest.fixture
def client(tmp_path):
    """A live app over a small seeded database."""
    db_path = tmp_path / "t.db"
    conn = db_mod.connect(db_path)
    db_mod.migrate(conn)

    source_id = conn.execute(
        "INSERT INTO sources (kind, name, url) VALUES ('rss', 'Test Feed', 'https://e.test')"
    ).lastrowid

    def add(n, title, kind="article", vector=(1.0,), at="2026-09-15T00:00:00Z", arxiv=None):
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, summary, "
            "published_at, triage_state, triage_score, content_hash, embedded_hash) "
            "VALUES (?, ?, ?, ?, ?, 'A summary.', ?, 'kept', 0.8, 'h', 'h')",
            (source_id, f"e{n}", kind, f"https://e.test/{n}", title, at),
        ).lastrowid
        conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                     (item_id, unit(*vector)))
        if arxiv:
            conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, 'arxiv', ?)",
                         (item_id, arxiv))
        return item_id

    add(1, "A paper about models", kind="paper", vector=(1.0, 0.0), arxiv="2609.1")
    add(2, "Coverage of that paper", vector=(0.0, 1.0), arxiv="2609.1")
    add(3, "Something unrelated", kind="discussion", vector=(0.0, 0.0, 1.0))
    cluster.run(conn)
    conn.close()

    config = tmp_path / "config.toml"
    config.write_text(f'[tributary]\ndb_path = "{db_path}"\n')

    with TestClient(create_app(config)) as test_client:
        yield test_client


def test_the_bundle_is_served_live(client):
    # A wide window: the seeded items are dated, and the default is 30 days.
    body = client.get("/data.json?days=365").json()
    assert len(body["stories"]) == 2  # the paper and its coverage merged into one story
    merged = next(s for s in body["stories"] if s["item_count"] > 1)
    assert merged["kind"] == "paper", "the lead of a merged story is the paper, not its coverage"


def test_status_reports_health(client):
    body = client.get("/api/status").json()
    assert body["kept"] == 3
    assert body["stories"] == 2
    assert body["broken_sources"] == []


def test_status_surfaces_a_broken_source(client, tmp_path):
    """A dead feed must be visible in the UI, not a silent gap."""
    conn = db_mod.connect(tmp_path / "t.db")
    conn.execute("UPDATE sources SET last_error = 'HTTP 404'")
    conn.close()

    broken = client.get("/api/status").json()["broken_sources"]
    assert broken and broken[0]["error"] == "HTTP 404"


def _app(tmp_path, monkeypatch, built: bool) -> TestClient:
    page = tmp_path / "dist"
    if built:
        page.mkdir()
        (page / "index.html").write_text("<title>Tributary</title>")
    monkeypatch.setattr(api, "APP_DIR", page)
    config = tmp_path / "config.toml"
    config.write_text(f'[tributary]\ndb_path = "{tmp_path / "x.db"}"\n')
    return TestClient(create_app(config))


def test_the_built_page_is_served_at_the_root(tmp_path, monkeypatch):
    with _app(tmp_path, monkeypatch, built=True) as c:
        assert "<title>Tributary</title>" in c.get("/").text
        assert c.get("/api/next/ping").json() == {"ok": True}


def test_an_unbuilt_page_says_how_to_build_it(tmp_path, monkeypatch):
    with _app(tmp_path, monkeypatch, built=False) as c:
        assert "npm run build" in c.get("/").text


def test_the_old_address_of_the_page_still_lands(tmp_path, monkeypatch):
    """It lived at /next/ while version 1 held the root."""
    with _app(tmp_path, monkeypatch, built=True) as c:
        moved = c.get("/next/", follow_redirects=False)
        assert moved.status_code == 301 and moved.headers["location"] == "/"


def test_api_routes_win_over_the_static_mount(client):
    """The catch-all static mount must not shadow /api/*."""
    assert client.get("/api/status").json()["stories"] == 2
