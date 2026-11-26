"""Verificaciones del muro de contención en voladizo (D-173), por etapas de la fase A.

El empuje (decisión 9) queda BLOCKED si la fórmula de la teoría declarada no vale para el muro (c' > 0 con Coulomb,
α > φ', Ko con talud); si no, la estabilidad y las presiones de cada caso de servicio y la pantalla con los casos
mayorados. Mientras la fase A está en construcción, una verificación BLOCKED dice que el talón y la puntera aún no se
verifican, para que un muro nunca quede PASS sin haberse verificado por completo.
"""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.retaining_wall.stability import stability_checks
from structurelab_rc.domain.retaining_wall.stem import stem_checks
from structurelab_rc.domain.retaining_wall.thrust import stability_thrust, stem_thrust
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

THRUST = "Empuje del relleno"
PENDING = "Verificacion del muro de contencion"
CLAUSE = "D-173"


def retaining_wall_checks(basis: Basis, wall: RetainingWall, soil: RetainingSoil) -> list[Check]:
    thrust = stability_thrust(wall, soil)
    if thrust.blocked:
        error = blocked(thrust.blocked, member=wall.id)
        checks = [Check(THRUST, Status.BLOCKED, (error,), CLAUSE, member=wall.id, note=f"plano {thrust.plane.name}")]
    else:
        checks = [*stability_checks(basis.profile, wall, soil, thrust), *stem_checks(basis, wall, stem_thrust(wall, soil))]
    message = "el talon y la puntera aun no se verifican (D-173, fase A en construccion)"
    checks.append(Check(PENDING, Status.BLOCKED, (blocked(message, member=wall.id),), CLAUSE, member=wall.id))
    return checks
