# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Tributary is a personal AI-news feed: it ingests news, papers, releases and
discussion, groups them into **stories**, labels them, and serves a feed you
scan on a phone — live at https://sebbefagerstedt.github.io/tributary/.
`README.md` is the user-facing how-to. **`NEXT.md` is only the list of what to
build next**; this file holds everything else: the ground rules, how the code
fits together, and the decisions that should not be rediscovered.

## Ground rules

- **No LLM, no API key.** There is no `ANTHROPIC_API_KEY` and the owner does not
  want one yet. When something seems to need a model, check whether the local
  embeddings can do it first — they usually can (dynamic topics turned out to be
  plain vector clustering). The only genuinely LLM-shaped work is "why this
  matters" one-liners and YouTube transcript claim extraction: offer those as
  optional and priced, never on by default.
- **Do not cut arXiv.** A new paper is news whether or not anyone has reacted to
  it. Any popularity gate has to be per-kind, never global.
- **No Substack sources.** Substack blocks GitHub Actions IPs — Import AI returns
  403 on every scheduled run and works fine locally. Every source must behave
  the same wherever `trib` runs.
- **The ranking is not an engagement metric.** The project exists partly to
  replace a social-media habit with "något vettigt"; engagement mechanics that
  make a feed moreish are the thing being avoided.
- **Naming is a person's call.** Topics and entities are proposed by the
  pipeline and accepted by a human, via the `/suggest-topics` skill. Never
  auto-accept a proposal into `config.toml`.
