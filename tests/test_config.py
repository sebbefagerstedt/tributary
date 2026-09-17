from __future__ import annotations

from pathlib import Path

import pytest

from tributary import config as config_mod


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body)
    return path


def test_loads_sources(tmp_path):
    path = write(
        tmp_path,
        """
        [tributary]
        db_path = "/tmp/x.db"

        [[sources]]
        kind = "rss"
        name = "Feed"
        url = "https://e.test/f"
        """,
    )
    cfg = config_mod.load(path)
    assert cfg.db_path == Path("/tmp/x.db")
    assert len(cfg.sources) == 1
    assert cfg.sources[0].name == "Feed"
    assert cfg.sources[0].enabled is True


def test_unknown_keys_pass_through_as_adapter_options(tmp_path):
    path = write(
        tmp_path,
        """
        [[sources]]
        kind = "reddit"
        name = "r/LocalLLaMA"
        subreddit = "LocalLLaMA"
        min_score = 50
        """,
    )
    cfg = config_mod.load(path)
    assert cfg.sources[0].options == {"subreddit": "LocalLLaMA", "min_score": 50}


def test_missing_required_key_names_the_offending_entry(tmp_path):
    path = write(tmp_path, '[[sources]]\nname = "No kind"\n')
    with pytest.raises(ValueError, match="missing \\['kind'\\]"):
        config_mod.load(path)


def test_db_path_expands_user(tmp_path):
    path = write(tmp_path, '[tributary]\ndb_path = "~/db.sqlite"\n')
    assert config_mod.load(path).db_path == Path.home() / "db.sqlite"


def test_explicit_missing_path_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        config_mod.load(tmp_path / "nope.toml")


def test_no_config_anywhere_yields_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TRIBUTARY_CONFIG", raising=False)
    monkeypatch.setattr(config_mod, "user_config_path", lambda _: tmp_path / "absent")
    cfg = config_mod.load()
    assert cfg.sources == []
    assert cfg.db_path == config_mod.default_db_path()


def test_relative_db_path_is_relative_to_the_config_not_the_cwd(tmp_path, monkeypatch):
    """A cron entry has no useful working directory; the config's own location does."""
    project = tmp_path / "project"
    project.mkdir()
    config = project / "config.toml"
    config.write_text('[tributary]\ndb_path = "./tributary.db"\n')

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert config_mod.load(config).db_path == project / "tributary.db"


def test_absolute_db_path_is_left_alone(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[tributary]\ndb_path = "/var/data/t.db"\n')
    assert config_mod.load(config).db_path == Path("/var/data/t.db")


def test_loads_a_topic_spine(tmp_path):
    path = write(
        tmp_path,
        """
        [tributary]
        db_path = "/tmp/x.db"

        [topics]
        threshold = 0.71
        max_per_story = 2

        [[topics.spine]]
        slug = "agents"
        name = "Agents & tools"
        description = "agents, tool use and the protocols between them"
        """,
    )
    cfg = config_mod.load(path)
    assert cfg.topics.threshold == 0.71
    assert cfg.topics.max_per_story == 2
    assert cfg.topics.spine[0].slug == "agents"


def test_a_topic_missing_its_description_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
        [[topics.spine]]
        slug = "agents"
        name = "Agents"
        """,
    )
    with pytest.raises(ValueError, match="topic entry missing"):
        config_mod.load(path)


def test_no_topics_section_is_fine(tmp_path):
    """Topics are optional; the feed works without a spine."""
    cfg = config_mod.load(write(tmp_path, '[tributary]\ndb_path = "/tmp/x.db"\n'))
    assert cfg.topics.spine == []
