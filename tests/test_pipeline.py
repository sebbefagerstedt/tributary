from __future__ import annotations

import pytest

from tributary.config import SourceConfig
from tributary.models import Kind, RawItem
from tributary.pipeline import fetch_all
from tributary.sources.base import REGISTRY, FetchError, Source


@pytest.fixture
def fake_sources():
    """Register throwaway adapters, then restore the registry."""
    original = dict(REGISTRY)

    class Good(Source):
        kind = "good"

        def fetch(self, state):
            return [
                RawItem(
                    external_id=f"{self.name}-1",
                    kind=Kind.ARTICLE,
                    url=f"https://e.test/{self.name}",
                    title="Fine",
                )
            ], {"cursor": 1}

    class Broken(Source):
        kind = "broken"

        def fetch(self, state):
            raise FetchError("upstream is down")

    class Buggy(Source):
        kind = "buggy"

        def fetch(self, state):
            raise TypeError("adapter bug")

    REGISTRY.update({"good": Good, "broken": Broken, "buggy": Buggy})
    yield
    REGISTRY.clear()
    REGISTRY.update(original)


CONFIGS = [
    SourceConfig(kind="good", name="Alpha"),
    SourceConfig(kind="broken", name="Beta"),
    SourceConfig(kind="buggy", name="Gamma"),
    SourceConfig(kind="good", name="Delta"),
]


def test_one_failing_source_does_not_stop_the_others(conn, fake_sources):
    outcomes = {o.source: o for o in fetch_all(conn, CONFIGS)}

    assert outcomes["Alpha"].ok and outcomes["Alpha"].result.inserted == 1
    assert outcomes["Delta"].ok and outcomes["Delta"].result.inserted == 1
    assert not outcomes["Beta"].ok
    assert "upstream is down" in outcomes["Beta"].error


def test_an_adapter_bug_is_contained_and_labelled(conn, fake_sources):
    """An unexpected exception must be caught too, not just declared FetchErrors."""
    outcomes = {o.source: o for o in fetch_all(conn, CONFIGS)}
    assert not outcomes["Gamma"].ok
    assert outcomes["Gamma"].error == "TypeError: adapter bug"


def test_failures_are_recorded_against_the_source(conn, fake_sources):
    fetch_all(conn, CONFIGS)
    rows = {r["name"]: r for r in conn.execute("SELECT name, last_error, state FROM sources")}
    assert rows["Beta"]["last_error"] == "upstream is down"
    assert rows["Alpha"]["last_error"] is None
    assert rows["Alpha"]["state"] == '{"cursor": 1}'


def test_dry_run_writes_nothing(conn, fake_sources):
    outcomes = fetch_all(conn, CONFIGS, dry_run=True)
    assert conn.execute("SELECT COUNT(*) c FROM items").fetchone()["c"] == 0

    by_name = {o.source: o for o in outcomes}
    assert len(by_name["Alpha"].items) == 1
    assert conn.execute(
        "SELECT COUNT(*) c FROM sources WHERE last_fetched_at IS NOT NULL"
    ).fetchone()["c"] == 0


def test_only_filter_selects_by_substring(conn, fake_sources):
    outcomes = fetch_all(conn, CONFIGS, only="alph")  # case-insensitive
    assert [o.source for o in outcomes] == ["Alpha"]


def test_unknown_source_kind_is_reported_not_raised(conn):
    outcomes = fetch_all(conn, [SourceConfig(kind="nope", name="Mystery")])
    assert not outcomes[0].ok
    assert "unknown source kind" in outcomes[0].error
