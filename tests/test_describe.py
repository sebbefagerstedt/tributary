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
    found = describe.prose_summary(CARD)
    assert found.startswith("Agnes-3.0-Flash is a 7B model distilled")
    assert "four times the throughput" in found


def test_the_yaml_header_is_not_the_description():
    assert "license" not in (describe.prose_summary(CARD) or "")


def test_headings_badges_and_code_are_skipped():
    assert "#" not in (describe.prose_summary(CARD) or "")
    assert "img.shields.io" not in (describe.prose_summary(CARD) or "")


TEMPLATE = """---
license: apache-2.0
---

# Model Card for tournament-tourn_5c64e784a087074a

Users (both direct and downstream) should be made aware of the risks, biases and
limitations of the model. More information needed for further recommendations.

## Model Details

More Information Needed
"""


def test_template_boilerplate_is_not_a_description():
    """Seen live: this text reached the top of the feed. It is true of every
    model ever published, and worse than the bare title it replaced."""
    assert describe.prose_summary(TEMPLATE) is None


def test_a_card_with_no_prose_describes_nothing():
    bare = "---\nlicense: mit\n---\n\n# Model\n\n![badge](https://x.test/b.png)\n"
    assert describe.prose_summary(bare) is None


def test_an_empty_or_missing_card_is_not_an_error():
    assert describe.prose_summary("") is None
    assert describe.prose_summary(None) is None


def test_a_link_keeps_its_text_and_loses_its_url():
    card = "---\na: b\n---\n\nBuilt on [the original paper](https://arxiv.org/abs/1) "
    card += "and tuned for throughput on commodity hardware.\n"
    found = describe.prose_summary(card)
    assert "the original paper" in found
    assert "arxiv.org" not in found


def test_a_long_card_is_truncated():
    card = "---\na: b\n---\n\n" + ("word " * 400)
    assert len(describe.prose_summary(card)) <= describe.SUMMARY_LIMIT + 1


# --- choosing what to describe -----------------------------------------------

def add(conn, source_id, n, summary=None, metadata=None, body=None, url=None, kind="model"):
    return conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title, summary, body, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (source_id, f"e{n}", kind, url or f"https://e.test/{n}", f"org/Model-{n}", summary,
         body, json.dumps(metadata or {})),
    ).lastrowid


def steps(conn, **kwargs):
    """The strategies chosen for the single pending item, as (name, subject)."""
    return [(s.strategy, s.subject) for t in describe.pending(conn, **kwargs) for s in t.steps]


def test_only_items_with_nothing_to_say_are_fetched(conn, source_id):
    bare = add(conn, source_id, 1, metadata={"hf_id": "org/bare"})
    add(conn, source_id, 2, summary="Already says something.", metadata={"hf_id": "org/full"})

    found = describe.pending(conn)
    assert [t.item_id for t in found] == [bare]
    assert found[0].steps[0] == describe.Step(describe.CARD, "org/bare")


def test_an_item_with_no_hub_id_falls_back_to_its_own_page(conn, source_id):
    """It used to be undescribable. Its own page has a meta description."""
    add(conn, source_id, 1, metadata={"feed": "https://e.test/rss"}, url="https://e.test/a")
    assert steps(conn) == [(describe.PAGE, "https://e.test/a")]


def test_a_dataset_resolves_to_its_own_path(conn, source_id):
    add(conn, source_id, 1, metadata={"hf_dataset": "org/corpus"})
    assert steps(conn)[0] == (describe.CARD, "datasets/org/corpus")


def test_unusable_metadata_is_not_fatal(conn, source_id):
    add(conn, source_id, 1, metadata={})
    conn.execute("UPDATE items SET metadata = 'not json' WHERE external_id = 'e1'")
    # Unreadable metadata means no hub or repo hint, not a crash.
    assert steps(conn) == [(describe.PAGE, "https://e.test/1")]


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


# --- reading a page ----------------------------------------------------------

PAGE = """<!doctype html>
<html><head>
<title>Something</title>
<meta charset="utf-8">
<meta name="description" content="Test Blog &mdash; thoughts on things">
<meta property="og:description" content="A new scheduler cuts tail latency by
     40% on shared GPUs, by letting short requests overtake long ones.">
</head><body>
<p>Accept cookies to continue reading this article on our website.</p>
</body></html>"""


def test_the_og_description_is_preferred_over_the_site_tagline():
    found = describe.page_summary(PAGE)
    assert found.startswith("A new scheduler cuts tail latency")
    assert "Test Blog" not in found


def test_the_page_body_is_never_read():
    """The body is cookie banners and navigation. Only <meta> is trusted."""
    assert "cookies" not in (describe.page_summary(PAGE) or "")


def test_a_description_below_the_head_does_not_count():
    html = "<head><title>x</title></head><body>"
    html += '<meta property="og:description" content="Injected well after the head ends.">'
    assert describe.page_summary(html) is None


