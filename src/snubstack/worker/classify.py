"""Run detectors and decide a verdict + terminal domain state."""

from __future__ import annotations

from ..config import settings
from ..detectors import ALL_DETECTORS
from ..detectors.base import Verdict


def classify_domain(host: str) -> Verdict | None:
    for det in ALL_DETECTORS:
        v = det.classify_domain(host)
        if v is not None:
            return v
    return None


def classify_html(host: str, html: str, headers: dict[str, str]) -> Verdict | None:
    best: Verdict | None = None
    for det in ALL_DETECTORS:
        v = det.classify_html(host, html, headers)
        if v is None:
            continue
        if best is None or v.confidence > best.confidence:
            best = v
    return best


def decide_state(verdict: Verdict | None) -> str:
    if verdict is None:
        return "green"
    if verdict.confidence >= settings.auto_promote_confidence:
        return "red"
    if verdict.confidence >= settings.review_confidence:
        return "pending_review"
    return "green"
