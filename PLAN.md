# Tributary — the plan for starting over

Decided 2026-10-24. This repository stays as it is — version 1's pipeline and
the redesign's page, live at https://sebbefagerstedt.github.io/tributary/ — and
the next Tributary starts small, **in a new repository, when the owner is
ready**. This file is that plan, and **`start-over/` is the package to start
that repository from**: five standalone files to copy to its root, with no
code (2026-11-01). It replaces `NEXT.md`, whose steps grew this repo beyond
what the core loop needed: *"my weakness is thinking too big from start."*

## What carries over

- **The idea.** Your own topics, fed by sources you choose, with help finding
  more of them. *"I find a topic I want to follow, Tributary should help me be
  up to date. I might know one source, e.g. where I first heard it, but I want
  help to find more."*
- **The frontend's design**, the part the owner is most satisfied with: tiles
  and cards, a topic's page and its subtopics, the crumbs back up, and the
  ontology graph. Copy it from `web-next/` (the components, `styles.css`,
  `graph.ts`) rather than redesign it.
- **A few pieces of the backend**: `discover.py` (a site's feed, from its
  `<link>`, the well-known paths and a news sitemap), the RSS adapter, and the
  HTTP layer's conditional GET. Everything else here stays behind.

## How a topic works

From `VISION.md`, "One kind of topic, and a tree that starts empty":

- **There is one thing, a topic**: what it is about, its sources, and later
  how strict it is. A name (Saab), a subject ("kitchen design") and a tone
  (Happy news) are all topics.
- **Every user starts with one topic, and your tree is only your topics.**
  "Kitchen design" can be the whole of it.
- **Sources are the filter they always were**: one source can feed several
  topics, and a topic shows only stories from its own.
- **Subtopics are never created for you** (decided 2026-11-01). What the old
  plan called proposed subtopics — clustering a topic's stories into narrower
  ones — is shown as **Related** instead: a short row on a topic's page, three
  or four topics close in meaning, each a look and never a follow. A subtopic
  exists only when **you add a topic yourself** and it is classified as part
  of one you have: *"This looks like part of Kitchen design. Put it inside?"*
  You accept or decline; declined, it stays a topic of its own.

## The workflow — what done means

The plan is done when this works end to end, on a phone, for a topic no source
covered beforehand. Steps 1–5 below build it; step 6 hosts it.

1. **Say what you want to follow.** A new user meets one screen: a sentence
   about the topic, and optionally a link to a source you already know — where
   you first heard of it.
2. **See what it found, as two lists.**
   - **Sources**: the one you pasted and the ones suggested from it, each with a
     preview — its latest headlines and how many items a week it publishes —
     and a tick. **Include all**, or pick some.
   - **Example stories it would catch**: recent stories from the ticked
     sources that name the topic or are close to it in meaning, each with
     **✓ fits** and **✗ does not fit**. Ticking a source changes the list; a ✓
     or ✗ teaches the topic what it means, and the list re-sorts.
3. **Create it, and read.** You land in the topic's feed with stories in it,
   in the design that carries over.
4. **Keep teaching it, quietly.** Like or dislike on any story in the feed is
   the same ✓ and ✗. The topic's settings hold its sources (remove one in a
   tap, paste a link to add one, with the same preview) and its words.
5. **Look sideways.** The topic's page shows Related topics. Opening one is a
   preview; following it goes through step 2.
6. **Add a second topic yourself.** Same flow. If it is classified as part of a
   topic you have, you are asked whether to put it inside; nothing else ever
   makes a subtopic.

**Done means:** a new user gets from a sentence to a feed with fitting stories
in a few minutes; the example list is mostly right before any ✓ or ✗, and
clearly better after a handful; every source in the topic was shown with a
preview before it was added; and nothing — a source, a subtopic, a follow — was
added without a tap.

### Example: AI best practices

The owner's own topic (2026-10-31): *"I really want to follow the latest AI
best practices in models settings prompts etc."*

- **Typed:** "The latest AI best practices: model settings, prompting, evals,
  agent setups". **Pasted:** one practitioner's blog the owner already reads.
- **Sources:** that blog, then the sites its posts link to most — provider docs
  and changelogs, other practitioners' blogs — each previewed.
- **Examples:** *"What changed in how we prompt reasoning models"* gets ✓;
  *"Lab raises $40B"* gets ✗ — it names AI and is not practice.
- **Why it is the hard case:** it is a genre (how-to, lessons learned), not a
  subject, so its words alone catch the wrong stories — the ✓ and ✗ are what
  make it work. Many of the best writers for it are on Substack, which blocks
  cloud IPs; a suggestion that cannot be fetched says so.
- **Related**, for instance: "Coding agents", "Local models". **A subtopic**
  only if the owner later adds, say, "Prompting Claude" themselves and accepts
  putting it inside.

### Example: Kitchen design

The first test case (see the end of this file): a topic none of this repo's
sources covers, so everything comes from the paste.

