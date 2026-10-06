"""Static export, for hosting the feed without a server.

Every read endpoint returns a slice of the same database, and that database only
changes when the pipeline runs -- so the whole API collapses into one JSON
bundle that can be generated ahead of time and served from anywhere.

The bundle is the contract for both deployments: the server returns it live at
/data.json, and this writes the identical shape to disk. The page cannot tell
the difference, so there is no second frontend to keep in step.

The page is the React app in `web-next/` (VISION.md), built by `npm run build`
into `web-next/dist`. It lives in the repository rather than the package,
because it needs a build step; `write_site` copies it in when it has been
built, and the workflow builds it before exporting.
"""

from __future__ import annotations

import base64
import json
import shutil
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from tributary import embeddings, entities, facets, topics, triage
from tributary import feed as feed_mod
from tributary.text import truncate

# The built page. Version 1's single-file page lived in the package and was
# retired on 2026-10-05, when this one became the site.
APP_DIR = Path(__file__).resolve().parents[2] / "web-next" / "dist"
# Written by the dev-data script for `npm run dev`; never published.
_DEV_ONLY = {"dev-data.json"}
# No cap on the number of stories: the window is decided by time, not volume.
# A cap of 120 on the deployed site covered two or three days at this corpus's
# rate, so a subject quiet for a weekend -- AI video, reported 2026-09-25 --
# looked empty while thirty days of it sat in the database. Thirty days is about
# 1,300 stories, roughly a megabyte gzipped; the page draws fifty at a time.
DEFAULT_LIMIT = 0  # 0 means every story in the window
DEFAULT_DAYS = 30
# Item blurbs are for scanning a story's members, not reading them, and every
# one of them is paid for by every story in the bundle.
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
    keep_days_for: Callable[[str | None], int | None] | None = None,
    keep_most_for: Callable[[str | None], int | None] | None = None,
) -> dict:
    """Everything the page needs, in one object.

    Story items are embedded rather than fetched per story: one request beats a
    thousand. `limit` of 0 takes every story inside `days`. `keep_days_for`
    narrows that per topic (`TopicsConfig.keep_days_for`): general news arrives
    many times faster than AI news, and a month of it would not fit in a page.
    `keep_most_for` caps each topic at its newest stories as well: about 2,000
    general items a day arrived once the categories had feeds (2026-10-06), and
    four days of that made a 13 MB bundle.
    """
    # Newest first, not best first. The page's default feed is chronological,
    # so the bundle is selected by date; every card still carries `score`, which
    # is what Trending sorts by.
    cards = feed_mod.recent(conn, limit=limit, days=days, include_seen=True)
    story_ids = [card.story_id for card in cards]
    labels = topics.for_stories(conn, story_ids)
    if keep_days_for:
        now = datetime.now(UTC)

        def kept(card) -> bool:
            home = labels.get(card.story_id, [{}])[0].get("slug")
            window = keep_days_for(home)
            when = card.last_activity or card.published_at
            if not window or not when:
                return True
            at = datetime.fromisoformat(when.replace("Z", "+00:00"))
            if at.tzinfo is None:  # SQLite's datetime('now') carries no zone; it is UTC
                at = at.replace(tzinfo=UTC)
            age = now - at
            return age <= timedelta(days=window)

        cards = [card for card in cards if kept(card)]
        story_ids = [card.story_id for card in cards]
    if keep_most_for:
        # Cards come newest first, so the first N of each topic are its newest.
        seen: dict[str | None, int] = {}

        def room(card) -> bool:
            home = labels.get(card.story_id, [{}])[0].get("slug")
            seen[home] = seen.get(home, 0) + 1
            cap = keep_most_for(home)
            return not cap or seen[home] <= cap

        cards = [card for card in cards if room(card)]
        story_ids = [card.story_id for card in cards]
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
    topic wherever it came from. A topic with others under it also carries its
    description: those are written for people (only the bottom ones are
    scored), so the page shows it to say what a subject holds.
    """
    names = {t.slug: t.name for t in spine or []}
    has_children = {t.parent for t in spine or [] if t.parent}
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "parent": t.parent,
            "parent_name": names.get(t.parent) if t.parent else None,
            "description": t.description if t.slug in has_children else None,
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
    keep_days_for: Callable[[str | None], int | None] | None = None,
    keep_most_for: Callable[[str | None], int | None] | None = None,
) -> dict:
    """Write a static site into ``out_dir``: the bundle, and the page if built.

    Without a built page (`npm run build` in web-next/) only data.json is
    written, which is still a valid bundle for any page to read.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if APP_DIR.is_dir():
        shutil.copytree(
            APP_DIR, out_dir, dirs_exist_ok=True, ignore=lambda _d, names: _DEV_ONLY & set(names)
        )

    bundle = build_bundle(
        conn, limit=limit, days=days, facet_names=facet_names, spine=spine,
        keep_days_for=keep_days_for, keep_most_for=keep_most_for,
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
        "page": (out_dir / "index.html").is_file(),
    }
