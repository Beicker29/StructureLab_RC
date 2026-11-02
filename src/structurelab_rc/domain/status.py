"""Estados de verificación y su única agregación."""

from collections.abc import Iterable
from enum import StrEnum


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"


_PRECEDENCE = (Status.FAIL, Status.INCOMPLETE, Status.BLOCKED, Status.PASS)


def aggregate(statuses: Iterable[Status]) -> Status:
    """Devuelve el estado que prevalece; sin verificaciones el resultado es INCOMPLETE."""
    present = set(statuses)
    if not present:
        return Status.INCOMPLETE
    return next(status for status in _PRECEDENCE if status in present)
