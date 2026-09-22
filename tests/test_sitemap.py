from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tributary.config import SourceConfig
from tributary.models import Kind
from tributary.sources.base import FetchError
from tributary.sources.sitemap import SitemapSource, page_title

SITEMAP = "https://lab.test/sitemap.xml"
RECENT = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%d")
NEWER = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
OLD = "2019-01-01"


def urlset(*entries: tuple[str, str | None]) -> bytes:
    rows = "".join(
        f"<url><loc>{loc}</loc>{f'<lastmod>{mod}</lastmod>' if mod else ''}</url>"
        for loc, mod in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'
    ).encode()


def page(title="Introducing Claude Opus 5.5", published="2026-09-20T10:00:00Z") -> str:
    return f"""<html><head>
      <title>{title} \\ Anthropic</title>
      <meta property="og:title" content="{title}">
      <meta property="og:site_name" content="Anthropic">
      <meta name="description" content="Our most capable model yet, with a longer context.">
      <meta property="article:published_time" content="{published}">
      <meta property="og:image" content="/images/hero.png">
    </head><body>cookie banner</body></html>"""


def source(**options) -> SitemapSource:
    options = {"include": r"/news/", **options}
    return SitemapSource(SourceConfig(kind="sitemap", name="Lab", url=SITEMAP, options=options))


def test_first_run_takes_what_the_sitemap_dates_as_recent(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=urlset(
        ("https://lab.test/news/opus-5-5", RECENT),
        ("https://lab.test/news/old-post", OLD),
        ("https://lab.test/careers", RECENT),       # outside `include`
    ))
    httpx_mock.add_response(url="https://lab.test/news/opus-5-5", text=page())

    items, state = source().fetch({})

    [item] = items
    assert item.title == "Introducing Claude Opus 5.5"
    assert item.kind == Kind.ARTICLE
    assert item.external_id == item.url == "https://lab.test/news/opus-5-5"
    assert item.summary == "Our most capable model yet, with a longer context."
    assert item.published_at == datetime(2026, 9, 20, 10, tzinfo=UTC)
    assert item.media_url == "https://lab.test/images/hero.png"
    # The old post is a baseline, never visited; the careers page is not tracked.
    assert state["seen"] == ["https://lab.test/news/old-post", "https://lab.test/news/opus-5-5"]


def test_first_run_without_dates_is_only_a_baseline(httpx_mock):
    """No lastmod means no way to tell new from old, so nothing is crawled."""
    httpx_mock.add_response(url=SITEMAP, content=urlset(
        ("https://lab.test/news/a", None), ("https://lab.test/news/b", None),
    ))

    items, state = source().fetch({})

    assert items == []
    assert state["seen"] == ["https://lab.test/news/a", "https://lab.test/news/b"]


def test_later_runs_visit_only_what_was_not_listed_before(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=urlset(
        ("https://lab.test/news/a", None), ("https://lab.test/news/new", None),
    ))
    httpx_mock.add_response(url="https://lab.test/news/new", text=page("A new post"))

    items, state = source().fetch({"seen": ["https://lab.test/news/a"]})

    assert [i.title for i in items] == ["A new post"]
    assert state["seen"] == ["https://lab.test/news/a", "https://lab.test/news/new"]


def test_a_run_visits_at_most_limit_pages_newest_first(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=urlset(
        ("https://lab.test/news/older", RECENT), ("https://lab.test/news/newer", NEWER),
    ))
    httpx_mock.add_response(url="https://lab.test/news/newer", text=page("Newer"))

    items, state = source(limit=1).fetch({})

    assert [i.title for i in items] == ["Newer"]
    # The other waits for the next run rather than being dropped.
    assert "https://lab.test/news/older" not in state["seen"]


def test_a_page_with_no_title_is_seen_and_not_retried(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=urlset(("https://lab.test/news/x", None)))
    httpx_mock.add_response(url="https://lab.test/news/x", text="<html><head></head></html>")

    items, state = source().fetch({"seen": []})

    assert items == []
    assert state["seen"] == ["https://lab.test/news/x"]


def test_a_sitemap_index_is_followed(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=b"""<?xml version="1.0"?>
      <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <sitemap><loc>https://lab.test/sitemap-news.xml</loc></sitemap>
      </sitemapindex>""")
    httpx_mock.add_response(url="https://lab.test/sitemap-news.xml",
                            content=urlset(("https://lab.test/news/a", RECENT)))
    httpx_mock.add_response(url="https://lab.test/news/a", text=page("From the child"))

    items, _ = source().fetch({})

    assert [i.title for i in items] == ["From the child"]


def test_nothing_under_include_is_a_failure_not_quiet(httpx_mock):
    """A wrong path would otherwise look exactly like a lab with no news."""
    httpx_mock.add_response(url=SITEMAP, content=urlset(("https://lab.test/about", None)))

    with pytest.raises(FetchError, match="none match"):
        source().fetch({})


def test_a_site_refusing_every_visit_is_a_failure(httpx_mock):
    """What a lab blocking Actions looks like; the pages stay unseen for a retry."""
    httpx_mock.add_response(url=SITEMAP, content=urlset(("https://lab.test/news/a", None)))
    httpx_mock.add_response(url="https://lab.test/news/a", status_code=403)

    with pytest.raises(FetchError, match="every page visit failed"):
        source().fetch({"seen": []})


def test_a_body_that_is_not_xml_says_what_arrived(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, text="<!doctype html><p>Just a moment...</p>")

    with pytest.raises(FetchError, match="not a sitemap.*Just a moment"):
        source().fetch({})


def test_include_is_required():
    with pytest.raises(FetchError, match="include"):
        SitemapSource(SourceConfig(kind="sitemap", name="Lab", url=SITEMAP)).fetch({})


def test_a_title_tag_loses_its_site_name():
    html = """<head><title>Claude Opus 5.5 \\ Anthropic</title>
      <meta property="og:site_name" content="Anthropic"></head>"""
    assert page_title(html) == "Claude Opus 5.5"


def test_a_news_sitemap_is_dated_by_its_publication_date(httpx_mock):
    httpx_mock.add_response(url=SITEMAP, content=f"""<?xml version="1.0"?>
      <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
              xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
        <url><loc>https://lab.test/news/a</loc>
          <news:news><news:publication_date>{NEWER}</news:publication_date></news:news>
        </url>
      </urlset>""".encode())
    httpx_mock.add_response(url="https://lab.test/news/a", text=page("Dated by news"))

    items, _ = source().fetch({})

    assert [i.title for i in items] == ["Dated by news"]


def test_a_build_date_on_every_url_is_not_read_as_news(httpx_mock):
    """Generators stamp lastmod with the deploy; a first run must not crawl it all."""
    httpx_mock.add_response(url=SITEMAP, content=urlset(
        *((f"https://lab.test/news/post-{n}", RECENT) for n in range(25))
    ))

    items, state = source().fetch({})

    assert items == []
    assert len(state["seen"]) == 25
