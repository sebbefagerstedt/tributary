"""Where a story lives, and who it is about."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from tributary import (
    entities,
    facets,
    topics,
)
from tributary.cli.common import ConfigOpt, app, console, err, open_config
from tributary.text import truncate

PANEL = "Labels"


@app.command(rich_help_panel=PANEL, name="topics")
def topics_cmd(
    config: ConfigOpt = None,
    stats: Annotated[
        bool, typer.Option("--stats", help="Story count per topic, for tuning the spine.")
    ] = False,
    suggest: Annotated[
        bool, typer.Option("--suggest", help="Group recent stories so new topics can be named.")
    ] = False,
    days: Annotated[int, typer.Option("--days", help="How far back --suggest looks.")] = 7,
    reset: Annotated[
        bool, typer.Option("--reset", help="Discard assignments and re-label every story.")
    ] = False,
) -> None:
    """Give each story one home topic, and match its facets and entities."""
    cfg, conn = open_config(config)

    if suggest:
        # Printed rather than tabulated: the reader is a person or a model
        # deciding what to call these, and headlines are the evidence.
        found = topics.suggest(conn, days=days)
        if not found:
            console.print(f"[yellow]Nothing clustered in the last {days} days.[/]")
            return
        console.print(f"[bold]{len(found)} groups[/] over the last {days} days\n")
        for number, candidate in enumerate(found, start=1):
            claimed = (
                ", ".join(f"{name} ({n})" for name, n in sorted(candidate.covered.items()))
                or "nothing"
            )
            console.print(
                f"[cyan]Group {number}[/] — {candidate.size} stories, "
                f"{candidate.parked} parked on a shelf, {candidate.uncovered} with no topic"
                f" · homes: {claimed}"
            )
            for title in candidate.titles[:8]:
                console.print(f"    {truncate(title, 90)}")
            console.print()
        return

    if not cfg.topics.spine:
        # Escaped: rich reads square brackets as markup and would eat the name.
        err.print(r"[yellow]No topics configured.[/] Add a \[\[topics.spine]] section.")
        raise typer.Exit(1)

    if not stats:
        if reset:
            topics.reset(conn)
            console.print("[yellow]Cleared all topic assignments.[/]")
        elif topics.reset_if_profile_changed(conn, cfg.topics, cfg.label_fingerprint()):
            console.print("[yellow]Spine changed — re-labelling every story.[/]")

        result = topics.run(conn, cfg.topics)
        console.print(
            f"[green]{result.assigned} stories labelled[/] of {result.stories} scored — "
            f"{result.parked} parked on a shelf, "
            f"{result.unmatched} matched nothing on the spine"
        )
        marked = facets.run(conn, cfg.facets)
        named = entities.run(conn, cfg.entities)
        console.print(
            f"[green]{marked.matched} stories carry a facet[/] "
            f"and {named.matched} name an entity"
        )

    table = Table("topic", "stories", "below triage", "last story", title="Topics")
    below_total = 0
    for row in topics.stats(conn):
        # Topics are allowed to be short-lived, so "quiet since" is the column
        # that says whether one has finished rather than failed.
        below = row["below_triage"] or 0
        below_total += below
        table.add_row(
            row["name"],
            str(row["stories"]),
            str(below) if below else "[dim]—[/]",
            (row["newest"] or "never")[:10],
        )
    console.print(table)
    # Not coloured as an alarm any more: triage drops short AI posts as readily
    # as filler, so a high count says little about what a topic holds. See
    # "The topic floor was re-measured on everything" in CLAUDE.md.
    console.print(
        f"\n[dim]{below_total} stories are made only of items triage would have dropped — "
        "short or off the profile, not necessarily off-topic.[/]"
    )


@app.command(rich_help_panel=PANEL, name="entities")
def entities_cmd(
    config: ConfigOpt = None,
    suggest: Annotated[
        bool,
        typer.Option("--suggest", help="Propose names that recur and nobody has seeded yet."),
    ] = False,
    days: Annotated[int, typer.Option("--days", help="How far back --suggest looks.")] = 14,
) -> None:
    """Who stories are about: labs, model lines, tools."""
    cfg, conn = open_config(config)

    if suggest:
        # Proposals, not decisions. Accepting one means adding it to
        # `[[entities]]` in the config, which is what `/suggest-topics` does.
        found = entities.suggest(conn, cfg.entities, days=days)
        if not found:
            console.print(f"[yellow]No new names recurring in the last {days} days.[/]")
            return
        console.print(f"[bold]{len(found)} candidates[/] over the last {days} days\n")
        for candidate in found:
            console.print(f"[cyan]{candidate.name}[/] — {candidate.stories} stories")
            for title in candidate.titles:
                console.print(f"    {truncate(title, 90)}")
        return

    named = entities.run(conn, cfg.entities)
    console.print(f"[green]{named.matched} of {named.stories} stories name an entity[/]")
    table = Table("kind", "entity", "stories", title="Entities")
    for row in entities.stats(conn):
        table.add_row(row["kind"], row["name"], str(row["stories"]))
    console.print(table)
