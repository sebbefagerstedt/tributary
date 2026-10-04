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

## What the rebuild needs

| Piece | What it does |
|---|---|
| **Source discovery** | Turns "I want AI video news" or a pasted site into candidate feeds, checks each one parses, and offers a few. Feed autodiscovery (`<link rel="alternate">`, well-known paths, news sitemaps) is built today as `trib sources --suggest` (`discover.py`) and carries over. Finding *which sites* to try from a subject is the open part (below). |
| **A shared source catalogue** | Every source anyone follows, fetched on a schedule once each, with health and last error, as today's `sources` table. |
| **Per-reader trees** | Which sources and subjects each reader follows, stored with an account rather than in one phone's `localStorage`. |
| **The pipeline, per source** | Today's stages — fetch, describe, embed, cluster, label — still apply; they just run over the union of what readers follow. |
| **Expiry** | Items deleted after a fixed window; sources nobody follows stop being fetched. |
| **The reader** | Today's page shape is the starting point: Topics as the map, the Feed as the reader, circles that play what is new, "new" meaning unread and under 48 hours old. |

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
