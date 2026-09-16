from __future__ import annotations

import json

from tributary import identity


def row(**fields):
    base = {
        "title": "", "summary": None, "body": None,
        "url": "https://example.com/a", "canonical_url": "https://example.com/a",
        "metadata": "{}",
    }
    return base | fields


def find(kind, results):
    return [value for key, value in results if key == kind]


# --- arXiv -------------------------------------------------------------------

def test_arxiv_from_metadata_drops_the_version():
    got = identity.extract(row(metadata=json.dumps({"arxiv_id": "2609.17527v2"})))
    assert find(identity.ARXIV, got) == ["2609.17527"]


def test_arxiv_from_an_abs_url():
    got = identity.extract(row(url="https://arxiv.org/abs/2609.17527"))
    assert find(identity.ARXIV, got) == ["2609.17527"]


def test_arxiv_cited_in_prose():
    """The common case: a blog post or HN comment citing a paper."""
    got = identity.extract(row(summary="Building on arXiv:2609.16057 they show..."))
    assert find(identity.ARXIV, got) == ["2609.16057"]


def test_hf_papers_url_is_the_paper_not_a_model():
    got = identity.extract(row(url="https://huggingface.co/papers/2609.16057"))
    assert find(identity.ARXIV, got) == ["2609.16057"]
    assert find(identity.HF_MODEL, got) == []


def test_arxiv_pdf_and_abs_resolve_to_the_same_id():
    a = identity.extract(row(url="https://arxiv.org/abs/2609.17527"))
    b = identity.extract(row(url="https://arxiv.org/pdf/2609.17527"))
    assert find(identity.ARXIV, a) == find(identity.ARXIV, b)


# --- HuggingFace -------------------------------------------------------------

def test_hf_model_url():
    got = identity.extract(row(url="https://huggingface.co/deepseek-ai/DeepSeek-V4"))
    assert find(identity.HF_MODEL, got) == ["deepseek-ai/deepseek-v4"]


def test_hf_site_sections_are_not_models():
    for section in ("datasets", "blog", "spaces", "docs"):
        got = identity.extract(row(url=f"https://huggingface.co/{section}/something"))
        assert find(identity.HF_MODEL, got) == [], section


# --- GitHub ------------------------------------------------------------------

def test_github_repo_is_weak_not_strong():
    """A repo is referenced by many unrelated stories; it must not join them."""
    got = identity.extract(row(url="https://github.com/vllm-project/vllm"))
    assert find(identity.GITHUB_REPO, got) == ["vllm-project/vllm"]
    assert identity.GITHUB_REPO in identity.WEAK
    assert identity.GITHUB_REPO not in identity.STRONG


def test_a_release_tag_is_strong():
    """One release is a specific event, unlike the repo that produced it."""
    got = identity.extract(row(url="https://github.com/o/r/releases/tag/v1.2"))
    assert find(identity.GITHUB_RELEASE, got) == ["o/r@v1.2"]
    assert identity.GITHUB_RELEASE in identity.STRONG


def test_release_built_from_metadata():
    got = identity.extract(
        row(metadata=json.dumps({"github_repo": "ggml-org/llama.cpp", "tag": "b11003"}))
    )
    assert find(identity.GITHUB_RELEASE, got) == ["ggml-org/llama.cpp@b11003"]
    assert find(identity.GITHUB_REPO, got) == ["ggml-org/llama.cpp"]


def test_repo_metadata_accepts_a_url_or_a_bare_slug():
    a = identity.extract(row(metadata=json.dumps({"github_repo": "https://github.com/O/R"})))
    b = identity.extract(row(metadata=json.dumps({"github_repo": "O/R"})))
    assert find(identity.GITHUB_REPO, a) == find(identity.GITHUB_REPO, b) == ["o/r"]


def test_trailing_punctuation_in_prose_is_stripped():
    got = identity.extract(row(summary="See github.com/openai/whisper, it is good."))
    assert find(identity.GITHUB_REPO, got) == ["openai/whisper"]


def test_github_site_chrome_is_ignored():
    got = identity.extract(row(summary="via https://github.com/sponsors/someone"))
    assert find(identity.GITHUB_REPO, got) == []


# --- URLs --------------------------------------------------------------------

def test_an_hn_thread_points_at_the_article_it_submitted():
    """This is the join that connects a discussion to the thing discussed."""
    got = identity.extract(
        row(
            url="https://news.ycombinator.com/item?id=123",
            canonical_url="https://news.ycombinator.com/item?id=123",
            metadata=json.dumps({"outbound_url": "https://blog.test/a-new-model/"}),
        )
    )
    assert "https://blog.test/a-new-model" in find(identity.URL, got)


def test_url_identifiers_are_canonicalised():
    """Tracking parameters must not split one page into several identifiers."""
    a = identity.extract(row(url="https://blog.test/post?utm_source=rss"))
    b = identity.extract(row(url="http://www.blog.test/post/"))
    assert find(identity.URL, a) == find(identity.URL, b)


def test_a_bare_homepage_is_not_an_identifier():
    """Otherwise every item from one publication would merge into one story."""
    got = identity.extract(row(url="https://techcrunch.com/", canonical_url="https://techcrunch.com/"))
    assert find(identity.URL, got) == []


# --- shape -------------------------------------------------------------------

def test_duplicates_collapse():
    got = identity.extract(
        row(
            url="https://arxiv.org/abs/2609.17527",
            canonical_url="https://arxiv.org/abs/2609.17527",
            summary="See arXiv:2609.17527 and https://arxiv.org/pdf/2609.17527",
        )
    )
    assert find(identity.ARXIV, got) == ["2609.17527"]


def test_an_item_with_nothing_identifiable_yields_nothing():
    assert identity.extract(row(url="https://x.test/", canonical_url="https://x.test/")) == []


def test_strong_and_weak_sets_do_not_overlap():
    assert not (identity.STRONG & identity.WEAK)
