# Tributary — what is next

Only upcoming work lives here. **When a step is done, delete it** — history is in
git. The design these steps build is in **`VISION.md`**; read it first.
`CLAUDE.md` holds the pipeline's rules and lessons; version 1's page is retired.

The redesign goes in steps, and **each step ends in something the owner can try
and judge before the next one costs anything** — no hosting is paid for until
the design feels usable.

## 1. The new frontend, on GitHub Pages

Build what the approved mockup shows (`docs/mockup/index.html`, approved by the
owner 2026-10-04: *"It looks perfect"*). React with Vite (decided 2026-10-04), in its own folder,
published free on GitHub Pages.
It reads the bundle the current pipeline already produces. A profile is a name,
no password; topics and their source lists live with it in the browser.

**Built 2026-10-04 in `web-next/`**, and since 2026-10-05 the site itself at
https://sebbefagerstedt.github.io/tributary/ (version 1's page is retired): profile, first run, home with
the layout switch, topic pages with subtopics, the player, topic settings, new
topics, the story sheet and the tree. Starter subjects are the spine's shelves
and the sources offered are the ones the pipeline already reads, until step 2.
This step is done when the owner has used it on a phone and its fixes are in.

## 2. The backend on the owner's computer, with real suggestions

No shortcuts: suggestions are built against real fetching (`VISION.md`).

**Built 2026-10-04, first half.** `trib serve` serves the new page at `/`
beside the API (`/api/next/…`), and the page notices it and switches from the
browser to the server: profiles and topics with their source lists are stored
in the database (`readers.py`, migration 009), a typed subject or a pasted site
is searched (`suggest.py`, on `trib sources --suggest`) and previewed, a source
found that way becomes a row with `origin = 'reader'` that the pipeline fetches
while some topic uses it, and saving one runs the pipeline once so its news
arrives at once. How to run it is in `web-next/README.md`. What is left:

- **The owner tries it** on the computer and a phone, and the fixes go in.
- **Where subject suggestions come from.** A subject only ranks the sources
  Tributary already reads, by how many recent stories of theirs fit; a pasted
  site reaches anywhere. Finding sources for a subject on the open web has to
  be worked out on the owner's machine, where the network is open.
- **`FIT_FLOOR = 0.62` is unmeasured**, in `suggest.py` and `state.ts` alike —
  measure it against the owner's corpus before trusting a topic of one's own to
  catch stories that never use its words.
- Topic relations for "Up and related" (`VISION.md`): a topic's parent, and a
  short Related row from the embeddings — browsing only, never adding to the
  feed. An unfollowed topic opens as a preview: stories already held that fit,
  then a live fetch of its suggested sources, kept only briefly.

## The owner goes through this: how a topic of your own matches

Asked 2026-10-08: *"a topic should not only go on the actual word, that can be
a part of it, but I do not see why following a story should work smarter than
following a topic."* Today the ways of making a topic of your own match in
three different ways:

- **Following a story** matches by meaning: the story's vector, and any story
  within `EVENT_FLOOR` (0.82) of it (`state.likeExamples`). Its words are not
  asked.
- **A subject made on Pages** matches by words only — every word of its name
  (`state.namedIn`) — because only the pipeline runs the model, and it never
  sees what a reader types; the browser has vectors for stories, not for words.
- **A subject made with `trib serve`** matches its words *or* its embedded
  description, at `FIT_FLOOR` (0.62, unmeasured — see step 2).

