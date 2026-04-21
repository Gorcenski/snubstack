from .base import Detector, Verdict
from .domain_match import DomainMatchDetector
from .substack import SubstackDetector

ALL_DETECTORS: list[Detector] = [
    DomainMatchDetector(),
    SubstackDetector(),
]

__all__ = ["Detector", "Verdict", "ALL_DETECTORS"]
