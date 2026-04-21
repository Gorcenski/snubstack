"""Extract URLs from a Bluesky post record."""

from __future__ import annotations

from collections.abc import Iterator


def iter_urls(record: dict) -> Iterator[str]:
    # richtext facets
    for facet in record.get("facets") or []:
        for feature in facet.get("features") or []:
            if feature.get("$type") == "app.bsky.richtext.facet#link":
                uri = feature.get("uri")
                if uri:
                    yield uri

    # embed.external (link card)
    embed = record.get("embed") or {}
    etype = embed.get("$type")
    if etype == "app.bsky.embed.external":
        external = embed.get("external") or {}
        uri = external.get("uri")
        if uri:
            yield uri
    # record+media combos
    elif etype == "app.bsky.embed.recordWithMedia":
        media = embed.get("media") or {}
        if media.get("$type") == "app.bsky.embed.external":
            ext = media.get("external") or {}
            uri = ext.get("uri")
            if uri:
                yield uri


def post_uri(did: str, rkey: str) -> str:
    return f"at://{did}/app.bsky.feed.post/{rkey}"
