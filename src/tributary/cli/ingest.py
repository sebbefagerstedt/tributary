"""Bringing material in: fetching it, describing it, embedding it,
and letting the old go."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from tributary import db as db_mod
from tributary import (
    describe,
    embeddings,
    store,
)
from tributary.cli.common import ConfigOpt, app, console, err, open_config
from tributary.pipeline import fetch_all
from tributary.text import truncate

PANEL = "Pipeline"


@app.command(rich_help_panel=PANEL)
def fetch(
    config: ConfigOpt = None,
    source: Annotated[
        str | None, typer.Option("--source", "-s", help="Only sources matching this substring.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Fetch and report without writing.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Ignore cached validators and re-parse everything."),
    ] = False,
) -> None:
    """Fetch all configured sources."""
    cfg, conn = open_config(config)
    if not cfg.sources:
        err.print("[yellow]No sources configured.[/] Run `trib init` or edit your config.")
        raise typer.Exit(1)

    outcomes = fetch_all(conn, cfg.sources, only=source, dry_run=dry_run, force=force)
    if not outcomes:
        err.print(f"[yellow]No sources matched[/] {source!r}")
        raise typer.Exit(1)

    table = Table(title="Dry run — nothing written" if dry_run else None, box=None, pad_edge=False)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("New", justify="right")
    table.add_column("Updated", justify="right")
    table.add_column("Same", justify="right", style="dim")
    table.add_column("")

    new = updated = unchanged = failed = 0
    for outcome in outcomes:
        if not outcome.ok:
            failed += 1
            table.add_row(outcome.source, "-", "-", "-", f"[red]{truncate(outcome.error, 70)}[/]")
            continue
        if dry_run:
            count = len(outcome.items or [])
            new += count
            table.add_row(outcome.source, str(count), "-", "-", "[dim]fetched[/]")
        else:
            new += outcome.result.inserted
            updated += outcome.result.updated
            unchanged += outcome.result.unchanged
            table.add_row(
                outcome.source,
                str(outcome.result.inserted),
                str(outcome.result.updated),
                str(outcome.result.unchanged),
                "[green]ok[/]",
            )
    console.print(table)
    plural = "source" if len(outcomes) == 1 else "sources"
    summary = (
        f"\n{new} new, {updated} updated, {unchanged} unchanged "
        f"across {len(outcomes)} {plural}"
    )
    if failed:
        summary += f", [red]{failed} failed[/]"
    console.print(summary)


@app.command(rich_help_panel=PANEL, name="describe")
def describe_cmd(
    config: ConfigOpt = None,
    limit: Annotated[
        int, typer.Option("--limit", help="How many items to fetch cards for.")
    ] = describe.DEFAULT_LIMIT,
    reset: Annotated[
        bool, typer.Option("--reset", help="Retry every item, including past failures.")
    ] = False,
) -> None:
    """Fetch descriptions for items that arrived as a bare title."""
    _, conn = open_config(config)
    if reset:
        describe.reset(conn)
        console.print("[yellow]Cleared the record of what has been attempted.[/]")

    result = describe.run(conn, limit=limit)
    if not result["attempted"]:
        console.print("[green]Nothing missing prose or art.[/]")
        return
    console.print(
        f"[green]{result['filled']} described[/] and [green]{result['illustrated']} "
        f"illustrated[/] of {result['attempted']} attempted — the described ones are "
        f"re-embedded and re-triaged on the next run, a picture changes no vector"
    )


@app.command(rich_help_panel=PANEL)
def embed(
    config: ConfigOpt = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n")] = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Discard all vectors and start over.")
    ] = False,
) -> None:
    """Embed items that have no vector, or whose text has changed."""
    cfg, conn = open_config(config)

    if reset:
        conn.execute("DELETE FROM item_vectors")
        conn.execute("UPDATE items SET embedded_hash = NULL")
        conn.execute("DELETE FROM meta WHERE key = 'embedding_model'")
        console.print("[yellow]Cleared all vectors.[/]")

    embeddings.check_model(conn)
    rows = embeddings.pending(conn, limit=limit)
    if not rows:
        console.print("[green]Everything is embedded.[/]")
        return

    console.print(f"Embedding {len(rows)} items…")
    written = 0
    with typer.progressbar(range(0, len(rows), embeddings.BATCH_SIZE), label="  batches") as bar:
        for start in bar:
            batch = rows[start : start + embeddings.BATCH_SIZE]
            vectors = embeddings.embed([embeddings.embedding_text(r) for r in batch])
            with db_mod.transaction(conn):
                written += embeddings.store(conn, batch, vectors)
    console.print(f"[green]Embedded {written} items.[/]")


@app.command(rich_help_panel=PANEL)
def prune(
    config: ConfigOpt = None,
    days: Annotated[int, typer.Option("--days", "-d", help="Keep items newer than this.")] = 90,
    include_saved: Annotated[
        bool, typer.Option("--include-saved", help="Also delete saved stories.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation.")] = False,
) -> None:
    """Delete old items to keep the database small."""
    cfg, conn = open_config(config)
    doomed = conn.execute(
        "SELECT COUNT(*) c FROM items WHERE COALESCE(published_at, fetched_at) < "
        "datetime('now', ?)",
        (f"-{days} days",),
    ).fetchone()["c"]
    if not doomed:
        console.print(f"[green]Nothing older than {days} days.[/]")
        return

    if not yes:
        console.print(f"[yellow]About to delete {doomed} items older than {days} days.[/]")
        if not typer.confirm("Continue?"):
            raise typer.Abort()

    before = Path(cfg.db_path).stat().st_size
    result = store.prune(conn, days=days, keep_saved=not include_saved)
    store.vacuum(conn)
    after = Path(cfg.db_path).stat().st_size
    console.print(
        f"[green]Deleted {result['items']} items[/] and {result['stories']} empty stories — "
        f"database {before / 1e6:.1f} MB → {after / 1e6:.1f} MB"
    )
