"""Tier-2 detector: Substack HTML fingerprint for custom domains."""

from __future__ import annotations

from selectolax.parser import HTMLParser

from .base import Verdict


class SubstackDetector:
    platform = "substack"
    label_val = "substack"
    version = "2"

    def classify_domain(self, host: str) -> Verdict | None:
        # *.substack.com is caught by DomainMatchDetector; custom domains need HTML.
        return None

    def classify_html(self, host: str, html: str, headers: dict[str, str]) -> Verdict | None:
        """Only the generator meta tag is definitive. Secondary signals
        (substackcdn asset, window._preloads) are common on non-Substack sites
        that embed Substack widgets — they don't mean the page *is* a Substack.
        Require the generator meta tag; otherwise drop to green.
        """
        tree = HTMLParser(html)

        gen = tree.css_first('meta[name="generator"]')
        if not (gen and "substack" in (gen.attributes.get("content") or "").lower()):
            return None

        signals = ["meta:generator=Substack"]
        if "substackcdn.com" in html:
            signals.append("asset:substackcdn.com")

        return Verdict(
            platform=self.platform,
            label_val=self.label_val,
            confidence=0.97,
            signals=signals,
            detector_version="2",
        )
