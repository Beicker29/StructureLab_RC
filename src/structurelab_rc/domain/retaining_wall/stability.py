"""Estabilidad del muro en voladizo y presiones bajo la base con los casos de servicio (D-173), por unidad de ancho.

Fuerzas de cada caso, con sus factores declarados: el peso del concreto (pantalla y base) por dead_factor; el suelo que
cuenta como peso según el caso de empuje (todo el relleno sobre el talón, o la cuña del caso 4b) por fill_factor; y el
empuje del relleno (componentes horizontal y vertical en su punto de aplicación) por earth_factor. El peso del suelo
sobre la puntera no cuenta (puede erosionarse o retirarse).

- Volcamiento alrededor del borde de la puntera (Das 2016, §13.5): momento resistente de los pesos y de la componente
  vertical del empuje contra el momento volcador de la componente horizontal. La pasiva no se cuenta, como en las
  zapatas (D-070).
- Deslizamiento (Das 2016, §13.6): resistencia μ·N más la pasiva frente a la puntera (si se declara), sobre el espesor
  de la base desde su cara superior, contra la componente horizontal del empuje.
- Presiones: la resultante N a la distancia (Mr − Mo)/N del borde de la puntera; la presión lineal sin tracción de
  Bellos y Bakas (la de las zapatas) sobre una franja de la base, comparada con qa, y la fracción de la base en contacto
  con la mínima declarada. Sin equilibrio (N ≤ 0 o la resultante fuera de la base), las cuatro revisiones fallan.

Los nombres de las revisiones y sus numerales son los de las zapatas (13.3.1.1 y 13.2.6.1 del ACI; C.15.2.2 y el
Título H de la NSR-10).
"""

from dataclasses import dataclass

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.service import BEARING, CONTACT, CONTACT_CLAUSE
from structurelab_rc.domain.footing.stability import OVERTURNING, SLIDING
from structurelab_rc.domain.retaining_wall.thrust import Thrust
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete, invalid_input
from structurelab_rc.mechanics.earth_pressure import passive_force
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import footing_pressure
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall, WallCase

STRIP = 1.0  # mm: la franja de muro sobre la que se resuelve la presión (todo es por unidad de ancho)
REPORT_STRIP = 1000.0  # mm: la franja de 1 m en que se reportan las revisiones, como la pantalla y la base


@dataclass(frozen=True)
class WallResultant:
    """Resultante de un caso sobre la base, por unidad de ancho: N (vertical, N/mm), H (horizontal del empuje, N/mm),
    los momentos resistente y volcador alrededor del borde de la puntera (N·mm/mm), la pasiva (N/mm) y las partes de N."""

    n: float
    horizontal: float
    resisting: float
    overturning: float
    passive: float
    parts: tuple[tuple[str, float], ...]

    @property
    def x(self) -> float:
        """Distancia de la resultante al borde de la puntera (mm)."""
        return (self.resisting - self.overturning) / self.n

    def scaled(self, width: float) -> "WallResultant":
        """La misma resultante para un ancho de muro width (mm): fuerzas y momentos por width; x no cambia."""
        return WallResultant(self.n * width, self.horizontal * width, self.resisting * width, self.overturning * width,
                             self.passive * width, tuple((name, value * width) for name, value in self.parts))


def wall_resultant(wall: RetainingWall, soil: RetainingSoil, case: WallCase, thrust: Thrust) -> WallResultant:
    """Las fuerzas del caso con sus factores declarados (D-173) y sus momentos alrededor del borde de la puntera."""
    gamma = soil.unit_weight_concrete
    stem = gamma * wall.stem_thickness * wall.stem_height * case.dead_factor
    base = gamma * wall.base_width * wall.base_thickness * case.dead_factor
    # El suelo sobre el talón lleva siempre el factor del relleno (opción b de la decisión 9): la parte que P_a contiene
    # (el triángulo ABC con Chu) va con el del empuje dentro de P_a y se corrige aquí con (relleno − empuje).
    correction = thrust.inside_weight * (case.fill_factor - case.earth_factor)
    fill = thrust.soil_weight * case.fill_factor + correction
    vertical, horizontal = thrust.vertical * case.earth_factor, thrust.horizontal * case.earth_factor
    x_thrust, y_thrust = thrust.point
    resisting = (stem * (wall.toe + wall.stem_thickness / 2) + base * wall.base_width / 2
                 + thrust.soil_weight * case.fill_factor * thrust.soil_x + correction * thrust.inside_x + vertical * x_thrust)
    passive = 0.0
    if soil.passive_coefficient is not None and soil.unit_weight_front is not None:
        passive = passive_force(soil.passive_coefficient, soil.unit_weight_front, 0.0, wall.base_thickness, 0.0)
    parts = (("W pantalla", stem), ("W base", base), ("W suelo", fill), ("Pv", vertical))
    return WallResultant(stem + base + fill + vertical, horizontal, resisting, horizontal * y_thrust, passive, parts)


