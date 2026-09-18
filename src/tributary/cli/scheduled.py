"""The whole pipeline in one pass. This is the command to schedule."""

from __future__ import annotations

from typing import Annotated

import typer

from tributary import cluster as cluster_mod
from tributary import db as db_mod
from tributary import (
    describe,
    embeddings,
    enrich,
    entities,
    facets,
    topics,
    triage,
)
from tributary.cli.common import ConfigOpt, app, console, err, open_config
from tributary.pipeline import fetch_all
from tributary.text import truncate

PANEL = "Pipeline"


@app.command(rich_help_panel=PANEL)
def run(
    config: ConfigOpt = None,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Limit the fetch to matching sources."),
    ] = None,
) -> None:
    """Fetch, describe, embed, triage, cluster and label. The one to schedule."""
    cfg, conn = open_config(config)
    if not cfg.sources:
        err.print("[yellow]No sources configured.[/] Run `trib init`.")
        raise typer.Exit(1)

    outcomes = fetch_all(conn, cfg.sources, only=source)
    new = sum(o.result.inserted for o in outcomes if o.ok)
    updated = sum(o.result.updated for o in outcomes if o.ok)
    # Unchanged and stale are what tell you a run is doing real work rather than
    # re-ingesting the same archive: all-new with nothing unchanged is the shape
    # of churn, not of news.
    unchanged = sum(o.result.unchanged for o in outcomes if o.ok)
    stale = sum(o.result.stale for o in outcomes if o.ok)
    failed = [o for o in outcomes if not o.ok]
    console.print(
        f"[cyan]fetch[/]   {new} new, {updated} updated, {unchanged} unchanged, "
        f"{stale} too old across {len(outcomes)} sources"
    )
    for outcome in failed:
        err.print(f"  [red]{outcome.source}:[/] {truncate(outcome.error, 70)}")

    # Before embedding, so a fetched description feeds the vector and the triage
    # decision rather than arriving a run too late to affect either.
    described = describe.run(conn)
    if described["attempted"]:
        console.print(
            f"[cyan]describe[/] {described['filled']} of {described['attempted']} "
            f"bare items given a description"
        )

    embeddings.check_model(conn)
    rows = embeddings.pending(conn)
    written = 0
    for start in range(0, len(rows), embeddings.BATCH_SIZE):
        batch = rows[start : start + embeddings.BATCH_SIZE]
        vectors = embeddings.embed([embeddings.embedding_text(r) for r in batch])
        with db_mod.transaction(conn):
            written += embeddings.store(conn, batch, vectors)
    console.print(f"[cyan]embed[/]   {written} items")

    if not cfg.triage.interests:
        console.print("[yellow]triage[/]  skipped — no interests configured")
        return
    triage.reset_if_profile_changed(conn, cfg.triage)
    result = triage.run(conn, cfg.triage)
    console.print(f"[cyan]triage[/]  {result.kept} kept, {result.rejected} dropped")

    enriched = enrich.run(conn)
    console.print(f"[cyan]enrich[/]  {enriched['items']} items scanned for identifiers")

    clustered = cluster_mod.run(conn)
    info = cluster_mod.stats(conn)
    # The near-miss count belongs in the scheduled log too: a merge rate that
    # looks too low is only diagnosable next to the band that just missed.
    near = f", {len(clustered.ambiguous)} near-misses" if clustered.ambiguous else ""
    console.print(
        f"[cyan]cluster[/] {clustered.assigned} assigned "
        f"({clustered.joined_by_identifier} by id, {clustered.joined_by_similarity} by similarity"
        f"{near}) — {info['stories']} stories"
    )

    # After clustering: topics describe a story, which does not exist until here.
    if cfg.topics.spine:
        topics.reset_if_profile_changed(conn, cfg.topics, cfg.label_fingerprint())
        labelled = topics.run(conn, cfg.topics)
        marked = facets.run(conn, cfg.facets)
        named = entities.run(conn, cfg.entities)
        console.print(
            f"[cyan]topics[/]  {labelled.assigned} stories labelled "
            f"({labelled.parked} parked), {labelled.unmatched} off-spine; "
            f"{marked.matched} faceted, {named.matched} with entities"
        )

    if failed:
        raise typer.Exit(1)  # so a scheduler notices a broken source
