from __future__ import annotations

import re

from tributary import discover

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Lab Blog</title>
<item><title>A</title><link>https://lab.test/a</link></item>
<item><title>B</title><link>https://lab.test/b</link></item></channel></rss>"""

NEWS = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
<url><loc>https://lab.test/news/1</loc></url></urlset>"""

PAGE = """<html><head>
<link rel="stylesheet" href="/s.css">
<link type="application/rss+xml" rel="alternate" href="/blog/feed.xml" title="Blog">
</head></html>"""


def test_a_page_announcing_its_feed_is_read_first(httpx_mock):
    httpx_mock.add_response(url="https://lab.test", text=PAGE)
    httpx_mock.add_response(url="https://lab.test/blog/feed.xml", content=FEED)

    found = discover.find("lab.test")
    assert [(f.url, f.kind, f.how, f.entries) for f in found] == [
        ("https://lab.test/blog/feed.xml", "rss", "link", 2)
    ]
    assert found[0].title == "Lab Blog"


def test_a_well_known_path_is_tried_when_the_page_names_none(httpx_mock):
    httpx_mock.add_response(url="https://lab.test", text="<html></html>")
    httpx_mock.add_response(url="https://lab.test/feed/", status_code=404)
    httpx_mock.add_response(url="https://lab.test/feed", text="<html>a web page</html>")
    httpx_mock.add_response(url="https://lab.test/rss/", content=FEED)

    found = discover.find("https://lab.test")
    assert [(f.url, f.how) for f in found] == [("https://lab.test/rss/", "path")]


def test_a_news_sitemap_is_the_last_resort(httpx_mock):
    httpx_mock.add_response(url="https://lab.test", text="<html></html>")
    httpx_mock.add_response(url=re.compile(r"https://lab\.test/(feed|rss|index|atom).*"),
                            status_code=404, is_reusable=True)
    httpx_mock.add_response(url="https://lab.test/robots.txt",
                            text="User-agent: *\nSitemap: https://lab.test/news-map.xml\n")
    httpx_mock.add_response(url="https://lab.test/news-map.xml", content=NEWS)

    found = discover.find("lab.test")
    assert [(f.url, f.kind) for f in found] == [("https://lab.test/news-map.xml", "sitemap")]
    assert 'include = "lab\\\\.test/"' in discover.snippet(found[0])


def test_a_site_with_nothing_yields_nothing(httpx_mock):
    httpx_mock.add_response(url="https://lab.test", text="<html></html>")
    httpx_mock.add_response(url=re.compile(r".*"), status_code=404, is_reusable=True)
    assert discover.find("lab.test") == []


def test_the_snippet_is_config_to_paste():
    found = discover.Found("https://lab.test/feed", "rss", 'The "Lab"', "link", 3)
    assert discover.snippet(found) == (
        '[[sources]]\nkind = "rss"\nname = "The \\"Lab\\""\nurl = "https://lab.test/feed"'
    )


def test_a_site_that_cannot_be_reached_is_not_called_feedless(httpx_mock):
    import httpx
    import pytest

    httpx_mock.add_exception(httpx.ConnectError("refused"), url=re.compile(r".*"),
                             is_reusable=True)
    with pytest.raises(discover.FetchError, match="could not reach"):
        discover.find("lab.test")
