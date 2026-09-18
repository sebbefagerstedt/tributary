# Tributary — state and remaining work

Live at **https://sebbefagerstedt.github.io/tributary/**, rebuilt every three
hours at minute 17. 314 tests passing, lint clean.
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
| Mixed news and social | Built, Reddit included |
| Facts from articles *plus the people commenting* | Built — the wake |
| A subject channel, `r/AI` | Built — topics |
| One event, everything about it | Built — the story page |
| Start with news, to gather | Built |
| **Verifierad (mer trovärdig)** | **Not built** |
| **reddit** / tiktok / youtube, for quick info | Reddit built; video not |
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

**The ripple is not the whole of it, though.** Asked for 2026-09-17: *users need
to be able to post and comment directly on a topic.* That was previously written
down here as parked; it is not parked, it is a requirement. See "Posting and
commenting" below — it is the one item in this file that changes the
architecture rather than adding to it.

---

## What is left to build

### Posting and commenting — the one that changes the architecture

**Users need to be able to post and comment directly on a topic.** Asked for
2026-09-17, and it is what finishes the idea the rest of the app has been
building toward: a topic you *enter* is a place, and a place is where people
write. It also joins up two earlier notes — that users should tag news onto
topics themselves, and that they should be able to create a story by hand —
into one capability rather than three features.

**The read path already exists.** `Kind.POST` is defined, `cluster.py` maps it
to the `coverage` role and `_KIND_PRIORITY` ranks it — no adapter has ever
produced one. A user's post on a topic is an item like any other: it joins
`story_items`, takes a role, earns a chip, and appears in the wake. The
`follows` table (`target_kind: topic|entity|source`) has been sitting unused
since the first commit and is the subscription side of the same feature.

**The write path is what does not exist, and it is not a small thing.** Every
deployment assumption in this repo comes from the app being read-only:

- `data.json` is a static bundle rebuilt every three hours. Posts have to appear
  when written, not on the next cron tick.
- Per-device state lives in `localStorage` *because a static host has nowhere
  else to put it*. That works for seen/saved/dismissed, which are preferences.
  It cannot work for a post, whose entire purpose is that someone else reads it.
- So this needs a writable backend, with identity, moderation and spam handling
  behind it, and it ends the zero-cost GitHub Pages model. `trib serve` already
  exists and is the obvious starting point, but a server someone else can post
  to is a different thing from one you run locally.

**What it does not need is an API key.** Posting is not an LLM feature, and the
no-API-key constraint holds — worth stating, because "community features" and
"AI features" tend to get budgeted together and these should not be.

Open questions, none decided:

- Is a comment an item (so it joins the wake and gets a role), or its own table?
  Item-shaped reuses everything; comment-shaped avoids polluting the corpus that
  clustering and topic assignment run over.
- Does a user post get triaged and embedded like fetched material? If it does,
  it can be clustered and labelled automatically. If it does not, the author
  places it by hand — which is closer to how Reddit works, and to the
  propose-then-accept model already chosen for topics.
- Who can post, at what point does that need real accounts, and what happens the
  first time someone abusive arrives.

### Ready to start

**Left over from the three-axis rebuild** — finished 2026-09-18 except where
marked:

- ~~The page does not render facets or entities.~~ **Done.** A third filter row
  of facets, counted *within* the current topic so every chip leads somewhere,
  and entity names on cards and the story sheet as doors into "everything that
  names this, across every topic". Entity view has its own banner and a way
  back out. Neither facet nor entity is persisted — a stale refinement on open
  is the same bug as a stale search. Verified by driving the exported page in
  jsdom; **headless Chromium does not run on this machine** (missing
  `libnspr4.so`, needs `sudo apt`), which is worth fixing before the next UI
  change.
- ~~No tests for `facets.py` or `entities.py`.~~ **Done** — 27 across the two,
  plus config validation. Writing them found a real bug: the Llama *model* was
  matching `llama.cpp`, because `.` is not a word character. A dot followed by
  more word now counts as part of the word.
- ~~Entity extraction proposes nothing.~~ **Done** — `trib entities --suggest`.
  Reads summaries rather than titles (Title Case headlines make every word look
  like a name), and throws out anything also written in lower case elsewhere,
  which is the test that separates `Astra` from `Learning`. **About half its
  output is wrong** — eponyms like `Gaussian` and `Markov` pass every test —
  which is acceptable for a list a person reads, and is why accepting stays
  manual. Hub and repo *owners* were tried as a second source and dropped: they
  are mostly one-off individuals (`ukisai`, `dealignai`), not entities.
