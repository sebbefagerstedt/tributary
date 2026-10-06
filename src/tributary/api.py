"""HTTP API and the web app it serves.

The app is the React page in `web-next/` (VISION.md), built into
`web-next/dist` and served at the root. It reads the same bundle the static
export writes (`/data.json`), and, finding this server, keeps profiles and
topics here and searches for sources (`/api/next/...`).

Meant to run on your own machine and be reached from a phone over Tailscale.
There is no authentication, so do not bind it to a public interface.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from tributary import config as config_mod
from tributary import db as db_mod
from tributary import export as export_mod
from tributary import readers, suggest, triage

APP_DIR = export_mod.APP_DIR

_NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Tributary</title>
<body style="font:16px system-ui;max-width:34em;margin:3em auto;padding:0 1em">
<h1>The page is not built yet</h1>
<p>From the repository: <code>cd web-next &amp;&amp; npm ci &amp;&amp; npm run build</code>,
then reload. The API is running: <a href="/api/docs">/api/docs</a>.</p>"""


def create_app(config_path: Path | None = None) -> FastAPI:
    state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cfg = config_mod.load(config_path)
        # Sync handlers run in a threadpool and SQLite connections are not
        # shareable across threads, so each worker thread gets its own.
        pool = db_mod.ConnectionPool(cfg.db_path)
        db_mod.migrate(pool.get())
        state["pool"] = pool
        state["config"] = cfg
        yield
        pool.close()

    app = FastAPI(title="Tributary", lifespan=lifespan, docs_url="/api/docs")

    def conn() -> sqlite3.Connection:
        return state["pool"].get()

    @app.get("/data.json")
    def data_bundle(
        limit: int = Query(export_mod.DEFAULT_LIMIT, ge=0),
        days: int | None = Query(export_mod.DEFAULT_DAYS, ge=1, le=365),
    ) -> JSONResponse:
        """The same bundle the static export writes.

        Serving it here means the page has one code path: it always reads a
        bundle, whether a server built it just now or a scheduled job wrote it
        to disk hours ago.
        """
        return JSONResponse(
            export_mod.build_bundle(
                conn(),
                limit=limit,
                days=days,
                facet_names=state["config"].facets,
                spine=state["config"].topics.spine,
                keep_days_for=state["config"].topics.keep_days_for,
                keep_most_for=state["config"].topics.keep_most_for,
            )
        )

    @app.get("/api/status")
    def status() -> JSONResponse:
        counts = triage.stats(conn())
        stories = conn().execute("SELECT COUNT(*) c FROM stories").fetchone()["c"]
        newest = conn().execute(
            "SELECT MAX(COALESCE(published_at, fetched_at)) m FROM items"
        ).fetchone()["m"]
        broken = [
            {"name": r["name"], "error": r["last_error"]}
            for r in conn().execute(
                "SELECT name, last_error FROM sources WHERE enabled = 1 AND last_error IS NOT NULL"
            )
        ]
        return JSONResponse(
            {"stories": stories, "newest_item": newest, "broken_sources": broken, **counts}
        )

    # --- The redesign's API (VISION.md, NEXT.md step 2) ----------------------
    # Profiles are names with no password, and this server has no
    # authentication: run it on your own machine, never on a public interface.

    def _embed(texts):
        from tributary import embeddings  # loads the model only when needed

        return embeddings.embed(texts)

    def _reader(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except readers.ReaderError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/next/ping")
    def next_ping() -> JSONResponse:
        return JSONResponse({"ok": True})

    @app.get("/api/next/profiles")
    def next_profiles() -> JSONResponse:
        return JSONResponse({"profiles": readers.list_profiles(conn())})

    @app.post("/api/next/profiles")
    def next_create_profile(body: dict = Body(...)) -> JSONResponse:  # noqa: B008
        _reader(readers.ensure_profile, conn(), body.get("name", ""))
        return JSONResponse(readers.get_profile(conn(), body["name"].strip()[: readers.MAX_NAME]))

    @app.get("/api/next/profiles/{name}")
    def next_profile(name: str) -> JSONResponse:
        return JSONResponse(_reader(readers.get_profile, conn(), name))

    @app.patch("/api/next/profiles/{name}")
    def next_update_profile(name: str, body: dict = Body(...)) -> JSONResponse:  # noqa: B008
        _reader(readers.update_profile, conn(), name,
                layout=body.get("layout"), onboarded=body.get("onboarded"))
        return JSONResponse(readers.get_profile(conn(), name))

    @app.post("/api/next/profiles/{name}/reset")
    def next_reset(name: str) -> JSONResponse:
        _reader(readers.reset_profile, conn(), name)
        return JSONResponse(readers.get_profile(conn(), name))

    @app.put("/api/next/profiles/{name}/topics/{key}")
    def next_save_topic(name: str, key: str, body: dict = Body(...)) -> JSONResponse:  # noqa: B008
        topic = _reader(readers.save_topic, conn(), name, {**body, "id": key}, embed=_embed)
        return JSONResponse(topic)

    @app.delete("/api/next/profiles/{name}/topics/{key}")
    def next_delete_topic(name: str, key: str) -> JSONResponse:
        _reader(readers.delete_topic, conn(), name, key)
        return JSONResponse({"ok": True})

    @app.post("/api/next/profiles/{name}/seen")
    def next_seen(name: str, body: dict = Body(...)) -> JSONResponse:  # noqa: B008
        _reader(readers.mark_seen, conn(), name, body.get("story_ids", []))
        return JSONResponse({"ok": True})

    @app.get("/api/next/discover")
    def next_discover(q: str = Query(..., min_length=2, max_length=200)) -> JSONResponse:
        """Sources for a pasted site (found and previewed live) or a subject."""
        if suggest.looks_like_site(q):
            return JSONResponse(suggest.for_site(conn(), q))
        return JSONResponse(suggest.for_subject(conn(), q, _embed))

    # Refresh: after a reader adds sources, fetch and process them now instead
    # of waiting for the next scheduled run. One at a time, in the background,
    # as the same `trib run` the schedule uses.
    refresh: dict = {"running": False, "finished_at": None, "ok": None}
    refresh_lock = threading.Lock()

    def _run_pipeline() -> None:
        cmd = [sys.executable, "-m", "tributary.cli", "run"]
        if state["config"].path:
            cmd += ["--config", str(state["config"].path)]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
            refresh["ok"] = done.returncode == 0
        except (OSError, subprocess.SubprocessError):
            refresh["ok"] = False
        finally:
            refresh["finished_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            refresh["running"] = False

    @app.post("/api/next/refresh")
    def next_refresh() -> JSONResponse:
        with refresh_lock:
            if not refresh["running"]:
                refresh["running"] = True
                threading.Thread(target=_run_pipeline, daemon=True).start()
        return JSONResponse(refresh)

    @app.get("/api/next/refresh")
    def next_refresh_status() -> JSONResponse:
        return JSONResponse(refresh)

    # The page lived at /next/ while version 1 held the root; old links land.
    @app.get("/next", include_in_schema=False)
    @app.get("/next/", include_in_schema=False)
    def next_moved() -> RedirectResponse:
        return RedirectResponse("/", status_code=301)

    # The page. Mounted last so /api/* and /data.json win on any name clash.
    if APP_DIR.is_dir():
        app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="app")
    else:
        @app.get("/", include_in_schema=False)
        def not_built() -> HTMLResponse:
            return HTMLResponse(_NOT_BUILT)

    return app
