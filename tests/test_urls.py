from __future__ import annotations

import pytest

from tributary.urls import canonicalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com/post/", "https://example.com/post"),
        ("http://www.example.com/post", "https://example.com/post"),
        ("https://EXAMPLE.com/Post", "https://example.com/Post"),  # path case is significant
        ("https://example.com/p?utm_source=x&id=7", "https://example.com/p?id=7"),
        ("https://example.com/p?fbclid=abc", "https://example.com/p"),
        ("https://example.com/p#section", "https://example.com/p"),
        ("https://example.com/p?b=2&a=1", "https://example.com/p?a=1&b=2"),
        ("https://example.com", "https://example.com/"),
        ("https://example.com:443/p", "https://example.com/p"),
    ],
)
def test_canonicalize(raw, expected):
    assert canonicalize(raw) == expected


def test_tracking_variants_collapse_to_one_url():
    """The point of canonicalisation: one document, one key."""
    variants = [
        "https://example.com/story?utm_source=twitter&utm_medium=social",
        "http://www.example.com/story/",
        "https://example.com/story#intro",
        "https://example.com/story?fbclid=xyz",
    ]
    assert len({canonicalize(v) for v in variants}) == 1


def test_unparseable_input_is_returned_unchanged():
    assert canonicalize("not a url") == "not a url"
    assert canonicalize("") == ""
