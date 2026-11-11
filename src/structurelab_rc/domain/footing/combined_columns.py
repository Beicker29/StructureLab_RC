"""Franjas transversales, punzonamiento, desarrollo, aplastamiento y pasadores de una zapata combinada (D-080, V3J.3; D-082).

Acción de cada columna como carga neta equivalente (la misma que entra en la resultante de la base): fuerza
F = `column_vertical` y momentos estáticos ∫x·q = F·x + My + H·Vx y ∫y·q = F·y − Mx + H·Vy, con H = h + pedestal.

- Punzonamiento por columna: perímetro a d/2 recortado con la base y la carga que lo atraviesa, la acción de la columna
  menos la carga neta de Bellos dentro del área crítica (`transferred_load`, la misma de la zapata aislada).
- Franja transversal bajo cada columna, de ancho columna + d/2 a cada lado (recortado con la base): la fuerza F de la
  columna repartida en el ancho B con la forma de la presión de Bellos en la x de la columna (si es nula, la integrada en
  el ancho de la franja y, si también, uniforme: D-085), en voladizo desde las caras ±Y. La franja se revisa con el
  código de vigas en modo cimentación (D-082): flexión, εt, As,min de vigas, fisuración y cortante en las caras y a d
  de ellas, con las barras y de la malla inferior que caen en la franja y el refuerzo `band` de la columna.
- Fuera de las franjas, la malla y cumple el mínimo de losa y la separación de 3h y 450 mm.
- Desarrollo: barras x desde la sección de mayor momento de su signo hasta el extremo más cercano; barras y de cada
  franja desde la cara de la columna hasta el borde. Aplastamiento y pasadores por columna, como en la zapata aislada.
"""

from collections.abc import Callable
from dataclasses import replace

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.geometry import placed_bars
from structurelab_rc.domain.beam.station import checks_for
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.development import development_check, required_length
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.combined_beam import extreme_moments
from structurelab_rc.domain.footing.connection import Support, bar_anchorage, bearing_checks, dowel_checks
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_row, uniform_positions
from structurelab_rc.domain.footing.shear import PunchedColumn, punching_checks, transferred_load
from structurelab_rc.domain.shear_strength import two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.perimeter import critical_perimeter
from structurelab_rc.model.combined import CombinedColumn, CombinedFooting
from structurelab_rc.model.footing import FootingLoad, Soil
from structurelab_rc.model.project import Demands, Member, Section, Station
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, ReinforcementLayout

OUTSIDE_MINIMUM = "Malla inferior y: acero minimo fuera de las franjas"
OUTSIDE_SPACING = "Malla inferior y: separacion maxima"
DEVELOPMENT = "Desarrollo"
Cases = list[tuple[FactoredCase, tuple[FootingLoad, ...]]]
_TOLERANCE = 1e-6  # mm


def column_action(footing: CombinedFooting, soil: Soil, column: CombinedColumn, load: FootingLoad) -> tuple[float, float, float]:
    """(F, ∫x·q, ∫y·q) de la columna, en N y N·mm."""
    force = column_vertical(footing, soil, column, load)
    height = footing.h + footing.pedestal_height
    return force, force * column.x + load.my + height * load.vx, force * column.y - load.mx + height * load.vy


def _note(column: CombinedColumn) -> str:
    return f"Columna {column.id}"


def _punching(basis: Basis, footing: CombinedFooting, soil: Soil, bottom: dict[str, BarRow], cases: Cases) -> list[Check]:
    profile, materials = basis.profile, basis.materials
    depth = (bottom["x"].depth + bottom["y"].depth) / 2
    bounds = ((-footing.lx / 2, -footing.ly / 2), (footing.lx / 2, footing.ly / 2))
    loaded = profile.footing.punching_size_factor()
    checks = []
    for index, column in enumerate(footing.columns):
        perimeter = critical_perimeter((column.x, column.y), column.cx, column.cy, depth, bounds)
        punched = PunchedColumn(column.cx, column.cy, column.x, column.y, bottom, _note(column))
        for pressure, loads in cases:
            load = transferred_load(column_action(footing, soil, column, loads[index]), pressure, perimeter)
            result = two_way_shear(profile, materials, perimeter, (column.cx, column.cy, loaded), load)
            checks += punching_checks(basis, footing, punched, (result, load, pressure.case))
    return checks


