"""Threshold calibration for tier-2 clustering.

The plan called for a hand-labelled golden set. Tier 1 provides a better one for
free: two items carrying the same strong identifier *are* the same story, with
no judgement involved. Those pairs are the positives.

Negatives come in two grades, and the distinction is the whole point:

  random    two arbitrary kept items -- easy, and misleadingly reassuring
  hard      two *different* papers published within a week of each other

Hard negatives are where the real false merges live: papers on the same topic in
the same week score higher than some genuine matches, so the distributions
overlap and no threshold is clean. This picks the one that honours the rule that
a wrong merge costs more than a missed link.
"""

from __future__ import annotations

import itertools
import random
import sqlite3
from dataclasses import dataclass

import numpy as np

from tributary import identity

HARD_NEGATIVE_WINDOW_DAYS = 7
RANDOM_NEGATIVE_PAIRS = 4000


@dataclass(slots=True)
class Distribution:
    name: str
    scores: np.ndarray

    def summary(self) -> dict:
        if not len(self.scores):
            return {"n": 0}
        return {
            "n": len(self.scores),
            "min": float(self.scores.min()),
            "p5": float(np.percentile(self.scores, 5)),
            "median": float(np.median(self.scores)),
            "p95": float(np.percentile(self.scores, 95)),
            "max": float(self.scores.max()),
        }


def _vectors(conn: sqlite3.Connection, item_ids: list[int]) -> dict[int, np.ndarray]:
    if not item_ids:
        return {}
    placeholders = ",".join("?" * len(item_ids))
    return {
        r["item_id"]: np.frombuffer(r["embedding"], dtype=np.float32)
        for r in conn.execute(
            f"SELECT item_id, embedding FROM item_vectors WHERE item_id IN ({placeholders})",
            item_ids,
        )
    }


def positives(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    """Pairs known to be the same story because they share a strong identifier."""
    placeholders = ",".join("?" * len(identity.STRONG))
    groups: dict[tuple[str, str], list[int]] = {}
    for row in conn.execute(
        f"""
        SELECT d.type, d.value, d.item_id
          FROM identifiers d JOIN items i ON i.id = d.item_id
         WHERE d.type IN ({placeholders}) AND i.triage_state = 'kept'
        """,
        sorted(identity.STRONG),
    ):
        groups.setdefault((row["type"], row["value"]), []).append(row["item_id"])

    pairs = []
    for members in groups.values():
        if 1 < len(members) <= identity.MAX_FANOUT:
            pairs.extend(itertools.combinations(sorted(set(members)), 2))
    return pairs


def hard_negatives(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    """Distinct papers published close together: the real false-merge risk."""
    by_paper: dict[str, sqlite3.Row] = {}
    for row in conn.execute(
        """
        SELECT i.id, d.value AS paper, COALESCE(i.published_at, i.fetched_at) AS at
          FROM items i JOIN identifiers d ON d.item_id = i.id AND d.type = ?
         WHERE i.triage_state = 'kept' AND i.kind = 'paper'
        """,
        (identity.ARXIV,),
    ):
        by_paper.setdefault(row["paper"], row)

    papers = list(by_paper.values())
    window = np.timedelta64(HARD_NEGATIVE_WINDOW_DAYS, "D")
    pairs = []
    for a, b in itertools.combinations(papers, 2):
        if abs(np.datetime64(a["at"][:19]) - np.datetime64(b["at"][:19])) <= window:
            pairs.append((a["id"], b["id"]))
    return pairs


def random_negatives(conn: sqlite3.Connection, seed: int = 7) -> list[tuple[int, int]]:
    kept = [r["id"] for r in conn.execute("SELECT id FROM items WHERE triage_state = 'kept'")]
    if len(kept) < 2:
        return []
    rng = random.Random(seed)
    pairs = {
        tuple(sorted((rng.choice(kept), rng.choice(kept)))) for _ in range(RANDOM_NEGATIVE_PAIRS)
    }
    return [(a, b) for a, b in pairs if a != b]


def score(conn: sqlite3.Connection, pairs: list[tuple[int, int]]) -> np.ndarray:
    """Cosine similarity for each pair, skipping any item without a vector."""
    if not pairs:
        return np.array([], dtype=np.float32)
    vectors = _vectors(conn, sorted({i for pair in pairs for i in pair}))
    return np.array(
        [float(vectors[a] @ vectors[b]) for a, b in pairs if a in vectors and b in vectors],
        dtype=np.float32,
    )


def evaluate(conn: sqlite3.Connection, thresholds: list[float]) -> dict:
    """Score every distribution, then count what each threshold gets wrong."""
    distributions = {
        "positive": Distribution("positive", score(conn, positives(conn))),
        "hard_negative": Distribution("hard_negative", score(conn, hard_negatives(conn))),
        "random_negative": Distribution("random_negative", score(conn, random_negatives(conn))),
    }

    table = []
    positive_scores = distributions["positive"].scores
    hard_scores = distributions["hard_negative"].scores
    for threshold in thresholds:
        caught = int((positive_scores >= threshold).sum()) if len(positive_scores) else 0
        merged = int((hard_scores >= threshold).sum()) if len(hard_scores) else 0
        table.append(
            {
                "threshold": threshold,
                "recall": caught / len(positive_scores) if len(positive_scores) else 0.0,
                "caught": caught,
                "positives": len(positive_scores),
                "false_merges": merged,
                "hard_pairs": len(hard_scores),
            }
        )
    return {
        "distributions": {k: v.summary() for k, v in distributions.items()},
        "thresholds": table,
    }
