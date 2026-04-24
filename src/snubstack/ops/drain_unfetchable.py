"""Retroactively mark chronically-failing fetch_queue hosts as unfetchable.

For every host in fetch_queue whose attempts >= --threshold, writes a
domain row with state='unfetchable' (preserving the last_error in signals),
drops its pending_posts, and deletes it from fetch_queue. Intended as a
one-shot drain after deploying the give-up-at-threshold fail path.

Usage:
    docker compose run --rm worker \\
        python -m snubstack.ops.drain_unfetchable --dry-run
    docker compose run --rm worker \\
        python -m snubstack.ops.drain_unfetchable
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from ..config import settings
from ..db import SessionLocal


async def drain(threshold: int, dry_run: bool) -> tuple[int, int, int]:
    """Return (domains_marked, pending_dropped, queue_deleted)."""
    async with SessionLocal() as session:
        async with session.begin():
            if dry_run:
                result = await session.execute(
                    text(
                        """
                        SELECT count(*) FROM fetch_queue WHERE attempts >= :t
                        """
                    ),
                    {"t": threshold},
                )
                count = result.scalar_one()
                return count, 0, 0

            marked = await session.execute(
                text(
                    """
                    INSERT INTO domains (host, state, signals, last_checked, last_changed)
                    SELECT
                        host,
                        'unfetchable',
                        jsonb_build_object(
                            'fetch_error', COALESCE(last_error, ''),
                            'attempts', attempts
                        ),
                        NOW(),
                        NOW()
                    FROM fetch_queue
                    WHERE attempts >= :t
                    ON CONFLICT (host) DO UPDATE SET
                        state = EXCLUDED.state,
                        signals = EXCLUDED.signals,
                        last_checked = NOW(),
                        last_changed = CASE
                            WHEN domains.state IS DISTINCT FROM EXCLUDED.state THEN NOW()
                            ELSE domains.last_changed END
                    """
                ),
                {"t": threshold},
            )
            dropped = await session.execute(
                text(
                    """
                    DELETE FROM pending_posts
                    WHERE host IN (SELECT host FROM fetch_queue WHERE attempts >= :t)
                    """
                ),
                {"t": threshold},
            )
            deleted = await session.execute(
                text("DELETE FROM fetch_queue WHERE attempts >= :t"),
                {"t": threshold},
            )
            return marked.rowcount or 0, dropped.rowcount or 0, deleted.rowcount or 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=settings.fetch_max_attempts)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    marked, dropped, deleted = asyncio.run(drain(args.threshold, args.dry_run))
    if args.dry_run:
        print(f"dry-run: {marked} hosts in fetch_queue have attempts >= {args.threshold}")
    else:
        print(
            f"marked {marked} domains unfetchable, "
            f"dropped {dropped} pending_posts, "
            f"deleted {deleted} fetch_queue rows"
        )


if __name__ == "__main__":
    main()
