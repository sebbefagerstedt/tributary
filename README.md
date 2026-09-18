# Tributary

A personal AI-news feed. Many sources, one river.

Following AI is fragmented across news sites, Hacker News, Reddit, arXiv,
Hugging Face and GitHub. Tributary ingests all of them, groups what it finds
into **stories**, and serves a feed you can scan on a phone and drill into.

The unit is the story, not the article. One release shows up once, with the
blog post, the paper, the repo and the discussion threads attached to it —
rather than as twelve near-duplicate headlines.

**No LLM, no API key, no cost.** Everything runs locally; the one model is a
small embedding model on your CPU.

Live at **https://sebbefagerstedt.github.io/tributary/**. What is next is in
[`NEXT.md`](NEXT.md); how the code fits together, and why it works the way it
does, is in [`CLAUDE.md`](CLAUDE.md).

## Quick start

```bash
uv sync
uv run trib init      # writes config.toml, creates the database
uv run trib run       # the whole pipeline
uv run trib serve     # the web app at http://127.0.0.1:8808
```

Or stay in the terminal: `trib feed` for the ranked list, `trib story <id>` to
drill into one, `trib status` to see where everything is.

`trib run` is the command to schedule. It exits non-zero if any source failed,
so a scheduler notices a broken feed.

## Commands

Grouped as `trib --help` groups them. Every stage of `run` is also its own
command, for when you are working on that stage.

| Command | |
|---|---|
| **Setup** | |
| `trib init` | write a starter config and create the database; `--force` overwrites |
| `trib migrate` | apply pending database migrations |
| `trib status` | config and database paths, counts, last fetch, failing sources |
| **Pipeline** | |
| `trib run` | fetch, describe, embed, triage, cluster and label — what you schedule |
| `trib fetch` | `--source <substr>` limits scope; `--dry-run` writes nothing; `--force` ignores cached validators |
| `trib describe` | fetch descriptions for items that arrived as a bare title |
| `trib embed` | embed what has no vector yet; `--reset` starts over |
| `trib prune` | delete items older than `--days`, keeping saved ones |
| `trib triage` | keep or drop against the interest profile; `--by-source`, `--show` |
| `trib explain <id>` | why one item was kept or dropped, and what it matched |
| `trib enrich` | extract the identifiers that link items across sources |
| `trib cluster` | group items into stories; `--reset`, `--threshold` |
| `trib calibrate` | measure the clustering threshold against ground truth |
| **Labels** | |
| `trib topics` | one home topic per story, plus facets and entities; `--stats`, `--suggest`, `--reset` |
| `trib entities` | stories per entity; `--suggest` proposes names nobody has seeded |
| **Reading** | |
| `trib feed` | the ranked feed; `--days N`, `--unseen`, `--mark` |
| `trib story <id>` | every item attached to one story |
| `trib list` | recent items; `--state kept\|rejected\|pending`, `--ids` |
| `trib sources` | per-source health: counts, last fetch, last error |
| **Publishing** | |
| `trib serve` | the web app; `--host 0.0.0.0` to reach it from a phone |
| `trib export <dir>` | a static site that needs no server |

## Configuration

`config.toml` is the source of truth. Each section is commented with how to
tune it; this is the overview.

### Sources

```toml
[[sources]]
kind = "rss"
name = "Simon Willison"
url = "https://simonwillison.net/atom/everything/"
```

Adapters: `rss` (also Atom, and Reddit's public `.rss` endpoints), `hn`
(Algolia), `arxiv`, `hf` (models, datasets, daily papers) and `github`
(releases). Unknown keys pass through to the adapter, so each kind takes its own
options:

```toml
[[sources]]
kind = "github"
name = "GitHub Releases"
repos = ["vllm-project/vllm", "ggml-org/llama.cpp"]
prereleases = false   # the default; llama.cpp tags a prerelease per commit
```

Removing a source disables it rather than deleting it, so its items survive.

### Triage — what is worth keeping

Not a keyword filter. You write sentences describing what you care about, they
are embedded, and each item is scored by its closest one. An item closer to an
`exclude` sentence is dropped regardless; `always_keep` and `always_drop` are
keyword escape hatches for what similarity gets wrong.

```bash
trib triage --by-source   # keep rate per source -- reach for this first
trib triage --show        # weakest kept and strongest dropped
trib explain 1423         # which interest one item matched, and how closely
```

A healthy profile shows a *gradient*: research feeds kept at 80–100%, general
tech feeds at 20–30%. A uniform rate means the profile is measuring text length
rather than relevance. When a source you trust has a low keep rate, read what it
dropped — usually the fix is a missing interest sentence, not the threshold.

### Topics, facets and entities — how a story is labelled

A story is labelled on three axes, each matched the way that suits it:

| Axis | Question | Matched by | Per story |
|---|---|---|---|
| `[topics]` | where does it live | embedding, best fit | exactly one |
| `[[facets]]` | what kind of thing is it | regex | any number |
| `[[entities]]` | who is it about | name and alias | any number |

Topics are a tree of shelves and leaves. Only leaves are scored, and each story
goes to the one that fits best — there is no threshold to tune. A story whose
two best leaves are on the same shelf and too close to call sits on the shelf
instead. Facets are for subjects that cut across every shelf, like agents or
benchmarks. Entities are the labs, model lines and tools you might follow.

Naming new ones is a person's job, not the pipeline's. `trib topics --suggest`
and `trib entities --suggest` show what is clustering and recurring; the
`/suggest-topics` Claude Code skill in this repo turns that into proposals to
accept or reject.

## Reading it on a phone

```bash
trib serve --host 0.0.0.0
```

Open the printed address on your phone and add it to the home screen. It
installs as an app, and caches its own shell so it opens instantly on a bad
connection. The feed itself is never cached: a stale feed is worse than an
honest error.

**There is no authentication.** Run it over [Tailscale](https://tailscale.com),
which reaches your machine from your phone privately with nothing exposed to the
internet. `serve` lists Tailscale addresses (100.x) first. Do not put this on a
public interface.

## Hosting it free on GitHub Pages

`trib export site/` writes a self-contained static site, and
`.github/workflows/update.yml` runs the pipeline every three hours and publishes
it. To set it up: push to GitHub, then **Settings → Pages → Source: GitHub
Actions**. The first run takes a few minutes; later ones about one.

Two things worth knowing:

- **The database is not committed.** It lives in the Actions cache. A cache
  miss is survivable — the run rebuilds from the sources.
- **Some sources behave differently there.** Actions runners are cloud IPs.
  Substack blocks them, which is why Import AI works locally but not on a run,
  and YouTube would too.

## Development

```bash
uv run pytest
uv run ruff check .
```

Migrations are plain SQL in `src/tributary/migrations/`, applied in filename
order. Add a numbered file and it applies on the next command.

The page is one self-contained file, `src/tributary/web/index.html` — no build
step. It reads one JSON bundle whether `trib serve` built it just now or a
scheduled job wrote it hours ago, so both deployments share one frontend.
