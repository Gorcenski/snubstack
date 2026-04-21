"""Postgres-backed fetch queue using FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def enqueue_host(session: AsyncSession, host: str) -> None:
    """Idempotent enqueue; no-op if already queued."""
    await session.execute(
        text(
            """
            INSERT INTO fetch_queue (host)
            VALUES (:host)
            ON CONFLICT (host) DO NOTHING
            """
        ),
        {"host": host},
    )


async def claim_one(session: AsyncSession, lock_for: timedelta) -> str | None:
    """Atomically claim one host for processing, or return None."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        text(
            """
            WITH claimed AS (
                SELECT host FROM fetch_queue
                WHERE locked_until IS NULL OR locked_until < :now
                ORDER BY enqueued_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE fetch_queue fq
            SET locked_until = :lock_until, attempts = fq.attempts + 1
            FROM claimed
            WHERE fq.host = claimed.host
            RETURNING fq.host
            """
        ),
        {"now": now, "lock_until": now + lock_for},
    )
    row = result.first()
    return row[0] if row else None


async def complete(session: AsyncSession, host: str) -> None:
    """Remove a host from the queue after successful classification."""
    await session.execute(
        text("DELETE FROM fetch_queue WHERE host = :host"),
        {"host": host},
    )


async def fail(session: AsyncSession, host: str, err: str, backoff: timedelta) -> None:
    """Record a failure and release the lock with backoff."""
    await session.execute(
        text(
            """
            UPDATE fetch_queue
            SET last_error = :err, locked_until = :until
            WHERE host = :host
            """
        ),
        {"host": host, "err": err[:1000], "until": datetime.now(timezone.utc) + backoff},
    )
