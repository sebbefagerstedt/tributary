"""Stage 2: triage.

A cheap relevance gate that runs before anything expensive. arXiv alone puts
hundreds of papers a day into the pipeline, and TechCrunch's AI feed carries
conference marketing; deciding what to drop has to cost approximately nothing,
which is why it runs on local embeddings rather than an LLM.

Scoring is max cosine similarity against a profile of interest sentences, with
an exclude profile that can outvote it and keyword lists that override both.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np

from tributary.config import TriageConfig
from tributary.db import transaction
from tributary.embeddings import DEFAULT_MODEL, embed

KEPT = "kept"
REJECTED = "rejected"
PENDING = "pending"


@dataclass(slots=True)
class TriageResult:
    kept: int = 0
    rejected: int = 0
    skipped: int = 0  # no vector yet

    @property
    def total(self) -> int:
        return self.kept + self.rejected


@dataclass(slots=True)
class Decision:
    state: str
    score: float
    reason: str


def _matches(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    return next((k for k in keywords if k in lowered), None)


def decide(
    title: str,
    score: float,
    exclude_score: float,
    profile: TriageConfig,
) -> Decision:
    """Apply the profile to one item. Pure, so the rules are testable in isolation."""
    if hit := _matches(title, profile.always_drop):
        return Decision(REJECTED, score, f"always_drop: {hit}")
    if hit := _matches(title, profile.always_keep):
        return Decision(KEPT, score, f"always_keep: {hit}")
    # An item closer to something explicitly unwanted than to anything wanted is
    # out, even if it clears the threshold on its own.
    if exclude_score > score:
        return Decision(REJECTED, score, f"closer to excluded ({exclude_score:.3f})")
    if score >= profile.threshold:
        return Decision(KEPT, score, f"similarity {score:.3f}")
    return Decision(REJECTED, score, f"below threshold ({score:.3f})")


def profile_vectors(profile: TriageConfig, model_name: str = DEFAULT_MODEL) -> tuple:
    """Embed the interest and exclude sentences. Returns (interests, excludes)."""
    if not profile.interests:
        raise ValueError("triage profile has no interests; nothing to compare against")
    interests = np.array(embed(profile.interests, model_name), dtype=np.float32)
    excludes = (
        np.array(embed(profile.exclude, model_name), dtype=np.float32)
        if profile.exclude
        else np.zeros((0, interests.shape[1]), dtype=np.float32)
    )
    return interests, excludes


def reset_if_profile_changed(conn: sqlite3.Connection, profile: TriageConfig) -> bool:
    """Send everything back through triage when the profile changes.

    Without this, editing your interests would only affect items fetched after
    the edit — the back catalogue would keep whatever verdict the old profile gave.
    """
    fingerprint = profile.fingerprint()
    row = conn.execute("SELECT value FROM meta WHERE key = 'triage_profile'").fetchone()
    if row and row["value"] == fingerprint:
        return False

    with transaction(conn):
        conn.execute("UPDATE items SET triage_state = ?, triage_score = NULL", (PENDING,))
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('triage_profile', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (fingerprint,),
        )
    return True


def run(
    conn: sqlite3.Connection,
    profile: TriageConfig,
    model_name: str = DEFAULT_MODEL,
    limit: int | None = None,
) -> TriageResult:
    """Score every pending item that has a vector."""
    interests, excludes = profile_vectors(profile, model_name)

    sql = """
        SELECT i.id, i.title, v.embedding
          FROM items i
          JOIN item_vectors v ON v.item_id = i.id
         WHERE i.triage_state = ?
         ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = list(conn.execute(sql, (PENDING,)))

    result = TriageResult()
    if not rows:
        result.skipped = conn.execute(
            "SELECT COUNT(*) c FROM items WHERE triage_state = ? AND embedded_hash IS NULL",
            (PENDING,),
        ).fetchone()["c"]
        return result

    vectors = np.frombuffer(b"".join(r["embedding"] for r in rows), dtype=np.float32)
    vectors = vectors.reshape(len(rows), -1)

    # Vectors are L2-normalised, so the dot product is cosine similarity.
    interest_scores = (vectors @ interests.T).max(axis=1)
    exclude_scores = (
        (vectors @ excludes.T).max(axis=1)
        if excludes.shape[0]
        else np.zeros(len(rows), dtype=np.float32)
    )

    with transaction(conn):
        for row, score, exclude_score in zip(rows, interest_scores, exclude_scores, strict=True):
            decision = decide(row["title"], float(score), float(exclude_score), profile)
            conn.execute(
                "UPDATE items SET triage_state = ?, triage_score = ? WHERE id = ?",
                (decision.state, decision.score, row["id"]),
            )
            if decision.state == KEPT:
                result.kept += 1
            else:
                result.rejected += 1

    result.skipped = conn.execute(
        "SELECT COUNT(*) c FROM items WHERE triage_state = ? AND embedded_hash IS NULL",
        (PENDING,),
    ).fetchone()["c"]
    return result


