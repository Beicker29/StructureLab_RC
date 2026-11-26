"""Base del muro en voladizo (D-173, fase A, etapa 4): talón, puntera, refuerzo longitudinal, altura mínima y desarrollo
del refuerzo, por franja de 1 m de muro.

La base es una zapata en una dirección (ACI 13.3.2.1, capítulos 7 y 9; NSR-10 C.15). Cargas de cada caso mayorado, con
sus factores declarados: las mismas de la estabilidad (wall_resultant), con la presión del suelo de Bellos y Bakas que
produce la resultante mayorada (como las zapatas, D-057).

- Talón, de la cara del relleno de la pantalla al extremo: carga neta (decisión 5 de D-173) = el peso de su concreto
  (dead_factor), el suelo que la estabilidad cuenta sobre el talón (fill_factor, con la corrección de la opción b) y la
  componente vertical del empuje (earth_factor), menos la presión del suelo sobre el talón. Momento y cortante en la cara
  de la pantalla (la junta se abre, ACI R13.3.6.3; decisión del usuario, como el manual): barras superiores en tracción.
- Puntera, del borde a la cara exterior de la pantalla: la presión del suelo menos el peso de su concreto (dead_factor);
  el suelo sobre la puntera no cuenta (puede erosionarse o retirarse). Momento en la cara (ACI 13.2.7.1; NSR-10
  C.15.4.2) y cortante a d de la cara (ACI 13.2.7.2; NSR-10 C.15.5.2): barras inferiores en tracción.
- Vc de las zapatas (ACI 13.2.6.2(a); NSR-10 el mayor de C.11.2.1 y C.11.2.2, D-030), decisión del usuario. As mínimo y
  separación máxima de la zapata en una dirección; agrietamiento de las vigas; altura mínima de las zapatas.
- Longitudinal: la cuantía de retracción y temperatura sobre la sección de la base (declarada en cada cara) y su
  separación.
- Desarrollo, como el manual: las barras de la pantalla dentro de la base (espesor − recubrimiento); las superiores del
  talón y las inferiores de la puntera a cada lado de la cara de la pantalla (el lado más corto, menos el recubrimiento).

Un momento de signo contrario al de la pieza (tracción en la otra cara) queda BLOCKED: no está en la fase A.
"""

from dataclasses import replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.development import BarAnchorage, developed_end, development_check, required_length
from structurelab_rc.domain.retaining_wall.slab import (
    STRIP,
    Slab,
    flexure_checks,
    per_strip,
    reinforcement_checks,
    shear_checks,
    status,
)
from structurelab_rc.domain.retaining_wall.stability import STRIP as UNIT
from structurelab_rc.domain.retaining_wall.stability import wall_resultant
from structurelab_rc.domain.retaining_wall.thrust import Thrust
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import blocked, incomplete, invalid_input
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import SoilPressure, footing_pressure
from structurelab_rc.model.footing import BarSet
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall, WallCase

HEEL, TOE = "talon", "puntera"
HEEL_NOTE = "Talon en la cara de la pantalla (lado del relleno)"
TOE_NOTE = "Puntera en la cara exterior de la pantalla"
TOE_SHEAR_NOTE = "Puntera a d de la cara exterior de la pantalla"
LONGITUDINAL = "Refuerzo longitudinal base"
LONGITUDINAL_SPACING = "Separacion refuerzo longitudinal base"
DEPTH = "Altura minima base"
DOWEL = "Desarrollo barras de la pantalla en la base"
HEEL_DEVELOPMENT = "Desarrollo barras superiores talon"
TOE_DEVELOPMENT = "Desarrollo barras inferiores puntera"
LOADS = "Cargas de la base"


def base_checks(basis: Basis, wall: RetainingWall, soil: RetainingSoil, thrust: Thrust) -> list[Check]:
    """Las verificaciones de la base con el empuje de la estabilidad (thrust, sin factores, por mm de muro)."""
    cases = [case for case in wall.cases if case.kind == "factored"]
    if not cases:
        error = incomplete("La base no tiene casos mayorados", member=wall.id)
        checks = [Check(LOADS, Status.INCOMPLETE, (error,), basis.profile.footing.clauses()["strength"], member=wall.id)]
    else:
        checks = _strength_checks(basis, wall, soil, (thrust, cases))
    return checks + _detailing_checks(basis, wall, _service_moments(wall, soil, thrust))


def _service_moments(wall: RetainingWall, soil: RetainingSoil, thrust: Thrust) -> dict[str, float | None]:
    """El mayor momento de servicio del talón y de la puntera en la cara de la pantalla (N·mm por franja), para el
    agrietamiento; None si no hay casos de servicio con equilibrio."""
    heel: list[float] = []
    toe: list[float] = []
    for case in wall.cases:
        if case.kind != "service":
            continue
        try:
            pressure = _pressure(wall, soil, case, thrust)
        except NoEquilibrium:
            continue
        heel.append(_heel(wall, soil, case, thrust, pressure)[1] * STRIP)
        toe.append(_toe(wall, soil, case, pressure, wall.toe)[1] * STRIP)
    return {HEEL: max(heel, default=None), TOE: max(toe, default=None)}


