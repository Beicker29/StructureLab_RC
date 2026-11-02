"""Errores estructurados con código estable."""

from dataclasses import dataclass, field
from enum import StrEnum


class ErrorCode(StrEnum):
    BLOCKED = "blocked"
    INCOMPLETE = "incomplete"
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True)
class StructuredError:
    code: ErrorCode
    message: str
    details: dict[str, object] = field(default_factory=dict)


def blocked(message: str, **details: object) -> StructuredError:
    return StructuredError(ErrorCode.BLOCKED, message, details)


def incomplete(message: str, **details: object) -> StructuredError:
    return StructuredError(ErrorCode.INCOMPLETE, message, details)


def invalid_input(message: str, **details: object) -> StructuredError:
    return StructuredError(ErrorCode.INVALID_INPUT, message, details)
