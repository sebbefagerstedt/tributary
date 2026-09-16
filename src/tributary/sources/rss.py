"""RSS/Atom adapter.

Fetching goes through httpx rather than letting feedparser do it, so we control
timeouts and can send conditional-GET headers: polling a few dozen feeds every
half hour should mostly return 304s.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import struct_time

import feedparser

from tributary.http import request
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.text import strip_boilerplate, strip_html, truncate

SUMMARY_LIMIT = 2000


def _to_datetime(parsed: struct_time | None) -> datetime | None:
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _media_url(entry) -> str | None:
    """Best available image for the card, checked in decreasing order of quality."""
    for item in entry.get("media_content", []) or []:
        if url := item.get("url"):
            return url
    for item in entry.get("media_thumbnail", []) or []:
        if url := item.get("url"):
            return url
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image/"):
            return link.get("href")
    return None


@register
class RSSSource(Source):
    kind = "rss"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        url = self.config.url
        if not url:
            raise FetchError("rss source requires a url")

        response, new_state = request(url, state=state)
        if response is None:
            return [], new_state

        parsed = feedparser.parse(response.content)
        # bozo marks malformed feeds; many still parse usefully, so only fail when
        # nothing came back at all.
        if parsed.bozo and not parsed.entries:
            raise FetchError(f"unparseable feed ({parsed.bozo_exception})")

        items = [built for entry in parsed.entries if (built := self._build(entry))]
        return items, new_state

    def _build(self, entry) -> RawItem | None:
        link = entry.get("link")
        title = strip_html(entry.get("title"))
        if not link or not title:
            return None  # an entry without a link or title is not addressable

        published = _to_datetime(entry.get("published_parsed")) or _to_datetime(
            entry.get("updated_parsed")
        )
        return RawItem(
            # Prefer the feed's own guid; fall back to the link, which is stable enough.
            external_id=entry.get("id") or link,
            kind=Kind.ARTICLE,
            url=link,
            title=title,
            author=entry.get("author") or None,
            published_at=published,
            summary=truncate(strip_boilerplate(strip_html(entry.get("summary"))), SUMMARY_LIMIT),
            media_url=_media_url(entry),
            metadata={"feed": self.config.url},
        )
