# Tributary — the spec for the redesign

**This is the design of the next Tributary, and the file to read first.** It is
meant to outlive the code: the app is being redesigned from scratch, and most of
this repo will be replaced. Written 2026-10-04 from a day of decisions with the
owner, consolidated into one pass so nothing here contradicts anything else.

- `CLAUDE.md` describes **version 1** — the pipeline that still runs, and the
  page that was retired on 2026-10-05 — and what building it taught. Where the two disagree, this file wins for the redesign;
  `CLAUDE.md` stays as the record of lessons.
- `NEXT.md` is the roadmap: the steps from here to the redesign, in order.
- **`docs/mockup/index.html` is the approved look** — a clickable mockup of
  these flows, approved by the owner on 2026-10-04 (*"It looks perfect"*), also
  published at https://claude.ai/artifact/1XeimYb1Q7VEdZJ6H6KnsG. Build to it.

## The idea

**Tributary is a platform for building your own news.** You follow topics, and
you decide where each topic's news comes from: the app finds and suggests
sources, you choose which ones to keep, and your topics grow into your own news
tree. Version 1 was one person's AI feed with a fixed source list; its AI topics
become one starter example among others.

In the owner's words:

> Tributary should be a platform to be able to personalise news. So a user
> should be able to create their news tree themself. […] So it is less of an app
> with fixed sources, and more a personal news app like i wanted.

> I will never be able to know what the user wants in advance. This is the
> entire reason why is has felt unscaleable. To have a user find and choose on
> their own is sooo much better.

**Why the idea changed.** Version 1 has one source list in `config.toml`,
fetched for everyone by a scheduled job. Every new subject meant the owner
finding its sources by hand, and every reader got the owner's choices — that is
what felt unscalable, not the storage, which is small. When readers choose
their own sources, the app no longer has to know in advance what everyone
wants.

**What it is for has not changed.** Replace a social-media scrolling habit with
something worth the time — *"något vettigt"* — keeping the form of those apps
and none of their hooks.

## Design principles

1. **You follow topics, and you decide where they get their news.** Every topic
   has sources you chose, and you can always see and change them — quietly, in
   the topic's settings, never in the way of the news.
2. **The app suggests; you decide.** Nothing joins a topic without your say-so.
   Suggested sources, proposed subtopics and similar topics are offered and
   accepted, never added silently.
3. **Never start empty.** The first run ends in a feed with news in it, built
   from what you said you care about, using starter topics with starter sources.
4. **Fetch only what someone uses, and only once.** A source is fetched while at
   least one topic uses it, once however many do. Cost grows with what people
   chose, never with the size of the internet.
5. **Keep headlines and links, not the news.** A title, a short summary, a link,
   a date and a vector, for a limited time. The article stays on the
   publisher's site; old items expire.
6. **Keep the form of social apps, never their hooks.** Large, image-led,
   immersive and fast to scan. No autoplay timers, no feed that refills itself
   as you reach the end, no ranking that learns from your behaviour, no
   notifications you did not ask for. A clear "you're all caught up" is a place
   to stop.
7. **No paid AI by default.** Local embeddings do the understanding: grouping
   articles into stories, placing them in topics, proposing subtopics, judging
   whether a source fits. Anything that needs a paid model is optional and
   priced.
8. **Lightweight first.** *"The first version needs to be lightweight. I do not
   want unnecessary features."* Every feature in the first version below earns
   its place; everything else waits.
9. **What many people choose helps the next person — later.** Once there are
   users, topics and sources that many follow become the best suggestions.
   Until then, nothing pretends to know.

## The core flows

### First run

The first time a device opens the app — a device with nothing stored is a new
reader, so this works without accounts:

1. **What do you care about?** One screen of subjects to tap, or type your own.
2. **Here is what we found.** For each pick, a starter topic and its suggested
   sources, each with a preview. **Include all** is the one-tap path; picking
   some is the other.
3. **News, straight away.** You land in your own feed with stories in it.
4. **A light pointer to the rest** — your tree, the layout switch — shown once.

This is the "hook" the owner asked for, in the good sense: a welcome that gets
you to your own news fast. It is not an engagement hook (principle 6).

### Creating a topic

