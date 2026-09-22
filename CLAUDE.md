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

**Testing the page:** `tests/test_lens.py` boots the whole script under **node**
against a real exported bundle, with a thirty-line DOM stub and a fake `fetch`,
and then calls into it — so `render()`, `visible()` and the lens maths are
covered without a browser, a build step or an npm dependency. It skips where
node is absent. Prefer extending it over adding another string assertion on the
exported HTML: those catch a renamed class and nothing else.

It also slices the block between `/* LENS_MATHS_START */` and
`/* LENS_MATHS_END */` out of the page and runs it alone, which is why
everything in there must stay pure — no DOM, no `localStorage`, no globals.
That is what lets the page's cosine be checked against the numpy that packed
the vectors it reads.

**For layout, screenshot it.** On the dev machine headless Chromium still needs
`sudo .venv/bin/playwright install-deps chromium` first. In a Claude Code remote
container it is already there and the note above used to say otherwise: pass
`executable_path="/opt/pw-browsers/chromium"` and `args=["--no-sandbox"]`,
because the pinned Playwright asks for a build number the image does not carry
and otherwise tells you to run `playwright install`, which is wrong. Serve the
exported site over HTTP rather than `file://` — the page fetches `data.json`,
and CORS blocks that on a file URL. Screenshot at 390×844, and **not**
`full_page`: `.sheet` is `position: fixed`, so a full-page capture renders the
chrome underneath it and invents a bug that is not there.

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

### Four surfaces, and what orders each

The page is **Feed, Trending, Topics, Saved**. What separates them is only the
order and the scope; all four read the same bundle.

| Surface | Order | Scope |
|---|---|---|
| Feed | newest first, by the date on the card | what you follow, and nothing else |
| Trending *(beta)* | the ranking below | everything, or what you follow |
| Topics | most unread first | every subject in the bundle |
| Saved | newest first | what you starred |

**Triage scores; it does not gate.** Changed 2026-09-19, on the owner's call:
*"I have solved filtering with following instead. It is a much more basic and
better solution since everyone has their own preferences."* So `enrich.pending`
and `cluster.unclustered` no longer filter on `triage_state`, and everything
fetched becomes a story. Triage still runs, and its score is still `relevance`
in the ranking — so what the profile dislikes sinks in Trending rather than
never existing. Trending is marked **beta** in the UI while that is judged.

**The consequence to watch is the topic floor.** Topics have no relevance
threshold by design — a story goes to its single best leaf — and `floor = 0.55`
was measured at *1 story in 2239* **on already-triaged material**. On
everything, that floor is the only thing between a crypto post and whichever AI
leaf it most resembles, and following is what gets polluted if it fails.
`trib topics --stats` has a **below triage** column counting stories made
entirely of items triage would have dropped; a topic filling up with those is
the signal to re-measure the floor on the new population.

**The profile chooser lists what that profile follows.** Asked for 2026-09-21:
*"In the profiles, I would also like to see the topics i follow"* — and it is
where the apps this borrows from keep it. Reddit's "Your communities" sits in
the drawer behind the avatar; X keeps "Topics" in the profile menu. A follow
belongs to whoever is reading, and the chooser is the only surface that is about
them: every other list of subjects on the page is built from the stories in the
bundle, so it can only show follows the news happens to be covering. Rows carry
the same count and the same follow button as the subject panel, and tapping one
opens it. **The rows are a snapshot taken when the chooser opened**, not the
live set — unfollowing leaves the row in place reading `Follow`, because a row
that vanishes under the thumb that tapped it leaves nothing to undo with.

**Profiles are a namespace, not a login.** Asked for 2026-09-19: *"a Login that
is just a selection of choosing a profile or creating a new profile which only
is a name. No password."* So a profile prefixes every `localStorage` key this
device already wrote — `p:<name>:seen`, `p:<name>:follows` and so on — and the
chooser stands in for a login screen because writing one person's marks into
another's bucket is worse than making them tap a name. It protects nothing and
syncs nothing: the same name on a laptop is a different profile, since a static
host has nowhere to put a server. Turning it on adopts whatever the device
already stored into the first profile created, so nobody's follows vanish on
upgrade. The one seam is `trib serve`: `interactions` has no column for a
person, so on a local server every profile's marks land in one bucket. On Pages
there is no server and the profiles are cleanly separate.

**Following is the filter, not the source list.** The owner's rule: *"I want to
be able to choose what news/topics to follow, that is exactly what I was
missing."* So model cards and release notes stay in the pipeline and are
filtered by what you follow, rather than dropped from config. Follows are
`topic:<slug>` and `entity:<name>` in `localStorage` beside seen and saved.

