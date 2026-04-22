"""Heron data platform client.

OAuth client-credentials flow: fetches a token, caches until ~1 minute
before expiry, refreshes on 401. Single `ingest` method handles the
report PUT.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class HeronError(Exception):
    pass


class HeronClient:
    def __init__(
        self,
        *,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        api_endpoint: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token_endpoint = token_endpoint
        self._client_id = client_id
        self._client_secret = client_secret
        self._api_endpoint = api_endpoint.rstrip("/")
        self._http = client or httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        resp = await self._http.post(
            self._token_endpoint,
            json={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if resp.status_code >= 400:
            raise HeronError(f"token {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires_at = time.time() + float(body.get("expires_in", 3600))
        return self._token

    async def ingest(
        self,
        *,
        report_name: str,
        data: list[dict[str, Any]],
        mode: str = "overwrite",
        indexes: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "report_name": report_name,
            "data": data,
            "mode": mode,
        }
        if indexes:
            body["indexes"] = indexes

        async def _put() -> httpx.Response:
            token = await self._get_token()
            return await self._http.put(
                f"{self._api_endpoint}/ingest",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        resp = await _put()
        if resp.status_code == 401:
            # token may be revoked; force refresh and retry once
            self._token = None
            resp = await _put()
        if resp.status_code >= 400:
            raise HeronError(
                f"ingest {report_name} {resp.status_code}: {resp.text[:500]}"
            )

    async def aclose(self) -> None:
        await self._http.aclose()