def stability_checks(profile: Profile, wall: RetainingWall, soil: RetainingSoil, thrust: Thrust) -> list[Check]:
    """Presión, contacto, deslizamiento y volcamiento de cada caso de servicio."""
    clauses = profile.footing.clauses()
    cases = [case for case in wall.cases if case.kind == "service"]
    if not cases:
        error = incomplete("El muro no tiene casos de servicio", member=wall.id)
        return [Check(BEARING, Status.INCOMPLETE, (error,), clauses["bearing"], member=wall.id)]
    return [check for case in cases for check in _case_checks(clauses, wall, soil, (case, wall_resultant(wall, soil, case, thrust)))]


def _case_checks(clauses: dict[str, str], wall: RetainingWall, soil: RetainingSoil,
                 given: tuple[WallCase, WallResultant]) -> list[Check]:
    """Las cuatro revisiones de un caso; las fuerzas y momentos se reportan por franja de 1 m de muro, como la pantalla
    y la base (el cálculo es por mm)."""
    case, unit_resultant = given
    resultant = unit_resultant.scaled(REPORT_STRIP)
    member, name = wall.id, case.case
    where = {"member": member, "case": name}
    width = wall.base_width
    values = (*resultant.parts, ("N", resultant.n), ("H", resultant.horizontal), ("Mr", resultant.resisting),
              ("Mo", resultant.overturning))
    try:
        if resultant.n <= 0:
            raise NoEquilibrium("la carga de servicio sobre el suelo no es de compresion")
        eccentricity = resultant.x - width / 2
        pressure = footing_pressure(width, STRIP, unit_resultant.n * STRIP, eccentricity, 0.0)
    except NoEquilibrium as error:
        failure = invalid_input(f"Sin equilibrio con el suelo: {error}", **where)
        return [Check(name, Status.FAIL, (failure,), clause, values=values, member=member, case=name)
                for name, clause in ((BEARING, clauses["bearing"]), (CONTACT, CONTACT_CLAUSE), (SLIDING, clauses["stability"]),
                                     (OVERTURNING, clauses["stability"]))]
    values += (("e", eccentricity), ("x resultante", resultant.x))
    fraction = pressure.contact_fraction()
    p_toe, p_heel = pressure.at(-width / 2, 0.0), pressure.at(width / 2, 0.0)
    friction = soil.friction_coefficient * resultant.n
    resistance = friction + resultant.passive
    sliding_ok = soil.sliding_safety_factor * resultant.horizontal <= resistance
    overturning_ok = soil.overturning_safety_factor * resultant.overturning <= resultant.resisting
    return [
        Check(BEARING, Status.PASS if pressure.pmax <= soil.allowable_pressure else Status.FAIL, clause=clauses["bearing"],
              demand=pressure.pmax, capacity=soil.allowable_pressure, unit="N/mm2",
              values=(*values, ("q puntera", p_toe), ("q talon", p_heel)), member=member, case=name),
        Check(CONTACT, Status.PASS if fraction >= soil.min_contact_fraction else Status.FAIL, clause=CONTACT_CLAUSE,
              demand=soil.min_contact_fraction, capacity=fraction, values=(*values, ("contacto", fraction)), member=member, case=name),
        Check(SLIDING, Status.PASS if sliding_ok else Status.FAIL, clause=clauses["stability"],
              demand=soil.sliding_safety_factor * resultant.horizontal, capacity=resistance, unit="N",
              values=(*values, ("mu N", friction), ("Pp", resultant.passive), ("R", resistance),
                      ("FS requerido", soil.sliding_safety_factor), *_safety(resistance, resultant.horizontal)), member=member, case=name),
        Check(OVERTURNING, Status.PASS if overturning_ok else Status.FAIL, clause=clauses["stability"],
              demand=soil.overturning_safety_factor * resultant.overturning, capacity=resultant.resisting, unit="N*mm",
              values=(*values, ("FS requerido", soil.overturning_safety_factor),
                      *_safety(resultant.resisting, resultant.overturning)),
              note="Alrededor del borde de la puntera", member=member, case=name),
    ]


def _safety(capacity: float, demand: float) -> tuple[tuple[str, float], ...]:
    """El factor de seguridad obtenido, si hay demanda."""
    return (("FS", capacity / demand),) if demand > 0 and capacity > 0 else ()
