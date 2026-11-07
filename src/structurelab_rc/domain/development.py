"""Longitud de desarrollo requerida, común a todos los elementos (zapatas ahora, vigas en la Fase 5): una sola fuente.

Cada elemento calcula la longitud disponible y el confinamiento cb; aquí se elige la ecuación del perfil según cómo
termina la barra (recta o con gancho estándar) o si trabaja a compresión, y se arma el Check.
"""

from typing import Literal

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.model.project import Materials


def required_length(
    profile: Profile, materials: Materials, db: float, end: Literal["straight", "hook", "compression"], confinement: tuple[float, float]
) -> tuple[float, str] | StructuredError:
    """Longitud requerida (mm) y numeral. confinement = (cb, concreto fresco bajo la barra), solo para barras rectas."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return lam
    development, fy, fc = profile.development, materials.fy, materials.fc
    if end == "hook":
        return development.hook_development_length(fy=fy, fc=fc, lam=lam, db=db), development.clauses()["hook"]
    if end == "compression":
        return development.compression_development_length(fy=fy, fc=fc, lam=lam, db=db), development.clauses()["compression"]
    cb, below = confinement
    length = development.tension_development_length(fy=fy, fc=fc, lam=lam, db=db, cb=cb, concrete_below=below)
    return length, development.clauses()["tension"]


def development_check(name: str, required: tuple[float, str] | StructuredError, available: float, note: str = "") -> Check:
    """Longitud requerida frente a la disponible."""
    if isinstance(required, StructuredError):
        return check_from_errors(name, [required])
    length, clause = required
    return Check(name, Status.PASS if length <= available else Status.FAIL, clause=clause, demand=length, capacity=available,
                 unit="mm", note=note)
