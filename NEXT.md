# Tributary — what is next

Only upcoming work lives here. **When something is built, delete its entry** —
history is in git, and the reasoning behind how things work is in `CLAUDE.md`.

## Posting and commenting — the next big step, and the one that changes the architecture

**This is the next big step: real accounts, a server, and topics that are shared
rather than personal.** Confirmed 2026-09-22, and it outranks everything else in
this file. "Personal lenses" below is not an alternative to it — a topic only
its author can see is not the feature — it is the way to build and use every
part of this one before paying for a host or writing a moderation policy.

**On hold until the owner decides to make the change**, said 2026-09-22 of both
this and the shared tier of personal lenses below. Nothing in either section
is to be started before then; the notes are here so the decision can be made
with them in hand.

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

**Hugging Face's paper page is the worked example.** Offered 2026-09-22, as a
screenshot of `huggingface.co/papers/…`: the abstract, then **Community**, then
comments — an author, a `Paper submitter` badge, a relative timestamp, prose, an
overflow menu. *"An example of how the comments could work is actually found on
huggingface. Here you have a paper and then community with comments."* It
settles three things and breaks one.

**Where the thread hangs: on the story, not on the topic.** This entry has said
"post and comment directly on a topic" since 2026-09-17, and the reference sits
one level below that — a *paper*, which here is a story. It is also the cheaper
end: `fillStory` already ends with the wake, so Community is a section under it
and needs no new surface. A topic is still where a *post* belongs, being
item-shaped and about the subject; a comment belongs to the thing it reacts to.
So the two halves of the split below get two different homes on screen, which is
what keeps them visibly separate features rather than one with a mode switch.

**The data model, in favour of the split already sketched.** A HF community
thread is not part of the paper: it is not indexed with it, not retagged from
it, and contributes nothing to how the paper ranks or what it is filed under.
That is precisely the argument made below for a comment table over `Kind.POST`
— comments are about the story, so they must not reach the centroid or the
topic argmax that reads it — running in production somewhere else.

**And the table already exists.** `notes` has been in `001_initial.sql` since
the first commit — `(story_id, body, created_at)` — under a schema comment
reading *"Your own takes. One user today; the same table becomes posts when
there are many."* No Python references it. It is the row this wants, one author
column short.

**What it breaks is the address, and that was not visible before.** A HF thread
hangs off a paper, and a paper is permanent: the page *is* an arXiv id. A
Tributary story is not permanent. `story_id` is an autoincrement row from
`create_story`, and `cluster.reset()` — `trib cluster --reset`, which this file
recommends running to rebuild stale roles — is `DELETE FROM stories`, which
`notes.story_id ON DELETE CASCADE` turns into deleting every comment ever
written. `prune` takes the rest at 60 days, and clustering is free to attach new
items to the story under a live thread and change the headline above it. Two
consequences:

- **A comment cannot be addressed by `story_id` alone**, which is what both this
  entry and the `notes` table currently assume. It wants the story's strongest
  tier-1 identifier where there is one — arXiv id, DOI, canonical URL — which is
  exactly what HF addresses by, and a stable key minted once per story where
  there is not.
- **`cluster --reset` stops being a safe operation**, or comments have to
  survive it. Those are the only two options, and the first has a real price:
  re-clustering is how every calibration change gets applied to the back
  catalogue.

**What does not carry over is the `Paper submitter` badge.** The opening comment
in the screenshot is the submitter pasting the abstract, so the thread starts
with an authority in it. Tributary has no submitters — stories arrive from a
cron — so its thread opens empty, and the abstract is already printed above it
as `s.summary`. The nearest analogue would badge a comment written by the
source's own author, which is rarer than HF's case and not the thing to build
first.

**And it is a login.** Commenting on HF needs an HF account — the same collision
giscus has with *"Profiles are a namespace, not a login. No password."* The
reference does not dodge that question, it just answers it the other way.

Open questions, none decided:

- Is a comment an item (so it joins the wake and gets a role), or its own table?
  Item-shaped reuses everything; comment-shaped avoids polluting the corpus that
  clustering and topic assignment run over. **The split that looks right,
  2026-09-22:** a *comment* gets its own table, because comments are short,
  reactive and about the thread rather than the subject, so they would drag
  story centroids and the topic argmax that reads them; a *post* is genuinely
  item-shaped and belongs in `Kind.POST`. One feature, two data models, divided
  by whether the text is about the subject or about the story. The Hugging Face
  reference above is that split already built, so treat this one as decided
  unless something argues back.
- **What addresses a comment**, now that `story_id` is known not to survive a
  re-cluster. See the Hugging Face note above: a tier-1 identifier where the
  story has one, a minted key where it does not. Nothing is decided, and it has
  to be, because it is the one part that cannot be changed after people have
  written things.
- Does a user post get triaged and embedded like fetched material? If it does,
  it can be clustered and labelled automatically. If it does not, the author
  places it by hand — which is closer to how Reddit works, and to the
  propose-then-accept model already chosen for topics.
