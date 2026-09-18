from __future__ import annotations

import pytest

from tributary import facets
from tributary.config import FacetConfig

AGENTS = FacetConfig(slug="agents", name="Agents", pattern=r"\bagent(s|ic)?\b")
BENCH = FacetConfig(slug="benchmark", name="Benchmarks", pattern=r"\bbenchmark")


@pytest.fixture
def story(conn, source_id):
    """A story from (title, summary) pairs, one item each, returning its id."""
    counter = {"n": 0}

    def _story(*texts):
        story_id = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) "
            "VALUES ('2026-09-15T00:00:00Z', datetime('now'))"
        ).lastrowid
        for title, summary in texts:
            counter["n"] += 1
            item_id = conn.execute(
                "INSERT INTO items (source_id, external_id, kind, url, title, summary, "
                "triage_state) VALUES (?, ?, 'article', 'https://e.test/x', ?, ?, 'kept')",
                (source_id, f"e{counter['n']}", title, summary),
            ).lastrowid
            conn.execute(
                "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                (story_id, item_id),
            )
        return story_id

    return _story


def slugs(conn, story_id) -> set[str]:
    return {
        row["slug"]
        for row in conn.execute("SELECT slug FROM story_facets WHERE story_id = ?", (story_id,))
    }


def test_a_word_in_the_title_sets_the_facet(conn, story):
    found = story(("Coding agents have converged", None))
    facets.run(conn, [AGENTS])

    assert slugs(conn, found) == {"agents"}


def test_matching_ignores_case(conn, story):
    found = story(("AGENTIC workflows", None))
    facets.run(conn, [AGENTS])

    assert slugs(conn, found) == {"agents"}


def test_the_summary_counts_as_much_as_the_title(conn, story):
    found = story(("A new model", "It ships with an agent SDK."))
    facets.run(conn, [AGENTS])

    assert slugs(conn, found) == {"agents"}


def test_a_story_is_matched_on_everything_in_it(conn, story):
    """The first item is not the story -- the thread arguing about it counts too."""
    found = story(("A paper on routing", None), ("HN: do agents need this?", None))
    facets.run(conn, [AGENTS])

    assert slugs(conn, found) == {"agents"}


def test_facets_stack(conn, story):
    found = story(("An agent benchmark", None))
    facets.run(conn, [AGENTS, BENCH])

    assert slugs(conn, found) == {"agents", "benchmark"}


def test_a_word_inside_another_word_does_not_count(conn, story):
    """`agenda` is not about agents: the pattern's word boundary is doing work."""
    found = story(("The agenda for the week", None))
    result = facets.run(conn, [AGENTS])

    assert slugs(conn, found) == set()
    assert result.matched == 0
    assert result.stories == 1


def test_rerunning_replaces_rather_than_accumulates(conn, story):
    """A pattern that stops matching must take its old rows with it."""
    found = story(("An agent benchmark", None))
    facets.run(conn, [AGENTS, BENCH])
    facets.run(conn, [BENCH])

    assert slugs(conn, found) == {"benchmark"}


def test_no_facets_clears_every_match(conn, story):
    found = story(("An agent", None))
    facets.run(conn, [AGENTS])
    facets.run(conn, [])

    assert slugs(conn, found) == set()


def test_counts_are_per_facet(conn, story):
    story(("One agent", None))
    story(("Two agents and a benchmark", None))
    result = facets.run(conn, [AGENTS, BENCH])

    assert result.by_facet == {"agents": 2, "benchmark": 1}
    assert result.matched == 2


def test_for_stories_returns_slugs_for_the_bundle(conn, story):
    found = story(("An agent benchmark", None))
    bare = story(("Nothing to see", None))
    facets.run(conn, [AGENTS, BENCH])

    by_story = facets.for_stories(conn, [found, bare])
    assert sorted(by_story[found]) == ["agents", "benchmark"]
    assert bare not in by_story
    assert facets.for_stories(conn, []) == {}
