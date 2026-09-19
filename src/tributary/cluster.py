"""Stage 4: clustering.

Groups items into stories, so one release appears once with its paper, its repo,
its coverage and its discussion attached, rather than as twelve headlines.

Three tiers, cheapest and most precise first:

  1. strong identifier shared with an existing story -- exact, free
  2. embedding similarity within a trailing window   -- catches uncited coverage
  3. LLM adjudication for the ambiguous band          -- deferred, optional

Tier 3 is not wired to a model: items in the ambiguous band start their own
story and are recorded, so enabling adjudication later is a change of policy,
not of structure.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import numpy as np

from tributary import identity
from tributary.db import transaction
from tributary.store import utcnow

# Measured, not guessed -- see `trib calibrate`, which uses tier-1 identifier
# matches as ground truth. On the first real corpus the distributions overlapped:
# genuine matches ran as low as 0.888, while *different* papers from the same
# week reached 0.944. There is no clean split, so these honour the rule that a
# wrong merge costs more than a missed link:
#
#   0.88 -> caught all 87 positives, but merged 16 of 36,470 hard-negative pairs
#   0.92 -> missed 1 positive,       and merged 2
MERGE_THRESHOLD = 0.92
# Between these two lies the band where similarity genuinely cannot decide. Items
# here start their own story and are reported; it is the band an LLM adjudicator
# would be asked about, if one is ever wired in.
AMBIGUOUS_LOW = 0.86
WINDOW_DAYS = 14

# Roles describe what an item contributes to its story.
SEED = "seed"
COVERAGE = "coverage"
PAPER = "paper"
CODE = "code"
VIDEO = "video"
DISCUSSION = "discussion"

# A story's primary artefact, where one exists.
_KIND_ROLE = {
    "paper": PAPER,
    "repo": CODE,
    "video": VIDEO,
    "discussion": DISCUSSION,
    "model": SEED,
    "article": COVERAGE,
    "post": COVERAGE,
}
# Kinds that can anchor a story on their own.
_PRIMARY = frozenset({"paper", "model", "repo"})


@dataclass(slots=True)
class ClusterResult:
    stories_created: int = 0
    joined_by_identifier: int = 0
    joined_by_similarity: int = 0
    ambiguous: list[tuple[int, int, float]] = field(default_factory=list)

    @property
    def assigned(self) -> int:
        return self.stories_created + self.joined_by_identifier + self.joined_by_similarity


def role_for(kind: str, *, first_in_story: bool) -> str:
    """What this item contributes: whatever opens a story leads it, and whatever
    arrives afterwards contributes to it.

    Asking "does this story already have a seed?" was the wrong question, because
    a paper-led story holds the role `paper` and no seed at all -- so everything
    joining one was labelled a second seed. That made a story's own coverage
    invisible in its wake, seed being the one role that describes the
    announcement rather than a reaction to it.
    """
    role = _KIND_ROLE.get(kind, COVERAGE)
    if first_in_story:
        # Something has to lead, even when all that showed up is a wire rewrite.
        return SEED if role is COVERAGE else role
    # A hub artefact turning up later was built on the story, not announced by it.
    return CODE if role is SEED else role


def unclustered(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    """Embedded items not yet in a story, oldest first.

    Oldest first matters: stories accrete forward in time, so the earliest item
    becomes the seed and later coverage attaches to it.

    **Not filtered by the triage verdict.** Triage used to decide what existed;
    following decides that now, and a reader's own subjects are a better filter
    than one profile of prose for everybody. Triage still runs and still scores,
    because `relevance` in the ranking is its score -- so what it dislikes sinks
    in Trending rather than never being fetched into a story at all.
    """
    # Joined to the vectors rather than trusting `embedded_hash`: the hash says
    # which text was embedded, not that the row survived. `vectors_for` indexes
    # the result by item, so one item with a hash and no vector used to take the
    # whole stage down -- which the triage gate happened to hide.
    sql = """
        SELECT i.id, i.kind, i.title, COALESCE(i.published_at, i.fetched_at) AS at
          FROM items i
          JOIN item_vectors v ON v.item_id = i.id
         WHERE i.embedded_hash IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM story_items si WHERE si.item_id = i.id)
         ORDER BY at ASC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return list(conn.execute(sql))


