"""Franjas transversales, punzonamiento, desarrollo, aplastamiento y pasadores de una zapata combinada (D-080, V3J.3; D-082).

En ejes de la viga: X a lo largo de ella (dirección principal; barras x), Y transversal (dirección secundaria; barras y,
franjas). Las verificaciones nombran las barras por su dirección y se devuelven en los ejes declarados (D-101).

Acción de cada columna como carga neta equivalente (la misma que entra en la resultante de la base): fuerza
F = `column_vertical` y momentos estáticos ∫x·q = F·x + My + H·Vx y ∫y·q = F·y − Mx + H·Vy, con H = h + pedestal.

- Punzonamiento por columna: perímetro a d/2 recortado con la base y la carga que lo atraviesa, la acción de la columna
  menos la carga neta de Bellos dentro del área crítica (`transferred_load`, la misma de la zapata aislada). Si los
  perímetros de columnas vecinas se traslapan, además el perímetro común de cada grupo encadenado (D-086, D-163).
- Franja transversal bajo cada columna, de ancho columna + d/2 a cada lado (recortado con la base y, si se monta con la
  de una columna vecina, en el punto medio entre sus caras, D-163): la fuerza F de la
  columna repartida en el ancho B con la forma de la presión de Bellos en la x de la columna (si es nula, la integrada en
  el ancho de la franja y, si también, uniforme: D-085), en voladizo desde las caras ±Y. La franja se revisa con el
  código de vigas en modo cimentación (D-082): flexión, εt, As,min de vigas, fisuración y cortante en las caras y a d
  de ellas, con las barras y de la malla inferior que caen en la franja y el refuerzo `band` de la columna.
- Fuera de las franjas, la malla y cumple el mínimo de losa y la separación de 3h y 450 mm.
- Desarrollo: barras x desde la sección de mayor momento de su signo hasta el extremo más cercano; barras y de cada
  franja desde la cara de la columna hasta el borde. Aplastamiento y pasadores por columna, como en la zapata aislada.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from functools import partial

from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.beam.flexure import MIN_REINFORCEMENT as FLEXURE_MINIMUM
from structurelab_rc.domain.beam.flexure import STRENGTH as FLEXURE_STRENGTH
from structurelab_rc.domain.beam.shear import MIN_REINFORCEMENT, STRENGTH, concrete_lambda, section_at_depth, shear_depth
from structurelab_rc.domain.beam.station import flexure_station_checks, shear_and_torsion_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check, check_from_errors
from structurelab_rc.domain.development import END_TEXT, development_check, required_length
from structurelab_rc.domain.flexure_strength import MomentStrength, RectangularSection, rectangular_strength, required_area
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.combined_beam import BeamCase, bar_extent, beam_case, developed, extreme_moments, moment_sign
from structurelab_rc.domain.footing.connection import Support, bar_anchorage, bearing_checks, dowel_checks
from structurelab_rc.domain.footing.declared import DIRECTIONS, PRINCIPAL, SECONDARY
from structurelab_rc.domain.footing.flexure import plain_resists, plain_strip_check
from structurelab_rc.domain.footing.loads import FactoredCase, combined_service_cases, remembered, service_moment
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, positions_within, stirrup_diameter, top_rows, uniform_positions
from structurelab_rc.domain.footing.shear import PunchedColumn, punching_checks, transferred_load
from structurelab_rc.domain.shear_strength import two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.flexure import SteelLayer
from structurelab_rc.mechanics.perimeter import Perimeter, critical_perimeter, plan_perimeter
from structurelab_rc.mechanics.plate import wood_armer
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedColumn, CombinedFooting
from structurelab_rc.model.footing import BarSet, FootingLoad, Soil
from structurelab_rc.model.project import Demands, Member, Section, Station
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, ReinforcementLayout

SHRINKAGE = "Retraccion y temperatura"
OUTSIDE_MINIMUM = "Direccion secundaria: acero minimo (malla inferior fuera de las franjas)"
OUTSIDE_SPACING = "Direccion secundaria: separacion maxima (malla inferior)"
DEVELOPMENT = "Desarrollo"
MINIMUM_NOTE = "criterio del usuario (D-087): 8.6.1.2 aplicado a la zapata combinada, aunque 13.3.2.1 la remite a los capitulos 7 y 9"
Cases = list[tuple[FactoredCase, tuple[FootingLoad, ...]]]
_TOLERANCE = 1e-6  # mm
_SWEEP = 64  # puntos por voladizo para buscar el mayor momento negativo de la franja (D-095)
_NEGLIGIBLE_MOMENT = 1e3  # N·mm: por debajo, no hay momento negativo que revisar
_NEGLIGIBLE_TWIST = 1.0  # N·mm/mm: por debajo, no hay torsión de placa (D-118)


def column_action(footing: CombinedFooting, soil: Soil, column: CombinedColumn, load: FootingLoad) -> tuple[float, float, float]:
    """(F, ∫x·q, ∫y·q) de la columna, en N y N·mm."""
    force = column_vertical(footing, soil, column, load)
    height = footing.h + footing.pedestal_height
    return force, force * column.x + load.my + height * load.vx, force * column.y - load.mx + height * load.vy


def _perimeter(footing: CombinedFooting, centre: tuple[float, float], size: tuple[float, float], depth: float) -> Perimeter:
    """El perímetro crítico a d/2 recortado con la base: con el rectángulo lx × ly o con la planta trapezoidal o en T/L,
    con αs por las esquinas dentro de ella (D-164)."""
    if footing.plan is not None:
        return plan_perimeter(centre, *size, depth, footing.outline)
    bounds = ((-footing.lx / 2, -footing.ly / 2), (footing.lx / 2, footing.ly / 2))
    return critical_perimeter(centre, *size, depth, bounds)


def _note(column: CombinedColumn) -> str:
    return f"Columna {column.id}"


def _punching(basis: Basis, footing: CombinedFooting, soil: Soil, bottom: dict[str, BarRow], cases: Cases) -> list[Check]:
    profile, materials = basis.profile, basis.materials
    depth = (bottom["x"].depth + bottom["y"].depth) / 2
    loaded = profile.footing.punching_size_factor()
    checks = []
    for index, column in enumerate(footing.columns):
        perimeter = _perimeter(footing, (column.x, column.y), (column.cx, column.cy), depth)
        punched = PunchedColumn(column.cx, column.cy, column.x, column.y, _punching_rows(basis, footing, bottom, [column]),
                                _note(column), MINIMUM_NOTE, _top_rows(basis, footing), DIRECTIONS)
        for pressure, loads in cases:
            load = transferred_load(column_action(footing, soil, column, loads[index]), pressure, perimeter)
            result = two_way_shear(profile, materials, perimeter, (column.cx, column.cy, loaded), load)
            checks += punching_checks(basis, footing, punched, (result, load, pressure.case))
    return checks + _group_punching(basis, footing, soil, (bottom, depth), cases)


def _punching_rows(basis: Basis, footing: CombinedFooting, bottom: dict[str, BarRow],
                   columns: list[CombinedColumn]) -> dict[str, tuple[BarRow, ...]]:
    """Filas de barras inferiores alrededor de las columnas: la malla en las dos direcciones y, en Y, el band de cada una."""
    bands = tuple(band for column in columns if (band := band_row(footing, column, bottom["y"], basis)) is not None)
    return {"x": (bottom["x"],), "y": (bottom["y"], *bands)}


def _top_rows(basis: Basis, footing: CombinedFooting) -> dict[str, tuple[BarRow, ...]]:
    """Barras superiores alrededor de las columnas: top.x y, en Y, top.y fuera de las zonas de band superior y el band
    superior de cada columna (D-097, D-099, D-119), si los hay."""
    rows = top_rows(footing, basis.bars)
    depth = mat_rows(footing, footing.bottom, basis.bars)["y"].depth
    result: dict[str, tuple[BarRow, ...]] = {"x": (rows["x"],)} if "x" in rows else {}
    across = transverse_top(footing, rows.get("y"), depth)
    bands = tuple(band for column in footing.columns if (band := band_top_row(footing, column, depth, basis.bars)) is not None)
    if across is not None or bands:
        result["y"] = (*(() if across is None else (across,)), *bands)
    return result


def _overlap(first: CombinedColumn, second: CombinedColumn, depth: float) -> bool:
    """Los perímetros críticos de dos columnas (a d/2 de sus caras, sin recortar) se traslapan."""
    apart_x = abs(first.x - second.x) >= (first.cx + second.cx) / 2 + depth
    apart_y = abs(first.y - second.y) >= (first.cy + second.cy) / 2 + depth
    return not (apart_x or apart_y)


def punching_groups(footing: CombinedFooting, depth: float) -> list[list[int]]:
    """Los grupos de columnas (índices en el orden declarado) cuyos perímetros se traslapan, directamente o encadenados
    (D-163: si C1 se traslapa con C2 y C2 con C3, el grupo es C1, C2 y C3); solo los de dos o más columnas."""
    groups: list[set[int]] = []
    for index, column in enumerate(footing.columns):
        touching = [group for group in groups if any(_overlap(column, footing.columns[other], depth) for other in group)]
        merged = {index}.union(*touching)
        groups = [group for group in groups if group not in touching] + [merged]
    return [sorted(group) for group in groups if len(group) > 1]


def _names(ids: list[str]) -> str:
    return ids[0] if len(ids) == 1 else f"{', '.join(ids[:-1])} y {ids[-1]}"


def _group_punching(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[dict[str, BarRow], float],
                    cases: Cases) -> list[Check]:
    """Perímetro común de cada grupo de columnas cuyos perímetros se traslapan (ACI R13.2.7.2, NSR-10 CR15.5.2; D-086,
    D-163): el menor rectángulo que contiene sus perímetros, que es el perímetro a d/2 de la caja que contiene las
    columnas del grupo, recortado con la base; la carga es la suma de sus acciones menos la carga neta dentro de él. Se
    agrega a las revisiones individuales, que se conservan."""
    bottom, depth = rows
    checks = []
    for group in punching_groups(footing, depth):
        members = [footing.columns[index] for index in group]
        left = min(column.x - column.cx / 2 for column in members)
        right = max(column.x + column.cx / 2 for column in members)
        low = min(column.y - column.cy / 2 for column in members)
        high = max(column.y + column.cy / 2 for column in members)
        size, centre = (right - left, high - low), ((left + right) / 2, (low + high) / 2)
        perimeter = _perimeter(footing, centre, size, depth)
        punched = PunchedColumn(*size, *centre, _punching_rows(basis, footing, bottom, members),
                                f"Columnas {_names([column.id for column in members])} (perimetro comun)", MINIMUM_NOTE,
                                _top_rows(basis, footing), DIRECTIONS)
        for pressure, loads in cases:
            actions = [column_action(footing, soil, footing.columns[index], loads[index]) for index in group]
            total = (sum(action[0] for action in actions), sum(action[1] for action in actions),
                     sum(action[2] for action in actions))
            load = transferred_load(total, pressure, perimeter)
            result = two_way_shear(basis.profile, basis.materials, perimeter, (*size, basis.profile.footing.punching_size_factor()),
                                   load)
            checks += punching_checks(basis, footing, punched, (result, load, pressure.case))
    return checks


def strip_limits(footing: CombinedFooting, column: CombinedColumn, depth: float) -> tuple[float, float]:
    """Ancho de la franja: la columna más d/2 a cada lado, dentro de la base (D-080) y, si se monta con la franja de una
    columna vecina, hasta el punto medio entre sus caras (D-163), para no contar dos veces la misma presión."""
    low, high = column.x - column.cx / 2 - depth / 2, column.x + column.cx / 2 + depth / 2
    for other in footing.columns:
        if other.x > column.x and other.x - other.cx / 2 - depth / 2 < high:
            high = (column.x + column.cx / 2 + other.x - other.cx / 2) / 2
        elif other.x < column.x and other.x + other.cx / 2 + depth / 2 > low:
            low = (column.x - column.cx / 2 + other.x + other.cx / 2) / 2
    first, last = footing.x_range
    return max(low, first), min(high, last)


def strip_edges(footing: CombinedFooting, column: CombinedColumn, depth: float) -> tuple[float, float]:
    """Bordes −Y y +Y hasta los que van los voladizos de la franja: ±ly/2 en el rectángulo; en una planta trapezoidal o
    en T/L (D-164), los bordes en el eje de la columna y, si la franja cruza un escalón, los del tramo más angosto."""
    if footing.plan is None:
        return -footing.ly / 2, footing.ly / 2
    x0, x1 = strip_limits(footing, column, depth)
    outline = footing.outline
    stepped = any(a[0] == b[0] and x0 < a[0] < x1 for a, b in zip(outline, (*outline[1:], outline[0]), strict=True))
    return footing.across(x0, x1) if stepped else footing.across(column.x)


def shear_limits(footing: CombinedFooting, column: CombinedColumn, depth: float) -> tuple[float, float]:
    """Ancho efectivo de la franja para el cortante (decisión del usuario, D-151): la columna más d a cada lado, dentro de
    la base y sin pasar la mitad del espacio libre hasta la columna vecina; nunca menor que el ancho de la franja de
    flexión (strip_limits). La flexión sigue con la columna más d/2 a cada lado (D-080)."""
    low, high = column.x - column.cx / 2 - depth, column.x + column.cx / 2 + depth
    for other in footing.columns:
        if other.x > column.x:
            high = min(high, (column.x + column.cx / 2 + other.x - other.cx / 2) / 2)
        elif other.x < column.x:
            low = max(low, (column.x - column.cx / 2 + other.x + other.cx / 2) / 2)
    flexure = strip_limits(footing, column, depth)
    first, last = footing.x_range
    return max(min(low, flexure[0]), first), min(max(high, flexure[1]), last)


def band_row(footing: CombinedFooting, column: CombinedColumn, row: BarRow, basis: Basis) -> BarRow | None:
    """El refuerzo band de la columna como fila de barras y en el ancho de su franja, a la profundidad de la fila y."""
    if column.band is None:
        return None
    spec = next(bar for bar in basis.bars if bar.designation == column.band.designation)
    x0, x1 = strip_limits(footing, column, row.depth)
    first, last = footing.x_range
    inset = footing.cover + spec.diameter_mm / 2
    positions = uniform_positions(max(x0 + spec.diameter_mm / 2, first + inset), min(x1 - spec.diameter_mm / 2, last - inset),
                                  column.band.spacing)
    return BarRow("y", spec.designation, spec.diameter_mm, spec.area_mm2, row.depth, x1 - x0, tuple(positions), None, ())


def band_top_row(footing: CombinedFooting, column: CombinedColumn, depth: float, bars: Sequence[RebarSpec]) -> BarRow | None:
    """El band superior de la columna (D-119) como fila de barras y en el ancho de su franja (con la d de la malla y
    inferior, como band_row): arriba, debajo de top.x si esa dirección va más cerca de la cara, como top.y. depth de la
    fila: la altura efectiva desde la cara inferior."""
    if column.band_top is None:
        return None
    specs = {bar.designation: bar for bar in bars}
    spec = specs[column.band_top.designation]
    top = footing.top
    above = specs[top.x.designation].diameter_mm if top is not None and top.x is not None and top.nearest == "x" else 0.0
    from_face = footing.cover + stirrup_diameter(footing, bars) + above + spec.diameter_mm / 2
    x0, x1 = strip_limits(footing, column, depth)
    first, last = footing.x_range
    inset = footing.cover + spec.diameter_mm / 2
    positions = uniform_positions(max(x0 + spec.diameter_mm / 2, first + inset), min(x1 - spec.diameter_mm / 2, last - inset),
                                  column.band_top.spacing)
    return BarRow("y", spec.designation, spec.diameter_mm, spec.area_mm2, footing.h - from_face, x1 - x0, tuple(positions), None, ())


def transverse_top(footing: CombinedFooting, row: BarRow | None, depth: float) -> BarRow | None:
    """Las barras superiores y (top.y) fuera de las zonas de band superior (D-119), como la malla inferior frente al band;
    sin band superior, en todo el largo. depth: la d de la malla y inferior, que fija el ancho de las franjas."""
    if row is None:
        return None
    zones = [strip_limits(footing, column, depth) for column in footing.columns if column.band_top is not None]
    kept = tuple(p for p in row.positions if not any(x0 - _TOLERANCE <= p <= x1 + _TOLERANCE for x0, x1 in zones))
    return replace(row, positions=kept)


def strip_top(footing: CombinedFooting, column: CombinedColumn, depth: float,
              bars: Sequence[RebarSpec]) -> tuple[BarRow | None, float | None]:
    """(fila, separación) de las barras superiores transversales de la franja: el band superior si lo hay (D-119); si no,
    top.y (D-097); None si no hay ninguno."""
    band = band_top_row(footing, column, depth, bars)
    if band is not None and column.band_top is not None:
        return band, column.band_top.spacing
    top = top_rows(footing, bars).get("y")
    if top is None or footing.top is None or footing.top.y is None:
        return None, None
    return top, footing.top.y.spacing


def transverse_bottom(footing: CombinedFooting, row: BarRow) -> BarRow:
    """La malla inferior en Y de la zapata combinada (D-097): solo fuera de las zonas de band, porque el band es el único
    refuerzo inferior transversal en el ancho de su franja; sin band, la malla en todo el largo."""
    zones = [strip_limits(footing, column, row.depth) for column in footing.columns if column.band is not None]
    if not zones:
        return row
    kept = tuple(p for p in row.positions if not any(x0 - _TOLERANCE <= p <= x1 + _TOLERANCE for x0, x1 in zones))
    return replace(row, positions=kept)


def strip_member(footing: CombinedFooting, column: CombinedColumn, rows: tuple[BarRow, BarRow | None, BarRow | None, BarRow | None],
                 limits: tuple[float, float] | None = None) -> Member:
    """La franja como viga (D-082): ancho × h, a lo largo de Y, con las barras que caen en él, con x desde su borde −X y
    la profundidad desde la cara superior. rows = (malla y inferior fuera de las zonas de band, band, band superior,
    top.y fuera de las zonas de band superior) (D-097, D-119). limits: el ancho de la franja de flexión
    (strip_limits) o el de cortante (shear_limits, D-151)."""
    row, band, band_top, top = rows
    x0, x1 = strip_limits(footing, column, row.depth) if limits is None else limits
    layers = []
    for source, depth in ((row, row.depth), (band, row.depth), *((upper, None if upper is None else footing.h - upper.depth)
                                                                 for upper in (band_top, top))):
        if source is None or depth is None:
            continue
        inside = positions_within(source, (x0, x1))
        if inside:
            layers.append(BarLayer(depth=depth, role="flexure",
                                   bars=tuple(BarPosition(designation=source.designation, x=position - x0) for position in inside)))
    layout = ReinforcementLayout(layers=tuple(layers), stirrups=None)
    placeholder = Station.model_construct(z=0.0, layout=layout, demands=Demands.model_construct(), case=None)
    return Member.model_construct(id=footing.id, type="beam", min_steel_exception=footing.min_steel_exception,
                                  statically_determinate=None, length=footing.ly,
                                  section=Section(bw=x1 - x0, h=footing.h, cover=footing.cover), stations=(placeholder,))


def _strip_shape(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
                 depth: float) -> tuple[Callable[[float, float], tuple[float, float]], str]:
    """Forma de la carga de la franja en el ancho B (D-080, D-085): ∫q dy y ∫y·q dy entre y0 y y1, sin escalar. Primero la
    presión en la línea de la columna; si es nula, la presión integrada en el ancho de la franja; si también es nula,
    uniforme (equilibra el cortante de la viga larga, repartido en todo el ancho). La nota dice qué forma se usó."""
    low, high = strip_edges(footing, column, depth)

    def line(y0: float, y1: float) -> tuple[float, float]:
        y0, y1 = max(y0, low), min(y1, high)
        return pressure.pressure.along_y(column.x, y0, y1) if y1 > y0 else (0.0, 0.0)

    if line(low, high)[0] > 0:
        return line, ""
    x0, x1 = strip_limits(footing, column, depth)

    def strip(y0: float, y1: float) -> tuple[float, float]:
        y0, y1 = max(y0, low), min(y1, high)
        force, _, first = pressure.pressure.resultant(((x0, y0), (x1, y0), (x1, y1), (x0, y1))) if y1 > y0 else (0.0, 0.0, 0.0)
        return force, first

    def uniform(y0: float, y1: float) -> tuple[float, float]:
        y0, y1 = max(y0, low), min(y1, high)
        return (y1 - y0, (y1**2 - y0**2) / 2) if y1 > y0 else (0.0, 0.0)

    if strip(low, high)[0] > 0:
        return strip, "carga con la forma de la presion integrada en el ancho de la franja (presion nula en la linea de la columna)"
    return uniform, "carga uniforme F/B (presion nula en toda la franja)"


def strip_load(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
               given: tuple[float, float]) -> tuple[Callable[[float, float], tuple[float, float]], str]:
    """Carga neta de la franja a lo largo de Y (D-095): la fuerza F de la columna repartida en el ancho B con la forma de
    `_strip_shape` y la carga uniforme w (zapata, relleno y sobrecargas, mayorada) en el ancho b de la franja:
    q(y) = s·forma(y) − w·b, con s tal que ∫q dy = F. Con la forma uniforme es F/B, como antes de D-095; donde la presión
    se anula queda −w·b (hacia abajo). Devuelve (∫q dy, ∫y·q dy) entre y0 y y1 (N, N·mm) y la nota de la forma."""
    force, depth = given
    low, high = strip_edges(footing, column, depth)  # fuera de los bordes no hay carga (D-164)
    shape, note = _strip_shape(footing, pressure, column, depth)
    x0, x1 = strip_limits(footing, column, depth)
    uniform = pressure.net_load * (x1 - x0)
    scale = (force + uniform * (high - low)) / shape(low, high)[0]

    def load(y0: float, y1: float) -> tuple[float, float]:
        force_part, first = shape(y0, y1)
        y0, y1 = max(y0, low), min(y1, high)
        span = max(y1 - y0, 0.0)
        return scale * force_part - uniform * span, scale * first - uniform * ((y1**2 - y0**2) / 2 if span else 0.0)

    return load, note


def strip_cantilever(footing: CombinedFooting, load: Callable[[float, float], tuple[float, float]], at: float,
                     side: float) -> tuple[float, float]:
    """(M, V) en y = at del voladizo de la franja hacia el borde `side` (+1: +Y; −1: −Y), con el cuerpo libre entre la
    sección y el borde: M > 0 tracciona la cara inferior; V es la carga neta hacia arriba de ese tramo. La carga ya es
    nula fuera de los bordes de la franja: basta integrar hasta el borde de la base."""
    low, high = footing.y_range
    y0, y1 = (at, high) if side > 0 else (low, at)
    net, first = load(y0, y1)
    return side * (first - at * net), net


def _cantilever_depth(footing: CombinedFooting, load: Callable[[float, float], tuple[float, float]], side: float,
                     depth_at: Callable[[float, float], float | None]) -> Callable[[float], float | None]:
    """La d del cortante en y del voladizo side, con el momento de la franja en y."""
    return lambda y: depth_at(y, strip_cantilever(footing, load, y, side)[0])


def strip_demands(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn, given: tuple[float, float],
                  depth_at: Callable[[float, float], float | None] | None = None) -> tuple[list[tuple[float, float, float, str]], str]:
    """(y, Mu, V, sección) en las caras ±Y de la columna, a d de ellas hacia el borde y, en cada voladizo, en el mayor
    momento negativo si no está en la cara (D-095), y la nota de la forma de carga usada. given = (F, d). V es la carga
    neta hacia arriba entre la sección y el borde, con signo (strip_cantilever): el cortante por flexión de la franja.
    depth_at(y, M) da la d del cortante de la sección en y con el momento M de la franja (D-131): con ella la sección a d
    de la cara queda a esa misma d (D-151); sin ella, a la d dada."""
    depth = given[1]
    low, high = strip_edges(footing, column, depth)
    load, note = strip_load(footing, pressure, column, given)
    result = []
    for side, face, name in ((1.0, column.y + column.cy / 2, "+Y"), (-1.0, column.y - column.cy / 2, "-Y")):
        at_d = face + side * depth if depth_at is None else section_at_depth(face, side, _cantilever_depth(footing, load, side, depth_at),
                                                                              depth)
        inside = low < at_d < high
        if not low < face < high:
            continue
        # La cara es sección de flexión; el cortante se revisa a d de ella (D-148).
        moment, shear = strip_cantilever(footing, load, face, side)
        result.append((face, moment, shear, f"cara {name}"))
        if inside:
            moment, shear = strip_cantilever(footing, load, at_d, side)
            result.append((at_d, moment, shear, f"a d de la cara {name}"))
        edge = high if side > 0 else low
        # El barrido no depende del refuerzo: se recuerda por geometría, caso, columna, F, d y lado (D-165).
        key = (footing.geometry_key, pressure, column.id, given, side)
        span = (face, edge)
        y, moment, shear = remembered(_PEAKS, key, partial(_negative_peak, footing, load, span, side))
        if moment < -_NEGLIGIBLE_MOMENT and moment < strip_cantilever(footing, load, face, side)[0]:
            result.append((y, moment, shear, f"mayor M negativo hacia el borde {name}"))
    return result, note


_PEAKS: dict[tuple[str, FactoredCase, str, tuple[float, float], float], tuple[float, float, float]] = {}


def _negative_peak(footing: CombinedFooting, load: Callable[[float, float], tuple[float, float]], span: tuple[float, float],
                   side: float) -> tuple[float, float, float]:
    """(y, M, V) del menor momento del voladizo entre la cara y el borde (64 puntos, D-095)."""
    face, edge = span
    points = [face + (edge - face) * index / _SWEEP for index in range(1, _SWEEP)]
    y, moment = min(((point, strip_cantilever(footing, load, point, side)[0]) for point in points), key=lambda item: item[1])
    return y, moment, strip_cantilever(footing, load, y, side)[1]


def strip_twist(footing: CombinedFooting, soil: Soil, given: tuple[FactoredCase, tuple[FootingLoad, ...]],
                limits: tuple[float, float]) -> float:
    """|mxy| de la franja (D-118): el mayor |T|/B en sus dos bordes, a cada lado del par de la columna."""
    beam = beam_case(footing, soil, *given)
    return max(abs(beam.twist(limits[0])), abs(beam.twist(limits[1])))


def strip_moments(moment: float, width: float, twist: float) -> list[float]:
    """Los momentos de diseño de la franja de ancho width por Wood-Armer (D-118), con my = M/b, |mxy| = twist y mx = 0:
    el de las barras inferiores (> 0) y el de las superiores (< 0) que no sean nulos; sin ninguno, [M]. Con mx = 0 el my*
    de Wood-Armer es el mayor posible, como mx* con my = 0 en la viga larga: juntos cumplen el criterio de Wood-Armer."""
    design = wood_armer(0.0, moment / width, twist)
    return [value for value in (design.bottom.y * width, design.top.y * width) if value != 0] or [moment]


StripService = tuple[Callable[[float, float], tuple[float, float]], float]  # la carga de la franja y su |mxy|


def _strip_services(footing: CombinedFooting, soil: Soil, given: tuple[int, float], limits: tuple[float, float]) -> list[StripService]:
    """La carga de la franja y su torsión de placa en cada caso de servicio, con el mismo reparto de los mayorados
    (D-174); given = (índice de la columna, d)."""
    index, depth = given
    column = footing.columns[index]
    services = []
    for pressure, loads in combined_service_cases(footing, soil):
        load, _ = strip_load(footing, pressure, column, (column_vertical(footing, soil, column, loads[index]), depth))
        services.append((load, strip_twist(footing, soil, (pressure, loads), limits)))
    return services


def _strip_service_moment(footing: CombinedFooting, services: list[StripService], at: tuple[float, str, float],
                          moment: float) -> float | None:
    """El momento de diseño de servicio en la sección y de la franja (Wood-Armer, del signo de moment); at = (y, nombre
    de la sección, ancho de la franja)."""
    y, label, width = at
    side = 1.0 if label.endswith("+Y") else -1.0
    values = (value for load, twist in services
              for value in strip_moments(strip_cantilever(footing, load, y, side)[0], width, twist))
    return service_moment(moment, values)


def _strip_checks(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, int], cases: Cases) -> list[Check]:
    row, index = rows
    column = footing.columns[index]
    x0, x1 = strip_limits(footing, column, row.depth)
    services = _strip_services(footing, soil, (index, row.depth), (x0, x1))
    top, _ = strip_top(footing, column, row.depth, basis.bars)  # el band superior o top.y (D-119)
    has_top = top is not None and bool(positions_within(top, (x0, x1)))
    member = strip_member(footing, column, strip_rows(basis, footing, column, row))
    sheared_member = strip_shear_member(basis, footing, column, row)  # ancho de cortante: columna + d a cada lado (D-151)
    width = sheared_member.section.bw
    title = f"Franja transversal de la columna {column.id}"
    checks = []
    for pressure, loads in cases:
        force = column_vertical(footing, soil, column, loads[index])
        demands, shape = strip_demands(footing, pressure, column, (force, row.depth),
                                       strip_depth_at(basis, footing, soil, (index, row), (pressure, loads)))
        twist = strip_twist(footing, soil, (pressure, loads), (x0, x1))
        jump = strip_torsion_shear(footing, soil, (pressure, loads), (x0, x1))
        plate = (f"Wood-Armer (D-118): M de la franja y mxy = {twist / 1e3:.2f} kN*m/m; (T(x1) - T(x0))/B = "
                 f"{jump / 1e3:.1f} kN: alivia el voladizo de un lado y carga el del otro (D-119, D-151)"
                 if twist > _NEGLIGIBLE_TWIST else "")
        for y, physical, shear, label in demands:
            z = y - footing.y_range[0]
            torsion_shear = torsion_side(jump, label)
            # El cortante se revisa en la sección crítica a d de la cara y más allá, con su Vu y su Mu (C.11.1.3.1, ACI
            # 9.4.3.2); en la cara solo la flexión (decisión del usuario, D-148).
            sheared = not label.startswith("cara")
            for order, moment in enumerate(strip_moments(physical, x1 - x0, twist)):
                section = f"{title}, {label}, {moment_sign(moment)}"
                # Vu = V por flexión + V por la torsión de placa (decisión del usuario, D-119).
                station = Station.model_construct(z=z, layout=member.stations[0].layout, case=pressure.case,
                                                  demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0,
                                                                                  vu=abs(shear + torsion_shear), v3=0.0, tu=0.0))
                # Las caras laterales de la franja quedan dentro del concreto: sin refuerzo superficial (D-083). El
                # cortante, con el ancho efectivo de cortante (D-151).
                service = _strip_service_moment(footing, services, (y, label, x1 - x0), moment)
                given = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False,
                                     service_mu=service)
                sheared_given = replace(given, member=sheared_member,
                                        station=station.model_copy(update={"layout": sheared_member.stations[0].layout}))
                flexure_values = _strip_values(physical, moment, (x1 - x0, twist))
                shear_values = (("V flexion", shear), ("V torsion", torsion_shear))
                if moment < 0 and (not has_top or plain_resists(basis, x1 - x0, footing.h, -moment)):  # D-140
                    # Momento negativo sin barras superiores transversales: concreto simple en el ancho de la franja (D-072,
                    # D-095) y el cortante de vigas. Con top.y lo revisa la flexión de vigas con esas barras (D-097).
                    note = section + "".join(f": {text}" for text in (shape, plate) if text)
                    plain = plain_strip_check(basis, footing, -moment, (label, pressure.case, note), x1 - x0)
                    checks.append(replace(plain, z=z, values=(*plain.values, *flexure_values)))
                    selected = list(shear_and_torsion_checks(sheared_given)) if order == 0 and sheared else []
                else:
                    selected = [*flexure_station_checks(given),
                                *(shear_and_torsion_checks(sheared_given) if order == 0 and sheared else ())]
                for check in selected:
                    extra = plate if check.name.startswith("Flexion") else ""
                    if check.name.startswith("Cortante"):
                        extra = "; ".join(text for text in (plate, f"ancho de cortante {width:.0f} mm (columna + d a cada lado, D-151)")
                                          if text)
                    note = section + "".join(f": {text}" for text in (check.note, shape, extra) if text)
                    added = flexure_values if check.name == FLEXURE_STRENGTH else (shear_values if check.name == STRENGTH else ())
                    check = replace(check, note=note, member=footing.id, case=pressure.case, z=z, values=(*check.values, *added))
                    checks.append(_beam_shear(_negative_minimum(check, moment)))
    return checks


def strip_rows(basis: Basis, footing: CombinedFooting, column: CombinedColumn,
               row: BarRow) -> tuple[BarRow, BarRow | None, BarRow | None, BarRow | None]:
    """Las filas de barras de la franja: la malla y inferior fuera de las zonas de band (row), el band, el band superior y
    top.y fuera de las zonas de band superior (D-097, D-119)."""
    return (row, band_row(footing, column, row, basis), band_top_row(footing, column, row.depth, basis.bars),
            transverse_top(footing, top_rows(footing, basis.bars).get("y"), row.depth))


def strip_shear_member(basis: Basis, footing: CombinedFooting, column: CombinedColumn, row: BarRow) -> Member:
    """La franja para el cortante (D-151): el ancho efectivo shear_limits con todas las barras que caen en él."""
    return strip_member(footing, column, strip_rows(basis, footing, column, row), shear_limits(footing, column, row.depth))


def strip_depth_at(basis: Basis, footing: CombinedFooting, soil: Soil, column_row: tuple[int, BarRow],
                   given: tuple[FactoredCase, tuple[FootingLoad, ...]]) -> Callable[[float, float], float | None]:
    """La d del cortante de la franja en y con el momento físico M (D-131, D-151): la de la franja de cortante con el
    momento de diseño con que se revisa el cortante (el primero de Wood-Armer, D-118)."""
    index, row = column_row
    column = footing.columns[index]
    member = strip_shear_member(basis, footing, column, row)
    limits = strip_limits(footing, column, row.depth)
    twist = strip_twist(footing, soil, given, limits)

    def depth_at(y: float, physical: float) -> float | None:
        moment = strip_moments(physical, limits[1] - limits[0], twist)[0]
        station = Station.model_construct(z=y - footing.y_range[0], layout=member.stations[0].layout, case=given[0].case,
                                          demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=0.0, v3=0.0, tu=0.0))
        return shear_depth(StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False))

    return depth_at


def strip_torsion_shear(footing: CombinedFooting, soil: Soil, given: tuple[FactoredCase, tuple[FootingLoad, ...]],
                        limits: tuple[float, float]) -> float:
    """El salto de la torsión de placa en la franja, (T(x1) − T(x0))/B (N), con signo (D-119, D-151): qy = ∂mxy/∂x con
    mxy = T/B, integrado en el ancho b. El salto es el momento respecto al eje X de las cargas de la franja (la presión en
    todo el ancho menos el par de la columna, que la flexión de la franja no toma, D-088)."""
    beam = beam_case(footing, soil, *given)
    # Con mxy = T/B(x): el salto de mxy entre los bordes de la franja (con B constante, (T(x1) − T(x0))/B; D-164).
    return beam.twist(limits[1]) - beam.twist(limits[0])


def torsion_side(jump: float, label: str) -> float:
    """El cortante por torsión de placa en el voladizo del lado de la sección (D-151), para sumarlo con su signo al de
    flexión (la carga neta hacia arriba más allá de la sección). Con T(x1) − T(x0) > 0 sobra momento de carga hacia +Y en la
    franja y la viga lo equilibra con un par que empuja hacia abajo el lado +Y y hacia arriba el −Y: alivia el voladizo
    +Y y carga el −Y. Así, en +Y es −(T(x1) − T(x0))/B y en −Y, +(T(x1) − T(x0))/B."""
    return -jump if label.endswith("+Y") else jump


def _strip_values(physical: float, moment: float, plate: tuple[float, float]) -> tuple[tuple[str, float], ...]:
    """Mu = M flexión + M torsión de la estación de franja y los momentos por unidad de ancho de Wood-Armer de las barras
    y (my = M/b, mx = 0, |mxy|), para la memoria y su tabla (D-118, D-119). plate = (b, |mxy|)."""
    width, twist = plate
    design = wood_armer(0.0, physical / width, twist)
    return (("M flexion", physical), ("M torsion", moment - physical), ("mx", 0.0), ("my", physical / width), ("mxy", twist),
            ("my* inf", design.bottom.y), ("my* sup", design.top.y))


PLATE_BOTTOM = "Direccion secundaria: torsion de placa (barras inferiores)"
PLATE_TOP = "Direccion secundaria: torsion de placa (barras superiores)"
PLATE_PLAIN = "Direccion secundaria: torsion de placa, concreto simple (cara superior)"
PLATE_SHEAR = "Direccion secundaria: torsion de placa, cortante"  # qy = ∂mxy/∂x fuera de las franjas (D-119)
_NEGLIGIBLE_SHEAR = 1.0  # N por metro
_PLATE_STRIP = 1000.0  # mm: fuera de las franjas, por metro de largo
_PLATE_SAMPLES = 64


def outside_twist(footing: CombinedFooting, soil: Soil, given: tuple[FactoredCase, tuple[FootingLoad, ...]],
                   zones: list[tuple[float, float]]) -> tuple[float, float]:
    """(x, |mxy|) del mayor momento torsor de placa fuera de las franjas, por muestreo del largo y en los bordes de cada
    franja (allí salta T por el par de la columna)."""
    beam = beam_case(footing, soil, *given)
    return max(((x, abs(beam.twist(x))) for x in _outside_points(footing, zones)), key=lambda item: item[1], default=(0.0, 0.0))


def outside_twist_envelope(footing: CombinedFooting, soil: Soil, depth: float, cases: Cases) -> float:
    """El mayor |mxy| fuera de las franjas en todos los casos (N·mm/mm), con d de la malla y; 0 en la T invertida, sin
    torsión de placa (D-118). La clase de los empalmes de las barras y fuera de las franjas parte de él (D-129)."""
    if footing.beam is not None:
        return 0.0
    zones = [strip_limits(footing, column, depth) for column in footing.columns]
    return max((outside_twist(footing, soil, given, zones)[1] for given in cases), default=0.0)


def _outside_points(footing: CombinedFooting, zones: list[tuple[float, float]]) -> list[float]:
    """Las secciones x fuera de las franjas: 64 tramos del largo y los bordes de cada franja."""
    start = footing.x_range[0]
    points = [start + footing.lx * index / _PLATE_SAMPLES for index in range(_PLATE_SAMPLES + 1)]
    points += [edge for zone in zones for edge in zone]
    return [x for x in points if not any(x0 + _TOLERANCE < x < x1 - _TOLERANCE for x0, x1 in zones)]


def plate_shear(footing: CombinedFooting, pressure: FactoredCase, x: float) -> float:
    """Cortante de placa por unidad de ancho en la dirección y fuera de las franjas (decisión del usuario, D-119): con
    my = 0, el equilibrio de la placa da qy = ∂mxy/∂x = (dT/dx)/B, y dT/dx en x es ∫y·q dy de la carga neta en esa
    línea; la carga uniforme w es simétrica en el ancho, así que solo cuenta la presión del suelo (N/mm). En una planta
    trapezoidal o en T/L, con el ancho local (D-164); allí el momento de w respecto al eje X no se anula y se suma."""
    low, high = footing.across(x)
    first = pressure.pressure.along_y(x, low, high)[1] - pressure.net_load * (high**2 - low**2) / 2
    return abs(first) / (high - low)


def _plate_shear_check(basis: Basis, footing: CombinedFooting, row: BarRow, beam: BeamCase,
                       zones: list[tuple[float, float]]) -> Check | None:
    """Cortante de placa fuera de las franjas por metro (D-119), en la sección de mayor qy, frente a φVc de cimentación
    por metro con la malla y inferior (Mu, el |mxy| de esa sección); None si es despreciable."""
    profile, materials = basis.profile, basis.materials
    x, shear = max(((x, plate_shear(footing, beam.pressure, x)) for x in _outside_points(footing, zones)),
                   key=lambda item: item[1], default=(0.0, 0.0))
    vu = shear * _PLATE_STRIP
    if vu <= _NEGLIGIBLE_SHEAR:
        return None
    clause = profile.footing.clauses()["one_way_shear"]
    lam = concrete_lambda(profile, materials)
    if isinstance(lam, Check):
        return replace(lam, name=PLATE_SHEAR, member=footing.id, case=beam.case)
    per_metre = row.bar_area * _PLATE_STRIP / footing.bottom.y.spacing
    rho = per_metre / (_PLATE_STRIP * row.depth)
    mu = abs(beam.twist(x)) * _PLATE_STRIP
    vc = profile.footing.one_way_concrete_shear(fc=materials.fc, lam=lam, bw=_PLATE_STRIP, d=row.depth, h=footing.h, rho_w=rho,
                                                vu=vu, mu=mu)
    phi = profile.shear.strength_reduction()
    where = f"a {x - footing.x_range[0]:.0f} mm del borde negativo a lo largo de la viga"
    breadth = footing.across(x)[1] - footing.across(x)[0]
    note = (f"Fuera de las franjas, {where}: dT/dx = {shear * breadth / 1e3:.1f} kN (presion del suelo en la linea), "
            f"qy = (dT/dx)/B = {shear:.2f} kN/m, por metro (cortante de placa, D-119)")
    return Check(PLATE_SHEAR, Status.PASS if vu <= phi * vc else Status.FAIL, clause=clause, demand=vu, capacity=phi * vc, unit="N",
                 member=footing.id, case=beam.case, note=note,
                 values=(("phi", phi), ("Vc", vc), ("bw", _PLATE_STRIP), ("d", row.depth), ("rho w", rho), ("lambda", lam),
                         ("fc", materials.fc), ("V flexion", 0.0), ("V torsion", vu)))  # fuera de las franjas, sin V de flexión


def _plate_flexure(basis: Basis, footing: CombinedFooting, layer: tuple[str, BarRow, float], given: tuple[float, str, str]) -> Check:
    """Flexión por metro de las barras y fuera de las franjas: layer = (nombre, fila, separación); given = (Mu, caso,
    nota). La fila trae su d desde la cara comprimida."""
    name, row, spacing = layer
    demand, case, note = given
    per_metre = row.bar_area * _PLATE_STRIP / spacing
    clause = basis.profile.footing.clauses()["strength"]
    strength = rectangular_strength(basis.profile, basis.materials, RectangularSection(_PLATE_STRIP, footing.h),
                                    (SteelLayer(row.depth, per_metre),))
    if not isinstance(strength, MomentStrength):
        return replace(check_from_errors(name, [strength]), clause=clause, member=footing.id, case=case)
    return Check(name, Status.PASS if strength.design >= demand else Status.FAIL, clause=clause, demand=demand,
                 capacity=strength.design, unit="N*mm", member=footing.id, case=case, note=note,
                 values=(("phi", strength.phi), ("Mn", strength.nominal), ("b", _PLATE_STRIP), ("h", footing.h), ("d", row.depth),
                         ("As", per_metre), ("fc", basis.materials.fc), ("fy", basis.materials.fy)))


def plate_secondary_checks(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> list[Check]:
    """Barras y fuera de las franjas con la torsión de placa (decisión del usuario, D-118): allí my = 0 y Wood-Armer da
    my* = +|mxy| (barras inferiores) y −|mxy| (superiores, o concreto simple sin ellas, D-072), por metro, en la sección
    de mayor |mxy| de cada caso. Sin torsión no hay nada que revisar (D-116: solo retracción y temperatura)."""
    if footing.beam is not None:
        return []
    bottom = transverse_bottom(footing, mat_rows(footing, footing.bottom, basis.bars)["y"])
    top = transverse_top(footing, top_rows(footing, basis.bars).get("y"), bottom.depth)  # fuera del band superior (D-119)
    zones = [strip_limits(footing, column, bottom.depth) for column in footing.columns]
    checks = []
    for pressure, loads in cases:
        x, twist = outside_twist(footing, soil, (pressure, loads), zones)
        if twist <= _NEGLIGIBLE_TWIST:
            continue
        demand = twist * _PLATE_STRIP
        beam = beam_case(footing, soil, pressure, loads)
        shear = _plate_shear_check(basis, footing, bottom, beam, zones)
        if shear is not None:
            checks.append(shear)
        data = (f"T = {beam.torque(x) / 1e6:.1f} kN*m, B = {beam.width(x):.0f} mm, mxy = T/B = {twist / 1e3:.2f} kN*m/m; my = 0, "
                "asi que Wood-Armer pide my* = +|mxy| abajo y -|mxy| arriba, por metro (D-118)")
        # El signo en la nota: la memoria separa con él la revisión de cada cara (D-095).
        where = f"a {x - footing.x_range[0]:.0f} mm del borde negativo a lo largo de la viga"
        note = {sign: f"Fuera de las franjas, {where}, momento {sign}: {data}" for sign in ("positivo", "negativo")}
        # Mu = M flexión (0: fuera de las franjas la carga va en X) + M torsión (Wood-Armer con my = 0), por metro (D-119).
        design = wood_armer(0.0, 0.0, twist)
        plate = (("mx", 0.0), ("my", 0.0), ("mxy", twist), ("my* inf", design.bottom.y), ("my* sup", design.top.y))
        lower = _plate_flexure(basis, footing, (PLATE_BOTTOM, bottom, footing.bottom.y.spacing), (demand, pressure.case, note["positivo"]))
        checks.append(replace(lower, values=(*lower.values, ("M flexion", 0.0), ("M torsion", demand), *plate)))
        if top is not None and footing.top is not None and footing.top.y is not None and not plain_resists(
                basis, _PLATE_STRIP, footing.h, demand):  # D-140: el concreto simple primero
            upper = _plate_flexure(basis, footing, (PLATE_TOP, top, footing.top.y.spacing), (demand, pressure.case, note["negativo"]))
        else:
            plain = plain_strip_check(basis, footing, demand, ("fuera de las franjas", pressure.case, note["negativo"]), _PLATE_STRIP)
            upper = replace(plain, name=PLATE_PLAIN)
        checks.append(replace(upper, values=(*upper.values, ("M flexion", 0.0), ("M torsion", -demand), *plate)))
    return checks


NEGATIVE_MINIMUM_NOTE = ("momento negativo de la franja: lo toma la viga de cimentacion; no se exige el acero minimo por "
                         "flexion y las barras superiores cumplen el minimo de retraccion y temperatura (decision del usuario, "
                         "D-116)")


def _negative_minimum(check: Check, moment: float) -> Check:
    """El acero mínimo por flexión de una sección de franja con momento negativo (decisión del usuario, D-116): no se
    exige, porque ese momento lo toma la viga de cimentación; las barras superiores de la dirección secundaria cumplen
    el mínimo de retracción y temperatura (D-097). Queda CUMPLE, sin demanda, con la nota."""
    if moment >= 0 or check.name != FLEXURE_MINIMUM:
        return check
    return replace(check, status=Status.PASS, demand=None, errors=(), note=f"{check.note}; {NEGATIVE_MINIMUM_NOTE}")


BEAM_SHEAR = "excedente para la viga"
BEAM_SHEAR_NOTE = ("el cortante que excede phi Vc lo debe tomar el refuerzo transversal de la viga de cimentacion "
                   "(decision del usuario, D-103)")
BEAM_SHEAR_RATIO = 0.99  # DCR que se reporta en la franja cuyo excedente toma la viga (decisión del usuario, D-114)


def _beam_shear(check: Check) -> Check:
    """Cortante de la franja sin estribos que excede φVc (decisión del usuario, D-103): CUMPLE con DCR = 0.99 (D-114) y
    el excedente Vu − φVc queda para el refuerzo transversal de la viga de cimentación, que no se verifica aquí; el
    Av,min que esa franja exigiría también queda a cargo de la viga."""
    if check.status is not Status.FAIL or check.name not in (STRENGTH, MIN_REINFORCEMENT):
        return check
    note = f"{check.note}; {BEAM_SHEAR_NOTE}"
    if check.name == MIN_REINFORCEMENT:
        return replace(check, status=Status.PASS, note=note)
    assert check.demand is not None and check.capacity is not None
    values = (*check.values, ("Vu", check.demand), (BEAM_SHEAR, check.demand - check.capacity))
    return replace(check, status=Status.PASS, demand=BEAM_SHEAR_RATIO * check.capacity, values=values, note=note)


def outside_checks(basis: Basis, footing: CombinedFooting, row: BarRow,
                   names: tuple[str, str] = (OUTSIDE_MINIMUM, OUTSIDE_SPACING)) -> list[Check]:
    """La malla y fuera de las franjas (o las aletas de la T invertida, D-093): mínimo de losa por unidad de longitud y
    separación de 3h y 450 mm; names = (nombre del mínimo, nombre de la separación)."""
    profile = basis.profile
    spacing = footing.bottom.y.spacing
    required = profile.footing.min_reinforcement_ratio(basis.materials.fy) * footing.h * 1000.0
    provided = row.bar_area / spacing * 1000.0
    maximum = profile.footing.combined_max_bar_spacing(footing.h)
    clauses = profile.footing.clauses()
    minimum_name, spacing_name = names
    return [Check(minimum_name, Status.PASS if provided >= required else Status.FAIL, clause=clauses["combined_min_reinforcement"],
                  demand=required, capacity=provided, unit="mm2/m", member=footing.id),
            Check(spacing_name, Status.PASS if spacing <= maximum else Status.FAIL, clause=clauses["combined_spacing"],
                  demand=spacing, capacity=maximum, unit="mm", member=footing.id)]


def _per_metre(basis: Basis, bar_set: BarSet) -> float:
    spec = next(bar for bar in basis.bars if bar.designation == bar_set.designation)
    return float(spec.area_mm2) * 1000.0 / bar_set.spacing


def shrinkage_checks(basis: Basis, footing: CombinedFooting) -> list[Check]:
    """Retracción y temperatura de la zapata combinada (ACI 24.4.3.2 y 24.4.3.3, NSR-10 C.7.12.2.1 y C.7.12.2.2; D-097):
    por zona y por metro, el refuerzo inferior más el superior de cada dirección suma al menos ρ·h, y la separación de
    cada capa no excede la del perfil. Zonas en Y: cada zona de band (band o malla y, más band superior o superior
    transversal, D-119) y el resto (malla y + superior transversal); en X, todo el ancho (malla x + superior x)."""
    profile, h = basis.profile, footing.h
    ratio = profile.footing.shrinkage_temperature_ratio(basis.materials.fy)
    required = ratio * h * 1000.0
    maximum = profile.footing.shrinkage_temperature_max_spacing(h)
    clause = profile.footing.clauses()["shrinkage_temperature"]
    top_x = [("superiores", footing.top.x)] if footing.top is not None and footing.top.x is not None else []
    top_y = [("superiores", footing.top.y)] if footing.top is not None and footing.top.y is not None else []
    banded = [column for column in footing.columns if column.band is not None or column.band_top is not None]
    zones: list[tuple[str, str, list[tuple[str, BarSet]]]] = [
        ("x", "en todo el ancho", [("inferiores", footing.bottom.x), *top_x]),
        ("y", "fuera de las zonas de band" if banded else "en todo el largo", [("inferiores", footing.bottom.y), *top_y])]
    for column in banded:
        lower = [("band", column.band)] if column.band is not None else [("inferiores", footing.bottom.y)]
        upper = [("band superior", column.band_top)] if column.band_top is not None else top_y
        zones.append(("y", f"zona de band de la columna {column.id}", [*lower, *upper]))
    checks = []
    for direction, zone, layers in zones:
        provided = sum(_per_metre(basis, bar_set) for _, bar_set in layers)
        checks.append(Check(f"{SHRINKAGE}: cuantia ({DIRECTIONS[direction]}, {zone})", Status.PASS if provided >= required else Status.FAIL,
                            clause=clause, demand=required, capacity=provided, unit="mm2/m", member=footing.id,
                            values=(("cuantia minima", ratio), ("h", h)), note="Inferior y superior sumados, por metro"))
        checks += [Check(f"{SHRINKAGE}: separacion ({DIRECTIONS[direction]}, {label}, {zone})",
                         Status.PASS if bar_set.spacing <= maximum else Status.FAIL, clause=clause, demand=bar_set.spacing,
                         capacity=maximum, unit="mm", member=footing.id) for label, bar_set in layers]
    return checks


def steel_excess(basis: Basis, section: tuple[float, float, float], provided: float, moment: float,
                 exception: bool = False) -> float:
    """As requerido / As suministrado (≤ 1): el mayor entre el de análisis y el mínimo de vigas; con la excepción de 4/3
    declarada (min_steel_exception, D-123), el mínimo es el menor entre As,min y 4/3 del de análisis. section = (ancho, h,
    d)."""
    width, h, depth = section
    profile, materials = basis.profile, basis.materials
    analysis = required_area(profile, materials, RectangularSection(width, h), depth, moment)
    if analysis is None or provided <= 0:
        return 1.0
    as_min = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, width, depth)
    minimum = profile.flexure.effective_min_reinforcement(as_min, analysis) if exception else as_min
    return min(max(analysis, minimum) / provided, 1.0)


def steel_required(basis: Basis, section: tuple[float, float, float], moment: float, exception: bool = False) -> float | None:
    """El As requerido de la sección (el de análisis o el mínimo de vigas, como steel_excess); None sin solución."""
    width, h, depth = section
    profile, materials = basis.profile, basis.materials
    analysis = required_area(profile, materials, RectangularSection(width, h), depth, moment)
    if analysis is None:
        return None
    as_min = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, width, depth)
    return max(analysis, profile.flexure.effective_min_reinforcement(as_min, analysis) if exception else as_min)


def bar_development_check(basis: Basis, footing: CombinedFooting, row: BarRow,
                          anchorage: tuple[str, float, str, float, float], text: tuple[str, str]) -> Check:
    """anchorage = (extremo declarado del grupo de barras, menor separación, capa: "bottom" o "top", As requerido / As
    suministrado, longitud disponible); text = (nombre, nota). Cada grupo trae su extremo (D-134)."""
    end, spacing, layer, excess, available = anchorage
    name, note = text
    # La altura bajo las barras superiores es la total (en la T invertida, la de la viga, D-093).
    bar = bar_anchorage(row, (end, spacing, layer == "bottom"), (footing.total_height, footing.cover), excess)
    required = required_length(basis.profile, basis.materials, bar, basis.seismic_level)
    return replace(development_check(name, required, available, f"{note}; Barras {END_TEXT[end]}"), member=footing.id)


def _row_spacing(row: BarRow) -> float:
    """Menor separación entre barras vecinas de una fila; con una sola barra, el ancho de la fila."""
    gaps = [b - a for a, b in zip(row.positions, row.positions[1:], strict=False)]
    return min(gaps) if gaps else row.width


def x_development(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, BarRow | None], cases: Cases) -> list[Check]:
    """Barras x desde la sección de mayor momento de su signo hasta el extremo más cercano, menos el recubrimiento."""
    bottom, top = rows
    positive, negative = extreme_moments(footing, soil, cases)
    start = footing.x_range[0]
    checks = []
    top_x = footing.top.x if footing.top is not None else None
    spacings = (footing.bottom.x.spacing, 0.0 if top_x is None else top_x.spacing)
    ends = (footing.bottom.x.end, "straight" if top_x is None else top_x.end)
    if footing.beam is not None:
        # Las capas de la viga de la T invertida (D-106): la inferior y la de flexión más alta, cada una con su extremo.
        flexure = [layer for layer in footing.beam.layers if layer.role == "flexure"]
        top_layer = min(flexure, key=lambda layer: layer.depth)
        ends = (footing.beam.bottom_layer.end or "straight", top_layer.end or "straight")
        # Barras de las capas de la viga de la T invertida (D-106): la menor separación entre las de cada capa.
        spacings = (_row_spacing(bottom), _row_spacing(top) if top is not None else 0.0)
    for moment_at, row, spacing, end, label in ((positive, bottom, spacings[0], ends[0], "inferiores"),
                                                (negative, top, spacings[1], ends[1], "superiores")):
        moment, x = moment_at
        if row is None or moment <= 0:
            continue
        low, high = footing.across(x)
        width = high - low
        if label == "superiores" and footing.beam is None and plain_resists(basis, width, footing.h, moment):
            continue  # D-140: el concreto simple resiste el momento negativo; las barras superiores no se exigen
        sign = "positivo" if label == "inferiores" else "negativo"
        name = f"{DEVELOPMENT} barras {label}, {PRINCIPAL}"
        # En una planta no rectangular (opción A del usuario, D-164) cuentan las barras que cruzan x y alcanzan a
        # desarrollarse allí: deben bastar para el As requerido de la sección; si no, no cumple.
        passing = list(row.positions)
        if footing.plan is not None:
            crossing = [y for y in row.positions if low < y < high
                        and (span := bar_extent(footing, y, x))[0] + footing.cover <= x <= span[1] - footing.cover]
            passing = developed(basis, footing, (row, end, spacing, label == "inferiores"), x, crossing)
            # En la T invertida la sección es una T: su flexión ya se revisa con ella (D-093, D-167); aquí, solo el anclaje.
            needed = (None if footing.beam is not None
                      else steel_required(basis, (width, footing.h, row.depth), moment, footing.min_steel_exception))
            provided = len(passing) * row.bar_area
            if needed is not None and provided < needed:
                checks.append(Check(name, Status.FAIL, clause=basis.profile.development.clauses()["tension"], demand=needed,
                                    capacity=provided, unit="mm2", member=footing.id,
                                    note=f"Desde la seccion de mayor momento {sign} (z = {x - start:.0f} mm): las barras que "
                                         f"alcanzan a desarrollarse ({len(passing)} de {len(crossing)}) no bastan para el As "
                                         "requerido (D-164)"))
                continue
            if not passing:
                continue
        # En la T invertida la sección no es rectangular: sin reducción por As requerido / As provisto (D-093).
        excess = 1.0 if footing.beam is not None else steel_excess(basis, (width, footing.h, row.depth),
                                                                    len(passing) * row.bar_area, moment, footing.min_steel_exception)
        # Hasta el extremo real de cada barra que pasa por la sección (D-164): la más corta rige.
        available = min(min(x - first, last - x) for first, last in (bar_extent(footing, y, x) for y in passing)) - footing.cover
        note = f"Desde la seccion de mayor momento {sign} (z = {x - start:.0f} mm)"
        if footing.plan is not None:
            note += f"; {len(passing)} barras que alcanzan a desarrollarse (D-164)"
        checks.append(bar_development_check(basis, footing, row, (end, spacing, "bottom" if label == "inferiores" else "top", excess,
                                                                  available), (name, note)))
    return checks


def strip_envelope(footing: CombinedFooting, soil: Soil, column_depth: tuple[int, float], cases: Cases) -> tuple[float, float]:
    """(mayor momento positivo en las caras, mayor momento negativo con signo positivo) de la franja de la columna en
    todos los casos, con Wood-Armer en la combinada rectangular (D-118); column_depth = (índice de la columna, d de la
    malla y). El desarrollo de las barras y y la clase de sus empalmes (D-129) parten de ellos."""
    index, depth = column_depth
    column = footing.columns[index]
    limits = strip_limits(footing, column, depth)
    width = limits[1] - limits[0]
    positive = negative = 0.0
    for pressure, loads in cases:
        demands, _ = strip_demands(footing, pressure, column, (column_vertical(footing, soil, column, loads[index]), depth))
        twist = strip_twist(footing, soil, (pressure, loads), limits) if footing.beam is None else 0.0
        design = [(strip_moments(moment, width, twist), label) for _, moment, _, label in demands]
        positive = max([positive, *(value for values, label in design if label.startswith("cara") for value in values)])
        negative = max([negative, *(-value for values, _ in design for value in values)])
    return positive, negative


def _y_development(basis: Basis, footing: CombinedFooting, soil: Soil, row: BarRow, cases: Cases) -> list[Check]:
    """Barras y de cada franja desde la cara de la columna hasta el borde, menos el recubrimiento: las inferiores (el band
    si lo hay, que es el único refuerzo inferior de la franja, D-097; si no, la malla y) con el mayor momento positivo de
    las caras, y las superiores y (D-097, D-099) con el mayor momento negativo de la franja."""
    checks = []
    for index, column in enumerate(footing.columns):
        band = band_row(footing, column, row, basis)
        limits = strip_limits(footing, column, row.depth)
        width = limits[1] - limits[0]
        positive, negative = strip_envelope(footing, soil, (index, row.depth), cases)
        low, high = strip_edges(footing, column, row.depth)  # los bordes locales en una planta no rectangular (D-164)
        available = min(high - (column.y + column.cy / 2), column.y - column.cy / 2 - low) - footing.cover
        note = f"Franja transversal de la columna {column.id}, desde la cara de la columna"
        bottom = band if band is not None else row
        bottom_area = len(positions_within(bottom, limits)) * bottom.bar_area
        if positive > 0 and bottom_area > 0:
            bar_set = column.band if column.band is not None else footing.bottom.y
            spacing = bar_set.spacing
            excess = steel_excess(basis, (width, footing.h, row.depth), bottom_area, positive, footing.min_steel_exception)
            name = (f"{DEVELOPMENT} refuerzo band (columna {column.id})" if band is not None
                    else f"{DEVELOPMENT} barras inferiores, {SECONDARY} (franja de la columna {column.id})")
            checks.append(bar_development_check(basis, footing, bottom, (bar_set.end, spacing, "bottom", excess, available), (name, note)))
        top, top_spacing = strip_top(footing, column, row.depth, basis.bars)  # el band superior o top.y (D-119)
        if top is None or top_spacing is None or negative <= _NEGLIGIBLE_MOMENT or plain_resists(basis, width, footing.h, negative):
            continue
        top_area = len(positions_within(top, limits)) * top.bar_area
        if top_area > 0:
            excess = steel_excess(basis, (width, footing.h, top.depth), top_area, negative, footing.min_steel_exception)
            name = (f"{DEVELOPMENT} band superior (columna {column.id})" if column.band_top is not None
                    else f"{DEVELOPMENT} barras superiores, {SECONDARY} (franja de la columna {column.id})")
            top_set = column.band_top if column.band_top is not None else footing.top.y if footing.top is not None else None
            end = "straight" if top_set is None else top_set.end
            checks.append(bar_development_check(basis, footing, top, (end, top_spacing, "top", excess, available), (name, note)))
    return checks


def column_checks(basis: Basis, footing: CombinedFooting, soil: Soil, cases: Cases) -> list[Check]:
    """V3J.3: punzonamiento, franjas transversales, malla y fuera de las franjas, desarrollo, aplastamiento y pasadores."""
    bottom = mat_rows(footing, footing.bottom, basis.bars)
    # La malla inferior en Y va solo fuera de las zonas de band (D-097).
    mesh = {"x": bottom["x"], "y": transverse_bottom(footing, bottom["y"])}
    checks = _punching(basis, footing, soil, mesh, cases)
    for index in range(len(footing.columns)):
        checks += _strip_checks(basis, footing, soil, (mesh["y"], index), cases)
    # Retracción y temperatura por zona reemplaza el mínimo de losa fuera de las franjas (D-097); la separación de 3h y
    # 450 mm de la malla y sigue (flexión en una dirección).
    checks += shrinkage_checks(basis, footing)
    checks += [check for check in outside_checks(basis, footing, mesh["y"]) if check.name == OUTSIDE_SPACING]
    checks += plate_secondary_checks(basis, footing, soil, cases)
    checks += x_development(basis, footing, soil, (bottom["x"], top_rows(footing, basis.bars).get("x")), cases)
    checks += _y_development(basis, footing, soil, mesh["y"], cases)
    first = footing.bottom.first
    for index, column in enumerate(footing.columns):
        support = Support(column.cx, column.cy, column.x, column.y, column.dowels, _note(column))
        dowels, area = dowel_checks(basis, footing, support, (bottom[first], bottom["y" if first == "x" else "x"]))
        loads = [(pressure.case, loads[index].p) for pressure, loads in cases]
        checks += [*dowels, *bearing_checks(basis, footing, support, (loads, area))]
    return checks
