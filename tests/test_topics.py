from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
import sqlite_vec

from tributary import embeddings, topics
from tributary.config import CLAIMS_FLAGS, TopicConfig, TopicsConfig, load


def unit(*values) -> bytes:
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    vector /= np.linalg.norm(vector)
    return sqlite_vec.serialize_float32(vector.tolist())


def profile(floor=0.55, *slugs, park_margin=0.02, parents=None) -> TopicsConfig:
    parents = parents or {}
    return TopicsConfig(
        floor=floor,
        park_margin=park_margin,
        spine=[
            TopicConfig(
                slug=s, name=s.title(), description=f"about {s}", parent=parents.get(s)
            )
            for s in slugs
        ],
    )


@pytest.fixture
def axes(monkeypatch):
    """Topic descriptions pinned to known axes, so scores are exact cosines."""
    directions = {
        "about models": unit(1.0, 0.0),
        "about agents": unit(0.0, 1.0),
        "about safety": unit(0.0, 0.0, 1.0),
        # Two neighbours on one shelf, close enough to be a coin-toss.
        "about frontier": unit(1.0, 0.0),
        "about open": unit(0.99, 0.1),
    }

    def fake_embed(texts, model_name=None):
        return [np.frombuffer(directions[t], dtype=np.float32) for t in texts]

    monkeypatch.setattr(topics, "embed", fake_embed)


@pytest.fixture
def story(conn, source_id):
    """Build a story from items at given angles, returning its id."""
    counter = {"n": 0}

    def _story(*vectors, titles=(), kind="article"):
        """`titles` name the items in arrival order; the first is the headline."""
        # last_activity is "now" because --suggest works on a recent window.
        story_id = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) "
            "VALUES ('2026-09-15T00:00:00Z', datetime('now'))"
        ).lastrowid
        for n, vector in enumerate(vectors):
            counter["n"] += 1
            item_id = conn.execute(
                "INSERT INTO items (source_id, external_id, kind, url, title, triage_state) "
                "VALUES (?, ?, ?, 'https://e.test/x', ?, 'kept')",
                (source_id, f"e{counter['n']}", kind,
                 titles[n] if n < len(titles) else "A title"),
            ).lastrowid
            conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                         (item_id, vector))
            conn.execute(
                "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                (story_id, item_id),
            )
        return story_id

    return _story


def slugs_for(conn, story_id) -> set[str]:
    return {
        row["slug"]
        for row in conn.execute(
            "SELECT t.slug FROM story_topics stp JOIN topics t ON t.id = stp.topic_id "
            "WHERE stp.story_id = ?",
            (story_id,),
        )
    }


# --- centroids ---------------------------------------------------------------

def test_a_story_is_the_mean_of_its_members(conn, story):
    """Its subject is everything in it, not whichever item arrived first."""
    story_id = story(unit(1.0, 0.0), unit(0.0, 1.0))
    found, vectors = topics.centroids(conn, [story_id])

    assert found == [story_id]
    # Halfway between the two axes, and still a unit vector.
    assert vectors[0][0] == pytest.approx(0.7071, abs=1e-3)
    assert vectors[0][1] == pytest.approx(0.7071, abs=1e-3)
    assert float(np.linalg.norm(vectors[0])) == pytest.approx(1.0, abs=1e-5)


def test_a_story_with_no_vectors_is_skipped(conn, story):
    assert topics.centroids(conn, [story()]) == ([], pytest.approx(np.zeros((0, 0))))


# --- assignment --------------------------------------------------------------

def test_a_story_goes_to_the_topic_that_fits_it_best(conn, story, axes):
    on_models = story(unit(1.0, 0.0))
    topics.run(conn, profile(0.55, "models", "agents"))

    assert slugs_for(conn, on_models) == {"models"}


def test_a_story_between_two_subjects_still_picks_one(conn, story, axes):
    """One home. A tie on two unrelated shelves is broken, not split.

    This is the behaviour that replaced multi-label assignment: scoring two
    descriptions against the same story produced differences far inside the
    noise, so taking every topic over a line meant taking almost all of them.
    """
    both = story(unit(1.0, 0.999))  # very nearly equidistant from both axes
    topics.run(conn, profile(0.55, "models", "agents"))

    assert len(slugs_for(conn, both)) == 1