def strip_limits(footing: CombinedFooting, column: CombinedColumn, depth: float) -> tuple[float, float]:
    """Ancho de la franja: la columna más d/2 a cada lado, dentro de la base (D-080)."""
    return max(column.x - column.cx / 2 - depth / 2, -footing.lx / 2), min(column.x + column.cx / 2 + depth / 2, footing.lx / 2)


def _band_row(footing: CombinedFooting, column: CombinedColumn, row: BarRow, basis: Basis) -> BarRow | None:
    """El refuerzo band de la columna como fila de barras y en el ancho de su franja, a la profundidad de la fila y."""
    if column.band is None:
        return None
    spec = next(bar for bar in basis.bars if bar.designation == column.band.designation)
    x0, x1 = strip_limits(footing, column, row.depth)
    edge = footing.lx / 2 - footing.cover - spec.diameter_mm / 2
    positions = uniform_positions(max(x0 + spec.diameter_mm / 2, -edge), min(x1 - spec.diameter_mm / 2, edge), column.band.spacing)
    return BarRow("y", spec.designation, spec.diameter_mm, spec.area_mm2, row.depth, x1 - x0, tuple(positions), None, ())


def strip_member(footing: CombinedFooting, column: CombinedColumn, rows: tuple[BarRow, BarRow | None]) -> Member:
    """La franja como viga (D-082): ancho de franja × h, a lo largo de Y, con las barras y de la malla inferior que caen
    en ella y el refuerzo band, con x desde el borde −X de la franja."""
    row, band = rows
    x0, x1 = strip_limits(footing, column, row.depth)
    layers = []
    for source in (row, band):
        if source is None:
            continue
        inside = [position for position in source.positions if x0 - _TOLERANCE <= position <= x1 + _TOLERANCE]
        if inside:
            layers.append(BarLayer(depth=source.depth, role="flexure",
                                   bars=tuple(BarPosition(designation=source.designation, x=position - x0) for position in inside)))
    layout = ReinforcementLayout(layers=tuple(layers), stirrups=None)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    return Member.model_construct(id=footing.id, type="beam", statically_determinate=None, length=footing.ly,
                                  section=Section(bw=x1 - x0, h=footing.h, cover=footing.cover), stations=(placeholder,))


def _strip_shape(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
                 depth: float) -> tuple[Callable[[float, float], tuple[float, float]], str]:
    """Forma de la carga de la franja en el ancho B (D-080, D-085): ∫q dy y ∫y·q dy entre y0 y y1, sin escalar. Primero la
    presión en la línea de la columna; si es nula, la presión integrada en el ancho de la franja; si también es nula,
    uniforme (equilibra el cortante de la viga larga, repartido en todo el ancho). La nota dice qué forma se usó."""
    half = footing.ly / 2
    if pressure.pressure.along_y(column.x, -half, half)[0] > 0:
        return (lambda y0, y1: pressure.pressure.along_y(column.x, y0, y1)), ""
    x0, x1 = strip_limits(footing, column, depth)

    def strip(y0: float, y1: float) -> tuple[float, float]:
        force, _, first = pressure.pressure.resultant(((x0, y0), (x1, y0), (x1, y1), (x0, y1))) if y1 > y0 else (0.0, 0.0, 0.0)
        return force, first

    if strip(-half, half)[0] > 0:
        return strip, "carga con la forma de la presion integrada en el ancho de la franja (presion nula en la linea de la columna)"
    return (lambda y0, y1: (y1 - y0, (y1**2 - y0**2) / 2)), "carga uniforme F/B (presion nula en toda la franja)"


