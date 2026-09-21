from __future__ import annotations

import json

import numpy as np
import sqlite_vec

from tributary import cluster, embeddings, export


def unit(*values) -> bytes:
    v = np.zeros(embeddings.DIMENSION, dtype=np.float32)
    v[: len(values)] = values
    v /= np.linalg.norm(v)
    return sqlite_vec.serialize_float32(v.tolist())


def seed(conn, source_id):
    def add(n, title, kind="article", vector=(1.0,), arxiv=None):
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, summary, "
            "published_at, triage_state, triage_score, content_hash, embedded_hash) "
            "VALUES (?, ?, ?, ?, ?, 'A summary.', datetime('now', '-1 day'), "
            "'kept', 0.8, 'h', 'h')",
            (source_id, f"e{n}", kind, f"https://e.test/{n}", title),
        ).lastrowid
        conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                     (item_id, unit(*vector)))
        if arxiv:
            conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, 'arxiv', ?)",
                         (item_id, arxiv))

    add(1, "A paper", kind="paper", vector=(1.0, 0.0), arxiv="2609.1")
    add(2, "Coverage of it", vector=(0.0, 1.0), arxiv="2609.1")
    add(3, "Unrelated", kind="discussion", vector=(0.0, 0.0, 1.0))
    cluster.run(conn)


def test_bundle_embeds_every_story_s_items(conn, source_id):
    """One request has to be enough: there is no server to ask for more."""
    seed(conn, source_id)
    bundle = export.build_bundle(conn)

    assert bundle["stories"]
    for story in bundle["stories"]:
        assert "items" in story
        assert len(story["items"]) == story["item_count"]


def test_bundle_carries_the_fields_the_page_renders(conn, source_id):
    seed(conn, source_id)
    story = export.build_bundle(conn)["stories"][0]
    for field in ("story_id", "title", "kind", "source", "signal", "score", "published_at"):
        assert field in story


def test_bundle_reports_status_and_generation_time(conn, source_id):
    seed(conn, source_id)
    bundle = export.build_bundle(conn)
    assert bundle["generated_at"].endswith("Z")
    assert bundle["status"]["kept"] == 3
    assert bundle["status"]["broken_sources"] == []


def test_bundle_surfaces_a_broken_source(conn, source_id):
    seed(conn, source_id)
    conn.execute("UPDATE sources SET last_error = 'HTTP 404'")
    broken = export.build_bundle(conn)["status"]["broken_sources"]
    assert broken[0]["error"] == "HTTP 404"


def test_write_site_produces_a_self_contained_directory(conn, source_id, tmp_path):
    seed(conn, source_id)
    result = export.write_site(conn, tmp_path / "site")
    site = tmp_path / "site"

    for name in ("index.html", "manifest.json", "sw.js", "icon.svg", "data.json"):
        assert (site / name).is_file(), name
    # Without this GitHub Pages runs the output through Jekyll.
    assert (site / ".nojekyll").is_file()
    assert result["stories"] == len(json.loads((site / "data.json").read_text())["stories"])


def test_site_assets_use_relative_paths(conn, source_id, tmp_path):
    """GitHub Pages serves a project repo under /<repo>/, not at the root."""
    seed(conn, source_id)
    export.write_site(conn, tmp_path / "site")
    site = tmp_path / "site"

    page = (site / "index.html").read_text()
    assert 'href="manifest.json"' in page
    assert "fetch('data.json'" in page

    manifest = json.loads((site / "manifest.json").read_text())
    assert manifest["start_url"] == "./"
    assert manifest["icons"][0]["src"].startswith("./")

    worker = (site / "sw.js").read_text()
    assert "'./index.html'" in worker


def test_the_page_opens_a_subject_and_offers_no_kind_row(conn, source_id, tmp_path):
    """Both halves of the owner's call on 2026-09-21.

    Tapping a subject has to open it -- it used to clear the scope and land on
    the feed, which for anyone following nothing is an empty one -- and the
    facet row ("code, agents, multimodal") is gone from the UI. Facets are
    still labelled and still in the bundle; nothing reads them.
    """
    seed(conn, source_id)
    export.write_site(conn, tmp_path / "site")
    page = (tmp_path / "site" / "index.html").read_text()

    assert 'id="subject-sheet"' in page
    assert "data-subject=" in page and "data-see-feed=" in page
    # The attributes that navigated nowhere, and the row that has gone with them.
    for gone in ("data-to-feed", "data-goto", 'id="facetfilters"', "data-facet="):
        assert gone not in page, gone


def test_the_service_worker_never_caches_the_feed_data(conn, source_id, tmp_path):
    """A stale feed is worse than an honest error."""
    seed(conn, source_id)
    export.write_site(conn, tmp_path / "site")
    worker = (tmp_path / "site" / "sw.js").read_text()
    assert "data.json" in worker and "isData" in worker


def test_bundle_json_is_serialisable(conn, source_id):
    seed(conn, source_id)
    json.dumps(export.build_bundle(conn))


def test_limit_caps_the_bundle(conn, source_id):
    seed(conn, source_id)
    assert len(export.build_bundle(conn, limit=1)["stories"]) == 1


