"""Load seed files into the `domains` table.

Usage:
    python -m snubstack.ops.seed seeds/substack_red.txt --state red --platform substack
    python -m snubstack.ops.seed seeds/green.txt --state green
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import text

from ..db import SessionLocal


async def load(path: Path, state: str, platform: str | None) -> int:
    hosts: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        hosts.append(line.lower())

    async with SessionLocal() as session:
        async with session.begin():
            for host in hosts:
                await session.execute(
                    text(
                        """
                        INSERT INTO domains (host, state, platform, confidence, detector_version)
                        VALUES (:host, :state, :platform, 1.0, 'seed')
                        ON CONFLICT (host) DO UPDATE SET
                            state = EXCLUDED.state,
                            platform = COALESCE(EXCLUDED.platform, domains.platform),
                            last_changed = NOW()
                        """
                    ),
                    {"host": host, "state": state, "platform": platform},
                )
    return len(hosts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--state", required=True, choices=["red", "green"])
    ap.add_argument("--platform", default=None)
    args = ap.parse_args()
    n = asyncio.run(load(args.path, args.state, args.platform))
    print(f"loaded {n} hosts as {args.state}")


if __name__ == "__main__":
    main()