def test_a_weak_best_match_still_wins(conn, story, axes):
    """There is no threshold deciding what counts as a match, only a floor."""
    leaning = story(unit(1.0, 0.9, 0.2))
    topics.run(conn, profile(0.10, "models", "agents", "safety"))

    assert slugs_for(conn, leaning) == {"models"}


def test_a_close_pair_on_one_shelf_parks_on_the_shelf(conn, story, axes):
    """The shelf is clear and the leaf is a coin-toss, so do not invent a leaf."""
    parents = {"frontier": "models", "open": "models"}
    spine = profile(0.10, "models", "frontier", "open", parents=parents, park_margin=0.5)
    near = story(unit(1.0, 0.0))
    topics.run(conn, spine)

    assert slugs_for(conn, near) == {"models"}


def test_a_clear_leaf_is_not_parked(conn, story, axes):
    parents = {"frontier": "models", "open": "models"}
    spine = profile(0.10, "models", "frontier", "open", parents=parents, park_margin=0.0)
    near = story(unit(1.0, 0.0))
    topics.run(conn, spine)

    assert slugs_for(conn, near) != {"models"}


def test_a_story_matching_nothing_is_still_marked_done(conn, story, axes):
    """Otherwise every off-spine story is rescored on every run, forever."""
    unrelated = story(unit(0.0, 0.0, 0.0, 1.0))
    result = topics.run(conn, profile(0.60, "models"))

    assert result.unmatched == 1
    assert slugs_for(conn, unrelated) == set()
    assert topics.pending(conn) == []


def test_an_assigned_story_is_not_rescored(conn, story, axes):
    story(unit(1.0, 0.0))
    spine = profile(0.60, "models")
    topics.run(conn, spine)

    assert topics.run(conn, spine).stories == 0


def test_no_spine_does_nothing(conn, story):
    story(unit(1.0, 0.0))
    assert topics.run(conn, TopicsConfig()).stories == 0


# --- the spine changing ------------------------------------------------------

def test_changing_the_spine_relabels_the_back_catalogue(conn, story, axes):
    labelled = story(unit(1.0, 0.0))
    first = profile(0.60, "models")
    topics.reset_if_profile_changed(conn, first)
    topics.run(conn, first)
    assert slugs_for(conn, labelled) == {"models"}

    widened = profile(0.60, "models", "agents")
    assert topics.reset_if_profile_changed(conn, widened) is True
    assert topics.pending(conn) == [labelled]


def test_an_unchanged_spine_does_not_relabel(conn, axes):
    spine = profile(0.60, "models")
    assert topics.reset_if_profile_changed(conn, spine) is True
    assert topics.reset_if_profile_changed(conn, spine) is False


def test_a_slug_dropped_from_the_spine_stops_existing(conn, story, axes):
    story(unit(1.0, 0.0))
    both = profile(0.60, "models", "agents")
    topics.reset_if_profile_changed(conn, both)
    topics.run(conn, both)

    narrowed = profile(0.60, "models")
    topics.reset_if_profile_changed(conn, narrowed)
    topics.run(conn, narrowed)
    assert {row["slug"] for row in topics.stats(conn)} == {"models"}


# --- the bundle --------------------------------------------------------------

def test_for_stories_returns_names_the_page_can_render(conn, story, axes):
    story_id = story(unit(1.0, 0.0))
    topics.run(conn, profile(0.60, "models"))

    assert topics.for_stories(conn, [story_id]) == {
        story_id: [{"slug": "models", "name": "Models"}]
    }


def test_for_stories_of_nothing_is_empty(conn):
    assert topics.for_stories(conn, []) == {}


# --- suggesting new topics ---------------------------------------------------
# The half that can be automated: find what clusters, and let something with
# judgement do the naming.


