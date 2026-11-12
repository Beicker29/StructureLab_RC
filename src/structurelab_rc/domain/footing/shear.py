"""Cortante en una dirección y punzonamiento de zapatas aisladas con los casos mayorados (V3D.2; D-059, D-063).

Una dirección: sección a d de cada cara de la columna (ACI 13.2.7.2, NSR-10 C.15.5.2), con la carga neta que actúa más
allá en todo el ancho y la d de las barras de esa dirección. Dos direcciones: perímetro a d/2 con d promedio de la malla
inferior (ACI 22.6.2.1), recortado con la base (αs de 40, 30 o 20, D-059), con la fuerza y los momentos de la carga neta
fuera de él. La carga neta sale de domain/footing/loads.py; la resistencia, de domain/shear_strength.py y codes.
"""

from dataclasses import dataclass, field, replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import MomentStrength, RectangularSection, rectangular_strength
from structurelab_rc.domain.footing.loads import FactoredCase, column_faces
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.plain_strength import plain_rectangular_moment
from structurelab_rc.domain.shear_strength import TransferredLoad, TwoWayShear, concrete_lambda, two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter
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
                 demand=demand, capacity=capacity, unit="N",
                 values=(("phi", phi), ("Vc", capacity / phi), ("bw", row.width), ("d", row.depth),
                         ("rho w", row.area / (row.width * row.depth)), ("lambda", lam), ("fc", materials.fc)),
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
    """Columna (o grupo) que punzona: área cargada cx × cy centrada en (x, y), las filas de barras inferiores de cada
    dirección (la malla y, en la combinada, el refuerzo band), la nota de sus checks y una nota extra para el acero mínimo
    por punzonamiento. labels nombra las barras de cada dirección en las verificaciones (por omisión "barras x" y
    "barras y"; la zapata combinada, por su dirección principal y secundaria, D-101)."""

    cx: float
    cy: float
    x: float
    y: float
    bottom: dict[str, tuple[BarRow, ...]]
    note: str
    minimum_note: str = ""
    top: dict[str, tuple[BarRow, ...]] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)

    def bars(self, direction: str) -> str:
        return self.labels.get(direction, f"barras {direction}")


def punching_checks(basis: Basis, footing: FootingBase, column: PunchedColumn, given: tuple[TwoWayShear | StructuredError,
                    TransferredLoad | None, str]) -> list[Check]:
    """El punzonamiento de una columna y, si aplica, el acero mínimo por punzonamiento (ACI 8.6.1.2)."""
    profile, materials = basis.profile, basis.materials
    result, load, case = given
    clause = profile.shear.clauses()["punching"]
    if isinstance(result, StructuredError):
        return [Check(PUNCHING, Status.BLOCKED, (result,), clause, member=footing.id, case=case)]
    assert load is not None
    xc, yc = result.perimeter.centroid
    values: tuple[tuple[str, float], ...] = (
        ("Vu", load.force), ("b0", result.perimeter.length), ("d", result.perimeter.depth), ("alpha s", result.alpha_s),
        ("gamma v x", result.gamma_v[0]), ("gamma v y", result.gamma_v[1]), ("vuv", result.vuv),
        ("Msc x", load.moment_along_x), ("Msc y", load.moment_along_y), ("Jc x", result.jc[0]), ("Jc y", result.jc[1]),
        ("xc", xc), ("yc", yc))
    # Esfuerzo en cada esquina del perímetro (cortante directo más el del momento transferido); gobierna la mayor.
    for index, (x, y, stress) in enumerate(result.corners, start=1):
        values += ((f"esquina {index} x", x), (f"esquina {index} y", y), (f"esquina {index} v", stress))
    checks = [Check(PUNCHING, Status.PASS if result.vu <= result.phi_vc else Status.FAIL, clause=clause, member=footing.id,
                    case=case, demand=result.vu, capacity=result.phi_vc, unit="MPa", values=values, note=column.note)]
    checks.extend(replace(check, case=case) for check in _punching_minimum(profile, materials, (footing, column), result))
    checks.extend(replace(check, case=case) for check in _transfer_checks(profile, materials, (footing, column), (result, load)))
    checks.extend(replace(check, case=case) for check in _negative_transfer_checks(basis, (footing, column), (result, load)))
    return checks


