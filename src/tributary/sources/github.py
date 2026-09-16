"""GitHub releases for a watchlist of repositories.

One source watches many repos, each with its own ETag: GitHub does not count
304 responses against the rate limit, so per-repo validators are what keep a
long watchlist inside the unauthenticated budget of 60 requests an hour.
Setting a token (GITHUB_TOKEN by default) raises that to 5000.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from tributary.http import get_json
from tributary.models import Kind, RawItem
from tributary.sources.base import FetchError, Source, register
from tributary.text import truncate

API = "https://api.github.com"
BODY_LIMIT = 4000
DEFAULT_PER_PAGE = 10


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


@register
class GitHubSource(Source):
    kind = "github"

    def fetch(self, state: dict) -> tuple[list[RawItem], dict]:
        options = self.config.options
        repos = options.get("repos") or []
        if not repos:
            raise FetchError("github source requires a non-empty 'repos' list")

        headers = {"Accept": "application/vnd.github+json"}
        if token := os.environ.get(options.get("token_env", "GITHUB_TOKEN")):
            headers["Authorization"] = f"Bearer {token}"

        per_page = int(options.get("per_page", DEFAULT_PER_PAGE))
        # Validators are stored per repo, since each has its own resource.
        etags: dict = dict(state.get("etags", {}))
        items: list[RawItem] = []
        failures: list[str] = []

        for repo in repos:
            try:
                payload, repo_state = get_json(
                    f"{API}/repos/{repo}/releases",
                    params={"per_page": per_page},
                    headers=headers,
                    state=etags.get(repo, {}),
                )
            except FetchError as exc:
                # One missing or renamed repo must not cost us the other releases.
                failures.append(f"{repo}: {exc}")
                continue

            etags[repo] = repo_state
            if payload is None:
                continue
            items.extend(
                built for release in payload if (built := self._build(repo, release))
            )

        if failures and not items:
            raise FetchError("; ".join(failures[:3]))
        return items, {"etags": etags, "failures": failures}

    def _build(self, repo: str, release: dict) -> RawItem | None:
        if release.get("draft"):
            return None
        tag = release.get("tag_name")
        url = release.get("html_url")
        if not tag or not url:
            return None

        name = release.get("name") or tag
        return RawItem(
            external_id=f"{repo}@{tag}",
            kind=Kind.REPO,
            url=url,
            title=f"{repo} {name}" if name != repo else name,
            author=(release.get("author") or {}).get("login"),
            published_at=_parse_time(release.get("published_at")),
            body=truncate(release.get("body"), BODY_LIMIT),
            metadata={
                "github_repo": repo,
                "tag": tag,
                "prerelease": bool(release.get("prerelease")),
            },
        )
