"""Adapter tests for HN, arXiv, HuggingFace and GitHub."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime

import pytest

from tributary.config import SourceConfig
from tributary.models import Kind
from tributary.sources.arxiv import ArxivSource
from tributary.sources.base import FetchError
from tributary.sources.github import GitHubSource
from tributary.sources.hn import HackerNewsSource
from tributary.sources.huggingface import HuggingFaceSource


def cfg(kind, **options):
    return SourceConfig(kind=kind, name=f"Test {kind}", url=None, options=options)


# --- Hacker News -------------------------------------------------------------

HN_PAYLOAD = {
    "hits": [
        {
            "objectID": "123",
            "title": "A new model",
            "url": "https://example.com/model",
            "author": "pg",
            "points": 240,
            "num_comments": 88,
            "created_at_i": 1789569036,
        },
        {   # Ask HN: no outbound link, the discussion is the content
            "objectID": "124",
            "title": "Ask HN: what are you running locally?",
            "url": None,
            "author": "dang",
            "points": 90,
            "num_comments": 300,
            "created_at_i": 1789569000,
        },
    ]
}


def test_hn_item_is_the_discussion_not_the_link(httpx_mock):
    httpx_mock.add_response(json=HN_PAYLOAD)
    items, _ = HackerNewsSource(cfg("hn")).fetch({})

    first = items[0]
    assert first.kind == Kind.DISCUSSION
    assert first.url == "https://news.ycombinator.com/item?id=123"
    # The submitted link is a reference to something else -- a clustering key.
    assert first.metadata["outbound_url"] == "https://example.com/model"
    assert first.metadata["points"] == 240
    assert first.published_at == datetime(2026, 9, 16, 14, 30, 36, tzinfo=UTC)


def test_hn_text_post_without_outbound_link(httpx_mock):
    httpx_mock.add_response(json=HN_PAYLOAD)
    items, _ = HackerNewsSource(cfg("hn")).fetch({})
    assert items[1].url == "https://news.ycombinator.com/item?id=124"
    assert items[1].metadata["outbound_url"] is None


def test_hn_high_water_mark_advances_and_is_sent_back(httpx_mock):
    httpx_mock.add_response(json=HN_PAYLOAD)
    _, state = HackerNewsSource(cfg("hn")).fetch({})
    assert state["last_created_at_i"] == 1789569036

    httpx_mock.add_response(json={"hits": []})
    HackerNewsSource(cfg("hn")).fetch(state)
    sent = str(httpx_mock.get_requests()[-1].url)
    assert "created_at_i%3E1789569036" in sent or "created_at_i>1789569036" in sent


def test_hn_min_points_is_configurable(httpx_mock):
    httpx_mock.add_response(json={"hits": []})
    HackerNewsSource(cfg("hn", min_points=500)).fetch({})
    assert "points%3E%3D500" in str(httpx_mock.get_requests()[-1].url)


# --- arXiv -------------------------------------------------------------------

ARXIV_FEED = b"""<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2609.17527v2</id>
    <link href="https://arxiv.org/abs/2609.17527v2" rel="alternate" type="text/html"/>
    <title>Agentic Societies Need a Social Harness</title>
    <summary>An agentic society is a collection of AI agents.</summary>
    <published>2026-09-15T17:57:27Z</published>
    <updated>2026-09-16T09:00:00Z</updated>
    <author><name>Tapan Chugh</name></author>
    <author><name>Vidushi Singh</name></author>
    <author><name>Ratul Mahajan</name></author>
    <arxiv:primary_category term="cs.MA"/>
    <category term="cs.MA"/>
    <category term="cs.AI"/>
  </entry>
