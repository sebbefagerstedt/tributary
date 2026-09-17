# Tributary — state and remaining work

Live at **https://sebbefagerstedt.github.io/tributary/**, rebuilt every three
hours at minute 17. 254 tests passing, lint clean.
**Zero LLM/API usage — everything local and free.**

This file is for what is *not* built and what should not be rediscovered. The
history of what shipped is in git; only the decisions that still constrain
future work are kept here.

---

## What it is for

From the notebook page this started as, transcribed 2026-09-17. Kept because
the roadmap records what got built, which is not the same as what the thing
was for.

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

| From the page | Where it stands |
|---|---|
| Mixed news and social | Built, except Reddit (API approval) |
| Facts from articles *plus the people commenting* | Built — the wake |
| A subject channel, `r/AI` | Built — topics |
| One event, everything about it | Built — the story page |
| Start with news, to gather | Built |
| **Verifierad (mer trovärdig)** | **Not built** |
| **reddit / tiktok / youtube, for quick info** | **Not built** |
| Prio/**börja** med AI | Config-deep, not code-deep |

**The anti-doomscroll motive is a constraint, not an origin story.** It argues
against the engagement mechanics that would be the obvious way to make a feed
moreish. The README already says the ranking is deliberately not an engagement
metric — keep those two agreeing.

### What "community" means here: the ripple, not a chat room

The wanted thing is **what happened because of a story** — the projects people
started after the news, the arguments about it, the write-ups and the video
takes. A story is not the announcement; it is the announcement plus its wake.

**This is already the data model.** `cluster.py` gives every item in a story a
role — `seed`, `paper`, `code`, `video`, `discussion`, `coverage`. A repo citing
a paper's arXiv ID joins that paper's story as `code`; an HN thread linking an
announcement joins it as `discussion`. The ripple is computed on every run, and
renders as coloured chips on the card and grouped sections on the story sheet.

In-app community — comments, accounts, votes of our own — is parked rather than
rejected. It would mean a writable backend, which ends the static-Pages,
zero-cost model.

---

## What is left to build

### Ready to start

- **`cli.py` is ~900 lines.** By far the largest file; first thing to split.
- **Bare-title cards.** `describe.py` fixed the Hugging Face case by fetching the
  model card. Still open for HN threads and GitHub releases
  (`ggml-org/llama.cpp b11003` says nothing), which need the linked page's
  description and therefore **the HTML-scrape adapter that does not exist yet**.
  That adapter is the blocker shared with TLDR and with `config.toml`'s
  Anthropic entry — building it once unlocks three things.
- **Podcast links.** Podcast feeds are RSS, so this is an adapter and a config
  block. Summaries are the wanted half and are Phase 4, not this.
- **"More like this" on a story page.** Nearest-neighbour over vectors already on
  disk, and much easier now that a story has a centroid. This is the "I want to
  keep reading" path.
- **`trib status`** (db path, size, counts, last fetch) — suggested, not built.
- **README cleanup.** It reads as a build journal of design decisions. It should
  say what the tool is and how to run it; the reasoning moves here or goes.

### Needs a decision, not code

- **Topic names.** Flagged as not good enough. Needs `/suggest-topics` run where
  the database lives — it cannot run in a cloud session, because `tributary.db`
  is gitignored and the skill's `data.json` fallback is blocked by the egress
  proxy. **That fallback is itself a bug worth fixing.**
- **The topic threshold is too loose.** 1442 of 1499 stories took a label. A
  topic holding almost everything is worded too broadly; needs
  `trib topics --stats` against real data to retune.
- **Import AI**: drop it from `config.toml` or accept the gap. It returns HTTP
  403 on Actions because Substack blocks those IPs, and works fine locally.
- **MarkTechPost**: `unparseable feed (not well-formed, invalid token)`. Unlike
  Import AI this is not an IP block — the feed itself is malformed, so either
  the adapter tolerates it or the source goes.

### Designed, deliberately not built

- **The entity layer.** Worked out in full below. De-prioritised once topics were
  allowed to die, since a short-lived topic covers some of the same ground.
- **"Verifierad (mer trovärdig)".** Corroboration exists as a *ranking* input —
  `SOURCE_BONUS` lifts a story several sources covered, and the card shows a
  "4 sources" chip — but the app never makes the claim. Saying "three
  independent sources agree" out loud, and knowing when they are not independent
  (a wire rewrite is not confirmation), is a different feature from nudging a
  score.
- **A feed you can get through at TikTok speed.** "Combo reddit, tiktok, youtube
  … för snabb info", read with "vill ta bort mitt sociala medier beroende", is
  not a source list: it is the *format* those apps are good at — fast, scannable,
  mostly not prose — aimed at something worth reading. Card art and chips are a
  step. Nothing here has been designed against that target yet.
- **No time axis.** Items cluster inside a 14-day window, but nothing orders a
  story as announcement → what followed. The shape over time is the interesting
  part and is currently invisible.
- **Nothing discovers reactions.** `sources/github.py` polls ten hardcoded repos
  for *releases* and cannot find a new project built on a story. Hugging Face's
  `arxiv:` tags partly cover artefacts; Reddit would cover argument.

### Blocked on something external

- **Phase 4 — YouTube/podcast transcripts, claim extraction, timestamp
  deep-links.** The differentiated feature. **Will not work on GitHub Actions** —
  runners are cloud IPs and YouTube blocks them. Needs a residential connection:
  the WSL machine, or a Pi at home pushing to the same repo.
- **Reddit** needs a manual API approval ticket; self-service registration closed
  in late 2025. **Worth requesting early** — it is the one item here whose lead
  time is measured in weeks.
- **Phase 5** — notes/takes layer, interaction-learned ranking, "catch me up"
  digest.
- **Phase 6+** — multi-user.

---

## Decisions worth not rediscovering

### Topics are an ontology, and the shipped spine is one level of it

**The whole idea is topics, and topics are an ontology.** The flat spine
conflates three different things:

| Level | Example | How it should be made |
|---|---|---|
| **Category** | "ai models", "frontier models", "new model releases" | Few, stable, hand-made. Hardcoding is correct here |
| **Entity** | "OpenAI", "Astra", "Opus", "Hugging Face" | Extracted, then accepted by a human. **The missing layer** |
| **Event** | "the huggingface incident", "Astra 6.1 released" | Already exists — it is a story |

What is built is level 1, flattened. That is why it read as "hardcoded from
specific sources": it was the one level where hardcoding is fine, doing the job
of the two levels where it is not.

**A tree will not hold.** The huggingface incident belongs under Astra *and*
under OpenAI. This is a graph: `story_topics` is already many-to-many,
`topics.parent_id` gives the browsing skeleton, and an event can hang off
several entities at once.

**Reddit cannot be copied.** Subreddits are user-created, the namespace is flat,
and there is no hierarchy in the data model — r/MachineLearning and r/LocalLLaMA
are unrelated. Apparent relatedness is convention: sidebar links, naming, and
multireddits, which are personal rather than shared. Flair is the only real
sub-level. The load-bearing part is that **a human classifies at submission
time**; no algorithm assigns posts to subreddits. Tributary has no submitters,
so classification has to be automatic — the same problem wearing different
clothes.

**The way through is propose, then accept.** Extraction proposes entity
candidates; a human accepts, renames or rejects them; accepted entities become
followable and slot under a category. That recovers Reddit's human-decides
property without needing a crowd, and it is how a topic ends up called whatever
people actually call it. Sebastian is that human for now, and the mechanism
generalises to users later.

**The schema has been waiting since the first commit**, entirely unused — no
Python references any of it:

```sql
entities      (kind: model|org|person|tool|paper|dataset, name, aliases)
item_entities / story_entities
follows       (target_kind: topic|entity|source, weight)
```

`identity.py` is already a partial entity extractor — HF orgs and model slugs,
GitHub repos, arXiv ids — but it writes to `identifiers`, which exists to *join*
items into stories. The same extraction pointed at `entities` is for
*following*. Same signal, different destination.

Open questions, if this is picked up:

- **Ranking candidates for review.** Frequency across stories is the obvious
  first cut, and it is reliable but late: a brand-new name is interesting on day
  one and only frequent by day three. Being first is most of the value.
- **Aliases.** "Astra", "Astra 6", "Astra 6.1", `astra-6.1-flash` are one thing.
  The `aliases` column exists; unclear whether a human fills it at accept time
  or whether near-matches are proposed automatically.
- **Retroactivity.** Accepting an entity should presumably re-label the back
  catalogue, the way changing the triage or topic profile already does.
- **Categories**: hand-written, or proposed like entities?
- **Where review happens** — a CLI queue (`trib entities --review`) is cheapest,
  but accepting topics from the phone is where it would actually get done.

### Gossip is content, and it argues for entities rather than looser clustering

Speculation, leaks and the argument around an incident are wanted material, not
noise. Two consequences:

1. Triage must not treat rumour and speculation as low quality.
2. **The entity is the right bundle for this, not the event.** "Astra 6.1
   speculation" and "Astra 6.1 released" are different happenings about the same
   thing. Following the *entity* collects both; clustering them into one story
   would be wrong, because they are not the same event.

Measurement backs this up: 18 near-misses against 3 similarity merges out of 829
items means the 0.86–0.92 band is nearly empty, so **lowering the merge
threshold would buy almost nothing**. It is the source mix, not the threshold.

### Topics have a lifecycle, and dying is the cheap part

A topic is not permanent taxonomy: it is created when something starts happening
and **dies when nobody looks at it any more**. Dying is dormancy, not deletion —
the entry stays in the spine.

That needs almost no code, because the page already behaves this way: the filter
row is built from the stories actually loaded, so a topic with nothing recent
disappears on its own and returns by itself if the subject does.
`trib topics --stats` reports last activity per topic so dormancy is visible.

Deleting a dormant topic would be actively worse: removing an entry changes the
spine fingerprint, which drops every `story_topics` row and re-labels the whole
corpus. Surviving topics are re-derived, so nothing permanent is lost, but it is
pointless churn for something that was already invisible. **Removal is for
topics that were a mistake** — never matched anything, worded so broadly it
swallows the feed, duplicates another — not for topics that are finished.

A long tail of dormant topics is the expected steady state, which is what makes
proposing new ones cheap: a badly named topic goes quiet and stops mattering, at
the cost of one config line.

### Why not GitHub repo search

Tried first and rejected on evidence rather than taste:

- A bare arXiv id matches nothing: repo search does not index READMEs without
  `in:readme`.
- `2305.14314 in:readme created:>2026-06-01` returns roadmaps, awesome-lists and
  course notes (`llm-systems-engineering-roadmap`, `ai-system-design`,
  `FM-os: curated repos, courses, papers`). Those cite hundreds of papers each
  and are created constantly, so they match *every* paper story and would flood
  each one with the same junk.
- The genuine implementation, `artidoro/qlora`, is excluded by that same date
  filter: it was created in 2023, long before the wake window.
- The noise cannot be filtered in the query — GitHub rejects more than five
  boolean operators, so `NOT awesome NOT roadmap …` does not fit.

The structural problem is that lists cite everything, so text matching cannot
separate "built on" from "mentions". If it is ever revisited, the discriminator
has to run client-side: fetch a candidate's README and count distinct arXiv
citations (an implementation cites one or two, a list cites dozens). That needs
a DB-reading pipeline stage rather than a `Source`, since adapters deliberately
never touch the database.

**Hugging Face's `arxiv:` tags are the same signal already structured**, which is
why they came first. `_build_model` lifts the first such tag into
`metadata["arxiv_id"]`, which `identity` already treats as a strong identifier —
so a model lands in its paper's story through tier-1 clustering with no text
matching. The `cites_paper` option keeps only repos that cite a paper, which is
what turns newest-first over the hub (mostly daily requants and fine-tunes) into
"someone implemented this". The hub has no server-side filter for "has any arxiv
tag", so it runs client-side and `limit` is spent *before* it — hence 300.

### TLDR AI is a digest, not a feed

Researched, not implemented. The official feed follows
`https://tldr.tech/api/rss/<newsletter>` (`/tech` confirmed; `/ai` inferred from
that pattern and **not verified** — tldr.tech is blocked by the sandbox's egress
proxy).

**It publishes one entry per daily issue, not one per story** — a digest of ~10
unrelated links pointing at the whole issue page. Adding it as `kind = "rss"` is
four lines of config and would go wrong in three ways:

- `embeddings.py` embeds title + summary truncated to 2000 chars, so ten
  unrelated blurbs average into one meaningless vector and triage scores noise.
- `identity.extract` reads identifiers out of free text, so one digest citing ten
  arXiv IDs and GitHub repos attaches all ten to itself; tier-1 clustering then
  welds those ten unrelated stories into one mega-story. `MAX_FANOUT` does not
  catch this — it only fires above 8 items per value, and here each value is
  held by 2.
- Consecutive issues are near-identical title strings inside the 14-day window,
  so they risk tier-2 merging into one rolling story.

Doing it properly is a two-stage adapter shaped like `sources/github.py` (fetch
the feed, then one request per issue page, emit one `RawItem` per story with a
stable `external_id` such as `f"{issue_id}#{n}"`). That needs the HTML parser the
repo does not have. The payoff is real beyond the source: TLDR's hand-written
one-line blurbs are exactly the missing summaries in the bare-title debt.

Caveat before scheduling it: tldr.tech may block cloud IPs the way Substack
blocks Import AI. Verify with `trib fetch --source TLDR --dry-run` both locally
and on a run. Note the tension with the direction above — TLDR is a secondary
aggregator of things already arriving via TechCrunch, HN, arXiv and HF, and "it
is so much text" was the original complaint about it. Its value here is the
blurbs and the editorial judgement, not the coverage.

### Dynamic topics do not need an LLM

Worth carrying forward, because the assumption blocked this work for a while.
Topic clustering is vector clustering over embeddings already computed and
stored. The only genuinely LLM-shaped work in this project is "why this matters"
one-liners and YouTube transcript claim extraction — both optional, neither
started. **Naming** a cluster is the human step, which is what
`.claude/skills/suggest-topics` exists for.

### Beyond AI

The architecture is already close to domain-general: sources and the whole
triage profile live in `config.toml`, and the pipeline never mentions a subject.
What is AI-specific is (a) that config, (b) the arXiv/HF identifier extractors in
`identity.py`, which simply find nothing on other subjects and cost nothing, and
(c) the framing. Nothing in the topic spine is AI-specific by design.

So "a Tributary for X" is mostly a second profile, not a rewrite. The open
question is whether one instance carries several subjects at once — topics become
the spine and filters become the primary navigation — or whether each subject is
its own deployment.

### Calibrated values — measured, don't guess these again

```
cluster.MERGE_THRESHOLD  = 0.92   # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW    = 0.86
cluster.WINDOW_DAYS      = 14
triage threshold         = 0.66
store.MAX_ITEM_AGE_DAYS  = 60     # must match `trib prune --days`
```

bge puts *unrelated* text near 0.5, so the usable similarity range is ~0.5–1.0.
Positive and hard-negative distributions genuinely overlap (matches as low as
0.888; different same-week papers up to 0.944) — 0.92 honours "a wrong merge
costs more than a missed link". Re-run `trib calibrate` as the corpus grows.

---

## How it runs

### The two deployments share one frontend

Every read endpoint is a slice of a database that only changes when the pipeline
runs, so the whole API collapses into one `data.json` bundle. The server serves
it live at `/data.json`; `trib export` writes the identical shape to disk. The
page cannot tell the difference. Per-device state (seen, saved, dismissed) lives
in `localStorage` — it is a preference, not data, and a static host has nowhere
else to put it.

The database is **not** committed; it lives in the Actions cache, because git
stores each version of a binary in full. A cache miss is self-healing: the run
rebuilds from the sources.

### Local setup

Database at `./tributary.db` in the project. Relative `db_path` resolves against
`config.toml`, not the cwd, so `trib` works from cron or any directory.

Cron in WSL works (`systemd=true`, `cron.service` enabled) if you ever want local
scheduling; a Windows Task Scheduler entry running `wsl.exe -e <path>/trib run`
would cover post-reboot.

Scheduled workflows are disabled after 60 days of repo inactivity (email first;
any push resets it).

### The pipeline was churning, not accumulating — fixed 2026-09-17

Kept because it explains `MAX_ITEM_AGE_DAYS` and because the diagnosis is the
reusable part. Found by reading a scheduled run's log rather than the site:

```
Cache restored from key: tributary-db-7     <- the cache was fine
fetch    1298 new, 0 updated across 20 sources
Deleted  1295 items and 823 empty stories
```

**Zero updated** was the tell. On a restored database the arXiv papers fetched
three hours earlier should come back as updates; zero means last run's items were
gone. Feeds that serve their whole archive have no cursor and no useful
validators, so they re-delivered years-old entries every run: inserted as new,
embedded (45 seconds of it), triaged, clustered, deleted by the next prune, and
fetched again three hours later, forever.

The fix drops an item older than the retention window at ingest rather than
storing it, so nothing is embedded that the next prune would immediately delete.
An item already stored is exempt — it ages out through prune rather than
vanishing mid-window. Undated items count as current, since plenty of sources
give no date and refusing them would empty the feed.

`trib run` now prints unchanged and too-old counts too. **All-new with nothing
unchanged is the shape of churn rather than of news**, and the old one-line
summary could not show it.

**The schedule was never broken.** A long detour concluded it was, on the
strength of checks that stopped before the run that proved otherwise: the 09:00
window fired at 09:18, an 18-minute delay, which is ordinary. The schedule moved
to minute 17 anyway, which is still worth having, but the reasoning recorded in
that commit message was wrong.

---

## Shipped

| Phase | Status |
|---|---|
| 0 — schema, config, fetch pipeline, RSS, CLI | complete |
| 1 — HN/arXiv/HF/GitHub adapters, local embeddings, triage gate | complete |
| 2 — identifier extraction, 3-tier clustering, calibration, feed ranking | complete |
| 3 — FastAPI, web app, PWA, `trib serve` | complete, verified live |
| 3.5 — static export, prune, GitHub Pages + Actions | complete, deployed |

Since then, all 2026-09-17:

- **The wake made visible** — role chips on the card, vote and comment counts
  reaching the page for the first time (`export._engagement` normalises HN
  `points`/`num_comments` and HF `upvotes` onto one shape), card art and detail
  hero from the `media_url` that was already stored, item blurbs on the story
  sheet.
- **`arxiv:` tags become a join**, the `cites_paper` option, and the
  `HF New Implementations` source.
- **`role_for` asks whether an item opens a story**, not whether the story holds
  a `seed`. Those are different questions: a paper-led story holds the role
  `paper` and no seed at all, so everything joining one was labelled a second
  seed — and since seed is the one role meaning "the announcement", **a paper's
  own coverage was invisible in its wake**. Roles are stored, not recomputed, so
  stories already in the database keep the old labels until
  `trib cluster --reset` rebuilds them; worth running once.
- **Topics** — `topics.py`, a nested spine in `config.toml`, a two-level filter
  row, `trib topics` with `--stats`, `--suggest` and `--reset`, and the
  `suggest-topics` skill for the naming step.
- **Topics as somewhere you go**, not a filter you lose on click — a topic
  banner on the story sheet, chips that navigate, and history/popstate so the
  phone's back button returns to the feed instead of leaving the site.
- **Search**, and a bigger back target.
- **`describe.py`** — fetches the Hugging Face model card for items that arrive
  as a bare title, and fixes the circular import that made `tributary.http`
  impossible to import on its own.
- **The churn fix** above.

Two corrections from that work, both worth keeping:

- **The story sheet always grouped items by role.** An earlier revision of this
  file claimed otherwise, on the strength of a truncated grep. What was missing
  was on the *feed*, not the sheet.
- **`_lead_rank` sorts by kind first**, so a late model release was never able to
  outrank the paper for the lead card. The guard already existed.

---

## Sebastian's notes

Kept verbatim from when they were written, with status added — most of this has
since been built, and what has not is the sharpest statement of what is left.

> The README includes a lot of different design choices and stuff that is not
> relevant anymore since it is published on pages. It needs to be cleaned up.

**Still open** — see README cleanup above.

> I am missing the different topics I was wanting in the beginning. So when I go
> to one link, there should be lots of related info on the same topic. Or
> comments on that event, like releases of nee models. The reddit /r topics is
> what I am missing. Now it just a long feed. I want to continue reading if I
> find something interesting.

**Built** — topics, the topic banner on a story, and topic pages you enter
rather than filters you lose. The remaining piece of "I want to continue
reading" is **"more like this"**, which is still open.

> I am also missing some sort of filter, this might be related to the /r topics I
> am wanting. But I would like more general filters as well.

**Built** — two-level filter rows plus search.

> an idea is that the filter is dynamic as well and can be based on latest
> happenings by clustering events and news but that would need AI I presume which
> i do not want yet since I do not have an api key

**Built, and the assumption was wrong** — `trib topics --suggest` clusters story
centroids and proposes groups with no API key at all. Only the *naming* needs a
human, which is what the `suggest-topics` skill is for.

> I also want links to podcast, and it would be reallt nice with podcast
> summaries

**Open.** Links are an RSS adapter away; summaries are Phase 4 and the one place
an API key would genuinely buy something.

> I only want the most popular news, not everything. Otherwise it is not really
> news.

**Open**, and constrained by a second instruction given at the same time: **do
not cut arXiv** — a new paper is real news whether or not anyone has reacted to
it yet. So this cannot be one global popularity gate, since that is exactly what
would drop arXiv. Per-kind thresholds are the likely shape.