def titled(conn, source_id, story_id, title):
    item_id = conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, triage_state) "
        "VALUES (?, ?, 'article', 'https://e.test/x', ?, 'kept')",
        (source_id, f"t{story_id}-{title[:8]}", title),
    ).lastrowid
    conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                 (item_id, unit(1.0)))
    conn.execute("INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'coverage')",
                 (story_id, item_id))


def test_stories_about_the_same_thing_group(conn, story):
    for _ in range(3):
        story(unit(1.0, 0.05))
    for _ in range(3):
        story(unit(0.0, 1.0))

    groups = topics.suggest(conn, min_size=3)
    assert [g.size for g in groups] == [3, 3]


def test_a_group_too_small_to_name_is_not_offered(conn, story):
    story(unit(1.0))
    story(unit(1.0))
    assert topics.suggest(conn, min_size=3) == []


def test_groups_report_which_topics_already_claim_them(conn, story, axes):
    """The reviewer needs to know what is genuinely uncovered, not just what clusters."""
    for _ in range(3):
        story(unit(1.0, 0.0))
    topics.run(conn, profile(0.60, "models"))

    group = topics.suggest(conn, min_size=3)[0]
    assert group.covered == {"Models": 3}
    assert group.uncovered == 0


def test_a_story_on_two_topics_is_counted_once():
    """`covered` counts topic hits, and a story can hold more than one.

    Subtracting their sum from the group size reported negative "unclaimed"
    counts -- and since that is the sort key, the groups most worth naming sank
    to the bottom of the list.
    """
    group = topics.Candidate(size=3, covered={"Models": 3, "Agents": 3}, claimed=3)

    assert group.uncovered == 0


def test_an_uncovered_group_sorts_first(conn, story, axes):
    for _ in range(3):
        story(unit(1.0, 0.0))          # will be claimed by "models"
    for _ in range(3):
        story(unit(0.0, 0.0, 0.0, 1.0))  # nothing on the spine reaches this
    topics.run(conn, profile(0.60, "models"))

    groups = topics.suggest(conn, min_size=3)
    assert groups[0].uncovered == 3
    assert groups[0].covered == {}


def test_titles_come_back_for_the_reviewer_to_read(conn, source_id, story):
    titled(conn, source_id, story(), "A headline worth naming a topic after")
    for _ in range(2):
        story(unit(1.0, 0.02))

    group = topics.suggest(conn, min_size=3)[0]
    assert "A headline worth naming a topic after" in group.titles


def test_nothing_recent_suggests_nothing(conn):
    assert topics.suggest(conn) == []


# --- nesting -----------------------------------------------------------------

def nested() -> TopicsConfig:
    return TopicsConfig(
        spine=[
            # Child first, to prove declaration order does not matter.
            TopicConfig("models", "Models", "about models", parent="shelf"),
            TopicConfig("shelf", "AI models", "about agents"),
        ],
    )


def test_a_child_knows_its_parent(conn, story, axes):
    story_id = story(unit(1.0, 0.0))
    topics.run(conn, nested())

    labels = {t["slug"]: t for t in topics.for_stories(conn, [story_id])[story_id]}
    assert labels["models"]["parent"] == "shelf"
    assert labels["models"]["parent_name"] == "AI models"


def test_a_shelf_has_no_parent_of_its_own(conn, story, axes):
    """A shelf is reached by parking, since only leaves are ever scored."""
    parents = {"frontier": "models", "open": "models"}
    story_id = story(unit(1.0, 0.0))
    topics.run(
        conn, profile(0.10, "models", "frontier", "open", parents=parents, park_margin=0.5)
    )

    label = topics.for_stories(conn, [story_id])[story_id][0]
    assert label["slug"] == "models"
    assert "parent" not in label


def test_moving_a_topic_to_another_shelf_changes_the_fingerprint():
    flat = TopicsConfig(spine=[TopicConfig("a", "A", "about a")])
    under = TopicsConfig(spine=[TopicConfig("a", "A", "about a", parent="b")])
    assert flat.fingerprint() != under.fingerprint()


