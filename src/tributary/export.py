"""Static export, for hosting the feed without a server.

Every read endpoint returns a slice of the same database, and that database only
changes when the pipeline runs -- so the whole API collapses into one JSON
bundle that can be generated ahead of time and served from anywhere.

The bundle is the contract for both deployments: the server returns it live at
/data.json, and this writes the identical shape to disk. The page cannot tell
the difference, so there is no second frontend to keep in step.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from tributary import feed as feed_mod
from tributary import topics, triage
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


def build_bundle(
    conn: sqlite3.Connection,
    limit: int = DEFAULT_LIMIT,
    days: int | None = DEFAULT_DAYS,
) -> dict:
    """Everything the page needs, in one object.

    Story items are embedded rather than fetched per story: a feed of 80 stories
    is a few hundred kilobytes, and one request beats eighty.
    """
    cards = feed_mod.build(conn, limit=limit, days=days, include_seen=True)
    labels = topics.for_stories(conn, [card.story_id for card in cards])

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
                "score": round(card.score, 4),
                "signal": card.signal(),
                "item_count": card.item_count,
                "media_url": card.media_url,
                "topics": labels.get(card.story_id, []),
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
        "stories": stories,
    }


def write_site(
    conn: sqlite3.Connection,
    out_dir: Path,
    limit: int = DEFAULT_LIMIT,
    days: int | None = DEFAULT_DAYS,
) -> dict:
    """Write a self-contained static site into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in ("index.html", "manifest.json", "sw.js", "icon.svg"):
        shutil.copy2(WEB_DIR / name, out_dir / name)

    bundle = build_bundle(conn, limit=limit, days=days)
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
