"""Flexión de zapatas aisladas con los casos mayorados (V3D.1; D-054, D-057, D-059).

Carga neta: presión del suelo (Bellos y Bakas 2017, con la columna, los pesos y las sobrecargas factorados) menos las
cargas por unidad de área sobre el voladizo (zapata, relleno y sobrecargas con los factores del caso). El momento en
cada cara de la columna es el de la carga neta que actúa a un lado del plano vertical, en todo el ancho (ACI 13.2.6.6,
NSR-10 C.15.4.1). Positivo tracciona la cara inferior; negativo, la superior. La resistencia es la de una sección
rectangular del ancho total con la capa de esa dirección (domain/flexure_strength).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.flexure_strength import (
    MomentStrength,
    RectangularSection,
    net_tensile_strain_check,
    rectangular_strength,
    required_area,
)
from structurelab_rc.domain.footing.base import base_resultant
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import StructuredError, blocked, incomplete, invalid_input
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import SoilPressure, footing_pressure
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import Footing, FootingLoad, Soil
from structurelab_rc.model.project import Materials

EQUILIBRIUM = "Zapata: equilibrio con cargas mayoradas"
_MATS = {"bottom": "inferior", "top": "superior"}
_FACES = {"x": ("+X", "-X"), "y": ("+Y", "-Y")}
_NEGLIGIBLE = 1e-6  # N·mm


@dataclass(frozen=True)
class FaceMoments:
    """Momentos de la carga neta en las caras de la columna, por dirección de las barras: {"x": (+X, −X), "y": (+Y, −Y)}."""

    case: str
    moments: dict[str, tuple[float, float]]


def _net_load(footing: Footing, soil: Soil, load: FootingLoad) -> float:
    """Cargas hacia abajo sobre el voladizo por unidad de área, en N/mm²."""
    dead = soil.unit_weight_concrete * footing.h + soil.unit_weight_fill * footing.fill_height + footing.surcharge_dead
    return load.dead_factor * dead + load.live_factor * footing.surcharge_live


def _face_moments(footing: Footing, pressure: SoilPressure, net_load: float) -> dict[str, tuple[float, float]]:
    hx, hy = footing.lx / 2, footing.ly / 2
    column = footing.column
    east, west = column.offset_x + column.cx / 2, column.offset_x - column.cx / 2
    north, south = column.offset_y + column.cy / 2, column.offset_y - column.cy / 2

    def moment(polygon: tuple[tuple[float, float], ...], axis: int, face: float, outward: float, length: float) -> float:
        force, sx, sy = pressure.resultant(polygon)
        static = sx if axis == 0 else sy
        soil = outward * (static - face * force)
        width = footing.ly if axis == 0 else footing.lx
        return soil - net_load * length * width * length / 2

    return {
        "x": (moment(((east, -hy), (hx, -hy), (hx, hy), (east, hy)), 0, east, 1.0, hx - east),
              moment(((-hx, -hy), (west, -hy), (west, hy), (-hx, hy)), 0, west, -1.0, west + hx)),
        "y": (moment(((-hx, north), (hx, north), (hx, hy), (-hx, hy)), 1, north, 1.0, hy - north),
              moment(((-hx, -hy), (hx, -hy), (hx, south), (-hx, south)), 1, south, -1.0, south + hy)),
    }


def factored_moments(footing: Footing, soil: Soil) -> tuple[list[FaceMoments], list[Check]]:
    """Momentos de cada caso mayorado; un caso sin equilibrio con el suelo es FAIL (D-054)."""
    results, failures = [], []
    for load in footing.loads:
        if load.kind != "factored":
            continue
        resultant = base_resultant(footing, soil, load)
        try:
            if resultant.ex is None or resultant.ey is None:
                raise NoEquilibrium("la carga mayorada sobre el suelo no es de compresion")
            pressure = footing_pressure(footing.lx, footing.ly, resultant.n, resultant.ex, resultant.ey)
        except NoEquilibrium as error:
            failure = invalid_input(f"La resultante mayorada sale de la base: {error}", member=footing.id, case=load.case)
            failures.append(Check(EQUILIBRIUM, Status.FAIL, (failure,), "D-054", member=footing.id, case=load.case))
            continue
        results.append(FaceMoments(load.case, _face_moments(footing, pressure, _net_load(footing, soil, load))))
    return results, failures


def _strength(profile: Profile, materials: Materials, footing: Footing, row: BarRow) -> MomentStrength | StructuredError:
    return rectangular_strength(profile, materials, RectangularSection(row.width, footing.h), (SteelLayer(row.depth, row.area),))


def _name(kind: str, mat: str, direction: str) -> str:
    return f"{kind} malla {_MATS[mat]} (barras {direction})"


def _strength_checks(
    profile: Profile, materials: Materials, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]
) -> list[Check]:
    clause = profile.footing.clauses()["strength"]
    checks = []
    for case in cases:
        for direction in ("x", "y"):
            positive, negative = _FACES[direction]
            plus, minus = case.moments[direction]
            for mat, sign in (("bottom", 1.0), ("top", -1.0)):
                demand, face = max((sign * plus, positive), (sign * minus, negative))
                if mat == "top" and demand <= _NEGLIGIBLE:
                    continue
                name = _name("Flexion", mat, direction)
                member, load_case = footing.id, case.case
                if mat not in rows:
                    error = blocked("Momento negativo sin malla superior: el concreto simple no esta implementado (D-059)",
                                    face=face, member=member, case=load_case)
                    checks.append(Check(name, Status.BLOCKED, (error,), clause, member=member, case=load_case, demand=demand,
                                        unit="N*mm"))
                    continue
                row = rows[mat][direction]
                strength = _strength(profile, materials, footing, row)
                if isinstance(strength, StructuredError):
                    checks.append(replace(check_from_errors(name, [strength]), clause=clause, member=member, case=load_case))
                    continue
                values = (("phi", strength.phi), ("Mn", strength.nominal), ("d", row.depth), ("As", row.area),
                          ("et", strength.state.extreme_strain))
                status = Status.PASS if strength.design >= demand else Status.FAIL
                checks.append(Check(name, status, clause=clause, demand=max(demand, 0.0), capacity=strength.design,
                                    unit="N*mm", values=values, note=f"Cara {face} de la columna", member=member,
                                    case=load_case))
    return checks


def _negative(cases: list[FaceMoments], direction: str) -> bool:
    return any(min(case.moments[direction]) < -_NEGLIGIBLE for case in cases)


def _section_checks(
    profile: Profile, materials: Materials, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]
) -> list[Check]:
    """Verificaciones que no dependen del caso: εt, As,min, separación, franja γs y altura mínima."""
    clauses = profile.footing.clauses()
    checks = []
    member = footing.id
    ratio = profile.footing.min_reinforcement_ratio(materials.fy)
    max_spacing = profile.footing.max_bar_spacing(footing.h)
    for mat, mat_rows_ in rows.items():
        bar_sets = {"x": getattr(footing, mat).x, "y": getattr(footing, mat).y}
        for direction, row in mat_rows_.items():
            strength = _strength(profile, materials, footing, row)
            if isinstance(strength, MomentStrength):
                checks.append(replace(net_tensile_strain_check(_name("Deformacion neta de traccion", mat, direction),
                                                               clauses["net_tensile_strain"], profile, materials,
                                                               strength.state.extreme_strain), member=member))
            if mat == "bottom" or _negative(cases, direction):
                required = ratio * row.width * footing.h
                checks.append(Check(_name("Acero minimo", mat, direction), Status.PASS if row.area >= required else Status.FAIL,
                                    clause=clauses["min_reinforcement"], demand=required, capacity=row.area, unit="mm2",
                                    values=(("cuantia minima", ratio),), member=member))
            spacings = [bar_sets[direction].spacing]
            if bar_sets[direction].band_spacing is not None:
                spacings.append(bar_sets[direction].band_spacing)
            largest = max(spacings)
            checks.append(Check(_name("Separacion maxima", mat, direction), Status.PASS if largest <= max_spacing else Status.FAIL,
                                clause=clauses["spacing"], demand=largest, capacity=max_spacing, unit="mm", member=member))
            if row.band is not None and (mat == "bottom" or _negative(cases, direction)):
                checks.append(_band_check(profile, materials, footing, (mat, row), cases))
    bottom = rows["bottom"]
    first = bottom[footing.bottom.first]
    second = bottom["y" if footing.bottom.first == "x" else "x"]
    measured = profile.footing.footing_depth(footing.h, footing.cover, first.diameter, second.diameter)
    minimum = profile.footing.min_depth()
    checks.append(Check("Altura minima de la zapata", Status.PASS if measured >= minimum else Status.FAIL,
                        clause=clauses["min_depth"], demand=minimum, capacity=measured, unit="mm", member=member))
    return checks


def _band_check(
    profile: Profile, materials: Materials, footing: Footing, mat_row: tuple[str, BarRow], cases: list[FaceMoments]
) -> Check:
    """Franja central de la dirección corta: As en la franja ≥ γs·As, con As el mayor entre el requerido y As,min."""
    mat, row = mat_row
    ratio = profile.footing.min_reinforcement_ratio(materials.fy)
    sign = 1.0 if mat == "bottom" else -1.0
    demand = max([sign * moment for case in cases for moment in case.moments[row.direction]], default=0.0)
    needed = required_area(profile, materials, RectangularSection(row.width, footing.h), row.depth, demand)
    name = _name("Franja central", mat, row.direction)
    clause = profile.footing.clauses()["band"]
    if needed is None:
        error = invalid_input("Ninguna cuantia alcanza el momento de la direccion corta", member=footing.id)
        return Check(name, Status.FAIL, (error,), clause, member=footing.id)
    total = max(needed, ratio * row.width * footing.h)
    beta = max(footing.lx, footing.ly) / min(footing.lx, footing.ly)
    gamma = profile.footing.band_fraction(beta)
    required = gamma * total
    return Check(name, Status.PASS if row.band_area >= required else Status.FAIL, clause=clause, demand=required,
                 capacity=row.band_area, unit="mm2", values=(("gamma s", gamma), ("As", total)), member=footing.id)


def flexure_checks(profile: Profile, materials: Materials, footing: Footing, soil: Soil, bars: Sequence[RebarSpec]) -> list[Check]:
    if not any(load.kind == "factored" for load in footing.loads):
        error = incomplete("La zapata no tiene casos mayorados", member=footing.id)
        name = _name("Flexion", "bottom", "x")
        return [Check(name, Status.INCOMPLETE, (error,), profile.footing.clauses()["strength"], member=footing.id)]
    cases, failures = factored_moments(footing, soil)
    rows = {"bottom": mat_rows(footing, footing.bottom, bars)}
    if footing.top is not None:
        rows["top"] = mat_rows(footing, footing.top, bars)
    return [*failures, *_strength_checks(profile, materials, footing, rows, cases),
            *_section_checks(profile, materials, footing, rows, cases)]
