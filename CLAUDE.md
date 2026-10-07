# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Tributary is a personal AI-news feed: it ingests news, papers, releases and
discussion, groups them into **stories**, labels them, and serves a feed you
scan on a phone — live at https://sebbefagerstedt.github.io/tributary/.
`README.md` is the user-facing how-to. **`NEXT.md` is only the list of what to
build next**; this file holds everything else: the ground rules, how the code
fits together, and the decisions that should not be rediscovered.

**This file describes version 1 — the pipeline that runs today — and what
building it taught.** The app is being redesigned (decided 2026-10-04): **`VISION.md` is
the spec for the redesign and wins wherever the two disagree**, and `NEXT.md` is
its roadmap. Version 1's page (one HTML file with tabs, follows, lenses) was
**retired on 2026-10-05**; the site is now the React app in `web-next/`, and the
page decisions that carry over are listed at the end of `VISION.md` — the rest
are in git history, in this file before the commit that retired the page. Still
true of the code here: sources in `config.toml` are fetched for everyone; topics
are one shared spine; deployment is a static site rebuilt every three hours.

## Ground rules

- **No LLM, no API key.** There is no `ANTHROPIC_API_KEY` and the owner does not
  want one yet. When something seems to need a model, check whether the local
  embeddings can do it first — they usually can (dynamic topics turned out to be
  plain vector clustering). The only genuinely LLM-shaped work left is "why
  this matters" one-liners: offer that as optional and priced, never on by
  default.
- **Do not cut arXiv.** A new paper is news whether or not anyone has reacted to
  it. Any popularity gate has to be per-kind, never global.
- **No Substack sources.** Substack blocks GitHub Actions IPs — Import AI
  returned 403 on every scheduled run while working fine locally, and was
  dropped for it on 2026-09-22. Every source must behave the same wherever
  `trib` runs.
- **The ranking is not an engagement metric — but that is about mechanics, not
  format.** The project exists partly to replace a social-media habit with "något
  vettigt", so a ranking tuned to keep you scrolling is the thing being avoided.
  The *shape* of those apps is not: *"Jag vill absolut inte ersätta formaten av
  instagram och tiktok, snarare behålla det men att ersätta innehållet"*
  (2026-09-22). Borrow the form — large, image-led, immersive, fast to scan —
  and never the hooks.
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
uv run trib topics --why "…"   # a story's scores against every leaf: id or title words
uv run trib entities --suggest # recurring names nobody has seeded
uv run trib sources --suggest example.com  # find a site's feed; prints config, writes nothing
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

**Testing the page:** `cd web-next && npm test` runs its logic under vitest —
what a topic holds, "new", the source catalogue, and the int8 vectors checked
against the numbers `readers.pack` wrote in Python. Keep that logic in pure
functions (`state.ts`, `data.ts`, `vectors.ts`) so it stays testable without a
browser.

**For layout, screenshot it.** On the dev machine headless Chromium still needs
`sudo .venv/bin/playwright install-deps chromium` first. In a Claude Code remote
container it is already there: pass `executable_path="/opt/pw-browsers/chromium"`
and `args=["--no-sandbox"]`, because the pinned Playwright asks for a build
number the image does not carry and otherwise tells you to run `playwright
install`, which is wrong. `npm run dev` in `web-next/` serves the page on sample
data (`scripts/make_dev_data.py` writes it); `trib serve` serves the built page
with the API. Screenshot at 390×844, and emulate touch (`has_touch=True`) when
checking gestures: the player and sheets are driven by touch and pointer events.

## Architecture

### The pipeline, in the order `trib run` executes it

| Stage | Module | Does |
|---|---|---|
| fetch | `pipeline.py`, `sources/*`, `store.py` | adapters return items; the store upserts them |
| describe | `describe.py` | finds prose for items that arrived as a bare title |
| embed | `embeddings.py` | fastembed bge-small-en-v1.5, 384-dim, local ONNX |
| triage | `triage.py` | *scores* by similarity to prose interests; drops nothing |
| enrich | `enrich.py`, `identity.py` | extracts join keys: arXiv ids, DOIs, URLs, repos |
| cluster | `cluster.py` | groups items into stories, and gives each item a role |
| label | `topics.py`, `facets.py`, `entities.py` | topic, facets and entities per story |

