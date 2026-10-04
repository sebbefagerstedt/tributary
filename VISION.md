# Tributary — the vision, for the rebuild

Written 2026-10-04, when the idea changed shape. **This file is meant to outlive
the code.** The app will be rebuilt on a different deployment, and most of what
is in this repo will be replaced; this is what should not be. `CLAUDE.md`
explains how the current app works and why; this explains what the next one is
for.

## The idea

**Tributary is a platform for building your own news, not a news app with fixed
sources.** Each reader grows their own news tree: they find sources, choose
which to keep, and arrange what arrives into subjects that mean something to
them. The current AI feed is one example of a tree, offered as a starting point
and never imposed.

In the owner's words, 2026-10-04:

> Tributary should be a platform to be able to personalise news. So a user
> should be able to create their news tree themself. […] So it is less of an app
> with fixed sources, and more a personal news app like i wanted.

> I will never be able to know what the user wants in advance. This is the
> entire reason why is has felt unscaleable. To have a user find and choose on
> their own is sooo much better.

### Why this replaced the old shape

The current app has one source list in `config.toml`, fetched for everyone by a
scheduled job. Every new subject meant the owner finding its sources by hand,
and every reader got the owner's choices. That is what felt unscalable: not the
storage, which is small, but having to know in advance what everyone wants. Once
readers find their own sources, the app no longer has to guess.

## Design principles

1. **The reader finds and chooses; the app suggests.** Search for a subject or
   paste a site, get a few suggested sources, then take all of them, some or
   none — and do it again at any time, not only at signup. Nothing joins a
   reader's tree without their say-so. (The same propose-then-accept rule the
   current app uses for topics and entities.)
2. **Start from examples, never from nothing.** A new reader picks from starter
   trees — the AI tree that exists today, and others — so the first screen is
   news, not a form.
3. **Fetch only what someone follows, once.** A source is fetched if at least one
   reader follows it, and once however many do. Nothing nobody follows is
   fetched or kept. This is what makes "personal" affordable: cost grows with
   what people chose, never with the size of the internet.
4. **Keep headlines and links, not the news.** Store a title, a short summary, a
   link, a date and a vector, for a limited time. The article stays on the
   publisher's site. Old items expire; nothing is archived "just in case".
5. **Discovery needs the open web, so the app needs a server.** Finding sources
   a reader asks for cannot be done in advance or from a static page. The
   rebuild is a real deployment with network access and accounts — see below.
6. **Shared knowledge emerges from many readers, later.** Once there are users,
   sources and subjects that many people follow become the best suggestions
   for the next person ("people who follow X also follow Y"), and a subject
   many people build in the same place is a candidate for a shared one. Until
   then, nothing pretends to know.
7. **Replace the scroll habit's content, keep its form.** Unchanged from the
   current ground rules: borrow the large, image-led, immersive form of social
   apps and never their hooks. No autoplay timers, no endless refill, no
   ranking tuned to keep you scrolling, no learning from time spent.
8. **No LLM by default.** Local embeddings do the understanding — grouping items
   into stories, matching subjects, judging whether a suggested source fits.
   Anything that needs a paid model is optional and priced.

## The tree, and how you look at it

Added 2026-10-04, the same day.

**The embedding layer stays, as the tree's engine.** The current app already
builds an ontology from local embeddings — topics, the subtopics under them,
names, and stories — and the owner wants it kept: *"The embedding layer we have
now to create a ontology tree is very nice. I think it will be useful in some
way, the relations can be used to find similar topics and of course to auto
create the subtopics."* In a personal tree that becomes:

- **Subtopics proposed automatically.** When a subject fills up, clustering what
  sits in it (what `trib topics --suggest` does today) proposes the subtopics
  under it. The reader names and accepts them; nothing is added silently.
- **Similar topics from the relations.** Topic vectors sit in one space, so
  "near this" is a cosine away: related subjects to explore, a synonym caught
  before it becomes a duplicate, and a new source's items placed where they fit
  in the tree.
