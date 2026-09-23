"""Extracting the join keys that link items across sources.

This is tier 1 of clustering, and the part nobody else does well. An arXiv
paper, the HN thread discussing it, the GitHub repo implementing it and the
blog post announcing it all mention the same identifier; matching on that is
exact and free, where matching on text similarity is neither.

Identifiers differ in how much they justify a merge:

  strong  a specific artefact -- one paper, one page, one model, one release
  weak    a container many unrelated things reference -- a repo, an org

Only strong identifiers join stories. ``github:huggingface/transformers``
appears in hundreds of unrelated items; treating it as a join key would collapse
the whole feed into one story.
"""

from __future__ import annotations

import json
import re
import sqlite3

from tributary.urls import canonicalize

# --- identifier types --------------------------------------------------------

ARXIV = "arxiv"
DOI = "doi"
URL = "url"
HF_MODEL = "hf_model"
GITHUB_RELEASE = "github_release"
GITHUB_REPO = "github_repo"
HF_ORG = "hf_org"

STRONG = frozenset({ARXIV, DOI, URL, HF_MODEL, GITHUB_RELEASE})
WEAK = frozenset({GITHUB_REPO, HF_ORG})

# An identifier shared by more than this many items is describing a category,
# not an event. Acts as an automatic guard against a bad extraction rule
# collapsing unrelated stories together.
MAX_FANOUT = 8

# --- patterns ----------------------------------------------------------------

_ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)
_ARXIV_CITE = re.compile(r"arxiv[:\s]\s*(\d{4}\.\d{4,5})", re.I)
_DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:a-z0-9]+)", re.I)
_GITHUB = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)", re.I)
_HF = re.compile(r"huggingface\.co/([\w.-]+)/([\w.-]+)", re.I)

# huggingface.co paths that are site sections, not model repos.
_HF_SECTIONS = frozenset({"datasets", "papers", "blog", "spaces", "docs", "collections", "learn"})
# Repo names that are really site chrome caught by the github pattern.
_GITHUB_SECTIONS = frozenset({"sponsors", "orgs", "topics", "features", "about", "pricing"})


def _clean_repo(name: str) -> str:
    """Strip the trailing punctuation a URL picks up inside prose."""
    return name.rstrip(".,);:'\"").removesuffix(".git")


def extract(row: sqlite3.Row) -> list[tuple[str, str]]:
    """Return ``(type, value)`` identifiers found in and around one item.

    Both the item's own identity and its references are returned, undifferentiated:
    a paper "is" arxiv:X and a thread "mentions" arxiv:X, and joining on the value
    is exactly what connects them.
    """
    metadata = json.loads(row["metadata"] or "{}")
    found: set[tuple[str, str]] = set()

    # Structured metadata first: the adapters already resolved these, so they
    # need no pattern matching and cannot be wrong.
    if value := metadata.get("arxiv_id"):
        found.add((ARXIV, _strip_version(str(value))))
    if value := metadata.get("hf_id"):
        found.add((HF_MODEL, str(value).lower()))
    if repo := _repo_from(str(metadata.get("github_repo") or "")):
        found.add((GITHUB_REPO, repo))
        if tag := metadata.get("tag"):
            found.add((GITHUB_RELEASE, f"{repo}@{tag}"))

    # The item's own address, and anything it points at.
    for candidate in (row["canonical_url"], row["url"], metadata.get("outbound_url")):
        if candidate and (key := _url_identifier(candidate)):
            found.add(key)

    # Links the item's own prose points at, which the adapter kept before the
    # HTML was flattened: how a blog post about an announcement joins it.
    found.update(_cited(row["url"], metadata.get("links") or []))

    # Then free text, where citations actually live.
    haystack = " ".join(
        part for part in (row["title"], row["summary"], row["body"]) if part
    )
    for match in _ARXIV_URL.finditer(haystack):
        found.add((ARXIV, match.group(1)))
    for match in _ARXIV_CITE.finditer(haystack):
        found.add((ARXIV, match.group(1)))
    for match in _DOI.finditer(haystack):
        found.add((DOI, match.group(1).lower().rstrip(".")))
    for match in _GITHUB.finditer(haystack):
        owner, repo = match.group(1).lower(), _clean_repo(match.group(2).lower())
        if owner not in _GITHUB_SECTIONS and repo:
            found.add((GITHUB_REPO, f"{owner}/{repo}"))

    return sorted(found)


