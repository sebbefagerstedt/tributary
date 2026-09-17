"""Persistence for sources and items.

Adapters produce ``RawItem``s; everything that touches the database lives here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from tributary.config import SourceConfig
from tributary.db import transaction
from tributary.models import RawItem
from tributary.urls import canonicalize


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_hash(item: RawItem) -> str:
    """Fingerprint the fields an upstream edit would change.

    Kept separate from identity: ``(source_id, external_id)`` says *which* item
    this is, the hash says whether it still holds the same content.
    """
    parts = [
        item.kind, item.url, item.title, item.author or "",
        _iso(item.published_at) or "", item.summary or "", item.body or "",
        item.media_url or "",
    ]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


@dataclass(slots=True)
class SourceRow:
    id: int
    kind: str
    name: str
    url: str | None
    state: dict


# Items older than this are dropped at ingest instead of inserted, and the
# number matches `trib prune --days`, so nothing is stored that the next prune
# would immediately delete.
#
# Without this the pipeline churns. Feeds that serve their whole archive have no
# cursor and no useful validators, so every run re-delivers the same years-old
# entries: they insert as new, get embedded, triaged and clustered, are deleted
# by prune minutes later, and arrive again three hours after that. Measured on
# the scheduled run of 2026-09-17 -- 1298 inserted, *zero* updated, 1295 pruned,
# with embedding alone taking 45 seconds of it.
MAX_ITEM_AGE_DAYS = 60


@dataclass(slots=True)
class IngestResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    stale: int = 0  # older than the retention window, so never stored

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged + self.stale


def sync_sources(conn: sqlite3.Connection, configs: list[SourceConfig]) -> list[SourceRow]:
    """Reconcile the config file's sources into the database.

    The config file is the source of truth for which sources exist and their
    options; the database keeps identity and fetch state across runs. Sources
    dropped from the config are disabled rather than deleted, so their items
    survive.
    """
    with transaction(conn):
        configured = {(c.kind, c.name) for c in configs}
        for cfg in configs:
            conn.execute(
                """
                INSERT INTO sources (kind, name, url, config, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (kind, name) DO UPDATE SET
                    url     = excluded.url,
                    config  = excluded.config,
                    enabled = excluded.enabled
                """,
                (cfg.kind, cfg.name, cfg.url, json.dumps(cfg.options), int(cfg.enabled)),
            )
        for row in conn.execute("SELECT id, kind, name FROM sources WHERE enabled = 1"):
            if (row["kind"], row["name"]) not in configured:
                conn.execute("UPDATE sources SET enabled = 0 WHERE id = ?", (row["id"],))

    return [
        SourceRow(
            id=r["id"],
            kind=r["kind"],
            name=r["name"],
            url=r["url"],
            state=json.loads(r["state"]),
        )
        for r in conn.execute(
            "SELECT id, kind, name, url, state FROM sources WHERE enabled = 1 ORDER BY kind, name"
        )
    ]


def _is_stale(item: RawItem, cutoff: datetime | None) -> bool:
    """Too old to be worth storing. An undated item is treated as current."""
    if cutoff is None or item.published_at is None:
        return False
    published = item.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    return published < cutoff


def record_items(
    conn: sqlite3.Connection,
    source_id: int,
    items: list[RawItem],
    max_age_days: int | None = MAX_ITEM_AGE_DAYS,
) -> IngestResult:
    """Insert new items and refresh content on ones already seen.

    Re-fetching is idempotent on ``(source_id, external_id)``. Upstream edits to
    a title or summary are picked up, but triage state is never clobbered — a
    corrected typo should not send an item back through the pipeline.

    Anything older than ``max_age_days`` is dropped here rather than inserted:
    see ``MAX_ITEM_AGE_DAYS``. Pass ``None`` to keep everything.
    """
    result = IngestResult()
    if not items:
        return result

    cutoff = (
        datetime.now(UTC) - timedelta(days=max_age_days) if max_age_days is not None else None
    )
    with transaction(conn):
        existing = {
            r["external_id"]: r["content_hash"]
            for r in conn.execute(
                "SELECT external_id, content_hash FROM items WHERE source_id = ?", (source_id,)
            )
        }
        for item in items:
            # Checked before the hash so an archive feed costs nothing to skip,
            # but after nothing else: an item already stored stays stored, and
            # ages out through prune rather than vanishing mid-window.
            if item.external_id not in existing and _is_stale(item, cutoff):
                result.stale += 1
                continue

            digest = content_hash(item)
            if existing.get(item.external_id) == digest:
                result.unchanged += 1
                continue

            values = (
                item.kind,
                item.url,
                canonicalize(item.url),
                item.title,
                item.author,
                _iso(item.published_at),
                item.summary,
                item.body,
                item.media_url,
                json.dumps(item.metadata),
                digest,
            )
            if item.external_id in existing:
                conn.execute(
                    """
                    UPDATE items SET
                        kind = ?, url = ?, canonical_url = ?, title = ?, author = ?,
                        published_at = ?, summary = ?, body = ?, media_url = ?,
                        metadata = ?, content_hash = ?
                    WHERE source_id = ? AND external_id = ?
                    """,
                    (*values, source_id, item.external_id),
                )
                result.updated += 1
            else:
                conn.execute(
                    """
                    INSERT INTO items (
                        source_id, external_id, kind, url, canonical_url, title, author,
                        published_at, summary, body, media_url, metadata, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (source_id, item.external_id, *values),
                )
                result.inserted += 1
    return result


def mark_fetched(
    conn: sqlite3.Connection,
    source_id: int,
    state: dict | None = None,
    error: str | None = None,
) -> None:
    """Record the outcome of a fetch. A failure keeps the previous state."""
    if error is None:
        conn.execute(
            """
            UPDATE sources
               SET last_fetched_at = ?, state = ?, last_error = NULL, last_error_at = NULL
             WHERE id = ?
            """,
            (utcnow(), json.dumps(state or {}), source_id),
        )
    else:
        conn.execute(
            """
            UPDATE sources
               SET last_fetched_at = ?, last_error = ?, last_error_at = ?
             WHERE id = ?
            """,
            (utcnow(), error, utcnow(), source_id),
        )


def recent_items(
    conn: sqlite3.Connection, limit: int = 50, state: str | None = None
) -> list[sqlite3.Row]:
    where = "WHERE i.triage_state = ?" if state else ""
    params = (state, limit) if state else (limit,)
    return list(
        conn.execute(
            f"""
            SELECT i.id, i.kind, i.title, i.url, i.author, i.published_at,
                   i.summary, i.triage_state, i.triage_score, s.name AS source_name
              FROM items i
              JOIN sources s ON s.id = i.source_id
             {where}
             ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
             LIMIT ?
            """,
            params,
        )
    )


def source_health(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Per-source counts and last error — so a broken feed is visible, not a silent gap."""
    return list(
        conn.execute(
            """
            SELECT s.id, s.kind, s.name, s.enabled, s.last_fetched_at,
                   s.last_error, s.last_error_at,
                   COUNT(i.id) AS item_count,
                   MAX(COALESCE(i.published_at, i.fetched_at)) AS newest
              FROM sources s
              LEFT JOIN items i ON i.source_id = s.id
             GROUP BY s.id
             ORDER BY s.kind, s.name
            """
        )
    )


def prune(conn: sqlite3.Connection, days: int, keep_saved: bool = True) -> dict:
    """Delete items older than ``days``, and any story left with nothing in it.

    A personal feed does not need a two-year archive: the window that matters is
    the one the feed can show. Pruning is what keeps the database small enough to
    move around and quick to re-embed after a cache miss.

    Saved stories are exempt by default -- deleting something you deliberately
    kept would be the one unrecoverable thing this does.
    """
    cutoff = f"-{int(days)} days"
    exempt = (
        """
        AND NOT EXISTS (
            SELECT 1 FROM story_items si
              JOIN interactions x ON x.story_id = si.story_id AND x.action = 'saved'
             WHERE si.item_id = items.id
        )
        """
        if keep_saved
        else ""
    )

    with transaction(conn):
        removed = conn.execute(
            f"""
            DELETE FROM items
             WHERE COALESCE(published_at, fetched_at) < datetime('now', ?)
             {exempt}
            """,
            (cutoff,),
        ).rowcount
        # item_vectors is a vec0 virtual table, and SQLite foreign keys do not
        # apply to virtual tables -- so its rows are NOT cascaded and must be
        # cleared by hand. Vectors are the bulk of the database (1.5KB each), so
        # missing this makes pruning almost pointless. Matching on absence also
        # sweeps up any orphans left by earlier versions.
        vectors = conn.execute(
            "DELETE FROM item_vectors WHERE item_id NOT IN (SELECT id FROM items)"
        ).rowcount
        # story_items cascades with the item; a story with no items left is dead.
        orphans = conn.execute(
            "DELETE FROM stories WHERE NOT EXISTS "
            "(SELECT 1 FROM story_items si WHERE si.story_id = stories.id)"
        ).rowcount
    return {"items": removed, "stories": orphans, "vectors": vectors}


def vacuum(conn: sqlite3.Connection) -> None:
    """Reclaim the space a prune freed. Cannot run inside a transaction."""
    conn.execute("VACUUM")
