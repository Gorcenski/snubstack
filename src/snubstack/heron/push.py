"""Periodic Heron pushes: a snapshot report and an append-only timeseries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import text

from ..config import settings
from ..db import SessionLocal
from .client import HeronClient

log = structlog.get_logger()

PUSH_INTERVAL_S = 3600  # 1 hour
COUNTS_REPORT = "snubstack_label_counts"
TIMESERIES_REPORT = "snubstack_labels_timeseries"


def _enabled() -> bool:
    return all(
        [
            settings.heron_oauth_client_id,
            settings.heron_oauth_client_secret,
            settings.heron_oauth_token_endpoint,
            settings.heron_api_endpoint,
        ]
    )


async def _push_counts(heron: HeronClient) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT val, host, count(*) AS n
                FROM labels_emitted
                WHERE status='emitted' AND neg=false
                GROUP BY val, host
                """
            )
        )
        rows = result.all()
    data = [{"val": v, "host": h, "n": int(n)} for v, h, n in rows]
    await heron.ingest(
        report_name=COUNTS_REPORT,
        data=data,
        mode="overwrite",
        indexes="val,host",
    )
    return len(data)


async def _push_timeseries(heron: HeronClient) -> int:
    now = datetime.now(timezone.utc)

    async with SessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT last_pushed_at FROM heron_push_state WHERE report_name = :n"
            ),
            {"n": TIMESERIES_REPORT},
        )
        row = result.first()
        last = row[0] if row else None

        if last is None:
            sql = """
                SELECT date_trunc('hour', delivered_at) AS hour, val, host, count(*) AS n
                FROM labels_emitted
                WHERE status='emitted' AND neg=false
                  AND delivered_at IS NOT NULL AND delivered_at < :now
                GROUP BY 1, 2, 3
                ORDER BY 1
            """
            params: dict = {"now": now}
        else:
            sql = """
                SELECT date_trunc('hour', delivered_at) AS hour, val, host, count(*) AS n
                FROM labels_emitted
                WHERE status='emitted' AND neg=false
                  AND delivered_at IS NOT NULL
                  AND delivered_at > :last AND delivered_at < :now
                GROUP BY 1, 2, 3
                ORDER BY 1
            """
            params = {"last": last, "now": now}
        result = await session.execute(text(sql), params)
        rows = result.all()

    data = [
        {"hour": h.isoformat(), "val": v, "host": host_, "n": int(n)}
        for h, v, host_, n in rows
    ]
    if data:
        await heron.ingest(
            report_name=TIMESERIES_REPORT,
            data=data,
            mode="append",
            indexes="hour,val",
        )

    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO heron_push_state (report_name, last_pushed_at)
                    VALUES (:n, :now)
                    ON CONFLICT (report_name)
                    DO UPDATE SET last_pushed_at = EXCLUDED.last_pushed_at
                    """
                ),
                {"n": TIMESERIES_REPORT, "now": now},
            )

    return len(data)


async def _push_once(heron: HeronClient) -> None:
    counts = await _push_counts(heron)
    series = await _push_timeseries(heron)
    log.info("heron.push", counts_rows=counts, timeseries_rows=series)


async def push_loop() -> None:
    if not _enabled():
        log.info("heron.push_loop.disabled", reason="missing config")
        return
    heron = HeronClient(
        token_endpoint=settings.heron_oauth_token_endpoint,
        client_id=settings.heron_oauth_client_id,
        client_secret=settings.heron_oauth_client_secret,
        api_endpoint=settings.heron_api_endpoint,
    )
    try:
        while True:
            try:
                await _push_once(heron)
            except Exception as e:
                log.warning("heron.push_failed", err=str(e))
            await asyncio.sleep(PUSH_INTERVAL_S)
    finally:
        await heron.aclose()
