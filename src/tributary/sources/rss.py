"""RSS/Atom adapter.

Fetching goes through httpx rather than letting feedparser do it, so we control
timeouts and can send conditional-GET headers: polling a few dozen feeds every
half hour should mostly return 304s.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from time import struct_time

import feedparser

from tributary.http import request
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.text import strip_boilerplate, strip_html, truncate

SUMMARY_LIMIT = 2000

# What a failing feed gets to say about itself. "unparseable feed (not
# well-formed, invalid token)" was the whole of the old message, and it is not
# enough to act on: MarkTechPost reported exactly that for weeks and the
# hypothesis it invites -- broken XML from a sloppy CMS -- turns out to be the
# one thing it cannot be. feedparser recovers from malformed XML remarkably
# well; a stray ampersand, an undeclared &nbsp;, a control character, junk above
# the declaration and a truncated document all still yield their items. Nothing
# structurally wrong with *XML* produces zero entries.
#
# What does: a body that is not XML at all. A JSON error, a bot-check page, a
# body in an encoding that contradicts its declaration, or bytes that were never
# decompressed. Those need entirely different fixes from each other -- and the
# only way to tell them apart is to look at what arrived, so that is what this
# reports.
_HTML = re.compile(rb"\s*<(?:!doctype\s+html|html)\b", re.I)
PREVIEW = 100


def _to_datetime(parsed: struct_time | None) -> datetime | None:
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
# Kept raw, deduplicated and capped; `identity._cited` decides which count.
LINK_LIMIT = 20


def _links(html_text: str | None) -> list[str]:
    """The links in an entry's summary, in order, before the HTML is flattened.

    Only the summary, not the full content: what a post links in its description
    is what it is about, while a full article links everything it mentions.
    """
    found: list[str] = []
    for href in _HREF.findall(html_text or ""):
        href = html.unescape(href).strip()
        if href not in found:
            found.append(href)
    return found[:LINK_LIMIT]


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
        # An empty but well-formed feed is legal: a source with nothing new is
        # not a broken source, and `version` is set for a feed even when it
        # carries no items. Everything else with no entries is a real failure,
        # including the ones feedparser is too forgiving to flag.
        if not parsed.entries and not parsed.get("version"):
            raise FetchError(_diagnose(response, parsed))

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
            metadata={"feed": self.config.url}
            | ({"links": links} if (links := _links(entry.get("summary"))) else {}),
        )


def _diagnose(response, parsed) -> str:
    """Say what actually arrived, since it was not a feed.

    The content type, the size and the opening bytes separate the four causes
    from each other at a glance, which the parser's own message cannot do.
    """
    body = response.content
    content_type = (response.headers.get("content-type") or "unknown").split(";")[0].strip()
    shape = f"{content_type}, {len(body)} bytes"

    if not body:
        return f"empty response ({shape})"

    if _HTML.match(body):
        # A login wall, a rate-limit notice or a bot check, served with a 200
        # so nothing upstream treats it as an error.
        title = strip_html(body[:2000].decode("utf-8", "replace"))
        return f"served a web page, not a feed ({shape}): {truncate(title, PREVIEW)}"

    opening = body[:PREVIEW].decode("utf-8", "replace").strip()
    detail = parsed.get("bozo_exception") or "no entries and no feed version"
    return f"not a feed ({shape}): {detail}; body starts {opening!r}"
