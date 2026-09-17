# Tributary — state and remaining work

Live at **https://sebbefagerstedt.github.io/tributary/**, rebuilt at 06:00,
11:00 and 18:00 Swedish time. 184 tests passing, lint clean.
**Zero LLM/API usage — everything local and free.**

## The original idea

From the notebook page this started as, transcribed 2026-09-17. Kept because
the roadmap below records what got built, which is not the same as what the
thing was for.

> - Blandat nyheter & sociala medier — **Verifierad (mer trovärdig)**
> - Börja med nyheter för att samla
> - **Vill ta bort mitt sociala medier beroende → något vettigt**
> - Samla fakta från artiklar med personer som kommenterar
> - Combo reddit, tiktok, youtube — (tech videos) för snabb info
> - **Mål: Följa med på allt som händer — prio/börja med AI**

The sketch above the list is three columns: a mixed feed, then `r/AI`, then
`r/AI – huggingface incident`, with a funnel producing `anthropic IPO`.
Everything → a subject → one event. That is feed, topic filter, story page, and
the funnel is the clusterer.

Measured against it:

| From the page | Where it stands |
|---|---|
| Mixed news and social | Built, except Reddit (API approval) |
| Facts from articles *plus the people commenting* | Built — the wake, 2026-09-17 |
| A subject channel, `r/AI` | Built — topics, 2026-09-17 |
| One event, everything about it | Built — the story page |
| Start with news, to gather | Built |
| **Verifierad (mer trovärdig)** | **Not built.** See below |
| **reddit / tiktok / youtube, for quick info** | **Not built.** See below |
| Prio/**börja** med AI | Config-deep, not code-deep — see topics |

Two things the page asks for that nothing in this repo does yet:

1. **"Verifierad (mer trovärdig)".** Corroboration exists as a *ranking* input —
   `SOURCE_BONUS` lifts a story several sources covered, and the card shows a
   "4 sources" chip — but the app never makes the claim. Saying "three
   independent sources agree" out loud, and knowing when they are not
   independent (a wire rewrite is not confirmation), is a different feature from
   nudging a score.
2. **"Combo reddit, tiktok, youtube … för snabb info".** Read with "vill ta bort
   mitt sociala medier beroende", this is not a source list: it is the *format*
   those apps are good at — fast, scannable, mostly not prose — aimed at
   something worth reading. Card art and chips are a step; a feed you can get
   through at that speed is a bigger idea, and the honest note is that nothing
   here has been designed against it yet.

The anti-doomscroll motive is a constraint, not just a nice origin story: it
argues against the engagement mechanics that would be the obvious way to make a
feed moreish. The README already says the ranking is deliberately not an
engagement metric. Keep those two agreeing.

## Direction: less wall-of-text, more community

Stated 2026-09-16, and it reframes the phases below. The complaint about TLDR —
*"so much text"* — applies to Tributary as it stands: a single column of
title-plus-paragraph cards is the same object with a different masthead. The
feed should be **fun to use**, and the point is to **connect the community**,
not just to deliver links. Also: **this must not stay AI-only in the long run.**

Three findings from reading the current code, cheapest first:

1. **Images are already there and thrown away.** `media_url` is fetched by the
   RSS and HF adapters, stored, and exported (`export.py:57`) — and
   `web/index.html` never renders an `<img>`. Card art is a frontend-only
   change against data already on disk.
2. **The community signal is collected and then dropped at the export
   boundary.** HN carries `points` and `num_comments`, HF carries `upvotes`,
   all in item `metadata`. `feed.py:276` selects `i.metadata`, but neither
   `StoryCard` nor `export.py` exposes it, so nothing reaches the page.
   Surfacing "312 points · 88 comments →" next to a story, linked to the thread
   where the argument is actually happening, is social proof and a way *into*
   the community — and it needs no backend, no accounts, no moderation.
3. **In-app community is parked** — still being thought about. Comments,
   accounts and votes of our own would mean a writable backend, which ends the
   static-Pages, zero-cost model (see "How the two deployments share one
   frontend"). Not the ask right now.

### What "community" means here: the ripple, not a chat room

Clarified 2026-09-16. The wanted thing is **what happened because of a story** —
the projects people started after the news, the arguments about it, the
write-ups and the video takes. A story is not the announcement; it is the
announcement plus its wake.

**This is already the data model, and that is the surprise.** `cluster.py:44-49`
gives every item in a story a role — `seed`, `paper`, `code`, `video`,
`discussion`, `coverage`. A repo citing a paper's arXiv ID joins that paper's
story as `code`; an HN thread linking an announcement joins it as `discussion`.
`feed.py:73-88` already folds those counts into `1 paper · 2 repos · 1
discussion · 3 sources`. The ripple is computed on every run today.

Three gaps between that and the product wanted, cheapest first:

1. ~~**The wake is invisible while browsing.**~~ **Done 2026-09-17.** The story
   sheet always did group items by role into labelled, clickable sections
   (`openStory`) — an earlier revision of this file claimed otherwise and was
   wrong. What was actually missing was on the feed itself, and is now fixed:
   role counts render as colour-coded chips instead of one line of grey text,
   vote and comment counts reach the page at all, stories and their items show
   the art and blurbs that were already being fetched. See "Shipped" below.
2. **Nothing discovers reactions.** **Partly addressed 2026-09-17** via Hugging
   Face; see "Shipped" and "Why not GitHub repo search" below. `sources/github.py`
   still only polls ten hardcoded repos for *releases* and cannot find a new
   project built on a story. Reddit would cover argument rather than artefacts
   and is still blocked on API approval — worth requesting early (see Later
   phases).
3. **No time axis.** Items cluster inside a 14-day window, but nothing orders a
   story as announcement → what followed. The shape over time is the
   interesting part and is currently invisible.

### Shipped 2026-09-17

- **Role chips.** The wake of a story renders on the card as coloured chips
  (`1 paper · 1 repo · 1 discussion`), using the per-kind palette already in
  `:root`. Counts come from the items the bundle already carried, so this cost
  no new backend query. `seed` earns no chip: it is the announcement, not a
  reaction to it.
- **Community counts.** `export._engagement` lifts votes and replies out of an
  item's metadata blob, normalising HN `points`/`num_comments` and HF `upvotes`
  onto one shape so the page never learns which adapter it is reading. A story
  shows its loudest thread; each item shows its own. This is the first time
  that signal has left the database.
- **Art and blurbs.** `media_url` was fetched, stored and exported all along
  and no `<img>` existed to show it — now a card thumbnail and a detail hero.
  Broken hotlinks remove themselves rather than leaving a grey box. Story items
  carry a truncated summary, so the drill-down is no longer a list of bare
  titles.
- Verified in Chromium at phone width in both themes, against a real bundle
  built by `build_bundle` rather than hand-written JSON. 192 tests, lint clean.
  **This retires the "UI never visually verified" debt** below: the browser
  libs it was blocked on are present in the Claude Code web sandbox, with
  Playwright pointed at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.

Known rough edge, pre-existing and untouched: at phone width the header's
"N stories · updated Xm ago" wraps under the brand and crowds the tabs.

### Shipped 2026-09-17, part two: finding what a paper set off

- **`arxiv:` tags become a join.** The hub tags a repo `arxiv:2609.11234` when
  its card cites that paper. `_build_model` now lifts the first such tag into
  `metadata["arxiv_id"]`, which `identity` already treats as a strong
  identifier — so the model lands in that paper's story through tier-1
  clustering with no text matching and no changes to `identity.py`.
- **A `cites_paper` option**, and a new `HF New Implementations` source using
  `sort = "createdAt"`. Newest-first over the hub is mostly daily requants and
  fine-tunes; keeping only repos that cite a paper is what turns that firehose
  into "someone implemented this". The hub has no server-side filter for "has
  any arxiv tag", so it runs client-side and `limit` is spent *before* it —
  hence 300.
- **`role_for` now asks whether an item opens a story, not whether the story
  holds a `seed` role.** Those are different questions: a paper-led story holds
  the role `paper` and no seed at all, so everything joining one was labelled a
  second seed. Since seed is the one role that means "the announcement" and
  therefore earns no chip, **a paper's own coverage was invisible in its wake**.
  This also drops a per-item query from `add_to_story`.

**Roles are stored, not recomputed**, so existing stories keep the old labels
until `trib cluster --reset` rebuilds them. Worth doing once to get the
coverage chips on stories already in the database.

**One unverified assumption:** `sort = "createdAt"` is the hub's sort key by
name. It could not be checked from the sandbox this was written in, where
`huggingface.co` is blocked by the egress proxy — the adapter's parsing is the
existing proven path, so this is the only new guess. Confirm with
`trib fetch --source "HF New" --dry-run` on a machine that can reach the hub.

### Why not GitHub repo search

Tried first, and rejected on evidence rather than taste — worth not
rediscovering:

- A bare arXiv id matches nothing: repo search does not index READMEs without
  `in:readme`.
- `2305.14314 in:readme created:>2026-06-01` returns roadmaps, awesome-lists
  and course notes (`llm-systems-engineering-roadmap`, `ai-system-design`,
  `FM-os: curated repos, courses, papers`). Those cite hundreds of papers each
  and are created constantly, so they match *every* paper story and would
  flood each one with the same handful of junk.
- The genuine implementation, `artidoro/qlora`, is excluded by that same date
  filter: it was created in 2023, long before the wake window.
- The noise cannot be filtered in the query — GitHub rejects more than five
  boolean operators, so `NOT awesome NOT roadmap …` does not fit.

The structural problem is that lists cite everything, so text matching cannot
separate "built on" from "mentions". If it is ever worth revisiting, the
discriminator has to run client-side: fetch a candidate's README and count
distinct arXiv citations (an implementation cites one or two, a list cites
dozens). That needs a DB-reading pipeline stage rather than a `Source`, since
adapters deliberately never touch the database. HF's tags are the same signal
already structured, which is why they came first.

**Beyond AI.** The architecture is already close to domain-general: sources and
the whole triage profile are `config.toml`, and the pipeline never mentions a
subject. What is AI-specific is (a) that config, (b) the arXiv/HF identifier
extractors in `identity.py`, which simply find nothing on other subjects and
cost nothing, and (c) the framing. So "a Tributary for X" is mostly a matter of
a second profile, not a rewrite — the open question is whether one instance
carries several subjects at once (topics become the spine, and the filters in
item 3 below become the primary navigation) or whether each subject is its own
deployment.

The topics work below is not superseded by this — it is the same feature seen
from the other end. Topics are what make filters, drill-down and a
multi-subject feed possible.

## Shipped 2026-09-17, part three: topics and filters

Items 1 and 3 of the list below, the ones your notes kept coming back to.

- **`topics.py`** — the same machinery as triage aimed at a different question:
  not "is this worth keeping" but "what is it about". Cosine similarity against
  embedded prose, so **still no API key**; the note further down about dynamic
  topics not needing an LLM turned out to be exactly right.
- **Topics attach to stories, not items.** A story is what you browse and
  filter, and its members are by construction about the same thing, so it is
  scored once — as the *mean* of its members' vectors, re-normalised, rather
  than whichever item happened to arrive first.
- **A spine in `config.toml`** (`[topics]` plus `[[topics.spine]]`): models,
  agents, safety, running it yourself, research, building with it, industry. A
  story takes every topic it clears up to `max_per_story`, so overlapping
  descriptions are fine. Changing the spine re-labels the back catalogue via
  the same fingerprint trick triage uses, and a `topic_assigned` marker keeps
  off-spine stories from being rescored every run.
- **Filter row in the page**, built from the stories actually loaded — so a
  filter never leads to an empty feed, and a topic nothing was written about
  this week simply does not appear. Selection persists in `localStorage`
  alongside the view.
- **`trib topics --stats`** for tuning: a topic holding almost everything is
  worded too broadly, one holding nothing is too narrow or is not something the
  sources cover.
- Also fixed the header, which wrapped "N stories · updated Xm ago" mid-sentence
  at phone width and read as a bug; it is a stacked subtitle now.

**Judged on live data the same day and found wanting** — see "Topics as an
ontology" below. 1442 of 1499 stories took a label, the spine read as
source-driven rather than subject-driven, and it turned out to be only the
category level of a three-level problem. The filter row stays: filtering by
topic is the entire point of the product. The spine is what needs replacing.

**Nothing in the spine is AI-specific by design.** Replacing it and the triage
profile is most of what pointing Tributary at another subject involves — which
is the "not only AI" thread from the direction section, now actually load
bearing rather than aspirational.

Still open from that list: **"more like this"** (item 2) — nearest-neighbour
over vectors already on disk, now much easier since a story has a centroid.

## Topics as an ontology

Worked out 2026-09-17. This supersedes the flat spine shipped the same day, and
it is the core of the product rather than a feature of it: **the whole idea is
topics, and topics are an ontology.**

### The flat spine conflated three different things

| Level | Example | How it should be made |
|---|---|---|
| **Category** | "ai models", "frontier models", "new model releases" | Few, stable, hand-made. Hardcoding is correct here |
| **Entity** | "OpenAI", "Astra", "Opus", "Hugging Face" | Extracted, then accepted by a human. **The missing layer** |
| **Event** | "the huggingface incident", "Astra 6.1 released" | Already exists — it is a story |

The spine built today is only level 1, flattened. That is why it felt
"hardcoded from specific sources": it was the one level where hardcoding is
fine, doing the job of the two levels where it is not.

**A tree will not hold.** The huggingface incident belongs under Astra *and*
under OpenAI. This is a graph, not a hierarchy — `story_topics` is already
many-to-many, `topics.parent_id` gives the browsing skeleton, and an event can
hang off several entities at once.

### How Reddit actually does it, and why it cannot be copied

Subreddits are user-created, the namespace is **flat**, and there is no
hierarchy at all: r/MachineLearning and r/LocalLLaMA are unrelated in the data
model. Apparent relatedness is convention — sidebar links, naming, and
multireddits, which are a personal grouping rather than a shared tree. Flair is
the only real sub-level, defined per subreddit by moderators.

The load-bearing part is that **a human classifies at submission time**. Someone
decides a link belongs in r/LocalLLaMA by posting it there. No algorithm assigns
posts to subreddits. Tributary has no submitters, so classification has to be
automatic — the same shape of problem wearing different clothes.

### The way through: propose, then accept

Extraction proposes entity candidates; a human accepts, renames or rejects them;
accepted entities become followable and slot under a category. That recovers
Reddit's human-decides property without needing a crowd, and it is how a topic
ends up called whatever people actually call it. For now Sebastian is that
human — "I can be the person to accept the topics you suggest" — and the same
mechanism generalises to users later if this ever has any.

**The schema has been waiting for this since the first commit**, entirely
unused — no Python references any of it:

```sql
entities      (kind: model|org|person|tool|paper|dataset, name, aliases)
item_entities / story_entities
follows       (target_kind: topic|entity|source, weight)
```

`identity.py` is already a partial entity extractor: HF orgs and model slugs,
GitHub repos, arXiv ids. But it writes to `identifiers`, which exists to *join*
items into stories. The same extraction pointed at `entities` is for *following*.
Same signal, different destination.

### Gossip is content, not noise

"New Astra 6.1 speculations and release date… this is what I want to read about
as well, the gossip." Speculation, leaks and the argument around an incident are
wanted material. Two consequences:

1. Triage must not treat rumour and speculation as low quality.
2. **The entity is the right bundle for this, not the event.** "Astra 6.1
   speculation" and "Astra 6.1 released" are different happenings about the same
   thing. Following the *entity* collects both; clustering them into one story
   would be wrong, because they are not the same event. This is the clearest
   argument that the fix for "it has to be bundled together" is the entity
   layer, **not** a lower merge threshold.

### Open questions

- **Ranking candidates for review.** Frequency across stories is the obvious
  first cut, and it is reliable but late: a brand-new name is interesting on day
  one and only frequent by day three. Being first is most of the value.
- **Aliases.** "Astra", "Astra 6", "Astra 6.1", `astra-6.1-flash` are one thing.
  The `aliases` column exists; unclear whether a human fills it at accept time
  or whether near-matches are proposed automatically.
- **Retroactivity.** Accepting an entity should presumably re-label the back
  catalogue, the way changing the triage or topic profile already does.
- **Categories**: hand-written, or proposed like entities?
- **Where review happens** — a CLI queue (`trib entities --review`) is the
  cheapest, but accepting topics from the phone is where it would actually get
  done.

## The original list: topics, drill-down and filters

This is the gap between what exists and what was originally described. All of it
is local; none of it needs an API key (see the correction below).

1. **Topic assignment.** A stable spine (models, agents, safety, local
   inference, research, industry) *plus* emergent topics that form around
   whatever is actually happening that week. Score each story against topic
   descriptions exactly as triage scores relevance; cluster the leftovers.
   Fills the `topics` / `story_topics` tables, which exist and are empty.
2. **"More like this" on a story page.** Currently a story shows only its own
   items. Related stories on the same subject is a nearest-neighbour lookup over
   vectors already on disk — this is the "I want to keep reading" path.
3. **Filters in the UI.** Topic, kind, source, time window. `data.json` already
   carries every field these need, so this is mostly frontend.
4. **README cleanup.** It reads as a build journal of design decisions. It
   should say what the tool is and how to run it; the reasoning can move to a
   separate document or go.

**Do these as one piece of work.** "Related info on the same topic" and "the
/r/ topics I'm missing" are the same feature underneath: assign stories to
subjects once, and both the drill-down and the filters fall out of it.

### Correction worth carrying forward

Dynamic topic clustering does **not** need an LLM. It is vector clustering over
embeddings already computed and stored. The only genuinely LLM-shaped work in
this project is "why this matters" one-liners and YouTube transcript claim
extraction — both optional, neither started.

## Done

| Phase | Status |
|---|---|
| 0 — schema, config, fetch pipeline, RSS, CLI | complete |
| 1 — HN/arXiv/HF/GitHub adapters, local embeddings, triage gate | complete |
| 2 — identifier extraction, 3-tier clustering, calibration, feed ranking | complete |
| 3 — FastAPI, web app, PWA, `trib serve` | complete, verified live |
| 3.5 — static export, prune, GitHub Pages + Actions | complete, deployed |

### How the two deployments share one frontend

Every read endpoint is a slice of a database that only changes when the pipeline
runs, so the whole API collapses into one `data.json` bundle. The server serves
it live at `/data.json`; `trib export` writes the identical shape to disk. The
page cannot tell the difference. Per-device state (seen, saved, dismissed) lives
in `localStorage` — it is a preference, not data, and a static host has nowhere
else to put it.

The database is **not** committed; it lives in the Actions cache, because git
stores each version of a binary in full. A cache miss is self-healing: the run
rebuilds from the sources.

## Later phases

- **4** — YouTube/podcast transcripts, claim extraction, timestamp deep-links.
  The differentiated feature. **Will not work on GitHub Actions** — runners are
  cloud IPs and YouTube blocks them. Needs a residential connection: this
  machine, or a Pi at home pushing to the same repo.
- **5** — notes/takes layer, interaction-learned ranking, "catch me up" digest.
- **6+** — Reddit (needs a manual API approval ticket; self-service registration
  closed late 2025 — worth requesting early), podcasts, multi-user.

## Calibrated values — measured, don't guess these again

```
cluster.MERGE_THRESHOLD = 0.92    # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW   = 0.86
cluster.WINDOW_DAYS     = 14
triage threshold        = 0.66
```

bge puts *unrelated* text near 0.5, so the usable similarity range is ~0.5–1.0.
Positive and hard-negative distributions genuinely overlap (matches as low as
0.888; different same-week papers up to 0.944) — 0.92 honours "a wrong merge
costs more than a missed link". Re-run `trib calibrate` as the corpus grows.

## Source candidates

### TLDR AI — wanted, but not a plain RSS entry

Asked for 2026-09-16. Researched, not implemented.

The official feed follows `https://tldr.tech/api/rss/<newsletter>` (`/tech`
confirmed; `/ai` inferred from that pattern and **not verified** — tldr.tech is
blocked by this sandbox's egress proxy, so check it before trusting it).

**It publishes one entry per daily issue, not one per story** — a digest of ~10
unrelated links pointing at the whole issue page. Adding it as `kind = "rss"` is
four lines of config and would go wrong in three ways:

- `embeddings.py` embeds title + summary truncated to 2000 chars, so ten
  unrelated blurbs average into one meaningless vector and triage scores noise.
- `identity.extract` reads identifiers out of free text, so one digest citing
  ten arXiv IDs and GitHub repos attaches all ten to itself; tier-1 clustering
  then welds those ten unrelated stories into one mega-story. `MAX_FANOUT`
  does not catch this — it only fires above 8 items per value, and here each
  value is held by 2.
- Consecutive issues are near-identical title strings inside the 14-day
  window, so they risk tier-2 merging into one rolling story.

Doing it properly is a two-stage adapter shaped like `sources/github.py`
(fetch the feed, then one request per issue page, emit one `RawItem` per story
with a stable `external_id` such as `f"{issue_id}#{n}"`). That needs an HTML
parser — the repo has none today, only `re` and `feedparser`. The payoff is
real beyond the source itself: TLDR's hand-written one-line blurbs are exactly
the missing summaries in the 42%-no-summary debt below, and it is the
HTML-scrape adapter `config.toml` already anticipates for Anthropic.

Caveat before scheduling it: tldr.tech may block cloud IPs the way Substack
blocks Import AI on Actions. Verify with `trib fetch --source TLDR --dry-run`
both locally and on a run.

Note the tension with the direction section: TLDR is a secondary aggregator of
things already arriving via TechCrunch, HN, arXiv and HF, and "it is so much
text" was the original complaint about it. Its value here is the blurbs and the
editorial judgement, not the coverage.

## Known debt

- **42% of feed cards have no summary at all** — just a title. Worst for
  releases, models and HN threads (`ggml-org/llama.cpp b11003` says nothing).
  Fix by fetching the linked page's description / HF model card / release notes.
  Seen live 2026-09-17 and it is worse than the number suggests: the story page
  for `Agnes-AI/Agnes-3.0-Flash` is a title, one item, and nothing else — "I
  want to know what makes this different. And what the reactions are." Both
  halves are missing for the same reason. The hub's *list* endpoint returns no
  description, so the card is a bare repo id; fetching the model card would fix
  it. The reactions are missing because nothing clustered to it.
- **Podcasts: links wanted, summaries wanted more.** Not started, and not in any
  phase below as a near-term item. Links are an RSS adapter away, since podcast
  feeds are RSS. Summaries are the genuinely hard half — that is transcription
  plus summarisation, the same Phase 4 problem as YouTube, and the one place an
  API key would actually buy something.
- `cli.py` is ~900 lines — by far the largest file, first thing to split.
- **Import AI returns HTTP 403 on GitHub Actions** — Substack blocks those IPs.
  Works fine locally. Either drop it from `config.toml` or accept the gap; it is
  already surfaced in the UI's broken-sources banner.
- UI never visually verified — blocked on sudo-installed browser libs:
  `libnspr4 libnss3 libasound2t64 libatk-bridge2.0-0 libatspi2.0-0 libgbm1 libxkbcommon0`.
- `trib status` (db path, size, counts, last fetch) — suggested, not built.
- Scheduled workflows are disabled after 60 days of repo inactivity (email first;
  any push resets it).

## Current setup

Database at `./tributary.db` in the project. Relative `db_path` resolves against
`config.toml`, not the cwd, so `trib` works from cron or any directory.

Cron in WSL works (`systemd=true`, `cron.service` enabled) if you ever want local
scheduling; a Windows Task Scheduler entry running `wsl.exe -e <path>/trib run`
would cover post-reboot.

## Sebastian notes

The README includes a lot of different design choices and stuff that is not
relevant anymore since it is published on pages. It needs to be cleaned up. I
realise that it is not finished, but I am missing the different topics I was
wanting in the beginning. So when I go to one link, there should be lots of
related info on the same topic. Or comments on that event, like releases of nee
models. I want latest reviews etc. The reddit /r topics is what I am missing.
Now it just a long feed. I want to continue reading if I find something
interesting. I am also missing some sort of filter, this might be related to the
/r topics I am wanting. But I would like more general filters as well. an idea is
that the filter is dynamic as well and can be based on latest happenings by
clustering events and news but that would need AI I presume which i do not want
yet since I do not have an api key
