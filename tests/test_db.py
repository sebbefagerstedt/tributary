from __future__ import annotations

import sqlite3

import pytest

from tributary import db as db_mod


def test_migrate_is_idempotent(tmp_path):
    conn = db_mod.connect(tmp_path / "t.db")
    first = db_mod.migrate(conn)
    assert first  # something was applied
    assert db_mod.migrate(conn) == []  # nothing left to do


def test_migrations_are_recorded(tmp_path):
    conn = db_mod.connect(tmp_path / "t.db")
    applied = db_mod.migrate(conn)
    recorded = [r["name"] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert recorded == sorted(applied)


def test_foreign_keys_are_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute(
            "INSERT INTO items (source_id, external_id, kind, url, title) "
            "VALUES (9999, 'x', 'article', 'https://e.test', 'T')"
        )


def test_deleting_a_source_cascades_to_its_items(conn, source_id):
    conn.execute(
        "INSERT INTO items (source_id, external_id, kind, url, title) "
        "VALUES (?, 'x', 'article', 'https://e.test', 'T')",
        (source_id,),
    )
    conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    assert conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 0


def test_failed_migration_leaves_no_partial_schema(tmp_path, monkeypatch):
    """A migration and its bookkeeping row must commit or fail together."""
    bad = tmp_path / "migrations"
    bad.mkdir()
    (bad / "001_ok.sql").write_text("CREATE TABLE good (id INTEGER PRIMARY KEY);")
    (bad / "002_bad.sql").write_text(
        "CREATE TABLE half (id INTEGER PRIMARY KEY);\nCREATE TABLE half (nope);"
    )
    monkeypatch.setattr(db_mod, "MIGRATIONS_DIR", bad)

    conn = db_mod.connect(tmp_path / "t.db")
    with pytest.raises(sqlite3.OperationalError):
        db_mod.migrate(conn)

    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "good" in tables      # the first migration committed
    assert "half" not in tables  # the second rolled back entirely
    recorded = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
    assert recorded == {"001_ok.sql"}
