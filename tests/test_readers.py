from __future__ import annotations

import pytest

from tributary import readers, store
from tributary.config import SourceConfig


def fake_embed(texts):
    # A fixed direction per text is enough: tests check that a vector is stored
    # and reused, never what it means (CLAUDE.md: no model in tests).
    return [[1.0] + [0.0] * 383 for _ in texts]


def test_a_profile_is_just_a_name_and_comes_back_empty(conn):
    readers.ensure_profile(conn, "Sebastian")
    readers.ensure_profile(conn, "Sebastian")
    assert readers.list_profiles(conn) == ["Sebastian"]
    got = readers.get_profile(conn, "Sebastian")
    assert got == {
        "name": "Sebastian",
        "layout": "grid",
        "onboarded": False,
        "topics": [],
        "seen": [],
    }


def test_a_nameless_profile_is_refused(conn):
    with pytest.raises(readers.ReaderError):
        readers.ensure_profile(conn, "  ")


def test_a_starter_topic_keeps_its_sources_and_needs_no_vector(conn, source_id):
    readers.ensure_profile(conn, "S")
    saved = readers.save_topic(
        conn,
        "S",
        {
            "id": "agents",
            "name": "AI agents",
            "spine": "agents",
            "sources": ["Test Feed"],
            "muted": ["crypto"],
        },
        embed=fake_embed,
    )
    assert saved["sources"] == ["Test Feed"] and saved["muted"] == ["crypto"]
    assert saved["spine"] == "agents" and saved["vector"] is None


def test_a_topic_of_your_own_is_embedded_once(conn, source_id):
    readers.ensure_profile(conn, "S")
    calls = []

    def counting(texts):
        calls.append(list(texts))
        return fake_embed(texts)

    first = readers.save_topic(
        conn, "S", {"name": "AI video", "sources": ["Test Feed"]}, embed=counting
    )
    assert first["id"] == "ai-video" and first["vector"]
    readers.save_topic(
        conn, "S", {"id": "ai-video", "name": "AI video", "sources": []}, embed=counting
    )
    assert len(calls) == 1, "an unchanged description must not be embedded again"


def test_a_model_that_cannot_load_still_saves_the_topic(conn, source_id):
    readers.ensure_profile(conn, "S")

    def offline(texts):
        raise OSError("model download refused")

    saved = readers.save_topic(
        conn, "S", {"name": "Robot dogs", "sources": ["Test Feed"]}, embed=offline
    )
    assert saved["id"] == "robot-dogs" and saved["vector"] is None
    again = readers.save_topic(
        conn, "S", {"id": "robot-dogs", "name": "Robot dogs", "sources": ["Test Feed"]},
        embed=fake_embed,
    )
    assert again["vector"], "the next save tries the model again"


def test_a_source_a_reader_found_is_fetched_while_a_topic_uses_it(conn):
    readers.ensure_profile(conn, "S")
    spec = {"name": "Runway Blog", "url": "https://runway.test/feed", "kind": "rss"}
    readers.save_topic(conn, "S", {"name": "AI video", "sources": [spec]}, embed=fake_embed)

    row = conn.execute("SELECT enabled, origin FROM sources WHERE name = 'Runway Blog'").fetchone()
    assert (row["enabled"], row["origin"]) == (1, "reader")

    readers.delete_topic(conn, "S", "ai-video")
    assert (
        conn.execute("SELECT enabled FROM sources WHERE name = 'Runway Blog'").fetchone()["enabled"]
        == 0
    )


def test_the_config_sync_leaves_a_readers_source_alone(conn):
    readers.ensure_profile(conn, "S")
    readers.save_topic(
        conn,
        "S",
        {
            "name": "AI video",
            "sources": [{"name": "Runway Blog", "url": "https://runway.test/feed"}],
        },
        embed=fake_embed,
    )
    rows = store.sync_sources(
        conn, [SourceConfig(kind="rss", name="Config Feed", url="https://c.test/f")]
    )
    names = {r.name: r for r in rows}
    assert "Runway Blog" in names and names["Runway Blog"].origin == "reader"
    assert names["Runway Blog"].url == "https://runway.test/feed"


def test_only_feeds_and_sitemaps_can_be_added(conn):
    readers.ensure_profile(conn, "S")
    with pytest.raises(readers.ReaderError):
        readers.save_topic(
            conn,
            "S",
            {"name": "X", "sources": [{"name": "Odd", "url": "https://x.test", "kind": "github"}]},
            embed=fake_embed,
        )


def test_seen_is_per_profile_and_starting_over_clears_it(conn, source_id):
    readers.ensure_profile(conn, "A")
    readers.ensure_profile(conn, "B")
    readers.mark_seen(conn, "A", [3, 4, 3])
    assert readers.get_profile(conn, "A")["seen"] == [3, 4]
    assert readers.get_profile(conn, "B")["seen"] == []
    readers.save_topic(
        conn,
        "A",
        {"id": "agents", "name": "AI agents", "spine": "agents", "sources": ["Test Feed"]},
    )
    readers.update_profile(conn, "A", layout="cards", onboarded=True)
    readers.reset_profile(conn, "A")
    got = readers.get_profile(conn, "A")
    assert (
        got["topics"] == []
        and got["seen"] == []
        and not got["onboarded"]
        and got["layout"] == "cards"
    )


def test_a_topic_taught_by_a_story_takes_its_vector_not_the_descriptions(conn, source_id):
    """Following one event: the story's centroid, never an embedded headline."""
    import numpy as np
    import sqlite_vec

    item_id = conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, content_hash) "
        "VALUES (?, 'e1', 'article', 'https://e.test/1', 'Rogue agents on Wikimedia', 'h')",
        (source_id,),
    ).lastrowid
    vector = np.zeros(384, dtype=np.float32)
    vector[1] = 1.0
    conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                 (item_id, sqlite_vec.serialize_float32(vector.tolist())))
    story_id = conn.execute("INSERT INTO stories DEFAULT VALUES").lastrowid
    conn.execute("INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                 (story_id, item_id))
    readers.ensure_profile(conn, "S")
    calls = []

    saved = readers.save_topic(
        conn, "S",
        {"name": "Rogue agents", "description": "Rogue agents on Wikimedia",
         "sources": ["Test Feed"], "examples": [story_id]},
        embed=lambda texts: calls.append(texts) or fake_embed(texts),
    )
    assert saved["examples"] == [story_id]
    assert saved["vector"] == readers.pack(vector)
    assert calls == [], "a topic taught by a story never embeds its description"
