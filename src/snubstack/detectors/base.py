from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Verdict:
    platform: str
    label_val: str
    confidence: float
    signals: list[str] = field(default_factory=list)
    detector_version: str = "0"


@runtime_checkable
class Detector(Protocol):
    platform: str
    label_val: str
    version: str

    def classify_domain(self, host: str) -> Verdict | None:
        """Decide from hostname alone. Return None to defer to HTML fetch."""
        ...

    def classify_html(
        self, host: str, html: str, headers: dict[str, str]
    ) -> Verdict | None:
        """Decide from fetched HTML. Return None if not a match."""
        ...
