"""Static export, for hosting the feed without a server.

Every read endpoint returns a slice of the same database, and that database only
changes when the pipeline runs -- so the whole API collapses into one JSON
bundle that can be generated ahead of time and served from anywhere.

The bundle is the contract for both deployments: the server returns it live at
/data.json, and this writes the identical shape to disk. The page cannot tell
the difference, so there is no second frontend to keep in step.
"""

from __future__ import annotations

import base64
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from tributary import embeddings, entities, facets, topics, triage
from tributary import feed as feed_mod
from tributary.text import truncate

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_LIMIT = 80
DEFAULT_DAYS = 30
# Item blurbs are for scanning a story's members, not reading them, and every
# one of them is paid for by all eighty stories in the bundle.
ITEM_SUMMARY_LIMIT = 220

# Adapters name engagement differently; the page should not have to care.
_METRICS = (("points", ("points", "upvotes", "likes")), ("comments", ("num_comments",)))


def _engagement(raw: str | None) -> dict | None:
    """Vote and comment counts lifted out of an item's metadata blob.

    This is the community signal -- how much argument a story actually drew --
    and it is the whole reason the detail sheet is worth opening.
    """
    try:
        metadata = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(metadata, dict):
        return None

    found = {}
    for name, keys in _METRICS:
        value = next((metadata[key] for key in keys if isinstance(metadata.get(key), int)), None)
        if value:
            found[name] = value
    return found or None


# A centroid is packed one byte per dimension. Measured against a bge-shaped
# spread of cosines over 2000 stories: mean error 0.0026, worst 0.011, the top
# ten by similarity keeping nine of their places, and one story in two thousand
# crossing a 0.75 threshold it should not have. Below what a filter can show,
# and a quarter of what float32 would cost to deliver.
VECTOR_SCALE = 127


def _centroids(conn: sqlite3.Connection, story_ids: list[int]) -> dict[int, str]:
    """Each story's centroid, quantised to int8 and base64-encoded.

    This is what lets the page answer "like this one" with no server behind it:
    a personal lens is a cosine against vectors that are already on screen. It
    is `topics.centroids` rather than a second mean, so the page and the
    labeller agree about what a story is.

    int8 because the bundle is fetched on a phone: measured at `--limit 120`,
    the vectors add 60KB raw and 40KB gzipped, where float32 would be four
    times that. Base64 rather than a JSON array of numbers, which would be
    three times the characters again. The service worker caches the shell and
    never the feed, so this is paid on every load -- worth it because the
    vectors are not a lens-only luxury: a related-topics row wants them on
    every story, for every reader. If that stops being true, the cheap move is
    a second static file fetched on demand, not float32.

    A story whose items were never embedded is simply absent, and the page has
    to tolerate a card without a vector.
    """
    found, vectors = topics.centroids(conn, story_ids)
    if not found:
        return {}
    packed = np.clip(np.rint(vectors * VECTOR_SCALE), -VECTOR_SCALE, VECTOR_SCALE).astype(np.int8)
    return {
        story_id: base64.b64encode(row.tobytes()).decode("ascii")
        for story_id, row in zip(found, packed, strict=True)
    }


