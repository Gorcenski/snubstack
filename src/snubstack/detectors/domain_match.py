"""Tier-1 detector: pure domain-name match. Cheap and deterministic."""

from __future__ import annotations

from .base import Verdict

# (suffix_or_exact_host, platform, label_val)
# A `*.` prefix means suffix-match; otherwise exact host.
RULES: list[tuple[str, str, str]] = [
    ("*.substack.com", "substack", "substack"),
    ("nytimes.com", "nytimes", "nytimes"),
    ("*.nytimes.com", "nytimes", "nytimes"),
    ("medium.com", "medium", "medium"),
    ("*.medium.com", "medium", "medium"),
    ("ghost.io", "ghost", "ghost"),
    ("*.ghost.io", "ghost", "ghost"),
    ("mirror.xyz", "mirror", "mirror"),
    ("*.mirror.xyz", "mirror", "mirror"),
]


def _matches(rule: str, host: str) -> bool:
    if rule.startswith("*."):
        return host.endswith(rule[1:])
    return host == rule


class DomainMatchDetector:
    platform = "domain-match"
    label_val = ""  # set per-match
    version = "1"

    def classify_domain(self, host: str) -> Verdict | None:
        for rule, platform, label in RULES:
            if _matches(rule, host):
                return Verdict(
                    platform=platform,
                    label_val=label,
                    confidence=1.0,
                    signals=[f"domain:{rule}"],
                    detector_version=self.version,
                )
        return None

    def classify_html(self, host: str, html: str, headers: dict[str, str]) -> Verdict | None:
        return None
