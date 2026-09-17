"""Stage 6a: facets.

What a story *is*, as opposed to where it lives. A story has exactly one topic
and any number of facets, and they stack: "agents" inside "Speed, memory & cost".

Facets are regexes, and that is the whole point of them. Some subjects cut
across every shelf -- an agent paper is also a safety paper and a benchmark
paper, because it really is all three -- so similarity cannot separate them from
their neighbours. It puts them wherever they most resemble, which is how
`RepoAtlas: Guiding Coding Agents` ended up under interpretability. A word,
meanwhile, is either in the text or it is not: matching `agent` finds a quarter
of the feed where scoring a description found a twentieth.

Cheap enough to redo from scratch every run, so there is no assignment marker
here the way `topic_assigned` exists for topics.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from tributary.config import FacetConfig
from tributary.db import transaction


@dataclass(slots=True)
class FacetResult:
    stories: int = 0
    matched: int = 0  # stories carrying at least one facet
    by_facet: dict[str, int] = field(default_factory=dict)


def run(conn: sqlite3.Connection, facets: list[FacetConfig]) -> FacetResult:
    """Match every story's text against every facet pattern."""
    result = FacetResult()
    with transaction(conn):
        conn.execute("DELETE FROM story_facets")
        if not facets:
            return result

        patterns = [(f.slug, re.compile(f.pattern, re.IGNORECASE)) for f in facets]
        for story_id, text in story_texts(conn):
            result.stories += 1
            hit = False
            for slug, pattern in patterns:
                if pattern.search(text):
                    conn.execute(
                        "INSERT OR IGNORE INTO story_facets (story_id, slug) VALUES (?, ?)",
                        (story_id, slug),
                    )
                    result.by_facet[slug] = result.by_facet.get(slug, 0) + 1
                    hit = True
            result.matched += hit
    return result


def story_texts(conn: sqlite3.Connection):
    """One blob of searchable text per story: every member's title and summary.

    Matching the whole story rather than its first item is the same choice
    `centroids` makes -- what a story is about is better described by everything
    in it than by whichever item happened to arrive first.
    """
    current: int | None = None
    parts: list[str] = []
    for row in conn.execute(
        """
        SELECT si.story_id, i.title, i.summary
          FROM story_items si
          JOIN items i ON i.id = si.item_id
         ORDER BY si.story_id
        """
    ):
        if row["story_id"] != current:
            if current is not None:
                yield current, " ".join(parts)
            current, parts = row["story_id"], []
        parts.append(f"{row['title'] or ''} {row['summary'] or ''}")
    if current is not None:
        yield current, " ".join(parts)


def for_stories(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, list[str]]:
    """Facet slugs per story, for the bundle."""
    if not story_ids:
        return {}
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list[str]] = {}
    for row in conn.execute(
        f"SELECT story_id, slug FROM story_facets WHERE story_id IN ({placeholders})",
        story_ids,
    ):
        found.setdefault(row["story_id"], []).append(row["slug"])
    return found
