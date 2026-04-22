"""Polite HTML fetcher with size and timeout caps."""

from __future__ import annotations

import httpx
import structlog

from ..config import settings

log = structlog.get_logger()


class FetchError(Exception):
    pass


async def fetch_html(
    client: httpx.AsyncClient, host: str
) -> tuple[str, dict[str, str]] | None:
    """Fetch the homepage of `host` and return (html, response_headers).

    Returns None on non-HTML responses or content-too-large. Raises FetchError on
    transport/HTTP errors so the queue can backoff.
    """
    url = f"https://{host}/"
    try:
        host.encode("idna")
    except (UnicodeError, UnicodeDecodeError) as e:
        raise FetchError(f"invalid IDNA host: {e}") from e
    try:
        async with client.stream("GET", url, follow_redirects=True) as resp:
            if resp.status_code >= 400:
                raise FetchError(f"http {resp.status_code}")
            ctype = resp.headers.get("content-type", "").lower()
            if "html" not in ctype:
                return None
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > settings.fetch_max_bytes:
                    log.info("fetcher.truncated", host=host, bytes=total)
                    break
                chunks.append(chunk)
            body = b"".join(chunks)
            # Best-effort decode; fall back to utf-8 with replacement.
            try:
                text = body.decode(resp.encoding or "utf-8", errors="replace")
            except LookupError:
                text = body.decode("utf-8", errors="replace")
            return text, dict(resp.headers)
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        raise FetchError(str(e)) from e