def strip_demands(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
                  given: tuple[float, float]) -> tuple[list[tuple[float, float, float, str]], str]:
    """(y, Mu, Vu, sección) en las caras ±Y de la columna y a d de ellas, hacia el borde, y la nota de la forma de carga
    usada. given = (F, d): la fuerza de la columna se reparte en el ancho B con la forma de `_strip_shape`."""
    force, depth = given
    half = footing.ly / 2
    shape, note = _strip_shape(footing, pressure, column, depth)
    scale = force / shape(-half, half)[0]

    def beyond(at: float, side: float) -> tuple[float, float]:
        load, first = shape(at, half) if side > 0 else shape(-half, at)
        return scale * side * (first - at * load), scale * load

    result = []
    for side, face, name in ((1.0, column.y + column.cy / 2, "+Y"), (-1.0, column.y - column.cy / 2, "-Y")):
        at_d = face + side * depth
        inside = -half < at_d < half
        if -half < face < half:
            # En la cara, el cortante es el de la sección a d (ACI 9.4.3.2 y 13.2.7.2, NSR-10 C.11.1.3; D-082).
            moment, shear = beyond(face, side)
            result.append((face, moment, beyond(at_d, side)[1] if inside else shear, f"cara {name}"))
        if inside:
            moment, shear = beyond(at_d, side)
            result.append((at_d, moment, shear, f"a d de la cara {name}"))
    return result, note


def _strip_checks(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, int], cases: Cases) -> list[Check]:
    row, index = rows
    column = footing.columns[index]
    member = strip_member(footing, column, (row, _band_row(footing, column, row, basis)))
    title = f"Franja transversal de la columna {column.id}"
    checks = []
    for pressure, loads in cases:
        force = column_vertical(footing, soil, column, loads[index])
        demands, shape = strip_demands(footing, pressure, column, (force, row.depth))
        for y, moment, shear, label in demands:
            station = Station.model_construct(z=y + footing.ly / 2, layout=member.stations[0].layout, case=pressure.case,
                                              demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=shear, v3=0.0, tu=0.0))
            # Las caras laterales de la franja quedan dentro del concreto: sin refuerzo superficial (D-083).
            given = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False)
            for check in checks_for(given):
                note = f"{title}, {label}" + "".join(f": {text}" for text in (check.note, shape) if text)
                checks.append(replace(check, note=note))
    return checks


def _outside_checks(basis: Basis, footing: CombinedFooting, row: BarRow) -> list[Check]:
    """La malla y fuera de las franjas: mínimo de losa por unidad de longitud y separación de 3h y 450 mm."""
    profile = basis.profile
    spacing = footing.bottom.y.spacing
    required = profile.footing.min_reinforcement_ratio(basis.materials.fy) * footing.h * 1000.0
    provided = row.bar_area / spacing * 1000.0
    maximum = profile.footing.combined_max_bar_spacing(footing.h)
    clauses = profile.footing.clauses()
    return [Check(OUTSIDE_MINIMUM, Status.PASS if provided >= required else Status.FAIL, clause=clauses["combined_min_reinforcement"],
                  demand=required, capacity=provided, unit="mm2/m", member=footing.id),
            Check(OUTSIDE_SPACING, Status.PASS if spacing <= maximum else Status.FAIL, clause=clauses["combined_spacing"],
                  demand=spacing, capacity=maximum, unit="mm", member=footing.id)]


def _excess(basis: Basis, section: tuple[float, float, float], provided: float, moment: float) -> float:
    """As requerido / As suministrado (≤ 1): el mayor entre el de análisis y el mínimo de vigas efectivo. section = (ancho,
    h, d)."""
    width, h, depth = section
    profile, materials = basis.profile, basis.materials
    analysis = required_area(profile, materials, RectangularSection(width, h), depth, moment)
    if analysis is None or provided <= 0:
        return 1.0
    as_min = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, width, depth)
    return min(max(analysis, profile.flexure.effective_min_reinforcement(as_min, analysis)) / provided, 1.0)


def _development_check(basis: Basis, footing: CombinedFooting, row: BarRow, anchorage: tuple[float, bool, float, float],
                       text: tuple[str, str]) -> Check:
    """anchorage = (menor separación, malla inferior, As requerido / As suministrado, longitud disponible); text = (nombre,
    nota). El tipo de extremo es el de la malla inferior o el de las barras superiores (D-082)."""
    spacing, bottom, excess, available = anchorage
    name, note = text
    end = footing.bottom.end if bottom or footing.top is None else footing.top.end
    bar = bar_anchorage(row, (end, spacing, bottom), (footing.h, footing.cover), excess)
    required = required_length(basis.profile, basis.materials, bar, basis.seismic_level)
    ends = "Barras con gancho estandar" if end == "hook" else "Barras rectas"
    return replace(development_check(name, required, available, f"{note}; {ends}"), member=footing.id)