The read side runs at request or export time: `feed.py` ranks stories,
`export.py` builds one JSON bundle, `api.py` serves it and `export` writes it to
disk, and the page in `web-next/` renders it.

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
  the page cannot tell the difference. On a static host a reader's profile
  lives in `localStorage`; served by `trib serve` it lives in the database.
- **The JSON bundle is the contract**, so the frontend was replaced (2026-10-05)
  without touching the pipeline. The page registers no service worker: a stale
  page or feed is worse than an honest error. `web-next/public/sw.js` exists
  only to retire version 1's worker on phones that installed it.
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

### What the bundle holds, and the reading rules that outlived version 1's page

Version 1's page had four surfaces (Topics, Feed, Trending, Saved), follows,
circles and lenses; it was retired on 2026-10-05 and its decisions are in git
history. These are the ones the pipeline and the new page still act on.

**Triage scores; it does not gate.** Changed 2026-09-19, on the owner's call:
*"I have solved filtering with following instead. It is a much more basic and
better solution since everyone has their own preferences."* So `enrich.pending`
and `cluster.unclustered` no longer filter on `triage_state`, and everything
fetched becomes a story. Triage still runs, and its score is still `relevance`
in the ranking — so what the profile dislikes sinks in the ranking rather than
never existing.

**The topic floor was re-measured on everything, and stays at 0.55.** Topics
have no relevance threshold by design — a story goes to its single best leaf —
and `floor = 0.55` was first measured at *1 story in 2239* **on already-triaged
material**. Once everything became a story, the floor was the only thing
between a crypto post and whichever AI leaf it most resembles, so it was
measured again on 2026-09-22: 30 days of stories, 428 of them labelled by hand
as about AI or not.

- **There is no gap to cut at.** Short and image-only posts score low whatever
  they are about — *Anthropic releases Opus 5.5* scored 0.565, *Qwen 4
  Announced* 0.559 — so raising the floor cuts AI news about as fast as filler:
  0.58 costs 17 more AI stories their topic for 30 fewer filler, 0.60 costs 44
  for 56. arXiv papers never score that low; the lowest of 299 was 0.631.
- **Filler is 9% of stories with a topic** — 102 of 1,167, about three a day
  spread over every topic, 2–8% in the big ones. It is only a large share of a
  *thin* topic, where three stray stories can be all there is.
- **Most of it is one source**, the Hacker News front page: 105 of 139 non-AI
  stories. A floor of 0.60 for stories made only of its items was the best rule
  measured — 33 fewer filler, 8 more AI stories without a topic, 6 of them
  still carrying an entity — and was not taken, because the problem is not big
  enough to earn a per-source mechanism. Two others did worse: hidden "not
  about AI" descriptions competing in the argmax lost to a plain floor, since
  AI news about politics matches a politics description better than any leaf;
  and triage as a second opinion changed nothing, because it misjudges short
  posts both ways.
- **The below-triage column overstates filler.** `trib topics --stats` counts
  a topic's stories made entirely of items triage would have dropped, and
  triage drops short AI posts too — *Grok 4.7*, *MiMo v2.6*, *Transformers
  Explained Visually*. In the same 30 days, 9 of Frontier model releases' 24
  stories were below triage and 7 of those 9 were real releases. Read the
  column as "short or off the profile", never as "not AI"; what a topic holds
  is in its headlines.

**The feed orders by when the news broke, not by the story's clock.** A story's
clock restarts when its wake grows (see `trib renewal`), and a chronological
feed where a three-day-old paper jumps the queue because someone commented is
exactly what looked unsorted. The wake shows as "active 2h" on the card
instead — over a 6-hour threshold, since a paper and its own announcement land
minutes apart and that is one event, not a wake.

**The bundle is selected by date** (`feed.recent`), not by rank. Taking the
top-ranked N and sorting those by date would silently drop a recent story the
ranking did not rate, and the reader would never learn it existed. Every card
still carries `score`, which is all a ranked view needs. **And it is bounded by time, not by count.** The
workflow exported `--limit 120`, which at this corpus's rate — about 1,300
stories a month — was two or three days deep: on 2026-09-25 AI video news was
"at the most 24h old" on the page while thirty days of it sat in the database.
The limit is gone (`export.DEFAULT_LIMIT = 0`, every story in `--days 30`),
about 1 MB gzipped, and the page draws fifty cards at a time behind a **Show
more** button — a button, never loading on scroll, because a feed that refills
as you reach the end is a hook.