- **The same vectors judge suggestions.** A candidate source is embedded and
  compared with the subject the reader asked for before it is offered.

**A view where you explore your own tree.** *"I would actually like a view where
you can explore your tree it would be cool."* The tree is the reader's own
creation, so it deserves a place to be seen whole — subjects, their subtopics,
the sources feeding each, and the related subjects around them — not only a
list of follows. How it looks is open: an outline you fold, a map of nodes, or
both.

**Layouts, not tabs.** *"I want to keep a similar format with the topics and
feed view, but it does not have to be in different tabs in the new app. Think
like instagram and most sites where you can choose which layout you want."*
Today Topics (circles and tiles, the map) and Feed (big cards, the reader) are
separate tabs. In the rebuild they are **layouts of the same place**: wherever
you stand — everything, a subject, a subtopic — you pick how to see it, the way
Instagram switches a profile between a grid and a list. The formats themselves
stay; the tab bar that separates them does not have to.

## What the rebuild needs

| Piece | What it does |
|---|---|
| **Source discovery** | Turns "I want AI video news" or a pasted site into candidate feeds, checks each one parses, and offers a few. Feed autodiscovery (`<link rel="alternate">`, well-known paths, news sitemaps) is built today as `trib sources --suggest` (`discover.py`) and carries over. Finding *which sites* to try from a subject is the open part (below). |
| **A shared source catalogue** | Every source anyone follows, fetched on a schedule once each, with health and last error, as today's `sources` table. |
| **Per-reader trees** | Which sources and subjects each reader follows, stored with an account rather than in one phone's `localStorage`. |
| **The pipeline, per source** | Today's stages — fetch, describe, embed, cluster, label — still apply; they just run over the union of what readers follow. |
| **Expiry** | Items deleted after a fixed window; sources nobody follows stop being fetched. |
| **The reader** | Today's formats are the starting point — tiles and circles, big cards, circles that play what is new, "new" meaning unread and under 48 hours old — but as switchable layouts of one place rather than tabs, plus a view to explore your whole tree. |
| **The ontology** | Today's embedding layer: subtopics proposed from clusters, similar topics from vector relations, and candidate sources judged against the subject asked for. |

### Open questions to settle before building

- **Where suggestions come from, without an API key.** Candidates to test: a
  starter catalogue curated by hand; sites that already appear in followed
  sources' links (which this repo already extracts); Reddit and Hacker News
  domains for a subject; public feed directories and OPML collections. A search
  API would work and costs money. None of these has been measured.
- **How a suggestion is judged before it is offered.** Fetch it, check it parses,
  embed a few recent items and compare them with what the reader asked for.
- **Hosting and identity.** `NEXT.md` has the notes from the multiple-users work:
  a free tier (Cloudflare Workers with D1) has the headroom, and a login of some
  kind is unavoidable once trees live on a server.
- **What can be tried before the rebuild.** Following *sources* (not only
  topics) works in the current static app, from a larger fixed catalogue —
  the database already has an unused `follows` table with
  `target_kind = 'source'`. It tests the feeling of choosing sources before
  anything is hosted.

## Features for the first version — and what was left out on purpose

From a scan of similar apps on 2026-10-04 (Feedly, Inoreader, NewsBlur, Ground
News, Particle, Artifact, Bluesky), filtered by the owner's rule: *"the first
version needs to be lightweight. I do not want unnecessary features."*

**First version** — small, and each one serves the reader choosing for
themselves:

1. **Preview a source before following it** — its latest headlines and how
   many items a week it publishes, so a source that posts forty times a day is
   seen before it floods a subject. This is what makes "the reader chooses"
   work: choosing well needs something to judge by.
2. **Mute words and sources** — the opposite of a follow: hide anything that
   mentions "crypto", or one source inside one subject. Feedly ships it as mute
   filters, NewsBlur as "Hide". A word match, and the direct answer to "I got
   too much".
