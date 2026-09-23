# Tributary — what is next

Only upcoming work lives here. **When something is built, delete its entry** —
history is in git, and the reasoning behind how things work is in `CLAUDE.md`.

**Two big directions**, named 2026-09-23 once the redesign had landed: *"The big
things I see now is multiple users, more data from topics outside AI (big
change)."* Each has a section below, and neither is started until the owner
says so. Everything that could be built before them was, on 2026-09-23.

## Multiple users — accounts, a server, and what people write

**This is the next big step: real accounts, a server, and topics that are shared
rather than personal.** Confirmed 2026-09-22, and it outranks everything else in
this file — but it is **on hold until the owner decides to make the change**,
said the same day. The notes are here so the decision can be made with them in
hand.

Personal lenses are not an alternative to it — a topic only its author can see
is not the feature — they are how every part of it gets built and used before
anything is paid for, hosted or moderated: *"jag vill kunna testa att skapa
topics, kommentera och alla funktionaliteter innan"*. So the test for each piece
is whether it survives the account arriving. Anything that would need rewriting
when login lands is the wrong shape now.

### Posting and commenting

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
  behind it. It ends the static-only site, though not the zero cost — see
  hosting below. `trib serve` is the obvious starting point, but a server
  someone else can post to is a different thing from one you run locally.

**What it does not need is an API key.** Posting is not an LLM feature, and the
no-API-key rule holds — worth stating, because "community features" and "AI
features" tend to get budgeted together and these should not be.

**Hugging Face's paper page is the worked example.** Offered 2026-09-22, as a
screenshot of `huggingface.co/papers/…`: the abstract, then **Community**, then
comments — an author, a `Paper submitter` badge, a relative timestamp, prose, an
overflow menu. *"An example of how the comments could work is actually found on
huggingface. Here you have a paper and then community with comments."* It
settles where a thread hangs and what it is stored as, and it breaks the
address.

**A comment hangs on the story; a post belongs to the topic.** The reference
sits one level below "on a topic" — on a *paper*, which here is a story — and
that is the cheaper end: `fillStory` already ends with the wake, so Community is
a section under it and needs no new surface. A post is item-shaped and about the
subject, so it lives on the topic; a comment belongs to the thing it reacts to.
Two homes on screen keep them visibly two features rather than one with a mode
switch.

**Two data models, divided by what the text is about — treat this as decided
unless something argues back.** A comment gets its own table: comments are
short, reactive and about the thread rather than the subject, so as items they
would drag story centroids and the topic argmax that reads them. A HF community
thread is exactly that — not indexed with the paper, not retagged from it, and
contributing nothing to how it ranks or where it is filed. A post is genuinely
item-shaped and belongs in `Kind.POST`.

**And the table already exists.** `notes` has been in `001_initial.sql` since
the first commit — `(story_id, body, created_at)` — under a schema comment
reading *"Your own takes. One user today; the same table becomes posts when
there are many."* No Python references it. It is the row a comment wants, one
author column short — and a private note on a story, the old "notes and takes"
idea, is the same row with its author as the only reader.

**What it breaks is the address.** A HF thread hangs off a paper, and a paper is
permanent: the page *is* an arXiv id. A Tributary story is not. `story_id` is an
autoincrement row from `create_story`, and `cluster.reset()` — `trib cluster
--reset`, which is how a calibration change reaches the back catalogue — is
`DELETE FROM stories`, which `notes.story_id ON DELETE CASCADE` turns into
deleting every comment ever written. `prune` takes the rest at 60 days, and
clustering is free to attach new items to the story under a live thread and
change the headline above it. So:

- **A comment cannot be addressed by `story_id` alone.** It wants the story's
  strongest tier-1 identifier where there is one — arXiv id, DOI, canonical URL,
  which is what HF addresses by — and a stable key minted once per story where
  there is not. **Not decided, and it has to be**: it is the one part that
  cannot be changed after people have written things.
- **Either `cluster --reset` stops being a safe operation, or comments survive
  it.** Those are the only two options, and the first has a real price, since
  re-clustering is how every calibration change is applied.

**What does not carry over is the `Paper submitter` badge.** HF's thread opens
with the submitter pasting the abstract, so it starts with an authority in it.
Tributary has no submitters — stories arrive from a cron — so its thread opens
empty, under an abstract already printed as `s.summary`. The nearest analogue
would badge a comment by the source's own author, which is rarer and not the
thing to build first.

Still open:

- Does a user post get triaged and embedded like fetched material? If it does,
  it can be clustered and labelled automatically. If it does not, the author
  places it by hand — closer to how Reddit works, and to the propose-then-accept
  model already chosen for topics.
- Who can post, at what point that needs real accounts, and what happens the
  first time someone abusive arrives.

### Shared topics

The private lens is built; `CLAUDE.md` has it under *"A reader's own topic is a
lens, not a home"*. A **shared topic** is the same lens visible to other
readers, and it is where proposals get ranked — against every existing leaf's
description, by yield and by coherence, not by followers (`CLAUDE.md` says why).

**What it needs is only storage.** A lens is already shaped like a row —
`{id, name, terms, vector, seeds, parent, created}` — so moving lenses to a
server should not touch `visible()`, the panel or the chip row.

**The ceiling on the private version is reach, not comments.** A lens sees only
the bundle — on Pages, 120 stories over 30 days (`trib export site --days 30
--limit 120`). Raising that is affordable on the vectors alone, measured at
60KB per 120 stories, so 500 would be 250KB — but the JSON around them grows
with it. That, not commenting, is the honest reason a backend eventually wins.

