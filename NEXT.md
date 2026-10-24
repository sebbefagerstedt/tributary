# Tributary — what is next

Only upcoming work lives here. **When a step is done, delete it** — history is in
git. The design these steps build is in **`VISION.md`**; read it first.
`CLAUDE.md` holds the pipeline's rules and lessons; version 1's page is retired.


## 1. The backend on the owner's computer, with real suggestions

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

## One kind of topic, and a tree that starts empty

Decided 2026-10-24; the design is in `VISION.md` under that name. What differs
from today, to build — best once the backend is hosted, since a topic's words
need the model when it is made:

- **A followed story becomes an ordinary topic at the strict end**, not a
  separate thing. Today it is a topic with `examples` matched only by
  closeness (`EVENT_FLOOR`, 0.82); it keeps its vector, and gains the names in
  its story as words, so naming them counts too.
- **Every topic gets a strictness setting**, from the whole subject
  (`FIT_FLOOR`, 0.62) to one happening (`EVENT_FLOOR`, 0.82). Both bars are
  unmeasured: measure them on the owner's corpus before choosing the range.
- **A topic matches by naming it or meaning it**, at its strictness. Today
  Pages asks every word of the name and nothing else, and `trib serve` asks
  the words or the vector at 0.62; on Pages the words-only rule goes once the
  hosted backend can embed what a reader types. Check what a lone name's
  vector (Saab) pulls in. Happy News, a tone rather than a subject, is the
  hard case (below).
- **Your tree starts empty.** Today the first run, New topic, the tree graph,
  every topic page's "Inside" boxes and the start page's "Inside Technology"
  rows (added 2026-10-24) all show the pipeline's shared labels as the tree.
  The shared labels become suggestions to start a topic from; the tree, the
  graph and "Inside" show only your topics and the subtopics you made or
  accepted.
- **Subtopics, proposed** (`VISION.md`, The model): clustering a topic's
  stories proposes subtopics, you name and accept them — what fills a tree
  that starts empty.
- **"Kitchen design" is the test case**: a topic with nothing in the shared
  labels and no source Tributary reads today, so it needs sources found on
  the web (pasting a site works; finding them for a subject is the open
  question in step 1).
- **Other languages come later**, as their own step: a multilingual embedding
  model, every item re-embedded and every calibrated value re-measured.

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
