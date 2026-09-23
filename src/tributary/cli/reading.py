"""Looking at what is in the database, from the terminal."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from tributary import (
    discover,
    store,
)
from tributary import feed as feed_mod
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
def sources(
    config: ConfigOpt = None,
    suggest: Annotated[
        str | None,
        typer.Option(
            "--suggest",
            help="Find a site's feed: a domain or URL. Prints config to paste; writes nothing.",
        ),
    ] = None,
) -> None:
    """Show per-source health: item counts, last fetch, last error."""
    if suggest is not None:
        _suggest_source(config, suggest)
        return
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
def renewal(
    config: ConfigOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    days: Annotated[
        int | None, typer.Option("--days", "-d", help="Only stories active in the last N days.")
    ] = None,
) -> None:
    """Show how much of the feed's order comes from late arrivals."""
    _, conn = open_config(config)
    rows, summary = feed_mod.renewal(conn, limit=limit, days=days)
    if not rows:
        console.print("[yellow]Nothing to show.[/] Run `trib run` first.")
        return

    table = Table(box=None, pad_edge=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Shown", style="dim", no_wrap=True)
    table.add_column("Gap", justify="right", no_wrap=True)
    table.add_column("Lift", justify="right", style="dim", no_wrap=True)
    table.add_column("Renewed by", no_wrap=True)
    table.add_column("Moved", justify="right", no_wrap=True)
    # One row per story: six columns already, and a wrapped title turns the
    # table into a paragraph you cannot scan down.
    table.add_column("Title", no_wrap=True, overflow="ellipsis")

    for row in rows:
        # A day of gap is where the shown date and the ranking date start to
        # read as a contradiction: two half-lives is a 1.4x lift.
        colour = "red" if row.gap_hours >= 48 else "yellow" if row.gap_hours >= 24 else "dim"
        gap = "—" if row.gap_hours < 1 else f"[{colour}]{row.gap_hours:.0f}h[/]"
        lift = "—" if row.gap_hours < 1 else f"{row.lift:.2f}x"
        renewed = "—" if row.gap_hours < 1 else (
            f"{row.renewed_role} · {truncate(row.renewed_source, 18)}"
        )
        if row.carried:
            moved = "[red]carried[/]"
        elif row.moved and row.moved > 0:
            moved = f"[yellow]+{row.moved}[/]"
        else:
            moved = "—"
        table.add_row(
            str(row.position),
            (row.shown or "")[:10] or "—",
            gap,
            lift,
            renewed,
            moved,
            truncate(row.title, 54),
        )
    console.print(table)

    console.print(
        f"\n[cyan]{summary['renewed']}[/]/{summary['stories']} stories were renewed by a later "
        f"arrival, median gap [cyan]{summary['median_gap']:.0f}h[/]."
    )
    if summary["by_role"]:
        parts = [f"{count} {role}" for role, count in sorted(
            summary["by_role"].items(), key=lambda kv: -kv[1])]
        console.print(f"[dim]Renewed by: {', '.join(parts)}.[/]")
    if summary["carried"]:
        console.print(
            f"[yellow]{summary['carried']}[/] would not be in the feed at all if stories "
            "were aged from their oldest item."
        )
    else:
        console.print(
            "[green]None of them would drop out[/] if stories were aged from their oldest "
            "item — the wake is reordering the feed, not filling it."
        )


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


def _suggest_source(config, target: str) -> None:
    """Propose a source for a site; a person pastes it into config.toml."""
    cfg, _ = open_config(config)
    try:
        found = discover.find(target)
    except discover.FetchError as exc:
        err.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    if not found:
        err.print(
            f"[yellow]No feed found for {target}[/] — no <link rel=\"alternate\">, "
            "none at the usual paths, and no news sitemap."
        )
        raise typer.Exit(1)
    have = {source.url for source in cfg.sources}
    for feed in found:
        how = {"link": "announced by the page", "path": "at a well-known path",
               "sitemap": "a news sitemap"}[feed.how]
        state = " [dim](already configured)[/]" if feed.url in have else ""
        console.print(f"[green]{feed.title}[/] — {how}, {feed.entries} entries{state}")
        console.print(discover.snippet(feed), markup=False, highlight=False)
        console.print()