**An empty follow set means an empty feed.** Reversed 2026-09-19, on the
owner's call: *"feed should be empty if you do not follow anything. That is the
whole point."* It had been the opposite — following nothing showed everything,
on the reasoning that an empty feed on a new device looked like a fault. But a
feed that is full before you have chosen anything is the habit the project is
replacing, and it hides the one action that makes the app yours. So the Feed
filters on `isFollowed` unconditionally, and following nothing gets an empty
state pointing at Topics, which is where you choose. Saved and search are
deliberately outside this — both are ways back to something you already have —
and Trending is still everything, since it is a place you go to look around.

**A follow is a preference, not a view of the corpus.** Topics die by dormancy
— the filter rows are built from the stories loaded, so a quiet one vanishes —
and that is right for a filter and wrong for a follow. A followed subject with
nothing in the bundle had no row anywhere, so it could not be seen or turned
off, while still counting in `follows` and still deciding what the feed held:
an invisible follow, and (once follows gated the feed) an empty feed with no
reachable cause. The digest now ends with **Followed, but quiet** — every
follow the page has not already given you a control for. Naming those needs the
spine, since no story carries the name: `export.build_bundle` passes the whole
spine as `bundle.spine`, for the reason it already passed `facets` by name.
An old bundle without the key falls back to the slug.

**Following is reachable from the place you are in.** `topicHead` and
`entityHead` carry a follow button. It used to live only in the digest, so the
subject you were actually reading was the one subject you could not act on.

**Follows gate the feed; they do not gate a place you walked into.** A topic or
an entity reached deliberately — from a story's chip — shows what is in it
whether or not you follow it. Requiring both emptied every subject you had not
already chosen, which is precisely the subject you went to look at, and the
banner saying "0 stories" sat above a digest row that had just counted them.
So `visible()` applies `isFollowed` only when nothing is scoped.

**A place you walked into hides the filter row.** Reported 2026-09-21: *"it now
shows the filters I follow even though i clicked on a topic"* — and they were
never filters on that place. Standing in `Industry & policy`, the row offered
`Language models` and `AI agents`: neither in the feed below, neither lit, and
the subject actually on screen missing from the row because it is not followed.
Tapping one would not narrow the place, it would leave it for another. So
`renderFilters` draws nothing while `narrowed()`, and the row carries no pressed
state or `Clear` any more — it cannot show a lit chip, because it is gone the
moment you are inside a subject. It is a way *in* to what you follow, and the
banner is the place's own chrome.

**Every part of the banner's name is a way somewhere.** Asked for 2026-09-21:
*"I also want to be able to click on e.g Ai agent-> coding agents to browse
other topics deeper and to go back to ai agents"*. `AI agents › Coding agents`
was plain text, so a leaf was a dead end: the only moves were back to the feed
or into a story. Both segments are now `data-subject` buttons, which is the
rule the rest of the page already follows rather than a fourth behaviour for
names. Going up and browsing sideways are the same gesture because they land on
the same surface: the shelf's panel lists every leaf under it with a count and
a follow each, and its **See all in the feed** is what puts you in the shelf
itself. The current segment opens its own subject too — from a shelf, that is
how you reach the leaves without leaving the feed first.

**Which is why `topicHead` carries `Back to feed`.** `entityHead` always had
one; a topic's only exit was the `Clear` chip in that row, which renders only
when you follow something — so following nothing and walking into a topic left
no way back to the feed at all, on the one path (an empty feed, then Topics,
then a subject) a new reader is most likely to take.

**Tapping a subject opens it.** Everywhere — the digest, a story's chips, a name
on a card — `data-subject` opens a panel for that topic or entity. Asked for
2026-09-21: *"I can not see topics when I click them now. It just navigates me
to an empty feed. I would also like to get a popup when I click a topic and a
chance to follow (similar to an instagram profile)."* Both halves were one gap.
Nothing in the digest opened anything: the shelf name (`data-to-feed`) went to
the feed and cleared the scope on the way, which for anyone following nothing is
an empty feed, and a leaf chip toggled a follow without moving at all. Before
that, the name had set the topic on the way out, which left the feed filtered
days later with no memory of setting it — so the fix for *that* was right about
the filter and wrong about the name. A name should open its subject; neither
navigating nowhere nor leaving a filter behind is that.