def explain(
    conn: sqlite3.Connection,
    profile: TriageConfig,
    item_id: int,
    model_name: str = DEFAULT_MODEL,
) -> dict | None:
    """Why one item was kept or dropped, and which interest it matched.

    Threshold tuning is guesswork without this: the useful question is never
    "what is the score" but "which sentence did it match, and does that look right".
    """
    row = conn.execute(
        """
        SELECT i.id, i.title, i.kind, i.triage_state, i.triage_score, v.embedding
          FROM items i LEFT JOIN item_vectors v ON v.item_id = i.id
         WHERE i.id = ?
        """,
        (item_id,),
    ).fetchone()
    if row is None or row["embedding"] is None:
        return None

    interests, excludes = profile_vectors(profile, model_name)
    vector = np.frombuffer(row["embedding"], dtype=np.float32)
    interest_scores = vector @ interests.T
    best = int(interest_scores.argmax())
    exclude_score = float((vector @ excludes.T).max()) if excludes.shape[0] else 0.0
    decision = decide(row["title"], float(interest_scores[best]), exclude_score, profile)

    return {
        "id": row["id"],
        "title": row["title"],
        "kind": row["kind"],
        "state": decision.state,
        "score": decision.score,
        "reason": decision.reason,
        "best_interest": profile.interests[best],
        "exclude_score": exclude_score,
        "ranked": sorted(
            zip(profile.interests, interest_scores.tolist(), strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )[:5],
    }


def stats(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT triage_state, COUNT(*) c FROM items GROUP BY triage_state"
    ).fetchall()
    counts = {r["triage_state"]: r["c"] for r in rows}
    return {
        "kept": counts.get(KEPT, 0),
        "rejected": counts.get(REJECTED, 0),
        "pending": counts.get(PENDING, 0),
    }


def by_source(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Keep rate per source.

    The single most useful tuning view: a gate that is working drops most of a
    general tech feed and keeps most of a research feed. One uniform rate across
    every source means the profile is measuring text length, not relevance.
    """
    return list(
        conn.execute(
            """
            SELECT s.name,
                   COUNT(*) AS total,
                   SUM(i.triage_state = 'kept') AS kept,
                   AVG(i.triage_score) AS mean_score
              FROM items i
              JOIN sources s ON s.id = i.source_id
             WHERE i.triage_score IS NOT NULL
             GROUP BY s.id
             ORDER BY 1.0 * SUM(i.triage_state = 'kept') / COUNT(*) DESC
            """
        )
    )


def sample(conn: sqlite3.Connection, state: str, limit: int = 20) -> list[sqlite3.Row]:
    """Items at the margin — the ones worth eyeballing when tuning."""
    order = "ASC" if state == KEPT else "DESC"  # nearest the threshold from either side
    return list(
        conn.execute(
            f"""
            SELECT i.id, i.title, i.kind, i.triage_score, s.name AS source_name
              FROM items i JOIN sources s ON s.id = i.source_id
             WHERE i.triage_state = ? AND i.triage_score IS NOT NULL
             ORDER BY i.triage_score {order}
             LIMIT ?
            """,
            (state, limit),
        )
    )
