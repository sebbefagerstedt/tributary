# Plan

## The idea

*"I find a topic I want to follow, [Vett] should help me be up to date. I
might know one source, e.g. where I first heard it, but I want help to find
more."*

Every reader starts with **one topic**. Following one topic well is the whole
product until it works. Everything else waits.

## How a topic works

- **There is one kind of thing: a topic.** A name ("Saab"), a subject
  ("kitchen design") and a tone ("Happy news") are all topics. A topic has:
  - what it is about: the reader's sentence;
  - its sources;
  - its examples, the stories the reader marked as fitting or not fitting.
- **A story is in a topic** when it comes from one of the topic's sources
  **and** either names the topic or is close to it in meaning. A source alone
  is never the whole filter: a magazine about kitchens also writes about
  gardens.
- **One source can feed several topics**, and is fetched once.
- **Your topics are your whole tree, and it starts with one.**
- **Subtopics are never created for you.** A topic's page shows a short
  **Related** row instead: three or four topics close in meaning, each a look
  and never a follow. A subtopic exists only when **you add a topic yourself**
  and it is classified as part of one you have: *"This looks like part of
  Kitchen design. Put it inside?"* You accept or decline. If you decline, it
  stays a topic of its own.

## The workflow, and what "done" means

The plan is done when this works end to end, on a phone, for a topic no
source covered beforehand. Steps 1–5 below build it; step 6 hosts it.

1. **Say what you want to follow.** A new reader meets one screen: a sentence
   about the topic, and optionally a link to a source they already know.
2. **See what it found, as two lists.**
   - **Sources**: the one pasted and the ones suggested from it, each with a
     preview (its latest headlines, and how many items a week it publishes)
     and a tick. **Include all**, or pick some.
   - **Example stories it would catch**: recent stories from the ticked
     sources that fit, each with **✓ fits** and **✗ does not fit**. Ticking a
     source changes the list. A ✓ or ✗ teaches the topic, and the list
     re-sorts.
3. **Create it, and read.** The reader lands in the topic's feed with stories
   already in it.
4. **Keep teaching it, quietly.** Like and dislike on any story in the feed
   are the same ✓ and ✗. The topic's settings hold its sources (remove one in
   a tap, or paste a link to add one, with the same preview) and its sentence.
5. **Look sideways.** The topic's page shows Related topics. Opening one is a
   preview; following it goes through step 2.
6. **Add a second topic yourself.** Same flow. If it is classified as part of
   a topic you have, you are asked whether to put it inside. Nothing else ever
   makes a subtopic.

**Done means:**
- A new reader gets from a sentence to a feed of fitting stories in a few
  minutes.
- The example list is mostly right before any ✓ or ✗, and clearly better
  after a handful.
- Every source in the topic was shown with a preview before it was added.
- Nothing (a source, a subtopic, a follow) was added without a tap.

### Example: AI best practices

The owner's own topic: *"I really want to follow the latest AI best practices
in models settings prompts etc."*

- **Typed:** "AI best practices: model settings, prompting, evals, agent
  setups". **Pasted:** one practitioner's blog the owner already reads.
- **Sources:** that blog, then the sites its posts link to most, such as
  provider docs and changelogs and other practitioners' blogs, each
  previewed.
- **Examples:** *"What changed in how we prompt reasoning models"* gets ✓.
  *"Lab raises $40B"* gets ✗: it names AI, but it is not practice.
- **Why it is the hard case:** it is a genre (how-to, lessons learned), not a
  subject, so its words alone catch the wrong stories. The ✓ and ✗ are what
  make it work. Many good writers on it publish on Substack, which blocks
  cloud IPs, so a suggestion that cannot be fetched must say so.
- **Related**, for instance: "Coding agents", "Local models". **A subtopic**
  only if the owner later adds, say, "Prompting Claude" and accepts putting it
  inside.

### Example: Kitchen design

The first test case.

- **Typed:** "kitchen design". **Pasted:** an interior magazine the owner
  reads.
- **Sources:** the magazine, then the sites its articles link to, such as
  other magazines, studios and a maker's news page. Each is previewed, so a
  source that posts forty times a day is seen before it floods the topic.
- **Examples:** a renovation feature gets ✓. The same magazine's piece on
  garden furniture gets ✗: it comes from a ticked source and is still not the
  topic.
