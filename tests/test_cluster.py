from __future__ import annotations

import json

import numpy as np
import pytest
import sqlite_vec

from tributary import cluster, embeddings


def unit(*values) -> bytes:
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    vector /= np.linalg.norm(vector)
    return sqlite_vec.serialize_float32(vector.tolist())


@pytest.fixture
def make(conn, source_id):
    """Insert a kept, embedded item and optionally its identifiers."""
    counter = {"n": 0}

    def _make(title, kind="article", at="2026-09-15T00:00:00Z", vector=(1.0,), identifiers=(),
              source=None, metadata=None):
        counter["n"] += 1
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, published_at, "
            "triage_state, triage_score, content_hash, embedded_hash, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, 'kept', 0.8, 'h', 'h', ?)",
            (source or source_id, f"e{counter['n']}", kind, f"https://e.test/{counter['n']}",
             title, at, json.dumps(metadata or {})),
        ).lastrowid
        conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                     (item_id, unit(*vector)))
        for kind_, value in identifiers:
            conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, ?, ?)",
                         (item_id, kind_, value))
        return item_id

    return _make


def story_of(conn, item_id):
    row = conn.execute("SELECT story_id FROM story_items WHERE item_id = ?", (item_id,)).fetchone()
    return row["story_id"] if row else None


# --- tier 1: identifiers -----------------------------------------------------

def test_a_shared_strong_identifier_merges(conn, make):
    a = make("Paper, as published", kind="paper", identifiers=[("arxiv", "2609.1")])
    b = make("Blog post about it", vector=(0.0, 1.0), identifiers=[("arxiv", "2609.1")])

    cluster.run(conn)
    assert story_of(conn, a) == story_of(conn, b)


def test_identifier_merge_beats_dissimilar_text(conn, make):
    """The point of tier 1: it works where similarity cannot."""
    a = make("Attention Is All You Need", kind="paper", identifiers=[("arxiv", "2609.2")])
    b = make("Cooking with tomatoes", vector=(0.0, 0.0, 1.0),
             identifiers=[("arxiv", "2609.2")])

    result = cluster.run(conn)
    assert story_of(conn, a) == story_of(conn, b)
    assert result.joined_by_identifier == 1
    assert result.joined_by_similarity == 0


def test_a_weak_identifier_does_not_merge(conn, make):
    """A repo is referenced by many unrelated stories."""
    a = make("vLLM adds a feature", vector=(1.0,), identifiers=[("github_repo", "v/vllm")])
    b = make("Unrelated vLLM benchmark", vector=(0.0, 1.0),
             identifiers=[("github_repo", "v/vllm")])

    cluster.run(conn)
    assert story_of(conn, a) != story_of(conn, b)


def test_an_over_shared_identifier_is_ignored(conn, make):
    """Above MAX_FANOUT an identifier describes a category, not an event."""
    count = cluster.identity.MAX_FANOUT + 2
    ids = [
        make(f"Item {n}", vector=(1.0, n * 0.9), identifiers=[("url", "https://e.test/shared")])
        for n in range(count)
    ]

    cluster.run(conn)
    stories = {story_of(conn, item_id) for item_id in ids}
    assert len(stories) > 1  # not collapsed into a single story


# --- tier 2: similarity ------------------------------------------------------

def test_near_identical_text_merges(conn, make):
    a = make("A new model is released", at="2026-09-15T00:00:00Z", vector=(1.0, 0.0))
    b = make("A new model is released", at="2026-09-15T06:00:00Z", vector=(1.0, 0.02))

    result = cluster.run(conn)
    assert story_of(conn, a) == story_of(conn, b)
    assert result.joined_by_similarity == 1


def test_similar_but_distinct_stays_separate(conn, make):
    """Topical neighbours must not merge; a wrong merge costs more than a miss."""
    a = make("RAG paper one", vector=(1.0, 0.0))
    b = make("RAG paper two", vector=(1.0, 0.5))  # cosine ~0.89: the ambiguous band

    result = cluster.run(conn)
    assert story_of(conn, a) != story_of(conn, b)
    assert len(result.ambiguous) == 1


def test_the_time_window_separates_recurrences(conn, make):
    """The same headline a year apart is two events, not one."""
    a = make("Quarterly model update", at="2026-01-01T00:00:00Z", vector=(1.0, 0.0))
    b = make("Quarterly model update", at="2026-09-01T00:00:00Z", vector=(1.0, 0.0))

    cluster.run(conn)
    assert story_of(conn, a) != story_of(conn, b)


# --- roles and story state ---------------------------------------------------

def test_role_follows_kind():
    assert cluster.role_for("paper", story_has_seed=False) == cluster.PAPER
    assert cluster.role_for("repo", story_has_seed=False) == cluster.CODE
    assert cluster.role_for("discussion", story_has_seed=False) == cluster.DISCUSSION


def test_an_article_leads_only_when_nothing_else_does():
    assert cluster.role_for("article", story_has_seed=False) == cluster.SEED
    assert cluster.role_for("article", story_has_seed=True) == cluster.COVERAGE


def test_more_coverage_does_not_count_as_a_material_update(conn, make):
    """Otherwise a story you have read resurfaces on every rehash."""
    seed = make("Model released", kind="model", identifiers=[("hf_model", "o/m")])
    cluster.run(conn)
    story_id = story_of(conn, seed)
    before = conn.execute(
        "SELECT materially_updated_at FROM stories WHERE id = ?", (story_id,)
    ).fetchone()["materially_updated_at"]

    make("Someone wrote about it", kind="article", at="2026-09-20T00:00:00Z",
         identifiers=[("hf_model", "o/m")])
    cluster.run(conn)

    after = conn.execute(
        "SELECT materially_updated_at, last_activity FROM stories WHERE id = ?", (story_id,)
    ).fetchone()
    assert after["materially_updated_at"] == before   # unchanged: no new artefact
    assert after["last_activity"] == "2026-09-20T00:00:00Z"


def test_a_new_artefact_is_a_material_update(conn, make):
    seed = make("Model released", kind="model", identifiers=[("hf_model", "o/m2")])
    cluster.run(conn)
    story_id = story_of(conn, seed)

    make("The paper", kind="paper", at="2026-09-20T00:00:00Z",
         identifiers=[("hf_model", "o/m2")])
    cluster.run(conn)

    row = conn.execute(
        "SELECT materially_updated_at FROM stories WHERE id = ?", (story_id,)
    ).fetchone()
    assert row["materially_updated_at"] == "2026-09-20T00:00:00Z"


def test_clustering_is_idempotent(conn, make):
    make("One", vector=(1.0, 0.0))
    make("Two", vector=(0.0, 1.0))
    first = cluster.run(conn)
    second = cluster.run(conn)

    assert first.assigned == 2
    assert second.assigned == 0  # nothing left unclustered


def test_only_kept_items_are_clustered(conn, source_id, make):
    make("Kept", vector=(1.0,))
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, triage_state, "
        "content_hash, embedded_hash) VALUES (?, 'r', 'article', 'https://e.test/r', "
        "'Rejected', 'rejected', 'h', 'h')",
        (source_id,),
    )
    cluster.run(conn)
    assert cluster.stats(conn)["items"] == 1


def test_reset_clears_stories(conn, make):
    make("One")
    cluster.run(conn)
    cluster.reset(conn)
    assert cluster.stats(conn)["stories"] == 0
    assert cluster.run(conn).assigned == 1  # re-clusterable
