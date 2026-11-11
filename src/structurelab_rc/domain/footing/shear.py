"""Cortante en una dirección y punzonamiento de zapatas aisladas con los casos mayorados (V3D.2; D-059, D-063).

Una dirección: sección a d de cada cara de la columna (ACI 13.2.7.2, NSR-10 C.15.5.2), con la carga neta que actúa más
allá en todo el ancho y la d de las barras de esa dirección. Dos direcciones: perímetro a d/2 con d promedio de la malla
inferior (ACI 22.6.2.1), recortado con la base (αs de 40, 30 o 20, D-059), con la fuerza y los momentos de la carga neta
fuera de él. La carga neta sale de domain/footing/loads.py; la resistencia, de domain/shear_strength.py y codes.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.footing.loads import FactoredCase, column_faces
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.shear_strength import TransferredLoad, TwoWayShear, concrete_lambda, two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import Footing, FootingBase
from structurelab_rc.model.project import Materials

PUNCHING = "Punzonamiento"
_AXES = {"x": 0, "y": 1}
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}


def _one_way(profile: Profile, materials: Materials, footing: Footing, row: BarRow, case: FactoredCase) -> Check:
    name = f"Cortante en una direccion (barras {row.direction})"
    clause = profile.footing.clauses()["one_way_shear"]
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return check_from_errors(name, [lam])
    axis = _AXES[row.direction]
    plus, minus = column_faces(footing)[row.direction]
    sides = ((case.beyond(footing, axis, plus + row.depth, 1.0), _FACES[row.direction][0]),
             (case.beyond(footing, axis, minus - row.depth, -1.0), _FACES[row.direction][1]))
    phi = profile.shear.strength_reduction()
    worst: tuple[float, float, float, str] | None = None  # razón, Vu, φVc, cara
    for (shear_force, moment), face in sides:
        vc = profile.footing.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=row.width, d=row.depth, h=footing.h,
                                                    rho_w=row.area / (row.width * row.depth), vu=abs(shear_force), mu=abs(moment))
        demand, capacity = abs(shear_force), phi * vc
        if worst is None or demand / capacity > worst[0]:
            worst = (demand / capacity, demand, capacity, face)
    assert worst is not None
    _, demand, capacity, face = worst
    return Check(name, Status.PASS if demand <= capacity else Status.FAIL, clause=clause, member=footing.id, case=case.case,
                 demand=demand, capacity=capacity, unit="N", values=(("phi", phi), ("Vc", capacity / phi), ("d", row.depth)),
                 note=f"Seccion a d de la cara {face} de la columna")


def transferred_load(column: tuple[float, float, float], case: FactoredCase, perimeter: Perimeter) -> TransferredLoad:
    """Carga que atraviesa la sección crítica: la acción de la columna expresada como carga neta equivalente (fuerza y
    momentos estáticos ∫q, ∫x·q, ∫y·q) menos la carga neta dentro del área crítica, con los momentos respecto al
    centroide del perímetro."""
    (x0, y0), (x1, y1) = perimeter.region
    inside = case.net(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    force, sx, sy = (a - b for a, b in zip(column, inside, strict=True))
    xc, yc = perimeter.centroid
    return TransferredLoad(force, sx - xc * force, sy - yc * force)


def _punching_load(footing: Footing, case: FactoredCase, perimeter: Perimeter) -> TransferredLoad:
    """En la zapata aislada, la acción de la columna equivale a la carga neta de toda la base."""
    hx, hy = footing.lx / 2, footing.ly / 2
    return transferred_load(case.net(((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))), case, perimeter)


def _punching(
    profile: Profile, materials: Materials, footing: Footing, bottom: dict[str, BarRow], case: FactoredCase
) -> tuple[TwoWayShear | StructuredError, TransferredLoad | None]:
    column = footing.column
    depth = (bottom["x"].depth + bottom["y"].depth) / 2
    hx, hy = footing.lx / 2, footing.ly / 2
    perimeter = critical_perimeter((column.offset_x, column.offset_y), column.cx, column.cy, depth, ((-hx, -hy), (hx, hy)))
    if not perimeter.sides:
        return two_way_shear(profile, materials, perimeter, (column.cx, column.cy, 1.0), TransferredLoad(0.0, 0.0, 0.0)), None
    load = _punching_load(footing, case, perimeter)
    loaded = (column.cx, column.cy, profile.footing.punching_size_factor())
    return two_way_shear(profile, materials, perimeter, loaded, load), load


@dataclass(frozen=True)
class PunchedColumn:
    """Columna que punzona: sección cx × cy centrada en (x, y), las barras inferiores de la zapata y la nota del check."""

    cx: float
    cy: float
    x: float
    y: float
    bottom: dict[str, BarRow]
    note: str


def punching_checks(basis: Basis, footing: FootingBase, column: PunchedColumn, given: tuple[TwoWayShear | StructuredError,
                    TransferredLoad | None, str]) -> list[Check]:
    """El punzonamiento de una columna y, si aplica, el acero mínimo por punzonamiento (ACI 8.6.1.2)."""
    profile, materials = basis.profile, basis.materials
    result, load, case = given
    clause = profile.shear.clauses()["punching"]
    if isinstance(result, StructuredError):
        return [Check(PUNCHING, Status.BLOCKED, (result,), clause, member=footing.id, case=case)]
    assert load is not None
    values = (("Vu", load.force), ("b0", result.perimeter.length), ("d", result.perimeter.depth), ("alpha s", result.alpha_s),
              ("gamma v x", result.gamma_v[0]), ("gamma v y", result.gamma_v[1]), ("vuv", result.vuv))
    checks = [Check(PUNCHING, Status.PASS if result.vu <= result.phi_vc else Status.FAIL, clause=clause, member=footing.id,
                    case=case, demand=result.vu, capacity=result.phi_vc, unit="MPa", values=values, note=column.note)]
    checks.extend(replace(check, case=case) for check in _punching_minimum(profile, materials, (footing, column), result))
    return checks


def _punching_checks(
    profile: Profile, materials: Materials, footing: Footing, bottom: dict[str, BarRow], case: FactoredCase
) -> list[Check]:
    result, load = _punching(profile, materials, footing, bottom, case)
    column = footing.column
    punched = PunchedColumn(column.cx, column.cy, column.offset_x, column.offset_y, bottom, "")
    return punching_checks(Basis(profile, materials, (), ""), footing, punched, (result, load, case.case))


def _punching_minimum(
    profile: Profile, materials: Materials, given: tuple[FootingBase, PunchedColumn], result: TwoWayShear
) -> list[Check]:
    """ACI 8.6.1.2 (D-059): con vuv alto, As,min en el ancho bslab alrededor de la columna, en cada dirección."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return []
    footing, column = given
    checks = []
    for direction, row in column.bottom.items():
        across = column.cy if direction == "x" else column.cx
        centre = column.y if direction == "x" else column.x
        bslab = profile.shear.effective_slab_width(across, footing.h)
        required = profile.shear.punching_min_reinforcement(
            vuv=result.vuv, fc=materials.fc, lam=lam, lam_s=profile.footing.punching_size_factor(), alpha_s=result.alpha_s,
            fy=materials.fy, b0=result.perimeter.length, bslab=bslab)
        if not required:
            continue
        provided = sum(row.bar_area for position in row.positions if abs(position - centre) <= bslab / 2 + 1e-6)
        checks.append(Check(f"Acero minimo por punzonamiento (barras {direction})", Status.PASS if provided >= required else Status.FAIL,
                            clause=profile.footing.clauses()["punching_min_reinforcement"], member=footing.id,
                            demand=required, capacity=provided, unit="mm2", values=(("bslab", bslab),), note=column.note))
    return checks


def shear_checks(
    profile: Profile, materials: Materials, footing: Footing, cases: list[FactoredCase], bars: Sequence[RebarSpec]
) -> list[Check]:
    bottom = mat_rows(footing, footing.bottom, bars)
    checks: list[Check] = []
    for case in cases:
        checks.extend(_one_way(profile, materials, footing, bottom[direction], case) for direction in ("x", "y"))
        checks.extend(_punching_checks(profile, materials, footing, bottom, case))
    return checks
