"""Pantalla del muro en voladizo (D-173, fase A, etapa 3), por franja de 1 m de muro.

La pantalla es una losa en una dirección empotrada en la base (ACI 13.3.6.1; NSR-10 C.14.1.2, flexión según C.10). La
sección crítica de flexión y de cortante es la unión con la base (ACI 13.3.6.3; en la NSR-10, la misma por decisión del
usuario, como el manual ACI). Las demandas salen del empuje sobre la cara de la pantalla (stem_thrust) por el factor del
empuje de cada caso mayorado: Vu = P_h y Mu = P_h·H/3, con H la altura del relleno sobre la base; la carga axial se
desprecia (D-173). Las barras verticales de la cara del relleno resisten la flexión, con d = espesor − recubrimiento − db/2.

Verificaciones, como el ejemplo 2 del manual ACI MNL-17(21): flexión (φMn ≥ Mu) y tracción controlada; As mínimo de
losa y separación máxima; separación por agrietamiento; cortante del concreto (φVc ≥ Vu, sin estribos); refuerzo
horizontal de cada cara (la mitad de la cuantía del perfil en cada una) y su separación; verticales de la cara exterior
(la mitad del refuerzo de retracción) y su separación.
"""

from dataclasses import replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import RectangularSection, net_tensile_strain_check, rectangular_strength
from structurelab_rc.domain.retaining_wall.thrust import Thrust
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, incomplete
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.model.footing import BarSet
from structurelab_rc.model.retaining_wall import RetainingWall

STRIP = 1000.0  # mm: la franja de muro de las verificaciones de la pantalla
FLEXURE = "Flexion pantalla"
STRAIN = "Deformacion neta de traccion pantalla"
MINIMUM = "Acero minimo pantalla"
SPACING = "Separacion maxima pantalla"
CRACK = "Separacion por agrietamiento pantalla"
SHEAR = "Cortante pantalla"
SHEAR_SECTION = "Dimensiones de la seccion por cortante pantalla"
HORIZONTAL = "Refuerzo horizontal pantalla"
HORIZONTAL_SPACING = "Separacion refuerzo horizontal pantalla"
FRONT = "Refuerzo vertical cara exterior pantalla"
FRONT_SPACING = "Separacion vertical cara exterior pantalla"
SECTION_NOTE = "Union de la pantalla con la base"


def _per_strip(basis: Basis, bar_set: BarSet) -> tuple[float, float]:
    """(área por franja en mm², diámetro en mm) de un grupo de barras."""
    spec = next(bar for bar in basis.bars if bar.designation == bar_set.designation)
    return spec.area_mm2 * STRIP / bar_set.spacing, spec.diameter_mm


def _status(ok: bool) -> Status:
    return Status.PASS if ok else Status.FAIL


def stem_checks(basis: Basis, wall: RetainingWall, thrust: Thrust) -> list[Check]:
    """Las verificaciones de la pantalla con el empuje sobre su cara (thrust, sin factores, por mm de muro)."""
    profile, materials = basis.profile, basis.materials
    rules, clauses = profile.retaining_wall, profile.retaining_wall.clauses()
    member, thickness = wall.id, wall.stem_thickness
    area, diameter = _per_strip(basis, wall.stem.back)
    depth = thickness - wall.stem_cover - diameter / 2
    checks = [*_strength_checks(basis, wall, thrust, (area, depth)), *_shear_checks(basis, wall, thrust, (area, depth))]
    minimum = rules.stem_min_reinforcement_ratio(materials.fy) * STRIP * thickness
    largest = rules.stem_max_spacing(thickness)
    crack = profile.flexure.crack_control_spacing(materials.fy, wall.stem_cover)
    spacing = wall.stem.back.spacing
    checks += [
        Check(MINIMUM, _status(area >= minimum), clause=clauses["stem_min_reinforcement"], demand=minimum, capacity=area,
              unit="mm2/m", member=member),
        Check(SPACING, _status(spacing <= largest), clause=clauses["stem_spacing"], demand=spacing, capacity=largest, unit="mm",
              member=member),
        Check(CRACK, _status(spacing <= crack), clause=clauses["stem_crack_spacing"], demand=spacing, capacity=crack, unit="mm",
              values=(("cc", wall.stem_cover), ("fy", materials.fy)), member=member),
    ]
    return checks + _distribution_checks(basis, wall)


