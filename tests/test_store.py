from __future__ import annotations

from datetime import UTC, datetime

from tributary.config import SourceConfig
from tributary.models import Kind, RawItem
from tributary.store import mark_fetched, record_items, source_health, sync_sources


def item(external_id="a", title="Title", **kw):
    return RawItem(
        external_id=external_id,
        kind=Kind.ARTICLE,
        url=kw.pop("url", "https://example.com/a"),
        title=title,
        published_at=kw.pop("published_at", datetime(2026, 9, 15, tzinfo=UTC)),
        **kw,
    )


def test_insert_then_refetch_is_idempotent(conn, source_id):
    first = record_items(conn, source_id, [item(), item("b", "Second")])
    assert (first.inserted, first.updated, first.unchanged) == (2, 0, 0)

    second = record_items(conn, source_id, [item(), item("b", "Second")])
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 2)


def test_upstream_edit_is_picked_up(conn, source_id):
    record_items(conn, source_id, [item()])
    result = record_items(conn, source_id, [item(title="Corrected title")])
    assert (result.inserted, result.updated, result.unchanged) == (0, 1, 0)

    row = conn.execute("SELECT title FROM items WHERE external_id = 'a'").fetchone()
    assert row["title"] == "Corrected title"


def test_update_preserves_triage_state(conn, source_id):
    """A fixed typo upstream must not send an item back through the pipeline."""
    record_items(conn, source_id, [item()])
    conn.execute("UPDATE items SET triage_state = 'kept', triage_score = 0.9")

    record_items(conn, source_id, [item(title="Edited")])

    row = conn.execute("SELECT triage_state, triage_score FROM items").fetchone()
    assert row["triage_state"] == "kept"
    assert row["triage_score"] == 0.9


def test_canonical_url_is_stored(conn, source_id):
    record_items(conn, source_id, [item(url="https://www.example.com/x/?utm_source=rss")])
    row = conn.execute("SELECT canonical_url FROM items").fetchone()
    assert row["canonical_url"] == "https://example.com/x"


def test_same_external_id_in_different_sources_stays_distinct(conn, source_id):
    other = conn.execute(
        "INSERT INTO sources (kind, name, url) VALUES ('rss', 'Other', 'https://o.test')"
    ).lastrowid
    record_items(conn, source_id, [item()])
    record_items(conn, other, [item()])
    assert conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 2


def test_sync_sources_disables_removed_sources_without_losing_items(conn):
    configs = [
        SourceConfig(kind="rss", name="Keep", url="https://keep.test"),
        SourceConfig(kind="rss", name="Drop", url="https://drop.test"),
    ]
    rows = sync_sources(conn, configs)
    assert {r.name for r in rows} == {"Keep", "Drop"}

    drop_id = next(r.id for r in rows if r.name == "Drop")
    record_items(conn, drop_id, [item()])

    rows = sync_sources(conn, configs[:1])
    assert {r.name for r in rows} == {"Keep"}

    health = {r["name"]: r for r in source_health(conn)}
    assert health["Drop"]["enabled"] == 0
    assert health["Drop"]["item_count"] == 1  # items survive the source being dropped


def test_sync_sources_updates_url_in_place(conn):
    sync_sources(conn, [SourceConfig(kind="rss", name="Feed", url="https://old.test")])
    rows = sync_sources(conn, [SourceConfig(kind="rss", name="Feed", url="https://new.test")])
    assert len(rows) == 1
    assert rows[0].url == "https://new.test"


def test_mark_fetched_records_and_then_clears_an_error(conn, source_id):
    mark_fetched(conn, source_id, error="HTTP 500")
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    assert row["last_error"] == "HTTP 500"
    assert row["last_error_at"] is not None

    mark_fetched(conn, source_id, state={"etag": "x"})
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    assert row["last_error"] is None
    assert row["last_error_at"] is None
    assert row["state"] == '{"etag": "x"}'


def test_failed_fetch_keeps_previous_state(conn, source_id):
    """A transient failure must not discard the ETag we already hold."""
    mark_fetched(conn, source_id, state={"etag": "keep-me"})
    mark_fetched(conn, source_id, error="timed out")
    row = conn.execute("SELECT state FROM sources WHERE id = ?", (source_id,)).fetchone()
    assert row["state"] == '{"etag": "keep-me"}'


def test_empty_item_list_is_a_no_op(conn, source_id):
    assert record_items(conn, source_id, []).total == 0