- Who can post, at what point does that need real accounts, and what happens the
  first time someone abusive arrives.
- **"GitHub Pages or pay" is a false dichotomy**, and it was framing this whole
  entry wrongly. Cloudflare Workers' free tier is 100k requests a day and D1's
  is 5GB with 5M row reads a day — enormous headroom for a personal feed, and
  enough for real login, real comments and shared topics at no cost until there
  is real traffic. Two cautions: since 2026-09-01 D1 *hard-fails* queries past
  the daily limit rather than throttling, and "rows read" counts rows the engine
  examined, not rows returned, so an unindexed query burns the budget fast. A
  server also closes the seam `CLAUDE.md` records — `interactions` has no column
  for a person, so every profile on `trib serve` shares one bucket.
- **giscus is the zero-build option and it costs the profile model.** Comments
  live in GitHub Discussions, the site stays static, GitHub handles identity and
  storage. The price is a GitHub login to comment, which collides head-on with
  *"Profiles are a namespace, not a login. No password."* The audience is
  technical, so it is less absurd than it sounds — but it is a decision about
  identity, not about hosting.

## Personal lenses — how to exercise all of it before the server exists

**The destination is the entry above: real accounts, a server, and topics that
are shared rather than private.** Stated 2026-09-22, and it is not optional or
a later maybe — a topic only one person can see is not the feature. What this
section is for is the order: *"jag vill kunna testa att skapa topics, kommentera
och alla funktionaliteter innan"*. Everything below exists so that creating a
topic, commenting, following and ranking a proposal can all be built and used
before anything is paid for, hosted or moderated.

**So the test is whether a piece survives the account arriving.** A lens is
`{name, vector|pattern, created}` whether it sits in `localStorage` or in a
table; a comment is addressed by `story_id` either way. Anything that would need
rewriting when login lands is the wrong shape now, and that — not the storage —
is what to review each piece against.

**Asked 2026-09-22**, alongside the posting entry above: readers should be able
to create their own topics, which arrive as proposals and get ranked before
adoption, *"och skapa sitt egna filter vilket jag gillar"* — with the doubt that
making them work for their author from the start would need per-reader
filtering, which sounded cumbersome.

**It is not cumbersome, and it is the cheaper half of the feature.** Why a user
topic has to be a lens rather than a home, why a lens runs in the page, and why
proposals should be ranked by vector rather than by followers are all in
`CLAUDE.md` under *"A reader's own topic is a lens, not a home"* — read that
first, it is the design. What is left here is the work.

Three tiers, and the first one — the private lens, the only one that costs
nothing — is built. Name one on the subjects page and it filters the feed on its
own words at once; teach it with **More like this** on a card and it starts
matching stories that never use the word. How it works is in `CLAUDE.md`. The
two above it, both on hold with the posting entry until the owner decides:

1. **A shared topic.** Visible to other readers, so it needs the server the
   posting entry describes. This is where proposal ranking lives, gated on
   cosine-dedupe, yield and coherence.
2. **A spine topic.** `config.toml`, an argmax home, re-labels the corpus,
   human-accepted. Unchanged, and rare.

The private one was not a detour: a shared topic is "sync the private one to a
server", which is additive. And the order was forced — topics cannot be ranked
by followers before there are followers, but a personal filter is useful with
one reader.

**What the shared one now needs is only storage.** A lens is already shaped like
a row — `{id, name, terms, vector, seeds, parent, created}` — and a comment will be
addressed by `story_id`. Moving them to a server should not touch `visible()`,
the panel, or the chip row.

**The ceiling on the client-side version is reach, not comments.** A lens sees
only the bundle: 120 stories over 30 days. Raising that is affordable on the
vectors alone — measured at 60KB per 120 stories, so 500 would be 250KB — but
the JSON around them grows with it. That, not commenting, is the honest reason
a backend eventually wins.

**A lens that matches nothing is a gap report.** "Your lenses that caught
nothing" is a reader-generated list of what the sources do not cover — demand-led
source discovery instead of guessing, and the one way the "I do not want to miss
events" worry is actually answered by this feature rather than by ingestion.

## Product launches — a different subject, and a different shape

**Deferred, 2026-09-22:** it takes the project beyond AI-only subjects, which is
a big change the owner has not decided to make. **Search is the exception** —
*"a search would be interesting to look into"* — and it is the hard part below
(fetching in answer to a query), so it can be investigated for AI subjects
without taking on consumer hardware at all.

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

## Redesign the frontend — first pass built, now the owner's review

**Built overnight on 2026-09-22, while the owner slept**, on the request *"do
the redesign now during the night"*: a bottom tab bar, a one-line header that
hides while you read, search behind an icon, a cover on every card (art, or a
typographic cover for the kinds that never have art), the wake as one line,
and a banner on a subject's panel. What each decision is and why is in
`CLAUDE.md` under "The redesign" — every one of them was made without asking,
and each is one piece that can be reverted on its own.

**So the next step is the interview this was meant to start with**, against the
real thing now rather than notes. Ask about each decision in that list, then:

