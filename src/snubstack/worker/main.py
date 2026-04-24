"""Worker loop: claim host -> fetch -> classify -> update domain + back-label."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

import httpx
import structlog
from sqlalchemy import text

from ..config import settings
from ..db import SessionLocal
from ..labels import enqueue_label, outbox_loop
from ..logging_setup import configure as configure_logging
from ..ozone.client import OzoneClient
from ..queue import claim_one, complete, fail
from .classify import classify_domain, classify_html, decide_state
from .fetcher import FetchError, fetch_html
from ..heron.push import push_loop as heron_push_loop
from .reconcile import sweep_loop
from .resolver import resolver_loop

log = structlog.get_logger()

IDLE_SLEEP_S = 1.0
LOCK_FOR = timedelta(minutes=5)
BACKOFF_ON_FAIL = timedelta(minutes=30)


async def _update_domain(session, host: str, state: str, verdict) -> None:
    await session.execute(
        text(
            """
            INSERT INTO domains (host, state, platform, confidence, signals, detector_version, last_checked, last_changed)
            VALUES (:host, :state, :platform, :confidence, CAST(:signals AS jsonb), :dv, NOW(), NOW())
            ON CONFLICT (host) DO UPDATE SET
                state = EXCLUDED.state,
                platform = EXCLUDED.platform,
                confidence = EXCLUDED.confidence,
                signals = EXCLUDED.signals,
                detector_version = EXCLUDED.detector_version,
                last_checked = NOW(),
                last_changed = CASE
                    WHEN domains.state IS DISTINCT FROM EXCLUDED.state THEN NOW()
                    ELSE domains.last_changed END
            """
        ),
        {
            "host": host,
            "state": state,
            "platform": verdict.platform if verdict else None,
            "confidence": verdict.confidence if verdict else None,
            "signals": json.dumps(verdict.signals) if verdict else None,
            "dv": verdict.detector_version if verdict else None,
        },
    )


async def _backlabel_pending(session, host: str, label_val: str) -> int:
    result = await session.execute(
        text(
            "SELECT id, post_uri, post_cid FROM pending_posts WHERE host = :host"
        ),
        {"host": host},
    )
    rows = result.all()
    for _id, post_uri, post_cid in rows:
        await enqueue_label(
            session,
            post_uri=post_uri,
            post_cid=post_cid,
            val=label_val,
            host=host,
        )
    await session.execute(
        text("DELETE FROM pending_posts WHERE host = :host"),
        {"host": host},
    )
    return len(rows)


async def _drop_pending(session, host: str) -> None:
    await session.execute(
        text("DELETE FROM pending_posts WHERE host = :host"),
        {"host": host},
    )


async def _mark_unfetchable(session, host: str, err: str, attempts: int) -> None:
    await session.execute(
        text(
            """
            INSERT INTO domains (host, state, signals, last_checked, last_changed)
            VALUES (:host, 'unfetchable', CAST(:signals AS jsonb), NOW(), NOW())
            ON CONFLICT (host) DO UPDATE SET
                state = EXCLUDED.state,
                signals = EXCLUDED.signals,
                last_checked = NOW(),
                last_changed = CASE
                    WHEN domains.state IS DISTINCT FROM EXCLUDED.state THEN NOW()
                    ELSE domains.last_changed END
            """
        ),
        {
            "host": host,
            "signals": json.dumps({"fetch_error": err, "attempts": attempts}),
        },
    )


async def process_one(client: httpx.AsyncClient) -> bool:
    """Process one host. Returns True if work was done."""
    async with SessionLocal() as session:
        async with session.begin():
            host = await claim_one(session, LOCK_FOR)
            if host is None:
                return False

            # Tier-1 fast path: domain-only verdict without HTTP.
            verdict = classify_domain(host)
            if verdict is None:
                try:
                    fetched = await fetch_html(client, host)
                except FetchError as e:
                    log.warning("worker.fetch_failed", host=host, err=str(e))
                    attempts = await fail(session, host, str(e), BACKOFF_ON_FAIL)
                    if attempts >= settings.fetch_max_attempts:
                        await _mark_unfetchable(session, host, str(e), attempts)
                        await _drop_pending(session, host)
                        await complete(session, host)
                        log.info(
                            "worker.unfetchable",
                            host=host,
                            attempts=attempts,
                            err=str(e),
                        )
                    return True
                if fetched is not None:
                    html, headers = fetched
                    verdict = classify_html(host, html, headers)

            state = decide_state(verdict)
            await _update_domain(session, host, state, verdict)

            if state == "red" and verdict is not None:
                n = await _backlabel_pending(session, host, verdict.label_val)
                log.info(
                    "worker.promoted",
                    host=host,
                    platform=verdict.platform,
                    confidence=verdict.confidence,
                    backlabeled=n,
                )
            elif state == "green":
                await _drop_pending(session, host)
            # pending_review: leave buffered posts alone until human review

            await complete(session, host)
            return True


async def _fetch_loop(client: httpx.AsyncClient) -> None:
    while True:
        did_work = await process_one(client)
        if not did_work:
            await asyncio.sleep(IDLE_SLEEP_S)


async def main() -> None:
    configure_logging()
    log.info("worker.start", emit=settings.emit_labels)
    timeout = httpx.Timeout(settings.fetch_timeout_seconds)
    headers = {"User-Agent": settings.fetch_user_agent}
    ozone = OzoneClient(
        base_url=settings.ozone_url,
        admin_password=settings.ozone_admin_password,
        source_did=settings.labeler_did,
    )
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        try:
            await asyncio.gather(
                _fetch_loop(client),
                resolver_loop(client),
                outbox_loop(ozone),
                sweep_loop(),
                heron_push_loop(),
            )
        finally:
            await ozone.aclose()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