The one moment sources are the main event — *"When you first "create" a topic
it should be a good UI so it is clear what sources it found and suggest. And an
option to include all or select a few."* Name a subject or paste a site; the app
shows what it found, each source with its **preview** (latest headlines, and how
many items a week it publishes, so a source that posts forty times a day is seen
before it floods the topic). **Include all**, or pick some.

### Reading

Wherever you stand — everything you follow, one topic, one subtopic — you see
its stories, and you choose **how** to see them with a layout switch, the way
Instagram switches a profile between grid and list: *"it does not have to be in
different tabs in the new app. Think like instagram and most sites where you can
choose which layout you want."* The formats people liked in version 1 are the
starting point: tiles and circles for an overview, big cards for reading, and
circles that play a topic's new stories full screen, one at a time, with no
timer. **New** means unread *and* under 48 hours old; older stories stay
reachable but stop counting. The end of what is new says **you're all caught
up**.

### A topic's settings

After creation, sources step back — *"when you already have a topic it should
be more like settings where you can click and change."* Behind a settings entry
on the topic: the sources it uses, each removable with one tap; a search to add
more at any time (by subject, name or pasted site, with the same preview);
**muted words**, to hide anything mentioning, say, "crypto" in this topic; and
the topic's name. Removing a source from a topic affects only that topic.

### Up and related, on every topic page

Decided 2026-10-04: from a topic you can step **up** to the broader topic it
belongs to, and **sideways** to related topics — *"I like both. But it is
important that this does not bloat your feed."* So:

- **Up:** a topic page shows "Part of **AI**". Tapping it opens AI whether or
  not you follow it — its stories, its other subtopics, and a Follow button.
  This is how you find the siblings of something you already like.
- **Related:** a short row of topics close to this one but not above or below
  it (AI video beside Film & VFX), from the embeddings: topics whose
  descriptions sit near each other. A handful at most — three or four.
- **Your feed never grows by itself.** Walking up or sideways is looking, not
  following — the rule version 1 learned (*follows gate the feed; they do not
  gate a place you walked into*). Only a topic you follow puts stories in your
  feed; a parent you visited, or a related topic you peeked at, adds nothing.
  The Related row lives on the topic page only, never in the feed, and nothing
  is ever followed on your behalf.