**The panel is shaped like a profile**, which is what was asked for: the name and
the follow control together at the top, then what sits under it, then its
headlines, then "See all in the feed" for the walk-in that `data-goto` used to
be. Following is a button rather than a chip's tint — that is what makes it
*clear what is followed*, and it ends the collision where one chip shape
navigated in the Trending sheet and followed in the digest. A shelf's panel
lists its leaves with a follow each, so the two levels are visibly separate
choices; a leaf you follow is listed even when the bundle is quiet about it,
for the same reason **Followed, but quiet** exists.

**"Under this" has to account for every story the panel counts.** Reported
2026-09-21: a shelf saying 24 stories over leaves adding to 21. Not an
off-by-one — it is **parking**. A story whose top two leaves share a shelf and
sit within `park_margin` stays on the shelf, so `hasTopic` counts it in the
shelf's total and no leaf row can. At ~13% of the corpus the gap is the rule,
not an edge case. The panel now ends the list with **Not under a subtopic** and
its count, plus a line saying why and that following the shelf still collects
them. It is a row with nothing to open or follow, because parked stories are
not a subtopic — only a shelf with leaves can hold them, so a leaf's panel
never shows it. The digest has the same arithmetic and does not show this: its
leaf chips are a way in rather than a breakdown, and a tenth chip on every
shelf row would cost more than it explains.

**The panel is a page wearing a sheet, and that is deliberate.** Checked against
how other apps do this, 2026-09-21, because the brief was "a popup … similar to
an instagram profile" and the two halves of that pull in different directions.
What the survey said:

- **Every app opens a subject as a page, not an overlay.** An Instagram profile,
  a Reddit community, a YouTube channel and an X trend are all full pages in a
  navigation stack. None of them is a transient sheet.
- **Apple's rule for a sheet** is that it "helps people perform a *scoped task*
  that's closely related to their current context". Browsing a subject that has
  levels under it is not a scoped task.
- **Nielsen Norman on bottom sheets**: an expanded one looks like an ordinary
  page, so people reach for the back gesture — and are disoriented when the
  sheet has not wired it up. The fix they give is to support Back.
- **Nested modals are the named anti-pattern**: layers stacked on layers, no
  single exit, and no way to tell where you are.

Tributary's `.sheet` is `position: fixed; inset: 0` — full screen, with a back
arrow and one history entry per level. So it already *is* a pushed page in
everything but the entrance animation, and the back gesture that the sheet
literature says is usually missing is the mechanism this was built on. The one
finding that did apply: stacked layers were indistinguishable, all bar and no
label. Each panel now names itself in its bar (`#subject-where`, a leaf naming
its shelf), which is what a pushed page does and what makes depth legible.
Nothing else from the survey argued for changing the shape.

**Back climbs one level.** `panels` is a stack — a subject, a leaf inside it, a
story opened from either — and each entry pushes one history entry, so the back
arrow, Escape and the phone's own gesture are one path. *"När man klickar
tillbaka ska man komma upp en nivå liksom."* The story sheet already did this
for one level, on purpose: without it, back left the site. The panel on top is
drawn on show rather than on push, so one you return to reflects what changed
while you were deeper — a follow toggled, a story read.

**The feed orders by when the news broke, not by the story's clock.** A story's
clock restarts when its wake grows (see `trib renewal`), and a chronological
feed where a three-day-old paper jumps the queue because someone commented is
exactly what looked unsorted. The wake shows as "active 2h" on the card
instead — over a 6-hour threshold, since a paper and its own announcement land
minutes apart and that is one event, not a wake.

**The bundle is selected by date** (`feed.recent`), not by rank. Taking the
top-ranked N and sorting those by date would silently drop a recent story the
ranking did not rate, and the reader would never learn it existed. Every card
still carries `score`, which is all Trending needs.

**There is no kind row.** Facets had their own filter row under the Feed's
subjects and their own `Kind` group in Trending's sheet. Removed 2026-09-21, on
the owner's call: *"I would also like to remove the subtopics/kind (code,
agents, multimodal etc.) which lie under general topics. They do not make sense
right now."* The axes were being offered as siblings when they are not: under
one home the topic shelves *partition* the corpus, while facets are any number
per story and exist to cut across it, so the kind chips overlapped and their
counts summed past the pool. Offered before any subject was chosen, `Kind` asked
you to slice everything by a property built for narrowing somewhere you had
already walked into. Facets are still matched, still fingerprinted by
`Config.label_fingerprint`, and still in the bundle as `bundle.facets` — nothing
in the UI reads them. Putting a row back means deciding what it is subordinate
to first.

