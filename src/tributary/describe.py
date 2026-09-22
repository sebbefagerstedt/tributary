"""Stage 1.5: describe.

Some sources hand over a title and nothing else. The hub's listing endpoints are
the worst offender -- a trending model arrives as `Agnes-AI/Agnes-3.0-Flash` with
no description at all -- but it is not the only one: a Hacker News item is a
headline plus a link, and a GitHub release is `ggml-org/llama.cpp b11003`, which
does not even say what llama.cpp is. All of them make a feed card that says
nothing and a story page that answers none of the question a reader has.

In every case the text is not missing from the world, only from the listing. So
this stage goes and gets it, from whichever of four places the item points at:

    body   the item already carries prose nobody reads -- release notes are
           stored in `body`, and only `summary` ever reaches the page
    card   a hub repo, whose model card describes it
    repo   a GitHub repo, whose one-line description says what the project is
    page   a linked article, whose <meta> description was written to be exactly
           this: a sentence saying what is on the page

They are tried in that order, cheapest first, and the first one that produces
something wins. `body` costs no request at all.

**A page is also where the picture is.** A card wants art and almost nothing in
this corpus supplies it -- arXiv, Hacker News and GitHub releases carry no image
at all -- so the same `<meta>` parse that finds the description takes `og:image`
while it is there. That makes an item worth visiting when it has prose but no
picture, which is most of the feed, so `pending` asks for either half and a step
that cannot supply the missing one is skipped. Only `page` yields art: a release
note, a model card and a repo blurb are all text.

This runs *before* embedding rather than after triage, which costs a few requests
on items that later get dropped. The trade is worth it: a bare repo id is also a
bare embedding, so an item with no summary is judged for relevance on its name
alone. Fetching first means the description feeds the vector, the triage
decision, identifier extraction and the card, all in the same pass.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from urllib.parse import urljoin

from tributary.db import transaction
from tributary.http import FetchError, get_json, request
from tributary.models import Kind
from tributary.text import strip_html, truncate

CARD_URL = "https://huggingface.co/{repo}/raw/main/README.md"
REPO_URL = "https://api.github.com/repos/{repo}"
SUMMARY_LIMIT = 600
DEFAULT_LIMIT = 60

# Strategy names. Also the order they are tried in, cheapest first.
BODY = "body"
CARD = "card"
REPO = "repo"
PAGE = "page"

# A page is read for its <head> only, and only that much of it. A description
# that has not appeared in the first quarter-megabyte is not going to.
HEAD_BYTES = 250_000

# Prose has to clear this to count. Markdown needs the higher bar because the
# residue of a stripped badge line ("· ·") is short and looks like text; a
# <meta> description or a repo blurb was written on purpose, so "LLM inference
# in C/C++" is exactly what we want and must not be thrown away for being terse.
MIN_PROSE = 40
MIN_WRITTEN = 18

# Model cards open with a YAML block, then usually a title, then badges, then
# finally a sentence saying what the thing is.
_FRONTMATTER = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_SKIP_PREFIXES = ("#", "|", ">", "-", "*", "+", "```", "<", "[!", ":")

# The hub's card template is mostly prose already, so "the first paragraph" finds
# the template's own words rather than anything about this model. Seen live: a
# card whose description came out as "Users (both direct and downstream) should
# be made aware of the risks, biases and limitations of the model. More
# information needed" -- true of every model ever published, and worse than the
# bare title it replaced.
_BOILERPLATE = (
    "more information needed",
    "this model card has been automatically generated",
    "model card of a",
    "should be made aware of the risks",
    "use the code below to get started",
    "carbon emissions can be estimated",
    "[optional]",
    "more details on the model",
    "direct use",
)


def prose_summary(markdown: str | None) -> str | None:
    """The first sentence of real prose in a markdown document.

    Used for model cards and for release notes, which have the same shape:
    everything above the prose describes the repository rather than the thing --
    the YAML header, the title, and a wall of badges. A changelog of pull-request
    links is all list items and therefore yields nothing, which is correct; a
    release that opens with a written paragraph yields that paragraph.
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
        if not text or len(text) <= MIN_PROSE:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _BOILERPLATE):
            continue
        return truncate(text, SUMMARY_LIMIT)
    return None


# Kept: this is what the hub strategy reads, and the name says which.
card_summary = prose_summary


_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w:.-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")
_HEAD_END = re.compile(r"</head\s*>", re.I)

# In preference order. og: is the one publishers actually maintain, because it
# is what every social platform shows; the bare `description` is often a site-wide
# tagline, so it goes last.
_DESCRIPTION_KEYS = ("og:description", "twitter:description", "description")

# Same reasoning, same order of trust. `og:image` is the one a publisher sets on
# purpose, because it is the card every social platform renders.
_IMAGE_KEYS = ("og:image", "og:image:url", "twitter:image", "twitter:image:src")


def _attributes(tag: str) -> dict[str, str]:
    return {
        name.lower(): (double or single or bare)
        for name, double, single, bare in _ATTR.findall(tag)
    }


