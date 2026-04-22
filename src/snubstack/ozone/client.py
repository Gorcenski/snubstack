"""Ozone admin client.

Calls `tools.ozone.moderation.emitEvent` to apply labels. Ozone handles
persistence, signing, and the public xrpc surface (queryLabels /
subscribeLabels). snubstack only needs to push events.

Auth: HTTP Basic with username 'admin' and password = OZONE_ADMIN_PASSWORD.
"""

from __future__ import annotations

import base64

import httpx
import structlog

log = structlog.get_logger()


class OzoneError(Exception):
    pass


class OzoneClient:
    def __init__(
        self,
        *,
        base_url: str,
        admin_password: str,
        source_did: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        token = base64.b64encode(f"admin:{admin_password}".encode()).decode()
        self._auth = {"Authorization": f"Basic {token}"}
        self._source_did = source_did
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def emit_label(
        self,
        *,
        post_uri: str,
        post_cid: str,
        label_val: str,
        neg: bool = False,
        comment: str | None = None,
    ) -> None:
        body = {
            "event": {
                "$type": "tools.ozone.moderation.defs#modEventLabel",
                "createLabelVals": [] if neg else [label_val],
                "negateLabelVals": [label_val] if neg else [],
            },
            "subject": {
                "$type": "com.atproto.repo.strongRef",
                "uri": post_uri,
                "cid": post_cid,
            },
            "createdBy": self._source_did,
        }
        if comment is not None:
            body["event"]["comment"] = comment

        url = f"{self._base}/xrpc/tools.ozone.moderation.emitEvent"
        resp = await self._client.post(url, json=body, headers=self._auth)
        if resp.status_code >= 400:
            raise OzoneError(f"emitEvent {resp.status_code}: {resp.text[:500]}")

    async def aclose(self) -> None:
        await self._client.aclose()
