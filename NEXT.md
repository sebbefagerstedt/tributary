# Tributary — state and remaining work

Live at **https://sebbefagerstedt.github.io/tributary/**, rebuilt every three
hours at minute 17. **Zero LLM/API usage — everything local and free.**

This file is for what is *not* built and what should not be rediscovered. What
shipped, and when, is in git; this keeps only open work and the decisions that
still constrain it. When something here gets built, delete its entry rather than
striking it through.

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
moreish. The ranking is deliberately not an engagement metric (see "How the
pipeline decides" below) — keep those two agreeing.

### What "community" means here: the ripple, not a chat room

The wanted thing is **what happened because of a story** — the projects people
started after the news, the arguments about it, the write-ups and the video
takes. A story is not the announcement; it is the announcement plus its wake.

**This is already the data model.** `cluster.py` gives every item in a story a
role — `seed`, `paper`, `code`, `video`, `discussion`, `coverage`. A repo citing
a paper's arXiv ID joins that paper's story as `code`; an HN thread linking an
announcement joins it as `discussion`. The ripple is computed on every run, and
renders as coloured chips on the card and grouped sections on the story sheet.

**The ripple is not the whole of it.** Users need to be able to post and comment
directly on a topic — a requirement, not a nice-to-have. See "Posting and
commenting" below; it is the one item here that changes the architecture rather
than adding to it.

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

- **"More like this" on a story page.** Nearest-neighbour over vectors already on
  disk, and easy now that a story has a centroid. This is the rest of "I want to
  keep reading if I find something interesting".
- **Podcast links.** Podcast feeds are RSS, so this is config plus a check that
  the `rss` adapter reads enclosures sensibly; the feeds are already found and
  verified (see "The source scan" below). Latent Space's podcast feed carries
  full transcripts, which makes it the one podcast that embeds well today.
  Summaries are the wanted half, and are Phase 4.
- **YouTube channel feeds.** Plain Atom, so `kind = "rss"` should take them;
  channel IDs are verified below. Untested from Actions, where YouTube is known
  to block transcript fetching — check that the *feed* endpoint survives a run
  before relying on it. Prefer channel feeds to playlist feeds (see the scan).
- **TLDR AI and Anthropic** need a two-stage adapter — fetch a listing, then one
  request per page, emitting one item per story. Needs the HTML parser the repo
  does not have. See "TLDR AI is a digest, not a feed".
- **Extract linked URLs as join keys**, so a post clusters with the thing it is
  about. See "Commentary arrives without the thing it comments on". Touches
  clustering, which is calibrated, so it needs guards and tests rather than a
  one-line regex.
- **Qualified entity names.** `trib entities --suggest` proposes bare model
  suffixes like `Flash` and `Sol`, which would be ambiguous as entities (`Flash`
  claims every flash-attention paper). Reading the word before would let it
  propose `Gemini Flash` instead.
- **Patch-release chatter.** `transformers v5.15.1`, `ollama v0.33.3` and
  LangChain's per-package tags (`langchain-core==1.6.3`) are real releases, so
  they pass the prerelease filter, but few are news. A rule like "minor versions
  and up" would need care: projects version very differently.
- **Headless Chromium does not run on the dev machine** — it is missing
  `libnspr4.so` and friends. `sudo .venv/bin/playwright install-deps chromium`
  fixes it. Until then the page can only be driven through jsdom, which does not
  lay anything out.

### Needs a decision, or a look

- **Watch the first scheduled runs of the new sources.** Reddit and SemiAnalysis
  were verified from a home connection, and Actions runs on cloud IPs. If either
  shows as failing in `trib status` or at the foot of the page, that is why —
  the same way Substack blocks Import AI.
- **Import AI**: drop it from `config.toml` or accept the gap. It returns HTTP
  403 on Actions because Substack blocks those IPs, and works fine locally.
- **Anthropic is not a source**, and should be. It has no feed on `anthropic.com`
  or `alignment.anthropic.com` under any path, and no `application/rss+xml` in
  either page head — so it is the HTML-scrape adapter's first real customer. Two
  half-measures exist: its YouTube channel (`UCrDwWp7EBBv4NwvScIpBDOA`) has a
  working feed, and third-party scrapers republish its news as RSS, though
  trusting someone else's scraper for a primary source seems worse than the gap.
- **Stories clustered before the `role_for` fix carry stale roles.** Roles are
  stored, not recomputed, so a paper's own coverage can still be labelled as a
  second seed in old stories. `trib cluster --reset` once, on the database that
  matters, rebuilds them.

### Designed, deliberately not built

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
- **Nothing discovers reactions.** `sources/github.py` polls a fixed list of
  repos for *releases* and cannot find a new project built on a story. Hugging
  Face's `arxiv:` tags partly cover artefacts, and Reddit now covers some of the
  argument; nothing finds the new project.
- **Following.** The `follows` table (`target_kind: topic|entity|source`) has
  existed since the first commit and nothing uses it. Now that entities exist,
  "follow OpenAI" is a query away; what is missing is somewhere to say it.

### Blocked on something external

- **Phase 4 — YouTube/podcast transcripts, claim extraction, timestamp
  deep-links.** The differentiated feature. **Will not work on GitHub Actions** —
  runners are cloud IPs and YouTube blocks them. Needs a residential connection:
  the WSL machine, or a Pi at home pushing to the same repo.
- **Phase 5** — notes/takes layer, interaction-learned ranking, "catch me up"
  digest.
- **Phase 6+** — multi-user.

---

## Decisions worth not rediscovering

### One home, three axes

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

### The source scan, so it is not repeated

Done 2026-09-17, verified by fetching rather than guessed; what it found worth
having is in `config.toml` now. The aim was balance: the feed was 88% arXiv, and
about 90 items a week of non-paper material against arXiv's ~235 moves that
toward 60% **without cutting arXiv** — an explicit instruction, and still one.

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

**"Only the most popular models" is already true of Hugging Face.** Its models in
the feed had a minimum of 90 likes and a median of 964; the junk that read as
"irrelevant models" was GitHub release builds, now filtered. For when model
filtering is next touched, verified against the live API:

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

### Topics are an ontology

Three different things were once squeezed into one flat topic list:

| Level | Example | How it is made |
|---|---|---|
| **Category** | "Frontier model releases", "Speed, memory & cost" | Few, stable, hand-made — the topic spine |
| **Entity** | "OpenAI", "Astra", "Hugging Face" | Extracted, then accepted by a human — `[[entities]]` |
| **Event** | "the huggingface incident", "Astra 6.1 released" | Automatic — it is a story |

Hardcoding is right for the first level and wrong for the other two, which is
why the flat list read as "hardcoded from specific sources". "One home, three
axes" above is this table built.

**A tree will not hold, and does not have to.** The huggingface incident belongs
under Astra *and* under OpenAI. Topics are a tree because browsing wants one;
entities are what make the whole thing a graph, since a story can name any
number of them.

**Reddit cannot be copied.** Subreddits are user-created, the namespace is flat,
and there is no hierarchy in the data model — r/MachineLearning and r/LocalLLaMA
are unrelated. Apparent relatedness is convention: sidebar links, naming, and
multireddits, which are personal rather than shared. Flair is the only real
sub-level. The load-bearing part is that **a human classifies at submission
time**; no algorithm assigns posts to subreddits. Tributary has no submitters,
so classification has to be automatic — the same problem wearing different
clothes.

**The way through is propose, then accept.** Extraction proposes; a human
accepts, renames or rejects; accepted names go in the config. That recovers
Reddit's human-decides property without needing a crowd, and it is how a topic
ends up called whatever people actually call it. Sebastian is that human for
now, and the mechanism generalises to users later.

Still open:

- **Being first.** Frequency across stories is how candidates are ranked, and it
  is reliable but late: a brand-new name is interesting on day one and only
  frequent by day three.
- **Where review happens.** The `/suggest-topics` skill at a terminal works;
  accepting from the phone is where it would actually get done.

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
matching. That still works for every hub source.

A dedicated source built on it did not. `cites_paper` keeps only repos citing a
paper, meant to turn newest-first over the hub into "someone implemented this".
Asked for 300 repos, it kept **zero** — the hub has no server-side filter for it,
so the limit is spent before the filter runs, and newest-first is almost
entirely requants. The option remains; the source was removed.

### TLDR AI is a digest, not a feed

Researched, not implemented. The official feed is
`https://tldr.tech/api/rss/ai` — verified, about five issues a week.

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

Found from a case in the live feed: Simon Willison's write-up of an Anthropic
announcement was there, and the announcement was not. Two independent
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

### How the pipeline decides, in brief

Moved here from the README, which now only says how to run things.

- **Fetching is idempotent and polite.** Items are keyed on
  `(source, external_id)`. Conditional GET turns unchanged feeds into 304s, and
  for feeds without ETags a content hash means a re-parse writes nothing. A
  repeat fetch with no upstream change performs zero writes.
- **One source failing never stops a run.** The failure is recorded against the
  source, so a dead feed is a visible health row rather than a silently missing
  morning. `trib run` still exits non-zero, so a scheduler notices.
- **Adapters never touch the database.** They take fetch state in and return
  items plus new state, which keeps them testable without one — and is why
  anything that needs to read stories is a pipeline stage, not a `Source`.
- **Embeddings are local.** Triage scores every ingested item, and paying per
  token to decide what to throw away would invert the economics. fastembed runs
  bge-small under ONNX: ~200MB, against the ~2GB a torch install costs.
- **An HN item is the discussion, not the article.** Its URL is the thread; the
  submitted link becomes a join key connecting the thread to the article.
- **Clustering runs cheapest and most precise first.** Tier 1 is a shared strong
  identifier (arXiv id, DOI, canonical URL, hub model, release tag) — exact and
  free, and it earns its place: two HN posts with the *same* headline scored only
  0.888 on embeddings but joined instantly on their shared outbound URL. A repo
  is graded weak because hundreds of unrelated items reference one, and anything
  shared by more than 8 items is a category, not an event. Tier 2 is embedding
  similarity inside a 14-day window, for coverage that never cites its source.
  Tier 3, LLM adjudication of the ambiguous band, is designed for and not wired
  up; those items simply start their own story.
- **Ranking is recency-decayed relevance**, with a 48-hour half-life and a
  capped bonus for stories several independent sources covered. It must resist
  volume: arXiv publishes ~150 papers a day where a blog publishes one, and pure
  recency-times-relevance handed it 47 of the first 50 cards. The feed damps each
  *repeat* from a source or kind as it is built, which restores a mix with no
  hard quota — a day where arXiv genuinely is the news still leads with arXiv.
- **The page has no build step.** A bundler would be the heaviest thing in the
  repo for what is a card list. The JSON bundle is the contract, so replacing
  the frontend later touches nothing else.
- **A dense list, not full-screen snap cards.** One headline per screen is the
  opposite of scannable. This is the deliberate departure from "TikTok for
  news", and it is in tension with the TikTok-speed item above — that item is
  about pace and format, not about copying the snap.
- **The feed is never cached by the service worker**; only the app shell is. A
  stale feed is worse than an honest error.

### Calibrated values — measured, don't guess these again

```
cluster.MERGE_THRESHOLD  = 0.92   # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW    = 0.86
cluster.WINDOW_DAYS      = 14
triage threshold         = 0.66
store.MAX_ITEM_AGE_DAYS  = 60     # must match `trib prune --days`
topics floor             = 0.55   # 1 story in 2239 falls below it; not a tuning knob
topics park_margin       = 0.02   # parks 13% of stories on a shelf
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

### Reading a run's log for churn

`trib run` prints new, updated, unchanged and too-old counts. **All-new with
nothing unchanged is the shape of churn, not of news.** On a restored database,
items fetched three hours earlier should come back as updates; zero updated means
last run's items were gone.

That shape once meant feeds serving their whole archive were re-delivering
years-old entries every run — inserted, embedded, triaged, clustered, deleted by
the next prune, and fetched again. Hence `MAX_ITEM_AGE_DAYS`: an item older than
the retention window is dropped at ingest rather than stored, so nothing is
embedded that the next prune would delete. An item already stored is exempt and
ages out through prune instead, and undated items count as current, since
refusing them would empty the feed.

---

## Sebastian's open asks

Verbatim, because they are the sharpest statement of what is left. Delete each
one when it is built.

> I want to continue reading if I find something interesting.

Topics, entities and the story page cover most of this. The missing piece is
**"more like this"** — see "Ready to start".

> I also want links to podcast, and it would be reallt nice with podcast
> summaries

Links are config plus a check (see "Ready to start"); summaries are Phase 4, and
the one place an API key would genuinely buy something.

> I only want the most popular news, not everything. Otherwise it is not really
> news.

Constrained by a second instruction given at the same time: **do not cut
arXiv** — a new paper is real news whether or not anyone has reacted to it yet.
So this cannot be one global popularity gate, since that is exactly what would
drop arXiv. Per-kind thresholds are the likely shape.
