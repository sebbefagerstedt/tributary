from __future__ import annotations

import numpy as np
import sqlite_vec

from tributary import calibrate, embeddings


def unit(*values) -> bytes:
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    vector /= np.linalg.norm(vector)
    return sqlite_vec.serialize_float32(vector.tolist())


def add(conn, source_id, n, kind="paper", at="2026-09-15T00:00:00Z", vector=(1.0,), arxiv=None):
    item_id = conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, published_at, "
        "triage_state, content_hash, embedded_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, 'kept', 'h', 'h')",
        (source_id, f"e{n}", kind, f"https://e.test/{n}", f"Item {n}", at),
    ).lastrowid
    conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                 (item_id, unit(*vector)))
    if arxiv:
        conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, 'arxiv', ?)",
                     (item_id, arxiv))
    return item_id


def test_positives_are_pairs_sharing_a_strong_identifier(conn, source_id):
    add(conn, source_id, 1, arxiv="2609.1")
    add(conn, source_id, 2, arxiv="2609.1")
    add(conn, source_id, 3, arxiv="2609.9")

    pairs = calibrate.positives(conn)
    assert len(pairs) == 1  # only the shared id makes a pair


def test_an_over_shared_identifier_is_not_ground_truth(conn, source_id):
    """Above MAX_FANOUT the identifier is a category; its pairs are not positives."""
    for n in range(calibrate.identity.MAX_FANOUT + 2):
        add(conn, source_id, n, arxiv="2609.5")
    assert calibrate.positives(conn) == []


def test_hard_negatives_are_distinct_papers_close_in_time(conn, source_id):
    add(conn, source_id, 1, arxiv="2609.1", at="2026-09-15T00:00:00Z")
    add(conn, source_id, 2, arxiv="2609.2", at="2026-09-16T00:00:00Z")
    add(conn, source_id, 3, arxiv="2609.3", at="2026-12-01T00:00:00Z")  # far away

    pairs = calibrate.hard_negatives(conn)
    assert len(pairs) == 1  # only the two within a week of each other


def test_scores_are_cosine_similarity(conn, source_id):
    a = add(conn, source_id, 1, vector=(1.0, 0.0))
    b = add(conn, source_id, 2, vector=(0.0, 1.0))
    c = add(conn, source_id, 3, vector=(1.0, 0.0))

    scores = calibrate.score(conn, [(a, b), (a, c)])
    assert scores[0] == 0.0
    assert scores[1] > 0.999


def test_evaluate_reports_the_tradeoff_at_each_threshold(conn, source_id):
    # Two items that are the same story, worded differently (cosine ~0.995).
    add(conn, source_id, 1, arxiv="2609.1", vector=(1.0, 0.0))
    add(conn, source_id, 2, arxiv="2609.1", vector=(1.0, 0.1))
    # Two different papers that are merely similar.
    add(conn, source_id, 3, arxiv="2609.7", vector=(1.0, 0.4))
    add(conn, source_id, 4, arxiv="2609.8", vector=(1.0, 0.5))

    report = calibrate.evaluate(conn, [0.90, 0.999])
    low, high = report["thresholds"]

    assert low["recall"] == 1.0            # a loose threshold catches the match
    assert high["caught"] < low["caught"]  # a strict one does not
    assert low["false_merges"] >= high["false_merges"]


def test_evaluate_survives_an_empty_database(conn):
    report = calibrate.evaluate(conn, [0.9])
    assert report["distributions"]["positive"]["n"] == 0
    assert report["thresholds"][0]["recall"] == 0.0
