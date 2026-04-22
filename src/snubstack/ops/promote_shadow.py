"""Flip existing shadow rows in labels_emitted to pending.

Use this once, after EMIT_LABELS has been switched to true, to actually send
labels that accumulated during shadow mode. Filter by --val so you don't
promote label values your labeler.service record doesn't declare.

Usage:
    docker compose run --rm worker \\
        python -m snubstack.ops.promote_shadow --val substack --val nytimes --val cbsnews
    docker compose run --rm worker \\
        python -m snubstack.ops.promote_shadow  # promote ALL shadow rows
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from ..db import SessionLocal


async def promote(values: list[str] | None) -> int:
    async with SessionLocal() as session:
        async with session.begin():
            if values:
                result = await session.execute(
                    text(
                        """
                        UPDATE labels_emitted
                        SET status = 'pending', shadow = false
                        WHERE status = 'shadow' AND val = ANY(:vals)
                        """
                    ),
                    {"vals": values},
                )
            else:
                result = await session.execute(
                    text(
                        """
                        UPDATE labels_emitted
                        SET status = 'pending', shadow = false
                        WHERE status = 'shadow'
                        """
                    )
                )
            return result.rowcount or 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--val",
        action="append",
        help="label value to promote; repeat for multiple. If omitted, all shadow rows are promoted.",
    )
    args = ap.parse_args()
    n = asyncio.run(promote(args.val))
    print(f"promoted {n} rows")


if __name__ == "__main__":
    main()