- **Whether topics stay as a filter row** at all, now that following exists
  and a subject opens as a panel. The row survived the redesign unchanged.
- **Tabs across one subject** — its stories, what sits under it, who keeps
  appearing in it. The one idea from the survey not tried: it would change what
  a subject *is* on screen, which is not a call to make overnight.

One smaller thing the survey turned up and this does **not** do: X asks you to
confirm before unfollowing on mobile. Tributary does not, on the grounds that a
follow here costs nothing to restore and the chooser's list keeps the row
around to undo with. Worth revisiting only if someone actually loses a follow
by mis-tapping.

## Ready to start

- **`trib sources --suggest`.** Given a domain, find its feed: `<link
  rel="alternate">` first, then the well-known paths, then `sitemap-news.xml`.
  Propose-then-accept, like topics. It is a stage, never a `Source`, because
  adapters do not touch the database. Google's own Follow button works this way
  — see `CLAUDE.md` under Sources.
- **TLDR AI** needs a two-stage adapter — fetch the issue, then emit one item
  per story in it. Why it cannot be plain RSS is in `CLAUDE.md`.
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

**Interview the owner before building any of these.** Said 2026-09-22: they are
not sure about several and want to be asked about them, one at a time, first.

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

- **A shelf follow and a leaf follow say less in the UI than they do in the
  feed.** `isFollowed` already treats a follow on a shelf as covering every leaf
  under it, but the subject panel draws each leaf's button from its own key, so
  a leaf covered by its shelf still reads `Follow`. Either the leaf buttons
  should show that the shelf already covers them, or a shelf follow should stop
  covering its leaves. Left alone deliberately: guessing wrong here changes what
  the feed holds, and the panel at least makes the two levels visible for the
  first time, which is what was asked for.

- **Stories clustered before the `role_for` fix carry stale roles.** Roles are
  stored, not recomputed, so a paper's own coverage can still be labelled as a
  second seed in old stories. `trib cluster --reset` once, on the database that
  matters, rebuilds them.

- **Art only reaches what was fetched after 2026-09-22.** Everything older in
  the deployed database is already marked in `described`, so the stage never
  goes back for its `og:image`. `trib describe --reset` once backfills it for
  everything inside the retention window — but that database lives in the
  Actions cache, so it is a one-off workflow step, not something to run
  locally. Expect a few hundred page fetches over the runs that follow, capped
  at `DEFAULT_LIMIT` each.

- **GDELT as a broad-coverage source.** Open, keyless, 15-minute updates, and
  `ArtList` is documented to carry a real `url` plus a `socialimage` — but
  query-driven rather than scheduled, and all world news, which makes the
  per-kind popularity gate mandatory before it can land. **Probed from the WSL
  machine 2026-09-22, and refused:** HTTP 429, *"Please limit requests to one
  every 5 seconds"*, on three requests spaced well apart — the first one
  included, under curl's User-Agent and tributary's. So its shape is still
  unverified, and the rate limit is the first thing an adapter has to survive.
- **`LENS_FLOOR = 0.72` is a guess and is the one number in the page that is.**
  It decides when a lens catches a story its words would miss. bge puts
  unrelated text near 0.5 and a story's own members merge at 0.92, so it sits in
  the gap between them and nothing more. Measuring it needs a corpus with real
  lenses on it: take a handful of subjects, seed each with two or three stories
  by hand, and look at where the cosines to the rest actually fall — the same
  exercise `topics floor` had. Until then the lexical half is what carries a
  lens, which is why the order in `lensMatcher` is words first.

## Designed, deliberately not built

- **"Verifierad (mer trovärdig)".** Corroboration exists as a *ranking* input —
  `SOURCE_BONUS` lifts a story several sources covered, and the card shows a
  "4 sources" chip — but the app never makes the claim. Saying "three
  independent sources agree" out loud, and knowing when they are not independent
  (a wire rewrite is not confirmation), is a different feature from nudging a
  score.
- **No time axis.** Items cluster inside a 14-day window, but nothing orders a
  story as announcement → what followed. The shape over time is the interesting
  part and is currently invisible.
- **Nothing discovers reactions.** `sources/github.py` polls a fixed list of
  repos for *releases* and cannot find a new project built on a story. Hugging
  Face's `arxiv:` tags partly cover artefacts, and Reddit now covers some of the
  argument; nothing finds the new project.

## Blocked on something external

- **Phase 5** — notes/takes layer, interaction-learned ranking, "catch me up"
  digest.
- **Phase 6+** — multi-user.

---

## Sebastian's open asks

Verbatim, because they are the sharpest statement of what is left. Delete each
one when it is built.

> I only want the most popular news, not everything. Otherwise it is not really
> news.

Constrained by a second instruction given at the same time: **do not cut
arXiv** — a new paper is real news whether or not anyone has reacted to it yet.
So this cannot be one global popularity gate, since that is exactly what would
drop arXiv. Per-kind thresholds are the likely shape.