- **Related**, for instance: "Interior lighting", "Small apartments". **A
  subtopic:** the owner adds "Scandinavian kitchens" and is asked whether it
  belongs inside Kitchen design.

## How a sentence is understood

No LLM. A local **embedding model** turns the sentence into a vector (a list
of numbers standing for its meaning), and does the same for every story when
it is fetched. A story fits when its vector is close to the topic's (cosine
similarity), or when it names the topic. Each ✓ moves the topic's vector
towards that story, and each ✗ moves it away.

What an embedding model gets wrong, and the cheap answer to each:
- **It reads the subject, not the intent.** It cannot tell a how-to from a
  funding round. The answer is ✓ and ✗.
- **"Latest" means nothing to it.** The feed is ordered by date anyway.
- **It ignores "not".** "AI but not crypto" sits near crypto. The answer is ✗,
  or excluded words later.
- **A sentence with several things in it is averaged** into something vague.
  Split it at commas and let a story match any part.

An optional, priced LLM step that rewrites the sentence once, at creation,
is the fallback. It is worth trying only if the example list measures mostly
wrong before any ✓ or ✗.

## The steps

Each step is usable on its own. **Do not start a step before the previous one
has been used for a week.**

1. **One topic, sources by pasted link.** Paste a site; its feed is found
   (`LESSONS.md`, "Finding a site's feed") and previewed; read its articles in
   the design from `DESIGN.md`. Runs on the owner's computer with a real
   server and API from the first day, phone on the same network.
2. **Several topics, crumbs and the graph** (`DESIGN.md`). A subtopic here is
   one you put inside another by hand; asking "part of this one?" waits for
   step 5, which gives topics a meaning to compare.
3. **Add a story to a topic yourself**, by pasting its link, the same paste as
   a source. It belongs to that topic whatever its source, and from step 5 it
   is also an example of what the topic means.
4. **Suggested sources, from the ones you have.** The sites a source's
   articles link to most often are candidates. Find each one's feed and offer
   it with a preview. **Unproven:** try it on one real source before building
   around it.
5. **Close in meaning, taught by you.** The sentence is embedded, and a story
   fits when it names the topic or is close to it. ✓/✗ and like/dislike move
   the topic. This step brings the example list in the workflow, the Related
   row and the "part of this one?" question. Use a **multilingual** embedding
   model from the start.
6. **Hosted, with accounts.** Once it has been used daily for a couple of
   weeks. On a rented server (AWS is the owner's leaning), with login from an
   open-source library rather than a provider that can start charging.

## Decisions

- **A server from the first day.** The page always talks to its API, which
  embeds, matches, suggests and previews on request, and returns stories a
  page at a time. Nothing is designed around a static host: no single file of
  every story, no reader data kept only in the browser, no second mode for
  hosting without a server.
- **One repository, two folders** (`web/`, `api/`). Early on a feature changes
  both at once, and the owner works alone. They still deploy separately. Split
  only if someone else owns one half, one half goes open source, or a second
  client (a phone app) uses the API.
- **No news APIs.** Their free tiers are 12–24 hours late, cut the text and
  mostly forbid commercial use. Paid tiers start around $150–450 a month
  (checked 2026-10-24). RSS is free, immediate and usually carries a picture.
- **No web search for suggestions, for now.** Google's search API is closed to
  new customers and ends on 2027-01-01, scraping it breaks its terms, and the
  alternatives are paid services with free tiers. Suggestions start from the
  links in the sources the reader already has (step 4).
- **Like and dislike are allowed** because they are explicit and teach one
  topic. Time spent, dwell and scroll-past stay out.

## Later, once there are other users

- **Community at the foot of a topic's page**: comments hang on a story, posts
  on a topic. A comment's address must survive stories being regrouped, so it
  cannot be a story's row id alone.
- **Popular topics and sources offered as suggestions**: what many people
  choose helps the next person. Never the feed reordered by popularity, which
  is rich-get-richer and the ranking this app exists to avoid.
- **Following one story**, such as a model's release: grouping articles about
  one event into a story, and tracking it inside a topic.

## Not now

Grouping articles into stories · ranking beyond newest first · how strict a
topic is · a full-screen player · muted words · OPML import and export ·
other languages as a feature · a shared starter tree of categories · special
adapters (arXiv, Hacker News, GitHub releases) · news and search APIs.
