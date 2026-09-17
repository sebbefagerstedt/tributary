"""Stage 5: topics.

The same machinery as triage, pointed at a different question: not "is this worth
keeping" but "what is it about". Both are cosine similarity against embedded
prose, which is why neither needs an API key -- a point worth restating, because
"dynamic topics" sounds like it must need a model and does not.

Topics attach to stories rather than items. A story is the unit a reader browses
and filters, and its members are by construction about the same thing, so
scoring the story once is both cheaper and steadier than scoring each item and
arguing about disagreements.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import numpy as np

from tributary.config import TopicsConfig
from tributary.db import transaction
from tributary.embeddings import DEFAULT_MODEL, embed


@dataclass(slots=True)
class TopicResult:
    stories: int = 0
    assigned: int = 0
    unmatched: int = 0  # scored, but nothing on the spine fitted
    by_topic: dict[str, int] = field(default_factory=dict)


def sync_spine(conn: sqlite3.Connection, profile: TopicsConfig) -> dict[str, int]:
    """Make the topics table match the config, and return slug -> id."""
    with transaction(conn):
        for topic in profile.spine:
            conn.execute(
                "INSERT INTO topics (slug, name) VALUES (?, ?) "
                "ON CONFLICT (slug) DO UPDATE SET name = excluded.name",
                (topic.slug, topic.name),
            )
    return {
        row["slug"]: row["id"] for row in conn.execute("SELECT id, slug FROM topics")
    }


def reset_if_profile_changed(conn: sqlite3.Connection, profile: TopicsConfig) -> bool:
    """Re-assign everything when the spine changes.

    Editing a description would otherwise only affect stories clustered after the
    edit, leaving the back catalogue labelled by a spine that no longer exists.
    """
    fingerprint = profile.fingerprint()
    row = conn.execute("SELECT value FROM meta WHERE key = 'topic_spine'").fetchone()
    if row and row["value"] == fingerprint:
        return False

    with transaction(conn):
        conn.execute("DELETE FROM story_topics")
        conn.execute("DELETE FROM topic_assigned")
        # Dropping topics too, so a slug removed from the config stops existing
        # rather than lingering with no way to be assigned again.
        conn.execute("DELETE FROM topics")
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('topic_spine', ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (fingerprint,),
        )
    return True


def reset(conn: sqlite3.Connection) -> None:
    """Drop every assignment so the whole corpus is re-labelled."""
    with transaction(conn):
        conn.execute("DELETE FROM story_topics")
        conn.execute("DELETE FROM topic_assigned")


def pending(conn: sqlite3.Connection, limit: int | None = None) -> list[int]:
    """Stories that have not been scored against the current spine."""
    sql = """
        SELECT st.id
          FROM stories st
         WHERE st.id NOT IN (SELECT story_id FROM topic_assigned)
         ORDER BY st.last_activity DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [row["id"] for row in conn.execute(sql)]


def centroids(conn: sqlite3.Connection, story_ids: list[int]) -> tuple[list[int], np.ndarray]:
    """The mean vector of each story's members, re-normalised.

    A story's subject is better described by everything in it than by whichever
    item happened to arrive first, and averaging costs nothing next to having
    embedded them in the first place.
    """
    if not story_ids:
        return [], np.zeros((0, 0), dtype=np.float32)

    placeholders = ",".join("?" * len(story_ids))
    grouped: dict[int, list[np.ndarray]] = {}
    for row in conn.execute(
        f"""
        SELECT si.story_id, v.embedding
          FROM story_items si
          JOIN item_vectors v ON v.item_id = si.item_id
         WHERE si.story_id IN ({placeholders})
        """,
        story_ids,
    ):
        vector = np.frombuffer(row["embedding"], dtype=np.float32)
        grouped.setdefault(row["story_id"], []).append(vector)

    found = [story_id for story_id in story_ids if story_id in grouped]
    if not found:
        return [], np.zeros((0, 0), dtype=np.float32)

    stacked = np.array([np.mean(grouped[s], axis=0) for s in found], dtype=np.float32)
    norms = np.linalg.norm(stacked, axis=1, keepdims=True)
    # A story whose vectors cancel out has no direction to compare; leaving the
    # norm at 1 makes its scores zero rather than NaN.
    return found, stacked / np.where(norms == 0, 1.0, norms)


# Subject-level, and deliberately far looser than the 0.92 that merges two items
# into one story: this groups things that are *about the same sort of thing*, not
# things that are the same event.
GROUP_SIMILARITY = 0.78


@dataclass(slots=True)
class Candidate:
    """A cluster of recent stories with no good name yet."""

    titles: list[str] = field(default_factory=list)
    size: int = 0
    covered: dict[str, int] = field(default_factory=dict)  # existing topics these carry

    @property
    def uncovered(self) -> int:
        """Stories in this group that no current topic claims."""
        return self.size - sum(self.covered.values())


