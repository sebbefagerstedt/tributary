from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tributary import feed

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)


# --- the score ---------------------------------------------------------------

def test_recency_halves_the_score_every_half_life():
    fresh = feed.score_story(1.0, 0.0, 1, 1)
    older = feed.score_story(1.0, feed.HALF_LIFE_HOURS, 1, 1)
    assert older == fresh / 2


def test_corroboration_helps_but_does_not_dominate():
    """Several sources covering a thing is a signal; it must not beat relevance."""
    corroborated = feed.score_story(0.70, 0.0, sources=4, roles=3)
    more_relevant = feed.score_story(0.95, 0.0, sources=1, roles=1)
    assert corroborated > feed.score_story(0.70, 0.0, 1, 1)
    assert more_relevant > corroborated


def test_an_undated_item_is_not_treated_as_fresh():
    assert feed._age_hours(None, NOW) > 24 * 300


# --- diversity ---------------------------------------------------------------

def card(story_id, score, source, kind="article"):
    return feed.StoryCard(
        story_id=story_id, title=f"t{story_id}", summary=None, url="https://e.test",
        kind=kind, source=source, published_at="2026-09-16T00:00:00Z", score=score,
    )


def test_diversify_breaks_up_a_single_source_flood():
    """Measured problem: arXiv publishes ~150/day and took 47 of the first 50 cards."""
    flood = [card(n, 0.9 - n * 0.001, "arXiv", "paper") for n in range(20)]
    others = [card(100 + n, 0.5, f"Blog {n}", "article") for n in range(5)]

    picked = feed.diversify(flood + others, limit=6)
    sources = [c.source for c in picked]
    assert sources[0] == "arXiv"          # the strongest card still leads
    assert sources.count("arXiv") <= 3    # but stops crowding everything out
    assert len(set(sources)) >= 3


def test_diversify_keeps_a_dominant_source_when_it_really_dominates():
    """A day where arXiv genuinely is the news should still look like that."""
    strong = [card(n, 0.9, "arXiv", "paper") for n in range(5)]
    weak = [card(100 + n, 0.05, f"Blog {n}") for n in range(5)]
    picked = feed.diversify(strong + weak, limit=3)
    assert [c.source for c in picked].count("arXiv") >= 2


def test_diversify_returns_everything_when_under_the_limit():
    cards = [card(1, 0.5, "A"), card(2, 0.4, "B")]
    assert len(feed.diversify(cards, limit=10)) == 2


def test_diversify_never_repeats_a_card():
    cards = [card(n, 0.5, "Same") for n in range(5)]
    picked = feed.diversify(cards, limit=5)
    assert len({c.story_id for c in picked}) == 5


# --- cards -------------------------------------------------------------------

def test_signal_row_summarises_what_is_attached():
    c = card(1, 0.5, "A")
    c.roles = {"paper": 1, "discussion": 2, "coverage": 1}
    c.sources = ["A", "B", "C"]
    signal = c.signal()
    assert "1 paper" in signal
    assert "2 discussions" in signal  # pluralised
    assert "3 sources" in signal


def test_signal_row_is_empty_for_a_lone_item():
    c = card(1, 0.5, "A")
    c.roles = {"seed": 1}
    c.sources = ["A"]
    assert c.signal() == ""


def test_lead_prefers_the_paper_over_coverage_of_it():
    """Measured bug: an RSS rewrite outranked the paper and supplied its summary."""
    paper = {"kind": "paper", "role": "paper", "triage_score": 0.7}
    rewrite = {"kind": "article", "role": "seed", "triage_score": 0.9}
    assert feed._lead_rank(paper) < feed._lead_rank(rewrite)


# --- renewal -----------------------------------------------------------------

def make_story(conn, source_id, members, story_id=None):
    """A story whose members sit at the ages given, in hours before NOW.

    Written straight into the tables rather than through the clusterer: this is
    a measurement about dates, and the clusterer would drag embeddings into it.
    """
    story_id = conn.execute(
        "INSERT INTO stories (title, last_activity) VALUES (NULL, ?)",
        (NOW.isoformat(),),
    ).lastrowid
    for n, (age_hours, role, kind) in enumerate(members):
        stamp = (NOW - timedelta(hours=age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, published_at, "
            "triage_state, triage_score, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, 'kept', 0.8, 'h')",
            (source_id, f"s{story_id}i{n}", kind, f"https://e.test/{story_id}/{n}",
             f"Story {story_id} item {n}", stamp),
        ).lastrowid
        conn.execute(
            "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, ?)",
            (story_id, item_id, role),
        )
    return story_id


def test_renewal_reports_no_gap_for_a_story_that_arrived_all_at_once(conn, source_id):
    make_story(conn, source_id, [(2, "seed", "article")])
    rows, summary = feed.renewal(conn, now=NOW)

    assert len(rows) == 1
    assert rows[0].gap_hours == 0
    assert summary["renewed"] == 0


def test_renewal_measures_what_a_late_arrival_bought(conn, source_id):
    """A three-day-old paper with a thread from an hour ago ranks as an hour old."""
    make_story(conn, source_id, [(73, "paper", "paper"), (1, "discussion", "discussion")])
    rows, summary = feed.renewal(conn, now=NOW)

    row = rows[0]
    assert row.gap_hours == 72
    assert row.renewed_role == "discussion"
    # 72 hours is a day and a half of half-lives: 2 ** 1.5.
    assert row.lift == pytest.approx(2 ** 1.5)
    assert summary["renewed"] == 1
    assert summary["by_role"] == {"discussion": 1}


def test_renewal_shows_the_positions_a_refreshed_clock_gained(conn, source_id):
    """The complaint this exists for: an older story sitting above a newer one."""
    old = make_story(conn, source_id, [(96, "paper", "paper"), (1, "coverage", "article")])
    make_story(conn, source_id, [(10, "seed", "article")])

    rows, _ = feed.renewal(conn, now=NOW)
    by_story = {row.story_id: row for row in rows}

    assert by_story[old].position == 1           # the refreshed story leads
    assert by_story[old].origin_position == 2    # aged from its paper, it would not
    assert by_story[old].moved == 1


def test_renewal_counts_a_story_only_a_late_arrival_put_in_the_feed(conn, source_id):
    """`carried` is the number that decides whether the clock needs damping."""
    stale = make_story(conn, source_id, [(24 * 30, "paper", "paper"), (1, "coverage", "article")])
    for _ in range(3):
        make_story(conn, source_id, [(4, "seed", "article")])

    rows, summary = feed.renewal(conn, limit=2, now=NOW)
    carried = [row for row in rows if row.carried]

    # A month-old paper is far outside the feed on its own dates, so it is in
    # this list only because something joined it an hour ago.
    assert [row.story_id for row in carried] == [stale]
    assert summary["carried"] == 1


def test_renewal_is_empty_rather_than_failing_on_an_empty_database(conn):
    rows, summary = feed.renewal(conn, now=NOW)
    assert rows == []
    assert summary["stories"] == 0
