"""Deciding what to keep, and what belongs together."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.table import Table

from tributary import calibrate as calibrate_mod
from tributary import cluster as cluster_mod
from tributary import (
    enrich,
    triage,
)
from tributary.cli.common import ConfigOpt, app, console, err, open_config
from tributary.text import truncate

PANEL = "Pipeline"


@app.command(rich_help_panel=PANEL, name="triage")
def triage_cmd(
    config: ConfigOpt = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n")] = None,
    show: Annotated[
        bool, typer.Option("--show", help="Print the items nearest the threshold.")
    ] = False,
    by_source: Annotated[
        bool, typer.Option("--by-source", help="Show the keep rate for each source.")
    ] = False,
) -> None:
    """Score items against the interest profile and keep or drop them."""
    cfg, conn = open_config(config)
    if not cfg.triage.interests:
        err.print("[yellow]No interests configured.[/] Add a [triage] section to your config.")
        raise typer.Exit(1)

    if triage.reset_if_profile_changed(conn, cfg.triage):
        console.print("[yellow]Profile changed — re-triaging everything.[/]")

    result = triage.run(conn, cfg.triage, limit=limit)
    console.print(
        f"[green]{result.kept} kept[/], {result.rejected} dropped"
        + (f", [yellow]{result.skipped} awaiting embedding[/]" if result.skipped else "")
    )

    counts = triage.stats(conn)
    total = counts["kept"] + counts["rejected"]
    if total:
        share = 100 * counts["kept"] / total
        console.print(f"[dim]Overall: {counts['kept']}/{total} kept ({share:.0f}%)[/]")

    if by_source:
        table = Table(box=None, pad_edge=False)
        table.add_column("Source", style="cyan", no_wrap=True)
        table.add_column("Kept", justify="right")
        table.add_column("Total", justify="right", style="dim")
        table.add_column("Rate", justify="right")
        table.add_column("Mean", justify="right", style="dim")
        for row in triage.by_source(conn):
            rate = 100 * row["kept"] / row["total"]
            colour = "green" if rate >= 60 else "yellow" if rate >= 25 else "red"
            table.add_row(
                truncate(row["name"], 26),
                str(row["kept"]),
                str(row["total"]),
                f"[{colour}]{rate:.0f}%[/]",
                f"{row['mean_score']:.3f}",
            )
        console.print()
        console.print(table)

    if show:
        margins = ((triage.KEPT, "Weakest kept"), (triage.REJECTED, "Strongest dropped"))
        for state, heading in margins:
            table = Table(title=heading, box=None, pad_edge=False, title_justify="left")
            table.add_column("Score", justify="right", style="dim")
            table.add_column("Source", style="cyan", no_wrap=True)
            table.add_column("Title")
            for row in triage.sample(conn, state, limit=10):
                table.add_row(
                    f"{row['triage_score']:.3f}",
                    truncate(row["source_name"], 20),
                    truncate(row["title"], 74),
                )
            console.print(table)
            console.print()


@app.command(rich_help_panel=PANEL)
def explain(
    item_id: Annotated[int, typer.Argument(help="Item id, as shown by `trib list --ids`.")],
    config: ConfigOpt = None,
) -> None:
    """Show why an item was kept or dropped, and what it matched."""
    cfg, conn = open_config(config)
    detail = triage.explain(conn, cfg.triage, item_id)
    if detail is None:
        err.print(f"[red]No embedded item with id {item_id}.[/]")
        raise typer.Exit(1)

    colour = "green" if detail["state"] == triage.KEPT else "red"
    console.print(f"[bold]{detail['title']}[/]")
    console.print(f"  kind    {detail['kind']}")
    console.print(f"  verdict [{colour}]{detail['state']}[/] — {detail['reason']}")
    if detail["exclude_score"]:
        console.print(f"  exclude {detail['exclude_score']:.3f}")
    console.print()
    console.print("  [dim]closest interests[/]")
    for interest, score in detail["ranked"]:
        console.print(f"    {score:.3f}  {truncate(interest, 80)}")


@app.command(rich_help_panel=PANEL, name="enrich")
def enrich_cmd(
    config: ConfigOpt = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Re-extract identifiers for every item.")
    ] = False,
) -> None:
    """Extract the identifiers that link items across sources."""
    _, conn = open_config(config)
    if reset:
        enrich.reset(conn)
        console.print("[yellow]Cleared all identifiers.[/]")

    result = enrich.run(conn)
    console.print(f"[green]Scanned {result['items']} items.[/]")
    for kind, count in sorted(result["by_type"].items(), key=lambda kv: -kv[1]):
        console.print(f"  {kind:16} {count}")

    shared = enrich.shared_identifiers(conn)
    console.print(f"\n[cyan]{len(shared)}[/] strong identifiers are shared by more than one item.")


@app.command(rich_help_panel=PANEL, name="cluster")
def cluster_cmd(
    config: ConfigOpt = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Discard all stories and re-cluster.")
    ] = False,
    threshold: Annotated[
        float, typer.Option("--threshold", help="Similarity required to merge.")
    ] = cluster_mod.MERGE_THRESHOLD,
) -> None:
    """Group items into stories."""
    _, conn = open_config(config)
    if reset:
        cluster_mod.reset(conn)
        console.print("[yellow]Cleared all stories.[/]")

    result = cluster_mod.run(conn, merge_threshold=threshold)
    console.print(
        f"[green]{result.assigned} items assigned[/] — "
        f"{result.stories_created} new stories, "
        f"{result.joined_by_identifier} joined by identifier, "
        f"{result.joined_by_similarity} by similarity"
    )
    if result.ambiguous:
        console.print(
            f"[yellow]{len(result.ambiguous)} near-misses[/] in the ambiguous band "
            f"(started their own stories)"
        )

    info = cluster_mod.stats(conn)
    console.print(
        f"\n{info['stories']} stories over {info['items']} items — "
        f"{info['multi']} with more than one item, largest has {info['largest']}"
    )


@app.command(rich_help_panel=PANEL)
def calibrate(
    config: ConfigOpt = None,
) -> None:
    """Measure clustering thresholds against tier-1 ground truth."""
    _, conn = open_config(config)
    thresholds = [0.84, 0.86, 0.88, 0.90, 0.92, 0.94]
    report = calibrate_mod.evaluate(conn, thresholds)

    table = Table(title="Similarity distributions", box=None, pad_edge=False, title_justify="left")
    table.add_column("Set", style="cyan")
    table.add_column("Pairs", justify="right")
    for column in ("min", "p5", "median", "p95", "max"):
        table.add_column(column, justify="right")
    for name, summary in report["distributions"].items():
        if not summary["n"]:
            continue
        table.add_row(
            name,
            str(summary["n"]),
            *[f"{summary[c]:.3f}" for c in ("min", "p5", "median", "p95", "max")],
        )
    console.print(table)

    console.print()
    choice = Table(title="Threshold trade-off", box=None, pad_edge=False, title_justify="left")
    choice.add_column("Threshold", justify="right")
    choice.add_column("Positives caught", justify="right")
    choice.add_column("Recall", justify="right")
    choice.add_column("False merges", justify="right")
    for row in report["thresholds"]:
        marker = " [dim]<- current[/]" if row["threshold"] == cluster_mod.MERGE_THRESHOLD else ""
        colour = "red" if row["false_merges"] > 5 else "green"
        choice.add_row(
            f"{row['threshold']:.2f}",
            f"{row['caught']}/{row['positives']}",
            f"{row['recall']:.0%}",
            f"[{colour}]{row['false_merges']}[/]/{row['hard_pairs']}" + marker,
        )
    console.print(choice)
    console.print(
        "\n[dim]Positives are pairs sharing a strong identifier. Hard negatives are\n"
        "different papers from the same week — where real false merges come from.[/]"
    )