- **An unfollowed topic opens as a preview** (decided 2026-10-04: *"I would
  think that a user wants to explore the parent before deciding"*). A parent or
  related topic you do not follow has no sources of yours, so its page is
  filled cheapest first: (1) stories the backend already holds — from any source
  someone uses, starter sources included — that fit the topic by embedding,
  shown at once; (2) when that is thin, a **live preview**: the backend finds
  the topic's suggested sources, as topic creation does, and fetches their
  latest items right then, kept only briefly and never fetched on a schedule,
  so "fetch only what someone uses" holds; (3) **Follow** turns the preview
  into a real topic through the usual "Here's what we found" screen. The page
  shows what is already there immediately and fills in the rest as it arrives;
  the feed is untouched until you follow. Previews get better as Tributary
  gets users, since more of the world is already fetched.
- **Who decides the parent.** A topic from a starter tree knows its parent. A
  topic you made yourself gets one proposed by the embeddings — "This looks
  like part of AI. Show it as a subtopic?" — which you accept or decline, like
  every suggestion.

It needs the backend's topic relations, so it belongs with step 2 or just after.

### Exploring your tree

*"I would actually like a view where you can explore your tree it would be
cool."* Your topics, the subtopics under them, the sources feeding each, and the
related topics around them, seen whole — as an **interactive graph**: nodes for
topics, subtopics and sources, colour-coded by kind, with lines for how they
connect (a subtopic to its topic, a source to the topics it feeds, a related
topic to its neighbour). Decided 2026-10-04 from a reference the owner sent —
[Magnowlia's ontology graph](docs/reference/tree-view-magnowlia.png) — *"Tree
view similar to this but prettier."* The reference shows the shape (coloured
boxes, curved links, a canvas you explore); the new one should be calmer and
more beautiful: fewer crossing lines, room to breathe, and tapping a node opens
that topic.

**Built 2026-10-05 as an outline, not a wheel** (`web-next/src/graph.ts`). The
first version put the reader in the middle and was a radial graph; the owner's
verdict: everything hung off their initial when it belongs to AI, and it did
not show how topics relate. A radial layout of fifty named nodes was also three
phone screens wide with labels on top of each other. So: **AI at the top**, its
topics, their subtopics indented under them, your own topics after; **dashed
arcs** join topics whose stories are alike (the mean of their stories' vectors,
each topic linked to its closest one, ranked rather than thresholded); filters
for your topics or all of AI, related links, and sources; and **tapping a node
focuses it** — its links light up, the rest fades, and a panel lists what it is
closest to anywhere in AI, with Open, or Add to your topics.

## The model

| Thing | What it is |
|---|---|
| **Source** | A feed (RSS, Atom, a news sitemap, or a special adapter such as arXiv, Hacker News, GitHub releases). Shared: fetched once for everyone who uses it, with its health and last error. |
| **Item** | One entry from a source: title, short summary, link, date, picture, vector. Expires after a fixed window. |
| **Story** | Items about the same event, grouped — the unit you read, as in version 1. |
| **Topic** | Yours. A name, a short description (embedded, so it can be compared), the sources you chose for it, optional muted words, and optionally a parent topic — subtopics are topics with a parent. |
| **Your tree** | Your topics and how they nest, under your profile. |
| **Profile** | A name you create, nothing else — no password for now (decided 2026-10-04: *"Keep it simple and let the user create a profile for now, no password yet"*). Version 1 already works this way. Real sign-in comes later. |

**How a story gets into a topic.** A story is in your topic when it comes from
one of the topic's sources **and** fits the topic; muted words then take out
what you never want to see. **The fit filter stays, always** — decided
2026-10-04, replacing an earlier "general sources are the reader's call": *"Yes
i want to keep the filter. This is really important."* It is what makes broad
sources usable: add Hacker News to a language-models topic and you get its
stories about language models, not its stories about databases. Fit is decided
by the embeddings — the story's vector against the topic's description, as
version 1 homes stories today. Because of it a source is never labelled "writes
about everything": a broad source is safe to add, so the warning only added
noise and was removed the same day.

**A story can sit in several of your topics, and is read once** (decided
2026-10-04). If it belongs to two of your topics it appears in both; once you
have seen it in either, it is read everywhere — as seen marks already work in
version 1. Version 1's "one home per story" was for one shared tree; a
personal tree does not need it.

**The embedding layer is the tree's engine**, kept from version 1 on the owner's
call: *"the relations can be used to find similar topics and of course to auto
create the subtopics."*

- **Subtopics, proposed.** When a topic fills up, clustering its stories
  proposes subtopics; you name and accept them.
- **Similar topics, from the relations.** Topic vectors sit in one space, so
  "related to this" is a cosine away — something to explore, and a duplicate
  caught before it is made.
- **Suggestions, judged.** A candidate source's recent items are embedded and
  compared with the topic before it is offered.

## The first version

Built on the flows above, and nothing more. From a scan of similar apps
(Feedly, Inoreader, NewsBlur, Ground News, Particle, Artifact, Bluesky), four
features earn a place:

1. **Source previews** — in topic creation and settings.
2. **Muted words** — per topic, in its settings.
3. **OPML import and export** — the standard file every feed reader uses; its
   folders map onto topics, so a reader brings their old sources in one go and
   is never locked in.
4. **"You're all caught up"** — at the end of what is new.

**Later, once there are users:** shareable topics and trees, as links others can
adopt (how "what many follow" starts); opt-in alerts for one topic, off by
default.

**Left out on purpose**, so they are not reconsidered without a reason:

- **AI summaries and rewritten headlines** (Artifact, Particle) need a paid
  model. Grouping articles about one event — Particle's core — Tributary
  already does with local embeddings.
- **Bias ratings and "blindspots"** (Ground News) rely on outside rating
  services; the owner removed the related "Verifierad" idea on 2026-09-23.
- **Rules engines** (Inoreader) — heavy, and built for analysts.
- **Like/dislike training** (NewsBlur) and any ranking that learns from what you
  do — principle 6.
- **Posting and commenting** were designed for version 1 (the notes are in git
  history, see `NEXT.md`); they wait until there are users to write.

A warning from the scan: Artifact, by Instagram's founders and full of AI
features, shut down in 2024 when growth stalled. Lightweight is the safer bet.

## Technology

**Decided:**

- **The backend stays Python** — the pipeline, the embedding model
  (bge-small-en-v1.5, local), clustering and the measured thresholds carry over.
  *"Ok python is fine for the backend."*
- **The frontend is a new app in a real frontend framework**, replacing version
  1's single HTML file. *"The frontend needs to be a frontend language. I do not
  want to lose functionality or design because it should be simple."* Simple
  means a small, clear codebase, not fewer features or a plainer look. **Version
  1's design is thrown away** — the new one is designed fresh, and version 1's
  recorded decisions are a checklist of lessons, not a template. **The framework is React**
  (decided 2026-10-04: *"I like react"*), built with Vite into a static site
  that GitHub Pages can host now and the server can serve later.
- **Backend and frontend talk through JSON**, as in version 1, so either can be
  replaced without the other.

**Hosting — the leading option, not decided.** One small rented Linux server
(Hetzner's smallest was about €4–5 a month; check the current price) running the
API, the scheduled fetching and SQLite, with Caddy for HTTPS; nightly backups to
a free storage tier (Cloudflare R2 or Backblaze B2); sign-in by emailed link
(a free tier such as Resend) or with Google or GitHub; an optional domain.
About €5 a month. Serverless platforms cannot run the embedding model, which
would force a rewrite of the core; Oracle Cloud's free tier is the free
alternative, with a fiddlier signup. A rented server is a cloud IP, so sources
that block cloud IPs (Substack) will block it too — discovery says so rather
than offering them.

**Testing before paying for anything** — two setups, both free:

| Setup | What it tests | How |
|---|---|---|
| **GitHub Pages** | Reading, layouts, topic settings, the tree view — over the sources the scheduled job already fetches | The new frontend, the site itself since 2026-10-05 (version 1's page is retired), reading the bundle the current pipeline produces. Every device that has never opened it is a new reader. |
| **The owner's computer** | The same app plus **suggestions and discovery** — the first run's "here is what we found", creating a topic, and adding sources — for real, for any subject or site | `trib serve` delivers both the new page and a discovery endpoint (built on today's `trib sources --suggest`). Phone on the same Wi-Fi: `--host 0.0.0.0`; away from home: a free tunnel (Cloudflare Tunnel or Tailscale) while the computer is on. The page and the endpoint come from the same server, because a page on Pages cannot call a plain-http server on another device. |

**Suggestions are built on the real backend, not faked.** Decided 2026-10-04:
*"Lets wait with suggestions until I setup the backend on my computer. I do not
want to take too many shortcuts now."* So suggesting and discovering sources is
designed and tested only on the owner's computer, with real fetching — no
hand-made catalogue standing in for it on Pages.

## Open questions

- **Where suggestions come from, without paying for search** — to be worked out
  once the backend runs on the owner's computer. Candidates: sites linked from
  sources already used; Reddit and Hacker News domains for a subject; public
  feed directories and OPML collections; a starter catalogue as a seed. A search
  API works and costs money. None measured yet.
- **Real sign-in**, later: emailed link or Google/GitHub. For now a profile is
  just a name.

## What carries over from version 1

Lessons that cost real work, detailed in `CLAUDE.md`:

- **The story is the unit, not the article**, built cheapest-first: a shared
  identifier (arXiv id, DOI, canonical URL) before embedding similarity, and a
  wrong merge costs more than a missed link. The measured merge threshold is
  0.92.
- **Following is the filter**: an empty follow set is an empty feed, and a
  feed full before you choose anything is the habit the project replaces.
- **Version 1's personal "lenses" were a rehearsal of personal topics** — a
  saved query any reader could make — and showed that per-reader filtering
  works in the page.
- **Source findings**: Substack blocks cloud IPs; Reddit needs no key but a real
  User-Agent; Google News links break clustering; GDELT rate-limits hard;
  GitHub's pre-release flag cannot be trusted alone.
- **Page lessons**: big cards are wanted and chrome is the waste; back climbs
  one level; a subject opens like a profile; nothing narrows the feed silently;
  a hidden search is a filter nobody can see; "new" is unread and recent.
