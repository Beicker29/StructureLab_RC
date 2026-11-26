"""Losa en una dirección por franja de 1 m de muro (D-173): las verificaciones que comparten la pantalla, el talón y la
puntera. Cada pieza da su espesor, su recubrimiento, las barras en tracción, sus demandas por caso mayorado y sus
numerales; aquí se arman las revisiones con las funciones del perfil (flexión de sección rectangular, deformación neta,
agrietamiento, cortante y límite de dimensiones de la sección)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import RectangularSection, net_tensile_strain_check, rectangular_strength
from structurelab_rc.domain.shear_strength import concrete_lambda
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.mechanics.flexure import SteelLayer, cracked_steel_stress
from structurelab_rc.model.footing import BarSet

STRIP = 1000.0  # mm: la franja de muro de las verificaciones


# Vc del perfil para la pieza (en N), con la firma de las zapatas: fc, lam, bw, d, h, rho_w, vu y mu por nombre.
ConcreteShear = Callable[..., float]


@dataclass(frozen=True)
class Slab:
    """Una pieza del muro como losa en una dirección: part (pantalla, talon o puntera, para los nombres), espesor y
    recubrimiento libre (mm), las barras en tracción, el miembro y la nota de la sección crítica."""

    part: str
    thickness: float
    cover: float
    bars: BarSet
    member: str
    note: str


@dataclass(frozen=True)
class Steel:
    """Las barras en tracción por franja: área (mm²), diámetro y d (mm)."""

    area: float
    diameter: float
    depth: float


def status(ok: bool) -> Status:
    return Status.PASS if ok else Status.FAIL


def per_strip(basis: Basis, bar_set: BarSet) -> tuple[float, float]:
    """(área por franja en mm², diámetro en mm) de un grupo de barras."""
    spec = next(bar for bar in basis.bars if bar.designation == bar_set.designation)
    return spec.area_mm2 * STRIP / bar_set.spacing, spec.diameter_mm


def steel(basis: Basis, slab: Slab) -> Steel:
    """Las barras en tracción de la pieza, con d = espesor − recubrimiento − db/2."""
    area, diameter = per_strip(basis, slab.bars)
    return Steel(area, diameter, slab.thickness - slab.cover - diameter / 2)


def flexure_checks(basis: Basis, slab: Slab, demands: Sequence[tuple[str, float]], clauses: tuple[str, str]) -> list[Check]:
    """Flexión de cada caso (case, Mu en N·mm por franja) y la deformación neta de tracción de la sección."""
    profile, materials = basis.profile, basis.materials
    strength_clause, strain_clause = clauses
    name, member = f"Flexion {slab.part}", slab.member
    bars = steel(basis, slab)
    strength = rectangular_strength(profile, materials, RectangularSection(STRIP, slab.thickness),
                                    (SteelLayer(bars.depth, bars.area),))
    if isinstance(strength, StructuredError):
        return [replace(check_from_errors(name, [strength]), clause=strength_clause, member=member)]
    values = (("phi", strength.phi), ("Mn", strength.nominal), ("b", STRIP), ("h", slab.thickness), ("d", bars.depth),
              ("As", bars.area), ("fc", materials.fc), ("fy", materials.fy), ("a", strength.state.a), ("c", strength.state.c),
              ("et", strength.state.extreme_strain))
    checks = [Check(name, status(strength.design >= demand), clause=strength_clause, demand=demand, capacity=strength.design,
                    unit="N*mm", values=values, note=slab.note, member=member, case=case)
              for case, demand in demands]
    strain = net_tensile_strain_check(f"Deformacion neta de traccion {slab.part}", strain_clause, profile, materials,
                                      strength.state.extreme_strain)
    return [*checks, replace(strain, member=member)]


def service_stress(basis: Basis, slab: Slab, moment: float | None) -> float | None:
    """fs de las barras en tracción con el mayor momento de servicio (N·mm por franja), sección fisurada elástica con
    n = Es/Ec del perfil; None sin momento de servicio positivo (el perfil toma entonces fs = 2/3·fy)."""
    if moment is None or moment <= 0:
        return None
    assumptions = basis.profile.strength_assumptions
    bars = steel(basis, slab)
    ratio = assumptions.steel_modulus() / assumptions.concrete_modulus(basis.materials.fc)
    return cracked_steel_stress(moment, STRIP, bars.depth, bars.area, ratio)


def reinforcement_checks(basis: Basis, slab: Slab, given: tuple[float, float, float | None],
                         clauses: tuple[str, str, str]) -> list[Check]:
    """Acero mínimo, separación máxima y separación por agrietamiento de las barras en tracción; given = (cuantía
    mínima sobre el área bruta, separación máxima en mm, del perfil, y el mayor momento de servicio en N·mm por franja o
    None): el agrietamiento usa fs calculado con ese momento (decisión del usuario, D-173) o, sin él, 2/3·fy."""
    profile, materials = basis.profile, basis.materials
    ratio, largest, moment = given
    minimum_clause, spacing_clause, crack_clause = clauses
    area, _ = per_strip(basis, slab.bars)
    minimum = ratio * STRIP * slab.thickness
    fs = service_stress(basis, slab, moment)
    crack = profile.flexure.crack_control_spacing(materials.fy, slab.cover, fs)
    crack_values = (("cc", slab.cover), ("fy", materials.fy),
                    *((("Ms", moment), ("fs", fs)) if fs is not None and moment is not None else ()))
    crack_note = "fs con el momento de servicio, seccion fisurada elastica" if fs is not None else "fs = 2/3 fy"
    spacing, member = slab.bars.spacing, slab.member
    return [
        Check(f"Acero minimo {slab.part}", status(area >= minimum), clause=minimum_clause, demand=minimum, capacity=area,
              unit="mm2/m", member=member),
        Check(f"Separacion maxima {slab.part}", status(spacing <= largest), clause=spacing_clause, demand=spacing,
              capacity=largest, unit="mm", member=member),
        Check(f"Separacion por agrietamiento {slab.part}", status(spacing <= crack), clause=crack_clause, demand=spacing,
              capacity=crack, unit="mm", values=crack_values, note=crack_note, member=member),
    ]


def shear_checks(basis: Basis, slab: Slab, demands: Sequence[tuple[str, float, float]], given: tuple[ConcreteShear, str]) -> list[Check]:
    """Cortante sin refuerzo de cortante de cada caso (case, Vu y Mu en la sección, en N y N·mm por franja): Vu ≤ φVc
    (Vn = Vc, con la Vc del perfil para la pieza) y el límite de dimensiones de la sección (ACI 22.5.1.2; NSR-10
    C.11.4.7.9), el mismo de las vigas; given = (Vc de la pieza, su numeral)."""
    profile, materials = basis.profile, basis.materials
    concrete_shear, clause = given
    name, member = f"Cortante {slab.part}", slab.member
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return [replace(check_from_errors(name, [lam]), clause=clause, member=member)]
    bars = steel(basis, slab)
    rho_w = bars.area / (STRIP * bars.depth)
    phi = profile.shear.strength_reduction()
    checks = []
    for case, vu, mu in demands:
        vc = concrete_shear(fc=materials.fc, lam=lam, bw=STRIP, d=bars.depth, h=slab.thickness, rho_w=rho_w, vu=vu, mu=mu)
        section = phi * (vc + profile.shear.max_steel_shear(materials.fc, STRIP, bars.depth))
        values = (("phi", phi), ("Vc", vc), ("bw", STRIP), ("d", bars.depth), ("rho w", rho_w), ("lambda", lam),
                  ("fc", materials.fc))
        checks += [Check(name, status(vu <= phi * vc), clause=clause, demand=vu, capacity=phi * vc, unit="N", values=values,
                         note=f"{slab.note}; sin refuerzo de cortante, Vn = Vc", member=member, case=case),
                   Check(f"Dimensiones de la seccion por cortante {slab.part}", status(vu <= section),
                         clause=profile.shear.clauses()["section"], demand=vu, capacity=section, unit="N", values=values,
                         note=slab.note, member=member, case=case)]
    return checks