**Google Discover's card is an image contract, and this corpus cannot sign
it.** Offered 2026-09-22 as the target for Trending, as a screenshot. Discover
mandates an image at least 1200px wide plus `max-image-preview:large`, which is
why every card in it has one. Tributary's `media_url` comes only from RSS
`media:content`, `media:thumbnail` and image enclosures (`sources/rss.py`) and
from Hugging Face thumbnails, so arXiv, HN and GitHub releases carry none — and
at ~235 papers a week against ~90 non-papers, that is most of the feed. The
cheap half of the fix is `og:image`, **built 2026-09-22** — see "Describing an
item" under Sources for what it does and does not cover. The other half does not
exist: a paper and a release have no image, ever, so imageless kinds get a
typographic cover (built 2026-09-22, below). Discover's
uniformity comes from a uniform corpus — publisher articles and nothing else —
and "do not cut arXiv" is the rule that makes this corpus the other kind.

**One word per kind.** The badge on a card and the line counting what else is
attached to it were two tables, and they drifted: the same kind was badged
`news` while the chip beside it said `1 article`, and `code` against `1 repo`.
Nothing told a reader those were the same thing. `KIND_WORD` is now the only
vocabulary — paper, model, repo, video, discussion, article, post — used by
both. A *story* is still a different unit from any of them: it is the cluster,
which is why counts say "6 stories" while a card in it is badged `article`.

**"New" is unread and under 48 hours old.** Seen marks are per story and per
device, and a count you clear by reading beats one that resets itself at
midnight — but unread alone stopped working once the bundle held thirty days:
every circle and tile counted a month, and a circle played two hundred stories
to reach today's. Reported 2026-10-04: *"news should not be marked as new
unless they are under 48 hours old … I still want to have the opportunity to
look at more"*. So `isNew` is the one test every count, ring and playlist uses;
older unread stories stay in the feed to scroll to, they just stop being news.

### Ranking

Recency-decayed relevance with a 48-hour half-life, plus a capped bonus for
stories several sources covered (`SOURCE_BONUS`, `MAX_CORROBORATION`). It must
resist volume: arXiv publishes ~150 papers a day where a blog publishes one, and
recency-times-relevance alone handed it 47 of the first 50 cards. The feed damps
each *repeat* of a source or kind as it is built (`SOURCE_DECAY`, `KIND_DECAY`),
which restores a mix with no hard quota. It was version 1's **Trending**; the
bundle still carries each story's `score`, while the new page reads in date order.

**The ranking does not learn from what you do.** Ruled out 2026-09-23, in the
review of `NEXT.md`; it was the last of an old "Phase 5", which would have let
your saves and dismissals reorder the feed. Learning from behaviour is how a
ranking turns into the engagement metric the ground rules keep out. If it is
ever reopened, only explicit signals — a save, a dismissal — and never time
spent, dwell or scroll-past.

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
| Topic | where does it live | embedding, argmax over leaves — unless the headline claims it | exactly one |
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

**A leaf can claim a story by its headline, before anything is scored.**
Built 2026-09-22 for launch posts: in the fortnight before, the spine homed 4 of
16 launch stories under Frontier model releases — *Introducing GPT-6 Sol and
Luna* went to Jailbreaks & attacks, *Introducing Claude Opus 5.5* to Chips &
datacenters. A launch post is benchmarks, pricing and safety, and its centroid
follows that prose. Six rewordings of the description were measured: naming
the model lines reached 8–9 of 16 and no further, and naming the labs caught 12
by taking 21% of every story. Its title, meanwhile, says exactly what it is. So
a leaf may
carry `claims`, a regex compiled with `CLAIMS_FLAGS` (case-blind and verbose, so
it can be laid out and commented in `config.toml`), and a match makes that leaf
the home outright — no floor, no parking. Three limits keep it from becoming a
second classifier:

