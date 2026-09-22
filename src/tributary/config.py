"""Configuration loading.

Resolution order for the config file: an explicit path, then ``$TRIBUTARY_CONFIG``,
then ``./config.toml``, then the per-user config dir.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP = "tributary"

# Mirrors the `kind` column on `entities`, which has carried this list since the
# first migration.
ENTITY_KINDS = frozenset({"model", "org", "person", "tool", "paper", "dataset"})


@dataclass(slots=True)
class SourceConfig:
    kind: str
    name: str
    url: str | None = None
    enabled: bool = True
    options: dict = field(default_factory=dict)


DEFAULT_THRESHOLD = 0.62


@dataclass(slots=True)
class TriageConfig:
    """What counts as relevant.

    ``interests`` and ``exclude`` are prose, embedded and compared against each
    item. Keyword lists are escape hatches for the cases similarity gets wrong.
    """

    threshold: float = DEFAULT_THRESHOLD
    interests: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    always_keep: list[str] = field(default_factory=list)
    always_drop: list[str] = field(default_factory=list)

    def fingerprint(self) -> str:
        """Identity of this profile, so a change can trigger a re-triage."""
        payload = json.dumps(
            {
                "threshold": self.threshold,
                "interests": sorted(self.interests),
                "exclude": sorted(self.exclude),
                "always_keep": sorted(self.always_keep),
                "always_drop": sorted(self.always_drop),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# A story goes to the topic that fits it best, so there is no threshold to tune.
# The floor only catches stories the spine has no opinion about at all; it sits
# far below where real scores land (p01 is 0.59 over the whole corpus).
DEFAULT_TOPIC_FLOOR = 0.55

# Two leaves on the same shelf this close means the shelf is clear and the leaf
# is not, so the story sits on the shelf instead of being forced onto one of them.
DEFAULT_PARK_MARGIN = 0.02

# How a topic's `claims` is compiled. Verbose, so a pattern long enough to need
# it can be laid out and commented in config.toml: whitespace is ignored, and a
# space that should match is written \s.
CLAIMS_FLAGS = re.IGNORECASE | re.VERBOSE


@dataclass(slots=True)
class TopicConfig:
    slug: str
    name: str
    description: str
    # The slug this sits under, if any. One level only: browsing wants a shelf
    # and a row, not a tree to get lost in.
    parent: str | None = None
    # A regex over a story's headline that makes this leaf its home outright,
    # before anything is scored. For a subject that names itself: a launch post
    # is mostly benchmarks and pricing, so its prose scores against whatever
    # those resemble, while its title says exactly what it is.
    claims: str | None = None


@dataclass(slots=True)
class FacetConfig:
    """A property a story has, rather than a place it lives.

    Matched by regex because that is what works: "agents" is a word that appears
    or does not, and looking for it finds five times what scoring a description
    against an embedding does. Facets stack on top of a topic as filters.
    """

    slug: str
    name: str
    pattern: str


@dataclass(slots=True)
class EntityConfig:
    """Someone or something a story is about: a lab, a model line, a tool.

    Seeded here for the ones worth having on day one; the rest arrive by
    extraction and are accepted by hand. Matching is by name and alias, never by
    similarity -- proper nouns do not need a model to recognise.
    """

    kind: str  # model|org|person|tool|paper|dataset
    name: str
    aliases: list[str] = field(default_factory=list)

    def names(self) -> list[str]:
        return [self.name, *self.aliases]


@dataclass(slots=True)
class TopicsConfig:
    """Where a story lives: exactly one place, chosen by best fit.

    `description` is a sentence describing the kind of story that belongs here,
    not a list of search terms -- it is embedded and compared, the same way
    triage works. Only leaves are scored; a shelf earns its stories from
    whichever of its leaves wins, which is why a shelf's description is
    documentation rather than an input.
    """

    floor: float = DEFAULT_TOPIC_FLOOR
    park_margin: float = DEFAULT_PARK_MARGIN
    spine: list[TopicConfig] = field(default_factory=list)

    def leaves(self) -> list[TopicConfig]:
        """The topics that get scored: everything nothing else sits under."""
        shelves = {t.parent for t in self.spine if t.parent}
        return [t for t in self.spine if t.slug not in shelves]

    def fingerprint(self) -> str:
        """Identity of this spine, so a change can trigger re-assignment."""
        payload = json.dumps(
            {
                "floor": self.floor,
                "park_margin": self.park_margin,
                "spine": sorted(
                    (t.slug, t.name, t.description, t.parent or "", t.claims or "")
                    for t in self.spine
                ),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(slots=True)
class Config:
    db_path: Path
    sources: list[SourceConfig] = field(default_factory=list)
    triage: TriageConfig = field(default_factory=TriageConfig)
    topics: TopicsConfig = field(default_factory=TopicsConfig)
    facets: list[FacetConfig] = field(default_factory=list)
    entities: list[EntityConfig] = field(default_factory=list)
    path: Path | None = None  # where this config was loaded from, for diagnostics

    def label_fingerprint(self) -> str:
        """Identity of everything that labels a story.

        Facets and entities are matched in the same pass as topics, so a change
        to any of the three has to re-run all of it. One fingerprint keeps that
        honest -- the alternative is three, and three ways to be half re-labelled.
        """
        payload = json.dumps(
            {
                "topics": self.topics.fingerprint(),
                "facets": sorted((f.slug, f.name, f.pattern) for f in self.facets),
                "entities": sorted(
                    (e.kind, e.name, *sorted(e.aliases)) for e in self.entities
                ),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def default_db_path() -> Path:
    return user_data_path(APP) / "tributary.db"


def _resolve_db_path(value: str | None, config_path: Path) -> Path:
    """Where the database lives.

    A relative path is taken as relative to the config file, not the working
    directory: `db_path = "./tributary.db"` should mean "next to my config"
    whether you run trib from the project or from a cron entry with no cwd.
    """
    if not value:
        return default_db_path()
    expanded = Path(value).expanduser()
    if expanded.is_absolute():
        return expanded
    return (config_path.parent / expanded).resolve()


def candidate_paths(explicit: Path | None = None) -> list[Path]:
    if explicit:
        return [explicit]
    paths = []
    if env := os.environ.get("TRIBUTARY_CONFIG"):
        paths.append(Path(env))
    paths.append(Path.cwd() / "config.toml")
    paths.append(user_config_path(APP) / "config.toml")
    return paths


def load(explicit: Path | None = None) -> Config:
    """Load config, falling back to an empty config with defaults if none exists."""
    for candidate in candidate_paths(explicit):
        if candidate.is_file():
            return _parse(tomllib.loads(candidate.read_text()), candidate)
    if explicit:
        raise FileNotFoundError(f"config file not found: {explicit}")
    return Config(db_path=default_db_path())


def _parse(raw: dict, path: Path) -> Config:
    settings = raw.get("tributary", {})
    resolved = _resolve_db_path(settings.get("db_path"), path)

    sources = []
    for entry in raw.get("sources", []):
        known = {"kind", "name", "url", "enabled"}
        missing = {"kind", "name"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: source entry missing {sorted(missing)}: {entry!r}")
        sources.append(
            SourceConfig(
                kind=entry["kind"],
                name=entry["name"],
                url=entry.get("url"),
                enabled=entry.get("enabled", True),
                # Anything else is adapter-specific and passed through untouched.
                options={k: v for k, v in entry.items() if k not in known},
            )
        )
    raw_triage = raw.get("triage", {})
    triage = TriageConfig(
        threshold=float(raw_triage.get("threshold", DEFAULT_THRESHOLD)),
        interests=list(raw_triage.get("interests", [])),
        exclude=list(raw_triage.get("exclude", [])),
        always_keep=[k.lower() for k in raw_triage.get("always_keep", [])],
        always_drop=[k.lower() for k in raw_triage.get("always_drop", [])],
    )
    raw_topics = raw.get("topics", {})
    spine = []
    for entry in raw_topics.get("spine", []):
        missing = {"slug", "name", "description"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: topic entry missing {sorted(missing)}: {entry!r}")
        spine.append(
            TopicConfig(
                slug=entry["slug"],
                name=entry["name"],
                description=entry["description"],
                parent=entry.get("parent"),
                claims=entry.get("claims"),
            )
        )
    known = {topic.slug for topic in spine}
    shelves = {topic.parent for topic in spine if topic.parent}
    for topic in spine:
        if topic.parent and topic.parent not in known:
            raise ValueError(f"{path}: topic {topic.slug!r} has unknown parent {topic.parent!r}")
        if topic.parent == topic.slug:
            raise ValueError(f"{path}: topic {topic.slug!r} is its own parent")
        if topic.claims is not None:
            if topic.slug in shelves:
                # Only leaves are homes; a shelf is reached through them.
                raise ValueError(f"{path}: topic {topic.slug!r} is a shelf and cannot claim")
            try:
                re.compile(topic.claims, CLAIMS_FLAGS)
            except re.error as exc:
                raise ValueError(
                    f"{path}: topic {topic.slug!r} has a bad claims pattern: {exc}"
                ) from exc
    topics = TopicsConfig(
        floor=float(raw_topics.get("floor", DEFAULT_TOPIC_FLOOR)),
        park_margin=float(raw_topics.get("park_margin", DEFAULT_PARK_MARGIN)),
        spine=spine,
    )
    if not topics.leaves() and spine:
        raise ValueError(f"{path}: every topic is a parent of another; nothing to score")

    facets = []
    for entry in raw.get("facets", []):
        missing = {"slug", "name", "pattern"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: facet entry missing {sorted(missing)}: {entry!r}")
        try:
            re.compile(entry["pattern"])
        except re.error as exc:
            raise ValueError(f"{path}: facet {entry['slug']!r} has a bad pattern: {exc}") from exc
        facets.append(
            FacetConfig(slug=entry["slug"], name=entry["name"], pattern=entry["pattern"])
        )

    entities = []
    for entry in raw.get("entities", []):
        missing = {"kind", "name"} - entry.keys()
        if missing:
            raise ValueError(f"{path}: entity entry missing {sorted(missing)}: {entry!r}")
        if entry["kind"] not in ENTITY_KINDS:
            raise ValueError(
                f"{path}: entity {entry['name']!r} has unknown kind {entry['kind']!r} "
                f"(expected one of {sorted(ENTITY_KINDS)})"
            )
        entities.append(
            EntityConfig(
                kind=entry["kind"],
                name=entry["name"],
                aliases=list(entry.get("aliases", [])),
            )
        )
    return Config(
        db_path=resolved,
        sources=sources,
        triage=triage,
        topics=topics,
        facets=facets,
        entities=entities,
        path=path,
    )
