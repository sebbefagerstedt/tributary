"""Sitemap adapter: for a publisher that has no feed.

Anthropic is the case it was written for -- no feed on either domain, no
`application/rss+xml` in either page head -- and it is not alone among labs. A
sitemap is the one machine-readable list such a site still keeps, because search
engines need it. So this reads the sitemap, keeps the URLs under one path
(`include`, a regex over the URL), and visits each one it has not seen before
for the same `<meta>` tags `describe` reads: a title, a description, a date and
a picture. Never the page body, for the reason `describe.page_summary` gives.

Three things make it differ from a feed, each handled here:

- **A sitemap lists everything, forever.** Hundreds of old posts sit beside the
  new one. `lastmod` says which are recent when the site gives it; otherwise the
  first run takes what is there as a baseline and fetches nothing, and from
  then on only URLs that were not in the sitemap before are visited. Missing a
  back catalogue is better than spending a week of runs crawling it. That
  includes a `lastmod` which is really the site's build date: many generators
  stamp it on every URL alike, so dozens of "recent" pages on one or two days
  are read as no dates at all.
- **Each new item costs a request.** At most `limit` pages per run, newest
  `lastmod` first; the rest wait for the next run. A page is marked seen once it
  answered, whatever it said, so a page with no title is not retried forever --
  the marker-table rule, kept in fetch state because adapters own no tables.
- **A wrong `include` looks like quiet.** A sitemap that parses but has nothing
  under the path is reported as a failure, not as a source with no news, and so
  is a run where every page visit failed: that is a site refusing Actions, which
  is exactly what a new source needs to show on its first run.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta

from tributary.describe import head_meta, page_image, page_summary
from tributary.http import request
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.store import MAX_ITEM_AGE_DAYS
from tributary.text import strip_html, truncate

DEFAULT_LIMIT = 10
# A sitemap index names its children; a site big enough to split its sitemap
# is big enough that following every child would be a crawl.
MAX_CHILDREN = 20
PREVIEW = 100
# This many "recent" URLs dated on one or two days is a build stamp, not news:
# no lab publishes twenty posts in two days.
STAMPED = 20

_TITLE_KEYS = ("og:title", "twitter:title")
_DATE_KEYS = ("article:published_time", "og:published_time", "date", "publish_date")
_SITE_KEYS = ("og:site_name",)
_WANTED = frozenset(
    (*_TITLE_KEYS, *_DATE_KEYS, *_SITE_KEYS, "og:description", "twitter:description",
     "description", "og:image", "og:image:url", "twitter:image", "twitter:image:src")
)
_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title\s*>", re.I | re.S)
# What separates a page's title from its site's name: "Post | Site", "Post \ Site".
_SEPARATORS = " |\\-–—·:"


def _local(tag: str) -> str:
    """An element's name without its namespace, which every sitemap declares."""
    return tag.rsplit("}", 1)[-1]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _read(url: str) -> ET.Element:
    response, _ = request(url)
    body = response.content if response is not None else b""
    try:
        return ET.fromstring(body)
    except ET.ParseError as exc:
        opening = body[:PREVIEW].decode("utf-8", "replace").strip()
        raise FetchError(f"not a sitemap: {exc}; body starts {opening!r}") from exc


def entries(url: str) -> list[tuple[str, datetime | None]]:
    """Every `(loc, lastmod)` in a sitemap, following one level of index."""
    root = _read(url)
    if _local(root.tag) == "sitemapindex":
        children = [
            el.text.strip()
            for el in root.iter()
            if _local(el.tag) == "loc" and el.text
        ][:MAX_CHILDREN]
        found: list[tuple[str, datetime | None]] = []
        for child in children:
            found.extend(_urls(_read(child)))
        return found
    return _urls(root)


def _urls(root: ET.Element) -> list[tuple[str, datetime | None]]:
    found = []
    for node in root:
        if _local(node.tag) != "url":
            continue
        # Descendants, not children: a Google news sitemap dates an entry in a
        # nested <news:publication_date> rather than in <lastmod>.
        fields = {_local(el.tag): (el.text or "").strip() for el in node.iter()}
        if loc := fields.get("loc"):
            dated = fields.get("lastmod") or fields.get("publication_date")
            found.append((loc, _parse_date(dated)))
    return found


def page_title(html: str | None) -> str | None:
    """A page's headline: `og:title` if set, else `<title>` minus the site name."""
    found = head_meta(html, _WANTED)
    for key in _TITLE_KEYS:
        if title := strip_html(found.get(key)):
            return title
    match = _TITLE_TAG.search(html or "")
    title = strip_html(match.group(1)) if match else None
    if not title:
        return None
    site = strip_html(found.get("og:site_name"))
    if site and title.endswith(site) and title != site:
        title = title[: -len(site)].rstrip(_SEPARATORS) or title
    return title


@register
class SitemapSource(Source):
    kind = "sitemap"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        url = self.config.url
        include = self.config.options.get("include")
        if not url or not include:
            raise FetchError("sitemap source requires a url and an include pattern")
        limit = int(self.config.options.get("limit", DEFAULT_LIMIT))

        listed = entries(url)
        pattern = re.compile(include)
        wanted = [(loc, lastmod) for loc, lastmod in listed if pattern.search(loc)]
        if not wanted:
            raise FetchError(f"sitemap lists {len(listed)} URLs and none match {include!r}")

        seen = set(state.get("seen", []))
        first_run = "seen" not in state
        cutoff = datetime.now(UTC) - timedelta(days=MAX_ITEM_AGE_DAYS)
        if first_run:
            # A baseline: only what the sitemap itself dates as recent is news.
            candidates = [(loc, m) for loc, m in wanted if m and m >= cutoff]
            if len(candidates) >= STAMPED and len({m.date() for _, m in candidates}) <= 2:
                candidates = []  # the build date, stamped on every URL alike
            seen = {loc for loc, _ in wanted} - {loc for loc, _ in candidates}
        else:
            candidates = [(loc, m) for loc, m in wanted if loc not in seen]
        oldest = datetime.min.replace(tzinfo=UTC)
        candidates.sort(key=lambda pair: pair[1] or oldest, reverse=True)

        items: list[RawItem] = []
        errors: list[str] = []
        for loc, lastmod in candidates[:limit]:
            try:
                response, _ = request(loc)
            except FetchError as exc:
                errors.append(str(exc))
                continue  # unanswered, so left unseen and tried again next run
            seen.add(loc)
            if item := self._build(loc, lastmod, response.text if response else None):
                items.append(item)
        if errors and not items and len(errors) == min(len(candidates), limit):
            raise FetchError(f"every page visit failed ({len(errors)}): {errors[0]}")

        # Forget what the sitemap no longer lists, so the state cannot only grow.
        listed_now = {loc for loc, _ in wanted}
        return items, {"seen": sorted(seen & listed_now)}

    def _build(self, loc: str, lastmod: datetime | None, html: str | None) -> RawItem | None:
        title = page_title(html)
        if not title:
            return None
        found = head_meta(html, _WANTED)
        published = next(
            (d for key in _DATE_KEYS if (d := _parse_date(found.get(key)))), None
        ) or lastmod
        return RawItem(
            external_id=loc,
            kind=Kind.ARTICLE,
            url=loc,
            title=truncate(title, 300),
            published_at=published,
            summary=page_summary(html),
            media_url=page_image(html, loc),
            metadata={"sitemap": self.config.url},
        )
