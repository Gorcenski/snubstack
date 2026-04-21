"""Outbox-style label emission.

Two phases:
  1. `enqueue_label` — idempotent insert of a row in `labels_emitted` with
     status=pending (or shadow if EMIT_LABELS=false). Called from consumer
     hot path and worker back-label path.
  2. `deliver_pending` — outbox loop pulls pending rows and POSTs to Ozone,
     marking emitted/failed. Runs inside the worker process.

Idempotency comes from UNIQUE(post_uri, val, neg). If we crash between
phases, the next run will pick the row up again.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import SessionLocal
from .ozone.client import OzoneClient, OzoneError

log = structlog.get_logger()


async def enqueue_label(
    session: AsyncSession,
    *,
    post_uri: str,
    post_cid: str,
    val: str,
    host: str,
) -> bool:
    """Insert a pending label row. Returns True if newly inserted."""
    status = "shadow" if not settings.emit_labels else "pending"
    result = await session.execute(
        text(
            """
            INSERT INTO labels_emitted
                (seq, post_uri, post_cid, val, host, neg, shadow, status)
            VALUES
                (nextval('labels_emitted_seq_seq'),
                 :post_uri, :post_cid, :val, :host, false, :shadow, :status)
            ON CONFLICT (post_uri, val, neg) DO NOTHING
            RETURNING id
            """
        ),
        {
            "post_uri": post_uri,
            "post_cid": post_cid,
            "val": val,
            "host": host,
            "shadow": not settings.emit_labels,
            "status": status,
        },
    )
    return result.first() is not None


async def _claim_pending(session: AsyncSession, limit: int) -> list[tuple]:
    result = await session.execute(
        text(
            """
            SELECT id, post_uri, post_cid, val, neg
            FROM labels_emitted
            WHERE status = 'pending'
            ORDER BY id
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return list(result.all())


async def _mark_emitted(session: AsyncSession, label_id: int) -> None:
    await session.execute(
        text(
            """
            UPDATE labels_emitted
            SET status = 'emitted', delivered_at = :now, ozone_error = NULL
            WHERE id = :id
            """
        ),
        {"id": label_id, "now": datetime.now(timezone.utc)},
    )


async def _mark_failed(session: AsyncSession, label_id: int, err: str) -> None:
    await session.execute(
        text(
            """
            UPDATE labels_emitted
            SET status = 'failed', ozone_error = :err
            WHERE id = :id
            """
        ),
        {"id": label_id, "err": err[:1000]},
    )


async def deliver_pending(client: OzoneClient, batch: int = 50) -> int:
    """Drain up to `batch` pending labels to Ozone. Returns number processed."""
    async with SessionLocal() as session:
        async with session.begin():
            rows = await _claim_pending(session, batch)
        if not rows:
            return 0

        n_ok = 0
        for label_id, post_uri, post_cid, val, neg in rows:
            try:
                await client.emit_label(
                    post_uri=post_uri,
                    post_cid=post_cid,
                    label_val=val,
                    neg=neg,
                    comment="snubstack:auto",
                )
            except OzoneError as e:
                log.warning("ozone.emit_failed", id=label_id, err=str(e))
                async with session.begin():
                    await _mark_failed(session, label_id, str(e))
                continue
            async with session.begin():
                await _mark_emitted(session, label_id)
            n_ok += 1
        return n_ok


async def outbox_loop(client: OzoneClient, idle_sleep: float = 1.0) -> None:
    while True:
        n = await deliver_pending(client)
        if n == 0:
            await asyncio.sleep(idle_sleep)
