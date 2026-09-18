"""What every command shares: the app, the consoles, and opening a config."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from tributary import config as config_mod
from tributary import db as db_mod

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Tributary — a personal AI-news feed. Many sources, one river.",
)
console = Console()
err = Console(stderr=True)

ConfigOpt = Annotated[
    Path | None, typer.Option("--config", "-c", help="Path to config.toml.")
]


def open_config(config_path: Path | None):
    """Load the config and bring its database up to date."""
    cfg = config_mod.load(config_path)
    conn = db_mod.connect(cfg.db_path)
    db_mod.migrate(conn)
    return cfg, conn