- **Only the headline is read** — the earliest item's title, what `_titles`
  already calls the headline. Summaries and later coverage name GPT-5 in
  passing constantly.
- **Never a paper's.** A paper with a model in its title is a paper *about* that
  model, which is what scoring is for.
- **Only leaves claim**, and the loader rejects one on a shelf.

The frontier pattern takes a flagship line *with a version on it* — `Claude
Code 2.0` and `Gemini CLI` are tools on a model line's name — either after a
launch verb (`Introducing …`, `OpenAI releases …`) or bare with at most three
words after it, so *Grok 4.7* is claimed and *Claude Opus 5.5 helped me write a
compiler* is left to scoring. Open-weight lines (Qwen, Llama, DeepSeek) are not
in it; they have their own leaf, and nothing has shown that leaf missing them.
**It was pinned against those 16 titles and hand-written near-misses, not
measured on the corpus** — the database was unreachable from where it was
built. `trib run` prints how many stories were homed by headline; if Frontier
model releases starts collecting things that are not launches, the pattern is
where to look, and its tests are in `tests/test_topics.py`.

Facets are labelled but not shown: see **There is no kind row** above.

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
those. A word that mostly follows the same name is proposed with it — `Gemini
Flash`, never a bare `Flash` (2026-09-23) — unless that name is an ordinary word
opening a sentence.

**Topics are an ontology, and the tree is only its browsing skeleton.** Category
(hand-made spine), entity (extracted, human-accepted), event (a story). The
huggingface incident belongs under Astra *and* OpenAI: topics are a tree because
browsing wants one, and entities make the whole thing a graph. Reddit's model
cannot be copied — subreddits are flat, user-created, and a *human* classifies at
submission time; Tributary has no submitters, so the equivalent is propose, then
accept.

**A reader's own topic is a lens, not a home, and `_home` is what forces
that.** Asked 2026-09-22: users should be able to create topics, arriving as
proposals and ranked before adoption. What the code says about it: `topics.run`
scores every leaf and `_home` takes the argmax, so a new leaf competes with the
whole spine for every story and one person's topic changes what everyone else
sees; and `Config.label_fingerprint` covers topics, so *each* new one re-labels
the entire corpus. A user topic therefore cannot be a spine topic. It can be the
other shape the three axes already describe — any number per story, cutting
across rather than partitioning — which is a facet matched by embedding instead
of regex. A saved query. Nothing competes, nothing is re-labelled, and
multi-label is fine precisely because it is not a home.