_WANTED_KEYS = frozenset(_DESCRIPTION_KEYS) | frozenset(_IMAGE_KEYS)


def _head_meta(html: str | None) -> dict[str, str]:
    """Every ``<meta>`` in the head this stage has a use for, by key.

    One pass for both halves, which is what makes taking the picture free: the
    page was already fetched and already parsed to find its description.
    """
    if not html:
        return {}
    head = _HEAD_END.split(html[:HEAD_BYTES], maxsplit=1)[0]
    found: dict[str, str] = {}
    for tag in _META.findall(head):
        attributes = _attributes(tag)
        key = (attributes.get("property") or attributes.get("name") or "").lower()
        content = attributes.get("content")
        if key in _WANTED_KEYS and content and key not in found:
            found[key] = content
    return found


def page_summary(html: str | None) -> str | None:
    """A page's own description, from its ``<meta>`` tags.

    Deliberately **only** the meta tags: no first-paragraph scraping. A page's
    body is cookie banners, navigation and newsletter prompts, and picking prose
    out of it is the part of scraping that goes wrong and keeps going wrong. A
    meta description, by contrast, was written to be a one-sentence summary and
    is machine-readable by design. If a page does not have one, this returns
    nothing and the item keeps its bare title -- which is the honest outcome.
    """
    found = _head_meta(html)
    for key in _DESCRIPTION_KEYS:
        text = strip_html(found.get(key))
        if text and len(text) >= MIN_WRITTEN:
            return truncate(text, SUMMARY_LIMIT)
    return None


def page_image(html: str | None, base_url: str = "") -> str | None:
    """A page's own card art, from the same ``<meta>`` tags.

    Resolved against the page it came from, because plenty of publishers write
    `og:image` as a path. Anything that does not come out as http(s) is dropped
    rather than guessed at -- a `data:` URI would be inlined into the bundle,
    and a relative path with no base is a broken `<img>` on the card.
    """
    found = _head_meta(html)
    for key in _IMAGE_KEYS:
        if not (raw := (found.get(key) or "").strip()):
            continue
        resolved = urljoin(base_url, strip_html(raw) or raw)
        if resolved.lower().startswith(("http://", "https://")):
            return resolved
    return None


@dataclass(frozen=True, slots=True)
class Step:
    """One way of describing an item, and what to look at."""

    strategy: str
    subject: str


@dataclass(frozen=True, slots=True)
class Found:
    """What one strategy managed to turn up. Either half may be missing."""

    summary: str | None = None
    media_url: str | None = None


@dataclass(frozen=True, slots=True)
class Target:
    """An item worth visiting, the ways to try in order, and what it lacks."""

    item_id: int
    steps: tuple[Step, ...]
    wants_summary: bool = True
    wants_media: bool = True


def _metadata(raw: str | None) -> dict:
    try:
        found = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _hub_repo(metadata: dict) -> str | None:
    """The hub path whose card would describe this item, if it is a hub item."""
    if repo := metadata.get("hf_id"):
        return str(repo)
    if dataset := metadata.get("hf_dataset"):
        return f"datasets/{dataset}"
    return None


def steps_for(row: sqlite3.Row, want_media: bool = False) -> tuple[Step, ...]:
    """Every way this item could be described, cheapest first.

    `want_media` adds one possibility and changes nothing else: an item that
    already describes itself may still be worth reading for its picture, and a
    page is the only place one is kept.
    """
    metadata = _metadata(row["metadata"])
    steps: list[Step] = []

    if body := row["body"]:
        steps.append(Step(BODY, body))
    if repo := _hub_repo(metadata):
        steps.append(Step(CARD, repo))
    if github := metadata.get("github_repo"):
        steps.append(Step(REPO, str(github)))

    # A Hacker News item *is* the discussion; the thing worth describing is what
    # was submitted, which lives in metadata. Everything else describes itself.
    if outbound := metadata.get("outbound_url"):
        steps.append(Step(PAGE, str(outbound)))
    elif row["url"] and (not steps or want_media):
        # Normally a last resort, when nothing cheaper describes the item. It is
        # also the only step that can return a picture, so an item that wants
        # one reads its page even though its prose is already settled.
        steps.append(Step(PAGE, row["url"]))

    return tuple(steps)


# Which strategies can supply which half. Text is text wherever it came from;
# art only ever comes off a web page.
_YIELDS_MEDIA = frozenset({PAGE})

# Kinds whose pages reliably carry card art, and are therefore worth a request
# for the picture alone. A publisher maintains `og:image` because it is what
# every social platform renders from their link. A paper, a release and a model
# card are not written that way, and firing a request at all ~235 arXiv
# abstracts a week on the chance one has a picture is a guess, not a measurement
# -- widen this once someone has checked, not before.
_ILLUSTRATED_KINDS = frozenset({Kind.ARTICLE, Kind.POST})


def _worth_illustrating(row: sqlite3.Row) -> bool:
    """Whether this item's page is likely enough to hold art to go and look.

    A discussion pointing outward counts, because the page fetched is the
    article somebody submitted, not the thread.
    """
    if row["kind"] in _ILLUSTRATED_KINDS:
        return True
    return bool(_metadata(row["metadata"]).get("outbound_url"))


