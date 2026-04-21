"""Consumer entrypoint: Jetstream -> route per URL."""

from __future__ import annotations

import asyncio

import structlog

from ..config import settings
from ..db import SessionLocal
from ..logging_setup import configure as configure_logging
from ..urls import normalize
from .extract import iter_urls, post_uri
from .jetstream import stream_post_commits
from .routing import route_url

log = structlog.get_logger()


async def main() -> None:
    configure_logging()
    collections = [c.strip() for c in settings.jetstream_collections.split(",") if c.strip()]
    log.info("consumer.start", collections=collections, emit=settings.emit_labels)

    async for evt in stream_post_commits(settings.jetstream_url, collections):
        commit = evt["commit"]
        did = evt["did"]
        record = commit.get("record") or {}
        cid = commit.get("cid") or ""
        rkey = commit.get("rkey") or ""
        if not (cid and rkey):
            continue
        uri = post_uri(did, rkey)

        urls = list(iter_urls(record))
        if not urls:
            continue

        async with SessionLocal() as session:
            async with session.begin():
                for raw in urls:
                    norm = normalize(raw)
                    if norm is None:
                        continue
                    normalized_url, host = norm
                    await route_url(
                        session,
                        post_uri=uri,
                        post_cid=cid,
                        url=normalized_url,
                        host=host,
                    )


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
