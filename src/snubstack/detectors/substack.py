"""Tier-2 detector: Substack HTML fingerprint for custom domains."""

from __future__ import annotations

from selectolax.parser import HTMLParser

from .base import Verdict


class SubstackDetector:
    platform = "substack"
    label_val = "substack"
    version = "1"

    def classify_domain(self, host: str) -> Verdict | None:
        # *.substack.com is caught by DomainMatchDetector; custom domains need HTML.
        return None

    def classify_html(self, host: str, html: str, headers: dict[str, str]) -> Verdict | None:
        tree = HTMLParser(html)
        signals: list[str] = []
        confidence = 0.0

        gen = tree.css_first('meta[name="generator"]')
        if gen and "substack" in (gen.attributes.get("content") or "").lower():
            signals.append("meta:generator=Substack")
            confidence = max(confidence, 0.97)

        # Substack serves assets from substackcdn.com and writes specific script globals.
        if "substackcdn.com" in html:
            signals.append("asset:substackcdn.com")
            confidence = max(confidence, 0.85)

        if "window._preloads" in html and "substack" in html.lower():
            signals.append("js:window._preloads+substack")
            confidence = max(confidence, 0.8)

        # Combining two independent secondary signals boosts above auto-promote.
        secondary = {"asset:substackcdn.com", "js:window._preloads+substack"}
        if len(set(signals) & secondary) >= 2 and "meta:generator=Substack" not in signals:
            confidence = max(confidence, 0.95)

        if confidence == 0.0:
            return None

        return Verdict(
            platform=self.platform,
            label_val=self.label_val,
            confidence=confidence,
            signals=signals,
            detector_version=self.version,
        )