- **Typed:** "kitchen design". **Pasted:** an interior magazine the owner reads.
- **Sources:** the magazine, then the sites its articles link to — other
  magazines, studios, a maker's news page — each previewed, so one that posts
  forty times a day is seen before it floods the topic.
- **Examples:** a renovation feature gets ✓; the same magazine's piece on
  garden furniture gets ✗ — from a ticked source and still not the topic,
  which is why a source is never the whole filter.
- **Related**, for instance: "Interior lighting", "Small apartments". **A
  subtopic:** the owner adds "Scandinavian kitchens" and is asked whether it
  belongs inside Kitchen design.

## The steps

Each step is usable on its own. **Do not start a step before the previous one
has been used for a week**; a new idea goes on the "Not now" list instead of
into the code.

1. **One topic.** Add sources by pasting a URL; read their articles in the
   design that carries over. Single user, on the owner's computer — but every
   topic and source row belongs to a user from the first day, so accounts
   change where nothing is stored.
2. **Several topics, crumbs and the graph** — the navigation that carries
   over. A subtopic here is one you put inside another by hand; asking "part
   of this one?" waits for step 5, which gives topics a meaning to compare.
3. **Add a story to a topic yourself**, by pasting its link — the same paste
   as adding a source in step 1. It belongs to that topic whatever its source,
   and later (step 5) it is also an example of what the topic means.
4. **Suggested sources, from the ones you have.** The sites a source's
   articles link to most often are candidates; find each one's feed with
   `discover.py` and offer it with a preview. Unproven: try it on one real
   source before building around it.
5. **Close in meaning, taught by you.** A topic's description is embedded and
   a story fits when it names the topic or is close to it. **Like and dislike**
   on a story ("this does not fit my topic") move the topic towards and away
   from examples — teaching the topic what it means, never ranking by what you
   do. Use a **multilingual embedding model from the start**: a new repo has
   no calibrated values tied to the old one, so it costs nothing now. The
   same topic vectors give the **Related** row and the "part of this one?"
   question when you add a topic.
6. **Hosted, with accounts.** On AWS, once it has been used daily for a couple
   of weeks. Login from an open-source library, not a provider that can start
   charging.

## Later, once there are other users

From the owner's own list (2026-10-24); neither is worth anything with one
reader.

- **Community at the foot of a topic's page.** Version 1 designed it: comments
  hang on a story, posts on a topic, and a comment's address must survive a
  re-cluster, so it cannot be a story's row id alone. The notes are in this
  repo's history, `NEXT.md` as of commit `ed1c48f`.
- **Trending: what others like.** Careful: counting what many people like is
  exactly the ranking version 1 kept out, and it is rich-get-richer. The
  shape `VISION.md` allows — *"what many people choose helps the next person"*
  — is popular topics and sources offered as **suggestions**, never your feed
  reordered by popularity.

## Decisions

- **A server from the first day, and nothing shaped by GitHub Pages**
  (decided 2026-11-01). This repo's page was built to run as a static site,
  and that cost it: one JSON bundle of every story, kept small by caps per
  topic; profiles and topics in `localStorage`; a typed topic that could only
  match by its words, because the browser cannot run the model; two modes, one
  for Pages and one for `trib serve`; suggestions that worked only on the
  owner's computer. None of that carries over. The new app always talks to its
  API — on the owner's computer first, on AWS at step 6 — which embeds,
  matches, suggests and previews on request, and pages its stories instead of
  shipping them all at once.
- **One repository, two folders** (`web/` and `api/`). Early on a feature
  changes both at once; the owner works alone; and the two still deploy
  separately on AWS — a static site from `web/`, a server from `api/`, each
  deployed when its own folder changes. Split later only if someone else owns
  one half, one half goes open source, or a second client (a phone app) uses
  the API — splitting keeps history, merging two repos is messier.
- **No services that might start charging.** Nothing the app needs to work may
  depend on a free tier someone else controls.
- **No news APIs.** Their free tiers are 12–24 hours late, cut the text and
  mostly forbid commercial use; paid tiers start around $150–450 a month
  (checked 2026-10-24). RSS is free, immediate and carries a picture.
- **No web search for suggestions, for now.** Google's search API is closed to
  new customers and ends on 2027-01-01; scraping it breaks its terms; the
  alternatives are paid services with free tiers — the lock-in above.
  Suggestions start from the links in sources you already have (step 4).
- **Like and dislike are allowed** because they are explicit and teach a
  topic, not the ranking: version 1's rule against learning from behaviour
  was about time spent, dwell and scroll-past, and that stays out.

## Not now

Grouping articles into stories, and following one · ranking · how strict a
topic is · the player · muted words · OPML · other languages as a feature ·
the shared tree (News, Technology, AI…) · the arXiv, Hacker News and GitHub
adapters · news and search APIs.

## Before leaving this repository

- **The live site stops updating after 60 days without a push** — GitHub turns
  off scheduled workflows. It stays online either way; push now and then if its
  news should stay fresh.
- **"Kitchen design" is the first test case**: a topic no source here covers,
  so it needs a pasted URL, then step 4's suggestions.