**Each surface filters the way its own size allows.** The Feed's chip row shows
only the subjects you follow — the feed already holds nothing else, so offering
the other forty topics is offering forty empty filters — and only while you are
not inside a place (above). There used to be a second row — the whole spine,
shelf then leaf — for the case where you followed nothing and the feed was
therefore everything; that case no longer exists, so neither does the row. Trending is everything, where the same rows are forty-odd
chips over four lines before a headline, so it collapses to one bar reading its
own state (`Everything · AI agents`) that opens a filter sheet — the
same gesture the story detail and the profile chooser use. **The sheet lists shelves, not leaves.** Showing
all forty-odd subjects at once only moved the wall of chips behind a tap, so a
shelf opens on tap and one is open at a time, with `Everything` inside it
standing for the shelf itself; a shelf with nothing under it picks instead of
expanding. The sheet opens with the shelf holding the current selection already
open, and a collapsed shelf lights up for a leaf chosen inside it. So scope and
opening a shelf keep the sheet open, because neither finishes the choice; a
subject is the answer, so it applies and closes.

**No chip means "no filter", and the word is gone from the UI.** `All`,
`Everything`, `Anything` and `Any kind` were each the first chip of a row, lit
whenever nothing else was — which is only ever a restatement of the row's own
state. The owner's call, 2026-09-19: *"All and Everything is unecessary since it
is true if no filter is active. But a way to 'clear' all selected filters is
better UX."* So the rows hold subjects only; tapping a lit chip turns it off,
and `Clear` appears beside Trending's bar and in the sheet's header only when
something is on. The Feed's row no longer carries one: it is hidden whenever
there is anything to clear, and `Back to feed` in the banner is what clears it.

Three `Everything`s outlived that pass and were removed 2026-09-21 — *"There is
an 'everything' filter. That is unecessary"* — because each was the same
restatement in a different costume:

- **The sheet's `Show` row** was `Everything` / `What I follow`, a pair where
  one chip meant "no scope". It is now the one chip that means something, and
  tapping it while lit turns it off. Off is everything.
- **Trending's bar** opened with `Everything`, so the unfiltered state had a
  name where it needed a way in. With nothing on it now reads `Filter`; with
  something on it lists what is on.
- **The first chip inside an open shelf** now carries the shelf's own name.
  Unlike the other two this is a real selection and had to stay: under one home
  it is not the same as picking every leaf, because about 13% of stories are
  *parked* on a shelf and belong to no leaf, so it is the only way to reach
  them. Only the label was wrong. An open shelf's header drops its count, so
  the header and the chip below it do not read as one thing printed twice.

**A card says where its story lives.** Reported 2026-09-21: *"it is a bit
strange that e.g. the openai tag shows but you cannot see industry and policy
until you click on the news"*. The card carried who a story was about and not
where it sat, so the one axis that decides what the feed holds was the one you
had to open a story to see. `topicChip` now leads the signal row, in the accent
the page uses for a place you can walk into, with names after it in neutral —
an entity is a different cut of the feed, not where this story lives. Under one
home there is exactly one, and a parked story names its shelf, so it is always
one chip and never a row. It is shown even inside that subject: scoped to a
shelf, the chip names the *leaf*, which is the thing the banner cannot say.

**Google Discover's card is an image contract, and this corpus cannot sign
it.** Offered 2026-09-22 as the target for Trending, as a screenshot. Discover
mandates an image at least 1200px wide plus `max-image-preview:large`, which is
why every card in it has one. Tributary's `media_url` comes only from RSS
`media:content`, `media:thumbnail` and image enclosures (`sources/rss.py`) and
from Hugging Face thumbnails, so arXiv, HN and GitHub releases carry none — and
at ~235 papers a week against ~90 non-papers, that is most of the feed. The
cheap half of the fix is `og:image`, **built 2026-09-22** — see "Describing an
item" under Sources for what it does and does not cover. The other half does not
exist: a paper and a release have no image, ever, so either imageless kinds get
a typographic card or the wall stays uneven. Discover's
uniformity comes from a uniform corpus — publisher articles and nothing else —
and "do not cut arXiv" is the rule that makes this corpus the other kind.

**Big cards are wanted, and the old density rule is withdrawn.** The screenshot
holds two stories on a whole phone screen, and that was raised as a cost before
the owner corrected it, 2026-09-22: *"Jag har inga problem med att nyheter tar
upp för stor plats på sidan, det är snarare bra då det är svårare att missa."* A
card that fills the screen is harder to skip, which is the point; the earlier
"dense card list" framing treated size as waste and had it backwards. **What is
waste is chrome** — a 182px header is rows nobody asked for, while a large card
is the thing they came for. So the Discover shape is not a reversal to weigh
against anything, it is the target, and `og:image` is what stands between this
corpus and it.