So on Pages a followed story is smarter than a followed subject. The owner's
direction: words can be part of a topic, never all of it — and **words suit a
specific event better than a general topic** (2026-10-10: *"that might be more
suited to when following a specific event instead of a more general topic"*),
the opposite of how it works today:

- **An event has names**, so words fit it: the people, places, companies and
  versions in its headline ("Wikimedia", "Japan Open", "Bevy 0.20"), and the
  entities the pipeline already finds per story (they are in the bundle; 34
  seeded, all AI so far). One name alone is a whole subject — "OpenAI" is all
  of OpenAI's news — so an event asks for its names together, or for a name
  and closeness, and keeps its vector for follow-ups that use other words.
- **A general topic is a concept**: its stories rarely share one word, and a
  word catches the wrong ones — *"we're happy to announce"* put Bevy 0.20 in
  Happy News (2026-10-10). It needs meaning, with words as one part. Ways to
  give it meaning on Pages:
  - **Teach it by what it finds.** The stories its words catch, or the ones
    the reader taps in the preview, become its examples, and it then takes
    what is close to them by meaning, as a followed story does. No model in
    the browser — it is "A topic taught by examples" below, finished. A wrong
    word match would teach the wrong meaning, so the reader confirms them.
  - **Run the model in the browser.** bge-small has browser builds (ONNX
    Runtime Web, transformers.js), so Pages could embed a typed subject as the
    server does. Not tried here: it costs a download of tens of megabytes on a
    phone, and its vectors must agree with the pipeline's — measure both.
- **Then one rule for every topic of your own:** names and meaning together,
  weighted by kind — names first for an event, meaning first for a subject,
  and loosest for a tone like Happy News.

## Next: your own topics inside the tree

General news arrived on 2026-10-05 as one shared tree (News → eight
categories → subtopics, AI under Technology). The next step is the one AI
already showed: **a reader makes their own subtopic under any topic** — "New
topic inside Sport" from Sport's page, or the app proposing where a topic you
typed belongs ("This looks like part of Health. Put it there?", `VISION.md`,
"Who decides the parent"). A topic already carries `parent`, and the server
stores it; what is missing is choosing it and drawing it in the graph.

**Happy News is the test case for the topic filter** (the owner's own,
2026-10-06). The owner's rule: *"I want the news filter to work for any type of
topic"* — so the fix is not to switch the filter off for it, but to make the
filter able to hold a topic like it. Happy News is the hard case because it is
a *tone*, not a subject: no category holds it, its words appear in no headline,
and a description embedded once ("uplifting, hopeful news") measures what a
story is about far better than how it feels. Directions to try, cheapest first:

- **A topic taught by examples.** Version 1's lenses did this ("More like this",
  `addSeed`): the reader marks stories that fit and that do not, and the topic's
  vector moves towards the first and away from the second. Works for any kind
  of topic, needs no model in the browser, and is the same signal a shared topic
  will need later. **Half built (2026-10-07):** a topic can be taught by
  one story — "Follow this story" — and stores `examples` with their vector
  (`state.likeExamples`, `readers._examples_vector`). Left: adding more
  examples and counter-examples from a card, and a bar per topic — an event
  wants `EVENT_FLOOR` (0.82, unmeasured), a tone like Happy News a looser one.
- **A description with its opposite.** Score against "good news" *minus*
  "bad news" rather than "good news" alone, so the axis is the tone and not the
  subject. Measure it before trusting it: whether bge separates tone at all is
  an open question, and the corpus to measure on lives in the Actions cache.
- **Sources that write only in that tone** (Positive News, Good News Network,
  Reasons to be Cheerful) as the seed set — verified from Actions first.

## Subtopics the general categories are missing

Each category has three subtopics, so the nearest one took everything else in
its field — a tennis final went to Football (2026-10-06). A category now keeps
a story that fits it better than its subtopic (`topics._contest`), which stops
the wrong filing but leaves the story on the bare category. The real fix is the
missing subtopics: Tennis, Motorsport, Ice hockey under Sport; Books under
Culture; and whatever `trib topics --suggest` shows piling up on a category.
**Not now, on the owner's call** — and naming stays theirs.

## 3. Hosting, once it feels right

The small server from `VISION.md`, accounts, and topics stored per person.

## Parked — from version 1's plans

Not part of the first version. The full notes are in git history: `NEXT.md` as
of commit `ed1c48f`.

- **Posting and commenting**, with the worked-out design: comments hang on a
  story, posts on a topic; the comment's address must survive a re-cluster, so
  it cannot be the story's row id alone.
- **Subjects outside AI**: product launches and their affiliate-content problem,
  search that fetches when you ask, and GDELT (open, keyless, but rate-limited
  hard). The redesign absorbs most of this — every reader picks their own
  subjects — but those notes say what a broad source costs.