def _x_development(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, BarRow | None], cases: Cases) -> list[Check]:
    """Barras x desde la sección de mayor momento de su signo hasta el extremo más cercano, menos el recubrimiento."""
    bottom, top = rows
    positive, negative = extreme_moments(footing, soil, cases)
    half = footing.lx / 2
    checks = []
    for moment_at, row, spacing, label in ((positive, bottom, footing.bottom.x.spacing, "inferiores"),
                                           (negative, top, footing.top.spacing if footing.top else 0.0, "superiores")):
        moment, x = moment_at
        if row is None or moment <= 0:
            continue
        excess = _excess(basis, (footing.ly, footing.h, row.depth), row.area, moment)
        available = min(x + half, half - x) - footing.cover
        sign = "positivo" if label == "inferiores" else "negativo"
        note = f"Desde la seccion de mayor momento {sign} (z = {x + half:.0f} mm)"
        checks.append(_development_check(basis, footing, row, (spacing, label == "inferiores", excess, available),
                                         (f"{DEVELOPMENT} barras {label} x", note)))
    return checks


def _y_development(basis: Basis, footing: CombinedFooting, soil: Soil, row: BarRow, cases: Cases) -> list[Check]:
    """Barras y de cada franja (malla y band) desde la cara de la columna hasta el borde, menos el recubrimiento."""
    half = footing.ly / 2
    checks = []
    for index, column in enumerate(footing.columns):
        band = _band_row(footing, column, row, basis)
        member = strip_member(footing, column, (row, band))
        provided = sum(bar.area for bar in placed_bars(member.stations[0].layout, member.section, basis.bars))
        moment = 0.0
        for pressure, loads in cases:
            demands, _ = strip_demands(footing, pressure, column, (column_vertical(footing, soil, column, loads[index]), row.depth))
            moment = max([moment, *(demand[1] for demand in demands if demand[3].startswith("cara"))])
        if moment <= 0:
            continue
        excess = _excess(basis, (member.section.bw, footing.h, row.depth), provided, moment)
        available = min(half - (column.y + column.cy / 2), column.y - column.cy / 2 + half) - footing.cover
        spacing = min(footing.bottom.y.spacing, column.band.spacing if column.band else footing.bottom.y.spacing)
        note = f"Franja transversal de la columna {column.id}, desde la cara de la columna"
        checks.append(_development_check(basis, footing, row, (spacing, True, excess, available),
                                         (f"{DEVELOPMENT} barras y (franja de la columna {column.id})", note)))
        if band is not None and band.diameter != row.diameter:
            checks.append(_development_check(basis, footing, band, (spacing, True, excess, available),
                                             (f"{DEVELOPMENT} refuerzo band (columna {column.id})", note)))
    return checks


def column_checks(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> list[Check]:
    """V3J.3: punzonamiento, franjas transversales, malla y fuera de las franjas, desarrollo, aplastamiento y pasadores."""
    bottom = mat_rows(footing, footing.bottom, basis.bars)
    rows: dict[str, BarRow | None] = {"bottom x": bottom["x"], "bottom y": bottom["y"], "top": top_row(footing, basis.bars)}
    checks = _punching(basis, footing, soil, bottom, cases)
    for index in range(len(footing.columns)):
        checks += _strip_checks(basis, footing, soil, (bottom["y"], index), cases)
    checks += _outside_checks(basis, footing, bottom["y"])
    checks += _x_development(basis, footing, soil, (bottom["x"], rows["top"]), cases)
    checks += _y_development(basis, footing, soil, bottom["y"], cases)
    first = footing.bottom.first
    for index, column in enumerate(footing.columns):
        support = Support(column.cx, column.cy, column.x, column.y, column.dowels, _note(column))
        dowels, area = dowel_checks(basis, footing, support, (bottom[first], bottom["y" if first == "x" else "x"]))
        loads = [(pressure.case, loads[index].p) for pressure, loads in cases]
        checks += [*dowels, *bearing_checks(basis, footing, support, (loads, area))]
    return checks
