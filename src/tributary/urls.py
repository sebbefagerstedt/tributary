"""URL canonicalisation.

Used for dedup now, and as a tier-1 clustering join key later: two items that
canonicalise to the same URL are the same thing, and two items linking out to
the same canonical URL are strong evidence of the same story.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Tracking params carry no identity and would otherwise split one URL into many.
_STRIP_PREFIXES = ("utm_", "mc_", "pk_", "_hs")
_STRIP_EXACT = frozenset(
    {
        "fbclid", "gclid", "dclid", "msclkid", "igshid", "mkt_tok",
        "ref", "ref_src", "referrer", "source", "cmpid", "ncid",
        "spm", "at_medium", "at_campaign", "sh", "share", "si",
    }
)


def canonicalize(url: str) -> str:
    """Return a stable form of ``url``, or the input unchanged if unparseable."""
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.netloc:
        return url

    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.removesuffix(":80").removesuffix(":443")

    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _STRIP_EXACT and not k.lower().startswith(_STRIP_PREFIXES)
    ]
    query.sort()

    path = parts.path.rstrip("/") or "/"
    # Fragment is dropped: it never identifies a distinct document.
    return urlunsplit((scheme, host, path, urlencode(query), ""))
