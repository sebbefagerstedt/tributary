# Tributary — what is next

Only upcoming work lives here. **When something is built, delete its entry** —
history is in git, and the reasoning behind how things work is in `CLAUDE.md`.

## Posting and commenting — the one that changes the architecture

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

## Product launches — a different subject, and a different shape

**Asked 2026-09-19**, alongside a screenshot of a fitness-tracker review page:

> For later, this product would be really interesting for me. I want to be able
> to find things like this earlier, perhaps not always get it in feed but if I
> search for a product. I want to be abe to see new releases close to their
> launch

That is three wants, and only the first resembles anything that exists:

1. **New consumer hardware, near its launch.** Sources and config.
2. **Not necessarily in the feed** — a place you go, the way Trending is.
3. **Findable by searching for a product heard about elsewhere.** The hard one,
   and not a feature the current architecture can grow into.

**Triage currently excludes exactly this.** `config.toml` lists *"consumer
gadget reviews, phones, smartwatches and TVs"* under `exclude`, so this material
is dropped before it can become a story. That line is right for an AI feed, and
has to move before any of the rest matters.

**Search cannot do what is being asked.** The page searches the loaded bundle —
the most recent stories and nothing else. Looking up a product you heard about
elsewhere finds nothing, because the corpus is what the cron fetched, not what
you asked for. Doing it properly means fetching *in response to a query*, which
is a different shape from a scheduled pipeline whose adapters never touch the
database. It is the first thing this repo would want that is not a stage.

**The supply in this category is mostly affiliate content, and that is the
engineering problem.** The page that prompted this is the standard form: a sum
spent on testing, a newcomer that wins every category, no subscription, and a
domain nobody has heard of. Whatever any single one is worth, the format
dominates the category, and embeddings will not separate it from a real review —
both are prose about a gadget in the same register. This is the facets lesson
again: some distinctions are structural, not semantic. The signals that would
work are lexical and structural — who published it (a manufacturer's own
newsroom, a publication with a masthead, or a domain registered this year),
whether every outbound link carries a tracking parameter, and how close the
piece sits to an actual launch date.

**Try the cheap answer first.** `CLAUDE.md` already argues that "a Tributary for
X is mostly a second config": consumer hardware has its own sources — Product
Hunt, manufacturer newsrooms, r/gadgets, publications with real review desks —
and its own triage profile. That answers wants 1 and 2 for about the cost of a
config file. It does not answer want 3, and it costs a second feed to check,
which is close to the thing being asked to avoid.

## Redesign the frontend

**Asked 2026-09-19**, in those words and no more, so the brief is open. What is
known, so it is not rediscovered:

**It is a self-contained job.** The page is one file with no build step and the
JSON bundle is the contract, so a rewrite touches nothing else in the repo —
that was the point of the split. What a replacement must keep is small: the
four surfaces and what orders each, follows and marks namespaced per profile in
`localStorage`, and the fact that it has to work as a static file on GitHub
Pages with no server behind it.

**There is already a design brief for this, one section down** — "A feed you can
get through at TikTok speed". That entry is the *why*; this is the permission.
They should be read together rather than answered twice.

**The measured complaint is chrome.** At 390×844, the header is 182px — 22% of
the screen — and only three cards are fully visible before scrolling. Six rows
stack above the first headline: brand and profile, tabs, topics, subtopics,
facets, and search, with the Trending scope row making a seventh. Most of that
was added one row at a time, and following now does the job several of those
rows were built for, so the question is which of them still earn their place
rather than how to make them shorter.

**The original complaint was "boring"**, said of a feed that was mostly release
churn — some of which was the prerelease leak, now fixed, and some of which was
the ranking, now moved to Trending. Worth looking at the live feed again before
designing against a screenshot that no longer represents it.

Open, and nobody has decided: whether the card list survives at all, whether
topics and facets stay as filter rows now that following exists, and whether
the digest or the feed is the front door.

## Ready to start

- **"More like this" on a story page.** Nearest-neighbour over vectors already on
  disk, and easy now that a story has a centroid. This is the rest of "I want to
  keep reading if I find something interesting".
- **Podcast links.** Podcast feeds are RSS, so this is config plus a check that
  the `rss` adapter reads enclosures sensibly; the feeds are already found and
  verified (see "Sources" in `CLAUDE.md`). Latent Space's podcast feed carries
  full transcripts, which makes it the one podcast that embeds well today.
  Summaries are the wanted half, and are Phase 4.
- **YouTube channel feeds.** Plain Atom, so `kind = "rss"` should take them;
  channel IDs are in `CLAUDE.md`. Untested from Actions, where YouTube is known
  to block transcript fetching — check that the *feed* endpoint survives a run
  before relying on it. Use channel feeds, not playlist feeds.
- **TLDR AI and Anthropic** need a two-stage adapter — fetch a listing, then one
  request per page, emitting one item per story. Needs the HTML parser the repo
  does not have. Why TLDR cannot be plain RSS is in `CLAUDE.md`.
- **Extract linked URLs as join keys**, so a post clusters with the thing it is
  about. The guards it needs are in `CLAUDE.md` under Sources. Touches
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

## Needs a decision, or a look

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

## Designed, deliberately not built

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

## Blocked on something external

- **Phase 4 — YouTube/podcast transcripts, claim extraction, timestamp
  deep-links.** The differentiated feature. **Will not work on GitHub Actions** —
  runners are cloud IPs and YouTube blocks them. Needs a residential connection:
  the WSL machine, or a Pi at home pushing to the same repo.
- **Phase 5** — notes/takes layer, interaction-learned ranking, "catch me up"
  digest.
- **Phase 6+** — multi-user.

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
