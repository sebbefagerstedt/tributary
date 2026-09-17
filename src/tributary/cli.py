"""Command line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from tributary import calibrate as calibrate_mod
from tributary import cluster as cluster_mod
from tributary import config as config_mod
from tributary import db as db_mod
from tributary import (
    describe,
    embeddings,
    enrich,
    entities,
    facets,
    store,
    topics,
    triage,
)
from tributary import export as export_mod
from tributary import feed as feed_mod
from tributary.pipeline import fetch_all
from tributary.text import truncate

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Tributary — a personal AI-news feed. Many sources, one river.",
)
console = Console()
err = Console(stderr=True)

ConfigOpt = Annotated[
    Path | None, typer.Option("--config", "-c", help="Path to config.toml.")
]

SAMPLE_CONFIG = '''# Tributary configuration.
# This file is the source of truth for which sources exist: add or remove
# entries and re-run `trib fetch`. Sources removed here are disabled, not
# deleted, so their items survive.

[tributary]
# Relative paths resolve against this file, so trib works from any directory.
db_path = "./tributary.db"

# --- Labs and primary sources ------------------------------------------------

[[sources]]
kind = "rss"
name = "OpenAI Blog"
url = "https://openai.com/blog/rss.xml"

[[sources]]
kind = "rss"
name = "Google DeepMind"
url = "https://deepmind.google/blog/rss.xml"

[[sources]]
kind = "rss"
name = "Google Research"
url = "https://research.google/blog/rss/"

[[sources]]
kind = "rss"
name = "Apple Machine Learning"
url = "https://machinelearning.apple.com/rss.xml"

[[sources]]
kind = "rss"
name = "Hugging Face Blog"
url = "https://huggingface.co/blog/feed.xml"

# Anthropic publishes no public RSS feed; covered for now via TechCrunch and
# Simon Willison. Revisit when the HTML-scrape adapter lands.

# --- Commentary and analysis -------------------------------------------------

[[sources]]
kind = "rss"
name = "Simon Willison"
url = "https://simonwillison.net/atom/everything/"

[[sources]]
kind = "rss"
name = "Import AI"
url = "https://importai.substack.com/feed"

[[sources]]
kind = "rss"
name = "Latent Space"
url = "https://www.latent.space/feed"

[[sources]]
kind = "rss"
name = "Lilian Weng"
url = "https://lilianweng.github.io/index.xml"

[[sources]]
kind = "rss"
name = "The Gradient"
url = "https://thegradient.pub/rss/"

# --- Press -------------------------------------------------------------------

[[sources]]
kind = "rss"
name = "TechCrunch AI"
url = "https://techcrunch.com/category/artificial-intelligence/feed/"

[[sources]]
kind = "rss"
name = "MIT News AI"
url = "https://news.mit.edu/rss/topic/artificial-intelligence2"

[[sources]]
kind = "rss"
name = "MarkTechPost"
url = "https://www.marktechpost.com/feed/"

# --- Discussion --------------------------------------------------------------

[[sources]]
kind = "hn"
name = "Hacker News (AI)"
query = "AI OR LLM OR OpenAI OR Anthropic OR model"
min_points = 30
limit = 100

[[sources]]
kind = "hn"
name = "Hacker News (front page)"
min_points = 150
limit = 100

# --- Papers ------------------------------------------------------------------

[[sources]]
kind = "arxiv"
name = "arXiv AI"
categories = ["cs.AI", "cs.CL", "cs.LG"]
max_results = 150

[[sources]]
kind = "hf"
name = "HF Daily Papers"
mode = "papers"
limit = 50

# --- Models and code ---------------------------------------------------------

[[sources]]
kind = "hf"
name = "HF Trending Models"
mode = "models"
sort = "likes7d"
limit = 50

[[sources]]
kind = "github"
name = "GitHub Releases"
repos = [
    "vllm-project/vllm",
    "ggml-org/llama.cpp",
    "huggingface/transformers",
    "langchain-ai/langchain",
    "ollama/ollama",
    "comfyanonymous/ComfyUI",
    "modelcontextprotocol/servers",
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "unslothai/unsloth",
]
per_page = 5

# --- Triage ------------------------------------------------------------------
# Relevance gate. Every item is scored by its highest cosine similarity to the
# interest sentences below; anything closer to an exclude sentence is dropped
# regardless. Keyword lists override both.
#
# These are embeddings, not keywords: write sentences describing the kind of
# thing you want, not search terms. Tune with `trib triage --show` and
# `trib explain <id>`.
#
# bge puts unrelated text near 0.5, so the usable range is roughly 0.5-1.0.

[triage]
threshold = 0.66

interests = [
    "a new large language model is released, with benchmarks and capabilities",
    "an open source AI tool, library or framework you can run yourself",
    "research on language model reasoning, training methods or architecture",
    "AI agents, tool use, and the protocols that connect models to systems",
    "running models locally: quantization, inference speed, GPU requirements",
    "evaluation, benchmarks and measuring what models can actually do",
    "AI safety, interpretability, alignment and model behaviour research",
    "adversarial attacks, jailbreaks, prompt injection and model security",
    "how developers build with LLMs in practice: prompting, RAG, fine-tuning",
    "multimodal models that handle images, audio or video",
    "deep learning fundamentals: architectures, embeddings, generative models",
    "computer vision, reinforcement learning and classical machine learning",
    "the economics and infrastructure of AI: chips, compute, datacenters",
    "AI companies: acquisitions, lab moves, funding and competitive dynamics",
    "AI policy, regulation and copyright as they affect what gets built",
]

exclude = [
    "conference marketing, ticket sales, exhibitor booths and sponsorships",
    "cryptocurrency, blockchain, NFTs and token prices",
    "consumer gadget reviews, phones, smartwatches and TVs",
    "social media platform features, influencers and creator monetisation",
    "stock market movements, earnings calls and analyst price targets",
    "generic startup funding rounds with no technical substance",
]

always_keep = ["anthropic", "claude", "gpt-", "gemini", "llama", "deepseek", "qwen", "mistral"]
always_drop = []
'''


def _open(config_path: Path | None):
    cfg = config_mod.load(config_path)
    conn = db_mod.connect(cfg.db_path)
    db_mod.migrate(conn)
    return cfg, conn


@app.command()
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
        target.write_text(SAMPLE_CONFIG)
        console.print(f"[green]Wrote config:[/] {target}")

    cfg = config_mod.load(target)
    conn = db_mod.connect(cfg.db_path)
    applied = db_mod.migrate(conn)
    console.print(f"[green]Database ready:[/] {cfg.db_path}")
    if applied:
        console.print(f"  applied migrations: {', '.join(applied)}")
    console.print(f"  sources configured: {len(cfg.sources)}")


@app.command()
def migrate(config: ConfigOpt = None) -> None:
    """Apply any pending database migrations."""
    cfg = config_mod.load(config)
    conn = db_mod.connect(cfg.db_path)
    applied = db_mod.migrate(conn)
    console.print(
        f"[green]Applied {len(applied)}:[/] {', '.join(applied)}" if applied else "Already current."
    )


@app.command()
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
    cfg, conn = _open(config)
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


@app.command(name="list")
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
    _, conn = _open(config)
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


@app.command()
def sources(config: ConfigOpt = None) -> None:
    """Show per-source health: item counts, last fetch, last error."""
    _, conn = _open(config)
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


@app.command()
def embed(
    config: ConfigOpt = None,
    limit: Annotated[int | None, typer.Option("--limit", "-n")] = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Discard all vectors and start over.")
    ] = False,
) -> None:
    """Embed items that have no vector, or whose text has changed."""
    cfg, conn = _open(config)

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


@app.command(name="triage")
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
    cfg, conn = _open(config)
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


@app.command()
def explain(
    item_id: Annotated[int, typer.Argument(help="Item id, as shown by `trib list --ids`.")],
    config: ConfigOpt = None,
) -> None:
    """Show why an item was kept or dropped, and what it matched."""
    cfg, conn = _open(config)
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


@app.command(name="enrich")
def enrich_cmd(
    config: ConfigOpt = None,
    reset: Annotated[
        bool, typer.Option("--reset", help="Re-extract identifiers for every item.")
    ] = False,
) -> None:
    """Extract the identifiers that link items across sources."""
    _, conn = _open(config)
    if reset:
        enrich.reset(conn)
        console.print("[yellow]Cleared all identifiers.[/]")

    result = enrich.run(conn)
    console.print(f"[green]Scanned {result['items']} items.[/]")
    for kind, count in sorted(result["by_type"].items(), key=lambda kv: -kv[1]):
        console.print(f"  {kind:16} {count}")

    shared = enrich.shared_identifiers(conn)
    console.print(f"\n[cyan]{len(shared)}[/] strong identifiers are shared by more than one item.")


@app.command(name="cluster")
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
    _, conn = _open(config)
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


@app.command(name="describe")
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
    _, conn = _open(config)
    if reset:
        describe.reset(conn)
        console.print("[yellow]Cleared the record of what has been attempted.[/]")

    result = describe.run(conn, limit=limit)
    if not result["attempted"]:
        console.print("[green]Nothing missing a description.[/]")
        return
    console.print(
        f"[green]{result['filled']} described[/] of {result['attempted']} attempted — "
        f"those items are re-embedded and re-triaged on the next run"
    )


@app.command(name="topics")
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
    """Label stories with what they are about."""
    cfg, conn = _open(config)

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
                f"{candidate.uncovered} unclaimed · covered by: {claimed}"
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

    table = Table("topic", "stories", "last story", title="Topics")
    for row in topics.stats(conn):
        # Topics are allowed to be short-lived, so "quiet since" is the column
        # that says whether one has finished rather than failed.
        table.add_row(row["name"], str(row["stories"]), (row["newest"] or "never")[:10])
    console.print(table)


@app.command()
def calibrate(
    config: ConfigOpt = None,
) -> None:
    """Measure clustering thresholds against tier-1 ground truth."""
    _, conn = _open(config)
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


@app.command(name="feed")
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
    _, conn = _open(config)
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


@app.command()
def story(
    story_id: Annotated[int, typer.Argument(help="Story id, as shown in the feed.")],
    config: ConfigOpt = None,
) -> None:
    """Everything attached to one story."""
    _, conn = _open(config)
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


@app.command(name="export")
def export_cmd(
    out: Annotated[Path, typer.Argument(help="Directory to write the static site into.")],
    config: ConfigOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = export_mod.DEFAULT_LIMIT,
    days: Annotated[
        int | None, typer.Option("--days", "-d", help="Only stories active in the last N days.")
    ] = export_mod.DEFAULT_DAYS,
) -> None:
    """Write a static site that needs no server. For GitHub Pages and friends."""
    cfg, conn = _open(config)
    result = export_mod.write_site(conn, out, limit=limit, days=days, facet_names=cfg.facets)
    size = result["bytes"] / 1024
    console.print(
        f"[green]Wrote {result['stories']} stories[/] to {result['path']} "
        f"([dim]data.json {size:.0f} KB[/])"
    )


@app.command()
def prune(
    config: ConfigOpt = None,
    days: Annotated[int, typer.Option("--days", "-d", help="Keep items newer than this.")] = 90,
    include_saved: Annotated[
        bool, typer.Option("--include-saved", help="Also delete saved stories.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation.")] = False,
) -> None:
    """Delete old items to keep the database small."""
    cfg, conn = _open(config)
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


@app.command()
def serve(
    config: ConfigOpt = None,
    host: Annotated[
        str, typer.Option("--host", help="Interface to bind. 0.0.0.0 to reach it from a phone.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p")] = 8808,
    reload: Annotated[bool, typer.Option("--reload", help="Restart on code changes.")] = False,
) -> None:
    """Serve the web app.

    There is no authentication: this is meant to run on your own machine and be
    reached from a phone over Tailscale, not exposed to the internet.
    """
    import os

    import uvicorn

    # create_app() is built by uvicorn (possibly in a reloaded subprocess), so
    # the config path has to travel through the environment rather than a closure.
    if config:
        os.environ["TRIBUTARY_CONFIG"] = str(config.resolve())

    console.print(f"[green]Tributary[/] on [bold]http://{host}:{port}[/]")
    if host in ("0.0.0.0", "::"):
        addresses = _local_addresses()
        for address in addresses:
            console.print(f"  [dim]from your phone:[/] http://{address}:{port}")
        console.print(
            "  [yellow]No authentication[/] — keep this on a trusted network or Tailscale."
        )

    uvicorn.run(
        "tributary.api:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="warning",
    )


def _local_addresses() -> list[str]:
    """Addresses this machine can be reached on, Tailscale ones first."""
    import socket

    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    # Tailscale hands out 100.64.0.0/10; that is the one worth reaching from a phone.
    return sorted(found, key=lambda a: not a.startswith("100."))


@app.command()
def run(
    config: ConfigOpt = None,
    source: Annotated[
        str | None,
        typer.Option("--source", "-s", help="Limit the fetch to matching sources."),
    ] = None,
) -> None:
    """Fetch, embed and triage in one pass. This is the command to schedule."""
    cfg, conn = _open(config)
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


if __name__ == "__main__":
    app()
