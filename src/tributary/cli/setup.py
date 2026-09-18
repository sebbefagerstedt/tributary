"""Getting a config and a database, and seeing the state of both."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from tributary import cluster as cluster_mod
from tributary import config as config_mod
from tributary import db as db_mod
from tributary import (
    store,
    triage,
)
from tributary.cli.common import ConfigOpt, app, console, open_config

PANEL = "Setup"


def sample_config() -> str:
    """The config a new install starts from.

    A file in the package rather than a string in the code, because the string
    version drifted: it was still pointing MarkTechPost at a dead URL and had no
    topics, facets or entities at all, so a fresh install could not label
    anything. `test_cli` now pins this file to the repository's own config.
    """
    return resources.files("tributary").joinpath("sample_config.toml").read_text()


@app.command(rich_help_panel=PANEL)
def init(
    config: ConfigOpt = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing config.")] = False,
) -> None:
    """Create the database and a starter config file."""
    target = config or Path.cwd() / "config.toml"
    if target.exists() and not force:
        console.print(f"[yellow]Config already exists:[/] {target}  (use --force to overwrite)")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(sample_config())
        console.print(f"[green]Wrote config:[/] {target}")

    cfg = config_mod.load(target)
    conn = db_mod.connect(cfg.db_path)
    applied = db_mod.migrate(conn)
    console.print(f"[green]Database ready:[/] {cfg.db_path}")
    if applied:
        console.print(f"  applied migrations: {', '.join(applied)}")
    console.print(f"  sources configured: {len(cfg.sources)}")


@app.command(rich_help_panel=PANEL)
def migrate(config: ConfigOpt = None) -> None:
    """Apply any pending database migrations."""
    cfg = config_mod.load(config)
    conn = db_mod.connect(cfg.db_path)
    applied = db_mod.migrate(conn)
    console.print(
        f"[green]Applied {len(applied)}:[/] {', '.join(applied)}" if applied else "Already current."
    )


@app.command(rich_help_panel=PANEL)
def status(config: ConfigOpt = None) -> None:
    """Where everything is and how much of it there is."""
    cfg, conn = open_config(config)
    size = Path(cfg.db_path).stat().st_size if Path(cfg.db_path).exists() else 0
    items = triage.stats(conn)
    stories = cluster_mod.stats(conn)
    health = store.source_health(conn)
    enabled = [row for row in health if row["enabled"]]
    failing = [row["name"] for row in enabled if row["last_error"]]
    fetched = max((row["last_fetched_at"] or "" for row in enabled), default="")
    labelled = conn.execute("SELECT COUNT(DISTINCT story_id) c FROM story_topics").fetchone()["c"]

    table = Table(box=None, pad_edge=False, show_header=False)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("config", str(cfg.path or "none — using defaults"))
    table.add_row("database", f"{cfg.db_path}  [dim]({size / 1e6:.1f} MB)[/]")
    table.add_row("last fetch", fetched[:16].replace("T", " ") or "never")
    table.add_row(
        "items",
        f"{items['kept']} kept, {items['rejected']} dropped, {items['pending']} pending",
    )
    table.add_row("stories", f"{stories['stories']}, {labelled} with a topic")
    # The sources table only learns about a source on its first fetch, so a
    # config edit shows up here as a gap between the two numbers until then.
    configured = sum(1 for source in cfg.sources if source.enabled)
    notes = []
    if configured > len(enabled):
        notes.append(f"{configured - len(enabled)} not fetched yet")
    if failing:
        notes.append(f"[red]{len(failing)} failing:[/] {', '.join(failing)}")
    else:
        notes.append("none failing")
    table.add_row("sources", f"{configured} configured, " + ", ".join(notes))
    table.add_row(
        "labels",
        f"{len(cfg.topics.leaves())} topics, {len(cfg.facets)} facets, "
        f"{len(cfg.entities)} entities",
    )
    console.print(table)
