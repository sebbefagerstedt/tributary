# Tributary — the redesign

The new frontend, built to the approved mockup (`../docs/mockup/index.html`) and
the spec in `../VISION.md`. React and Vite; it reads the bundle the pipeline
publishes (`data.json`) and keeps each profile's topics in the browser until the
backend exists.

```bash
cd web-next
npm install
uv run python scripts/make_dev_data.py   # from the repo root: a sample bundle
npm run dev                              # http://localhost:5173
npm test                                 # the logic: topics, new, catalogue
npm run build                            # what the workflow publishes at /next/
```

Live at https://sebbefagerstedt.github.io/tributary/next/ after each run of the
workflow.

What it is today, and what waits for the backend:

- **Profiles are names**, kept on the device; topics, seen stories and the
  layout belong to a profile.
- **Starter subjects are the spine's shelves**, and the sources a topic is
  offered are the ones the pipeline already reads that put stories there. Real
  suggestions — any subject, any site — arrive with the backend (`../NEXT.md`).
- **A story is in a topic** when it lives on the topic's shelf, came from one of
  its sources, and mentions none of its muted words; it can sit in several
  topics and is read once.