3. **Import and export sources as OPML**, the standard file every feed reader
   speaks — a new reader brings their old sources in one go, and a tree is
   never locked in.
4. **"You're all caught up"** — a clear end once everything new is seen, as
   Instagram added. The end of the feed is a place to stop, not a refill.

**Later, once there are users:**

5. **Shareable trees and starter packs** — share a tree, or one subject in it,
   as a link others can adopt (Bluesky's custom feeds work this way). This is
   also how "topics and sources many people follow" starts.
6. **Opt-in alerts for one subject** — a push when something lands in a subject
   marked important. Off by default: notifications are the classic hook.

**Considered and left out**, so they are not reconsidered without a reason:

- **AI summaries and rewritten headlines** (Artifact, Particle) need a paid
  model. Particle's core — grouping articles about one event by embeddings —
  is what Tributary's stories already do, without one.
- **Bias ratings and "blindspots"** (Ground News) lean on outside rating
  services, and are the "Verifierad" idea the owner removed on 2026-09-23.
- **Rules engines** (Inoreader's auto-tag, auto-archive, send to Slack) are
  heavy and built for analysts.
- **Like/dislike training** (NewsBlur) is learning from behaviour, which
  `CLAUDE.md` rules out.
- **A warning from the scan:** Artifact, by Instagram's founders and full of AI
  features, shut down in 2024 when growth stalled. Lightweight is the safer bet.

## Technology

**Decided 2026-10-04:**

- **The backend stays Python.** The pipeline, the embedding model, clustering
  and the measured thresholds all carry over as they are. *"Ok python is fine
  for the backend."*
- **The frontend is rebuilt in a real frontend stack**, replacing today's single
  HTML file with no build step. *"The frontend needs to be a frontend language.
  I do not want to lose functionality or design because it should be simple."*
  Simple means a small, clear codebase — **not** fewer features or a plainer
  look: everything the current page does and how it looks (`CLAUDE.md` records
  each decision) is the floor for the new one. The JSON contract between
  backend and page already exists and keeps the two independent. Which
  framework is not decided yet.

**Hosting — the leading option, not decided.** The cheapest setup that runs
today's Python as it is: **one small rented Linux server** (Hetzner's smallest
cloud server was about €4–5 a month — check the current price), running the
API, the scheduled fetching and SQLite, with Caddy for HTTPS; nightly database
backups to a free storage tier (Cloudflare R2 or Backblaze B2); email sign-in
links through a free tier (e.g. Resend) or sign-in with Google or GitHub; and
an optional domain. Roughly €5 a month in all. Serverless platforms are cheaper
on paper but cannot run the embedding model, which would force a rewrite of the
core. Oracle Cloud's free tier is the free alternative, at the price of a
fiddlier signup. One caveat: a rented server is a cloud IP too, so sources that
block GitHub Actions (Substack) may block it as well — discovery should say so
rather than offer them.

**If it is built in steps**, each is usable on its own: move today's app to the
server unchanged; then accounts and follows stored per person; then source
discovery in the app.

## What carries over from the current app

Lessons that cost real work and should not be learned twice, all detailed in
`CLAUDE.md`:

- **The story is the unit, not the article**, built cheapest-first: a shared
  identifier (arXiv id, DOI, canonical URL) before embedding similarity, and a
  wrong merge costs more than a missed link.
- **Following is the filter**, and an empty follow set is an empty feed.
- **A topic has one home; a reader's own subject is a lens** that cuts across.
- **Measured values** — merge threshold 0.92, topic floor 0.55 — are in
  `CLAUDE.md` with how they were measured.
- **Source findings**: Substack blocks cloud IPs; Reddit needs no key but a real
  User-Agent; Google News links poison clustering; GDELT rate-limits hard.
- **The page's design decisions**: big cards, little chrome, back climbs one
  level, a subject opens like a profile, nothing narrows the feed silently.