**A subject nobody's news fills is a gap report.** Your own subjects already
read `quiet` when they match nothing, which says little to one reader. Across
many, the subjects that stay empty are a reader-written list of what the
sources do not cover — demand-led source discovery instead of guessing, and the
one way the "I do not want to miss events" worry is answered by this feature
rather than by ingestion. Moved here 2026-09-23: not useful until topics are
shared.

### Popularity from readers, for Trending only

**Asked 2026-09-23:** *"Lets introduce something to measure how popular a news
is. An easy thing is to like a news but also a point for opening a news, liking
should be better though."* It cannot be measured without a server: likes and
opens live in each device's `localStorage`, so the only count a static page can
make is one reader's own, which is taste, not popularity — and letting your own
behaviour reorder your feed is what `CLAUDE.md` rules out ("The ranking does not
learn from what you do"). Summed over many readers it is a different thing: the
readers' verdict on a story, beside the points and source counts Trending
already uses.

**It is also the answer to the first open ask**, from 2026-09-17: *"I only want
the most popular news, not everything. Otherwise it is not really news."* Decided
2026-09-23 that popularity is part of the multiple-users build rather than a
per-kind bar over source metrics before it. The constraint from that ask still
holds: **do not cut arXiv** — a new paper is news whether or not anyone has
reacted to it yet.

- **Trending only.** *"I do not want to miss any news"* — so the Feed stays
  everything you follow, newest first, and nothing a count says ever hides a
  story there.
- **Weights:** a like (the star) counts most, being a deliberate choice; an open
  counts little, since a headline that tricks you still earns one; **×** is at
  most a small minus, because it mixes "not for me" with "not important". Never
  time spent or scroll-past.
- **Anonymous counts per story are enough** — no login needed, so it can come
  before accounts, on the free tier under hosting below. It shares the comment's
  address problem: a count keyed on `story_id` is lost on a re-cluster.

### Hosting and identity

- **"GitHub Pages or pay" is a false choice.** Cloudflare Workers' free tier is
  100k requests a day and D1's is 5GB with 5M row reads a day — enormous
  headroom for a personal feed, and enough for real login, real comments and
  shared topics at no cost until there is real traffic. Two cautions: since
  2026-09-01 D1 *hard-fails* queries past the daily limit rather than
  throttling, and "rows read" counts rows the engine examined, not rows
  returned, so an unindexed query burns the budget fast. A server also closes
  the seam `CLAUDE.md` records — `interactions` has no column for a person, so
  every profile on `trib serve` shares one bucket.
- **All of this is a login**, which collides with *"Profiles are a namespace,
  not a login. No password."* Commenting on HF needs an HF account; the
  reference does not dodge the question, it answers it the other way.
- **giscus is the zero-build option, and it answers that the same way.**
  Comments live in GitHub Discussions, the site stays static, and GitHub handles
  identity and storage. The price is a GitHub login to comment. The audience is
  technical, so it is less absurd than it sounds — but it is a decision about
  identity, not about hosting.

## Subjects outside AI — more data, and a feed that is not only AI

**Deferred 2026-09-22** as a big change the owner had not decided to make, then
named as one of the two big directions on 2026-09-23. It started with product
launches, and everything in it meets the same two walls: a pipeline that only
fetches on a schedule, and a corpus with no popularity bar — which comes with
multiple users, under popularity from readers.

**Search is the exception** — *"a search would be interesting to look into"* —
and it is the hard part, so it can be investigated for AI subjects without
taking on consumer hardware at all.

### Product launches

**Asked 2026-09-19**, alongside a screenshot of a fitness-tracker review page:

> For later, this product would be really interesting for me. I want to be able
> to find things like this earlier, perhaps not always get it in feed but if I
> search for a product. I want to be abe to see new releases close to their
> launch

That is three wants, and only the first resembles anything that exists:

1. **New consumer hardware, near its launch.** Sources and config.
2. **Not necessarily in the feed** — a place you go, the way Trending is.
3. **Findable by searching for a product heard about elsewhere.** The hard one:
   see search below.

**The triage profile says this feed is not about gadgets.** `config.toml` lists
*"consumer gadget reviews, phones, smartwatches and TVs"* under `exclude`. Since
triage stopped gating (2026-09-19) that line drops nothing — it labels such
stories rejected, which `trib topics --stats` counts as below triage — but it is
the profile's statement of what the feed is for, and it has to change with the
subject.

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

### Search by query

**The page's search cannot do what is being asked.** It searches the loaded
bundle — the most recent stories and nothing else — so a product heard about
elsewhere finds nothing: the corpus is what the cron fetched, not what you asked
for. Doing it properly means fetching *in response to a query*, which is a
different shape from a scheduled pipeline whose adapters never touch the
database. It is the first thing this repo would want that is not a stage, and it
is the shape GDELT has too.

### GDELT

**The broad-coverage source.** Open, keyless, 15-minute updates, and `ArtList`
is documented to carry a real `url` plus a `socialimage` — but query-driven
rather than scheduled, and all world news. **Probed from the WSL machine
2026-09-22, and refused:** HTTP 429, *"Please limit requests to one every 5
seconds"*, on three requests spaced well apart — the first one included, under
curl's User-Agent and tributary's. So its shape is still unverified, and the
rate limit is the first thing an adapter has to survive. More in `CLAUDE.md`
under Sources.

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