def _pressure(wall: RetainingWall, soil: RetainingSoil, case: WallCase, thrust: Thrust) -> SoilPressure:
    """La presión del suelo con la resultante mayorada del caso (lanza NoEquilibrium si no hay equilibrio)."""
    resultant = wall_resultant(wall, soil, case, thrust)
    if resultant.n <= 0:
        raise NoEquilibrium("la carga mayorada sobre el suelo no es de compresion")
    return footing_pressure(wall.base_width, UNIT, resultant.n * UNIT, resultant.x - wall.base_width / 2, 0.0)


def _soil(pressure: SoilPressure, wall: RetainingWall, span: tuple[float, float]) -> tuple[float, float]:
    """Fuerza del suelo entre las abscisas span (mm desde el borde de la puntera) y su momento estático respecto al borde,
    por mm de muro."""
    a, b = (x - wall.base_width / 2 for x in span)
    half = UNIT / 2
    force, moment, _ = pressure.resultant(((a, -half), (b, -half), (b, half), (a, half)))
    return force / UNIT, (moment + force * wall.base_width / 2) / UNIT


def _heel(wall: RetainingWall, soil: RetainingSoil, case: WallCase, thrust: Thrust, pressure: SoilPressure) -> tuple[float, float]:
    """(Vu, Mu) del talón en la cara de la pantalla por mm de muro: positivos hacia abajo y con tracción arriba."""
    face = wall.toe + wall.stem_thickness
    concrete = soil.unit_weight_concrete * wall.base_thickness * wall.heel * case.dead_factor
    loads = ((concrete, face + wall.heel / 2), (thrust.soil_weight * case.fill_factor, thrust.soil_x),
             (thrust.inside_weight * (case.fill_factor - case.earth_factor), thrust.inside_x),
             (thrust.vertical * case.earth_factor, thrust.point[0]))
    force, moment = _soil(pressure, wall, (face, wall.base_width))
    shear = sum(load for load, _ in loads) - force
    bending = sum(load * (x - face) for load, x in loads) - (moment - force * face)
    return shear, bending


def _toe(wall: RetainingWall, soil: RetainingSoil, case: WallCase, pressure: SoilPressure, section: float) -> tuple[float, float]:
    """(Vu, Mu) de la puntera en la sección a section (mm desde el borde) por mm de muro: positivos hacia arriba y con
    tracción abajo. Fuera de la puntera (section ≤ 0), nulos."""
    if section <= 0:
        return 0.0, 0.0
    weight = soil.unit_weight_concrete * wall.base_thickness * case.dead_factor  # por mm de puntera
    force, moment = _soil(pressure, wall, (0.0, section))
    return force - weight * section, force * section - moment - weight * section**2 / 2


def _strength_checks(basis: Basis, wall: RetainingWall, soil: RetainingSoil, given: tuple[Thrust, list[WallCase]]) -> list[Check]:
    """Flexión y cortante del talón y de la puntera en cada caso mayorado."""
    thrust, cases = given
    profile = basis.profile
    clauses, footing = profile.retaining_wall.clauses(), profile.footing.clauses()
    heel = Slab(HEEL, wall.base_thickness, wall.base_cover, wall.base.top, wall.id, HEEL_NOTE)
    toe = Slab(TOE, wall.base_thickness, wall.base_cover, wall.base.bottom, wall.id, TOE_NOTE)
    _, bottom_db = per_strip(basis, wall.base.bottom)
    toe_section = wall.toe - (wall.base_thickness - wall.base_cover - bottom_db / 2)
    demands: dict[str, list[tuple[str, float, float]]] = {"heel": [], "toe": [], "toe shear": []}
    checks: list[Check] = []
    for case in cases:
        where = {"member": wall.id, "case": case.case}
        try:
            pressure = _pressure(wall, soil, case, thrust)
        except NoEquilibrium as error:
            failure = invalid_input(f"Sin equilibrio con el suelo en el caso mayorado: {error}", **where)
            checks.append(Check(LOADS, Status.FAIL, (failure,), footing["strength"], member=wall.id, case=case.case))
            continue
        demands["heel"].append((case.case, *_heel(wall, soil, case, thrust, pressure)))
        demands["toe"].append((case.case, *_toe(wall, soil, case, pressure, wall.toe)))
        demands["toe shear"].append((case.case, *_toe(wall, soil, case, pressure, toe_section)))
    flexure = (clauses["base_strength"], clauses["base_net_tensile_strain"])
    for slab, key, shear_key, shear_clause in ((heel, "heel", "heel", clauses["heel_shear"]),
                                               (toe, "toe", "toe shear", footing["one_way_shear"])):
        positive = [(case, v * STRIP, m * STRIP) for case, v, m in demands[key] if m >= 0]
        checks += [Check(f"Flexion {slab.part}", Status.BLOCKED,
                         (blocked(f"momento de signo contrario en {slab.part} (traccion en la otra cara): no esta en la "
                                  "fase A (D-173)", member=wall.id, case=case),), flexure[0], member=wall.id, case=case)
                   for case, _, m in demands[key] if m < 0]
        if positive:
            checks += flexure_checks(basis, slab, [(case, m) for case, _, m in positive], flexure)
        shears = [(case, abs(v) * STRIP, abs(m) * STRIP) for case, v, m in demands[shear_key]]
        note = TOE_SHEAR_NOTE if slab.part == TOE else slab.note
        checks += shear_checks(basis, replace(slab, note=note), shears, (profile.footing.one_way_concrete_shear, shear_clause))
    return checks


