# Tributary — the redesign

The new frontend, built to the approved mockup (`../docs/mockup/index.html`) and
the spec in `../VISION.md`. React and Vite; it reads the bundle the pipeline
publishes (`data.json`). On GitHub Pages it keeps each profile in the browser;
served by `trib serve` it keeps them on the server and searches for real.

```bash
cd web-next
npm install
uv run python scripts/make_dev_data.py   # from the repo root: a sample bundle
npm run dev                              # http://localhost:5173
npm test                                 # the logic: topics, new, catalogue
npm run build                            # what trib serve and the workflow publish
```

Live at https://sebbefagerstedt.github.io/tributary/ after each run of the
workflow (`/next/`, where it lived beside version 1, redirects there).

## On your computer, with the backend

```bash
git pull && uv sync
cd web-next && npm ci && npm run build && cd ..   # trib serve serves web-next/dist
uv run trib run                                   # fill the database once
uv run trib serve --host 0.0.0.0                  # then open http://<computer>:8808/
```

A phone on the same Wi-Fi reaches it at the computer's address; anywhere else
needs a tunnel (Tailscale is free). There is no password, so do not expose it to
the internet. The page asks `./api/next/ping` when it loads: if the server
answers, profiles, topics and what you have read live in the database, and every
device that opens it sees the same ones.

What the server adds:

- **Any subject, or a pasted site**, when you create a topic or add sources in
  its settings. A site is searched for its feed (`trib sources --suggest`) and
  previewed live; a subject ranks the sources already read by how many recent
  stories of theirs fit it.
- **New sources are fetched at once.** Saving a topic with a source the server
  has never read starts one pipeline run in the background; the page reloads
  the news when it finishes. After that it is fetched with everything else, for
  as long as some topic uses it.
- **A topic of your own** — one that is not a starter subject — has its
  description embedded, so it catches stories that fit without naming it. If
  the model cannot load, the topic is still saved and matches by its words.

## What a topic holds

- **Profiles are names**, with no password; topics, seen stories and the
  layout belong to a profile.
- **Starter subjects are the spine's shelves**, and the sources a topic is
  offered are the ones the pipeline already reads that put stories there.
- **A story is in a topic** when it fits it, came from one of its sources, and
  mentions none of its muted words; it can sit in several topics and is read
  once. A starter topic fits a story on its shelf; a topic of your own fits a
  story that names it, or whose vector is near its description
  (`FIT_FLOOR`, unmeasured).
