I can't write to files here, so here's the handoff in full — save it to `~/.claude/plans/hi-fluffy-peacock.md` (append to the existing plan) or `NEXT.md` in the project.

---

# Tributary — state and remaining work

## Done

| Phase | Status |
|---|---|
| 0 — schema, config, fetch pipeline, RSS, CLI | complete |
| 1 — HN/arXiv/HF/GitHub adapters, local embeddings, triage gate | complete |
| 2 — identifier extraction, 3-tier clustering, calibration, feed ranking | complete |
| 3 — FastAPI, web app, PWA, `trib serve` | complete, endpoints verified live |

165 tests passing, lint clean. Zero LLM/API usage — everything local and free.

## In progress: GitHub Pages static hosting

**Written already:** `src/tributary/export.py` — has `build_bundle()` and `write_site()`, passes lint, **not yet tested or wired into the CLI.**

Remaining steps, in order:

1. **`api.py`** — add a `/data.json` route returning `build_bundle()` live, so server and static serve the identical shape.
2. **`web/index.html`** — switch from `/api/feed` + `/api/status` + `/api/story/<id>` to a single `./data.json` fetch. Filter feed/unseen/saved client-side from the bundle. Actions write to `localStorage`; POST to the server only when one responds.
3. **`store.py` + CLI** — `trib prune --days 60`, deleting old items and their orphaned stories.
4. **CLI** — `trib export <dir>` and `trib prune`.
5. **Tests** — export bundle shape, prune behaviour.
6. **`git init`** + `.github/workflows/update.yml`.
7. **README** section.

### Design decisions already made (don't re-derive)

- **One `data.json`, not per-story files.** 2,236 story files would be absurd; 80 stories with items embedded is ~300–500KB and one request.
- **`localStorage` is the UI's source of truth** for seen/saved/dismissed — correct for a single-user tool, and it's what makes the static build fully functional. Server POST stays as best-effort sync so the CLI's `--unseen` keeps working.
- **The database goes in the Actions cache, NOT committed.** 4MB × hourly commits would balloon the repo — git stores binary in full each time. Use `actions/cache` with `restore-keys` prefix fallback; a daily cron keeps it warm. Cache miss is self-healing (re-fetch, re-embed, slower but recovers). If eviction becomes a problem, fall back to a `data` orphan branch with force-push.
- **Deploy via `actions/upload-pages-artifact` + `actions/deploy-pages`** — nothing gets committed to the repo at all.
- **`.nojekyll` is required** or Pages mangles underscore-prefixed files. `write_site()` already emits it.
- Cache the fastembed model too (~130MB per run otherwise).

### Constraints to remember

- **YouTube transcripts will not work on Pages.** Actions runners are cloud IPs and YouTube blocks them. Phase 4 needs a residential connection — a Pi at home, pushing to the same repo.
- Free-tier Pages means a public feed. Content is public news anyway; saves stay in `localStorage`. Private repo + Pages needs GitHub Pro (~$4/mo).

## Later phases

- **4** — YouTube/podcast transcripts, claim extraction, timestamp deep-links. The differentiated feature. First place a model earns its cost (Claude API, or local via Ollama).
- **5** — notes/takes layer, follows, interaction-learned ranking, "catch me up" digest.
- **6+** — Reddit (needs a manual API approval ticket; self-service registration closed late 2025), podcasts, multi-user.

## Calibrated values — measured, don't guess these again

```
cluster.MERGE_THRESHOLD = 0.92    # 85/87 positives, 1 false merge in 18,235 hard pairs
cluster.AMBIGUOUS_LOW   = 0.86
cluster.WINDOW_DAYS     = 14
triage threshold        = 0.66
```

bge puts *unrelated* text near 0.5, so the usable similarity range is ~0.5–1.0. Positive and hard-negative distributions genuinely overlap (matches as low as 0.888; different same-week papers up to 0.944) — 0.92 honours "a wrong merge costs more than a missed link". Re-run `trib calibrate` as the corpus grows.

## Known debt

- `cli.py` is 812 lines — by far the largest file, and the first thing to split.
- Not a git repository yet.
- UI never visually verified — blocked on sudo-installed browser libs: `libnspr4 libnss3 libasound2t64 libatk-bridge2.0-0 libatspi2.0-0 libgbm1 libxkbcommon0`.
- Cross-source joins are sparse because the corpus is an archive backfill, not a live week. Run daily for a week and this changes.
- `trib status` (db path, size, counts, last fetch) — suggested, not built.
- Cron in WSL works (`systemd=true`, `cron.service` enabled); a Windows Task Scheduler entry running `wsl.exe -e <path>/trib run` would cover post-reboot.

## Current setup

Database moved to `./tributary.db` in the project (3,226 items, 2,239 stories, 14MB). Relative `db_path` now resolves against `config.toml`, not the cwd — so `trib` works from cron or any directory.