- ~~`GitHub Releases` still carries nightly builds.~~ **Done.** Prereleases are
  skipped by default, and that turned out to be the whole fix: `llama.cpp` flags
  its per-commit builds as prereleases, as does Ollama its release candidates.
  Set `prereleases = true` on a source that wants them.
- ~~`/suggest-topics` still describes the old model.~~ **Rewritten**, and it
  needed a code change underneath it: under one home nearly nothing is
  "unclaimed", so `trib topics --suggest` sorted every group at zero. It now
  counts **parked** stories per group and sorts by those, since a pile parked
  on a shelf is what a missing leaf looks like.
- **Still open: `Flash`, `Sol` and other bare model suffixes.** The proposal
  pass finds them, but as entities they would be ambiguous (`Flash` claims
  every flash-attention paper). The skill says to qualify them — `Gemini Flash`
  — or leave them out; a smarter extractor would propose the qualified form
  itself by reading the word before.
- **Still open: patch-release chatter.** `transformers v5.15.1`,
  `ollama v0.33.3` and LangChain's per-package tags (`langchain-core==1.6.3`)
  are real releases and pass the prerelease filter, but few are news.

- **`cli.py` is ~900 lines.** By far the largest file; first thing to split.
- **TLDR and the Anthropic source** still need the two-stage adapter described
  below. Note this is *not* the same as reading a page's description, which
  `describe.py` now does: TLDR needs an issue page split into one item per
  story, which is real HTML parsing rather than a meta tag. **The one unverified
  thing in that section is now verified**: `https://tldr.tech/api/rss/ai`
  returns 200 at roughly 5 items a week. Everything else there still holds.
- **Podcast links.** Podcast feeds are RSS, so this is an adapter and a config
  block. Summaries are the wanted half and are Phase 4, not this.
- **Extract linked URLs as join keys**, so a post clusters with the thing it is
  about. See "Commentary arrives without the thing it comments on" below. This
  touches clustering, which is calibrated, so it needs guards and tests rather
  than a one-line regex.
- **"More like this" on a story page.** Nearest-neighbour over vectors already on
  disk, and much easier now that a story has a centroid. This is the "I want to
  keep reading" path.
- **`trib status`** (db path, size, counts, last fetch) — suggested, not built.
- **README cleanup.** It reads as a build journal of design decisions. It should
  say what the tool is and how to run it; the reasoning moves here or goes.

### Needs a decision, not code

