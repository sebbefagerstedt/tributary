# Tributary — the plan for starting over

Decided 2026-10-24. This repository stays as it is — version 1's pipeline and
the redesign's page, live at https://sebbefagerstedt.github.io/tributary/ — and
the next Tributary starts small, **in a new repository, when the owner is
ready**. This file is that plan. It replaces `NEXT.md`, whose steps grew this
repo beyond what the core loop needed: *"my weakness is thinking too big from
start."*

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
- **Your tree is only your topics and starts empty.** "Kitchen design" can be
  the whole of it. A subtopic is a topic you put inside another.
- **Sources are the filter they always were**: one source can feed several
  topics, and a topic shows only stories from its own.

## The steps

Each step is usable on its own. **Do not start a step before the previous one
has been used for a week**; a new idea goes on the "Not now" list instead of
into the code.

1. **One topic.** Add sources by pasting a URL; read their articles in the
   design that carries over. Single user, on the owner's computer — but every
   topic and source row belongs to a user from the first day, so accounts
   change where nothing is stored.
2. **Several topics, subtopics, crumbs and the graph** — the navigation that
   carries over.
3. **Suggested sources, from the ones you have.** The sites a source's
   articles link to most often are candidates; find each one's feed with
   `discover.py` and offer it with a preview. Unproven: try it on one real
   source before building around it.
4. **Close in meaning, taught by you.** A topic's description is embedded and
   a story fits when it names the topic or is close to it. **Like and dislike**
   on a story ("this does not fit my topic") move the topic towards and away
   from examples — teaching the topic what it means, never ranking by what you
   do. Use a **multilingual embedding model from the start**: a new repo has
   no calibrated values tied to the old one, so it costs nothing now.
5. **Hosted, with accounts.** On AWS, once it has been used daily for a couple
   of weeks. Login from an open-source library, not a provider that can start
   charging.

## Decisions

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
  Suggestions start from the links in sources you already have (step 3).
- **Like and dislike are allowed** because they are explicit and teach a
  topic, not the ranking: version 1's rule against learning from behaviour
  was about time spent, dwell and scroll-past, and that stays out.

## Not now

Grouping articles into stories, and following one · ranking · how strict a
topic is · the player · muted words · OPML · other languages as a feature ·
the shared tree (News, Technology, AI…) · the arXiv, Hacker News and GitHub
adapters · news and search APIs · posting and commenting.

## Before leaving this repository

- **The live site stops updating after 60 days without a push** — GitHub turns
  off scheduled workflows. It stays online either way; push now and then if its
  news should stay fresh.
- **"Kitchen design" is the first test case**: a topic no source here covers,
  so it needs a pasted URL, then step 3's suggestions.
