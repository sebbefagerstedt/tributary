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
view is an interactive graph like the reference in `docs/reference/`, but
prettier.

**First version built 2026-10-04:** `docs/mockup/index.html`, published as an
artifact at https://claude.ai/artifact/1XeimYb1Q7VEdZJ6H6KnsG. Sample stories,
nothing fetched. This step is done when the owner has tried it and the changes
it prompts are in.

## 2. The new frontend, on GitHub Pages

Choose the framework (Svelte suggested), set it up in its own folder, and
publish it free on GitHub Pages next to version 1 (for example under `/next/`).
It reads the bundle the current pipeline already produces. A profile is a name,
no password; topics and their source lists live with it in the browser.

## 3. The backend on the owner's computer, with real suggestions

No shortcuts: suggestions are built against real fetching (`VISION.md`).

- `trib serve` serves the new page and the API from one place, on the owner's
  computer, reachable from a phone (same Wi-Fi, or a free tunnel).
- Profiles (a name, no password) and their topics with source lists, stored by
  the backend.
- Discovery: from a subject or a pasted site to candidate sources, each with a
  preview (latest headlines, items a week) — built on `trib sources --suggest`.
  Where subject suggestions come from is worked out here.
- The pipeline fetches the sources the profiles' topics use, and a story can
  sit in several topics, read once.

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
