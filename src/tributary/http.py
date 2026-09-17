"""Shared HTTP behaviour for adapters.

Conditional GET lives here rather than in each adapter: every source polls on a
schedule, and on GitHub in particular a 304 does not count against the rate
limit, so getting this right is what makes frequent polling affordable.
"""

from __future__ import annotations

from typing import Any

import httpx

USER_AGENT = "tributary/0.1 (personal news aggregator)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)

NOT_MODIFIED = 304


class FetchError(RuntimeError):
    """A fetch failed. Recorded against the source, never fatal to a run.

    Defined here rather than in ``sources.base`` because this module raises it
    and must not depend on the adapters: importing it the other way round made
    ``tributary.http`` impossible to import on its own, and it worked only
    because every caller happened to load ``tributary.sources`` first.
    ``sources.base`` re-exports it, so the adapters' import path is unchanged.
    """


def request(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    state: dict | None = None,
    timeout: httpx.Timeout = TIMEOUT,
) -> tuple[httpx.Response | None, dict]:
    """GET ``url``, sending any cached validators from ``state``.

    Returns ``(response, new_state)``; the response is ``None`` when the server
    answered 304, meaning nothing has changed since the last poll. ``new_state``
    always carries forward the validators to send next time.
    """
    state = state or {}
    merged = {"User-Agent": USER_AGENT, **(headers or {})}
    if etag := state.get("etag"):
        merged["If-None-Match"] = etag
    if modified := state.get("last_modified"):
        merged["If-Modified-Since"] = modified

    try:
        response = httpx.get(
            url, params=params, headers=merged, timeout=timeout, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        raise FetchError(str(exc)) from exc

    if response.status_code == NOT_MODIFIED:
        return None, state

    if response.status_code >= 400:
        raise FetchError(_describe_error(response, url))

    new_state = dict(state)
    if tag := response.headers.get("ETag"):
        new_state["etag"] = tag
    if modified := response.headers.get("Last-Modified"):
        new_state["last_modified"] = modified
    return response, new_state


def get_json(url: str, **kwargs: Any) -> tuple[Any | None, dict]:
    """As ``request``, decoding the body as JSON. ``None`` means 304."""
    response, state = request(url, **kwargs)
    if response is None:
        return None, state
    try:
        return response.json(), state
    except ValueError as exc:
        raise FetchError(f"invalid JSON from {url}: {exc}") from exc


def _describe_error(response: httpx.Response, url: str) -> str:
    """Turn an error response into something actionable in a health row."""
    status = response.status_code
    if status == 429 or (status == 403 and response.headers.get("X-RateLimit-Remaining") == "0"):
        reset = response.headers.get("X-RateLimit-Reset") or response.headers.get("Retry-After")
        suffix = f" (resets {reset})" if reset else ""
        return f"rate limited by {httpx.URL(url).host}{suffix}"
    return f"HTTP {status} from {url}"