**One word per kind.** The badge on a card and the chips counting what else is
attached to it were two tables, and they drifted: the same kind was badged
`news` while the chip beside it said `1 article`, and `code` against `1 repo`.
Nothing told a reader those were the same thing. `KIND_WORD` is now the only
vocabulary — paper, model, repo, video, discussion, article, post — used by
both. A *story* is still a different unit from any of them: it is the cluster,
which is why counts say "6 stories" while a card in it is badged `article`.

**The digest counts unseen, not "since a timestamp".** Seen marks are already
per story and per device, and a count you clear by reading beats one that
resets itself at midnight. Counts are over the stories in the bundle, so they
always match what tapping through shows.

### Ranking

Recency-decayed relevance with a 48-hour half-life, plus a capped bonus for
stories several sources covered (`SOURCE_BONUS`, `MAX_CORROBORATION`). It must
resist volume: arXiv publishes ~150 papers a day where a blog publishes one, and
recency-times-relevance alone handed it 47 of the first 50 cards. The feed damps
each *repeat* of a source or kind as it is built (`SOURCE_DECAY`, `KIND_DECAY`),
which restores a mix with no hard quota. This is what **Trending** now is; the
default feed is chronological. The page is a card list and a card may be large:
size is not the cost, chrome is — see "Big cards are wanted" above.

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
those.

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

**Which is why a personal lens needs no server — and it is built, 2026-09-22.**
It is the shape `isFollowed` already has: a `localStorage` predicate over the
shared bundle, so per-reader filtering happens in the page and never in the
pipeline. A lens is `{id, name, terms, vector, seeds, created}` under the
profile's `lenses` key, followed as `lens:<id>` in the same set as
`topic:<slug>` and `entity:<name>`, and **it is a subject like any other**: it
fills the feed through `isFollowed`, sits in the chip row, opens as a panel, and
is a place you can walk into. Nothing in the UI knows it is yours except the
panel, which says so and offers to delete it.

**Words first, then the vector.** `lensMatcher` asks the lexical question before
the semantic one, the order and for the reason the clusterer uses. That is what
makes `LENS_FLOOR = 0.72` safe to ship **unmeasured** — bge puts unrelated text
near 0.5 and a story's own members merge at 0.92, so it is a guess in the gap
between them, and a lens always matches its own name whatever the floor does. A
floor set badly makes a lens narrow, never broken. Measure it against a real
corpus before trusting the vector half on its own.

**Teaching folds earlier seeds in by their number.** `addSeed` blends the stored
vector against the new story weighted by how many seeds it already stands for,
rather than averaging the two — otherwise the fifth story you point at would
weigh as much as the four before it. It deliberately does *not* recompute from
`seeds`: a story leaves the bundle after thirty days, and a lens must not
quietly forget what it was taught. The bundle carries
story centroids as of 2026-09-22, quantised to int8 and base64-encoded
(`export._centroids`): measured at `--limit 120` that is **+60KB raw, +40KB
gzipped**, against four times that for float32. The error it costs, over a
bge-shaped spread of 2000 cosines: mean 0.0026, worst 0.011, nine of the top
ten by similarity keeping their places, one story in two thousand crossing a
0.75 threshold it should not have — the same order as `park_margin`, so this is
fine for ranking and filtering and is *not* precise enough to re-derive a
topic's home from. The lens vector itself is cheapest as the re-normalised mean
of two or three stories the reader picks: no model in the browser, and it makes
"more like this" and a saved filter the same build. A lexical lens is cheaper
still and often better, for the reason facets are regexes. Running the real
model in the browser (transformers.js, `Xenova/bge-small-en-v1.5`, the same 384
dimensions) is the only way to accept a *written* description, and costs a
download not worth paying until the other two prove insufficient.

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
- **An empty 406 from `export.arxiv.org` is its CDN, not the API** — no
  `google` hop in `Via`, and `cache-control: private, no-store`. It hit httpx
  on the WSL machine for a few minutes on 2026-09-22 while curl got 200 from
  the same URL and Actions was unaffected, then cleared by itself. Retry before
  debugging the adapter: a header change looked like the fix and was not.
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
  is therefore a *stage* that proposes sources, never a `Source` — propose then
  accept, like topics.
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
topics floor             = 0.55   # 1 in 2239 -- but measured on TRIAGED material
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