- **Workflow: branch, test, push, merge.** When work is finished and tests pass,
  commit on a branch, push it, merge into `main` with `--no-ff` ("Merge … into
  main"), and push `main`. The workflow runs on every push to `main` and every
  three hours at minute 17, so a merge redeploys the live site.
- **`NEXT.md` is a to-do list, not a journal.** When an entry is built, delete
  it; do not strike it through. History is in git. A decision worth keeping goes
  here, or into the docstring of the code it is about.
- **`src/tributary/sample_config.toml` must be a copy of `config.toml`.**
  `trib init` hands it out, and `tests/test_cli.py` fails if they differ.

## Commands

```bash
uv sync                                   # install, including dev tools
uv run pytest                             # full suite (~20s, no network)
uv run pytest tests/test_topics.py::test_a_weak_best_match_still_wins
uv run pytest -k entities                 # by keyword
uv run ruff check .                       # lint; --fix sorts imports
```

```bash
uv run trib run                # the whole pipeline, as the schedule runs it
uv run trib status             # paths, counts, last fetch, failing sources
uv run trib topics --stats     # stories per topic
uv run trib topics --suggest   # recent clusters, sorted by stories parked on a shelf
uv run trib entities --suggest # recurring names nobody has seeded
uv run trib renewal            # what late arrivals do to the feed's order
uv run trib serve              # web app on :8808; --host 0.0.0.0 for a phone
uv run trib export site        # the static site the workflow publishes
```

Every stage of `run` is also its own command (`fetch`, `describe`, `embed`,
`triage`, `enrich`, `cluster`, `topics`, `entities`). `trib --help` groups them.

The database is `./tributary.db` (gitignored; the deployed copy lives in the
Actions cache). **Open it with `tributary.db.connect()`**, never
`sqlite3.connect()`: vectors live in a sqlite-vec `vec0` table, and a plain
connection fails with `no such module: vec0`.

**Testing the page:** headless Chromium does not start on the dev machine until
`sudo .venv/bin/playwright install-deps chromium` has been run. Until then,
drive `src/tributary/web/index.html` with jsdom, stubbing `fetch` to return an
exported `data.json`.

## Architecture

### The pipeline, in the order `trib run` executes it

| Stage | Module | Does |
|---|---|---|
| fetch | `pipeline.py`, `sources/*`, `store.py` | adapters return items; the store upserts them |
| describe | `describe.py` | finds prose for items that arrived as a bare title |
| embed | `embeddings.py` | fastembed bge-small-en-v1.5, 384-dim, local ONNX |
| triage | `triage.py` | keep or drop by similarity to prose interests |
| enrich | `enrich.py`, `identity.py` | extracts join keys: arXiv ids, DOIs, URLs, repos |
| cluster | `cluster.py` | groups items into stories, and gives each item a role |
| label | `topics.py`, `facets.py`, `entities.py` | topic, facets and entities per story |

The read side runs at request or export time: `feed.py` ranks stories,
`export.py` builds one JSON bundle, `api.py` serves it and `export` writes it to
disk, and `web/index.html` renders it.

### Mechanics that span several files

- **Adapters never touch the database.** An adapter registers itself with
  `@register` in `sources/base.py` and maps `(config, fetch state)` to
  `(items, new state)`. Persistence is all in `store.py`. Anything that needs to
  read stories is therefore a pipeline stage, never a `Source`.
- **Stages are incremental through marker tables** — `described`, `enriched`,
  `topic_assigned` record that an item or story was *attempted*, separately from
  whether it succeeded, so a failure is not retried forever.
- **Config changes re-run the back catalogue through fingerprints** stored in
  `meta`. Editing the triage profile re-triages everything;
  `Config.label_fingerprint()` covers topics, facets *and* entities, so a change
  to any of them re-labels every story. Without this, an edit would only affect
  what arrives afterwards.
- **A story is scored through its centroid** — the re-normalised mean of its
  members' vectors (`topics.centroids`), not its first item.
- **An HN item is the discussion, not the article.** Its URL is the thread; the
  submitted link goes in `metadata.outbound_url` and becomes a join key.
- **One source failing never stops a run.** The error is stored on the source
  and shows in `trib status`, `trib sources` and at the foot of the page, while
  `trib run` still exits non-zero so a scheduler notices.
- **Fetching is idempotent.** Items are keyed on `(source, external_id)`;
  conditional GET turns unchanged feeds into 304s, and a content hash makes a
  re-parse write nothing. Items older than the retention window are dropped at
  ingest rather than stored and then pruned.
- **One bundle, two deployments.** Every read endpoint is a slice of a database
  that only changes when the pipeline runs, so the whole API collapses into
  `data.json`. `trib serve` builds it live, `trib export` writes it to disk, and
  the page cannot tell the difference. Seen, saved and dismissed live in
  `localStorage` — they are preferences, and a static host has nowhere else.
- **The page is one file with no build step.** The JSON bundle is the contract,
  so replacing the frontend later touches nothing else. The service worker
  caches the shell only, never the feed: a stale feed is worse than an honest
  error.
- **The CLI is a package**, one module per `trib --help` panel. Importing a
  module registers its commands, so `cli/__init__.py` fences the import order
  off from the import sorter — alphabetised, it buries `run` mid-list.

### Clustering

Cheapest and most precise first. **Tier 1** is a shared strong identifier —
arXiv id, DOI, canonical URL, hub model, release tag. It is exact, and earns its
place: two HN posts with the same headline scored only 0.888 on embeddings but
joined on their shared outbound URL. A repo is a *weak* identifier, since
hundreds of unrelated items reference one, and any value shared by more than
`MAX_FANOUT = 8` items is a category, not an event. **Tier 2** is embedding
similarity inside a 14-day window. **Tier 3**, LLM adjudication of the ambiguous
band, is designed for and not wired up; those items start their own story.

Every item gets a role — `seed`, `paper`, `code`, `video`, `coverage`,
`discussion` — which is what renders as the story's "wake". Roles are stored,
not recomputed, so changing `role_for` needs `trib cluster --reset`.

### Ranking

Recency-decayed relevance with a 48-hour half-life, plus a capped bonus for
stories several sources covered (`SOURCE_BONUS`, `MAX_CORROBORATION`). It must
resist volume: arXiv publishes ~150 papers a day where a blog publishes one, and
recency-times-relevance alone handed it 47 of the first 50 cards. The feed damps
each *repeat* of a source or kind as it is built (`SOURCE_DECAY`, `KIND_DECAY`),
which restores a mix with no hard quota. The page is a dense card list, not
full-screen snap cards: one headline per screen is the opposite of scannable.

### Tests

- `tests/conftest.py` provides `conn`, a freshly migrated database in
  `tmp_path`, and `source_id`.
- Adapter tests mock HTTP with pytest-httpx (`httpx_mock`).
- **Never load the real embedding model in a test.** The topics tests use an
  `axes` fixture that monkeypatches `topics.embed` to return fixed unit vectors,
  so every cosine is exact and every assertion about routing is deterministic.
- `tests/test_cli.py` runs every command against a fresh `trib init`, with no
  network and no model — it exists because the CLI once had no tests at all and
  a stale sample config shipped unnoticed.

## Labelling: one home, three axes

A GPT-6 release is *OpenAI* (a provider you follow), *a frontier model release*
(a kind of story) and *an event* (already a story). Only the middle one is a
topic, and only the middle one is semantic. So labels are three axes, each
matched the way that works for it:

| Axis | Question | Matched by | Per story |
|---|---|---|---|
| Topic | where does it live | embedding, argmax over leaves | exactly one |
| Facet | what kind of thing is it | regex over titles and summaries | any number |
| Entity | who is it about | name and alias | any number |

**Topics have no threshold, and that is measured, not a shortcut.** With a flat
spine scored against one line: at 0.60, 2020 of 2239 stories took the cap of
three labels and `Research` held 54% of the corpus; raising it to 0.67 killed
`Policy & courts` outright (its best score across 600 stories was 0.64); and a
relative margin gave one paper **13 labels**, because 13 descriptions sat within
0.05 of each other. Scores live in a 0.60–0.85 band with no gap to cut at. So a
story goes to the single best leaf — a comparison needs no scale and cannot
drift. `floor = 0.55` only catches a story the spine has no opinion about at all.

**Only leaves are scored**; a shelf earns its stories from its leaves, so a
shelf's description is documentation. This is what stopped a vague parent
swallowing its own children. **Parking:** when the top two leaves share a shelf
and sit within `park_margin` (0.02), the story sits on the shelf — the shelf is
clear, the leaf is a coin-toss. A pile on a shelf is the signal that a leaf is
missing, which is why `trib topics --suggest` sorts by parked stories: under one
home, almost nothing is ever "unclaimed". Result: 43 topics over 10 shelves, the
largest leaf 10% of the corpus, none empty. What it does not fix: 41% of stories
have a runner-up on a *different* shelf within 0.02, and those pick a side. The
answer to that is a "related topics" row, not multi-label, which was measured
worse.

**Facets are regexes because some subjects are lexical.** An agent paper is also
a safety paper and a benchmark paper, so similarity files it under whichever it
resembles most — `RepoAtlas: Guiding Coding Agents` landed under
interpretability, and rewording the descriptions made it worse. Matching
`\bagent(s|ic)?\b` found 133 stories in a fortnight where scoring found 25.

**Entities match by name and alias, never similarity**, so they cannot drift.
Aliases must be unambiguous — a bare `Meta` claims meta-learning, a bare `Flash`
claims flash attention — and a dot followed by more word is part of the word, so
the Llama *model* does not match `llama.cpp`. Seeded ones live in config;
`trib entities --suggest` proposes more from summaries (Title Case headlines
make every word look like a name), dropping words also written in lower case
elsewhere. About half its output is eponyms like `Gaussian`; a person rejects
those.

**Topics are an ontology, and the tree is only its browsing skeleton.** Category
(hand-made spine), entity (extracted, human-accepted), event (a story). The
huggingface incident belongs under Astra *and* OpenAI: topics are a tree because
browsing wants one, and entities make the whole thing a graph. Reddit's model
cannot be copied — subreddits are flat, user-created, and a *human* classifies at
submission time; Tributary has no submitters, so the equivalent is propose, then
accept.

**Topics die by dormancy, not deletion.** The filter row is built from the
stories loaded, so a quiet topic vanishes on its own and returns if its subject
does. Deleting one re-labels the whole corpus and, under one home, hands its
stories to its neighbours, which then look swollen. Remove only entries that
were *wrong*, never ones that are finished.

**Gossip is content.** Speculation and leaks are wanted, so triage must not
treat rumour as low quality. "Astra 6.1 speculation" and "Astra 6.1 released"
are different events about one thing — following the *entity* collects both,
which is right; clustering them together would not be. Lowering the merge
threshold would not help anyway: the 0.86–0.92 band holds almost nothing.

## Sources

The feed was 88% arXiv before a verified scan (2026-09-17) added news, labs,
safety writing and Reddit; about 90 non-paper items a week against arXiv's ~235.
Findings that should not be researched again:

- **Every added source fetches from Actions too** — checked on the first runs
  after they landed (2026-09-18). Only Import AI fails there, being Substack.
- **Reddit needs no API key.** The `.rss` endpoints are public Atom, given three
  things: a descriptive User-Agent (a default one gets 403 HTML before the rate
  limiter), the multireddit form `r/a+b+c/.rss` (one rate-limit token for all of
  them — separate sources would 429 each other), and `www.reddit.com`
  (`old.reddit.com/.rss` now redirects to a login).
- **GitHub's `prerelease` flag cannot be trusted alone.** llama.cpp's per-commit
  builds (`b11020`) and LangChain's per-package alphas
  (`langchain-typesafe==0.0.1a1`) both arrive with it set to false, and both led
  the feed on 2026-09-19. `github._is_prerelease` reads the tag string as well.
  Set `prereleases = true` on a source that wants them.
- **Hugging Face models are already the popular ones** (minimum 90 likes, median
  964). For future filtering: there is no server-side min-likes filter
  (`min_likes` is silently ignored); `sort=trending` errors, and `likes7d` equals
  `trendingScore`; a `base_model:*` tag is the reliable mark of a derivative,
  while "author is an organisation" is not (unsloth is an org and a requant
  shop). `cites_paper` kept zero of 300 newest repos, so that source was removed.
- **Anthropic has no feed** on either domain or in either page head; it needs
  the HTML-scrape adapter. Its YouTube channel is `UCrDwWp7EBBv4NwvScIpBDOA`.
- **MarkTechPost's own `/feed/` returns 403**; the FeedBurner mirror works.
- **YouTube**: channel feeds at `youtube.com/feeds/videos.xml?channel_id=…`
  work — Dwarkesh `UCXl4i9dYBrFOabk0xGmbkRA`, MLST `UCMLtBahI5DMrt0NPvDSoIRQ`,
  Two Minute Papers `UCbfYPyITQ-7l4upoX8nvctg`, AI Explained
  `UCNJ1Ymd5yFuUPtn21xtRbbw`, bycloud `UCgfe2ooZD3VJPB6aJAnuQng`, Welch Labs
  `UConVfxXodg78Tzh5nNu85Ew`, Karpathy `UCXUPKJO5MZQN11PqgIvyuvQ`, Simons
  Institute `UCW1C2xOfXsIzPgjXyuhkw9g`. **Playlist feeds are ordered by
  playlist position, not date**, so they look frozen; use channel feeds.
- **Podcasts**: Latent Space's *podcast* feed
  `api.substack.com/feed/podcast/1084089.rss` is separate from its blog and
  carries full transcripts; also Dwarkesh (`…/podcast/69345.rss`), MLST
  (`anchor.fm/s/1e4a0eac/podcast/rss`), Practical AI, TWIML, Cognitive
  Revolution, No Priors, Last Week in AI. Hard Fork's feed is effectively dead.
- **Not worth it**: TikTok has no feed at all (a scraper against a private API);
  X is pay-per-read with no free tier; Discord and Slack need a bot per server;
  Papers with Code redirects to Hugging Face. Bluesky has native per-profile RSS
  at `bsky.app/profile/<handle>/rss`, but no topic or search feeds.

**Why not GitHub repo search** for "what a paper set off": a bare arXiv id
matches nothing without `in:readme`, and with it the results are roadmaps and
awesome-lists that cite every paper; the real implementation (`artidoro/qlora`)
predates any useful date filter; and GitHub rejects more than five boolean
operators, so the noise cannot be excluded in the query. Lists cite everything,
so text matching cannot tell "built on" from "mentions". If revisited, the
discriminator is client-side (an implementation cites one or two arXiv ids, a
list dozens) and it is a stage, not a `Source`. Hugging Face's `arxiv:` tags are
the same signal already structured, lifted into `metadata["arxiv_id"]`.

**TLDR AI is a digest, not a feed.** `https://tldr.tech/api/rss/ai` publishes
one entry per daily issue with ~10 unrelated links. As plain `kind = "rss"` it
would average ten blurbs into one meaningless vector; attach ten arXiv ids and
repos to one item, welding ten stories into one (each value is held by only two
items, so `MAX_FANOUT` does not catch it); and let consecutive issues merge as
near-identical titles. It needs a two-stage adapter shaped like
`sources/github.py`, emitting one item per story with an id like
`f"{issue_id}#{n}"`. Its value is the hand-written blurbs, not the coverage.

**Commentary can arrive without the thing it comments on.** `identity.py` treats
a URL as a strong identifier but only finds one in the item's own `url`,
`canonical_url` and `metadata.outbound_url` — its free-text scan finds arXiv
ids, DOIs and repos, never generic URLs. So a blog post about an announcement
does not join it, and `role_for` then promotes the commentary to seed. Extracting
body links has to be guarded: a link counts only if it leaves the item's own
domain, the item cites few enough URLs to mean them (a link roundup should
extract nothing), and `_has_specific_path` holds. Calibrate before trusting it —
a wrong merge still costs more than a missed link.

**A feed does not fail because its XML is bad.** feedparser recovers from bare
ampersands, undeclared entities, control characters, leading junk and
truncation. Zero entries means the body was never a feed, and the parser's
message is the same for all four causes — a web page (bot check), JSON (an API
error), the wrong encoding, or nothing — so the adapter reports content type,
size and opening bytes instead. An empty but *valid* feed is a success.

**Describing an item means finding where its words already are.**
`describe.py` tries, cheapest first: release notes already stored in `body`, a
hub model card, a repo's one-line description (cached per repo), and a linked
page's `<meta>` description. It reads meta tags only, never the page body —
picking prose out of cookie banners is the part of scraping that keeps going
wrong. For an HN item, describe what was submitted, not the thread.

**Beyond AI.** Sources, triage, topics, facets and entities are all config, and
the pipeline never names a subject; `identity.py`'s arXiv and hub extractors
simply find nothing elsewhere. "A Tributary for X" is mostly a second config.

## Calibrated values — measured, do not guess these again

```
cluster.MERGE_THRESHOLD  = 0.92   # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW    = 0.86
cluster.WINDOW_DAYS      = 14
triage threshold         = 0.66
store.MAX_ITEM_AGE_DAYS  = 60     # must match `trib prune --days` in the workflow
topics floor             = 0.55   # 1 story in 2239 falls below it
topics park_margin       = 0.02   # parks about 13% of stories on a shelf
```

bge puts unrelated text near 0.5, so the usable similarity range is about
0.5–1.0. Matches and hard negatives genuinely overlap (matches as low as 0.888,
different same-week papers up to 0.944); 0.92 honours "a wrong merge costs more
than a missed link". `trib calibrate` re-measures it against tier-1 ground truth
as the corpus grows. For triage, `trib triage --by-source` should show a
gradient — research feeds 80–100% kept, general tech 20–30% — and a uniform
rate means the profile is measuring text length, not relevance.

## How it runs

`.github/workflows/update.yml` runs `trib run`, `trib prune --days 60` and
`trib export`, then publishes to GitHub Pages — on every push to `main` and
every three hours at minute 17. The database lives in the Actions cache, because
git stores every version of a binary in full; a cache miss is survivable, since
the run rebuilds from the sources. Scheduled workflows are disabled after 60
days without a push.

Actions runs on cloud IPs, which is why Substack sources fail there and why
YouTube *transcripts* (Phase 4) need a residential connection — the WSL machine,
or a Pi at home pushing to the same repo.

**Reading a run's log:** `trib run` prints new, updated, unchanged and too-old
counts. All-new with nothing unchanged is the shape of churn, not news — on a
restored database, the previous run's items should come back as updates. Zero
updated once meant archive-serving feeds were re-delivering years-old entries
every run, which is what `MAX_ITEM_AGE_DAYS` at ingest fixed.

Locally, a relative `db_path` resolves against `config.toml`, not the working
directory, so `trib` works from cron. Cron works in WSL (`systemd=true`).

## What it is for

From the notebook page the project started as:

> - Blandat nyheter & sociala medier — **Verifierad (mer trovärdig)**
> - Börja med nyheter för att samla
> - **Vill ta bort mitt sociala medier beroende → något vettigt**
> - Samla fakta från artiklar med personer som kommenterar
> - Combo reddit, tiktok, youtube — (tech videos) för snabb info
> - **Mål: Följa med på allt som händer — prio/börja med AI**

The sketch beside it is three columns — a mixed feed, then `r/AI`, then
`r/AI – huggingface incident` — with a funnel producing `anthropic IPO`:
everything, then a subject, then one event. That is the feed, a topic and the
story page, and the funnel is the clusterer.

**"Community" means the ripple, not a chat room**: what happened *because of* a
story — the projects started after it, the arguments, the write-ups and video
takes. A story is the announcement plus its wake, which is what item roles are
for. Posting and commenting on a topic is a separate, open requirement, and the
one item in `NEXT.md` that changes the architecture.
