# Tributary — what is next

Only upcoming work lives here. **When a step is done, delete it** — history is in
git. The design these steps build is in **`VISION.md`**; read it first.
`CLAUDE.md` describes version 1, the app running today.

The redesign goes in steps, and **each step ends in something the owner can try
and judge before the next one costs anything** — no hosting is paid for until
the design feels usable.

## 1. Mockups of the key screens

A clickable mockup to try on a phone, before any app code:

1. First run — what do you care about, here is what we found, Include all.
2. Home, with the layout switch (overview and reading layouts).
3. Reading one topic, and the full-screen player for its new stories.
4. A topic's settings — its sources, remove, search to add, muted words.
5. Exploring your tree.

Cheap to change; the point is to find out whether it feels right. The tree
view's shape (outline, map, or both) is decided here.

## 2. The new frontend, on GitHub Pages

Choose the framework (Svelte suggested), set it up in its own folder, and
publish it free on GitHub Pages next to version 1 (for example under `/next/`).
It reads the bundle the current pipeline already produces. Topics and their
source lists live in the browser, so every new device is a new reader and the
first run can be tested over and over.

## 3. Small backend changes for the prototype

- The bundle says which source each story came from, and carries a catalogue of
  sources to choose from, with what a preview needs (latest headlines, items a
  week).
- The scheduled job fetches a wider starter catalogue across several subjects,
  so the first run has more than AI to offer.
- A discovery endpoint in `trib serve`, built on `trib sources --suggest`, so the
  owner can test real discovery of any subject or site from their own computer
  (see "Testing before paying" in `VISION.md`).

## 4. Hosting, once it feels right

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
