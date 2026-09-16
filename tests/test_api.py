from __future__ import annotations

import numpy as np
import pytest
import sqlite_vec
from fastapi.testclient import TestClient

from tributary import cluster, embeddings
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


def test_feed_returns_ranked_stories(client):
    body = client.get("/api/feed").json()
    assert body["count"] == 2  # the paper and its coverage merged into one story
    scores = [s["score"] for s in body["stories"]]
    assert scores == sorted(scores, reverse=True)


def test_feed_cards_carry_what_the_ui_needs(client):
    card = client.get("/api/feed").json()["stories"][0]
    for field in ("story_id", "title", "kind", "source", "score", "signal", "seen", "sources"):
        assert field in card


def test_the_lead_of_a_merged_story_is_the_paper(client):
    """Not the coverage of it, even though both are in the story."""
    stories = client.get("/api/feed").json()["stories"]
    merged = next(s for s in stories if s["item_count"] > 1)
    assert merged["kind"] == "paper"


def test_limit_is_bounded(client):
    assert client.get("/api/feed?limit=0").status_code == 422
    assert client.get("/api/feed?limit=500").status_code == 422


def test_story_detail_lists_every_attached_item(client):
    story_id = client.get("/api/feed").json()["stories"][0]["story_id"]
    body = client.get(f"/api/story/{story_id}").json()
    assert len(body["items"]) == body["item_count"]
    assert {"role", "kind", "title", "url", "source"} <= set(body["items"][0])


def test_missing_story_is_a_404(client):
    assert client.get("/api/story/999999").status_code == 404


def test_actions_are_recorded(client):
    story_id = client.get("/api/feed").json()["stories"][0]["story_id"]
    assert client.post(f"/api/story/{story_id}/saved").status_code == 200
    assert client.get("/api/saved").json()["count"] == 1


def test_unknown_action_is_rejected(client):
    """The action name goes straight into a row; it must be checked."""
    story_id = client.get("/api/feed").json()["stories"][0]["story_id"]
    response = client.post(f"/api/story/{story_id}/wat")
    assert response.status_code == 400


def test_action_on_a_missing_story_is_a_404(client):
    assert client.post("/api/story/999999/saved").status_code == 404


def test_seen_stories_can_be_filtered_out(client):
    stories = client.get("/api/feed").json()["stories"]
    client.post(f"/api/story/{stories[0]['story_id']}/seen")

    remaining = client.get("/api/feed?unseen=true").json()
    assert remaining["count"] == len(stories) - 1


def test_dismissed_stories_drop_out_of_saved(client):
    story_id = client.get("/api/feed").json()["stories"][0]["story_id"]
    client.post(f"/api/story/{story_id}/saved")
    client.post(f"/api/story/{story_id}/dismissed")
    assert client.get("/api/saved").json()["count"] == 0


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


def test_the_app_shell_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>Tributary</title>" in response.text


def test_pwa_assets_are_served(client):
    assert client.get("/manifest.json").status_code == 200
    assert client.get("/sw.js").status_code == 200
    assert client.get("/icon.svg").status_code == 200


def test_api_routes_win_over_the_static_mount(client):
    """The catch-all static mount must not shadow /api/*."""
    assert client.get("/api/status").json()["stories"] == 2
