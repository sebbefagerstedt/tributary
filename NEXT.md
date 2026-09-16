# Tributary — state and remaining work

Live at **https://sebbefagerstedt.github.io/tributary/**, rebuilt at 06:00,
11:00 and 18:00 Swedish time. 184 tests passing, lint clean.
**Zero LLM/API usage — everything local and free.**

## Next up: topics, drill-down and filters

This is the gap between what exists and what was originally described. All of it
is local; none of it needs an API key (see the correction below).

1. **Topic assignment.** A stable spine (models, agents, safety, local
   inference, research, industry) *plus* emergent topics that form around
   whatever is actually happening that week. Score each story against topic
   descriptions exactly as triage scores relevance; cluster the leftovers.
   Fills the `topics` / `story_topics` tables, which exist and are empty.
2. **"More like this" on a story page.** Currently a story shows only its own
   items. Related stories on the same subject is a nearest-neighbour lookup over
   vectors already on disk — this is the "I want to keep reading" path.
3. **Filters in the UI.** Topic, kind, source, time window. `data.json` already
   carries every field these need, so this is mostly frontend.
4. **README cleanup.** It reads as a build journal of design decisions. It
   should say what the tool is and how to run it; the reasoning can move to a
   separate document or go.

**Do these as one piece of work.** "Related info on the same topic" and "the
/r/ topics I'm missing" are the same feature underneath: assign stories to
subjects once, and both the drill-down and the filters fall out of it.

### Correction worth carrying forward

Dynamic topic clustering does **not** need an LLM. It is vector clustering over
embeddings already computed and stored. The only genuinely LLM-shaped work in
this project is "why this matters" one-liners and YouTube transcript claim
extraction — both optional, neither started.

## Done

| Phase | Status |
|---|---|
| 0 — schema, config, fetch pipeline, RSS, CLI | complete |
| 1 — HN/arXiv/HF/GitHub adapters, local embeddings, triage gate | complete |
| 2 — identifier extraction, 3-tier clustering, calibration, feed ranking | complete |
| 3 — FastAPI, web app, PWA, `trib serve` | complete, verified live |
| 3.5 — static export, prune, GitHub Pages + Actions | complete, deployed |

### How the two deployments share one frontend

Every read endpoint is a slice of a database that only changes when the pipeline
runs, so the whole API collapses into one `data.json` bundle. The server serves
it live at `/data.json`; `trib export` writes the identical shape to disk. The
page cannot tell the difference. Per-device state (seen, saved, dismissed) lives
in `localStorage` — it is a preference, not data, and a static host has nowhere
else to put it.

The database is **not** committed; it lives in the Actions cache, because git
stores each version of a binary in full. A cache miss is self-healing: the run
rebuilds from the sources.

## Later phases

- **4** — YouTube/podcast transcripts, claim extraction, timestamp deep-links.
  The differentiated feature. **Will not work on GitHub Actions** — runners are
  cloud IPs and YouTube blocks them. Needs a residential connection: this
  machine, or a Pi at home pushing to the same repo.
- **5** — notes/takes layer, interaction-learned ranking, "catch me up" digest.
- **6+** — Reddit (needs a manual API approval ticket; self-service registration
  closed late 2025 — worth requesting early), podcasts, multi-user.

## Calibrated values — measured, don't guess these again

```
cluster.MERGE_THRESHOLD = 0.92    # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW   = 0.86
cluster.WINDOW_DAYS     = 14
triage threshold        = 0.66
```

bge puts *unrelated* text near 0.5, so the usable similarity range is ~0.5–1.0.
Positive and hard-negative distributions genuinely overlap (matches as low as
0.888; different same-week papers up to 0.944) — 0.92 honours "a wrong merge
costs more than a missed link". Re-run `trib calibrate` as the corpus grows.

## Known debt

- **42% of feed cards have no summary at all** — just a title. Worst for
  releases, models and HN threads (`ggml-org/llama.cpp b11003` says nothing).
  Fix by fetching the linked page's description / HF model card / release notes.
- `cli.py` is ~900 lines — by far the largest file, first thing to split.
- **Import AI returns HTTP 403 on GitHub Actions** — Substack blocks those IPs.
  Works fine locally. Either drop it from `config.toml` or accept the gap; it is
  already surfaced in the UI's broken-sources banner.
- UI never visually verified — blocked on sudo-installed browser libs:
  `libnspr4 libnss3 libasound2t64 libatk-bridge2.0-0 libatspi2.0-0 libgbm1 libxkbcommon0`.
- `trib status` (db path, size, counts, last fetch) — suggested, not built.
- Scheduled workflows are disabled after 60 days of repo inactivity (email first;
  any push resets it).

## Current setup

Database at `./tributary.db` in the project. Relative `db_path` resolves against
`config.toml`, not the cwd, so `trib` works from cron or any directory.

Cron in WSL works (`systemd=true`, `cron.service` enabled) if you ever want local
scheduling; a Windows Task Scheduler entry running `wsl.exe -e <path>/trib run`
would cover post-reboot.

## Sebastian notes

The README includes a lot of different design choices and stuff that is not
relevant anymore since it is published on pages. It needs to be cleaned up. I
realise that it is not finished, but I am missing the different topics I was
wanting in the beginning. So when I go to one link, there should be lots of
related info on the same topic. Or comments on that event, like releases of nee
models. I want latest reviews etc. The reddit /r topics is what I am missing.
Now it just a long feed. I want to continue reading if I find something
interesting. I am also missing some sort of filter, this might be related to the
/r topics I am wanting. But I would like more general filters as well. an idea is
that the filter is dynamic as well and can be based on latest happenings by
clustering events and news but that would need AI I presume which i do not want
yet since I do not have an api key