# An item that links more places than this is a roundup or a reference list,
# not a piece about one thing, and extracting its links would weld unrelated
# stories together. What CLAUDE.md asked for, 2026-09-17: "a link roundup should
# extract nothing". Three allows "the announcement, its paper and its repo".
MAX_CITED = 3

# Hosts whose links are chrome -- share buttons, profiles, feed plumbing -- and
# never what a post is about. `_has_specific_path` alone lets them through, and
# two posts sharing the same share-intent URL would otherwise merge.
_CHROME_HOSTS = frozenset(
    {
        "twitter.com", "x.com", "t.co", "facebook.com", "linkedin.com", "bsky.app",
        "threads.net", "instagram.com", "mastodon.social", "news.ycombinator.com",
        "feedburner.com", "feeds.feedburner.com", "feedproxy.google.com", "wp.me",
        "gravatar.com", "doubleclick.net", "substack.com", "patreon.com",
    }
)
_CHROME_PATHS = re.compile(r"/(?:share|sharer|intent|subscribe|login|signup|feed)(?:[/.?]|$)", re.I)


def _site(url: str) -> str:
    """The last two labels of a URL's host: `blog.google.com` and `google.com` agree."""
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return ".".join(host.split(".")[-2:])


def _cited(own_url: str | None, links: list) -> set[tuple[str, str]]:
    """Strong and weak identifiers from the links an item's prose points at.

    Guarded three ways, because a wrong merge costs more than a missed link: a
    link must leave the item's own site (a post linking its own archive says
    nothing), must name a specific page rather than a homepage, and the item
    must cite few enough of them to mean them -- a roundup yields nothing.
    """
    own = _site(own_url or "")
    found: set[tuple[str, str]] = set()
    for raw in links:
        link = str(raw or "").strip()
        if not link.lower().startswith(("http://", "https://")):
            continue
        site = _site(link)
        if not site or site == own or site in _CHROME_HOSTS or _CHROME_PATHS.search(link):
            continue
        if key := _url_identifier(link):
            found.add(key)
    return found if len(found) <= MAX_CITED else set()


def _strip_version(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip())


def _repo_from(value: str) -> str | None:
    """Normalise a repo reference, whether given as a URL or as owner/name."""
    if match := _GITHUB.search(value):
        owner, repo = match.group(1).lower(), _clean_repo(match.group(2).lower())
        return f"{owner}/{repo}" if repo else None
    parts = value.strip().strip("/").lower().split("/")
    if len(parts) == 2 and all(parts):
        return f"{parts[0]}/{_clean_repo(parts[1])}"
    return None


def _url_identifier(raw: str) -> tuple[str, str] | None:
    """Classify a URL as the most specific identifier it represents."""
    if match := _ARXIV_URL.search(raw):
        return (ARXIV, match.group(1))

    if match := _HF.search(raw):
        section, name = match.group(1).lower(), _clean_repo(match.group(2).lower())
        if section in _HF_SECTIONS:
            # huggingface.co/papers/2609.16057 is a paper, not a model.
            return (ARXIV, name) if section == "papers" and _looks_like_arxiv(name) else None
        return (HF_MODEL, f"{section}/{name}") if name else None

    if match := _GITHUB.search(raw):
        owner, repo = match.group(1).lower(), _clean_repo(match.group(2).lower())
        if owner in _GITHUB_SECTIONS or not repo:
            return None
        if tag := re.search(r"/releases/tag/([^/?#]+)", raw):
            return (GITHUB_RELEASE, f"{owner}/{repo}@{tag.group(1)}")
        return (GITHUB_REPO, f"{owner}/{repo}")

    canonical = canonicalize(raw)
    # A bare homepage identifies a publication, not a story.
    return (URL, canonical) if _has_specific_path(canonical) else None


def _looks_like_arxiv(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}\.\d{4,5}", value))


def _has_specific_path(url: str) -> bool:
    from urllib.parse import urlsplit

    path = urlsplit(url).path.strip("/")
    return bool(path) and path != "/" and len(path) > 2
