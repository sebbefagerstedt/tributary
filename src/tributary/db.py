"""SQLite connection handling and the migration runner.

Migrations are plain .sql files in ``migrations/``, applied in filename order and
recorded in ``schema_migrations``. No ORM: the queries here are short enough that
raw SQL stays clearer than a mapping layer.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import sqlite_vec

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: Path | str) -> sqlite3.Connection:
    """Open the database with the pragmas this project assumes everywhere."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # autocommit; we manage txns
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    _load_vec(conn)
    return conn


def _load_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec, which provides the vector search used for clustering.

    Some Python builds ship without extension support; fail with a message that
    says what is missing rather than an AttributeError deep in a query.
    """
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except AttributeError as exc:
        raise RuntimeError(
            "this Python's sqlite3 was built without extension support, "
            "which sqlite-vec requires"
        ) from exc
    finally:
        with contextlib.suppress(AttributeError):
            conn.enable_load_extension(False)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Wrap a unit of work. Rolls back on any exception."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def _applied(conn: sqlite3.Connection) -> set[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  name       TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        ")"
    )
    return {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply any migrations not yet recorded. Returns the names applied.

    Transaction control lives inside the script rather than around it:
    ``executescript()`` commits any pending transaction before it runs, so an
    outer BEGIN would be discarded and a failing migration could land
    half-applied. SQLite DDL is transactional, so this makes each migration and
    its bookkeeping row commit or fail together.
    """
    done = _applied(conn)
    applied: list[str] = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if sql_file.name in done:
            continue
        name = sql_file.name.replace("'", "''")
        try:
            conn.executescript(
                "BEGIN;\n"
                f"{sql_file.read_text()}\n"
                f"INSERT INTO schema_migrations (name) VALUES ('{name}');\n"
                "COMMIT;"
            )
        except Exception:
            # executescript aborts mid-script on error, leaving the BEGIN open.
            # Without this the partial schema stays visible on the connection and
            # could be committed later by unrelated work.
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(sql_file.name)
    return applied


class ConnectionPool:
    """One connection per thread, created on first use.

    SQLite forbids sharing a connection across threads, and a web server runs
    sync handlers in a threadpool. Disabling the check instead would trade a
    loud error for silent corruption under concurrent writes; WAL mode lets
    separate connections work together properly.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._local = threading.local()

    def get(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect(self.path)
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
