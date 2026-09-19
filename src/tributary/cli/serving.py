"""Putting the feed where a phone can reach it."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from tributary import export as export_mod
from tributary.cli.common import ConfigOpt, app, console, open_config

PANEL = "Publishing"


@app.command(rich_help_panel=PANEL, name="export")
def export_cmd(
    out: Annotated[Path, typer.Argument(help="Directory to write the static site into.")],
    config: ConfigOpt = None,
    limit: Annotated[int, typer.Option("--limit", "-n")] = export_mod.DEFAULT_LIMIT,
    days: Annotated[
        int | None, typer.Option("--days", "-d", help="Only stories active in the last N days.")
    ] = export_mod.DEFAULT_DAYS,
) -> None:
    """Write a static site that needs no server. For GitHub Pages and friends."""
    cfg, conn = open_config(config)
    result = export_mod.write_site(
        conn, out, limit=limit, days=days, facet_names=cfg.facets, spine=cfg.topics.spine
    )
    size = result["bytes"] / 1024
    console.print(
        f"[green]Wrote {result['stories']} stories[/] to {result['path']} "
        f"([dim]data.json {size:.0f} KB[/])"
    )


@app.command(rich_help_panel=PANEL)
def serve(
    config: ConfigOpt = None,
    host: Annotated[
        str, typer.Option("--host", help="Interface to bind. 0.0.0.0 to reach it from a phone.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", "-p")] = 8808,
    reload: Annotated[bool, typer.Option("--reload", help="Restart on code changes.")] = False,
) -> None:
    """Serve the web app.

    There is no authentication: this is meant to run on your own machine and be
    reached from a phone over Tailscale, not exposed to the internet.
    """
    import os

    import uvicorn

    # create_app() is built by uvicorn (possibly in a reloaded subprocess), so
    # the config path has to travel through the environment rather than a closure.
    if config:
        os.environ["TRIBUTARY_CONFIG"] = str(config.resolve())

    console.print(f"[green]Tributary[/] on [bold]http://{host}:{port}[/]")
    if host in ("0.0.0.0", "::"):
        addresses = _local_addresses()
        for address in addresses:
            console.print(f"  [dim]from your phone:[/] http://{address}:{port}")
        console.print(
            "  [yellow]No authentication[/] — keep this on a trusted network or Tailscale."
        )

    uvicorn.run(
        "tributary.api:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="warning",
    )


def _local_addresses() -> list[str]:
    """Addresses this machine can be reached on, Tailscale ones first."""
    import socket

    found = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in found and not address.startswith("127."):
                found.append(address)
    except OSError:
        pass
    # Tailscale hands out 100.64.0.0/10; that is the one worth reaching from a phone.
    return sorted(found, key=lambda a: not a.startswith("100."))
