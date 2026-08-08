"""Classify workflow failures before deciding whether automated code repair is appropriate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json


class FailureKind(str, Enum):
    TRANSIENT = "TRANSIENT"
    BUSINESS = "BUSINESS"
    INPUT = "INPUT"
    CODE = "CODE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class FailureRecord:
    kind: FailureKind
    error_type: str
    message: str


class FailureClassifier:
    """Use deterministic exception and message evidence; ambiguous errors stay non-repairable."""

    def classify(self, error: BaseException) -> FailureRecord:
        message = str(error)
        lowered = message.lower()
        if isinstance(error, (TimeoutError, ConnectionError)) or type(error).__name__ in {
            "APIConnectionError",
            "APITimeoutError",
        } or any(
            marker in lowered for marker in ("timeout", "connection error", "connection reset", "temporarily unavailable")
        ):
            kind = FailureKind.TRANSIENT
        elif isinstance(error, (FileNotFoundError, json.JSONDecodeError)) or any(
            marker in lowered for marker in ("scenario", "json", "input path", "not found")
        ):
            kind = FailureKind.INPUT
        elif isinstance(error, (ImportError, ModuleNotFoundError, SyntaxError, AssertionError)) or any(
            marker in lowered for marker in ("traceback", "state-machine", "attributeerror", "typeerror")
        ):
            kind = FailureKind.CODE
        elif any(marker in lowered for marker in ("candidate", "semantic", "score", "validation")):
            kind = FailureKind.BUSINESS
        else:
            kind = FailureKind.UNKNOWN
        return FailureRecord(kind=kind, error_type=type(error).__name__, message=message)