# --- engagement --------------------------------------------------------------
# Metadata is whatever an adapter chose to store, so this reads a blob no schema
# guards.


def test_adapters_name_votes_differently_and_the_page_should_not_care():
    assert export._engagement(json.dumps({"points": 892})) == {"points": 892}
    assert export._engagement(json.dumps({"upvotes": 41})) == {"points": 41}
    # A hub like is the closest thing a model has to a vote, and without this a
    # *trending* model reached the page showing no reaction at all.
    assert export._engagement(json.dumps({"likes": 2807})) == {"points": 2807}


def test_counts_travel_together():
    found = export._engagement(json.dumps({"points": 892, "num_comments": 214}))
    assert found == {"points": 892, "comments": 214}


def test_an_item_that_carries_no_counts_has_no_engagement():
    assert export._engagement(json.dumps({"feed": "https://e.test/rss"})) is None
    assert export._engagement("{}") is None
    assert export._engagement(None) is None


def test_unusable_metadata_is_not_fatal():
    """One adapter storing junk must not take the whole bundle down with it."""
    assert export._engagement("not json") is None
    assert export._engagement("[1, 2]") is None
    assert export._engagement(json.dumps({"points": "many"})) is None


def test_zero_points_is_not_worth_a_badge():
    assert export._engagement(json.dumps({"points": 0, "num_comments": 0})) is None


def seed_threads(conn, source_id, *metadata, summary="A summary."):
    """One story, joined by a shared arXiv id, with a thread per metadata blob."""
    for n, blob in enumerate(metadata, start=1):
        item_id = conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title, summary, "
            "published_at, metadata, triage_state, triage_score, content_hash, embedded_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now', '-1 day'), ?, 'kept', 0.8, 'h', 'h')",
            (source_id, f"m{n}", "paper" if n == 1 else "discussion",
             f"https://e.test/m{n}", f"Thread {n}", summary, json.dumps(blob)),
        ).lastrowid
        conn.execute("INSERT INTO item_vectors (item_id, embedding) VALUES (?, ?)",
                     (item_id, unit(1.0)))
        conn.execute("INSERT INTO identifiers (item_id, type, value) VALUES (?, 'arxiv', ?)",
                     (item_id, "2609.9"))
    cluster.run(conn)


def test_the_loudest_thread_speaks_for_the_story(conn, source_id):
    """Two quiet threads are not the signal that one big argument is."""
    seed_threads(conn, source_id, {}, {"points": 120, "num_comments": 8},
                 {"points": 892, "num_comments": 214})

    story = export.build_bundle(conn)["stories"][0]
    assert story["engagement"] == {"points": 892, "comments": 214}


def test_a_story_nobody_argued_about_reports_none(conn, source_id):
    seed_threads(conn, source_id, {})
    assert export.build_bundle(conn)["stories"][0]["engagement"] is None


def test_items_carry_their_own_blurb_and_counts(conn, source_id):
    seed_threads(conn, source_id, {}, {"points": 5}, summary="x" * 400)

    items = export.build_bundle(conn)["stories"][0]["items"]
    assert all(len(item["summary"]) <= export.ITEM_SUMMARY_LIMIT + 1 for item in items)
    assert [i["engagement"] for i in items if i["kind"] == "discussion"] == [{"points": 5}]


def test_bundle_is_newest_first_and_carries_both_dates(conn, source_id):
    """The page's feed is chronological; Trending re-sorts the same list."""
    seed(conn, source_id)
    stories = export.build_bundle(conn)["stories"]

    dates = [s["published_at"] or "" for s in stories]
    assert dates == sorted(dates, reverse=True)
    for story in stories:
        assert "last_activity" in story   # "active 2h ago" on the card
        assert "score" in story           # what Trending orders by


def test_bundle_carries_what_the_digest_counts(conn, source_id):
    """Every story needs a topic label, or a subject silently loses stories."""
    seed(conn, source_id)
    bundle = export.build_bundle(conn)
    assert all("topics" in s and "entities" in s for s in bundle["stories"])


def test_the_bundle_names_every_topic_in_the_spine(conn, source_id):
    """A followed subject with nothing in the bundle still has to be nameable.

    Stories carry their own labels, so the page can name whatever it shows. A
    follow is a stored slug, and one whose subject has gone quiet has no story
    to carry its name -- so it could not be listed, and therefore could not be
    unfollowed, while still deciding what the feed held.
    """
    from tributary.config import TopicConfig

    seed(conn, source_id)
    spine = [
        TopicConfig(slug="safety", name="Safety & security", description="d"),
        TopicConfig(slug="misuse", name="Misuse", description="d", parent="safety"),
    ]
    bundle = export.build_bundle(conn, spine=spine)

    assert bundle["spine"] == [
        {"slug": "safety", "name": "Safety & security", "parent": None, "parent_name": None},
        {"slug": "misuse", "name": "Misuse", "parent": "safety",
         "parent_name": "Safety & security"},
    ]


def test_a_bundle_built_without_a_spine_still_has_the_key(conn, source_id):
    """The page reads `spine` unconditionally, so it is never absent."""
    seed(conn, source_id)
    assert export.build_bundle(conn)["spine"] == []
