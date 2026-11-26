"""Verificaciones del muro de contención en voladizo (D-173), por etapas de la fase A.

Hoy: el empuje (decisión 9), BLOCKED si la teoría declarada no vale para el muro, y una verificación BLOCKED que dice
que la estabilidad, las presiones, la pantalla, el talón y la puntera aún no se verifican, para que un muro nunca quede
PASS sin haberse verificado. Las etapas siguientes reemplazan esa verificación por las suyas.
"""

from structurelab_rc.domain.check import Check
from structurelab_rc.domain.retaining_wall.thrust import stability_thrust, stem_thrust
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

THRUST = "Empuje del relleno"
PENDING = "Verificacion del muro de contencion"
CLAUSE = "D-173"


def retaining_wall_checks(wall: RetainingWall, soil: RetainingSoil) -> list[Check]:
    checks = []
    for thrust in (stability_thrust(wall, soil), stem_thrust(wall, soil)):
        if thrust.blocked:
            error = blocked(thrust.blocked, member=wall.id)
            checks.append(Check(THRUST, Status.BLOCKED, (error,), CLAUSE, member=wall.id, note=f"plano {thrust.plane}"))
            break
    message = ("la estabilidad, las presiones, la pantalla, el talon y la puntera aun no se verifican (D-173, fase A en "
               "construccion)")
    checks.append(Check(PENDING, Status.BLOCKED, (blocked(message, member=wall.id),), CLAUSE, member=wall.id))
    return checks
