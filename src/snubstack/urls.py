from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES: tuple[str, ...] = ("utm_",)
TRACKING_EXACT: frozenset[str] = frozenset(
    {
        "fbclid",
        "gclid",
        "gbraid",
        "wbraid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "ref",
        "ref_src",
        "ref_url",
        "yclid",
        "igshid",
        "si",
    }
)

KNOWN_SHORTENERS: frozenset[str] = frozenset(
    {
        "bit.ly",
        "buff.ly",
        "t.co",
        "tinyurl.com",
        "ow.ly",
        "goo.gl",
        "lnkd.in",
        "dub.sh",
        "rb.gy",
        "is.gd",
        "trib.al",
    }
)


def _strip_tracking(query: str) -> str:
    kept = [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if k not in TRACKING_EXACT and not any(k.startswith(p) for p in TRACKING_PREFIXES)
    ]
    return urlencode(kept, doseq=True)


def normalize(url: str) -> tuple[str, str] | None:
    """Return (normalized_url, host) or None if the URL is unusable."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    try:
        host.encode("idna")
    except (UnicodeError, UnicodeDecodeError):
        return None
    query = _strip_tracking(parts.query)
    normalized = urlunsplit((parts.scheme, host, parts.path or "/", query, ""))
    return normalized, host


def is_shortener(host: str) -> bool:
    return host in KNOWN_SHORTENERS
