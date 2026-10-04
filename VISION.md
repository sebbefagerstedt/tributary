# Tributary — the spec for the redesign

**This is the design of the next Tributary, and the file to read first.** It is
meant to outlive the code: the app is being redesigned from scratch, and most of
this repo will be replaced. Written 2026-10-04 from a day of decisions with the
owner, consolidated into one pass so nothing here contradicts anything else.

- `CLAUDE.md` describes **version 1**, the app that runs today, and what
  building it taught. Where the two disagree, this file wins for the redesign;
  `CLAUDE.md` stays as the record of lessons.
- `NEXT.md` is the roadmap: the steps from here to the redesign, in order.

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

### Exploring your tree

*"I would actually like a view where you can explore your tree it would be
cool."* Your topics, the subtopics under them, the sources feeding each, and the
related topics around them, seen whole. An outline you fold, a map of nodes, or
both — to be decided in the mockups.

## The model

| Thing | What it is |
|---|---|
| **Source** | A feed (RSS, Atom, a news sitemap, or a special adapter such as arXiv, Hacker News, GitHub releases). Shared: fetched once for everyone who uses it, with its health and last error. |
| **Item** | One entry from a source: title, short summary, link, date, picture, vector. Expires after a fixed window. |
| **Story** | Items about the same event, grouped — the unit you read, as in version 1. |
| **Topic** | Yours. A name, a short description (embedded, so it can be compared), the sources you chose for it, optional muted words, and optionally a parent topic — subtopics are topics with a parent. |
| **Your tree** | Your topics and how they nest. On a device for now; with an account once there is a server. |

**How a story gets into a topic.** A story is in your topic when it comes from
one of the topic's sources **and** fits the topic. A dedicated source (a lab's
own blog in a model-releases topic) nearly always fits; a general source (Hacker
News, a tech site) writes about everything, and only its stories that match the
topic's description by embedding reach the topic. Muted words then take out
what you never want to see. *Open:* whether "fit" is always automatic, or each
source in a topic gets a visible choice between "everything" and "only what
fits".

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
  recorded decisions are a checklist of lessons, not a template. Framework not
  chosen yet; Svelte is the suggestion, for doing a lot of interface in little
  code.
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
| **GitHub Pages** | First run, reading, layouts, topic settings, the tree view — with a fixed menu of starter subjects and a catalogue of sources the scheduled job already fetches | The new frontend published next to version 1 (for example under `/next/`), reading the bundle the current pipeline produces. Every device that has never opened it is a new reader. |
| **The owner's computer** | The same app plus **real discovery** of any subject or site | `trib serve` delivers both the new page and a discovery endpoint (built on today's `trib sources --suggest`). Phone on the same Wi-Fi: `--host 0.0.0.0`; away from home: a free tunnel (Cloudflare Tunnel or Tailscale) while the computer is on. The page and the endpoint come from the same server, because a page on Pages cannot call a plain-http server on another device. |

## Open questions

- **Where suggestions come from, without paying for search.** Candidates: a
  starter catalogue curated by hand; sites linked from sources already used;
  Reddit and Hacker News domains for a subject; public feed directories and OPML
  collections. A search API works and costs money. None measured yet.
- **What a general source puts in a topic** — automatic fit, or a visible
  per-source choice (see The model).
- **One home or several within your tree?** Version 1 gave each story exactly
  one topic, because a shared spine needed that (`CLAUDE.md` has the
  measurements). In a personal tree a story fitting two of your topics may
  belong in both; to be decided with real use.
- **How the tree view looks** — outline, map, or both.
- **Identity**, once there is a server: emailed link or Google/GitHub sign-in.

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