- **The `data.json` fallback in `/suggest-topics` is blocked by the egress
  proxy**, so the skill cannot run in a cloud session at all. Still a bug worth
  fixing. (Topic names and the loose threshold are both **done** — see "One
  home, three axes" below.)
- **Anthropic is not a source at all**, and should be. **Re-tested 2026-09-17
  and the premise holds**: no feed on `anthropic.com` or
  `alignment.anthropic.com`, on any guessed path, and no `application/rss+xml`
  in either page head. So this is the HTML-scrape adapter's first real customer.
  Two cheaper half-measures exist: their YouTube channel
  (`UCrDwWp7EBBv4NwvScIpBDOA`) has a working Atom feed, and third-party scrapers
  republish their news as RSS — trusting someone else's scraper for a primary
  source seems worse than having the gap.
- **Import AI**: drop it from `config.toml` or accept the gap. It returns HTTP
  403 on Actions because Substack blocks those IPs, and works fine locally.
- ~~**MarkTechPost** serves something that is not a feed.~~ **Fixed
  2026-09-17.** The cause was the fourth of the four: the site's own `/feed/`
  returns 403 to anything that is not a browser. The FeedBurner mirror
  `https://feeds.feedburner.com/Marktechpost` carries the same content and
  serves valid RSS; config now points there.

### Designed, deliberately not built

- ~~**The entity layer.**~~ **Half built 2026-09-17** — `entities.py` seeds the
  labs, model lines and tools from config and attaches them to stories by name
  and alias. What is *not* built is the propose-then-accept pass: extraction
  currently proposes nothing, so an entity exists only if it is in `config.toml`.
  That pass is the next piece, and `/suggest-topics` is where it belongs.
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
- ~~**Reddit** needs a manual API approval ticket.~~ **Wrong, and now
  shipped.** The per-subreddit `.rss` endpoints are public Atom and work with no
  credentials at all. Three things make it go, all verified 2026-09-17:
  a descriptive User-Agent (a default one gets 403 HTML before the rate limiter
  is reached — `http.py` already sends one); the multireddit form
  `r/a+b+c/.rss`, which spends a single rate-limit token on all three and
  interleaves them correctly, where separate sources would 429 each other; and
  `www.reddit.com`, since `old.reddit.com/.rss` now redirects to a login.
  Self-text posts carry 900–3600 characters of real prose; link posts are
  title-and-thumbnail only, so it behaves like Hacker News for half its items.
- **Phase 5** — notes/takes layer, interaction-learned ranking, "catch me up"
  digest.
- **Phase 6+** — multi-user.

---

## Decisions worth not rediscovering

### One home, three axes — the 2026-09-17 rebuild

**The old spine was one mechanism asked to answer three questions.** A GPT-6
release is *OpenAI* (a provider you follow), *a frontier model release* (a kind
of story), and *an event* (already a story). Only the middle one is a topic, and
only the middle one is semantic. Forcing the other two through cosine similarity
is what made the labels read as strange — `Research` held 54% of the corpus,
`Running it yourself` held a Dota 2 paper and an audio-datasets guide, and
`Policy & courts` held nothing.

So labelling is now three axes, each using the mechanism that suits it:

| Axis | Question | Mechanism | Per story |
|---|---|---|---|
| Topic | where does it live | embedding, argmax over leaves | exactly one |
| Entity | who is it about | name and alias matching | any number |
| Facet | what kind of thing is it | regex over title and summary | any number |

**One home, many doors.** A story is reached by its topic, by any provider or
model named on it, or by search. "One home is hard to find" was a symptom of the
entity axis being missing, not of having one home.

#### Why the threshold went away rather than getting retuned

Measured over the corpus, not guessed:

- At `threshold = 0.60`, **2020 of 2239 stories carried exactly 3 topics** — the
  cap, not a judgement. The average story cleared 6.9 of 11 topics.
- Raising it to 0.67 was tried and is *also* wrong: it killed `Policy & courts`
  outright (its best score against 600 stories is 0.64) and cut `Frontier
  models` to 3.
- **A relative margin fails too.** At a 0.05 margin one paper took **13 labels**,
  because 13 descriptions sat within 0.05 of each other. Everything lands in a
  0.60–0.85 band; there is no gap to cut at.

So there is no line to draw, and drawing one better is not the fix. The question
"of these topics, which one is this?" needs no scale at all — a comparison is
scale-free, so nothing drifts when the embedding model changes or the spine
grows. `floor = 0.55` remains, but it is not a threshold in that sense: it
catches a story the spine has no opinion about whatsoever, which over the whole
corpus is **one story in 2239**. If it starts firing, the spine is wrong.

#### Only leaves are scored

A shelf earns its stories from whichever of its leaves wins. This is what stopped
a broad topic swallowing the feed: `Research` used to compete *against its own
children* and beat them everywhere, because vague prose sits near everything.
A shelf's `description` is now documentation for whoever edits the config, never
an input.

Result: 43 topics over 10 shelves, **largest leaf 10.3%** of the corpus against
the old 54%, and no leaf empty.

#### Parking, and what it is for

When the top two leaves are on the *same shelf* within `park_margin` (0.02), the
shelf is clear and the leaf is a coin-toss, so the story sits on the shelf.
Forcing a choice there invents precision the scores do not have. 291 of 2239
stories park. **The pile on a shelf is the signal that a leaf is missing**, and
is what `/suggest-topics` should read first.

#### Facets exist because some subjects are lexical

An agent paper is also a safety paper and a benchmark paper — it really is all
three, so similarity cannot separate it from its neighbours and files it under
whichever it most resembles. `RepoAtlas: Guiding Coding Agents` landed under
interpretability. Rewording the agent descriptions made it *worse*, not better:
the shelf fell from 28 stories to 12.

A word, meanwhile, is either present or not. Matching `\bagent(s|ic)?\b` finds
**133 stories in a fortnight where argmax found 25**, and every one is correct.
That is the whole argument for facets being regexes and not descriptions.

#### What this does not fix

41% of stories have a runner-up leaf on a *different* shelf within 0.02, and
those pick a side. Entities and facets are the compensation — other doors into
the same story — not a fix for the embedding space being compressed. If one-home
reads badly in practice, the next move is a "related topics" row on the story
page, **not** a return to multi-label. That was tried and measured; it is worse.

### The source scan of 2026-09-17, so it is not repeated

Verified by fetching, not guessed. **Added to config**: Ars Technica AI, MIT
Tech Review AI, IEEE Spectrum AI, SemiAnalysis, Mistral, Ai2, Together, NVIDIA,
vLLM, LangChain, Alignment Forum, LessWrong (curated), METR, CSET, lobste.rs,
Reddit. Roughly +90 items a week of non-paper material against arXiv's ~235,
which takes papers from 88% of the feed toward 60% **without cutting arXiv** —
that was an explicit instruction and still is.

**Substack is deliberately excluded.** It blocks Actions IPs, which is why
Import AI 403s on a run and works locally. That rules out Interconnects, Zvi,
Ahead of AI, Epoch, The Algorithmic Bridge and One Useful Thing — the best
commentary available, and the cost of every source behaving identically
wherever `trib` runs. Revisit only by moving fetching off Actions, which Phase 4
needs anyway. SemiAnalysis is on its own domain but has Substack history, so
confirm it from a runner before trusting it in CI.

**Worth having, not yet added** (all verified live):

- **YouTube**, via `youtube.com/feeds/videos.xml?channel_id=<UC...>`: Dwarkesh
  `UCXl4i9dYBrFOabk0xGmbkRA`, MLST `UCMLtBahI5DMrt0NPvDSoIRQ`, Two Minute Papers
  `UCbfYPyITQ-7l4upoX8nvctg`, AI Explained `UCNJ1Ymd5yFuUPtn21xtRbbw`, bycloud
  `UCgfe2ooZD3VJPB6aJAnuQng`, Welch Labs `UConVfxXodg78Tzh5nNu85Ew`, Karpathy
  `UCXUPKJO5MZQN11PqgIvyuvQ`, Anthropic `UCrDwWp7EBBv4NwvScIpBDOA`, Simons
  Institute `UCW1C2xOfXsIzPgjXyuhkw9g` (the best conference source found).
- **Gotcha worth keeping**: `playlist_id=` feeds return items in *playlist
  position* order, not upload order, so they silently look frozen — Stanford CS25
  and MLSys both do this. **Prefer a channel feed over a playlist feed.**
- **Podcasts**: Dwarkesh `api.substack.com/feed/podcast/69345.rss`, Latent Space
  *podcast* `api.substack.com/feed/podcast/1084089.rss` (**separate from the blog
  feed already configured, and it carries full transcripts — 125k characters on
  a sampled item**), Practical AI, TWIML, MLST `anchor.fm/s/1e4a0eac/podcast/rss`,
  Cognitive Revolution, No Priors, Last Week in AI. Hard Fork's public feed is
  effectively dead (3 items total) despite returning 200.
- **Bluesky has native per-profile RSS** at `bsky.app/profile/<handle>/rss`. No
  bridge needed, but per-profile only: no topic, list or search feeds exist.

**Confirmed not worth it**: TikTok has no feed of any kind and would need a
bespoke scraper against a private API — the worst cost/benefit of anything
examined. X/Twitter is pay-per-read since Feb 2026 with no free tier. Discord
and Slack need a bot joined to each server. Papers with Code now redirects to
`huggingface.co/papers/trending` and is dead as a separate source.

### Hugging Face: `base_model` is the signal, not likes

The "irrelevant models" complaint was aimed at the wrong source. **HF models in
the feed are already the popular ones** — 39 kept items, minimum 90 likes,
median 964. The junk was `GitHub Releases`, where 9 of the last 14 items were
`llama.cpp` nightly builds (`b10999`–`b11007`). `HF New Implementations` was
removed outright: it fetched 300 repos and kept zero.

For when model filtering is next touched, verified against the live API:

- There is **no server-side minimum-likes or minimum-downloads filter**.
  `min_likes=1000` is silently ignored. Filter client-side after the fetch.
- `sort=trending` **errors**; `sort=trendingScore` and `likes7d` are the same
  thing, and `likes7d` is already what the config uses.
- **A `base_model:*` tag is the clean signal for a derivative** — quantizations,
  merges and fine-tunes all carry it, originals have `base_model = None`.
  Verified on real repos both ways.
- **"Author is an organisation" does not work** as a filter: `unsloth` and
  `ISTA-DASLab` are registered orgs and are pure requant shops.
- Naming regex (`GGUF|AWQ|GPTQ|bnb-4bit|exl2`) caught only 13 of 50 derivatives
  in a real sample, so it is a secondary check at best.

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

**Update 2026-09-17: the schema is no longer unused.** `entities.py` seeds
entities from config and attaches them to stories by name and alias, and
`story_entities` is populated — 942 of 2239 stories name at least one. `follows`
is still untouched. What follows was written when none of it was wired up, and
the reasoning still holds for the half that is not:

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

### Commentary arrives without the thing it comments on

Found 2026-09-17 from a case in the live feed: Simon Willison's write-up of an
Anthropic announcement was there, and the announcement was not. Two independent
causes, and it takes both to produce that.

**The announcement was never fetched**, because Anthropic is not a source. See
the item above. Note `always_keep` in `config.toml` already lists `anthropic`
and `claude`, so triage is primed to keep this material -- there is simply none
arriving to keep.

**And even with the source, the two would not have joined.** `identity.py`
treats a plain URL as a *strong* identifier, but only finds one in three places:
the item's own `url`, its `canonical_url`, and `metadata.outbound_url`. The
free-text scan over title, summary and body looks for arXiv IDs, DOIs and GitHub
repos -- and no generic URLs at all. So:

| Item | Points at the announcement via | Joins today |
|---|---|---|
| A Hacker News thread | `outbound_url` | yes |
| A blog post about it | a link in the body | **no** |
| The announcement itself | its own URL | n/a, not a source |

A post citing the thing it is about is the most common shape commentary takes,
and it is the one case that extracts nothing. Worse, the result is not a missing
link but a wrong one: `role_for` makes the first item in a story its seed, so the
commentary gets promoted to "the news" and the feed reads as though Simon
announced it.

**Why this was not already done, and what it needs.** A blog post links to
dozens of things -- navigation, the author's own archive, related posts -- and
this is the same trap as "Why not GitHub repo search" below: lists cite
everything, so an unguarded rule collapses unrelated stories. `MAX_FANOUT = 8`
catches an identifier shared across many items, but not a single post that
sprays ten bad links at once. So a link is only a citation when:

- it leaves the item's own domain (a self-link is navigation, not a citation);
- the item cites few enough URLs to mean them. A link roundup -- which is a
  whole genre, Simon's own weeknotes included -- should extract nothing rather
  than join everything it mentions;
- `_has_specific_path` already holds: a bare homepage identifies a publication,
  not a story.

Test it against the existing calibration before trusting it: the cost of a wrong
merge is still higher than the cost of a missed link.

### A feed does not fail because its XML is bad

Measured 2026-09-17, because the obvious fix was the wrong one. feedparser
recovers from malformed XML far better than its error message suggests. A bare
ampersand, an undeclared `&nbsp;`, a raw control character, junk printed above
the declaration, and a file truncated mid-item **all still yield their items**.
A sanitiser for any of that would be dead code: the adapter only gives up when
there are no entries at all, and none of those produce that.

Zero entries means the body was never a feed. Four causes, needing four
different fixes:

| What arrived | Why | Fix |
|---|---|---|
| A web page | Bot check or login wall, served with a 200 | Different URL, or drop the source |
| JSON | An API error the CDN returned instead | Read the error |
| Wrong encoding | UTF-16 body declaring UTF-8 | Decode before parsing |
| Nothing | Empty 200 | Retry or drop |

The parser's own message cannot tell these apart — all four say "not
well-formed (invalid token)". So the adapter now reports the content type, the
size and the opening bytes, which separates them at a glance. An empty but
*valid* feed stays a success: a source with nothing new this week is not broken.

### Describing an item means finding where its words already are

The four strategies in `describe.py` are ordered by cost, and the first that
yields prose wins:

| | Where | Requests |
|---|---|---|
| `body` | Release notes already stored, which only `summary` ever reached the page from | none |
| `card` | A hub model card | 1 |
| `repo` | A GitHub repo's one-line description | 1, cached per repo |
| `page` | A linked article's `<meta>` description | 1 |

`page` reads **only** the meta tags, never the body. A page's body is cookie
banners, navigation and newsletter prompts, and picking prose out of it is the
part of scraping that goes wrong and keeps going wrong. A meta description was
written to be a one-sentence summary and is machine-readable by design. No
description means the item keeps its bare title, which is the honest outcome.

A Hacker News item is the one that needs care: the item *is* the discussion, so
the thing worth describing is what was submitted (`metadata.outbound_url`), not
the thread.

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