def _detailing_checks(basis: Basis, wall: RetainingWall, service: dict[str, float | None]) -> list[Check]:
    """Mínimos y separaciones de las barras de flexión (el agrietamiento con el momento de servicio de cada pieza), el
    longitudinal, la altura mínima y el desarrollo."""
    profile, materials = basis.profile, basis.materials
    clauses, footing = profile.retaining_wall.clauses(), profile.footing.clauses()
    thickness, cover, member = wall.base_thickness, wall.base_cover, wall.id
    rules = (profile.footing.min_reinforcement_ratio(materials.fy), profile.footing.combined_max_bar_spacing(thickness))
    rule_clauses = (footing["combined_min_reinforcement"], footing["combined_spacing"], clauses["base_crack_spacing"])
    checks = [check for part, bars, note in ((HEEL, wall.base.top, HEEL_NOTE), (TOE, wall.base.bottom, TOE_NOTE))
              for check in reinforcement_checks(basis, Slab(part, thickness, cover, bars, member, note),
                                                (*rules, service[part]), rule_clauses)]
    bar_area, _ = per_strip(basis, wall.base.longitudinal)
    provided = 2 * bar_area / STRIP * wall.base_width  # en cada cara, a lo ancho de la base
    required = profile.footing.shrinkage_temperature_ratio(materials.fy) * thickness * wall.base_width
    largest = profile.footing.shrinkage_temperature_max_spacing(thickness)
    _, bottom_db = per_strip(basis, wall.base.bottom)
    depth = thickness - cover - bottom_db / 2
    checks += [
        Check(LONGITUDINAL, status(provided >= required), clause=footing["shrinkage_temperature"], demand=required,
              capacity=provided, unit="mm2", note="Sobre la seccion de la base; barras en cada cara", member=member),
        Check(LONGITUDINAL_SPACING, status(wall.base.longitudinal.spacing <= largest), clause=footing["shrinkage_temperature"],
              demand=wall.base.longitudinal.spacing, capacity=largest, unit="mm", member=member),
        Check(DEPTH, status(depth >= profile.footing.min_depth()), clause=footing["min_depth"], demand=profile.footing.min_depth(),
              capacity=depth, unit="mm", note="Sobre las barras inferiores", member=member),
    ]
    return checks + _development_checks(basis, wall)


def _anchorage(basis: Basis, bars: BarSet, cover: float, concrete_below: float) -> BarAnchorage:
    """La barra que se desarrolla, con su extremo declarado: recubrimiento libre cover a la cara, a los lados y sobre la
    extensión del gancho, y concrete_below de concreto fresco bajo ella (ψt)."""
    _, diameter = per_strip(basis, bars)
    kind, angle = developed_end(bars.end)
    return BarAnchorage(diameter, kind, angle, cb=min(cover + diameter / 2, bars.spacing / 2), concrete_below=concrete_below,
                        clear_cover=cover, clear_spacing=bars.spacing - diameter, side_cover=cover, extension_cover=cover)


def _development_checks(basis: Basis, wall: RetainingWall) -> list[Check]:
    """Desarrollo de las barras de la pantalla en la base y de las de flexión de la base a cada lado de la pantalla."""
    profile, materials, level = basis.profile, basis.materials, basis.seismic_level
    cover, thickness, member = wall.base_cover, wall.base_thickness, wall.id
    _, top_db = per_strip(basis, wall.base.top)
    rows = (
        (DOWEL, _anchorage(basis, wall.stem.back, cover, 0.0), thickness - cover,
         "Dentro de la base, hasta la malla inferior: espesor menos recubrimiento"),
        (HEEL_DEVELOPMENT, _anchorage(basis, wall.base.top, cover, thickness - cover - top_db / 2),
         min(wall.heel, wall.toe + wall.stem_thickness) - cover,
         "A cada lado de la cara de la pantalla: el lado mas corto menos el recubrimiento"),
        (TOE_DEVELOPMENT, _anchorage(basis, wall.base.bottom, cover, 0.0),
         min(wall.toe, wall.stem_thickness + wall.heel) - cover,
         "A cada lado de la cara de la pantalla: el lado mas corto menos el recubrimiento"),
    )
    return [replace(development_check(name, required_length(profile, materials, bar, level), available, note), member=member)
            for name, bar, available, note in rows]
