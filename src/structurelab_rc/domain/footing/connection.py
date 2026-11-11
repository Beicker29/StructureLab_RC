"""Desarrollo de las mallas, aplastamiento y pasadores de zapatas aisladas (V3D.3; D-059, D-065).

Desarrollo: desde cada cara de la columna hasta el extremo de la barra, con la longitud disponible menos el
recubrimiento del extremo; la malla superior solo si algún caso produce momento negativo en esa dirección. Factores
(D-071): ψe por el recubrimiento de las barras, ψcc de ganchos con el recubrimiento lateral de la barra extrema y el del
extremo, y As requerido/As suministrado con el As de required_mat_area si el perfil lo permite con el nivel sísmico.
Aplastamiento: cara superior de la zapata, A2 del tronco de pirámide 1:2 contenido en la base. Pasadores: área mínima,
anclaje a compresión hasta la malla inferior y la compresión que excede el aplastamiento. Las longitudes salen de
domain/development.py; el aplastamiento y los mínimos, de codes.
"""

from dataclasses import dataclass, replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.development import BarAnchorage, development_check, required_length
from structurelab_rc.domain.footing.flexure import MAT_NAMES, FaceMoments, face_moments, has_negative_moment, required_mat_area
from structurelab_rc.domain.footing.loads import FactoredCase, column_faces
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows
from structurelab_rc.domain.status import Status
from structurelab_rc.errors import incomplete
from structurelab_rc.model.footing import Dowels, Footing, FootingBase

BEARING = "Aplastamiento en la zapata"
DOWELS_AREA = "Pasadores: area minima"
DOWELS_ANCHORAGE = "Pasadores: anclaje a compresion"
DOWELS_EXCESS = "Pasadores: compresion sobre el aplastamiento"


def _available(footing: Footing, direction: str) -> float:
    """Menor distancia de una cara de la columna al borde de la zapata, menos el recubrimiento del extremo."""
    plus, minus = column_faces(footing)[direction]
    half = (footing.lx if direction == "x" else footing.ly) / 2
    return min(half - plus, minus + half) - footing.cover


def bar_anchorage(row: BarRow, layout: tuple[str, float, bool], footing: tuple[float, float], excess: float) -> BarAnchorage:
    """Anclaje de una fila de barras de zapata: layout = (extremo, menor separación, malla inferior), footing = (h,
    recubrimiento) y excess = As requerido / As suministrado. La barra extrema queda al recubrimiento de la cara lateral
    y el extremo de la barra, al del extremo."""
    end, spacing, bottom = layout
    h, cover = footing
    face_cover = h - row.depth - row.diameter / 2  # recubrimiento libre a la cara de la malla
    return BarAnchorage(row.diameter, end, cb=min(cover + row.diameter / 2, spacing / 2),  # type: ignore[arg-type]
                        concrete_below=h - row.depth if bottom else row.depth, clear_cover=min(face_cover, cover),
                        clear_spacing=spacing - row.diameter, side_cover=cover, extension_cover=cover, excess=excess)


def _anchorage(basis: Basis, footing: Footing, mat_row: tuple[str, BarRow], cases: list[FaceMoments]) -> BarAnchorage:
    mat, row = mat_row
    spec = getattr(footing, mat)
    bar_set = getattr(spec, row.direction)
    spacing = min(bar_set.spacing, bar_set.band_spacing or bar_set.spacing)
    required = required_mat_area(basis.profile, basis.materials, footing, mat_row, cases)
    excess = 1.0 if required is None else min(required / row.area, 1.0)
    return bar_anchorage(row, (spec.end, spacing, mat == "bottom"), (footing.h, footing.cover), excess)


def _development_checks(
    basis: Basis, footing: Footing, rows: dict[str, dict[str, BarRow]], cases: list[FaceMoments]
) -> list[Check]:
    checks = []
    for mat, mat_rows_ in rows.items():
        spec = getattr(footing, mat)
        for direction, row in mat_rows_.items():
            if mat == "top" and not has_negative_moment(cases, direction):
                continue
            bar = _anchorage(basis, footing, (mat, row), cases)
            required = required_length(basis.profile, basis.materials, bar, basis.seismic_level)
            end = "con gancho estandar" if spec.end == "hook" else "rectas"
            name = f"Desarrollo malla {MAT_NAMES[mat]} (barras {direction})"
            checks.append(replace(development_check(name, required, _available(footing, direction), f"Barras {end}"),
                                  member=footing.id))
    return checks


@dataclass(frozen=True)
class Support:
    """Columna (o pedestal) sobre la zapata: sección cx × cy centrada en (x, y), sus pasadores y la nota de sus checks."""

    cx: float
    cy: float
    x: float
    y: float
    dowels: Dowels | None
    note: str


