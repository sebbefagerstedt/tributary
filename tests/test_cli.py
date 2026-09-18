"""Smoke tests for the command line.

These do not test what each command computes -- the modules underneath have
their own tests for that. They test that every command is registered, parses
its options, and runs to completion against a real database, which is the part
that breaks when commands move between files.

Nothing here touches the network or loads the embedding model: commands that
need either are only checked for `--help`.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from tributary.cli import app

runner = CliRunner()


@pytest.fixture
def config(tmp_path):
    """A fresh config and database, made the way a new user would make them."""
    path = tmp_path / "config.toml"
    result = runner.invoke(app, ["init", "--config", str(path)])
    assert result.exit_code == 0, result.output
    return str(path)


def invoke(*args):
    return runner.invoke(app, list(args), catch_exceptions=False)


def command_names() -> list[str]:
    return sorted(
        c.name or c.callback.__name__.replace("_", "-") for c in app.registered_commands
    )


def test_every_command_is_registered():
    """A command that silently fails to register just disappears from `trib`."""
    assert set(command_names()) >= {
        "init", "migrate", "status", "fetch", "list", "sources", "embed", "triage",
        "explain", "enrich", "cluster", "describe", "topics", "entities",
        "calibrate", "feed", "renewal", "story", "export", "prune", "serve", "run",
    }


@pytest.mark.parametrize("name", command_names())
def test_every_command_has_help(name):
    result = invoke(name, "--help")
    assert result.exit_code == 0, result.output


def test_init_writes_a_config_that_loads(config):
    from pathlib import Path

    from tributary import config as config_mod

    cfg = config_mod.load(Path(config))
    assert cfg.sources and cfg.topics.leaves() and cfg.facets and cfg.entities


def test_init_does_not_overwrite_without_force(config):
    result = invoke("init", "--config", config)
    assert "already exists" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["migrate"],
        ["status"],
        ["list"],
        ["sources"],
        ["feed"],
        # A cache miss hands the workflow an empty database, and this runs in it.
        ["renewal"],
        ["enrich"],
        ["cluster"],
        ["calibrate"],
        ["topics", "--stats"],
        ["topics", "--suggest"],
        ["entities"],
        ["entities", "--suggest"],
        ["prune", "--yes"],
    ],
    ids=lambda args: " ".join(args),
)
def test_runs_against_an_empty_database(config, args):
    result = invoke(*args, "--config", config)
    assert result.exit_code == 0, result.output


def test_export_writes_a_site(config, tmp_path):
    out = tmp_path / "site"
    result = invoke("export", str(out), "--config", config)
    assert result.exit_code == 0, result.output
    assert (out / "index.html").exists() and (out / "data.json").exists()


def test_a_missing_story_is_an_error_not_a_crash(config):
    result = invoke("story", "999", "--config", config)
    assert result.exit_code == 1
    assert "No story" in result.output


def test_the_sample_config_is_the_real_one():
    """`trib init` hands out the config this repo actually runs on.

    The sample used to be a string inside the CLI code, and it drifted until a fresh
    install had no topics at all. If this fails, copy `config.toml` over
    `src/tributary/sample_config.toml`.
    """
    from pathlib import Path

    from tributary.cli.setup import sample_config

    repo_config = Path(__file__).parent.parent / "config.toml"
    assert sample_config() == repo_config.read_text()