def build_bundle(
    conn: sqlite3.Connection,
    limit: int = DEFAULT_LIMIT,
    days: int | None = DEFAULT_DAYS,
    facet_names: list | None = None,
    spine: list | None = None,
) -> dict:
    """Everything the page needs, in one object.

    Story items are embedded rather than fetched per story: a feed of 80 stories
    is a few hundred kilobytes, and one request beats eighty.
    """
    # Newest first, not best first. The page's default feed is chronological,
    # so the bundle is selected by date; every card still carries `score`, which
    # is what Trending sorts by.
    cards = feed_mod.recent(conn, limit=limit, days=days, include_seen=True)
    story_ids = [card.story_id for card in cards]
    labels = topics.for_stories(conn, story_ids)
    marks = facets.for_stories(conn, story_ids)
    named = entities.for_stories(conn, story_ids)
    vectors = _centroids(conn, story_ids)

    stories = []
    for card in cards:
        found = feed_mod.detail(conn, card.story_id)
        items = found[1] if found else []
        engagements = [found for item in items if (found := _engagement(item["metadata"]))]
        stories.append(
            {
                "story_id": card.story_id,
                "title": card.title,
                "summary": card.summary,
                "url": card.url,
                "kind": card.kind,
                "source": card.source,
                "sources": card.sources,
                "published_at": card.published_at,
                # Two dates, because they answer different questions: when the
                # news happened, and when this story last grew. The feed orders
                # by the first; the second is what "active 2h ago" reports.
                "last_activity": card.last_activity,
                "score": round(card.score, 4),
                "signal": card.signal(),
                "item_count": card.item_count,
                "media_url": card.media_url,
                # What the story *is*, as a number, so the page can compare one
                # story to another without asking anyone. None when nothing in
                # the story was embedded.
                "centroid": vectors.get(card.story_id),
                "topics": labels.get(card.story_id, []),
                # Where it lives, what it is, who it is about: three axes, and
                # only the first is a place you browse to.
                "facets": marks.get(card.story_id, []),
                "entities": named.get(card.story_id, []),
                # The loudest thread wins the card: two small threads are not
                # the same story-level signal as one big argument.
                "engagement": {
                    name: biggest
                    for name in ("points", "comments")
                    if (biggest := max((e.get(name, 0) for e in engagements), default=0))
                }
                or None,
                "items": [
                    {
                        "role": item["role"],
                        "kind": item["kind"],
                        "title": item["title"],
                        "url": item["url"],
                        "author": item["author"],
                        "source": item["source_name"],
                        "published_at": item["published_at"],
                        "summary": truncate(item["summary"], ITEM_SUMMARY_LIMIT),
                        "engagement": _engagement(item["metadata"]),
                    }
                    for item in items
                ],
            }
        )

    counts = triage.stats(conn)
    newest = conn.execute(
        "SELECT MAX(COALESCE(published_at, fetched_at)) m FROM items"
    ).fetchone()["m"]
    broken = [
        {"name": r["name"], "error": r["last_error"]}
        for r in conn.execute(
            "SELECT name, last_error FROM sources WHERE enabled = 1 AND last_error IS NOT NULL"
        )
    ]

    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": {
            "stories": conn.execute("SELECT COUNT(*) c FROM stories").fetchone()["c"],
            "newest_item": newest,
            "broken_sources": broken,
            **counts,
        },
        # Facets are stored by slug, so the page is told what to call them.
        # Passing them through beats deriving a label from the slug, which would
        # quietly rename a facet whenever someone edited the config.
        "facets": [{"slug": f.slug, "name": f.name} for f in facet_names or []],
        # The whole spine, for the same reason -- but the reason is sharper for
        # topics. A story carries the name of its own topic, so the page can
        # name anything it is showing; a *follow* is a stored slug, and a
        # followed subject with nothing in this bundle has no story to carry its
        # name. Without this it cannot be listed, so it cannot be unfollowed:
        # an invisible follow that still decides what the feed holds.
        "spine": _spine(spine),
        # How the centroids above were packed. Declared rather than assumed:
        # the bundle is the contract, and a page that guessed the scale would
        # score noise rather than fail. An older page ignores the key.
        "vectors": {
            "encoding": "int8",
            "dimension": embeddings.DIMENSION,
            "scale": VECTOR_SCALE,
        },
        "stories": stories,
    }


def _spine(spine: list | None) -> list[dict]:
    """Every topic by slug and name, each shelf-dweller carrying its shelf.

    Shaped exactly like the labels on a story, so the page has one way to read a
    topic wherever it came from.
    """
    names = {t.slug: t.name for t in spine or []}
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "parent": t.parent,
            "parent_name": names.get(t.parent) if t.parent else None,
        }
        for t in spine or []
    ]


def write_site(
    conn: sqlite3.Connection,
    out_dir: Path,
    limit: int = DEFAULT_LIMIT,
    days: int | None = DEFAULT_DAYS,
    facet_names: list | None = None,
    spine: list | None = None,
) -> dict:
    """Write a self-contained static site into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "manifest.json", "sw.js", "icon.svg"):
        shutil.copy2(WEB_DIR / name, out_dir / name)

    bundle = build_bundle(
        conn, limit=limit, days=days, facet_names=facet_names, spine=spine
    )
    data_file = out_dir / "data.json"
    data_file.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")))

    # Tells GitHub Pages not to run the files through Jekyll, which would
    # otherwise ignore anything beginning with an underscore.
    (out_dir / ".nojekyll").write_text("")

    return {
        "stories": len(bundle["stories"]),
        "bytes": data_file.stat().st_size,
        "path": out_dir,
    }
