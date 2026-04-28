"""Shortener resolver: claim short URL → resolve via redirects → cache → dispatch."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import httpx
import structlog

from .. import shorteners
from ..db import SessionLocal
from ..urls import normalize
from ..consumer.routing import route_url

log = structlog.get_logger()

IDLE_SLEEP_S = 1.0
LOCK_FOR = timedelta(minutes=2)
BACKOFF_ON_FAIL = timedelta(hours=6)
MAX_REDIRECTS = 5


async def _resolve(
    client: httpx.AsyncClient, short_url: str
) -> tuple[str | None, str | None, str | None]:
    """Return (resolved_url, resolved_host, error). url/host are None on error."""
    try:
        resp = await client.head(
            short_url, follow_redirects=True, timeout=10.0
        )
        # Some shorteners reject HEAD; fall back to GET.
        if resp.status_code in (400, 403, 405, 501):
            resp = await client.get(
                short_url, follow_redirects=True, timeout=10.0
            )
        if resp.status_code >= 400:
            return None, None, f"http {resp.status_code}"
    except httpx.HTTPError as e:
        return None, None, str(e)

    final = str(resp.url)
    norm = normalize(final)
    if norm is None:
        return None, None, "non-http or unparseable target"
    return norm[0], norm[1], None


async def process_one(client: httpx.AsyncClient) -> bool:
    async with SessionLocal() as session:
        async with session.begin():
            short_url = await shorteners.claim_one(session, LOCK_FOR)
            if short_url is None:
                return False

        # Resolve outside the txn (HTTP call shouldn't hold a connection).
        resolved_url, resolved_host, err = await _resolve(client, short_url)

        async with SessionLocal() as session2:
            async with session2.begin():
                await shorteners.cache_resolution(
                    session2,
                    short_url=short_url,
                    resolved_url=resolved_url,
                    resolved_host=resolved_host,
                    error=err,
                )
                buffered = await shorteners.take_buffered(session2, short_url)

                if resolved_url and resolved_host:
                    for post_uri, post_cid in buffered:
                        await route_url(
                            session2,
                            post_uri=post_uri,
                            post_cid=post_cid,
                            url=resolved_url,
                            host=resolved_host,
                        )
                    log.info(
                        "resolver.resolved",
                        short_url=short_url,
                        host=resolved_host,
                        dispatched=len(buffered),
                    )
                else:
                    log.info(
                        "resolver.dead",
                        short_url=short_url,
                        err=err,
                        dropped=len(buffered),
                    )

                await shorteners.complete(session2, short_url)
                return True


async def resolver_loop(client: httpx.AsyncClient) -> None:
    while True:
        try:
            did_work = await process_one(client)
        except Exception:
            # Shortener targets can resolve to URLs with invalid IDNA hosts or
            # other surprises that escape httpx's normal exception types.
            # Don't let one bad redirect kill the worker via gather().
            log.exception("resolver.process_one_crashed")
            did_work = False
        if not did_work:
            await asyncio.sleep(IDLE_SLEEP_S)
