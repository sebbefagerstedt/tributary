"""Configuration loading.

Resolution order for the config file: an explicit path, then ``$TRIBUTARY_CONFIG``,
then ``./config.toml``, then the per-user config dir.
"""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_path, user_data_path

APP = "tributary"


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


@dataclass(slots=True)
class Config:
    db_path: Path
    sources: list[SourceConfig] = field(default_factory=list)
    triage: TriageConfig = field(default_factory=TriageConfig)
    path: Path | None = None  # where this config was loaded from, for diagnostics


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
    return Config(db_path=resolved, sources=sources, triage=triage, path=path)
