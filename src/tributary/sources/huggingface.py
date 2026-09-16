"""HuggingFace models, datasets and the curated daily papers list.

Daily papers are unusually valuable for clustering: each entry already carries
the arXiv id and often the GitHub repo, so one fetch links three sources that
would otherwise have to be matched by text similarity.
"""

from __future__ import annotations

from datetime import UTC, datetime

from tributary.http import get_json
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.text import truncate

API = "https://huggingface.co/api"
SUMMARY_LIMIT = 2000
MODES = ("models", "datasets", "papers")


def _owner(repo_id: str) -> str | None:
    """The account a hub repo belongs to, e.g. 'deepseek-ai/DeepSeek-V4' -> 'deepseek-ai'."""
    return repo_id.split("/")[0] if "/" in repo_id else None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


@register
class HuggingFaceSource(Source):
    kind = "hf"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        options = self.config.options
        mode = options.get("mode", "models")
        if mode not in MODES:
            raise FetchError(f"unknown hf mode {mode!r} (expected one of {MODES})")

        limit = int(options.get("limit", 50))
        if mode == "papers":
            payload, new_state = get_json(f"{API}/daily_papers", params={"limit": limit})
            builder = self._build_paper
        else:
            payload, new_state = get_json(
                f"{API}/{mode}",
                params={
                    "sort": options.get("sort", "likes7d"),
                    "direction": -1,
                    "limit": limit,
                },
            )
            builder = self._build_model if mode == "models" else self._build_dataset

        if payload is None:
            return [], new_state
        if not isinstance(payload, list):
            raise FetchError(f"unexpected response shape from {mode}: {type(payload).__name__}")

        return [built for entry in payload if (built := builder(entry))], new_state

    def _build_model(self, entry: dict) -> RawItem | None:
        repo_id = entry.get("id") or entry.get("modelId")
        if not repo_id:
            return None
        return RawItem(
            external_id=repo_id,
            kind=Kind.MODEL,
            url=f"https://huggingface.co/{repo_id}",
            title=repo_id,
            # The list endpoint omits `author` unless full=true; the owner is
            # always the first path segment, so derive it rather than pay for
            # the heavier response.
            author=entry.get("author") or _owner(repo_id),
            published_at=_parse_time(entry.get("createdAt")),
            metadata={
                "hf_id": repo_id,
                "likes": entry.get("likes", 0),
                "downloads": entry.get("downloads", 0),
                "trending_score": entry.get("trendingScore", 0),
                "pipeline_tag": entry.get("pipeline_tag"),
                "tags": entry.get("tags", []),
                "last_modified": entry.get("lastModified"),
            },
        )

    def _build_dataset(self, entry: dict) -> RawItem | None:
        repo_id = entry.get("id")
        if not repo_id:
            return None
        return RawItem(
            external_id=f"dataset:{repo_id}",
            kind=Kind.MODEL,  # a dataset is a hub artefact; kind splits only at render time
            url=f"https://huggingface.co/datasets/{repo_id}",
            title=repo_id,
            author=entry.get("author") or _owner(repo_id),
            published_at=_parse_time(entry.get("createdAt")),
            metadata={
                "hf_dataset": repo_id,
                "likes": entry.get("likes", 0),
                "downloads": entry.get("downloads", 0),
                "tags": entry.get("tags", []),
            },
        )

    def _build_paper(self, entry: dict) -> RawItem | None:
        paper = entry.get("paper") or {}
        paper_id = paper.get("id")
        title = entry.get("title") or paper.get("title")
        if not paper_id or not title:
            return None

        return RawItem(
            external_id=paper_id,
            kind=Kind.PAPER,
            url=f"https://huggingface.co/papers/{paper_id}",
            title=title.strip(),
            published_at=_parse_time(entry.get("publishedAt") or paper.get("publishedAt")),
            summary=truncate(entry.get("summary") or paper.get("summary"), SUMMARY_LIMIT),
            media_url=entry.get("thumbnail"),
            metadata={
                # Pre-resolved cross-source links: exactly what tier-1 clustering wants.
                "arxiv_id": paper_id,
                "github_repo": paper.get("githubRepo"),
                "github_stars": paper.get("githubStars"),
                "upvotes": paper.get("upvotes", 0),
                "num_comments": entry.get("numComments", 0),
            },
        )
