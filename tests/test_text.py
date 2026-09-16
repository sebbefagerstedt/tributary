from __future__ import annotations

import pytest

from tributary.text import strip_html, truncate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<p>Hello <b>world</b>.</p>", "Hello world."),
        ("<p>one</p><p>two</p>", "one two"),          # block tags must not glue words
        ("a &amp; b &quot;q&quot;", 'a & b "q"'),
        ("<p>See (<a href='#'>this</a>) now</p>", "See (this) now"),
        ("   \n  spaced   out \t", "spaced out"),
        ("<br/>", None),
        ("", None),
        (None, None),
    ],
)
def test_strip_html(raw, expected):
    assert strip_html(raw) == expected


def test_truncate_prefers_word_boundary():
    assert truncate("the quick brown fox jumps", 12) == "the quick…"


def test_truncate_cuts_mid_word_when_no_boundary_is_near():
    assert truncate("supercalifragilistic", 10) == "supercalif…"


def test_truncate_leaves_short_values_alone():
    assert truncate("short", 20) == "short"
    assert truncate(None, 20) is None
