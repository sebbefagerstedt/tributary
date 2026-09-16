"""Source adapters. Importing this package registers every built-in adapter."""

from tributary.sources import arxiv, github, hn, huggingface, rss  # noqa: F401
from tributary.sources.base import REGISTRY, FetchError, Source, build, register

__all__ = ["REGISTRY", "FetchError", "Source", "build", "register"]
