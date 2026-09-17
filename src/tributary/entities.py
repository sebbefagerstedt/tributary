"""Stage 6b: entities.

Who a story is about. A new model is its lab *and* its model line *and* a
frontier release -- three different questions, and only the last one is a topic.
Without this axis the other two get forced into the topic spine, which is what
made topics read as strange: `OpenAI` is not a place you browse, it is something
you follow.

Matched by name and alias, never by similarity. These are proper nouns, and
recognising one does not need a model -- which also means this axis cannot drift
when the embedding does. `identity.py` already extracts the machine-readable
half (arXiv ids, hub repos, GitHub repos) for clustering; this is the half a
reader would recognise.

Seeded entities come from the config. Everything else is proposed for a human to
accept, which is the same rule topics follow and the reason the namespace does
not fill with junk.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field

from tributary.config import EntityConfig
from tributary.db import transaction
from tributary.facets import story_texts


@dataclass(slots=True)
class EntityResult:
    stories: int = 0
    matched: int = 0  # stories carrying at least one entity
    by_entity: dict[str, int] = field(default_factory=dict)


def sync(conn: sqlite3.Connection, seeded: list[EntityConfig]) -> dict[str, int]:
    """Make the entities table hold the seeded list, and return name -> id.

    Accepted entities that came from extraction are left alone: this only owns
    the rows it seeded, so a human's decision is never overwritten by a config
    edit.
    """
    with transaction(conn):
        for entity in seeded:
            conn.execute(
                "INSERT INTO entities (kind, name, aliases) VALUES (?, ?, ?) "
                "ON CONFLICT (kind, name) DO UPDATE SET aliases = excluded.aliases",
                (entity.kind, entity.name, json.dumps(entity.aliases)),
            )
        return {
            f"{row['kind']}:{row['name']}": row["id"]
            for row in conn.execute("SELECT id, kind, name FROM entities")
        }


def _pattern(entity: EntityConfig) -> re.Pattern:
    """One pattern per entity, covering its name and every alias.

    Word-bounded so `Phi` does not match `philosophy`, and longest-first so
    `GPT-4o` is preferred over `GPT` when both would fit.
    """
    names = sorted(entity.names(), key=len, reverse=True)
    return re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w)",
        re.IGNORECASE,
    )


def run(conn: sqlite3.Connection, seeded: list[EntityConfig]) -> EntityResult:
    """Attach every seeded entity to the stories that name it."""
    result = EntityResult()
    ids = sync(conn, seeded)
    with transaction(conn):
        conn.execute("DELETE FROM story_entities")
        if not seeded:
            return result

        patterns = [(f"{e.kind}:{e.name}", _pattern(e)) for e in seeded]
        for story_id, text in story_texts(conn):
            result.stories += 1
            hit = False
            for key, pattern in patterns:
                if pattern.search(text):
                    conn.execute(
                        "INSERT OR IGNORE INTO story_entities (story_id, entity_id) "
                        "VALUES (?, ?)",
                        (story_id, ids[key]),
                    )
                    result.by_entity[key] = result.by_entity.get(key, 0) + 1
                    hit = True
            result.matched += hit
    return result


def for_stories(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, list[dict]]:
    """Entity names and kinds per story, for the bundle."""
    if not story_ids:
        return {}
    placeholders = ",".join("?" * len(story_ids))
    found: dict[int, list[dict]] = {}
    for row in conn.execute(
        f"""
        SELECT se.story_id, e.kind, e.name
          FROM story_entities se
          JOIN entities e ON e.id = se.entity_id
         WHERE se.story_id IN ({placeholders})
         ORDER BY e.name
        """,
        story_ids,
    ):
        found.setdefault(row["story_id"], []).append(
            {"kind": row["kind"], "name": row["name"]}
        )
    return found