**The bundle carries story centroids**, quantised to int8 and base64-encoded
(`export._centroids`, decided 2026-09-22 for version 1's lenses): measured at
`--limit 120` that is **+60KB raw, +40KB gzipped**, against four times that for
float32. The error it costs, over a bge-shaped spread of 2000 cosines: mean
0.0026, worst 0.011, nine of the top ten by similarity keeping their places, one
story in two thousand crossing a 0.75 threshold it should not have — the same
order as `park_margin`, so this is fine for ranking and filtering and is *not*
precise enough to re-derive a topic's home from. The new page's fit filter
(`fits` in `web-next/src/state.ts`) reads them against a reader topic's embedded
description, packed the same way by `readers.pack`, with an unmeasured
`FIT_FLOOR = 0.62`. A reader's topic asks its words first and the vector
second, the order version 1's lenses used and for the reason the clusterer does.

**But the destination is real accounts and a server, not personal lenses.**
Stated 2026-09-22: the next big step is proper login and topics that are shared
rather than private, and the personal version comes first only because it is how
every part of the feature — creating a topic, commenting, following, ranking a
proposal — can be exercised before any of it is paid for or moderated. **A
personal lens is a test harness for a shared one, not a smaller substitute.** So
build each piece such that the only thing the server changes is where the row is
stored: a lens is `{name, vector|pattern, created}` whether it lives in
`localStorage` or in a table, and a comment is addressed by `story_id` either
way. Anything that would have to be rewritten when the account arrives is the
wrong shape now.

**Ranking proposed topics by followers is the wrong instrument.** It is an
engagement metric, it is rich-get-richer — a topic nobody can see collects no
followers — and it measures popularity rather than whether the topic works as a
filter. Three signals need no users at all: **cosine against every existing
leaf's description**, where above about 0.9 the proposal is a synonym and the
existing topic should be offered instead — this, not voting, is what keeps the
spine from bloating; **yield**, how many stories match over a fortnight, where
too few is dead and too many is a category; and **coherence**, the mean pairwise
cosine of what it collects, which is what separates a subject from "AI stuff".
Followers are at most a tiebreaker for promotion into the spine, and promotion
stays a person's call.

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
  after they landed (2026-09-18). Only Import AI failed there, being Substack,
  and it was dropped on 2026-09-22.
- **Reddit needs no API key.** The `.rss` endpoints are public Atom, given three
  things: a descriptive User-Agent (a default one gets 403 HTML before the rate
  limiter), the multireddit form `r/a+b+c/.rss` (one rate-limit token for all of
  them — separate sources would 429 each other), and `www.reddit.com`
  (`old.reddit.com/.rss` now redirects to a login).
- **GitHub's `prerelease` flag cannot be trusted alone.** llama.cpp's per-commit
  builds (`b11020`) and LangChain's per-package alphas
  (`langchain-typesafe==0.0.1a1`) both arrive with it set to false, and both led
  the feed on 2026-09-19. `github._is_prerelease` reads the tag string as well.
  Set `prereleases = true` on a source that wants them. **Patch releases are
  skipped too** (2026-09-23): `transformers v5.15.1` and `langchain-core==1.6.3`
  are real releases and rarely news, so a third version number above zero is
  dropped at fetch (`github._is_patch`; calendar versions are exempt).
  `patches = true` keeps them.
- **Hugging Face models are already the popular ones** (minimum 90 likes, median
  964). For future filtering: there is no server-side min-likes filter
  (`min_likes` is silently ignored); `sort=trending` errors, and `likes7d` equals
  `trendingScore`; a `base_model:*` tag is the reliable mark of a derivative,
  while "author is an organisation" is not (unsloth is an org and a requant
  shop). `cites_paper` kept zero of 300 newest repos, so that source was removed.
- **Anthropic has no feed** on either domain or in either page head, so it is
  read from its sitemap (`kind = "sitemap"`, built 2026-09-22), as is
  DeepSeek. The adapter visits each URL under `include` once, for the same
  `<meta>` tags `describe` reads, and never crawls a back catalogue: its
  docstring has why, and what it does with a `lastmod` that is only the build
  date. The same adapter reads a Google news sitemap, dated by
  `news:publication_date`.
- **MarkTechPost's own `/feed/` returns 403**; the FeedBurner mirror works.
- **Lab sources added 2026-09-22 all fetch from Actions but two**, checked on
  the first run: Microsoft Research, Google's AI blog, Amazon Science, Qwen,
  Meta Engineering's ML category, GitHub's AI & ML blog, and Anthropic and
  DeepSeek by sitemap. **xAI's sitemap answers 403** to Actions, and
  **`cohere.com/blog/rss.xml` serves a web page**, not a feed; both were
  dropped. Meta AI's own blog has no feed, which is why its engineering blog
  stands in.
- **An empty 406 from `export.arxiv.org` is its CDN, not the API** — no
  `google` hop in `Via`, and `cache-control: private, no-store`. It hit httpx
  on the WSL machine for a few minutes on 2026-09-22 while curl got 200 from
  the same URL and Actions was unaffected, then cleared by itself. Retry before
  debugging the adapter: a header change looked like the fix and was not.
- **YouTube and podcasts are skipped**, the owner's call on 2026-09-22 — as
  sources, and with them the transcript and summary work that was their reason
  to exist. A video or episode still arrives when something else links to it,
  which is what the `video` role is for. The channel IDs and podcast feeds
  found for them were verified and are in git history, in this file before
  the commit that recorded this.
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
**Dropped 2026-09-23**, in the review of `NEXT.md`: the labs its issues link to
are read directly now, and the blurbs alone do not earn a two-stage adapter.
This stays so it is not researched again.

**Commentary joins the thing it comments on through its links** — built
2026-09-23. `identity.py` used to find a URL only in the item's own `url`,
`canonical_url` and `metadata.outbound_url`, so a blog post about an
announcement never joined it and `role_for` promoted the commentary to seed.
Feed summaries are flattened to text before they are stored, so the RSS adapter
keeps the summary's links in `metadata.links` first (the summary, not the full
content: a full article links everything it mentions). `identity._cited`
guards them three ways, because a wrong merge costs more than a missed link: a
link must leave the item's own site, it must name a specific page (not a
homepage, a share button or a profile — `_CHROME_HOSTS`), and an item citing
more than `MAX_CITED = 3` pages is a roundup and yields nothing. **It is guarded
and tested, not calibrated** — nothing reachable held a corpus when it was
built. If `trib calibrate` or the feed shows unrelated stories merged through a
shared URL, the guards are where to look. Items stored before it carry no
links and age out.

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

