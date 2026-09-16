from __future__ import annotations

import numpy as np
import sqlite_vec

from tributary import cluster, embeddings, store


def vector() -> bytes:
    v = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    v[0] = 1.0
    return sqlite_vec.serialize_float32(v.tolist())


def add(conn, source_id, external_id, days_old):
    item_id = conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, published_at, "
        "triage_state, triage_score, content_hash, embedded_hash) "
        "VALUES (?, ?, 'article', 'https://e.test', ?, datetime('now', ?), "
        "'kept', 0.8, 'h', 'h')",
        (source_id, external_id, external_id, f"-{days_old} days"),
    ).lastrowid
    conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                 (item_id, vector()))
    conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, 'url', ?)",
                 (item_id, f"https://e.test/{external_id}"))
    return item_id


def test_old_items_go_and_recent_ones_stay(conn, source_id):
    add(conn, source_id, "old", 120)
    add(conn, source_id, "recent", 5)

    result = store.prune(conn, days=60)
    assert result["items"] == 1
    remaining = [r["external_id"] for r in conn.execute("SELECT external_id FROM items")]
    assert remaining == ["recent"]


def test_vectors_are_cleared_too(conn, source_id):
    """item_vectors is a virtual table, so foreign keys do not cascade to it.

    Vectors are the bulk of the database; leaving them behind made pruning
    nearly pointless and let the database grow without bound.
    """
    add(conn, source_id, "old", 120)
    add(conn, source_id, "recent", 5)

    result = store.prune(conn, days=60)
    assert result["vectors"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM item_vectors").fetchone()["c"] == 1
    orphans = conn.execute(
        "SELECT COUNT(*) c FROM item_vectors WHERE item_id NOT IN (SELECT id FROM items)"
    ).fetchone()["c"]
    assert orphans == 0


def test_pre_existing_orphans_are_swept_up(conn, source_id):
    """Databases pruned by the buggy version still carry orphans."""
    item_id = add(conn, source_id, "recent", 5)
    conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)", (9999, vector()))

    store.prune(conn, days=60)
    rows = [r["item_id"] for r in conn.execute("SELECT item_id FROM item_vectors")]
    assert rows == [item_id]


def test_identifiers_cascade_with_the_item(conn, source_id):
    add(conn, source_id, "old", 120)
    store.prune(conn, days=60)
    assert conn.execute("SELECT COUNT(*) c FROM identifiers").fetchone()["c"] == 0


def test_empty_stories_are_removed(conn, source_id):
    add(conn, source_id, "old", 120)
    add(conn, source_id, "recent", 5)
    cluster.run(conn)
    assert cluster.stats(conn)["stories"] == 2

    result = store.prune(conn, days=60)
    assert result["stories"] == 1
    assert cluster.stats(conn)["stories"] == 1


def test_saved_stories_survive_by_default(conn, source_id):
    """Deleting something deliberately kept is the one unrecoverable thing here."""
    add(conn, source_id, "old", 120)
    cluster.run(conn)
    story_id = conn.execute("SELECT id FROM stories").fetchone()["id"]
    conn.execute("INSERT INTO interactions (story_id, action) VALUES (?, 'saved')", (story_id,))

    assert store.prune(conn, days=60)["items"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 1


def test_saved_stories_can_be_pruned_explicitly(conn, source_id):
    add(conn, source_id, "old", 120)
    cluster.run(conn)
    story_id = conn.execute("SELECT id FROM stories").fetchone()["id"]
    conn.execute("INSERT INTO interactions (story_id, action) VALUES (?, 'saved')", (story_id,))

    assert store.prune(conn, days=60, keep_saved=False)["items"] == 1


def test_pruning_an_empty_database_is_a_no_op(conn):
    assert store.prune(conn, days=60) == {"items": 0, "stories": 0, "vectors": 0}
