"""Readers: the redesign's profiles, their topics, and the sources they chose.

Version 1 has one source list, in config.toml, for everyone. The redesign
(VISION.md) lets each reader follow topics and decide which sources feed them,
so this module keeps, per profile:

- **topics** — a name, a description, the sources chosen for it, muted words,
  and, for a topic the version-1 spine does not know, its description embedded,
  so the page can tell which stories fit;
- **seen** stories — read in one topic, read everywhere.

A profile is a name with no password. It protects nothing; it is what lets one
person's tree follow them from phone to laptop on the same server.

Sources a reader adds are rows in `sources` with `origin = 'reader'`. They are
fetched like any other while some topic uses them, and switched off when none
does — "fetch only what someone uses, and only once".
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sqlite3
from collections.abc import Callable, Sequence

import numpy as np

from tributary.db import transaction

# How a topic's description becomes a vector. Injected so tests never load the
# model (CLAUDE.md); the API passes `embeddings.embed`.
Embedder = Callable[[Sequence[str]], list[list[float]]]

log = logging.getLogger(__name__)

VECTOR_SCALE = 127  # the same int8 packing as export._centroids
MAX_NAME = 40


class ReaderError(ValueError):
    """Something a reader asked for that cannot be done, said plainly."""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "topic"


def pack(vector: Sequence[float]) -> str:
    """A unit vector as int8 and base64, exactly as the bundle packs centroids."""
    v = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(v))
    if norm:
        v = v / norm
    packed = np.clip(np.rint(v * VECTOR_SCALE), -VECTOR_SCALE, VECTOR_SCALE).astype(np.int8)
    return base64.b64encode(packed.tobytes()).decode("ascii")


# --- profiles ----------------------------------------------------------------


def list_profiles(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM profiles ORDER BY created_at, id")]


def ensure_profile(conn: sqlite3.Connection, name: str) -> int:
    clean = name.strip()[:MAX_NAME]
    if not clean:
        raise ReaderError("A profile needs a name.")
    with transaction(conn):
        conn.execute("INSERT OR IGNORE INTO profiles (name) VALUES (?)", (clean,))
    return conn.execute("SELECT id FROM profiles WHERE name = ?", (clean,)).fetchone()["id"]


def _profile_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM profiles WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise ReaderError(f"No profile called {name!r}.")
    return row["id"]


def get_profile(conn: sqlite3.Connection, name: str) -> dict:
    """Everything the page needs about one reader, in the shape it keeps locally."""
    pid = _profile_id(conn, name)
    row = conn.execute(
        "SELECT name, layout, onboarded FROM profiles WHERE id = ?", (pid,)
    ).fetchone()
    topics = []
    for t in conn.execute(
        "SELECT id, key, name, description, spine_slug, parent_key, vector, muted, examples "
        "FROM reader_topics WHERE profile_id = ? ORDER BY created_at, id",
        (pid,),
    ).fetchall():
        sources = [
            r["name"]
            for r in conn.execute(
                "SELECT s.name FROM reader_topic_sources ts JOIN sources s ON s.id = ts.source_id "
                "WHERE ts.topic_id = ? ORDER BY s.name",
                (t["id"],),
            )
        ]
        topics.append(
            {
                "id": t["key"],
                "name": t["name"],
                "description": t["description"],
                "spine": t["spine_slug"],
                "parent": t["parent_key"],
                "vector": t["vector"],
                "sources": sources,
                "muted": json.loads(t["muted"]),
                "examples": json.loads(t["examples"]),
            }
        )
    seen = [
        r["story_id"]
        for r in conn.execute(
            "SELECT story_id FROM reader_seen WHERE profile_id = ? ORDER BY seen_at", (pid,)
        )
    ]
    return {
        "name": row["name"],
        "layout": row["layout"],
        "onboarded": bool(row["onboarded"]),
        "topics": topics,
        "seen": seen,
    }


def update_profile(
    conn: sqlite3.Connection, name: str, *, layout: str | None = None, onboarded: bool | None = None
) -> None:
    pid = _profile_id(conn, name)
    with transaction(conn):
        if layout in ("grid", "cards"):
            conn.execute("UPDATE profiles SET layout = ? WHERE id = ?", (layout, pid))
        if onboarded is not None:
            conn.execute("UPDATE profiles SET onboarded = ? WHERE id = ?", (int(onboarded), pid))


def reset_profile(conn: sqlite3.Connection, name: str) -> None:
    """Start over: no topics, nothing seen, the welcome again."""
    pid = _profile_id(conn, name)
    with transaction(conn):
        conn.execute("DELETE FROM reader_topics WHERE profile_id = ?", (pid,))
        conn.execute("DELETE FROM reader_seen WHERE profile_id = ?", (pid,))
        conn.execute("UPDATE profiles SET onboarded = 0 WHERE id = ?", (pid,))
    reconcile_sources(conn)


def mark_seen(conn: sqlite3.Connection, name: str, story_ids: Sequence[int]) -> None:
    pid = _profile_id(conn, name)
    with transaction(conn):
        conn.executemany(
            "INSERT OR IGNORE INTO reader_seen (profile_id, story_id) VALUES (?, ?)",
            [(pid, int(s)) for s in story_ids],
        )


# --- topics ------------------------------------------------------------------


def _source_id(conn: sqlite3.Connection, spec: str | dict) -> int:
    """A source by name, or a new one a reader found (`{name, url, kind}`)."""
    if isinstance(spec, str):
        row = conn.execute(
            "SELECT id FROM sources WHERE name = ? ORDER BY origin = 'config' DESC", (spec,)
        ).fetchone()
        if row is None:
            raise ReaderError(f"No source called {spec!r}. Find it with discovery first.")
        return row["id"]
    name, url, kind = (spec.get("name") or "").strip(), spec.get("url"), spec.get("kind") or "rss"
    if not name or not url:
        raise ReaderError("A new source needs a name and a feed address.")
    if kind not in ("rss", "sitemap"):
        raise ReaderError(f"Readers can add feeds and news sitemaps, not {kind!r} sources.")
    options = {"include": spec["include"]} if kind == "sitemap" and spec.get("include") else {}
    row = conn.execute("SELECT id FROM sources WHERE url = ?", (url,)).fetchone()
    if row:
        return row["id"]
    conn.execute(
        "INSERT INTO sources (kind, name, url, config, origin) VALUES (?, ?, ?, ?, 'reader') "
        "ON CONFLICT (kind, name) DO UPDATE SET url = excluded.url",
        (kind, name, url, json.dumps(options)),
    )
    return conn.execute(
        "SELECT id FROM sources WHERE kind = ? AND name = ?", (kind, name)
    ).fetchone()["id"]


def save_topic(
    conn: sqlite3.Connection, profile: str, topic: dict, embed: Embedder | None = None
) -> dict:
    """Create or replace one of a reader's topics, with its sources and muted words.

    A topic the spine does not know gets its description embedded, once, so the
    page can tell which stories fit it (VISION.md: the fit filter stays).
    """
    pid = _profile_id(conn, profile)
    name = (topic.get("name") or "").strip()[:MAX_NAME]
    if not name:
        raise ReaderError("A topic needs a name.")
    key = topic.get("id") or slug(name)
    spine = topic.get("spine")
    description = (topic.get("description") or name).strip()
    muted = [w.strip() for w in topic.get("muted", []) if w and w.strip()]
    examples = sorted({int(i) for i in topic.get("examples") or []})
    existing = conn.execute(
        "SELECT id, description, vector FROM reader_topics WHERE profile_id = ? AND key = ?",
        (pid, key),
    ).fetchone()
    vector = existing["vector"] if existing and existing["description"] == description else None
    if examples:
        # Taught by stories: their vector, not the description's. Computed
        # here from the full-precision item vectors, and from what the page
        # sent if none of them is in the database any more.
        vector = _examples_vector(conn, examples) or topic.get("vector")
    with transaction(conn):
        if existing:
            conn.execute(
                "UPDATE reader_topics SET name = ?, description = ?, spine_slug = ?, "
                "parent_key = ?, vector = ?, muted = ?, examples = ? WHERE id = ?",
                (
                    name,
                    description,
                    spine,
                    topic.get("parent"),
                    vector,
                    json.dumps(muted),
                    json.dumps(examples),
                    existing["id"],
                ),
            )
            topic_id = existing["id"]
        else:
            topic_id = conn.execute(
                "INSERT INTO reader_topics (profile_id, key, name, description, spine_slug, "
                "parent_key, vector, muted, examples) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    key,
                    name,
                    description,
                    spine,
                    topic.get("parent"),
                    vector,
                    json.dumps(muted),
                    json.dumps(examples),
                ),
            ).lastrowid
        ids = {_source_id(conn, spec) for spec in topic.get("sources", [])}
        conn.execute("DELETE FROM reader_topic_sources WHERE topic_id = ?", (topic_id,))
        conn.executemany(
            "INSERT INTO reader_topic_sources (topic_id, source_id) VALUES (?, ?)",
            [(topic_id, i) for i in sorted(ids)],
        )
    # Embedded only once the topic and its sources are known to be valid, so a
    # mistake never costs a model load. A model that cannot load (offline, the
    # first download refused) leaves the topic saved without a vector: the page
    # still matches it by its words, and the next save tries again.
    if vector is None and not spine and embed is not None:
        try:
            packed = pack(embed([description])[0])
        except Exception as exc:  # noqa: BLE001 - any model failure degrades the same way
            log.warning("could not embed topic %r: %s", key, exc)
        else:
            with transaction(conn):
                conn.execute(
                    "UPDATE reader_topics SET vector = ? WHERE id = ?", (packed, topic_id)
                )
    reconcile_sources(conn)
    return next(t for t in get_profile(conn, profile)["topics"] if t["id"] == key)


def _examples_vector(conn: sqlite3.Connection, story_ids: list[int]) -> str | None:
    """The stories' centroids averaged and packed, or None if none is stored."""
    from tributary.topics import centroids  # topics imports the model stack

    found, vectors = centroids(conn, story_ids)
    if not found:
        return None
    mean = vectors.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    return pack(mean / norm) if norm else None


def delete_topic(conn: sqlite3.Connection, profile: str, key: str) -> None:
    pid = _profile_id(conn, profile)
    with transaction(conn):
        conn.execute("DELETE FROM reader_topics WHERE profile_id = ? AND key = ?", (pid, key))
    reconcile_sources(conn)


def reconcile_sources(conn: sqlite3.Connection) -> None:
    """A reader's source is fetched while some topic uses it, and not otherwise."""
    with transaction(conn):
        conn.execute(
            """
            UPDATE sources SET enabled = CASE WHEN EXISTS (
                SELECT 1 FROM reader_topic_sources ts WHERE ts.source_id = sources.id
            ) THEN 1 ELSE 0 END
            WHERE origin = 'reader'
            """
        )
