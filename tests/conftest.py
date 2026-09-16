from __future__ import annotations

import pytest

from tributary import db as db_mod


@pytest.fixture
def conn(tmp_path):
    connection = db_mod.connect(tmp_path / "test.db")
    db_mod.migrate(connection)
    yield connection
    connection.close()


@pytest.fixture
def source_id(conn):
    cur = conn.execute(
        "INSERT INTO sources (kind, name, url) VALUES ('rss', 'Test Feed', 'https://ex.test/f')"
    )
    return cur.lastrowid