**And the same parse takes the picture.** Added 2026-09-22, because a card wants
art and almost nothing here supplies it. `og:image` comes out of the `<meta>`
pass that was already running, resolved against the page it came from — a bare
path or a `data:` URI is dropped rather than guessed at. Two consequences worth
knowing:

- **`pending` now asks for *either* half.** It used to select only items with no
  summary, which meant art could reach nothing but the few items that arrived
  with no words at all — and those are hub cards and release notes, which have
  no picture either. An item with prose and no picture is now worth visiting,
  and a step that cannot supply the missing half is skipped, so nothing costs a
  request it did not need.
- **Only `article`, `post` and anything with an `outbound_url` are visited for
  art alone** (`_ILLUSTRATED_KINDS`). A publisher maintains `og:image` because
  it is the card every social platform renders from their link; a paper, a
  release and a model card are not written that way. Firing a request at all
  ~235 arXiv abstracts a week on the chance one has a picture is a guess, and
  this repo measures instead. **Measured 2026-09-22, and not widened.** An
  arXiv abstract's `og:image` is arXiv's own logo, the same on every paper; a
  GitHub release's is a card GitHub renders from the release's own title and
  notes — a picture of the headline the card already prints, declined as art on
  the owner's call. Both are refused wherever they turn up (`_NOT_ART`),
  because a Hacker News post linking to a repo reaches the same card through
  its `outbound_url`; five local items had it before the guard.

A picture never re-opens triage. A summary clears `embedded_hash` and the
verdict because the vector was built without it; art changes nothing a model
reads.

**Google Discover has no ingestion of its own**, checked 2026-09-22 because it
was proposed as the model for getting *everything*. It is a ranking over the
ordinary Search index: content is eligible automatically once crawled, indexed
and within the content policy, with no submission and no approval — Publisher
Center is branding, not a way in. So the thing worth copying is not there. What
is copyable is how Google keeps that index fast, and one of the three is already
what this repo does:

- **News sitemaps.** `sitemap-news.xml`, named in `robots.txt`, holding only the
  last 48 hours and under 1000 URLs, crawled at minute-to-hour intervals. It is
  the only way to get a publisher's whole output when the publisher has no feed,
  and it is simple XML.
- **Feed autodiscovery.** Google's own Follow button runs on the RSS or Atom
  feed found via `<link rel="alternate">`, and where a site has none Google
  generates one from its crawl. Their answer to "follow a source" is this
  project's answer. The fallback paths when the `<link>` is missing are well
  known: `/feed/`, `/rss/`, `/feed.xml`, `/index.xml`, `/rss.xml`, `/atom.xml`
  (WordPress `/feed`, Ghost `/rss`, Hugo `/index.xml`). Finding a domain's feed
  proposes sources and is never a `Source` — propose then accept, like topics.
  **Built 2026-09-23 as `trib sources --suggest`** (`discover.py`): the page's
  `<link>` first, then those paths, then a news sitemap from `robots.txt`, each
  parsed before it is offered. A site that refuses to answer is reported as
  unreachable, never as having no feed.
- **Incremental clustering**, with an age limit of about four hours on arrivals
  and entity recognition beside it, is what Full Coverage is. That part is built.

Discover's personalisation is Web & App Activity: searches, YouTube history,
taps versus scroll-pasts, dwell time, saves, dismissals. It is the engagement
machine the ground rules reject, and the single control it shares with Tributary
is *follow* — which Google added late and this project started from.