</feed>
"""


def test_arxiv_external_id_drops_the_version(httpx_mock):
    """A v2 revision must update the existing paper, not create a near-duplicate."""
    httpx_mock.add_response(content=ARXIV_FEED)
    items, _ = ArxivSource(cfg("arxiv")).fetch({})

    assert items[0].external_id == "2609.17527"
    assert items[0].url == "https://arxiv.org/abs/2609.17527"
    assert items[0].metadata["version"] == "2"


def test_arxiv_fields(httpx_mock):
    httpx_mock.add_response(content=ARXIV_FEED)
    items, _ = ArxivSource(cfg("arxiv")).fetch({})
    item = items[0]

    assert item.kind == Kind.PAPER
    assert item.author == "Tapan Chugh et al."  # three authors collapse
    assert item.summary == "An agentic society is a collection of AI agents."
    assert item.metadata["primary_category"] == "cs.MA"
    assert set(item.metadata["categories"]) == {"cs.MA", "cs.AI"}
    assert item.metadata["pdf_url"] == "https://arxiv.org/pdf/2609.17527"


def test_arxiv_two_authors_are_both_named(httpx_mock):
    httpx_mock.add_response(content=ARXIV_FEED.replace(
        b"<author><name>Ratul Mahajan</name></author>", b""
    ))
    items, _ = ArxivSource(cfg("arxiv")).fetch({})
    assert items[0].author == "Tapan Chugh and Vidushi Singh"


def test_arxiv_categories_build_the_query(httpx_mock):
    httpx_mock.add_response(content=ARXIV_FEED)
    ArxivSource(cfg("arxiv", categories=["cs.CL", "stat.ML"])).fetch({})
    sent = str(httpx_mock.get_requests()[-1].url)
    assert "cat%3Acs.CL+OR+cat%3Astat.ML" in sent


# --- HuggingFace -------------------------------------------------------------

def test_hf_daily_paper_carries_cross_source_links(httpx_mock):
    httpx_mock.add_response(
        json=[
            {
                "title": "OmniHarness",
                "publishedAt": "2026-09-12T20:00:00.000Z",
                "summary": "Unified multimodal models.",
                "thumbnail": "https://cdn.hf.co/t.png",
                "numComments": 1,
                "paper": {
                    "id": "2609.16057",
                    "githubRepo": "https://github.com/OmniHarness/OmniHarness",
                    "githubStars": 12,
                    "upvotes": 40,
                },
            }
        ]
    )
    items, _ = HuggingFaceSource(cfg("hf", mode="papers")).fetch({})
    item = items[0]

    assert item.kind == Kind.PAPER
    assert item.external_id == "2609.16057"
    # These are pre-resolved joins: three sources linked without any text matching.
    assert item.metadata["arxiv_id"] == "2609.16057"
    assert item.metadata["github_repo"] == "https://github.com/OmniHarness/OmniHarness"
    assert item.media_url == "https://cdn.hf.co/t.png"


def test_hf_model_author_derived_from_repo_id(httpx_mock):
    httpx_mock.add_response(
        json=[{"id": "deepseek-ai/DeepSeek-V4", "likes": 2807, "downloads": 366459}]
    )
    items, _ = HuggingFaceSource(cfg("hf", mode="models")).fetch({})
    assert items[0].author == "deepseek-ai"
    assert items[0].url == "https://huggingface.co/deepseek-ai/DeepSeek-V4"
    assert items[0].metadata["likes"] == 2807


def test_hf_model_citing_a_paper_carries_its_id(httpx_mock):
    """The join that turns a new model into the wake of the paper it implements."""
    httpx_mock.add_response(
        json=[{"id": "someone/tinydistil", "tags": ["pytorch", "arxiv:2609.11234", "license:mit"]}]
    )
    items, _ = HuggingFaceSource(cfg("hf", mode="models")).fetch({})
    assert items[0].metadata["arxiv_id"] == "2609.11234"


def test_hf_model_citing_nothing_has_no_paper(httpx_mock):
    httpx_mock.add_response(json=[{"id": "someone/a-finetune", "tags": ["pytorch"]}])
    items, _ = HuggingFaceSource(cfg("hf", mode="models")).fetch({})
    assert items[0].metadata["arxiv_id"] is None


def test_cites_paper_drops_the_hub_firehose(httpx_mock):
    """Newest-first is mostly requants; only the ones citing a paper are wake."""
    httpx_mock.add_response(
        json=[
            {"id": "a/requant-of-the-week", "tags": ["gguf"]},
            {"id": "b/paper-implementation", "tags": ["arxiv:2609.11234"]},
            {"id": "c/another-finetune", "tags": []},
        ]
    )
    items, _ = HuggingFaceSource(
        cfg("hf", mode="models", sort="createdAt", cites_paper=True)
    ).fetch({})
    assert [item.external_id for item in items] == ["b/paper-implementation"]


def test_without_cites_paper_nothing_is_dropped(httpx_mock):
    httpx_mock.add_response(json=[{"id": "a/one", "tags": []}, {"id": "b/two", "tags": []}])
    items, _ = HuggingFaceSource(cfg("hf", mode="models")).fetch({})
    assert len(items) == 2


def test_hf_unknown_mode_is_rejected():
    with pytest.raises(FetchError, match="unknown hf mode"):
        HuggingFaceSource(cfg("hf", mode="wat")).fetch({})


def test_hf_unexpected_shape_is_reported(httpx_mock):
    httpx_mock.add_response(json={"error": "nope"})
    with pytest.raises(FetchError, match="unexpected response shape"):
        HuggingFaceSource(cfg("hf", mode="models")).fetch({})


# --- GitHub ------------------------------------------------------------------

def release(tag="v1.0", draft=False):
    return {
        "tag_name": tag,
        "name": tag,
        "html_url": f"https://github.com/o/r/releases/tag/{tag}",
        "published_at": "2026-09-09T08:54:49Z",
        "body": "# Highlights\nStuff.",
        "draft": draft,
        "prerelease": False,
        "author": {"login": "releaser"},
    }


def test_github_builds_release_items(httpx_mock):
    httpx_mock.add_response(json=[release()])
    items, _ = GitHubSource(cfg("github", repos=["o/r"])).fetch({})

    assert items[0].kind == Kind.REPO
    assert items[0].external_id == "o/r@v1.0"
    assert items[0].title == "o/r v1.0"
    assert items[0].metadata["github_repo"] == "o/r"


def test_github_skips_drafts(httpx_mock):
    httpx_mock.add_response(json=[release("v1.0"), release("v2.0-draft", draft=True)])
    items, _ = GitHubSource(cfg("github", repos=["o/r"])).fetch({})
    assert [i.external_id for i in items] == ["o/r@v1.0"]


def test_github_stores_validators_per_repo(httpx_mock):
    """Each repo is its own resource; a shared ETag would defeat conditional GET."""
    httpx_mock.add_response(url=re.compile(r".*/one/releases.*"), json=[release("v1")],
                            headers={"ETag": '"one-etag"'})
    httpx_mock.add_response(url=re.compile(r".*/two/releases.*"), json=[release("v2")],
                            headers={"ETag": '"two-etag"'})

    _, state = GitHubSource(cfg("github", repos=["o/one", "o/two"])).fetch({})
    assert state["etags"]["o/one"]["etag"] == '"one-etag"'
    assert state["etags"]["o/two"]["etag"] == '"two-etag"'


def test_github_one_bad_repo_does_not_lose_the_others(httpx_mock):
    httpx_mock.add_response(url=re.compile(r".*/gone/releases.*"), status_code=404)
    httpx_mock.add_response(url=re.compile(r".*/fine/releases.*"), json=[release("v1")])

    items, state = GitHubSource(cfg("github", repos=["o/gone", "o/fine"])).fetch({})
    assert [i.external_id for i in items] == ["o/fine@v1"]
    assert any("o/gone" in f for f in state["failures"])


def test_github_all_repos_failing_is_an_error(httpx_mock):
    httpx_mock.add_response(status_code=404)
    with pytest.raises(FetchError, match="o/gone"):
        GitHubSource(cfg("github", repos=["o/gone"])).fetch({})


def test_github_requires_repos():
    with pytest.raises(FetchError, match="non-empty 'repos'"):
        GitHubSource(cfg("github")).fetch({})


# --- package structure -------------------------------------------------------

def test_http_can_be_imported_without_the_adapters():
    """Regression: http took FetchError from sources.base, so importing http
    first pulled in every adapter, each of which imports http right back. It
    worked only because every caller happened to load sources first."""
    done = subprocess.run(
        [sys.executable, "-c", "from tributary.http import request, FetchError"],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr


def test_adapters_still_raise_the_same_class():
    """Moving it must not split FetchError into two unrelated exceptions."""
    from tributary import http

    assert FetchError is http.FetchError