def _strength_checks(basis: Basis, wall: RetainingWall, thrust: Thrust, steel: tuple[float, float]) -> list[Check]:
    """Flexión por caso mayorado y la tracción controlada de la sección."""
    profile, materials = basis.profile, basis.materials
    clauses = profile.retaining_wall.clauses()
    area, depth = steel
    member = wall.id
    strength = rectangular_strength(profile, materials, RectangularSection(STRIP, wall.stem_thickness), (SteelLayer(depth, area),))
    if isinstance(strength, StructuredError):
        return [replace(check_from_errors(FLEXURE, [strength]), clause=clauses["stem_strength"], member=member)]
    cases = [case for case in wall.cases if case.kind == "factored"]
    if not cases:
        error = incomplete("La pantalla no tiene casos mayorados", member=member)
        return [Check(FLEXURE, Status.INCOMPLETE, (error,), clauses["stem_strength"], member=member)]
    arm = thrust.plane.height / 3  # sobre la cara superior de la base
    values = (("phi", strength.phi), ("Mn", strength.nominal), ("b", STRIP), ("h", wall.stem_thickness), ("d", depth),
              ("As", area), ("fc", materials.fc), ("fy", materials.fy), ("a", strength.state.a), ("c", strength.state.c),
              ("et", strength.state.extreme_strain))
    checks = []
    for case in cases:
        demand = case.earth_factor * thrust.horizontal * arm * STRIP
        checks.append(Check(FLEXURE, _status(strength.design >= demand), clause=clauses["stem_strength"], demand=demand,
                            capacity=strength.design, unit="N*mm", values=values, note=SECTION_NOTE, member=member,
                            case=case.case))
    strain = net_tensile_strain_check(STRAIN, clauses["stem_net_tensile_strain"], profile, materials, strength.state.extreme_strain)
    return [*checks, replace(strain, member=member)]


def _shear_checks(basis: Basis, wall: RetainingWall, thrust: Thrust, steel: tuple[float, float]) -> list[Check]:
    """Cortante por caso mayorado, en la unión con la base, sin refuerzo de cortante: Vu ≤ φVc (Vn = Vc, con Vc del perfil
    según Vu, Mu y ρw del caso) y el límite de dimensiones de la sección (ACI 22.5.1.2; NSR-10 C.11.4.7.9), el mismo que
    usan las vigas."""
    profile, materials = basis.profile, basis.materials
    clause = profile.retaining_wall.clauses()["stem_shear"]
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return [replace(check_from_errors(SHEAR, [lam]), clause=clause, member=wall.id)]
    area, depth = steel
    rho_w = area / (STRIP * depth)
    phi = profile.shear.strength_reduction()
    checks = []
    for case in wall.cases:
        if case.kind != "factored":
            continue
        demand = case.earth_factor * thrust.horizontal * STRIP
        vc = profile.retaining_wall.stem_concrete_shear(fc=materials.fc, lam=lam, bw=STRIP, d=depth, h=wall.stem_thickness,
                                                        rho_w=rho_w, vu=demand, mu=demand * thrust.plane.height / 3)
        section = phi * (vc + profile.shear.max_steel_shear(materials.fc, STRIP, depth))
        values = (("phi", phi), ("Vc", vc), ("bw", STRIP), ("d", depth), ("rho w", rho_w), ("lambda", lam),
                  ("fc", materials.fc))
        checks += [Check(SHEAR, _status(demand <= phi * vc), clause=clause, demand=demand, capacity=phi * vc, unit="N",
                         values=values, note=f"{SECTION_NOTE}; sin refuerzo de cortante, Vn = Vc", member=wall.id,
                         case=case.case),
                   Check(SHEAR_SECTION, _status(demand <= section), clause=profile.shear.clauses()["section"], demand=demand,
                         capacity=section, unit="N", values=values, note=SECTION_NOTE, member=wall.id, case=case.case)]
    return checks


def _distribution_checks(basis: Basis, wall: RetainingWall) -> list[Check]:
    """Refuerzo horizontal de cada cara y verticales de la cara exterior, con sus separaciones."""
    materials, rules = basis.materials, basis.profile.retaining_wall
    clauses = rules.clauses()
    member, thickness = wall.id, wall.stem_thickness
    horizontal, horizontal_db = _per_strip(basis, wall.stem.horizontal)
    each_face = rules.stem_horizontal_ratio(materials.fy, horizontal_db) * STRIP * thickness / 2
    front, _ = _per_strip(basis, wall.stem.front)
    front_required = rules.stem_front_ratio(materials.fy) * STRIP * thickness
    horizontal_max, front_max = rules.stem_horizontal_max_spacing(thickness), rules.stem_front_max_spacing(thickness)
    return [
        Check(HORIZONTAL, _status(horizontal >= each_face), clause=clauses["stem_horizontal"], demand=each_face,
              capacity=horizontal, unit="mm2/m", note="En cada cara: la mitad de la cuantia, sobre el area bruta", member=member),
        Check(HORIZONTAL_SPACING, _status(wall.stem.horizontal.spacing <= horizontal_max), clause=clauses["stem_horizontal"],
              demand=wall.stem.horizontal.spacing, capacity=horizontal_max, unit="mm", member=member),
        Check(FRONT, _status(front >= front_required), clause=clauses["stem_front"], demand=front_required, capacity=front,
              unit="mm2/m", member=member),
        Check(FRONT_SPACING, _status(wall.stem.front.spacing <= front_max), clause=clauses["stem_front"],
              demand=wall.stem.front.spacing, capacity=front_max, unit="mm", member=member),
    ]
