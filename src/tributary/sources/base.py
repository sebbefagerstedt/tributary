"""Source adapter interface and registry.

An adapter turns one configured source into ``RawItem``s. It owns its own
fetch state (ETags, cursors, high-water marks) but never touches the database:
persistence is the store's job, which keeps adapters trivially testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from tributary.config import SourceConfig
from tributary.models import RawItem

REGISTRY: dict[str, type[Source]] = {}


def register(cls: type[Source]) -> type[Source]:
    REGISTRY[cls.kind] = cls
    return cls


class FetchError(RuntimeError):
    """A source failed to fetch. Recorded against the source, never fatal to a run."""


class Source(ABC):
    kind: ClassVar[str]

    def __init__(self, config: SourceConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        """Return newly fetched items and the state to persist for next time.

        Returning an empty list is normal (nothing new since last poll) and is
        not an error. Raise ``FetchError`` for genuine failures, describing only
        what went wrong: the message is recorded against this source's row, so
        naming the source in it would just read back twice.
        """


def build(config: SourceConfig) -> Source:
    try:
        cls = REGISTRY[config.kind]
    except KeyError:
        raise ValueError(
            f"unknown source kind {config.kind!r} (known: {sorted(REGISTRY)})"
        ) from None
    return cls(config)
