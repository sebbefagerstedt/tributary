"""Small text helpers. Feed summaries arrive as HTML fragments; we want plain text."""

from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# Tags become spaces so <p>a</p><p>b</p> reads "a b" -- but that leaves a gap
# before punctuation in "<b>word</b>." which would show up on every card.
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)\]}])")
_SPACE_AFTER_OPEN = re.compile(r"([(\[{])\s+")


def strip_html(value: str | None) -> str | None:
    """Flatten an HTML fragment to plain text. Returns None for empty input."""
    if not value:
        return None
    text = _TAG.sub(" ", value)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text).strip()
    return text or None


# arXiv's RSS feed (as opposed to its API) prefixes every abstract with
# "arXiv:2609.1234v1 Announce Type: new Abstract: ...". Left in, it is the first
# thing you read on every paper card and it says nothing.
_ARXIV_RSS_PREFIX = re.compile(
    r"^\s*arxiv:\s*\S+\s*(?:announce\s+type:\s*\w+)?\s*(?:abstract:)?\s*", re.I
)


# hnrss.org fills the description with link metadata that is already structured
# data elsewhere on the item.
_HN_RSS = re.compile(
    r"article url:\s*\S+|comments url:\s*\S+|points:\s*\d+|#\s*comments:\s*\d+", re.I
)


def strip_boilerplate(value: str | None) -> str | None:
    """Remove known feed boilerplate that carries no information."""
    if not value:
        return None
    cleaned = _ARXIV_RSS_PREFIX.sub("", value)
    cleaned = _HN_RSS.sub("", cleaned)
    cleaned = _WS.sub(" ", cleaned).strip()
    return cleaned or None


def truncate(value: str | None, limit: int) -> str | None:
    """Cut to ``limit`` characters on a word boundary where one is close by."""
    if value is None or len(value) <= limit:
        return value
    cut = value[:limit]
    space = cut.rfind(" ")
    if space > limit * 0.6:
        cut = cut[:space]
    return cut.rstrip() + "…"
