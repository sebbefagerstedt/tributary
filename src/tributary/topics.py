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
    parked: int = 0  # the shelf was clear, the leaf was not
    by_topic: dict[str, int] = field(default_factory=dict)


def sync_spine(conn: sqlite3.Connection, profile: TopicsConfig) -> dict[str, int]:
    """Make the topics table match the config, and return slug -> id."""
    with transaction(conn):
        # Two passes, because a child may be declared before its parent.
        for topic in profile.spine:
            conn.execute(
                "INSERT INTO topics (slug, name) VALUES (?, ?) "
                "ON CONFLICT (slug) DO UPDATE SET name = excluded.name",
                (topic.slug, topic.name),
            )
        ids = {row["slug"]: row["id"] for row in conn.execute("SELECT id, slug FROM topics")}
        for topic in profile.spine:
            conn.execute(
                "UPDATE topics SET parent_id = ? WHERE slug = ?",
                (ids.get(topic.parent) if topic.parent else None, topic.slug),
            )
    return ids


def reset_if_profile_changed(
    conn: sqlite3.Connection,
    profile: TopicsConfig,
    fingerprint: str | None = None,
) -> bool:
    """Re-assign everything when the spine changes.

    Editing a description would otherwise only affect stories clustered after the
    edit, leaving the back catalogue labelled by a spine that no longer exists.

    Callers pass the config-wide label fingerprint, which covers facets and
    entities too: all three are matched in one pass, so a change to any of them
    has to re-run all of it rather than leave the corpus half relabelled.
    """
    fingerprint = fingerprint or profile.fingerprint()
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
    claimed: int = 0  # stories at least one of those topics reached
    parked: int = 0  # stories sitting on a shelf because no leaf fitted them

    @property
    def uncovered(self) -> int:
        """Stories in this group that no current topic claims.

        Counted as whole stories, not by subtracting `covered`: a story carries
        up to `max_per_story` topics, so those counts sum past the size of the
        group and the subtraction goes negative.
        """
        return self.size - self.claimed

    @property
    def unplaced(self) -> int:
        """Stories with no specific home: nothing claimed them, or they parked.

        Under one-home assignment almost every story is claimed by *something*,
        so "unclaimed" stopped being a useful signal. A story parked on a shelf
        is the new one -- it means the shelf fits and none of its leaves does,
        which is exactly what a missing leaf looks like.
        """
        return self.uncovered + self.parked


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
    shelves = {
        row["slug"]
        for row in conn.execute(
            "SELECT DISTINCT p.slug FROM topics c JOIN topics p ON p.id = c.parent_id"
        )
    }

    candidates = []
    for group in members:
        if len(group) < min_size:
            continue
        covered: dict[str, int] = {}
        claimed = parked = 0
        for position in group:
            found_topics = labels.get(found[position], [])
            claimed += bool(found_topics)
            parked += any(topic["slug"] in shelves for topic in found_topics)
            for topic in found_topics:
                covered[topic["name"]] = covered.get(topic["name"], 0) + 1
        candidates.append(
            Candidate(
                titles=[titles.get(found[p], "") for p in group if titles.get(found[p])],
                size=len(group),
                covered=covered,
                claimed=claimed,
                parked=parked,
            )
        )
    return sorted(candidates, key=lambda c: (c.unplaced, c.size), reverse=True)


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
    """Give every unassigned story the one home that fits it best.

    Only leaves are scored, and the best one wins outright. There is no
    threshold deciding what counts as a match and no cap on how many topics a
    story may take, because both were answering a question that does not need
    asking: of these topics, which one is this? A comparison needs no scale, so
    nothing here drifts when the embedding model changes or the spine grows.

    The floor is not a threshold in that sense -- it catches a story the spine
    has no opinion about at all, which over the whole corpus is one story in
    2239. If it starts firing, the spine is missing something.
    """
    result = TopicResult()
    leaves = profile.leaves()
    if not leaves:
        return result

    ids = sync_spine(conn, profile)
    story_ids, vectors = centroids(conn, pending(conn, limit))
    if not story_ids:
        return result

    descriptions = np.array(
        embed([topic.description for topic in leaves], model_name), dtype=np.float32
    )
    scores = vectors @ descriptions.T
    parent_of = {topic.slug: topic.parent for topic in profile.spine}
    result.stories = len(story_ids)

    with transaction(conn):
        for story_id, row in zip(story_ids, scores, strict=True):
            home = _home(row, leaves, parent_of, profile)
            if home is None:
                result.unmatched += 1
            else:
                slug, parked = home
                conn.execute(
                    "INSERT OR IGNORE INTO story_topics (story_id, topic_id) VALUES (?, ?)",
                    (story_id, ids[slug]),
                )
                result.by_topic[slug] = result.by_topic.get(slug, 0) + 1
                result.assigned += 1
                result.parked += parked
            conn.execute(
                "INSERT OR IGNORE INTO topic_assigned (story_id) VALUES (?)", (story_id,)
            )
    return result


