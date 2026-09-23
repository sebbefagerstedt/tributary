"""Finding a site's feed, so adding a source is a proposal rather than a search.

Google's own Follow button works this way: it reads the RSS or Atom feed a page
announces with `<link rel="alternate">`. So does this, cheapest and most
reliable first:

1. **The page's own `<link rel="alternate">`**, which is the site saying where
   its feed is.
2. **The well-known paths** a publishing tool puts one at when the `<link>` is
   missing: WordPress `/feed/`, Ghost `/rss/`, Hugo `/index.xml`, and the rest.
3. **A news sitemap**, named in `robots.txt` or at its usual path, for a site
   with no feed at all -- the last 48 hours of a publisher's output, which the
   `sitemap` adapter reads.

Every candidate is fetched and parsed before it is offered: a path that answers
200 with a web page is not a feed, and CLAUDE.md records how often that happens
(`cohere.com/blog/rss.xml`). Nothing is written. This proposes, and a person
pastes what they accept into `config.toml` -- the same propose-then-accept rule
topics and entities follow. It is a command, never a `Source`: adapters map
config to items and do not decide what the config is.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import feedparser

from tributary.http import FetchError, request

# In the order publishing tools use them. `/feed/` and `/feed` are both tried
# because WordPress redirects one to the other and some hosts serve only one.
WELL_KNOWN = ("/feed/", "/feed", "/rss/", "/rss", "/feed.xml", "/index.xml", "/rss.xml",
              "/atom.xml")
NEWS_SITEMAPS = ("/sitemap-news.xml", "/news-sitemap.xml", "/sitemap_news.xml")

_LINK_TAG = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-z-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_FEED_TYPES = ("application/rss+xml", "application/atom+xml", "application/feed+json")
_SITEMAP_LINE = re.compile(r"^\s*sitemap:\s*(\S+)", re.I | re.M)


@dataclass(slots=True)
class Found:
    """A feed or news sitemap that answered and parsed."""

    url: str
    kind: str      # "rss" or "sitemap", the adapter that reads it
    title: str
    how: str       # where it was found: "link", "path" or "sitemap"
    entries: int


def site_root(target: str) -> str:
    """`example.com`, `https://example.com/blog/x` -> the URL to start from."""
    target = target.strip()
    if "://" not in target:
        target = f"https://{target}"
    return target


def announced(page: str, base: str) -> list[str]:
    """Feed URLs a page names in `<link rel="alternate" type="...feed...">`."""
    found: list[str] = []
    for tag in _LINK_TAG.findall(page):
        attrs = {
            name.lower(): html.unescape(double or single)
            for name, double, single in _ATTR.findall(tag)
        }
        rels = attrs.get("rel", "").lower().split()
        is_feed = "alternate" in rels and attrs.get("type", "").lower() in _FEED_TYPES
        if is_feed and (href := attrs.get("href")):
            url = urljoin(base, href)
            if url not in found:
                found.append(url)
    return found


def _get(url: str, errors: list[str] | None = None):
    try:
        response, _ = request(url)
    except FetchError as exc:
        if errors is not None:
            errors.append(str(exc))
        return None
    if response is None or response.status_code >= 400:
        return None
    return response


def _as_feed(url: str, how: str) -> Found | None:
    """The feed at `url`, if what answers there parses as one."""
    response = _get(url)
    if response is None:
        return None
    parsed = feedparser.parse(response.content)
    if not parsed.get("version"):
        return None  # a web page, JSON or nothing: never a feed, whatever the path
    title = parsed.feed.get("title") or urlsplit(url).hostname or url
    return Found(str(response.url), "rss", title, how, len(parsed.entries))


def _as_news_sitemap(url: str) -> Found | None:
    response = _get(url)
    if response is None:
        return None
    body = response.text
    if "<urlset" not in body:
        return None
    entries = body.count("<url>") + body.count("<url ")
    news = "sitemap-news" in body or "google.com/schemas/sitemap-news" in body
    if not news:
        return None
    host = urlsplit(url).hostname or url
    return Found(str(response.url), "sitemap", f"{host} news sitemap", "sitemap", entries)


def find(target: str) -> list[Found]:
    """Every feed the site at `target` offers, best first; empty if it has none.

    Raises `FetchError` when nothing was found and the site's own page did not
    answer, so "this site has no feed" is never said about a site that refused
    to talk -- a 403 to a cloud IP is common, and CLAUDE.md lists several.
    """
    root = site_root(target)
    errors: list[str] = []
    page = _get(root, errors)
    if not (found := _search(root, page)) and errors:
        raise FetchError(f"could not reach {root} ({errors[0]}), and found no feed")
    return found


def _search(root: str, page) -> list[Found]:
    feeds: list[Found] = []

    if page is not None:
        for url in announced(page.text, str(page.url)):
            if (feed := _as_feed(url, "link")) and feed.url not in {f.url for f in feeds}:
                feeds.append(feed)
    if feeds:
        return feeds

    origin = "{0.scheme}://{0.netloc}".format(urlsplit(str(page.url) if page else root))
    for path in WELL_KNOWN:
        if feed := _as_feed(urljoin(origin, path), "path"):
            return [feed]

    candidates: list[str] = []
    if robots := _get(urljoin(origin, "/robots.txt")):
        candidates += [u for u in _SITEMAP_LINE.findall(robots.text) if "news" in u.lower()]
    candidates += [urljoin(origin, path) for path in NEWS_SITEMAPS]
    for url in dict.fromkeys(candidates):
        if sitemap := _as_news_sitemap(url):
            return [sitemap]
    return []


def snippet(found: Found) -> str:
    """The `config.toml` entry for a found feed, ready to paste."""
    lines = ["[[sources]]", f'kind = "{found.kind}"', f"name = {_toml(found.title)}",
             f"url = {_toml(found.url)}"]
    if found.kind == "sitemap":
        # Every URL on the site, as a start: the adapter requires a pattern, and
        # narrowing it to the news path is the person's call.
        host = re.escape(urlsplit(found.url).hostname or "")
        lines.append(f"include = {_toml(host + '/')}")
    return "\n".join(lines)


def _toml(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