def bearing_area(footing: FootingBase, support: Support) -> tuple[float, float]:
    """A1 (columna) y A2: base del tronco de pirámide de pendiente 1:2 bajo A1, contenido en la zapata."""
    hx, hy = footing.lx / 2, footing.ly / 2
    gaps = (hx - (support.x + support.cx / 2), support.x - support.cx / 2 + hx,
            hy - (support.y + support.cy / 2), support.y - support.cy / 2 + hy)
    spread = min(2 * footing.h, *gaps)
    return support.cx * support.cy, (support.cx + 2 * spread) * (support.cy + 2 * spread)


def bearing_checks(
    basis: Basis, footing: FootingBase, support: Support, given: tuple[list[tuple[str, float]], float | None]
) -> list[Check]:
    """Aplastamiento con la carga de la columna en cada caso, (caso, Pu), y la compresión que excede φBn sobre los
    pasadores (D-065)."""
    profile, materials = basis.profile, basis.materials
    loads, dowel_area = given
    a1, a2 = bearing_area(footing, support)
    bearing = profile.bearing
    phi = bearing.strength_reduction()
    capacity = phi * bearing.nominal_bearing(materials.fc, a1, a2)
    checks = []
    for case, pu in loads:
        if pu <= 0:
            continue
        checks.append(Check(BEARING, Status.PASS if pu <= capacity else Status.FAIL, clause=bearing.clauses()["bearing"],
                            member=footing.id, case=case, demand=pu, capacity=capacity, unit="N",
                            values=(("phi", phi), ("A1", a1), ("A2", a2)), note=support.note))
        if pu > capacity:
            # La compresión que excede φBn la toman los pasadores con φ del aplastamiento (D-065).
            required = (pu - capacity) / (phi * materials.fy)
            clause = profile.footing.clauses()["dowel_excess"]
            if dowel_area is None:
                error = incomplete("Faltan los pasadores (column.dowels) para tomar la compresion que excede el aplastamiento",
                                   member=footing.id, case=case)
                checks.append(Check(DOWELS_EXCESS, Status.INCOMPLETE, (error,), clause, member=footing.id, case=case,
                                    note=support.note))
            else:
                checks.append(Check(DOWELS_EXCESS, Status.PASS if dowel_area >= required else Status.FAIL, clause=clause,
                                    member=footing.id, case=case, demand=required, capacity=dowel_area, unit="mm2",
                                    note=support.note))
    return checks


def dowel_checks(basis: Basis, footing: FootingBase, support: Support, bottom: tuple[BarRow, BarRow]) -> tuple[list[Check], float | None]:
    """Área mínima de los pasadores y su anclaje a compresión hasta la malla inferior (bottom: las dos filas, la de la
    cara primero)."""
    profile, materials, bars = basis.profile, basis.materials, basis.bars
    dowels = support.dowels
    clause = profile.footing.clauses()["dowels"]
    if dowels is None:
        error = incomplete("Faltan los pasadores (column.dowels); no se suponen (D-059)", member=footing.id)
        return [Check(DOWELS_AREA, Status.INCOMPLETE, (error,), clause, member=footing.id, note=support.note)], None
    spec = {bar.designation: bar for bar in bars}[dowels.designation]
    area = dowels.count * spec.area_mm2
    required = profile.footing.dowel_min_ratio() * support.cx * support.cy
    checks = [Check(DOWELS_AREA, Status.PASS if area >= required else Status.FAIL, clause=clause, member=footing.id,
                    demand=required, capacity=area, unit="mm2", note=support.note)]
    # Los pasadores bajan hasta la malla inferior y se apoyan en ella; su gancho no cuenta a compresión (D-065).
    first, second = bottom
    available = footing.h - footing.cover - first.diameter - second.diameter
    required_ldc = required_length(profile, materials, BarAnchorage(spec.diameter_mm, "compression"), basis.seismic_level)
    checks.append(replace(development_check(DOWELS_ANCHORAGE, required_ldc, available), member=footing.id, note=support.note))
    return checks, area


def footing_support(footing: Footing) -> Support:
    """La columna de una zapata aislada como apoyo."""
    column = footing.column
    return Support(column.cx, column.cy, column.offset_x, column.offset_y, column.dowels, "")


def connection_checks(basis: Basis, footing: Footing, cases: list[FactoredCase]) -> list[Check]:
    rows = {"bottom": mat_rows(footing, footing.bottom, basis.bars)}
    if footing.top is not None:
        rows["top"] = mat_rows(footing, footing.top, basis.bars)
    moments = [face_moments(footing, case) for case in cases]
    support = footing_support(footing)
    bottom = rows["bottom"]
    first = footing.bottom.first
    dowels, dowel_area = dowel_checks(basis, footing, support, (bottom[first], bottom["y" if first == "x" else "x"]))
    loads = [(case.case, case.load.p) for case in cases]
    return [*_development_checks(basis, footing, rows, moments), *dowels, *bearing_checks(basis, footing, support, (loads, dowel_area))]