def test_single_quoted_attributes_in_any_order_are_read():
    html = "<head><meta content='Quantisation, inference speed and what actually "
    html += "fits on one card.' property='og:description'></head>"
    assert describe.page_summary(html).startswith("Quantisation, inference speed")


def test_entities_are_decoded():
    html = '<head><meta name="description" content="Weights &amp; biases, '
    html += 'explained for people who ship things."></head>'
    assert "Weights & biases" in describe.page_summary(html)


def test_a_page_with_no_description_describes_nothing():
    assert describe.page_summary("<head><title>Just a title</title></head>") is None
    assert describe.page_summary("") is None
    assert describe.page_summary(None) is None


def test_a_one_word_description_is_not_a_summary():
    """Plenty of sites set content="Home". Keeping the title is better."""
    assert describe.page_summary('<head><meta name="description" content="Home"></head>') is None


# --- choosing between strategies ---------------------------------------------

def test_a_discussion_describes_what_was_submitted_not_the_thread(conn, source_id):
    """An HN item *is* the thread; the thing worth describing is the link."""
    add(conn, source_id, 1, kind="discussion", url="https://news.ycombinator.com/item?id=1",
        metadata={"outbound_url": "https://e.test/article", "points": 120})
    assert steps(conn) == [(describe.PAGE, "https://e.test/article")]


def test_a_release_reads_its_own_notes_before_asking_github(conn, source_id):
    add(conn, source_id, 1, kind="repo", body="Some notes.",
        metadata={"github_repo": "ggml-org/llama.cpp"})
    assert steps(conn) == [
        (describe.BODY, "Some notes."),
        (describe.REPO, "ggml-org/llama.cpp"),
    ]


def test_stored_release_notes_are_used_without_a_request(conn, source_id):
    """`body` was always fetched and stored, and never reached the page."""
    notes = "This release adds speculative decoding, which roughly doubles "
    notes += "throughput on batch-one workloads.\n\n## What's Changed\n* a by @b\n"
    add(conn, source_id, 1, kind="repo", body=notes, metadata={"github_repo": "org/thing"})

    assert describe.run(conn) == {"attempted": 1, "filled": 1}
    row = conn.execute("SELECT summary FROM items WHERE external_id = 'e1'").fetchone()
    assert row["summary"].startswith("This release adds speculative decoding")


def test_a_changelog_falls_through_to_the_repo_description(conn, source_id, httpx_mock):
    """`ggml-org/llama.cpp b11003` with a list of PRs says nothing about what
    llama.cpp actually is. The repo's own blurb does."""
    add(conn, source_id, 1, kind="repo", body="## What's Changed\n* fix by @a in #1\n",
        metadata={"github_repo": "ggml-org/llama.cpp"})
    httpx_mock.add_response(json={"description": "LLM inference in C/C++"})

    assert describe.run(conn) == {"attempted": 1, "filled": 1}
    row = conn.execute("SELECT summary FROM items WHERE external_id = 'e1'").fetchone()
    assert row["summary"] == "LLM inference in C/C++"


def test_one_repo_is_asked_about_once_however_many_releases(conn, source_id, httpx_mock):
    for n in (1, 2, 3):
        add(conn, source_id, n, kind="repo", metadata={"github_repo": "org/thing"})
    httpx_mock.add_response(json={"description": "A tool that does the thing well."})

    assert describe.run(conn)["filled"] == 3
    assert len(httpx_mock.get_requests()) == 1


def test_a_non_html_link_is_not_parsed_as_one(conn, source_id, httpx_mock):
    add(conn, source_id, 1, kind="discussion", metadata={"outbound_url": "https://e.test/p.pdf"})
    httpx_mock.add_response(content=b"%PDF-1.7 ...", headers={"content-type": "application/pdf"})

    assert describe.run(conn) == {"attempted": 1, "filled": 0}


def test_a_dead_link_is_not_an_error(conn, source_id, httpx_mock):
    add(conn, source_id, 1, kind="discussion", metadata={"outbound_url": "https://e.test/gone"})
    httpx_mock.add_response(status_code=403)

    assert describe.run(conn) == {"attempted": 1, "filled": 0}
    assert describe.pending(conn) == []  # and it is not asked about again


def test_a_linked_article_is_described_by_its_own_page(conn, source_id, httpx_mock):
    add(conn, source_id, 1, kind="discussion", metadata={"outbound_url": "https://e.test/a"})
    httpx_mock.add_response(text=PAGE, headers={"content-type": "text/html; charset=utf-8"})

    assert describe.run(conn) == {"attempted": 1, "filled": 1}
    row = conn.execute(
        "SELECT summary, triage_state FROM items WHERE external_id = 'e1'"
    ).fetchone()
    assert row["summary"].startswith("A new scheduler cuts tail latency")
    assert row["triage_state"] == "pending"