def _generic_identifiers(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    """Identifiers shared so widely they describe a category, not an event."""
    return {
        (r["type"], r["value"])
        for r in conn.execute(
            "SELECT type, value FROM identifiers GROUP BY type, value HAVING COUNT(*) > ?",
            (identity.MAX_FANOUT,),
        )
    }


def story_by_identifier(
    conn: sqlite3.Connection, item_id: int, generic: set[tuple[str, str]]
) -> int | None:
    """Tier 1: an existing story holding a strong identifier this item also has."""
    placeholders = ",".join("?" * len(identity.STRONG))
    rows = conn.execute(
        f"""
        SELECT DISTINCT si.story_id, d2.type, d2.value
          FROM identifiers d1
          JOIN identifiers d2 ON d2.type = d1.type AND d2.value = d1.value
          JOIN story_items si ON si.item_id = d2.item_id
         WHERE d1.item_id = ? AND d2.item_id != ? AND d1.type IN ({placeholders})
        """,
        (item_id, item_id, *sorted(identity.STRONG)),
    ).fetchall()
    for row in rows:
        if (row["type"], row["value"]) not in generic:
            return row["story_id"]
    return None


def _load_vectors(conn: sqlite3.Connection, item_ids: list[int]) -> np.ndarray:
    """Vectors for the given items, in the order requested."""
    if not item_ids:
        return np.zeros((0, 0), dtype=np.float32)
    placeholders = ",".join("?" * len(item_ids))
    stored = {
        r["item_id"]: r["embedding"]
        for r in conn.execute(
            f"SELECT item_id, embedding FROM item_vectors WHERE item_id IN ({placeholders})",
            item_ids,
        )
    }
    blobs = [stored[i] for i in item_ids]
    return np.frombuffer(b"".join(blobs), dtype=np.float32).reshape(len(blobs), -1)


def create_story(conn: sqlite3.Connection, item_id: int, kind: str, at: str) -> int:
    story_id = conn.execute(
        "INSERT INTO stories (first_seen, last_activity, materially_updated_at) VALUES (?, ?, ?)",
        (at, at, at),
    ).lastrowid
    conn.execute(
        "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, ?)",
        (story_id, item_id, role_for(kind, first_in_story=True)),
    )
    return story_id


def add_to_story(conn: sqlite3.Connection, story_id: int, item_id: int, kind: str, at: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO story_items (story_id, item_id, role) VALUES (?, ?, ?)",
        (story_id, item_id, role_for(kind, first_in_story=False)),
    )
    # A new primary artefact is a material update; more coverage of the same
    # thing is not, and must not resurface a story you have already seen.
    material = kind in _PRIMARY
    conn.execute(
        f"""
        UPDATE stories
           SET last_activity = MAX(last_activity, ?),
               synthesized_at = NULL
               {", materially_updated_at = MAX(COALESCE(materially_updated_at, ''), ?)"
                if material else ""}
         WHERE id = ?
        """,
        (at, at, story_id) if material else (at, story_id),
    )


def run(
    conn: sqlite3.Connection,
    limit: int | None = None,
    merge_threshold: float = MERGE_THRESHOLD,
    ambiguous_low: float = AMBIGUOUS_LOW,
    window_days: int = WINDOW_DAYS,
) -> ClusterResult:
    """Assign every unclustered item to a story, creating stories as needed."""
    rows = unclustered(conn, limit)
    result = ClusterResult()
    if not rows:
        return result

    generic = _generic_identifiers(conn)
    window = np.timedelta64(window_days, "D")

    # Candidates for similarity matching: items already in a story. Grown as we
    # go, so an item can attach to a story created moments earlier in this pass.
    candidate_ids: list[int] = []
    candidate_times: list[np.datetime64] = []
    candidate_stories: list[int] = []
    for row in conn.execute(
        """
        SELECT si.item_id, si.story_id, COALESCE(i.published_at, i.fetched_at) AS at
          FROM story_items si JOIN items i ON i.id = si.item_id
         ORDER BY at ASC
        """
    ):
        candidate_ids.append(row["item_id"])
        candidate_times.append(np.datetime64(row["at"][:19]))
        candidate_stories.append(row["story_id"])

    matrix = _load_vectors(conn, candidate_ids)
    new_vectors = _load_vectors(conn, [r["id"] for r in rows])

    with transaction(conn):
        for position, row in enumerate(rows):
            item_id, kind, at = row["id"], row["kind"], row["at"]

            story_id = story_by_identifier(conn, item_id, generic)
            if story_id is not None:
                add_to_story(conn, story_id, item_id, kind, at)
                result.joined_by_identifier += 1
            else:
                story_id, how, score = _match_by_similarity(
                    new_vectors[position],
                    np.datetime64(at[:19]),
                    matrix,
                    candidate_times,
                    candidate_stories,
                    window,
                    merge_threshold,
                    ambiguous_low,
                )
                if how == "merge":
                    add_to_story(conn, story_id, item_id, kind, at)
                    result.joined_by_similarity += 1
                else:
                    if how == "ambiguous":
                        result.ambiguous.append((item_id, story_id, score))
                    story_id = create_story(conn, item_id, kind, at)
                    result.stories_created += 1

            # The item is now itself a candidate for everything that follows.
            candidate_ids.append(item_id)
            candidate_times.append(np.datetime64(at[:19]))
            candidate_stories.append(story_id)
            matrix = (
                np.vstack([matrix, new_vectors[position][None, :]])
                if matrix.size
                else new_vectors[position][None, :]
            )

    return result


def _match_by_similarity(
    vector: np.ndarray,
    at: np.datetime64,
    matrix: np.ndarray,
    times: list[np.datetime64],
    stories: list[int],
    window: np.timedelta64,
    merge_threshold: float,
    ambiguous_low: float,
) -> tuple[int | None, str, float]:
    """Tier 2. Returns (story_id, verdict, score) where verdict is merge/ambiguous/new."""
    if not matrix.size:
        return None, "new", 0.0

    # Vectors are L2-normalised, so the dot product is cosine similarity.
    scores = matrix @ vector
    # Only compare against things recent enough to be the same event.
    in_window = np.array([abs(at - t) <= window for t in times])
    scores = np.where(in_window, scores, -1.0)

    best = int(scores.argmax())
    score = float(scores[best])
    if score >= merge_threshold:
        return stories[best], "merge", score
    if score >= ambiguous_low:
        return stories[best], "ambiguous", score
    return None, "new", score


def reset(conn: sqlite3.Connection) -> None:
    """Drop all stories so clustering can be re-run with different thresholds."""
    with transaction(conn):
        conn.execute("DELETE FROM story_items")
        conn.execute("DELETE FROM stories")


def stats(conn: sqlite3.Connection) -> dict:
    sizes = [
        r["n"]
        for r in conn.execute(
            "SELECT COUNT(*) n FROM story_items GROUP BY story_id ORDER BY n DESC"
        )
    ]
    clustered = sum(s for s in sizes if s > 1)
    return {
        "stories": len(sizes),
        "items": sum(sizes),
        "singletons": sum(1 for s in sizes if s == 1),
        "multi": sum(1 for s in sizes if s > 1),
        "largest": sizes[0] if sizes else 0,
        "items_in_multi": clustered,
        "updated_at": utcnow(),
    }