def _useful(step: Step, target: Target) -> bool:
    """Whether running this step could still supply something wanted."""
    if target.wants_summary:
        return True
    return target.wants_media and step.strategy in _YIELDS_MEDIA


def pending(conn: sqlite3.Connection, limit: int = DEFAULT_LIMIT) -> list[Target]:
    """Items missing prose or art, newest first.

    Either half is reason enough to visit. Most of the feed arrives with a
    summary and no picture, so asking only for the summary -- which is what this
    did until 2026-09-22 -- meant art could only ever reach the few items that
    turned up with no words at all.
    """
    found: list[Target] = []
    for row in conn.execute(
        """
        SELECT i.id, i.url, i.body, i.metadata, i.summary, i.media_url, i.kind
          FROM items i
         WHERE ((i.summary IS NULL OR i.summary = '')
                OR (i.media_url IS NULL OR i.media_url = ''))
           AND i.id NOT IN (SELECT item_id FROM described)
         ORDER BY COALESCE(i.published_at, i.fetched_at) DESC
        """
    ):
        wants_media = not row["media_url"] and _worth_illustrating(row)
        target = Target(
            row["id"],
            steps_for(row, want_media=wants_media),
            wants_summary=not row["summary"],
            wants_media=wants_media,
        )
        if any(_useful(step, target) for step in target.steps):
            found.append(target)
            if len(found) >= limit:
                break
    return found


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    # Same budget as the releases adapter: 60 requests an hour unauthenticated,
    # 5000 with a token. One request per repo, and repos repeat across releases.
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _describe(step: Step, repo_cache: dict[str, str | None]) -> Found:
    """Run one strategy. A failed fetch is not an error, just nothing found."""
    if step.strategy == BODY:
        return Found(summary=prose_summary(step.subject))

    try:
        if step.strategy == CARD:
            response, _ = request(CARD_URL.format(repo=step.subject))
            return Found(summary=prose_summary(response.text) if response else None)

        if step.strategy == REPO:
            if step.subject not in repo_cache:
                payload, _ = get_json(REPO_URL.format(repo=step.subject), headers=_github_headers())
                described = (payload or {}).get("description")
                repo_cache[step.subject] = strip_html(described)
            text = repo_cache[step.subject]
            usable = text and len(text) >= MIN_WRITTEN
            return Found(summary=truncate(text, SUMMARY_LIMIT) if usable else None)

        response, _ = request(step.subject)
        if response is None:
            return Found()
        # A PDF or a tarball has no <meta> description and reading it as text
        # would be megabytes of nonsense through the regex.
        if not response.headers.get("content-type", "").lower().startswith("text/html"):
            return Found()
        # One fetch, one parse, both halves -- which is the whole argument for
        # taking the picture here rather than in a stage of its own.
        return Found(
            summary=page_summary(response.text),
            media_url=page_image(response.text, str(response.url)),
        )
    except FetchError:
        # A missing card, a renamed repo, a dead link, a 403 from a publisher
        # that dislikes robots -- none of it is worth failing the run over, and
        # the marker below stops us asking again.
        return Found()


def run(conn: sqlite3.Connection, limit: int = DEFAULT_LIMIT) -> dict:
    """Fill in missing prose and art, capped per run."""
    targets = pending(conn, limit)
    repo_cache: dict[str, str | None] = {}
    fetched: list[tuple[Target, Found]] = []
    for target in targets:
        summary = media_url = None
        for step in target.steps:
            if not _useful(step, target):
                continue
            found = _describe(step, repo_cache)
            summary = summary or found.summary
            media_url = media_url or found.media_url
            # Stop as soon as nothing is outstanding. A step is only run for
            # what the item is actually missing, so this is the whole job done.
            if (summary or not target.wants_summary) and (media_url or not target.wants_media):
                break
        fetched.append((target, Found(summary, media_url)))

    filled = illustrated = 0
    with transaction(conn):
        for target, found in fetched:
            if target.wants_summary and found.summary:
                # Clearing the vector and the verdict re-opens the item: it was
                # judged on a bare name, and there is more to go on now. Art
                # does not do this -- a picture changes no embedding.
                conn.execute(
                    "UPDATE items SET summary = ?, embedded_hash = NULL, "
                    "triage_state = 'pending', triage_score = NULL WHERE id = ?",
                    (found.summary, target.item_id),
                )
                filled += 1
            if target.wants_media and found.media_url:
                conn.execute(
                    "UPDATE items SET media_url = ? WHERE id = ?",
                    (found.media_url, target.item_id),
                )
                illustrated += 1
            # Recorded either way, so an item nothing describes is not refetched.
            conn.execute(
                "INSERT OR IGNORE INTO described (item_id) VALUES (?)", (target.item_id,)
            )
    return {"attempted": len(targets), "filled": filled, "illustrated": illustrated}


def reset(conn: sqlite3.Connection) -> None:
    """Forget what has been attempted, so improved parsing can be re-applied."""
    with transaction(conn):
        conn.execute("DELETE FROM described")
