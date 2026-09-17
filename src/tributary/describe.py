"""Stage 1.5: describe.

Some sources hand over a title and nothing else. The hub's listing endpoints are
the worst offender: a trending model arrives as `Agnes-AI/Agnes-3.0-Flash` with
no description at all, which makes a feed card that says nothing and a story page
that answers none of the question a reader actually has. The text is not missing
from the world, only from the listing -- the model card has it.

This runs *before* embedding rather than after triage, which costs a few requests
on items that later get dropped. The trade is worth it: a bare repo id is also a
bare embedding, so an item with no summary is judged for relevance on its name
alone. Fetching first means the description feeds the vector, the triage
decision, identifier extraction and the card, all in the same pass.
"""

from __future__ import annotations

import json
import re
import sqlite3

from tributary.db import transaction
from tributary.http import FetchError, request
from tributary.text import strip_html, truncate

CARD_URL = "https://huggingface.co/{repo}/raw/main/README.md"
SUMMARY_LIMIT = 600
DEFAULT_LIMIT = 60

# Model cards open with a YAML block, then usually a title, then badges, then
# finally a sentence saying what the thing is.
_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SKIP_PREFIXES = ("#", "|", ">", "-", "*", "+", "```", "<", "[!", ":")


def card_summary(markdown: str | None) -> str | None:
    """The first sentence of prose in a model card.

    Everything above it is boilerplate that describes the repository rather than
    the model: the YAML header, the title, and a wall of badges.
    """
    if not markdown:
        return None

    body = _FRONTMATTER.sub("", markdown, count=1)
    for block in body.split("\n\n"):
        text = _IMAGE.sub("", block).strip()
        if not text or text.startswith(_SKIP_PREFIXES):
            continue
        text = _LINK.sub(r"\1", text)
        text = strip_html(text.replace("\n", " "))
        # A line that was only badges and links leaves punctuation behind.
        if text and len(text) > 40:
            return truncate(text, SUMMARY_LIMIT)
    return None


def _hub_repo(metadata: str | None) -> str | None:
    """The hub path whose card would describe this item, if it is a hub item."""
    try:
        found = json.loads(metadata or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(found, dict):
        return None
    if repo := found.get("hf_id"):
        return str(repo)
    if dataset := found.get("hf_dataset"):
        return f"datasets/{dataset}"
    return None


def pending(conn: sqlite3.Connection, limit: int = DEFAULT_LIMIT) -> list[tuple[int, str]]:
    """Describable items with no summary yet, newest first."""
    found: list[tuple[int, str]] = []
    for row in conn.execute(
        """
        SELECT i.id, i.metadata
          FROM items i
         WHERE (i.summary IS NULL OR i.summary = '')
           AND i.id NOT IN (SELECT item_id FROM described)
         ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
        """
    ):
        if repo := _hub_repo(row["metadata"]):
            found.append((row["id"], repo))
            if len(found) >= limit:
                break
    return found


def run(conn: sqlite3.Connection, limit: int = DEFAULT_LIMIT) -> dict:
    """Fill in missing descriptions. One request per item, capped per run."""
    targets = pending(conn, limit)
    fetched: list[tuple[int, str | None]] = []
    for item_id, repo in targets:
        try:
            response, _ = request(CARD_URL.format(repo=repo))
        except FetchError:
            # A missing or private card is not worth failing the run over, and
            # the marker below stops us asking again.
            response = None
        fetched.append((item_id, card_summary(response.text) if response is not None else None))

    filled = 0
    with transaction(conn):
        for item_id, summary in fetched:
            if summary:
                # Clearing the vector and the verdict re-opens the item: it was
                # judged on a bare name, and there is more to go on now.
                conn.execute(
                    "UPDATE items SET summary = ?, embedded_hash = NULL, "
                    "triage_state = 'pending', triage_score = NULL WHERE id = ?",
                    (summary, item_id),
                )
                filled += 1
            # Recorded either way, so a card that does not exist is not refetched.
            conn.execute("INSERT OR IGNORE INTO described (item_id) VALUES (?)", (item_id,))
    return {"attempted": len(targets), "filled": filled}


def reset(conn: sqlite3.Connection) -> None:
    """Forget what has been attempted, so improved parsing can be re-applied."""
    with transaction(conn):
        conn.execute("DELETE FROM described")
