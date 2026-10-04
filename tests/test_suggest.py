from __future__ import annotations

import numpy as np
import sqlite_vec

from tributary import embeddings, suggest

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Runway Blog</title>
<item><title>A new video model</title><link>https://runway.test/a</link>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
<item><title>Camera control, explained</title><link>https://runway.test/b</link></item>
</channel></rss>"""


def unit(*values) -> list[float]:
    v = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    v[: len(values)] = values
    return (v / np.linalg.norm(v)).tolist()


def test_a_query_with_a_dot_and_no_spaces_is_a_site():
    assert suggest.looks_like_site("runwayml.com")
    assert suggest.looks_like_site("https://www.theverge.com/ai")
    assert not suggest.looks_like_site("AI video")
    assert not suggest.looks_like_site("gpt-5.5 news")


def test_a_site_is_found_and_previewed_live(conn, httpx_mock):
    page = '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
    httpx_mock.add_response(url="https://runway.test", text=page)
    httpx_mock.add_response(url="https://runway.test/feed.xml", content=FEED, is_reusable=True)

    got = suggest.for_site(conn, "runway.test")
    assert got["kind"] == "site" and got["note"] == ""
    [src] = got["sources"]
    assert src["name"] == "Runway Blog" and src["kind"] == "rss" and not src["known"]
    assert src["latest"] == ["A new video model", "Camera control, explained"]
    assert src["week"] == 0, "an old item is not this week's"


def test_a_site_that_cannot_be_reached_says_so(conn, httpx_mock):
    import httpx

    httpx_mock.add_exception(httpx.ConnectError("refused"), is_reusable=True)
    got = suggest.for_site(conn, "gone.test")
    assert got["sources"] == [] and "could not reach" in got["note"]


def test_a_subject_ranks_known_sources_by_stories_that_fit(conn):
    def source(name):
        return conn.execute("INSERT INTO sources (kind, name, url) VALUES ('rss', ?, ?)",
                            (name, f"https://{name}.test/feed")).lastrowid

    video, chips = source("video"), source("chips")
    for n, (src, vec) in enumerate([(video, (1.0,)), (video, (0.95, 0.3)), (chips, (0.0, 1.0))]):
        item = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, published_at) "
            "VALUES (?, ?, 'article', ?, ?, datetime('now'))",
            (src, f"x{n}", f"https://e.test/{n}", f"Story {n}"),
        ).lastrowid
        conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                     (item, sqlite_vec.serialize_float32(unit(*vec))))
        story = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) VALUES (datetime('now'), "
            "strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        ).lastrowid
        conn.execute("INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                     (story, item))

    got = suggest.for_subject(conn, "AI video", lambda texts: [unit(1.0) for _ in texts])
    assert [s["name"] for s in got["sources"]] == ["video"]
    assert got["sources"][0]["fit"] == 2 and got["sources"][0]["latest"]
