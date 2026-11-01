# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repository.

Vett lets a person follow a topic: they describe it, choose its sources
with help, teach it what fits, and read it on a phone. `README.md` says what it
is, `PLAN.md` what to build next, `DESIGN.md` how it looks and `LESSONS.md`
what is already known. This file holds the rules and, as code arrives, how it
fits together.

## Ground rules

- **Lightweight first.** The owner's weakness, in their own words, is
  *"thinking too big from start"*. Build only the step in `PLAN.md` that is
  next. A new idea goes on its "Not now" list, never straight into the code.
- **The app suggests; the reader decides.** No source, topic, subtopic or
  follow is ever added without the reader's tap.
- **No paid AI by default, and no API key.** A local embedding model does the
  understanding. Anything that needs a paid model is optional, priced and off
  by default.
- **Keep the form of social apps, never their hooks.** Large, image-led, fast
  to scan. No autoplay timers, no feed that loads more as you reach the end
  (a **Show more** button instead), no notifications nobody asked for, and a
  clear "You're all caught up" as a place to stop.
- **The ranking never learns from behaviour.** Time spent, dwell and
  scroll-past are never read. Like and dislike are allowed only because they
  are explicit and they teach *one topic* what it means. They never reorder
  the feed by popularity.
- **No services that might start charging.** Nothing the app needs may depend
  on a free tier someone else controls. This rules out news APIs and web
  search APIs for now (`LESSONS.md` has why).
- **Every source must work from the server.** Sites that block cloud IPs
  (Substack is the known one) are reported as unreachable, never offered as
  though they work.
- **Every row belongs to a user from the first day**, even while there is one
  user, so accounts later change only who is signed in, not the schema.
- **Measure thresholds, do not guess them.** When a similarity cut-off is set,
  record what it was measured on and the result, next to the constant. An
  unmeasured value is marked unmeasured.

## Working here

- **Start from the latest `main`, every time.** Other agents and sessions
  merge into `main` while you work, so before writing anything run
  `git fetch origin main` and bring your branch up to date with
  `git pull --rebase origin main`; a new branch starts from `origin/main`.
  Rebase again right before merging, run the tests on the result, and only
  then merge. Never rebase `main` itself or a branch someone else pushed; on
  your own branch, push a rebase with `--force-with-lease`, never `--force`.
- **Branch, test, push, merge.** When work is finished and tests pass, commit
  on a branch, push it, merge into `main` with `--no-ff` ("Merge … into
  main"), and push `main`.
- **`PLAN.md` is a to-do list, not a journal.** When a step is built, delete
  it; history is in git. A decision worth keeping goes in this file or in the
  docstring of the code it is about.
- **Two folders, one repository**: `api/` (Python) and `web/` (React with
  Vite). They talk only through JSON, so either can be replaced.

## Tests

- No test touches the network. HTTP is mocked.
- **Never load the real embedding model in a test.** Patch the embedding
  function to return fixed unit vectors, so every similarity is exact and
  every assertion about matching is deterministic.
- Keep the page's logic (what a topic holds, what counts as new) in pure
  functions, so it is testable without a browser.
- **For layout, take a screenshot** at 390×844 with touch emulated. The page
  is built for a phone first.

## Commands

None yet. Add each one here as it is created.
