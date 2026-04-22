"""Emit negation events for already-emitted labels of given values.

For each post that has an emitted label with val in --val, insert a
mirrored row with neg=true and status=pending. The outbox loop then calls
Ozone's emitEvent with negateLabelVals, which is the atproto way to
retract a label.

Usage:
    docker compose run --rm worker \\
        python -m snubstack.ops.negate_labels --val medium --val ghost
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from ..db import SessionLocal


async def negate(values: list[str]) -> int:
    if not values:
        return 0
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    """
                    INSERT INTO labels_emitted
                        (seq, post_uri, post_cid, val, host, neg, shadow, status)
                    SELECT
                        nextval('labels_emitted_seq_seq'),
                        post_uri, post_cid, val, host,
                        true,   -- neg
                        false,  -- not shadow; we want this emitted
                        'pending'
                    FROM labels_emitted
                    WHERE status='emitted' AND neg=false AND val = ANY(:vals)
                    ON CONFLICT (post_uri, val, neg) DO NOTHING
                    """
                ),
                {"vals": values},
            )
            return result.rowcount or 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", action="append", required=True)
    args = ap.parse_args()
    n = asyncio.run(negate(args.val))
    print(f"queued {n} negations")


if __name__ == "__main__":
    main()
