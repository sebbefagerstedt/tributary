"""Suggesting sources for a topic: what "Here is what we found" is built from.

Two kinds of question, answered differently (VISION.md, "Creating a topic"):

- **A site** ("theverge.com", a pasted link): find its feed with
  `discover.find` — the page's own `<link>`, then the well-known paths, then a
  news sitemap — and preview it by actually fetching it: its newest headlines
  and how many items it published in the last week.
- **A subject** ("AI video"): rank the sources Tributary already reads by how
  many of their recent stories fit the subject, by the same embeddings that
  place stories in topics. That covers what is already fetched; finding sources
  on the open web for a subject is the open question VISION.md leaves for this
  step, and the answer says so rather than pretending.

Nothing here writes. A suggestion becomes a source only when a reader adds it to
a topic (`readers.save_topic`).
"""

from __future__ import annotations

import re
import sqlite3
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

import feedparser
import numpy as np

from tributary import discover, topics
from tributary.http import FetchError, request

Embedder = Callable[[Sequence[str]], list[list[float]]]

# Unmeasured, like version 1's LENS_FLOOR: between bge's "unrelated" (~0.5) and
# its "same event" (0.92), and above the topic floor (0.55) because this is a
# filter, not an argmax. Measure it against real topics before trusting it.
FIT_FLOOR = 0.62
LATEST = 3
WINDOW_DAYS = 30

_SITE = re.compile(r"^(https?://)?[\w-]+(\.[\w-]+)+(/\S*)?$", re.I)


def looks_like_site(query: str) -> bool:
    return bool(_SITE.match(query.strip())) and " " not in query.strip()


def preview_feed(url: str) -> dict:
    """A feed's newest headlines and its items in the last seven days."""
    try:
        response, _ = request(url)
    except FetchError:
        return {"week": 0, "latest": []}
    if response is None:
        return {"week": 0, "latest": []}
    parsed = feedparser.parse(response.content)
    week_ago = time.time() - 7 * 86400
    week = 0
    for entry in parsed.entries:
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if stamp and time.mktime(stamp) >= week_ago:
            week += 1
    latest = [e.get("title", "").strip() for e in parsed.entries[:LATEST] if e.get("title")]
    return {"week": week, "latest": latest}


def for_site(conn: sqlite3.Connection, query: str) -> dict:
    """Feeds a site offers, each previewed, or why there are none."""
    try:
        found = discover.find(query)
    except FetchError as exc:
        return {"kind": "site", "sources": [], "note": str(exc)}
    known = {r["url"]: r["name"] for r in conn.execute("SELECT name, url FROM sources")}
    out = []
    for feed in found:
        preview = preview_feed(feed.url) if feed.kind == "rss" else {"week": 0, "latest": []}
        out.append({
            "name": known.get(feed.url, feed.title),
            "url": feed.url,
            "kind": feed.kind,
            "known": feed.url in known,
            **preview,
        })
    note = "" if out else "No feed found on that site."
    return {"kind": "site", "sources": out, "note": note}


def for_subject(conn: sqlite3.Connection, query: str, embed: Embedder, limit: int = 8) -> dict:
    """Known sources ranked by how many recent stories of theirs fit the subject."""
    since = (datetime.now(UTC) - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    story_ids = [
        r["id"] for r in conn.execute("SELECT id FROM stories WHERE last_activity >= ?", (since,))
    ]
    found, vectors = topics.centroids(conn, story_ids)
    note = ("Only the sources Tributary already reads are searched by subject for now; "
            "paste a site to add one from anywhere.")
    if not found:
        return {"kind": "subject", "sources": [], "note": note}
    try:
        q = np.asarray(embed([query])[0], dtype=np.float32)
    except Exception:  # noqa: BLE001 - offline, or the model download refused
        return {"kind": "subject", "sources": [],
                "note": "The embedding model could not load, so subjects cannot be "
                        "searched right now. Paste a site instead."}
    q /= np.linalg.norm(q) or 1.0
    fits = [sid for sid, score in zip(found, vectors @ q, strict=True) if score >= FIT_FLOOR]
    if not fits:
        return {"kind": "subject", "sources": [], "note": note}
    placeholders = ",".join("?" * len(fits))
    ranked = conn.execute(
        f"""
        SELECT s.id, s.name, s.kind, s.url, COUNT(DISTINCT si.story_id) AS fit
          FROM story_items si JOIN items i ON i.id = si.item_id JOIN sources s ON s.id = i.source_id
         WHERE si.story_id IN ({placeholders})
         GROUP BY s.id ORDER BY fit DESC, s.name LIMIT ?
        """,
        (*fits, limit),
    ).fetchall()
    return {"kind": "subject", "sources": [_known(conn, r) for r in ranked], "note": note}


def _known(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    week = conn.execute(
        "SELECT COUNT(*) c FROM items "
        "WHERE source_id = ? AND COALESCE(published_at, fetched_at) >= ?",
        (row["id"], week_ago),
    ).fetchone()["c"]
    latest = [r["title"] for r in conn.execute(
        "SELECT title FROM items WHERE source_id = ? "
        "ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?",
        (row["id"], LATEST),
    )]
    return {"name": row["name"], "url": row["url"], "kind": row["kind"], "known": True,
            "week": week, "latest": latest, "fit": row["fit"]}