def _home(
    row: np.ndarray,
    leaves: list,
    parent_of: dict[str, str | None],
    profile: TopicsConfig,
) -> tuple[str, bool] | None:
    """The one topic a story belongs under, and whether it parked on a shelf.

    Parking is for the case where the shelf is obvious and the leaf is a
    coin-toss: two leaves on the same shelf within `park_margin` of each other.
    Forcing a choice there would be inventing precision the scores do not have,
    and the pile that collects on a shelf is the signal that a leaf is missing.
    """
    order = np.argsort(-row)
    best = int(order[0])
    if float(row[best]) < profile.floor:
        return None

    winner = leaves[best].slug
    shelf = parent_of.get(winner)
    if shelf and len(order) > 1:
        runner_up = leaves[int(order[1])].slug
        close = float(row[best]) - float(row[int(order[1])]) < profile.park_margin
        if close and parent_of.get(runner_up) == shelf:
            return shelf, True
    return winner, False


def for_stories(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, list[dict]]:
    """Topic slugs and names per story, for the bundle."""
    if not story_ids:
        return {}
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list[dict]] = {}
    for row in conn.execute(
        f"""
        SELECT stp.story_id, t.slug, t.name,
               parent.slug AS parent, parent.name AS parent_name
          FROM story_topics stp
          JOIN topics t           ON t.id = stp.topic_id
          LEFT JOIN topics parent ON parent.id = t.parent_id
         WHERE stp.story_id IN ({placeholders})
         ORDER BY t.name
        """,
        story_ids,
    ):
        # The parent travels with each label so the page can build the top row
        # without being handed the whole tree separately. A story that matched
        # only a child still knows which shelf it belongs on.
        label = {"slug": row["slug"], "name": row["name"]}
        if row["parent"]:
            label |= {"parent": row["parent"], "parent_name": row["parent_name"]}
        found.setdefault(row["story_id"], []).append(label)
    return found


def stats(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Story count and last activity per topic, most populated first.

    A topic with almost everything under it is too broadly worded; one with
    nothing is either too narrow or describes something the sources do not cover.
    `newest` is what says whether a topic has gone quiet: topics are allowed to
    be short-lived, so one with no recent stories has probably finished rather
    than failed, and is a candidate for retiring.

    `below_triage` is the number of a topic's stories made entirely of items
    triage would once have dropped, and it is the number that matters now that
    triage no longer gates the corpus. Topics have no relevance threshold --
    a story goes to its single best leaf, and `floor` was measured at 1 story
    in 2239 *on already-triaged material*. On everything, that floor is the
    only thing standing between a crypto post and whichever AI leaf it most
    resembles. A topic filling up with `below_triage` stories is following
    being polluted, and is the signal to re-measure the floor.
    """
    return list(
        conn.execute(
            """
            SELECT t.slug, t.name,
                   COUNT(stp.story_id) AS stories,
                   SUM(CASE WHEN stp.story_id IS NOT NULL AND NOT EXISTS (
                         SELECT 1 FROM story_items si
                           JOIN items i ON i.id = si.item_id
                          WHERE si.story_id = stp.story_id AND i.triage_state = 'kept'
                       ) THEN 1 ELSE 0 END) AS below_triage,
                   MAX(st.last_activity) AS newest
              FROM topics t
              LEFT JOIN story_topics stp ON stp.topic_id = t.id
              LEFT JOIN stories st       ON st.id = stp.story_id
             GROUP BY t.id
             ORDER BY stories DESC, t.name
            """
        )
    )