def suggest(
    conn: sqlite3.Connection,
    days: int = 7,
    min_size: int = 3,
    similarity: float = GROUP_SIMILARITY,
) -> list[Candidate]:
    """Group recent stories by subject so a human can name the groups.

    Naming is the part that cannot be automated well without a model, and the
    pipeline deliberately has no API key. So this stops at the useful half:
    it finds what clusters, shows what is in each cluster, and says which
    existing topics already claim it. Somebody -- or something -- with judgement
    reads the output and proposes the names.
    """
    story_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM stories WHERE last_activity >= datetime('now', ?) "
            "ORDER BY last_activity DESC",
            (f"-{int(days)} days",),
        )
    ]
    found, vectors = centroids(conn, story_ids)
    if not found:
        return []

    members: list[list[int]] = []
    sums: list[np.ndarray] = []
    heads: list[np.ndarray] = []
    for position, vector in enumerate(vectors):
        best, score = -1, similarity
        for group, head in enumerate(heads):
            if (found_score := float(head @ vector)) >= score:
                best, score = group, found_score
        if best < 0:
            members.append([position])
            sums.append(vector.copy())
            heads.append(vector.copy())
        else:
            members[best].append(position)
            sums[best] = sums[best] + vector
            norm = float(np.linalg.norm(sums[best]))
            heads[best] = sums[best] / (norm or 1.0)

    titles = _titles(conn, found)
    labels = for_stories(conn, found)

    candidates = []
    for group in members:
        if len(group) < min_size:
            continue
        covered: dict[str, int] = {}
        for position in group:
            for topic in labels.get(found[position], []):
                covered[topic["name"]] = covered.get(topic["name"], 0) + 1
        candidates.append(
            Candidate(
                titles=[titles.get(found[p], "") for p in group if titles.get(found[p])],
                size=len(group),
                covered=covered,
            )
        )
    return sorted(candidates, key=lambda c: (c.uncovered, c.size), reverse=True)


def _titles(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, str]:
    """One representative headline per story: the earliest item in it."""
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, str] = {}
    for row in conn.execute(
        f"""
        SELECT si.story_id, i.title
          FROM story_items si
          JOIN items i ON i.id = si.item_id
         WHERE si.story_id IN ({placeholders})
         ORDER BY COALESCE(i.published_at, i.fetched_at) ASC
        """,
        story_ids,
    ):
        found.setdefault(row["story_id"], row["title"])
    return found


def run(
    conn: sqlite3.Connection,
    profile: TopicsConfig,
    model_name: str = DEFAULT_MODEL,
    limit: int | None = None,
) -> TopicResult:
    """Score every unassigned story against the spine."""
    result = TopicResult()
    if not profile.spine:
        return result

    ids = sync_spine(conn, profile)
    story_ids, vectors = centroids(conn, pending(conn, limit))
    if not story_ids:
        return result

    descriptions = np.array(
        embed([topic.description for topic in profile.spine], model_name), dtype=np.float32
    )
    scores = vectors @ descriptions.T
    result.stories = len(story_ids)

    with transaction(conn):
        for story_id, row in zip(story_ids, scores, strict=True):
            ranked = sorted(
                (
                    (float(score), topic)
                    for score, topic in zip(row, profile.spine, strict=True)
                    if score >= profile.threshold
                ),
                key=lambda pair: pair[0],
                reverse=True,
            )[: profile.max_per_story]

            for _, topic in ranked:
                conn.execute(
                    "INSERT OR IGNORE INTO story_topics (story_id, topic_id) VALUES (?, ?)",
                    (story_id, ids[topic.slug]),
                )
                result.by_topic[topic.slug] = result.by_topic.get(topic.slug, 0) + 1
            if ranked:
                result.assigned += 1
            else:
                result.unmatched += 1
            conn.execute(
                "INSERT OR IGNORE INTO topic_assigned (story_id) VALUES (?)", (story_id,)
            )
    return result


def for_stories(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, list[dict]]:
    """Topic slugs and names per story, for the bundle."""
    if not story_ids:
        return {}
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list[dict]] = {}
    for row in conn.execute(
        f"""
        SELECT stp.story_id, t.slug, t.name
          FROM story_topics stp
          JOIN topics t ON t.id = stp.topic_id
         WHERE stp.story_id IN ({placeholders})
         ORDER BY t.name
        """,
        story_ids,
    ):
        found.setdefault(row["story_id"], []).append({"slug": row["slug"], "name": row["name"]})
    return found


def stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Story count per topic, most populated first: the view for tuning the spine.

    A topic with almost everything under it is too broadly worded; one with
    nothing is either too narrow or describes something the sources do not cover.
    """
    return list(
        conn.execute(
            """
            SELECT t.slug, t.name, COUNT(stp.story_id) AS stories
              FROM topics t
              LEFT JOIN story_topics stp ON stp.topic_id = t.id
             GROUP BY t.id
             ORDER BY stories DESC, t.name
            """
        )
    )
