from __future__ import annotations

import numpy as np
import pytest
import sqlite_vec

from tributary import embeddings, triage
from tributary.config import TriageConfig

PROFILE = TriageConfig(
    threshold=0.62,
    interests=["open source language models"],
    exclude=["cryptocurrency prices"],
    always_keep=["anthropic"],
    always_drop=["sponsored"],
)


# --- the decision rules (pure) -----------------------------------------------

def test_above_threshold_is_kept():
    assert triage.decide("A model", 0.70, 0.0, PROFILE).state == triage.KEPT


def test_below_threshold_is_dropped():
    decision = triage.decide("A model", 0.55, 0.0, PROFILE)
    assert decision.state == triage.REJECTED
    assert "below threshold" in decision.reason


def test_exclude_outvotes_a_passing_score():
    """Clearing the bar is not enough if the item is closer to something unwanted."""
    decision = triage.decide("Bitcoin hits a high", 0.65, 0.80, PROFILE)
    assert decision.state == triage.REJECTED
    assert "closer to excluded" in decision.reason


def test_always_keep_overrides_a_failing_score():
    decision = triage.decide("Anthropic ships something", 0.10, 0.0, PROFILE)
    assert decision.state == triage.KEPT
    assert "always_keep" in decision.reason


def test_always_drop_beats_always_keep():
    decision = triage.decide("Sponsored: Anthropic", 0.99, 0.0, PROFILE)
    assert decision.state == triage.REJECTED


def test_keyword_matching_is_case_insensitive():
    assert triage.decide("ANTHROPIC news", 0.1, 0.0, PROFILE).state == triage.KEPT


# --- profile fingerprinting --------------------------------------------------

def test_fingerprint_ignores_ordering():
    a = TriageConfig(interests=["x", "y"], exclude=["z"])
    b = TriageConfig(interests=["y", "x"], exclude=["z"])
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_tracks_the_threshold():
    a = TriageConfig(interests=["x"], threshold=0.6)
    b = TriageConfig(interests=["x"], threshold=0.7)
    assert a.fingerprint() != b.fingerprint()


def test_changing_the_profile_sends_everything_back_through_triage(conn, source_id):
    """Editing interests must re-judge the back catalogue, not just new items."""
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, triage_state, triage_score) "
        "VALUES (?, 'a', 'article', 'https://e.test/a', 'T', 'kept', 0.9)",
        (source_id,),
    )
    assert triage.reset_if_profile_changed(conn, PROFILE) is True
    row = conn.execute("SELECT triage_state, triage_score FROM items").fetchone()
    assert row["triage_state"] == "pending"
    assert row["triage_score"] is None

    # Same profile the second time: nothing to do.
    conn.execute("UPDATE items SET triage_state = 'kept'")
    assert triage.reset_if_profile_changed(conn, PROFILE) is False
    assert conn.execute("SELECT triage_state FROM items").fetchone()["triage_state"] == "kept"


# --- scoring over stored vectors ---------------------------------------------

def unit(*values) -> list[float]:
    """A normalised vector of the table's width, with `values` in the leading slots.

    Padding with zeros keeps the geometry of the leading dimensions exactly, so
    the cosines below are the ones the comments claim.
    """
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    return (vector / np.linalg.norm(vector)).tolist()


@pytest.fixture
def scored(conn, source_id, monkeypatch):
    """Three items at known angles to a one-dimensional interest profile."""
    vectors = {
        "on-topic": unit(1.0, 0.0),        # cosine 1.00 with the interest
        "off-topic": unit(0.3, 1.0),       # cosine 0.29
        "crypto": unit(0.0, 1.0),          # cosine 0.00, but 1.00 with exclude
    }
    for external_id, vector in vectors.items():
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title) "
            "VALUES (?, ?, 'article', 'https://e.test/x', ?)",
            (source_id, external_id, external_id),
        ).lastrowid
        conn.execute(
            "INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
            (item_id, sqlite_vec.serialize_float32(vector)),
        )

    def fake_embed(texts, model_name=None):
        table = {"open source language models": unit(1.0, 0.0),
                 "cryptocurrency prices": unit(0.0, 1.0)}
        return [table[t] for t in texts]

    monkeypatch.setattr(triage, "embed", fake_embed)
    return conn


def test_run_keeps_and_drops_by_similarity(scored):
    profile = TriageConfig(
        threshold=0.62,
        interests=["open source language models"],
        exclude=["cryptocurrency prices"],
    )
    result = triage.run(scored, profile)
    assert (result.kept, result.rejected) == (1, 2)

    verdicts = {
        r["external_id"]: r["triage_state"]
        for r in scored.execute("SELECT external_id, triage_state FROM items")
    }
    assert verdicts == {"on-topic": "kept", "off-topic": "rejected", "crypto": "rejected"}


def test_run_records_the_score(scored):
    profile = TriageConfig(threshold=0.62, interests=["open source language models"])
    triage.run(scored, profile)
    row = scored.execute(
        "SELECT triage_score FROM items WHERE external_id = 'on-topic'"
    ).fetchone()
    assert row["triage_score"] == pytest.approx(1.0, abs=1e-5)


def test_items_without_vectors_are_counted_not_judged(conn, source_id, monkeypatch):
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title) "
        "VALUES (?, 'no-vector', 'article', 'https://e.test/x', 'T')",
        (source_id,),
    )
    monkeypatch.setattr(triage, "embed", lambda texts, model_name=None: [unit(1.0, 0.0)])
    result = triage.run(conn, TriageConfig(interests=["anything"]))
    assert result.total == 0
    assert result.skipped == 1


def test_a_profile_with_no_interests_is_rejected(conn):
    with pytest.raises(ValueError, match="no interests"):
        triage.run(conn, TriageConfig())


def test_explain_names_the_matching_interest(scored):
    profile = TriageConfig(
        threshold=0.62,
        interests=["open source language models"],
        exclude=["cryptocurrency prices"],
    )
    triage.run(scored, profile)
    item_id = scored.execute("SELECT id FROM items WHERE external_id = 'crypto'").fetchone()["id"]

    detail = triage.explain(scored, profile, item_id)
    assert detail["state"] == triage.REJECTED
    assert detail["exclude_score"] == pytest.approx(1.0, abs=1e-5)
    assert detail["best_interest"] == "open source language models"


# --- model guard -------------------------------------------------------------

def test_switching_embedding_models_is_refused(conn):
    embeddings.check_model(conn, "model-a")
    with pytest.raises(RuntimeError, match="not comparable"):
        embeddings.check_model(conn, "model-b")
