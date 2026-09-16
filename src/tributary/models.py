"""The normalised shape every source adapter produces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Final


class Kind:
    """Item kinds. Everything downstream is kind-agnostic except rendering."""

    ARTICLE: Final = "article"
    VIDEO: Final = "video"
    PAPER: Final = "paper"
    MODEL: Final = "model"
    REPO: Final = "repo"
    DISCUSSION: Final = "discussion"
    POST: Final = "post"

    ALL: Final = frozenset({ARTICLE, VIDEO, PAPER, MODEL, REPO, DISCUSSION, POST})


@dataclass(slots=True)
class RawItem:
    """One fetched atom, before triage/enrichment.

    ``external_id`` must be stable within its source: it is half of the
    uniqueness key that makes re-fetching idempotent.
    """

    external_id: str
    kind: str
    url: str
    title: str
    author: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    body: str | None = None
    media_url: str | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in Kind.ALL:
            raise ValueError(f"unknown item kind: {self.kind!r}")
        if not self.external_id:
            raise ValueError("external_id is required and must be stable within the source")
