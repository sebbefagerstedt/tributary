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

**The measured complaint is chrome.** At 390×844 the header was 182px — 22% of
the screen — with only three cards fully visible before scrolling, and six rows
above the first headline: brand and profile, tabs, topics, subtopics, facets,
and search, with the Trending scope row making a seventh. The subtopics row has
since been deleted and the Feed's remaining rows no longer carry an "All" chip,
so **re-measure before designing against that number**. The point stands: most
of it was added one row at a time, and following now does the job several of
those rows were built for, so the question is which of them still earn their
place rather than how to make them shorter.

**The original complaint was "boring"**, said of a feed that was mostly release
churn — some of which was the prerelease leak, now fixed, and some of which was
the ranking, now moved to Trending. Worth looking at the live feed again before
designing against a screenshot that no longer represents it.

Open, and nobody has decided: whether the card list survives at all, whether
topics and facets stay as filter rows now that following exists, and whether
the digest or the feed is the front door.

## Tapping a topic should open the topic

**Asked 2026-09-19**, after following at both levels started working:

> I need to be able to follow topics on different levels which seems to work.
> But I want the topic to popup so it is clear what is followed. Also nothing
> shows up when I click a topic

**Both halves are the same gap: in the digest, nothing you can tap opens a
topic.** Verified against the live bundle, the three clickable things on a
subject row do this:

| What you tap | What happens |
|---|---|
| The shelf name (`data-to-feed`) | goes to the Feed, **unfiltered** — no banner, no sign of the subject |
| A leaf chip (`data-follow`) | toggles the follow. The page does not move; only the chip tints |
| The lead headline (`data-open`) | opens the story sheet — the only one that opens anything |

So "nothing shows up when I click a topic" is literally true, twice over, and
for two different reasons.

**The shelf name is a regression, and a cheap one to undo.** It used to walk
into the topic; it was changed on 2026-09-19 to clear the scope instead, because
going via Topics was leaving a filter on the Feed that you met days later with
no memory of setting it. That fix was right about the filter and wrong about the
name — the answer is for the name to *open* the subject, not to navigate
nowhere. `data-goto` still does exactly that and the story chip still uses it.

**The leaf chip is an affordance collision.** The same chip shape navigates in
the Trending sheet and follows in the digest, and only a tint tells them apart.
Whatever replaces this has to make "follow" a control rather than a chip state.

**What is being asked for is a topic sheet** — the same gesture the story
detail, the profile chooser and the filter sheet already use. It would answer
both halves at once: what this subject is, what sits under it, how much is
unread, and a follow control *per level* so the shelf and its leaves are visibly
separate choices.

**There is a reference design.** Ticketmaster's artist page, offered 2026-09-19
as *"Jag gillar denna design"*: a hero with the subject's name over its image,
a **back arrow top-left**, a **heart top-right**, tabs across the subject
(`KONSERTER / OM / SETLISTS / …`), then a count with a view toggle, a filter
control, and the list. What it lends this problem:

- **The heart in the hero is the answer to "clear what is followed".** The
  follow state belongs where the subject's name is, not in a row somewhere else.
- **It is a page, not a sheet.** Worth noticing, because the earlier note asked
  for a "popup". A hero, tabs and a filter row do not fit in a sheet, and the
  back arrow only makes sense on a page. Decide which before building either.
- **Tabs are how one subject holds several kinds of content.** Tributary's
  equivalents would be its stories, what sits under it, and who keeps appearing
  in it — which is the three-axis model arriving in the UI.

**Back should climb, and today nothing is on the stack to climb.**
*"när man klickar tillbaka ska man komma upp en nivå liksom"* — story → leaf →
shelf → feed. `openStory` already does exactly this for one level, on purpose:
it pushes a history entry so the phone's own back gesture closes the story
rather than leaving the site. Nothing else pushes anything, so back from inside
a topic leaves Tributary entirely. The mechanism is right and the coverage is
one level deep; extending it is the shape of the work, not inventing it.

**The undecided one is how you go down.** In the owner's words: *"Om alla dels
ska synas i huvudtopic och kunna filtreras eller om man måste klicka in på
subämne för att 'filtrera'"* — either a shelf shows everything beneath it and
its leaves are a filter row inside that page, or a leaf is a page you have to
enter. Nothing is decided, but the first is cheaper than it looks and the second
is worse than it looks:

- `hasTopic` already matches a shelf through `parent`, so a shelf page showing
  all of its leaves' stories needs no new query.
- Under **one home** a story sits on exactly one leaf, so a shelf's stories
  *are* its leaves' stories — there is no separate "shelf-level" content for a
  leaf page to be hiding.
- The leaves are thin. The largest leaf is 10% of the corpus and most are far
  smaller, so a leaf-as-page is often a handful of cards behind an extra tap.

Still open:

- A shelf and its leaves are independent follows today. Does following a shelf
  show its leaves as followed, or stay separate? `isFollowed` already treats a
  shelf follow as covering its leaves for the *feed*, so the UI currently says
  less than the behaviour does.
- Where entities fit. They are followable and have no level at all, so they
  either share the design or stay a flat row.

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
- **A cyber-misuse story landed under Companies & money.** Seen 2026-09-19:
  *"Gemini Hacked Three Companies in First Known Breakout by Google's AI"* took
  `Industry & policy › Companies & money`. The owner's read: *"I am not sure if
  it is wrong but I would not know that this is where a news like this would
  land."* The leaf that describes it exists — `misuse`, *"models used for harm:
  bio, cyber and influence operations, and what guards against it"* — and under
  one home a story cannot have both. Nothing here is measured yet; the database
  it happened on is the deployed one. What is worth checking, in order:
    - **There is no way to ask why a story landed where it did.** `trib topics`
      has `--stats`, `--suggest` and `--reset`, and none of them print a story's
      scores against the spine. Every question below needs that first, and it is
      a few lines over `topics.centroids` — build it before theorising.
    - **The likely cause is that the prose is about companies.** The summary
      names Google, OpenAI, Anthropic, Meta, Irregular and the WSJ, and reads as
      a disclosure story; `companies` is *"AI companies, funding, acquisitions
      and competitive moves between labs"*. If that is it, the story is scoring
      honestly against what it is written like, not what it is about, and no
      rewording of `misuse` fixes the general case.
    - **Then it is the known runner-up problem, not a bug.** `CLAUDE.md` already
      records that 41% of stories have a runner-up on a *different* shelf within
      0.02 and those pick a side, with a "related topics" row as the answer
      rather than multi-label. Check the margin before treating this as a
      spine defect: a 0.01 margin and a 0.15 margin are different faults.
    - **The lexical axis misses it too, and that part looks like a real gap.**
      Facets exist precisely for subjects that cut across the spine, but the
      `safety` pattern is `\bsafety\b|jailbreak|prompt injection|\balignment\b|misalign`
      and the story's words are *hacked*, *guessed passwords*, *credentials*,
      *intrusion*. A security pattern covering breach, exploit and credential
      would mark this story whatever leaf it lives on — which is the cheap half
      of the fix, and the half that does not touch anything calibrated.
- **Search is narrowed by the active topic, silently.** From the same session:
  with `Safety & security` selected, searching "Google" returned *"Nothing
  matches google"* while the Gemini story sat one shelf away. `visible()` scopes
  before it searches, which is deliberate — the comment there means search cuts
  across *tabs*, not across a filter — but the empty state names only the query.
  It is what made the misfiling above look like an absence. Either search should
  ignore the topic filter, or the empty state should say the filter is on.

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
