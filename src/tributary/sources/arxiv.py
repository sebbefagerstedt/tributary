"""arXiv via the official Atom API.

Papers are keyed on the version-less id, so a v2 revision updates the existing
row instead of creating a near-duplicate that clustering would have to merge.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from time import struct_time

import feedparser

from tributary.http import request
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.text import strip_html

# arXiv serves an empty body over plain http; https is required.
API_URL = "https://export.arxiv.org/api/query"
DEFAULT_CATEGORIES = ["cs.AI", "cs.CL", "cs.LG"]
DEFAULT_MAX_RESULTS = 100
ABS_ID = re.compile(r"arxiv\.org/abs/(?P<id>[\w.\-/]+?)(?:v(?P<version>\d+))?$")


def _to_datetime(parsed: struct_time | None) -> datetime | None:
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


@register
class ArxivSource(Source):
    kind = "arxiv"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        options = self.config.options
        categories = options.get("categories") or DEFAULT_CATEGORIES
        search = " OR ".join(f"cat:{c}" for c in categories)
        if extra := options.get("query"):
            search = f"({search}) AND ({extra})"

        params = {
            "search_query": search,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": int(options.get("max_results", DEFAULT_MAX_RESULTS)),
        }

        # arXiv ignores conditional-GET headers, so state is not passed through.
        response, _ = request(API_URL, params=params)
        if response is None:
            return [], state

        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise FetchError(f"unparseable arXiv response ({parsed.bozo_exception})")

        return [built for entry in parsed.entries if (built := self._build(entry))], state

    def _build(self, entry) -> RawItem | None:
        link = entry.get("link")
        title = strip_html(entry.get("title"))
        if not link or not title:
            return None

        match = ABS_ID.search(link)
        if not match:
            return None
        paper_id = match.group("id")

        authors = [a["name"] for a in entry.get("authors", []) if a.get("name")]
        categories = [t["term"] for t in entry.get("tags", []) if t.get("term")]

        return RawItem(
            external_id=paper_id,  # version-less: a revision updates, never duplicates
            kind=Kind.PAPER,
            url=f"https://arxiv.org/abs/{paper_id}",
            title=title,
            author=_format_authors(authors),
            published_at=_to_datetime(entry.get("published_parsed")),
            summary=strip_html(entry.get("summary")),
            metadata={
                "arxiv_id": paper_id,
                "version": match.group("version"),
                "authors": authors,
                "categories": categories,
                "primary_category": (entry.get("arxiv_primary_category") or {}).get("term"),
                "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
                "updated_at": entry.get("updated"),
            },
        )


def _format_authors(authors: list[str]) -> str | None:
    if not authors:
        return None
    if len(authors) <= 2:
        return " and ".join(authors)
    return f"{authors[0]} et al."