**Google News RSS is a trap for this repo specifically.** Since 2024 every
article link in `news.google.com/rss/search?q=…` is wrapped in an encoded
redirect (`/rss/articles/CBMi…`) that resolves only through Google's internal
`batchexecute` endpoint. Canonical URL is the strongest tier-1 identifier, so an
undecoded Google link poisons clustering outright — and an undocumented internal
endpoint that behaves differently on cloud IPs is exactly what the Substack rule
already forbids.

**GDELT is the firehose that would actually work.** Open data, no key, updated
every 15 minutes, 100+ languages; the DOC 2.0 API's `ArtList` mode returns
`url`, `title`, `seendate`, `socialimage`, `domain`, `language` and
`sourcecountry` — a real URL, so join keys survive, and an image, which most of
this corpus lacks. Two things make it a decision rather than a config line: it
is query-driven, which is the shape this repo does not have and the same shape
product search would need, and it is *all* world news, so the per-kind
popularity gate stops being optional. **GDELT refused the one machine that
could reach it.** The research sandbox's proxy blocked `api.gdeltproject.org`,
`news.google.com` and the live `data.json`; from the WSL machine on 2026-09-22
GDELT answered HTTP 429 to every request, the first one included. Google News
has still not been probed. Verify before building on any of it.

**Beyond AI.** Sources, triage, topics, facets and entities are all config, and
the pipeline never names a subject; `identity.py`'s arXiv and hub extractors
simply find nothing elsewhere. "A Tributary for X" is mostly a second config.

## Calibrated values — measured, do not guess these again

```
cluster.MERGE_THRESHOLD  = 0.92   # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW    = 0.86
cluster.WINDOW_DAYS      = 14
triage threshold         = 0.66   # no longer a gate; only labels kept/rejected
store.MAX_ITEM_AGE_DAYS  = 60     # must match `trib prune --days` in the workflow
topics floor             = 0.55   # re-measured on everything: no gap, 9% filler
topics park_margin       = 0.02   # parks about 13% of stories on a shelf
topics fallback_floor    = 0.50   # unmeasured; 0.55 caught 20 stories in 5,983
```

bge puts unrelated text near 0.5, so the usable similarity range is about
0.5–1.0. Matches and hard negatives genuinely overlap (matches as low as 0.888,
different same-week papers up to 0.944); 0.92 honours "a wrong merge costs more
than a missed link". `trib calibrate` re-measures it against tier-1 ground truth
as the corpus grows. For triage, `trib triage --by-source` should show a
gradient — research feeds 80–100% kept, general tech 20–30% — and a uniform
rate means the profile is measuring text length, not relevance.

## Beyond AI: one tree of general news (2026-10-05)

The owner sent a picture of the tree they wanted — News at the hub; Technology,
Culture, Sport, Politics, Security, Economy, Environment and Health around it;
three subtopics each — and chose that **AI sits under Technology** and that the
published site carries the new categories too. So:

- **The spine is any depth.** `parent` chains to any depth; only topics nothing
  sits under are scored, and parking stops at the parent the top two share, so
  every rule under "Labelling" holds unchanged. AI's ten topics are now under
  `ai`, which is under `technology`. The loader rejects a loop and a slug used
  twice. A label in the bundle carries `path`, every topic above it, so the
  page puts a story in Technology because it was filed under Coding agents.
- **Two slugs were taken.** AI's `chips` (Chips & datacenters) and `climate`
  exist, so Technology's Chips is `tech-chips` and Environment's Climate is
  `climate-change`. They compete in the argmax with the AI leaves of the same
  name; the AI ones say "AI" in their descriptions, which is what separates them.
- **General news is kept for days, AI for a month.** `[topics] keep_days = 4`
  and `keep_days = 30` on `ai`; a topic inherits the nearest setting above it
  (`TopicsConfig.keep_days_for`) and the export drops older stories from the
  bundle only — the database keeps everything for `MAX_ITEM_AGE_DAYS`. General
  feeds publish many times what the AI ones do, and a month of them would not
  fit in a page.
- **20 section feeds** (BBC, Guardian, The Verge, The Record, Carbon Brief,
  STAT…) **fetch from Actions**, checked on the runs of 2026-10-06. **ESPN's
  feed answers an empty `text/html`** there and was dropped, and SemiAnalysis
  (on Substack, 403 since the rule above) went with it.
