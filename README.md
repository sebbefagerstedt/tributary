# Tributary

A personal AI-news feed. Many sources, one river.

Following AI is fragmented across news sites, Hacker News, Reddit, YouTube, arXiv,
HuggingFace and GitHub. Tributary ingests all of them, groups what it finds into
**stories**, and serves a feed you can scan on a phone and drill into.

The unit is the story, not the article. One release shows up once, with the blog
post, the paper, the repo, the video walkthroughs and the discussion threads all
attached to it — rather than as twelve near-duplicate headlines.

> Working name; renaming means renaming one package directory.

## Status

**Phase 3 complete** — ingestion, local embeddings, the relevance gate,
cross-source clustering, a ranked feed, and a mobile web app you can install to
your phone's home screen, hosted either locally or free on GitHub Pages.
YouTube transcripts are next; see the [plan](~/.claude/plans/hi-fluffy-peacock.md).

**No LLM, no API key, no cost.** Everything runs locally. The one model is a
130MB embedding model on your CPU. Story synthesis ("why this matters") is the
only part of the design that needs an API, and it is optional — cards are built
from the best source's own words.

## Quick start

```bash
uv sync
uv run trib init      # writes config.toml, creates the database
uv run trib run       # fetch, embed, triage, enrich, cluster
uv run trib serve     # the web app at http://127.0.0.1:8808
```

Or stay in the terminal: `trib feed` for the ranked list, `trib story <id>` to
drill into one.

`trib run` is the command to schedule. It exits non-zero if any source failed,
so a scheduler notices a broken feed. The stages are also separate commands
(`fetch`, `embed`, `triage`) when you want to work on one of them.

| Command | |
|---|---|
| `trib run` | the whole pipeline; what you put in cron |
| `trib fetch` | `--dry-run` reports without writing; `--source <substr>` limits scope; `--force` ignores cached validators and re-parses |
| `trib embed` | `--reset` discards all vectors and starts over |
| `trib triage` | `--by-source` keep rate per source; `--show` the items nearest the threshold |
| `trib explain <id>` | why one item was kept or dropped, and what it matched |
| `trib serve` | the web app; `--host 0.0.0.0` to reach it from a phone |
| `trib export <dir>` | a static site needing no server |
| `trib prune` | delete items older than `--days`, keeping saved ones |
| `trib feed` | the ranked feed in the terminal; `--days N`, `--unseen`, `--mark` |
| `trib story <id>` | every item attached to one story |
| `trib cluster` | `--reset` re-clusters; `--threshold` overrides the merge bar |
| `trib topics` | label stories by subject; `--stats` story count per topic, `--reset` re-labels |
| `trib calibrate` | measures clustering thresholds against ground truth |
| `trib list` | `--state kept\|rejected\|pending`, `--ids`, `-n <limit>` |
| `trib sources` | per-source health: counts, last fetch, last error |

## Configuration

`config.toml` is the source of truth for which sources exist. Removing an entry
disables that source rather than deleting it, so its items survive.

```toml
[[sources]]
kind = "rss"
name = "Simon Willison"
url = "https://simonwillison.net/atom/everything/"
```

Unknown keys pass through to the adapter, so each kind takes its own options
without a config schema change:

```toml
[[sources]]
kind = "hn"
name = "Hacker News (AI)"
query = "AI OR LLM OR Anthropic"
min_points = 30

[[sources]]
kind = "github"
name = "GitHub Releases"
repos = ["vllm-project/vllm", "ggml-org/llama.cpp"]
```

Adapters: `rss`, `hn` (Algolia), `arxiv`, `hf` (models, datasets, daily papers),
`github` (releases).

## Triage

The `[triage]` section decides what is worth keeping. It is **not** a keyword
filter: you write sentences describing what you care about, they get embedded,
and each item is scored by its highest cosine similarity to any of them.

```toml
[triage]
threshold = 0.62
interests = ["an open source AI tool you can run yourself", "..."]
exclude = ["conference marketing and ticket sales", "..."]
always_keep = ["anthropic", "claude"]
```

An item closer to an `exclude` sentence than to any interest is dropped even if
it clears the threshold. Keyword lists override both, for the cases similarity
gets wrong.

Two things to know when tuning: bge puts *unrelated* text near 0.5, so the
usable range is roughly 0.5–1.0 and a threshold of 0.3 keeps everything. And
editing the profile re-triages the whole back catalogue — otherwise a change
would only affect items fetched afterwards.

```bash
trib triage --by-source   # keep rate per source -- the most useful view
trib triage --show        # weakest kept and strongest dropped: the margin
trib explain 1423         # which interest an item matched, and how closely
```

`--by-source` is the one to reach for first. A working profile shows a
*gradient* — research feeds in the 80–100% band, general tech feeds down at
20–30%. A uniform rate across every source means the profile is measuring text
length rather than relevance.

Tuning is mostly about coverage, not the threshold. When a source you trust
shows a low keep rate, read what it dropped: usually the profile has no sentence
for that topic. Adding one moved Lilian Weng's deep-learning posts from 30% to
68% kept, while Hacker News's front page stayed at 29%.

## Design notes

