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
    with pytest.raises(FetchError, match="not a feed"):
        make_source().fetch({})


def test_missing_url_raises_fetch_error():
    source = RSSSource(SourceConfig(kind="rss", name="No URL", url=None))
    with pytest.raises(FetchError, match="requires a url"):
        source.fetch({})


# --- when what arrives is not a feed ----------------------------------------
#
# MarkTechPost has reported "unparseable feed (not well-formed, invalid token)"
# for weeks while contributing nothing, and that message invites exactly the
# wrong fix. feedparser recovers from malformed XML: these first two tests pin
# that down, so nobody writes a sanitiser for a problem that does not exist.

MALFORMED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>R&D News</title>
<item><title>Models&nbsp;that fit</title><link>https://ex.test/1</link>
<description>Tom & Jerry</description></item>
</channel></rss>"""


def test_malformed_xml_still_yields_its_items(httpx_mock):
    """A bare ampersand, an undeclared entity and a control character together.
    All of it is invalid XML, and all of it parses anyway."""
    httpx_mock.add_response(url="https://ex.test/feed", content=b"\x0c" + MALFORMED.encode())
    items, _ = make_source().fetch({})
    assert [i.title for i in items] == ["Models that fit"]


def test_a_truncated_feed_keeps_what_arrived(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", content=MALFORMED.encode()[:175])
    items, _ = make_source().fetch({})
    assert [i.title for i in items] == ["Models that fit"]


def test_an_empty_but_valid_feed_is_not_a_failure(httpx_mock):
    """A source with nothing new this week is not a broken source."""
    httpx_mock.add_response(
        url="https://ex.test/feed",
        content=b'<?xml version="1.0"?><rss version="2.0">'
        b"<channel><title>Q</title></channel></rss>",
    )
    items, _ = make_source().fetch({})
    assert items == []


def test_a_web_page_served_as_a_feed_says_so(httpx_mock):
    """Bot checks and login walls come back with a 200, so nothing upstream
    catches them. This is the most likely thing MarkTechPost is doing."""
    httpx_mock.add_response(
        url="https://ex.test/feed",
        content=b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
                b"<body>Checking your browser</body></html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )
    with pytest.raises(FetchError) as caught:
        make_source().fetch({})

    message = str(caught.value)
    assert "served a web page, not a feed" in message
    assert "text/html" in message
    assert "Just a moment" in message


def test_a_json_error_body_says_so(httpx_mock):
    httpx_mock.add_response(
        url="https://ex.test/feed",
        content=b'{"error": "forbidden", "reason": "automated traffic"}',
        headers={"content-type": "application/json"},
    )
    with pytest.raises(FetchError) as caught:
        make_source().fetch({})

    message = str(caught.value)
    assert "not a feed" in message
    assert "application/json" in message
    assert "automated traffic" in message  # the actual reason, not a parser error


def test_an_empty_response_says_so(httpx_mock):
    httpx_mock.add_response(url="https://ex.test/feed", content=b"")
    with pytest.raises(FetchError) as caught:
        make_source().fetch({})
    assert "empty response" in str(caught.value)


def test_the_wrong_encoding_reports_the_bytes_that_arrived(httpx_mock):
    """Declared UTF-8, actually UTF-16 -- the parser's message alone cannot
    distinguish this from a truncated file or a JSON error."""
    httpx_mock.add_response(url="https://ex.test/feed", content=MALFORMED.encode("utf-16"))
    with pytest.raises(FetchError) as caught:
        make_source().fetch({})
    assert "body starts" in str(caught.value)


LINKED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>T</title>
  <item>
    <title>What the new model means</title>
    <link>https://blog.example.com/what-it-means</link>
    <description>&lt;p&gt;Today &lt;a href="https://lab.test/news/model-7?utm_source=x"&gt;the lab
      announced&lt;/a&gt; a model (&lt;a href='https://lab.test/news/model-7'&gt;again&lt;/a&gt;).
      &lt;/p&gt;</description>
  </item>
  <item><title>Plain</title><link>https://blog.example.com/plain</link>
    <description>No links at all.</description></item>
</channel></rss>
"""


def test_the_links_in_a_summary_survive_the_html_being_flattened(httpx_mock):
    """They are how a post about an announcement can join it (identity._cited)."""
    httpx_mock.add_response(url="https://ex.test/feed", content=LINKED.encode())
    linked, plain = make_source().fetch({})[0]

    assert linked.metadata["links"] == [
        "https://lab.test/news/model-7?utm_source=x", "https://lab.test/news/model-7",
    ]
    assert "links" not in plain.metadata
