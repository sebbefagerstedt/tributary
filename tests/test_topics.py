from __future__ import annotations

import numpy as np
import pytest
import sqlite_vec

from tributary import embeddings, topics
from tributary.config import TopicConfig, TopicsConfig


def unit(*values) -> bytes:
    vector = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    vector[: len(values)] = values
    vector /= np.linalg.norm(vector)
    return sqlite_vec.serialize_float32(vector.tolist())


def profile(threshold=0.60, max_per_story=3, *slugs) -> TopicsConfig:
    return TopicsConfig(
        threshold=threshold,
        max_per_story=max_per_story,
        spine=[TopicConfig(slug=s, name=s.title(), description=f"about {s}") for s in slugs],
    )


@pytest.fixture
def axes(monkeypatch):
    """Topic descriptions pinned to known axes, so scores are exact cosines."""
    directions = {
        "about models": unit(1.0, 0.0),
        "about agents": unit(0.0, 1.0),
        "about safety": unit(0.0, 0.0, 1.0),
    }

    def fake_embed(texts, model_name=None):
        return [np.frombuffer(directions[t], dtype=np.float32) for t in texts]

    monkeypatch.setattr(topics, "embed", fake_embed)


@pytest.fixture
def story(conn, source_id):
    """Build a story from items at given angles, returning its id."""
    counter = {"n": 0}

    def _story(*vectors):
        # last_activity is "now" because --suggest works on a recent window.
        story_id = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) "
            "VALUES ('2026-09-15T00:00:00Z', datetime('now'))"
        ).lastrowid
        for vector in vectors:
            counter["n"] += 1
            item_id = conn.execute(
                "INSERT INTO items (source_id, external_id, kind, url, title, triage_state) "
                "VALUES (?, ?, 'article', 'https://e.test/x', 'A title', 'kept')",
                (source_id, f"e{counter['n']}"),
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

def test_a_story_takes_the_topics_it_clears(conn, story, axes):
    on_models = story(unit(1.0, 0.0))
    topics.run(conn, profile(0.60, 3, "models", "agents"))

    assert slugs_for(conn, on_models) == {"models"}


def test_a_story_between_two_subjects_takes_both(conn, story, axes):
    both = story(unit(1.0, 0.0), unit(0.0, 1.0))  # cosine 0.707 with each
    topics.run(conn, profile(0.60, 3, "models", "agents"))

    assert slugs_for(conn, both) == {"models", "agents"}


def test_only_the_strongest_topics_survive_the_cap(conn, story, axes):
    leaning = story(unit(1.0, 0.9, 0.2))
    topics.run(conn, profile(0.10, 2, "models", "agents", "safety"))

    assert slugs_for(conn, leaning) == {"models", "agents"}  # safety scores lowest


def test_a_story_matching_nothing_is_still_marked_done(conn, story, axes):
    """Otherwise every off-spine story is rescored on every run, forever."""
    unrelated = story(unit(0.0, 0.0, 0.0, 1.0))
    result = topics.run(conn, profile(0.60, 3, "models"))

    assert result.unmatched == 1
    assert slugs_for(conn, unrelated) == set()
    assert topics.pending(conn) == []


def test_an_assigned_story_is_not_rescored(conn, story, axes):
    story(unit(1.0, 0.0))
    spine = profile(0.60, 3, "models")
    topics.run(conn, spine)

    assert topics.run(conn, spine).stories == 0


def test_no_spine_does_nothing(conn, story):
    story(unit(1.0, 0.0))
    assert topics.run(conn, TopicsConfig()).stories == 0


# --- the spine changing ------------------------------------------------------

def test_changing_the_spine_relabels_the_back_catalogue(conn, story, axes):
    labelled = story(unit(1.0, 0.0))
    first = profile(0.60, 3, "models")
    topics.reset_if_profile_changed(conn, first)
    topics.run(conn, first)
    assert slugs_for(conn, labelled) == {"models"}

    widened = profile(0.60, 3, "models", "agents")
    assert topics.reset_if_profile_changed(conn, widened) is True
    assert topics.pending(conn) == [labelled]


def test_an_unchanged_spine_does_not_relabel(conn, axes):
    spine = profile(0.60, 3, "models")
    assert topics.reset_if_profile_changed(conn, spine) is True
    assert topics.reset_if_profile_changed(conn, spine) is False


def test_a_slug_dropped_from_the_spine_stops_existing(conn, story, axes):
    story(unit(1.0, 0.0))
    both = profile(0.60, 3, "models", "agents")
    topics.reset_if_profile_changed(conn, both)
    topics.run(conn, both)

    narrowed = profile(0.60, 3, "models")
    topics.reset_if_profile_changed(conn, narrowed)
    topics.run(conn, narrowed)
    assert {row["slug"] for row in topics.stats(conn)} == {"models"}


# --- the bundle --------------------------------------------------------------

def test_for_stories_returns_names_the_page_can_render(conn, story, axes):
    story_id = story(unit(1.0, 0.0))
    topics.run(conn, profile(0.60, 3, "models"))

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
    topics.run(conn, profile(0.60, 3, "models"))

    group = topics.suggest(conn, min_size=3)[0]
    assert group.covered == {"Models": 3}
    assert group.uncovered == 0


def test_an_uncovered_group_sorts_first(conn, story, axes):
    for _ in range(3):
        story(unit(1.0, 0.0))          # will be claimed by "models"
    for _ in range(3):
        story(unit(0.0, 0.0, 0.0, 1.0))  # nothing on the spine reaches this
    topics.run(conn, profile(0.60, 3, "models"))

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
        threshold=0.60,
        max_per_story=3,
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
    story_id = story(unit(0.0, 1.0))
    topics.run(conn, nested())

    label = topics.for_stories(conn, [story_id])[story_id][0]
    assert label["slug"] == "shelf"
    assert "parent" not in label


def test_moving_a_topic_to_another_shelf_changes_the_fingerprint():
    flat = TopicsConfig(spine=[TopicConfig("a", "A", "about a")])
    under = TopicsConfig(spine=[TopicConfig("a", "A", "about a", parent="b")])
    assert flat.fingerprint() != under.fingerprint()
