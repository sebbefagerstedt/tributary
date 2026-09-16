"""Hacker News via the Algolia search API.

Algolia rather than the official Firebase API: one request returns titles,
scores, comment counts and outbound URLs together, where Firebase needs a
request per item. No auth, no rate limit worth worrying about.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tributary.http import get_json
from tributary.models import Kind, RawItem
from tributary.sources.base import Source, register

SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
DISCUSSION_URL = "https://news.ycombinator.com/item?id={}"
DEFAULT_MIN_POINTS = 50
DEFAULT_LIMIT = 100


@register
class HackerNewsSource(Source):
    kind = "hn"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        options = self.config.options
        filters = [f"points>={options.get('min_points', DEFAULT_MIN_POINTS)}"]
        # Only ask for what we haven't seen: Algolia sorts by date descending,
        # so the last seen timestamp is a clean high-water mark.
        if since := state.get("last_created_at_i"):
            filters.append(f"created_at_i>{since}")

        params = {
            "tags": options.get("tags", "story"),
            "numericFilters": ",".join(filters),
            "hitsPerPage": min(int(options.get("limit", DEFAULT_LIMIT)), 1000),
        }
        if query := options.get("query"):
            params["query"] = query

        payload, new_state = get_json(SEARCH_URL, params=params, state=state)
        if payload is None:
            return [], new_state

        hits = payload.get("hits", [])
        items = [built for hit in hits if (built := self._build(hit))]

        if timestamps := [h["created_at_i"] for h in hits if h.get("created_at_i")]:
            new_state["last_created_at_i"] = max(timestamps)
        return items, new_state

    def _build(self, hit: dict) -> RawItem | None:
        object_id = hit.get("objectID")
        title = hit.get("title")
        if not object_id or not title:
            return None

        discussion = DISCUSSION_URL.format(object_id)
        published = None
        if created := hit.get("created_at_i"):
            published = datetime.fromtimestamp(created, tz=UTC)

        return RawItem(
            external_id=object_id,
            kind=Kind.DISCUSSION,
            # The item *is* the discussion; the submitted link is a reference to
            # something else, and becomes a clustering join key in phase 2.
            url=discussion,
            title=title,
            author=hit.get("author"),
            published_at=published,
            metadata={
                "outbound_url": hit.get("url"),
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
            },
        )
