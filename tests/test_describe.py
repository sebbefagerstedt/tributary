from __future__ import annotations

import json

from tributary import describe

# A model card as the hub actually serves one: YAML header, title, a wall of
# badges, then finally a sentence saying what the thing is.
CARD = """---
license: apache-2.0
tags:
- text-generation
---

# Agnes-3.0-Flash

[![Paper](https://img.shields.io/badge/paper-arxiv-red)](https://arxiv.org/abs/2609.1)
![banner](https://cdn.test/banner.png)

Agnes-3.0-Flash is a 7B model distilled for low-latency serving, trading a
little accuracy on long-context tasks for roughly four times the throughput.

## Usage

```python
print("hello")
```
"""


# --- reading a card ----------------------------------------------------------

def test_the_first_real_sentence_wins():
    found = describe.card_summary(CARD)
    assert found.startswith("Agnes-3.0-Flash is a 7B model distilled")
    assert "four times the throughput" in found


def test_the_yaml_header_is_not_the_description():
    assert "license" not in (describe.card_summary(CARD) or "")


def test_headings_badges_and_code_are_skipped():
    assert "#" not in (describe.card_summary(CARD) or "")
    assert "img.shields.io" not in (describe.card_summary(CARD) or "")


def test_a_card_with_no_prose_describes_nothing():
    bare = "---\nlicense: mit\n---\n\n# Model\n\n![badge](https://x.test/b.png)\n"
    assert describe.card_summary(bare) is None


def test_an_empty_or_missing_card_is_not_an_error():
    assert describe.card_summary("") is None
    assert describe.card_summary(None) is None


def test_a_link_keeps_its_text_and_loses_its_url():
    card = "---\na: b\n---\n\nBuilt on [the original paper](https://arxiv.org/abs/1) "
    card += "and tuned for throughput on commodity hardware.\n"
    found = describe.card_summary(card)
    assert "the original paper" in found
    assert "arxiv.org" not in found


def test_a_long_card_is_truncated():
    card = "---\na: b\n---\n\n" + ("word " * 400)
    assert len(describe.card_summary(card)) <= describe.SUMMARY_LIMIT + 1


# --- choosing what to describe -----------------------------------------------

def add(conn, source_id, n, summary=None, metadata=None):
    return conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, summary, metadata) "
        "VALUES (?, ?, 'model', ?, ?, ?, ?)",
        (source_id, f"e{n}", f"https://e.test/{n}", f"org/Model-{n}", summary,
         json.dumps(metadata or {})),
    ).lastrowid


def test_only_items_with_nothing_to_say_are_fetched(conn, source_id):
    bare = add(conn, source_id, 1, metadata={"hf_id": "org/bare"})
    add(conn, source_id, 2, summary="Already says something.", metadata={"hf_id": "org/full"})

    assert describe.pending(conn) == [(bare, "org/bare")]


def test_an_item_with_no_hub_id_cannot_be_described(conn, source_id):
    add(conn, source_id, 1, metadata={"feed": "https://e.test/rss"})
    assert describe.pending(conn) == []


def test_a_dataset_resolves_to_its_own_path(conn, source_id):
    item = add(conn, source_id, 1, metadata={"hf_dataset": "org/corpus"})
    assert describe.pending(conn) == [(item, "datasets/org/corpus")]


def test_unusable_metadata_is_skipped_not_fatal(conn, source_id):
    add(conn, source_id, 1, metadata={})
    conn.execute("UPDATE items SET metadata = 'not json' WHERE external_id = 'e1'")
    assert describe.pending(conn) == []


# --- the run -----------------------------------------------------------------

def test_a_described_item_is_reopened_for_judging(conn, source_id, httpx_mock):
    """It was rejected on a bare name; there is more to go on now."""
    item = add(conn, source_id, 1, metadata={"hf_id": "org/bare"})
    conn.execute(
        "UPDATE items SET triage_state = 'rejected', triage_score = 0.2, embedded_hash = 'h' "
        "WHERE id = ?",
        (item,),
    )
    httpx_mock.add_response(text=CARD)

    assert describe.run(conn) == {"attempted": 1, "filled": 1}
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item,)).fetchone()
    assert row["summary"].startswith("Agnes-3.0-Flash is a 7B model")
    assert row["triage_state"] == "pending"
    assert row["embedded_hash"] is None


def test_an_item_with_no_card_is_not_asked_about_twice(conn, source_id, httpx_mock):
    add(conn, source_id, 1, metadata={"hf_id": "org/gone"})
    httpx_mock.add_response(status_code=404)

    assert describe.run(conn) == {"attempted": 1, "filled": 0}
    assert describe.pending(conn) == []  # marked, so the next run skips it


def test_a_described_item_is_not_fetched_again(conn, source_id, httpx_mock):
    add(conn, source_id, 1, metadata={"hf_id": "org/bare"})
    httpx_mock.add_response(text=CARD)
    describe.run(conn)

    assert describe.run(conn) == {"attempted": 0, "filled": 0}


def test_reset_allows_a_second_attempt(conn, source_id, httpx_mock):
    add(conn, source_id, 1, metadata={"hf_id": "org/gone"})
    httpx_mock.add_response(status_code=404)
    describe.run(conn)

    describe.reset(conn)
    assert len(describe.pending(conn)) == 1


def test_the_limit_caps_requests_per_run(conn, source_id):
    for n in range(5):
        add(conn, source_id, n, metadata={"hf_id": f"org/m{n}"})
    assert len(describe.pending(conn, limit=2)) == 2
