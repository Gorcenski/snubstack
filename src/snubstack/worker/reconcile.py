"""Periodic sweep that closes the consumer/worker race window.

Two things happen per tick, idempotently:
  1. For every `pending_posts` row whose host is now `red`, enqueue a label.
     Handles posts that were buffered by the consumer after the worker had
     already started the pending → red classification.
  2. Delete `pending_posts` rows for any host in state `red` or `green`
     (they're either now labeled or never will be).

Skips `pending_review` hosts — those await human triage in Ozone.
"""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import text

from ..db import SessionLocal
from ..labels import enqueue_label

log = structlog.get_logger()

SWEEP_INTERVAL_S = 30.0
BATCH = 1000


async def sweep_tick() -> tuple[int, int]:
    """Return (backlabeled, deleted) counts."""
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    """
                    SELECT pp.post_uri, pp.post_cid, pp.host, d.platform
                    FROM pending_posts pp
                    JOIN domains d ON d.host = pp.host
                    WHERE d.state = 'red' AND d.platform IS NOT NULL
                    LIMIT :batch
                    """
                ),
                {"batch": BATCH},
            )
            rows = result.all()
            for post_uri, post_cid, host, platform in rows:
                await enqueue_label(
                    session,
                    post_uri=post_uri,
                    post_cid=post_cid,
                    val=platform,
                    host=host,
                )

            deleted = await session.execute(
                text(
                    """
                    DELETE FROM pending_posts
                    WHERE host IN (
                        SELECT host FROM domains WHERE state IN ('red', 'green')
                    )
                    """
                )
            )
            return len(rows), deleted.rowcount or 0


async def sweep_loop() -> None:
    while True:
        try:
            backlabeled, deleted = await sweep_tick()
            if backlabeled or deleted:
                log.info("reconcile.tick", backlabeled=backlabeled, deleted=deleted)
        except Exception as e:
            log.warning("reconcile.error", err=str(e))
        await asyncio.sleep(SWEEP_INTERVAL_S)
