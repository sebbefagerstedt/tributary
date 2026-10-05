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
