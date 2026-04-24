"""Decide what to do with a (post, url, host) triple."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .. import shorteners
from ..labels import enqueue_label
from ..queue import enqueue_host
from ..urls import is_shortener


MAX_SHORTENER_HOPS = 5


async def route_url(
    session: AsyncSession,
    *,
    post_uri: str,
    post_cid: str,
    url: str,
    host: str,
) -> str:
    """Top-level dispatcher. Walks shortener cache iteratively until we land
    on a non-shortener host, then classifies by domain state."""
    for _ in range(MAX_SHORTENER_HOPS + 1):
        if not is_shortener(host):
            return await route(
                session,
                post_uri=post_uri,
                post_cid=post_cid,
                url=url,
                host=host,
            )
        cached = await shorteners.lookup(session, url)
        if cached is None:
            await shorteners.enqueue(session, url)
            await shorteners.buffer_post(
                session, post_uri=post_uri, post_cid=post_cid, short_url=url
            )
            return "shortener_unknown"
        if cached.error or not cached.resolved_url or not cached.resolved_host:
            return "shortener_dead"
        url = cached.resolved_url
        host = cached.resolved_host
    return "shortener_too_many_hops"


async def route(
    session: AsyncSession,
    *,
    post_uri: str,
    post_cid: str,
    url: str,
    host: str,
) -> str:
    """Classify a non-shortener URL by its host. Returns the decision string."""
    result = await session.execute(
        text("SELECT state, platform FROM domains WHERE host = :host"),
        {"host": host},
    )
    row = result.first()

    if row is None:
        await enqueue_host(session, host)
        await _buffer(session, post_uri=post_uri, post_cid=post_cid, url=url, host=host)
        await session.execute(
            text(
                """
                INSERT INTO domains (host, state)
                VALUES (:host, 'pending')
                ON CONFLICT (host) DO NOTHING
                """
            ),
            {"host": host},
        )
        return "unknown"

    state, platform = row
    if state == "red" and platform:
        await enqueue_label(
            session,
            post_uri=post_uri,
            post_cid=post_cid,
            val=platform,
            host=host,
        )
        return "labeled"
    if state == "green":
        return "green"
    if state == "unfetchable":
        return "unfetchable"
    if state in ("pending", "pending_review"):
        await _buffer(session, post_uri=post_uri, post_cid=post_cid, url=url, host=host)
        return state
    return "noop"


async def _buffer(
    session: AsyncSession,
    *,
    post_uri: str,
    post_cid: str,
    url: str,
    host: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO pending_posts (post_uri, post_cid, host, url)
            VALUES (:post_uri, :post_cid, :host, :url)
            """
        ),
        {"post_uri": post_uri, "post_cid": post_cid, "url": url, "host": host},
    )