def _negative_transfer_checks(basis: Basis, given: tuple[FootingBase, PunchedColumn],
                              results: tuple[TwoWayShear, TransferredLoad]) -> list[Check]:
    """Parte negativa de γf·Msc (D-087): la resiste la malla superior dentro de bslab; si no la hay, el concreto simple en
    bslab si el nivel sísmico lo permite (D-072); si no alcanza, la debe tomar la viga de cimentación, que el programa no
    diseña: la verificación cumple con aviso y reporta el momento para la viga."""
    profile, materials = basis.profile, basis.materials
    footing, column = given
    result, load = results
    checks = []
    for axis, direction in enumerate(column.bottom):
        msc = load.moment_along_x if direction == "x" else load.moment_along_y
        demand = (1 - result.gamma_v[axis]) * abs(msc)
        slab = slab_limits(profile, footing, column, direction)
        bslab = slab[2]
        top = column.top.get(direction, ())
        area = _in_slab(top, slab)
        capacity, source = 0.0, ""
        if area > 0:
            strength = rectangular_strength(profile, materials, RectangularSection(bslab, footing.h), (SteelLayer(top[0].depth, area),))
            capacity, source = (strength.design if isinstance(strength, MomentStrength) else 0.0), "malla superior dentro de bslab"
        elif profile.plain.permitted_in_foundations(basis.seismic_level):
            plain = plain_rectangular_moment(profile, materials, bslab, footing.h, cast_against_soil=True)
            capacity, source = (0.0 if isinstance(plain, StructuredError) else plain.design), "concreto simple dentro de bslab"
        resisted = demand <= capacity
        beam = 0.0 if resisted else demand
        who = f"la resiste la {source}" if resisted else (
            f"debe tomarla la viga de cimentacion: gamma f Msc = {demand / 1e6:.1f} kN-m (no se verifica aqui)")
        note = (f"{column.note}: " if column.note else "") + who
        # Si la toma la viga, la verificación no tiene razón demanda/capacidad en la zapata (cumple con aviso).
        checks.append(Check(f"Transferencia de momento: parte negativa ({column.bars(direction)})", Status.PASS,
                            clause=profile.footing.clauses()["moment_transfer"], member=footing.id,
                            demand=demand if resisted else None, capacity=capacity, unit="N*mm",
                            values=(("gamma f Msc", demand), *_slab_values(slab), ("para la viga", beam)), note=note))
    return checks


Slab = tuple[float, float, float, float]  # (desde, hasta, ancho bslab, ancho sin recortar)


def slab_limits(profile: Profile, footing: FootingBase, column: PunchedColumn, direction: str) -> Slab:
    """bslab de las barras de una dirección: la columna (o el grupo) más 1.5h a cada lado (ACI 8.4.2.2.3, NSR-10
    C.13.5.3.2), sin pasar de los bordes de la zapata (D-102): a cada lado se toma el menor entre 1.5h y la distancia de
    la cara al borde. Las barras x se cuentan a lo ancho de Y; las y, a lo largo de X."""
    across, centre = (column.cy, column.y) if direction == "x" else (column.cx, column.x)
    edge = (footing.ly if direction == "x" else footing.lx) / 2
    nominal = profile.shear.effective_slab_width(across, footing.h)
    low, high = max(centre - nominal / 2, -edge), min(centre + nominal / 2, edge)
    return low, high, high - low, nominal


def _slab_values(slab: Slab) -> tuple[tuple[str, float], ...]:
    """bslab y, si el borde lo recorta, el ancho sin recortar."""
    _, _, width, nominal = slab
    return (("bslab", width),) + ((("bslab sin recortar", nominal),) if width < nominal - 1e-6 else ())


def _in_slab(rows: tuple[BarRow, ...], slab: Slab) -> float:
    """Área de las barras de las filas que caen dentro de bslab, en mm²."""
    low, high = slab[0], slab[1]
    return sum(row.bar_area for row in rows for position in row.positions if low - 1e-6 <= position <= high + 1e-6)


