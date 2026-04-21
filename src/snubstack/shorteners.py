"""Postgres helpers for shortener resolution: cache, queue, buffer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CachedResolution(NamedTuple):
    resolved_url: str | None
    resolved_host: str | None
    error: str | None


async def lookup(session: AsyncSession, short_url: str) -> CachedResolution | None:
    """Return a cached resolution, or None if not yet resolved."""
    result = await session.execute(
        text(
            """
            SELECT resolved_url, resolved_host, error
            FROM shortener_resolutions
            WHERE short_url = :s
            """
        ),
        {"s": short_url},
    )
    row = result.first()
    return CachedResolution(*row) if row else None


async def cache_resolution(
    session: AsyncSession,
    *,
    short_url: str,
    resolved_url: str | None,
    resolved_host: str | None,
    error: str | None,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO shortener_resolutions
                (short_url, resolved_url, resolved_host, error, resolved_at)
            VALUES (:s, :u, :h, :e, NOW())
            ON CONFLICT (short_url) DO UPDATE SET
                resolved_url = EXCLUDED.resolved_url,
                resolved_host = EXCLUDED.resolved_host,
                error = EXCLUDED.error,
                resolved_at = NOW()
            """
        ),
        {"s": short_url, "u": resolved_url, "h": resolved_host, "e": error},
    )


async def enqueue(session: AsyncSession, short_url: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO shortener_queue (short_url)
            VALUES (:s)
            ON CONFLICT (short_url) DO NOTHING
            """
        ),
        {"s": short_url},
    )


async def buffer_post(
    session: AsyncSession,
    *,
    post_uri: str,
    post_cid: str,
    short_url: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO shortener_pending (post_uri, post_cid, short_url)
            VALUES (:u, :c, :s)
            """
        ),
        {"u": post_uri, "c": post_cid, "s": short_url},
    )


async def claim_one(session: AsyncSession, lock_for: timedelta) -> str | None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        text(
            """
            WITH claimed AS (
                SELECT short_url FROM shortener_queue
                WHERE locked_until IS NULL OR locked_until < :now
                ORDER BY enqueued_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE shortener_queue q
            SET locked_until = :until, attempts = q.attempts + 1
            FROM claimed
            WHERE q.short_url = claimed.short_url
            RETURNING q.short_url
            """
        ),
        {"now": now, "until": now + lock_for},
    )
    row = result.first()
    return row[0] if row else None


async def complete(session: AsyncSession, short_url: str) -> None:
    await session.execute(
        text("DELETE FROM shortener_queue WHERE short_url = :s"),
        {"s": short_url},
    )


async def fail(
    session: AsyncSession, short_url: str, err: str, backoff: timedelta
) -> None:
    await session.execute(
        text(
            """
            UPDATE shortener_queue
            SET last_error = :e, locked_until = :until
            WHERE short_url = :s
            """
        ),
        {
            "s": short_url,
            "e": err[:1000],
            "until": datetime.now(timezone.utc) + backoff,
        },
    )


async def take_buffered(session: AsyncSession, short_url: str) -> list[tuple[str, str]]:
    """Return (post_uri, post_cid) pairs awaiting this short_url and delete them."""
    result = await session.execute(
        text(
            """
            DELETE FROM shortener_pending
            WHERE short_url = :s
            RETURNING post_uri, post_cid
            """
        ),
        {"s": short_url},
    )
    return [(r[0], r[1]) for r in result.all()]
