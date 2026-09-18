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
        floor = 0.71
        park_margin = 0.05

        [[topics.spine]]
        slug = "agents"
        name = "Agents & tools"
        description = "agents, tool use and the protocols between them"
        """,
    )
    cfg = config_mod.load(path)
    assert cfg.topics.floor == 0.71
    assert cfg.topics.park_margin == 0.05
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


def test_a_topic_can_sit_under_another(tmp_path):
    path = write(
        tmp_path,
        """
        [[topics.spine]]
        slug = "models"
        name = "AI models"
        description = "a model is released"

        [[topics.spine]]
        slug = "frontier"
        parent = "models"
        name = "Frontier models"
        description = "the largest models from the leading labs"
        """,
    )
    spine = {t.slug: t for t in config_mod.load(path).topics.spine}
    assert spine["frontier"].parent == "models"
    assert spine["models"].parent is None


def test_a_parent_that_does_not_exist_is_rejected(tmp_path):
    """Otherwise the shelf silently vanishes and its children look top-level."""
    path = write(
        tmp_path,
        """
        [[topics.spine]]
        slug = "frontier"
        parent = "typo"
        name = "Frontier"
        description = "big models"
        """,
    )
    with pytest.raises(ValueError, match="unknown parent"):
        config_mod.load(path)


def test_a_topic_cannot_be_its_own_parent(tmp_path):
    path = write(
        tmp_path,
        """
        [[topics.spine]]
        slug = "loop"
        parent = "loop"
        name = "Loop"
        description = "round and round"
        """,
    )
    with pytest.raises(ValueError, match="its own parent"):
        config_mod.load(path)


# --- facets and entities -----------------------------------------------------

def test_loads_facets_and_entities(tmp_path):
    path = write(
        tmp_path,
        """
        [[facets]]
        slug = "agents"
        name = "Agents"
        pattern = "\\\\bagent"

        [[entities]]
        kind = "org"
        name = "OpenAI"
        aliases = ["Open AI"]
        """,
    )
    cfg = config_mod.load(path)
    assert cfg.facets[0].pattern == r"\bagent"
    assert cfg.entities[0].names() == ["OpenAI", "Open AI"]


def test_a_facet_with_a_broken_pattern_is_rejected_at_load(tmp_path):
    """Better at load than as a crash halfway through labelling the corpus."""
    path = write(
        tmp_path,
        """
        [[facets]]
        slug = "bad"
        name = "Bad"
        pattern = "(unclosed"
        """,
    )
    with pytest.raises(ValueError, match="bad pattern"):
        config_mod.load(path)


def test_an_entity_of_an_unknown_kind_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
        [[entities]]
        kind = "company"
        name = "OpenAI"
        """,
    )
    with pytest.raises(ValueError, match="unknown kind"):
        config_mod.load(path)


def test_only_topics_nothing_sits_under_are_leaves():
    shelf = config_mod.TopicConfig("models", "Models", "about models")
    leaf = config_mod.TopicConfig("frontier", "Frontier", "about frontier", parent="models")
    alone = config_mod.TopicConfig("policy", "Policy", "about policy")
    spine = config_mod.TopicsConfig(spine=[shelf, leaf, alone])

    assert [t.slug for t in spine.leaves()] == ["frontier", "policy"]


def test_changing_a_facet_or_an_entity_changes_the_label_fingerprint(tmp_path):
    """All three axes are matched in one pass, so any of them re-runs all of it."""
    base = config_mod.Config(db_path=tmp_path / "x.db")
    faceted = config_mod.Config(
        db_path=tmp_path / "x.db",
        facets=[config_mod.FacetConfig("agents", "Agents", r"\bagent")],
    )
    named = config_mod.Config(
        db_path=tmp_path / "x.db",
        entities=[config_mod.EntityConfig("org", "OpenAI")],
    )

    assert len({base.label_fingerprint(), faceted.label_fingerprint(),
                named.label_fingerprint()}) == 3