def test_parked_stories_are_the_gap_suggest_leads_with(conn, story, axes):
    """Under one home nearly nothing is unclaimed, so parking is the signal.

    A group whose stories sat on a shelf because no leaf fitted is what a
    missing leaf looks like, and it should be read first.
    """
    parents = {"frontier": "models", "open": "models"}
    for _ in range(3):
        story(unit(0.0, 1.0))  # a clear home on its own leaf
    for _ in range(3):
        story(unit(1.0, 0.0))  # a coin-toss between two leaves on one shelf
    topics.run(
        conn,
        profile(0.10, "models", "frontier", "open", "agents", parents=parents, park_margin=0.5),
    )

    groups = topics.suggest(conn, min_size=3)
    assert [g.parked for g in groups] == [3, 0]
    assert groups[0].uncovered == 0
    assert groups[0].unplaced == 3


def test_stats_counts_stories_triage_would_have_dropped(conn, source_id):
    """Short or off-profile stories -- which is not the same as off-topic."""
    from tributary import topics as topics_mod

    topic_id = conn.execute(
        "INSERT INTO topics (slug, name) VALUES ('t', 'A topic')"
    ).lastrowid

    def story(state):
        story_id = conn.execute("INSERT INTO stories DEFAULT VALUES").lastrowid
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, triage_state, "
            "content_hash) VALUES (?, ?, 'article', 'https://e.test/x', 'T', ?, 'h')",
            (source_id, f"e{story_id}", state),
        ).lastrowid
        conn.execute("INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                     (story_id, item_id))
        conn.execute("INSERT INTO story_topics (story_id, topic_id) VALUES (?, ?)",
                     (story_id, topic_id))

    story("kept")
    story("rejected")
    story("rejected")

    row = next(r for r in topics_mod.stats(conn) if r["slug"] == "t")
    assert row["stories"] == 3
    assert row["below_triage"] == 2


def test_stats_counts_nothing_below_triage_for_an_empty_topic(conn):
    from tributary import topics as topics_mod

    conn.execute("INSERT INTO topics (slug, name) VALUES ('quiet', 'Nothing here')")
    row = next(r for r in topics_mod.stats(conn) if r["slug"] == "quiet")
    assert row["stories"] == 0
    assert (row["below_triage"] or 0) == 0


# --- claiming by headline ----------------------------------------------------

def claiming(pattern=r"^introducing \s+ claude"):
    """Agents and frontier, where frontier claims launch headlines."""
    return TopicsConfig(
        spine=[
            TopicConfig("agents", "Agents", "about agents"),
            TopicConfig("frontier", "Frontier", "about frontier", claims=pattern),
        ]
    )


def test_a_claimed_headline_beats_a_better_score(conn, story, axes):
    """A launch post's prose scores wherever benchmarks and pricing resemble.

    *Introducing Claude Opus 5.5* went to Chips & datacenters on similarity; its
    title says what it is, and the title is asked first.
    """
    launch = story(unit(0.0, 1.0), titles=["Introducing Claude Opus 5.5"])
    result = topics.run(conn, claiming())

    assert slugs_for(conn, launch) == {"frontier"}
    assert result.claimed == 1


def test_a_story_nothing_claims_is_scored_as_before(conn, story, axes):
    plain = story(unit(0.0, 1.0), titles=["An agent that books flights"])
    result = topics.run(conn, claiming())

    assert slugs_for(conn, plain) == {"agents"}
    assert result.claimed == 0


def test_a_paper_is_never_claimed(conn, story, axes):
    """A paper naming a model in its title is about the model, not its launch."""
    paper = story(unit(0.0, 1.0), titles=["Introducing Claude to theorem proving"],
                  kind="paper")
    topics.run(conn, claiming())

    assert slugs_for(conn, paper) == {"agents"}


def test_only_the_headline_is_read(conn, story, axes):
    """Coverage arriving later names the model constantly; the first item decides."""
    coverage = story(unit(0.0, 1.0), unit(0.0, 1.0),
                     titles=["An agent that books flights", "Introducing Claude Opus 5.5"])
    topics.run(conn, claiming())

    assert slugs_for(conn, coverage) == {"agents"}


def test_a_claim_needs_no_floor(conn, story, axes):
    """The floor catches a story the spine has no opinion about; a claim is one."""
    far = story(unit(0.0, 0.0, 0.0, 1.0), titles=["Introducing Claude Opus 5.5"])
    topics.run(conn, claiming())

    assert slugs_for(conn, far) == {"frontier"}


def shipped_claim() -> re.Pattern:
    repo_config = Path(__file__).parent.parent / "config.toml"
    frontier = next(t for t in load(repo_config).topics.spine if t.slug == "frontier")
    return re.compile(frontier.claims, CLAIMS_FLAGS)


@pytest.mark.parametrize(
    "title",
    [
        # The four launches the spine missed in the fortnight to 2026-09-22.
        "Introducing GPT-6 Sol and Luna",
        "Introducing Claude Opus 5.5",
        "Grok 4.7",
        "Anthropic releases Opus 5.5",
        # And the other shapes a launch arrives in.
        "OpenAI launches GPT-6",
        "Google releases Gemini 3 with a million-token window",
        "xAI unveils Grok 5",
        "Introducing the new GPT-6",
        "Gemini 2.5 Flash",
        "GPT-5.5 is here",
        "GPT-4o",
        "[N] Claude Sonnet 5 released",
    ],
)
def test_the_frontier_claim_takes_launches(title):
    assert shipped_claim().search(title)


@pytest.mark.parametrize(
    "title",
    [
        "Claude Code 2.0 is out",          # a tool on a model line's name
        "Introducing Claude Code 2.0",
        "Gemini CLI now supports MCP",
        "GPT4All 3.0 released",            # not GPT at all
        "Grok Imagine",                    # no version, so no release
        "Qwen 4 Announced",                # open weights has its own leaf
        "Claude Opus 5.5 helped me write a compiler",
        "GPT-5.5 is worse at math than GPT-5",
        "Gemini 3 Pro scores 80% on ARC-AGI-3, beating Opus 5",
        "Why GPT-6 matters",
        "Evaluating GPT-5 on medical exams",
        "Anthropic releases a report on Claude 4 misuse",
        "OpenAI raises $40B",
    ],
)
def test_the_frontier_claim_leaves_the_rest_to_scoring(title):
    """A model's name in the title is not enough: it has to be the headline's subject."""
    assert not shipped_claim().search(title)


# --- explain -----------------------------------------------------------------

def test_explain_shows_the_scores_and_agrees_with_run(conn, story, axes):
    """`--why` must tell the truth about what `run` decided, and write nothing."""
    leaning = story(unit(1.0, 0.6), titles=("Gemini hacked three companies",))
    spine = profile(0.10, "models", "agents")

    found = topics.explain(conn, spine, leaning)
    assert found.home == "models" and not found.parked and found.stored is None
    assert [slug for slug, _ in found.scores] == ["models", "agents"]
    assert found.margin == pytest.approx(found.scores[0][1] - found.scores[1][1])
    assert not slugs_for(conn, leaning), "explaining must not label"

    topics.run(conn, spine)
    assert topics.explain(conn, spine, leaning).stored == "models"


def test_explain_names_a_parked_story_and_a_headline_claim(conn, story, axes):
    parents = {"frontier": "models", "open": "models"}
    spine = profile(0.10, "models", "frontier", "open", parents=parents, park_margin=0.5)
    near = story(unit(1.0, 0.0))
    assert topics.explain(conn, spine, near).parked

    spine.spine[1].claims = r"introducing\s+gpt"
    launch = story(unit(0.0, 1.0), titles=("Introducing GPT-7",))
    found = topics.explain(conn, spine, launch)
    assert found.claimed == "frontier" and found.home == "frontier"


def test_a_story_is_found_by_id_or_by_words_in_its_title(conn, story):
    first = story(unit(1.0), titles=("Gemini Hacked Three Companies",))
    assert topics.find_story(conn, str(first)) == first
    assert topics.find_story(conn, "hacked three") == first
    assert topics.find_story(conn, "nothing like this") is None
