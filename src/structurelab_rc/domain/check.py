"""Resultado de una verificación."""

from collections.abc import Iterable
from dataclasses import dataclass

from structurelab_rc.domain.status import Status, aggregate
from structurelab_rc.errors import ErrorCode, StructuredError

_STATUS_BY_CODE = {
    ErrorCode.BLOCKED: Status.BLOCKED,
    ErrorCode.INCOMPLETE: Status.INCOMPLETE,
    ErrorCode.INVALID_INPUT: Status.FAIL,
}


@dataclass(frozen=True)
class Check:
    """Demanda y capacidad en unidades internas; unit las nombra para la presentación."""

    name: str
    status: Status
    errors: tuple[StructuredError, ...] = ()
    clause: str = ""
    member: str = ""
    x: float | None = None
    demand: float | None = None
    capacity: float | None = None
    unit: str = ""
    values: tuple[tuple[str, float], ...] = ()
    note: str = ""


def check_from_errors(name: str, errors: Iterable[StructuredError]) -> Check:
    """Sin errores la verificación pasa; con ellos, prevalece el estado más severo."""
    found = tuple(errors)
    status = aggregate(_STATUS_BY_CODE[error.code] for error in found) if found else Status.PASS
    return Check(name, status, found)
