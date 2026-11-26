"""Pantalla del muro en voladizo (D-173, fase A, etapa 3), por franja de 1 m de muro.

La pantalla es una losa en una dirección empotrada en la base (ACI 13.3.6.1; NSR-10 C.14.1.2, flexión según C.10). La
sección crítica de flexión y de cortante es la unión con la base (ACI 13.3.6.3; en la NSR-10, la misma por decisión del
usuario, como el manual ACI). Las demandas salen del empuje sobre la cara de la pantalla (stem_thrust) por el factor del
empuje de cada caso mayorado: Vu = P_h y Mu = P_h·H/3, con H la altura del relleno sobre la base; la carga axial se
desprecia (D-173). Las barras verticales de la cara del relleno resisten la flexión, con d = espesor − recubrimiento − db/2.

Verificaciones, como el ejemplo 2 del manual ACI MNL-17(21), con las de losa de slab.py: flexión (φMn ≥ Mu) y tracción
controlada; As mínimo de losa y separación máxima; separación por agrietamiento; cortante sin refuerzo de cortante
(φVc ≥ Vu) y el límite de la sección; refuerzo horizontal de cada cara (la mitad de la cuantía del perfil en cada una) y su
separación; verticales de la cara exterior (la mitad del refuerzo de retracción) y su separación.
"""

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.retaining_wall.slab import (
    STRIP,
    Slab,
    flexure_checks,
    per_strip,
    reinforcement_checks,
    shear_checks,
    status,
)
from structurelab_rc.domain.retaining_wall.thrust import Thrust
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
from structurelab_rc.model.retaining_wall import RetainingWall

PART = "pantalla"
FLEXURE = f"Flexion {PART}"
STRAIN = f"Deformacion neta de traccion {PART}"
MINIMUM = f"Acero minimo {PART}"
SPACING = f"Separacion maxima {PART}"
CRACK = f"Separacion por agrietamiento {PART}"
SHEAR = f"Cortante {PART}"
SHEAR_SECTION = f"Dimensiones de la seccion por cortante {PART}"
HORIZONTAL = "Refuerzo horizontal pantalla"
HORIZONTAL_SPACING = "Separacion refuerzo horizontal pantalla"
FRONT = "Refuerzo vertical cara exterior pantalla"
FRONT_SPACING = "Separacion vertical cara exterior pantalla"
SECTION_NOTE = "Union de la pantalla con la base"


def stem_checks(basis: Basis, wall: RetainingWall, thrust: Thrust) -> list[Check]:
    """Las verificaciones de la pantalla con el empuje sobre su cara (thrust, sin factores, por mm de muro)."""
    rules, clauses = basis.profile.retaining_wall, basis.profile.retaining_wall.clauses()
    slab = Slab(PART, wall.stem_thickness, wall.stem_cover, wall.stem.back, wall.id, SECTION_NOTE)
    cases = [case for case in wall.cases if case.kind == "factored"]
    if not cases:
        error = incomplete("La pantalla no tiene casos mayorados", member=wall.id)
        checks = [Check(FLEXURE, Status.INCOMPLETE, (error,), clauses["stem_strength"], member=wall.id)]
    else:
        arm = thrust.plane.height / 3  # sobre la cara superior de la base
        shears = [(case.case, case.earth_factor * thrust.horizontal * STRIP) for case in cases]
        checks = [
            *flexure_checks(basis, slab, [(case, vu * arm) for case, vu in shears],
                            (clauses["stem_strength"], clauses["stem_net_tensile_strain"])),
            *shear_checks(basis, slab, [(case, vu, vu * arm) for case, vu in shears],
                          (rules.stem_concrete_shear, clauses["stem_shear"])),
        ]
    service = [case.earth_factor * thrust.horizontal * STRIP * thrust.plane.height / 3
               for case in wall.cases if case.kind == "service"]
    rule_values = (rules.stem_min_reinforcement_ratio(basis.materials.fy), rules.stem_max_spacing(wall.stem_thickness),
                   max(service, default=None))
    checks += reinforcement_checks(basis, slab, rule_values,
                                   (clauses["stem_min_reinforcement"], clauses["stem_spacing"], clauses["stem_crack_spacing"]))
    return checks + _distribution_checks(basis, wall)


def _distribution_checks(basis: Basis, wall: RetainingWall) -> list[Check]:
    """Refuerzo horizontal de cada cara y verticales de la cara exterior, con sus separaciones."""
    materials, rules = basis.materials, basis.profile.retaining_wall
    clauses = rules.clauses()
    member, thickness = wall.id, wall.stem_thickness
    horizontal, horizontal_db = per_strip(basis, wall.stem.horizontal)
    each_face = rules.stem_horizontal_ratio(materials.fy, horizontal_db) * STRIP * thickness / 2
    front, _ = per_strip(basis, wall.stem.front)
    front_required = rules.stem_front_ratio(materials.fy) * STRIP * thickness
    horizontal_max, front_max = rules.stem_horizontal_max_spacing(thickness), rules.stem_front_max_spacing(thickness)
    return [
        Check(HORIZONTAL, status(horizontal >= each_face), clause=clauses["stem_horizontal"], demand=each_face,
              capacity=horizontal, unit="mm2/m", note="En cada cara: la mitad de la cuantia, sobre el area bruta", member=member),
        Check(HORIZONTAL_SPACING, status(wall.stem.horizontal.spacing <= horizontal_max), clause=clauses["stem_horizontal"],
              demand=wall.stem.horizontal.spacing, capacity=horizontal_max, unit="mm", member=member),
        Check(FRONT, status(front >= front_required), clause=clauses["stem_front"], demand=front_required, capacity=front,
              unit="mm2/m", member=member),
        Check(FRONT_SPACING, status(wall.stem.front.spacing <= front_max), clause=clauses["stem_front"],
              demand=wall.stem.front.spacing, capacity=front_max, unit="mm", member=member),
    ]
