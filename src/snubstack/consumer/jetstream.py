"""Jetstream client: yields post commit events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import structlog
import websockets
from tenacity import AsyncRetrying, wait_exponential

log = structlog.get_logger()


async def stream_post_commits(url: str, collections: list[str]) -> AsyncIterator[dict]:
    """Yield `commit` events for `app.bsky.feed.post` create ops."""
    full_url = f"{url}?{urlencode([('wantedCollections', c) for c in collections])}"

    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=False,
    ):
        with attempt:
            log.info("jetstream.connecting", url=full_url)
            async with websockets.connect(
                full_url, max_size=2_000_000, ping_interval=20, ping_timeout=20
            ) as ws:
                log.info("jetstream.connected")
                async for raw in ws:
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("kind") != "commit":
                        continue
                    commit = evt.get("commit") or {}
                    if commit.get("operation") != "create":
                        continue
                    if commit.get("collection") not in collections:
                        continue
                    yield evt
        # connection closed; exponential backoff and reconnect
        await asyncio.sleep(0)
