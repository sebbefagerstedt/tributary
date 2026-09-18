from __future__ import annotations

import json

import pytest

from tributary import entities
from tributary.config import EntityConfig

OPENAI = EntityConfig(kind="org", name="OpenAI", aliases=["Open AI"])
GPT = EntityConfig(kind="model", name="GPT", aliases=["ChatGPT", "GPT-5"])
PHI = EntityConfig(kind="model", name="Phi")


@pytest.fixture
def story(conn, source_id):
    counter = {"n": 0}

    def _story(*titles):
        story_id = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) "
            "VALUES ('2026-09-15T00:00:00Z', datetime('now'))"
        ).lastrowid
        for title in titles:
            counter["n"] += 1
            item_id = conn.execute(
                "INSERT INTO items (source_id, external_id, kind, url, title, triage_state) "
                "VALUES (?, ?, 'article', 'https://e.test/x', ?, 'kept')",
                (source_id, f"e{counter['n']}", title),
            ).lastrowid
            conn.execute(
                "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
                (story_id, item_id),
            )
        return story_id

    return _story


def names(conn, story_id) -> set[str]:
    return {
        row["name"]
        for row in conn.execute(
            "SELECT e.name FROM story_entities se JOIN entities e ON e.id = se.entity_id "
            "WHERE se.story_id = ?",
            (story_id,),
        )
    }


def test_a_named_lab_is_attached(conn, story):
    found = story("OpenAI ships a new model")
    entities.run(conn, [OPENAI])

    assert names(conn, found) == {"OpenAI"}


def test_an_alias_attaches_the_entity_it_belongs_to(conn, story):
    found = story("ChatGPT gets memory")
    entities.run(conn, [GPT])

    assert names(conn, found) == {"GPT"}


def test_a_release_names_its_lab_and_its_model(conn, story):
    """The whole reason entities exist: one story, two things you might follow."""
    found = story("OpenAI releases GPT-5")
    entities.run(conn, [OPENAI, GPT])

    assert names(conn, found) == {"OpenAI", "GPT"}


def test_a_name_inside_a_longer_word_does_not_match(conn, story):
    """`Phi` is a model line; `philosophy` is not about it."""
    found = story("A philosophy of scaling")
    entities.run(conn, [PHI])

    assert names(conn, found) == set()


def test_a_dotted_name_is_one_word(conn, story):
    """`llama.cpp` is a tool; it must not also claim the Llama model."""
    llama = EntityConfig(kind="model", name="Llama")
    tool = EntityConfig(kind="tool", name="llama.cpp")
    build = story("ggml-org/llama.cpp b11003")
    sentence = story("Meta ships a new Llama.")
    entities.run(conn, [llama, tool])

    assert names(conn, build) == {"llama.cpp"}
    assert names(conn, sentence) == {"Llama"}


def test_a_hyphenated_alias_still_matches_as_a_whole(conn, story):
    found = story("Benchmarking GPT-5 on maths")
    entities.run(conn, [GPT])

    assert names(conn, found) == {"GPT"}


def test_seeding_writes_aliases_and_does_not_duplicate(conn):
    entities.sync(conn, [OPENAI])
    entities.sync(conn, [EntityConfig(kind="org", name="OpenAI", aliases=["OAI"])])

    rows = conn.execute("SELECT name, aliases FROM entities").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0]["aliases"]) == ["OAI"]


def test_an_entity_nobody_seeded_is_left_alone(conn):
    """An accepted entity must survive a config edit that never mentioned it."""
    conn.execute("INSERT INTO entities (kind, name) VALUES ('person', 'Andrej Karpathy')")
    entities.sync(conn, [OPENAI])

    found = {row["name"] for row in conn.execute("SELECT name FROM entities")}
    assert found == {"Andrej Karpathy", "OpenAI"}


def test_rerunning_drops_links_that_no_longer_match(conn, story):
    found = story("OpenAI releases GPT-5")
    entities.run(conn, [OPENAI, GPT])
    entities.run(conn, [OPENAI])

    assert names(conn, found) == {"OpenAI"}


def test_for_stories_returns_kind_and_name(conn, story):
    found = story("OpenAI releases GPT-5")
    entities.run(conn, [OPENAI, GPT])

    by_story = entities.for_stories(conn, [found])
    assert by_story[found] == [
        {"kind": "model", "name": "GPT"},
        {"kind": "org", "name": "OpenAI"},
    ]
    assert entities.for_stories(conn, []) == {}


def test_counts(conn, story):
    story("OpenAI news")
    story("OpenAI and ChatGPT")
    story("Nothing named")
    result = entities.run(conn, [OPENAI, GPT])

    assert result.stories == 3
    assert result.matched == 2
    assert result.by_entity == {"org:OpenAI": 2, "model:GPT": 1}


# --- proposing ---------------------------------------------------------------

@pytest.fixture
def told(conn, source_id):
    """A recent story with one item carrying a title and a prose summary."""
    counter = {"n": 0}

    def _told(title, summary):
        counter["n"] += 1
        story_id = conn.execute(
            "INSERT INTO stories (first_seen, last_activity) "
            "VALUES ('2026-09-15T00:00:00Z', datetime('now'))"
        ).lastrowid
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, summary, "
            "triage_state) VALUES (?, ?, 'article', 'https://e.test/x', ?, ?, 'kept')",
            (source_id, f"s{counter['n']}", title, summary),
        ).lastrowid
        conn.execute(
            "INSERT INTO story_items (story_id, item_id, role) VALUES (?, ?, 'seed')",
            (story_id, item_id),
        )
        return story_id

    return _told


def proposed(conn, seeded=(), **kwargs) -> list[str]:
    return [c.name for c in entities.suggest(conn, list(seeded), **kwargs)]


def test_a_name_recurring_in_prose_is_proposed(conn, told):
    for n in range(3):
        told(f"Launch day {n}", "The lab shipped Astra today, and people compared it.")

    found = entities.suggest(conn, [])
    assert [c.name for c in found] == ["Astra"]
    assert found[0].stories == 3
    assert found[0].titles  # the evidence a human decides from


def test_a_name_seen_in_too_few_stories_is_not(conn, told):
    for n in range(2):
        told(f"Launch day {n}", "The lab shipped Astra today.")

    assert proposed(conn) == []


def test_an_ordinary_word_that_is_sometimes_capitalised_is_not(conn, told):
    """`Learning` in a heading is not a name, and prose gives it away."""
    for n in range(3):
        told(f"Paper {n}", "We study Learning rates. learning is hard. learning helps.")

    assert proposed(conn) == []


def test_an_acronym_for_an_idea_is_not(conn, told):
    for n in range(3):
        told(f"Paper {n}", "We evaluate LLMs and one LLM-based agent on the task.")

    assert proposed(conn) == []


def test_a_seeded_entity_is_not_proposed_again(conn, told):
    for n in range(3):
        told(f"News {n}", "Yesterday OpenAI shipped an update.")

    assert proposed(conn, seeded=[OPENAI]) == []


def test_arxiv_boilerplate_is_not_a_name(conn, told):
    for n in range(3):
        told(f"Paper {n}", "arXiv:2609.1 Announce Type: new Abstract: we study things.")

    assert proposed(conn) == []
