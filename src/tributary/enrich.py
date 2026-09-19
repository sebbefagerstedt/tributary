"""Stage 3: enrich.

Populates the identifiers table from item text and metadata. Kept separate from
fetching so extraction rules can be improved and re-run over the whole corpus
without re-fetching anything.
"""

from __future__ import annotations

import sqlite3

from tributary import identity
from tributary.db import transaction


def pending(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    """Items whose identifiers have not been extracted yet.

    Everything, not just what triage liked: an identifier is how tier-1
    clustering joins an item to the story it belongs to, and an item with no
    identifiers can only ever start a story of its own.
    """
    sql = """
        SELECT i.id, i.title, i.summary, i.body, i.url, i.canonical_url, i.metadata
          FROM items i
         WHERE NOT EXISTS (SELECT 1 FROM identifiers d WHERE d.item_id = i.id)
           AND i.id NOT IN (SELECT item_id FROM enriched)
         ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return list(conn.execute(sql))


def run(conn: sqlite3.Connection, limit: int | None = None) -> dict:
    """Extract identifiers for every pending item."""
    rows = pending(conn, limit)
    counts: dict[str, int] = {}
    with transaction(conn):
        for row in rows:
            for kind, value in identity.extract(row):
                conn.execute(
                    "INSERT OR IGNORE INTO identifiers (item_id, type, value) VALUES (?, ?, ?)",
                    (row["id"], kind, value),
                )
                counts[kind] = counts.get(kind, 0) + 1
            # Recorded even when nothing was found, so an item with no
            # identifiers is not rescanned on every run.
            conn.execute("INSERT OR IGNORE INTO enriched (item_id) VALUES (?)", (row["id"],))
    return {"items": len(rows), "by_type": counts}


def reset(conn: sqlite3.Connection) -> None:
    """Drop all identifiers so improved extraction rules can be re-applied."""
    with transaction(conn):
        conn.execute("DELETE FROM identifiers")
        conn.execute("DELETE FROM enriched")


def shared_identifiers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Strong identifiers held by more than one item: the candidate tier-1 joins."""
    placeholders = ",".join("?" * len(identity.STRONG))
    return list(
        conn.execute(
            f"""
            SELECT type, value, COUNT(DISTINCT item_id) AS items
              FROM identifiers
             WHERE type IN ({placeholders})
             GROUP BY type, value
            HAVING items > 1 AND items <= ?
             ORDER BY items DESC
            """,
            (*sorted(identity.STRONG), identity.MAX_FANOUT),
        )
    )
