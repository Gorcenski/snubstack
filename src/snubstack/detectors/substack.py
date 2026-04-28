"""Tier-2 detector: Substack HTML/header fingerprint for custom domains."""

from __future__ import annotations

from selectolax.parser import HTMLParser

from .base import Verdict


def _header(headers: dict[str, str], name: str) -> str:
    name = name.lower()
    for k, v in headers.items():
        if k.lower() == name:
            return v
    return ""


class SubstackDetector:
    platform = "substack"
    label_val = "substack"
    version = "3"

    def classify_domain(self, host: str) -> Verdict | None:
        # *.substack.com is caught by DomainMatchDetector; custom domains need HTML.
        return None

    def classify_html(self, host: str, html: str, headers: dict[str, str]) -> Verdict | None:
        """Definitive signals come from Substack's own infrastructure: the
        page's generator meta tag (when present) and edge headers (x-served-by,
        x-cluster) added by Substack's CDN. Body strings like substackcdn or
        window._preloads are corroborating only — they show up on non-Substack
        sites that merely embed Substack widgets.
        """
        signals: list[str] = []

        tree = HTMLParser(html)
        gen = tree.css_first('meta[name="generator"]')
        if gen and "substack" in (gen.attributes.get("content") or "").lower():
            signals.append("meta:generator=Substack")

        served_by = _header(headers, "x-served-by")
        if "substack" in served_by.lower():
            signals.append(f"header:x-served-by={served_by}")

        cluster = _header(headers, "x-cluster")
        if "substack" in cluster.lower():
            signals.append(f"header:x-cluster={cluster}")

        if not signals:
            return None

        if "substackcdn.com" in html:
            signals.append("asset:substackcdn.com")

        return Verdict(
            platform=self.platform,
            label_val=self.label_val,
            confidence=0.97,
            signals=signals,
            detector_version=self.version,
        )
