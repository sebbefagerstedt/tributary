"""HTTP API and the web app it serves.

The app is a single self-contained page rather than a build-step frontend: the
UI is a vertical card list, CSS scroll-snap gives it the feel it needs, and a
bundler would become the heaviest thing in this repository for very little.
The JSON API below is the contract, so swapping the frontend later touches
nothing on this side.

Meant to run on your own machine and be reached from a phone over Tailscale.
There is no authentication, so do not bind it to a public interface.
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tributary import config as config_mod
from tributary import db as db_mod
from tributary import export as export_mod
from tributary import feed as feed_mod
from tributary import triage

WEB_DIR = Path(__file__).parent / "web"
VALID_ACTIONS = {"seen", "opened", "saved", "dismissed"}


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

    @app.get("/api/feed")
    def get_feed(
        limit: int = Query(30, ge=1, le=200),
        days: int | None = Query(None, ge=1, le=365),
        unseen: bool = False,
        diversify: bool = True,
    ) -> JSONResponse:
        cards = feed_mod.build(
            conn(), limit=limit, days=days, include_seen=not unseen, diversify_feed=diversify
        )
        return JSONResponse(
            {"stories": [_serialise(card) for card in cards], "count": len(cards)}
        )

    @app.get("/api/story/{story_id}")
    def get_story(story_id: int) -> JSONResponse:
        found = feed_mod.detail(conn(), story_id)
        if found is None:
            raise HTTPException(status_code=404, detail="no such story")
        card, members = found
        return JSONResponse(
            {
                **_serialise(card),
                "items": [
                    {
                        "id": m["id"],
                        "role": m["role"],
                        "kind": m["kind"],
                        "title": m["title"],
                        "url": m["url"],
                        "summary": m["summary"],
                        "author": m["author"],
                        "source": m["source_name"],
                        "published_at": m["published_at"],
                    }
                    for m in members
                ],
            }
        )

    @app.post("/api/story/{story_id}/{action}")
    def record(story_id: int, action: str) -> JSONResponse:
        if action not in VALID_ACTIONS:
            raise HTTPException(status_code=400, detail=f"unknown action {action!r}")
        exists = conn().execute("SELECT 1 FROM stories WHERE id = ?", (story_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="no such story")
        conn().execute(
            "INSERT INTO interactions (story_id, action) VALUES (?, ?)", (story_id, action)
        )
        return JSONResponse({"ok": True, "story_id": story_id, "action": action})

    @app.get("/api/saved")
    def saved(limit: int = Query(50, ge=1, le=200)) -> JSONResponse:
        rows = conn().execute(
            """
            SELECT DISTINCT story_id FROM interactions
             WHERE action = 'saved'
               AND story_id NOT IN (SELECT story_id FROM interactions WHERE action = 'dismissed')
             ORDER BY at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        cards = []
        for row in rows:
            found = feed_mod.detail(conn(), row["story_id"])
            if found:
                cards.append(_serialise(found[0]))
        return JSONResponse({"stories": cards, "count": len(cards)})

    @app.get("/data.json")
    def data_bundle(
        limit: int = Query(export_mod.DEFAULT_LIMIT, ge=1, le=500),
        days: int | None = Query(export_mod.DEFAULT_DAYS, ge=1, le=365),
    ) -> JSONResponse:
        """The same bundle the static export writes.

        Serving it here means the page has one code path: it always reads a
        bundle, whether a server built it just now or a scheduled job wrote it
        to disk hours ago.
        """
        return JSONResponse(export_mod.build_bundle(conn(), limit=limit, days=days))

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

    # The app shell. Mounted last so /api/* wins on any name collision.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    @app.get("/manifest.json", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(WEB_DIR / "manifest.json", media_type="application/manifest+json")

    return app


def _serialise(card: feed_mod.StoryCard) -> dict:
    data = asdict(card)
    data["signal"] = card.signal()
    return data
