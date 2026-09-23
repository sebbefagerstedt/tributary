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
    why: Annotated[
        str | None,
        typer.Option(
            "--why",
            help="Why a story landed where it did: a story id, or words from its title.",
        ),
    ] = None,
) -> None:
    """Give each story one home topic, and match its facets and entities."""
    cfg, conn = open_config(config)

    if why is not None:
        _explain(conn, cfg, why)
        return

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
            f"{result.claimed} claimed by headline, "
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


# How many leaves --why lists. The runner-up is what matters; a few more show
# whether the story had one plausible home or several.
WHY_TOP = 6


def _explain(conn, cfg, key: str) -> None:
    """Print a story's scores against the spine, and the rule that decided it."""
    story_id = topics.find_story(conn, key)
    if story_id is None:
        err.print(f"[red]No story matches[/] {key!r}.")
        raise typer.Exit(1)
    found = topics.explain(conn, cfg.topics, story_id)
    if found is None:
        err.print(f"[yellow]Story {story_id} has no vectors or the spine has no leaves.[/]")
        raise typer.Exit(1)

    def label(slug: str | None) -> str:
        if not slug:
            return "no topic"
        shelf = found.parent_of.get(slug)
        name = found.names.get(slug, slug)
        return f"{found.names.get(shelf, shelf)} › {name}" if shelf else name

    console.print(f"[bold]Story {story_id}[/] — {truncate(found.headline, 90)}")
    if found.claimed:
        rule = "claimed by its headline, before any scoring"
    elif found.home is None:
        rule = f"no leaf reached the floor of {cfg.topics.floor}"
    elif found.parked:
        rule = (
            f"parked on the shelf: its top two leaves share it and sit within "
            f"{cfg.topics.park_margin}"
        )
    else:
        rule = "the best-scoring leaf"
    console.print(f"Home today: [cyan]{label(found.home)}[/] — {rule}")
    if not found.attempted:
        console.print("[dim]Not labelled yet — the next `trib topics` gives it this home.[/]")
    elif found.stored != found.home:
        console.print(
            f"[yellow]It carries {label(found.stored)}[/] — labelled under an older spine "
            "or profile; `trib topics --reset` re-labels"
        )

    table = Table("leaf", "score", title="Against every leaf, best first")
    for slug, score in found.scores[:WHY_TOP]:
        table.add_row(label(slug), f"{score:.3f}")
    console.print(table)
    if (margin := found.margin) is not None:
        runner_up = found.scores[1][0]
        other_shelf = found.parent_of.get(runner_up) != found.parent_of.get(found.scores[0][0])
        console.print(
            f"Margin to the runner-up: [bold]{margin:.3f}[/]"
            + (" — on a different shelf" if other_shelf else " — on the same shelf")
            + (". A coin-toss, not a verdict." if margin < 0.02 else ".")
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