def _transfer_checks(profile: Profile, materials: Materials, given: tuple[FootingBase, PunchedColumn],
                     results: tuple[TwoWayShear, TransferredLoad]) -> list[Check]:
    """Transferencia de momento por flexión (ACI 8.4.2.2, NSR-10 C.11.11.7.1 y C.13.5.3; D-087): en cada dirección, la
    fracción γf·Msc del momento transferido se compara con φMn de la malla inferior dentro de bslab (y el band en la
    combinada). Es una revisión de capacidad de transferencia y de concentración de refuerzo: γf·Msc no se suma al
    momento de la zapata. Se reporta para que el analista lleve su parte negativa a la viga de cimentación."""
    footing, column = given
    result, load = results
    checks = []
    for axis, (direction, rows) in enumerate(column.bottom.items()):
        msc = load.moment_along_x if direction == "x" else load.moment_along_y
        gamma_f = 1 - result.gamma_v[axis]
        slab = slab_limits(profile, footing, column, direction)
        bslab = slab[2]
        area = _in_slab(rows, slab)
        demand = gamma_f * abs(msc)
        name = f"Transferencia de momento por flexion ({column.bars(direction)})"
        values: tuple[tuple[str, float], ...] = (("gamma f", gamma_f), ("Msc", msc), ("gamma f Msc", gamma_f * msc),
                                                 *_slab_values(slab), ("As bslab", area), ("d", rows[0].depth))
        capacity = 0.0
        if area > 0:
            strength = rectangular_strength(profile, materials, RectangularSection(bslab, footing.h), (SteelLayer(rows[0].depth, area),))
            if isinstance(strength, MomentStrength):
                capacity = strength.design
                values += (("phi", strength.phi), ("Mn", strength.nominal))
        note = (f"{column.note}: " if column.note else "") + (
            "malla inferior dentro de bslab; la parte negativa de gamma f Msc la debe tomar la viga de cimentacion (no se "
            "suma al momento de la zapata)")
        checks.append(Check(name, Status.PASS if demand <= capacity else Status.FAIL, clause=profile.footing.clauses()["moment_transfer"],
                            member=footing.id, demand=demand, capacity=capacity, unit="N*mm", values=values, note=note))
    return checks


def _punching_checks(
    profile: Profile, materials: Materials, footing: Footing, rows: tuple[dict[str, BarRow], dict[str, BarRow] | None],
    given: tuple[FactoredCase, str]
) -> list[Check]:
    case, seismic_level = given
    bottom = rows[0]
    result, load = _punching(profile, materials, footing, bottom, case)
    column = footing.column
    top: dict[str, tuple[BarRow, ...]] = {} if rows[1] is None else {key: (row,) for key, row in rows[1].items()}
    punched = PunchedColumn(column.cx, column.cy, column.offset_x, column.offset_y, {key: (row,) for key, row in bottom.items()}, "",
                            top=top)
    return punching_checks(Basis(profile, materials, (), seismic_level), footing, punched, (result, load, case.case))


def _punching_minimum(
    profile: Profile, materials: Materials, given: tuple[FootingBase, PunchedColumn], result: TwoWayShear
) -> list[Check]:
    """ACI 8.6.1.2 (D-059): con vuv alto, As,min en el ancho bslab alrededor de la columna, en cada dirección."""
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, StructuredError):
        return []
    footing, column = given
    checks = []
    for direction, rows in column.bottom.items():
        slab = slab_limits(profile, footing, column, direction)
        bslab = slab[2]
        required = profile.shear.punching_min_reinforcement(
            vuv=result.vuv, fc=materials.fc, lam=lam, lam_s=profile.footing.punching_size_factor(), alpha_s=result.alpha_s,
            fy=materials.fy, b0=result.perimeter.length, bslab=bslab)
        if not required:
            continue
        provided = _in_slab(rows, slab)
        note = "; ".join(text for text in (column.note, column.minimum_note) if text)
        checks.append(Check(f"Acero minimo por punzonamiento ({column.bars(direction)})",
                            Status.PASS if provided >= required else Status.FAIL,
                            clause=profile.footing.clauses()["punching_min_reinforcement"], member=footing.id,
                            demand=required, capacity=provided, unit="mm2", values=_slab_values(slab), note=note))
    return checks


def shear_checks(basis: Basis, footing: Footing, cases: list[FactoredCase]) -> list[Check]:
    """Cortante en una dirección y punzonamiento de cada caso; el nivel sísmico de basis decide si el concreto simple puede
    resistir la parte negativa de la transferencia de momento (D-072, D-087)."""
    profile, materials = basis.profile, basis.materials
    bottom = mat_rows(footing, footing.bottom, basis.bars)
    top = None if footing.top is None else mat_rows(footing, footing.top, basis.bars)
    checks: list[Check] = []
    for case in cases:
        checks.extend(_one_way(profile, materials, footing, bottom[direction], case) for direction in ("x", "y"))
        checks.extend(_punching_checks(profile, materials, footing, (bottom, top), (case, basis.seismic_level)))
    return checks
