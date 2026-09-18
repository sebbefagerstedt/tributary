"""Looking at what is in the database, from the terminal."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from tributary import feed as feed_mod
from tributary import (
    store,
)
from tributary.cli.common import ConfigOpt, app, console, err, open_config
from tributary.text import truncate

PANEL = "Reading"


@app.command(rich_help_panel=PANEL, name="list")
def list_items(
    config: ConfigOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 25,
    state: Annotated[
        str | None,
        typer.Option("--state", help="Filter by triage state: kept, rejected or pending."),
    ] = None,
    ids: Annotated[bool, typer.Option("--ids", help="Show item ids (for `trib explain`).")] = False,
) -> None:
    """List the most recent items."""
    _, conn = open_config(config)
    rows = store.recent_items(conn, limit=limit, state=state)
    if not rows:
        console.print("[yellow]No items yet.[/] Run `trib fetch`.")
        return

    table = Table(box=None, pad_edge=False)
    if ids:
        table.add_column("Id", justify="right", style="dim")
    table.add_column("When", style="dim", no_wrap=True)
    table.add_column("Source", style="cyan", no_wrap=True)
    if state is None:
        table.add_column("", no_wrap=True)
    table.add_column("Title")

    marks = {"kept": "[green]+[/]", "rejected": "[red]-[/]", "pending": "[dim]?[/]"}
    for row in rows:
        cells = []
        if ids:
            cells.append(str(row["id"]))
        cells.append((row["published_at"] or "")[:10] or "—")
        cells.append(truncate(row["source_name"], 20))
        if state is None:
            cells.append(marks.get(row["triage_state"], " "))
        cells.append(truncate(row["title"], 84))
        table.add_row(*cells)
    console.print(table)


@app.command(rich_help_panel=PANEL)
def sources(config: ConfigOpt = None) -> None:
    """Show per-source health: item counts, last fetch, last error."""
    _, conn = open_config(config)
    rows = store.source_health(conn)
    if not rows:
        console.print("[yellow]No sources yet.[/] Run `trib init`.")
        return

    table = Table(box=None, pad_edge=False)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Kind", style="dim")
    table.add_column("Items", justify="right")
    table.add_column("Newest", style="dim", no_wrap=True)
    table.add_column("Status")
    for row in rows:
        if not row["enabled"]:
            status = "[dim]disabled[/]"
        elif row["last_error"]:
            status = f"[red]{truncate(row['last_error'], 50)}[/]"
        elif row["last_fetched_at"]:
            status = "[green]ok[/]"
        else:
            status = "[dim]never fetched[/]"
        table.add_row(
            truncate(row["name"], 26),
            row["kind"],
            str(row["item_count"]),
            (row["newest"] or "")[:10] or "—",
            status,
        )
    console.print(table)


@app.command(rich_help_panel=PANEL, name="feed")
def feed_cmd(
    config: ConfigOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    days: Annotated[
        int | None, typer.Option("--days", "-d", help="Only stories active in the last N days.")
    ] = None,
    unseen: Annotated[
        bool, typer.Option("--unseen", help="Hide stories already shown.")
    ] = False,
    mark: Annotated[
        bool, typer.Option("--mark", help="Record these stories as seen.")
    ] = False,
) -> None:
    """The ranked feed. This is the product."""
    _, conn = open_config(config)
    cards = feed_mod.build(conn, limit=limit, days=days, include_seen=not unseen)
    if not cards:
        console.print("[yellow]Nothing to show.[/] Run `trib run` first.")
        return

    badges = {
        "paper": "[magenta]paper[/]", "model": "[blue]model[/]", "repo": "[yellow]repo[/]",
        "video": "[red]video[/]", "discussion": "[cyan]talk[/]", "article": "[green]news[/]",
    }
    for card in cards:
        when = (card.published_at or "")[:10] or "—"
        badge = badges.get(card.kind, card.kind)
        console.print()
        console.print(f"[dim]{card.story_id:>5}[/] {badge}  [bold]{card.title}[/]")
        if card.summary:
            console.print(f"       [white]{truncate(card.summary, 150)}[/]")
        signal = card.signal()
        trailer = f"       [dim]{when} · {card.source}"
        if signal:
            trailer += f" · {signal}"
        console.print(trailer + f" · {card.score:.3f}[/]")

    console.print(f"\n[dim]{len(cards)} stories. `trib story <id>` to drill in.[/]")
    if mark:
        feed_mod.mark_seen(conn, [c.story_id for c in cards])
        console.print("[dim]Marked as seen.[/]")


@app.command(rich_help_panel=PANEL)
def story(
    story_id: Annotated[int, typer.Argument(help="Story id, as shown in the feed.")],
    config: ConfigOpt = None,
) -> None:
    """Everything attached to one story."""
    _, conn = open_config(config)
    found = feed_mod.detail(conn, story_id)
    if found is None:
        err.print(f"[red]No story with id {story_id}.[/]")
        raise typer.Exit(1)
    card, members = found

    console.print(f"[bold]{card.title}[/]")
    if card.summary:
        console.print(f"\n{truncate(card.summary, 600)}")
    console.print(f"\n[dim]{card.item_count} items from {len(card.sources)} sources[/]\n")

    for member in members:
        console.print(f"  [cyan]{member['role']:<10}[/] [bold]{truncate(member['title'], 72)}[/]")
        byline = f"             [dim]{member['source_name']}"
        if member["author"]:
            byline += f" · {member['author']}"
        if member["published_at"]:
            byline += f" · {member['published_at'][:10]}"
        console.print(byline + "[/]")
        console.print(f"             [blue]{member['url']}[/]")