**Fetching is idempotent and polite.** Items are keyed on
`(source, external_id)`. Conditional GET means feeds that support ETags return
304s; for feeds that don't, a content hash means a re-parse writes nothing when
nothing changed. A repeat `trib fetch` with no upstream changes performs zero
writes.

**One source failing never stops a run.** Failures are recorded against the
source and surfaced by `trib sources`, so a dead feed is a visible health row
rather than a silently missing morning.

**Adapters never touch the database.** They take fetch state in and return
items plus new state, which keeps them testable without a database.

**Embeddings are local.** Triage has to score every ingested item, and paying
per token to decide what to throw away would invert the economics. fastembed
runs bge-small under ONNX: ~200MB rather than the ~2GB a torch install costs.

**An HN story is a discussion, not the article it links to.** The item's URL is
the thread; the submitted link becomes a clustering join key connecting the
thread to the article itself.

## Reading it on a phone

```bash
trib serve --host 0.0.0.0
```

Then open the printed address on your phone and add it to the home screen — it
installs as a standalone app, with a service worker caching the shell so it
opens instantly and survives a dropped connection. API responses are
deliberately *not* cached: a stale feed is worse than an honest error.

**There is no authentication.** Run it over [Tailscale](https://tailscale.com),
which puts your machine on your phone privately with no port forwarding and
nothing exposed to the internet. `trib serve --host 0.0.0.0` lists Tailscale
addresses (100.x) first. Do not put this on a public interface.

The UI is a single self-contained page — no build step, no `node_modules`. A
bundler would be the heaviest thing in this repository for what is a vertical
card list, and CSS scroll-snap gives it the feel it needs. The JSON API under
`/api` is the contract, so replacing the frontend later touches nothing else.

One deliberate departure from "TikTok for news": full-screen snap cards mean one
headline per screen, which is the opposite of scannable. The feed is a dense
card list instead — tap to drill into a story, with its paper, repo, coverage
and discussion grouped underneath.

## Hosting it free on GitHub Pages

Every read endpoint returns a slice of a database that only changes when the
pipeline runs, so the whole API collapses into **one JSON bundle** that can be
built ahead of time. `trib export site/` writes a self-contained static site;
`.github/workflows/update.yml` runs the pipeline hourly and publishes it.

The page reads that bundle whether a live server built it or a scheduled job
wrote it to disk hours ago — the server exposes the identical shape at
`/data.json`. One frontend, two deployments, no build step. Per-device state
(seen, saved, dismissed) lives in `localStorage`, because it is a preference
rather than data, and a static host has nowhere else to put it.

To set it up: push to GitHub, then **Settings → Pages → Source: GitHub Actions**.
The first run takes a few minutes (it fetches everything and builds the
embeddings); later runs take about one.

Two things worth knowing:

- **The database is not committed.** It lives in the Actions cache, because git
  stores each version of a binary in full and an hourly commit of a multi-megabyte
  file would grow the repository without bound. A cache miss is survivable: the
  run rebuilds from the sources.
- **YouTube transcripts will not work there.** Actions runners are cloud IPs, and
  YouTube blocks those. That feature needs a residential connection — your own
  machine, or a Raspberry Pi at home pushing to the same repo.

## Clustering

The unit of the feed is a *story*, not an article, so one release appears once
with its paper, its repo, its coverage and its discussion attached. Three tiers,
cheapest and most precise first:

1. **Shared strong identifier** — an arXiv id, DOI, canonical URL, HF model, or
   release tag. Exact and free. Identifiers are graded: a *repo* is referenced by
   hundreds of unrelated items, so it is a weak signal and never joins stories.
   Anything shared by more than 8 items is treated as a category, not an event.
2. **Embedding similarity** within a 14-day window, for coverage that never
   cites its source.
3. **LLM adjudication** for the ambiguous band — designed for, not wired up.
   Items there simply start their own story.

Tier 1 earns its place: two Hacker News posts of the *same* headline scored only
0.888 on embeddings — below the merge bar — but joined instantly on their shared
outbound URL.

### Thresholds are measured, not guessed

`trib calibrate` uses tier 1 as ground truth: two items carrying the same strong
identifier *are* the same story, no labelling required. It scores those against
two grades of negative — random pairs, and the hard case of *different* papers
published within a week of each other.

The distributions overlap. Genuine matches ran as low as 0.888 while different
papers from the same week reached 0.944, so no threshold is clean:

| merge at | positives caught | false merges (of 18,235 hard pairs) |
|---|---|---|
| 0.88 | 87/87 | 8 |
| **0.92** | **85/87** | **1** |

0.92, because a wrong merge costs more than a missed link.

## Ranking

Recency-decayed relevance (48-hour half-life), with a capped bonus for stories
several independent sources covered. Deliberately **not** an engagement
optimiser — the problem being solved is that existing feeds waste your time.

One thing the ranking must do is resist volume. arXiv publishes ~150 papers a
day where a blog publishes one, and pure recency-times-relevance handed it 47 of
the first 50 cards. The feed damps each *repeat* from a source or kind as it is
built, which restores a mix without any hard quota — a day where arXiv genuinely
is the news still leads with arXiv.

## Development

```bash
uv run pytest      # 184 tests
uv run ruff check .
```

Database migrations are plain SQL in `src/tributary/migrations/`, applied in
filename order and recorded in `schema_migrations`. Add a numbered file; it
applies on the next command.