- **They bring about 2,000 items a day**, an order of magnitude over the AI
  sources, and the first bundle with them was **13 MB, 5,272 stories**. So
  besides days, a topic has `keep_most` — at most its newest N stories in the
  bundle, inherited like `keep_days`: 30 for general news, 0 (no cap) on `ai`.
  Watch `Wrote N stories (data.json … KB)` in the run log; that line is the
  page's load time.
- **A story no subtopic takes falls back to its category** (owner's call,
  2026-10-06). On the first day, Guardian World left 22 of 61 stories with no
  home and BBC Politics 16 of 24: three narrow subtopics per category miss
  domestic politics, books, celebrity news. So when every subtopic scores under
  the floor, the categories' descriptions are scored and the best one over the
  `fallback_floor` takes it (`topics._fallback`). That bar was the floor,
  0.55, on the first run, and caught 20 stories of 5,983 — a category's
  description is broad and a short headline sits near all of them — so it is
  0.50 now. Only then — they never compete with
  subtopics, so "only leaves are scored" still holds for every story a leaf
  will take. `LABEL_RULES` in the fingerprint re-labelled the back catalogue
  once for it; bump it whenever a rule changes and the config does not.
- **A category also competes with the subtopics directly under it**, and
  keeps a story it fits better (`topics._contest`, owner's call 2026-10-06):
  *Carlos Alcaraz … Japan Open final* went to Football, because Sport has no
  tennis and a final is matches and results. Only subtopics *directly* under a
  category: deeper down, as in AI two levels under Technology, shelves still
  never compete, so the rule that stopped a vague parent swallowing its
  children holds there. Unmeasured — neither the database nor the model was
  reachable when it was built; `trib run`'s "N to a category" counts both
  this and the fallback, and `trib topics --why` shows a story's scores.
- **The bundle size stays as it is for now** (owner's call, 2026-10-06): 8.4 MB
  raw, 3.1 MB transferred, nearly all AI's thirty days (4,942 of 5,189 stories).
- **The triage profile is still about AI.** It only scores, so general news
  ranks low in `score` and nothing is lost; nothing on the new page sorts by it.

## The redesign's backend, beside version 1

Step 2 of `NEXT.md` lives in the same code without changing what version 1
does. Migration 009 adds `profiles`, `reader_topics`, `reader_topic_sources`
and `reader_seen`, and an `origin` column on `sources`: `config` for the ones in
`config.toml`, `reader` for a feed a reader found. **`sync_sources` only ever
disables `config` sources**, so a config edit cannot switch off a reader's;
`readers.reconcile_sources` enables a reader source while some topic uses it.
`readers.py` holds profiles and topics, `suggest.py` turns a subject or a site
into candidate sources with previews, and `api.py` serves both under
`/api/next/` plus the built page (`web-next/dist`) at `/`. The embedding
model is injected, as everywhere: `save_topic` embeds a topic's description only
after its sources validate, and a model that cannot load leaves the topic saved
without a vector rather than failing the request.

**A topic can be taught by a story** (migration 010, 2026-10-07): *"If I am
interested in this event and want to follow it I would like to create a topic
about it."* "Follow this story" on the story sheet saves a topic with
`examples` (story ids) and, as its vector, their centroids' mean — computed by
the server from full-precision item vectors, never an embedded headline. The
page matches it by `likeExamples`: the example itself, or a centroid within
`EVENT_FLOOR = 0.82` of it, far stricter than `FIT_FLOOR` because an event's
topic wants follow-ups, not its whole subject. Its words are not asked, and it
takes every source, since an event's follow-ups come from anywhere. Unmeasured;
the sheet previews what it would already hold before you follow.

## How it runs

`.github/workflows/update.yml` runs `trib run`, `trib prune --days 60` and
`trib export`, then publishes to GitHub Pages — on every push to `main` and
every three hours at minute 17. The database lives in the Actions cache, because
git stores every version of a binary in full; a cache miss is survivable, since
the run rebuilds from the sources. Scheduled workflows are disabled after 60
days without a push.

Actions runs on cloud IPs, which is why Substack sources fail there.

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
for. Posting and commenting on a topic is a separate requirement, parked in
`NEXT.md` until the redesign has users.
