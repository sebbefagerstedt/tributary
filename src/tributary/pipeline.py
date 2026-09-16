"""Stage 1: fetch.

One source failing must never take down a run — a dead feed should show up as a
health row, not as a missing morning.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from tributary.config import SourceConfig
from tributary.models import RawItem
from tributary.sources import FetchError, build
from tributary.store import IngestResult, SourceRow, mark_fetched, record_items, sync_sources


@dataclass(slots=True)
class FetchOutcome:
    source: str
    kind: str
    result: IngestResult | None = None
    error: str | None = None
    items: list[RawItem] | None = None  # populated on dry runs only

    @property
    def ok(self) -> bool:
        return self.error is None


def fetch_source(
    conn: sqlite3.Connection,
    row: SourceRow,
    config: SourceConfig,
    dry_run: bool = False,
    force: bool = False,
) -> FetchOutcome:
    try:
        adapter = build(config)
        # Dropping the validators makes the server send a body instead of a 304,
        # so changed parsing logic reaches items that have not themselves changed.
        items, state = adapter.fetch({} if force else row.state)
    except (FetchError, ValueError) as exc:
        if not dry_run:
            mark_fetched(conn, row.id, error=str(exc))
        return FetchOutcome(source=row.name, kind=row.kind, error=str(exc))
    except Exception as exc:  # an adapter bug shouldn't abort the other sources
        message = f"{type(exc).__name__}: {exc}"
        if not dry_run:
            mark_fetched(conn, row.id, error=message)
        return FetchOutcome(source=row.name, kind=row.kind, error=message)

    if dry_run:
        return FetchOutcome(
            source=row.name, kind=row.kind, result=IngestResult(), items=items
        )

    result = record_items(conn, row.id, items)
    mark_fetched(conn, row.id, state=state)
    return FetchOutcome(source=row.name, kind=row.kind, result=result)


def fetch_all(
    conn: sqlite3.Connection,
    configs: list[SourceConfig],
    only: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[FetchOutcome]:
    rows = sync_sources(conn, configs)
    by_key = {(c.kind, c.name): c for c in configs}

    outcomes = []
    for row in rows:
        if only and only.lower() not in row.name.lower():
            continue
        config = by_key.get((row.kind, row.name))
        if config is None:  # disabled between sync and now; nothing to fetch
            continue
        outcomes.append(fetch_source(conn, row, config, dry_run=dry_run, force=force))
    return outcomes
