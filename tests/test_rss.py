from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tributary.config import SourceConfig
from tributary.models import Kind
from tributary.sources.base import FetchError
from tributary.sources.rss import RSSSource

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>A &amp;quot;new&amp;quot; model drops</title>
      <link>https://example.com/post-1?utm_source=rss</link>
      <guid>tag:example.com,2026:post-1</guid>
      <author>ada@example.com (Ada)</author>
      <pubDate>Mon, 15 Sep 2026 09:30:00 GMT</pubDate>
      <description>&lt;p&gt;Body with &lt;b&gt;markup&lt;/b&gt;.&lt;/p&gt;</description>
      <media:content url="https://example.com/hero.png" />
    </item>
    <item>
      <title>No guid here</title>
      <link>https://example.com/post-2</link>
      <pubDate>Tue, 16 Sep 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Unaddressable, no link</title>
    </item>
  </channel>
</rss>
"""


def make_source(**options):
    return RSSSource(
        SourceConfig(kind="rss", name="Test Feed", url="https://ex.test/feed", **options)
    )


def test_parses_entries(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", content=FEED.encode())
    items, _ = make_source().fetch({})

    # The third entry has no link, so it is skipped: not addressable.
    assert len(items) == 2

    first = items[0]
    assert first.external_id == "tag:example.com,2026:post-1"
    assert first.kind == Kind.ARTICLE
    assert first.title == 'A "new" model drops'
    assert first.author == "ada@example.com (Ada)"
    assert first.published_at == datetime(2026, 9, 15, 9, 30, tzinfo=UTC)
    assert first.summary == "Body with markup."
    assert first.media_url == "https://example.com/hero.png"


def test_falls_back_to_link_when_guid_missing(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", content=FEED.encode())
    items, _ = make_source().fetch({})
    assert items[1].external_id == "https://example.com/post-2"


def test_conditional_get_sends_and_stores_validators(httpx_mock):
    httpx_mock.add_response(
        url="https://ex.test/feed",
        content=FEED.encode(),
        headers={"ETag": '"abc"', "Last-Modified": "Mon, 15 Sep 2026 09:30:00 GMT"},
    )
    _, state = make_source().fetch({})
    assert state == {"etag": '"abc"', "last_modified": "Mon, 15 Sep 2026 09:30:00 GMT"}

    httpx_mock.add_response(url="https://ex.test/feed", status_code=304)
    items, new_state = make_source().fetch(state)
    assert items == []
    assert new_state == state  # unchanged, so the validators survive

    request = httpx_mock.get_requests()[-1]
    assert request.headers["If-None-Match"] == '"abc"'
    assert request.headers["If-Modified-Since"] == "Mon, 15 Sep 2026 09:30:00 GMT"


def test_http_error_raises_fetch_error(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", status_code=404)
    with pytest.raises(FetchError, match="404"):
        make_source().fetch({})


def test_garbage_body_raises_fetch_error(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", content=b"\x00 not a feed")
    with pytest.raises(FetchError, match="unparseable"):
        make_source().fetch({})


def test_missing_url_raises_fetch_error():
    source = RSSSource(SourceConfig(kind="rss", name="No URL", url=None))
    with pytest.raises(FetchError, match="requires a url"):
        source.fetch({})
