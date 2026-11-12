"""Franjas transversales, punzonamiento, desarrollo, aplastamiento y pasadores de una zapata combinada (D-080, V3J.3; D-082).

En ejes de la viga: X a lo largo de ella (dirección principal; barras x), Y transversal (dirección secundaria; barras y,
franjas). Las verificaciones nombran las barras por su dirección y se devuelven en los ejes declarados (D-101).

Acción de cada columna como carga neta equivalente (la misma que entra en la resultante de la base): fuerza
F = `column_vertical` y momentos estáticos ∫x·q = F·x + My + H·Vx y ∫y·q = F·y − Mx + H·Vy, con H = h + pedestal.

- Punzonamiento por columna: perímetro a d/2 recortado con la base y la carga que lo atraviesa, la acción de la columna
  menos la carga neta de Bellos dentro del área crítica (`transferred_load`, la misma de la zapata aislada). Si los
  perímetros de las dos columnas se traslapan, además el perímetro común (D-086).
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
from structurelab_rc.domain.beam.station import checks_for, shear_and_torsion_checks
from structurelab_rc.domain.beam.station_input import StationInput
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.development import development_check, required_length
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.base import column_vertical
from structurelab_rc.domain.footing.combined_beam import extreme_moments, moment_sign
from structurelab_rc.domain.footing.connection import Support, bar_anchorage, bearing_checks, dowel_checks
from structurelab_rc.domain.footing.declared import DIRECTIONS, PRINCIPAL, SECONDARY
from structurelab_rc.domain.footing.flexure import plain_strip_check
from structurelab_rc.domain.footing.loads import FactoredCase
from structurelab_rc.domain.footing.mesh import BarRow, mat_rows, top_rows, uniform_positions
from structurelab_rc.domain.footing.shear import PunchedColumn, punching_checks, transferred_load
from structurelab_rc.domain.shear_strength import two_way_shear
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.perimeter import critical_perimeter
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
    bands = tuple(band for column in columns if (band := _band_row(footing, column, bottom["y"], basis)) is not None)
    return {"x": (bottom["x"],), "y": (bottom["y"], *bands)}


def _top_rows(basis: Basis, footing: CombinedFooting) -> dict[str, tuple[BarRow, ...]]:
    """Barras superiores alrededor de las columnas: top.x y top.y (D-097, D-099), si las hay."""
    return {direction: (row,) for direction, row in top_rows(footing, basis.bars).items()}


def _overlap(footing: CombinedFooting, depth: float) -> bool:
    """Los perímetros críticos de las dos columnas (a d/2 de sus caras, sin recortar) se traslapan."""
    first, second = footing.columns
    apart_x = abs(first.x - second.x) >= (first.cx + second.cx) / 2 + depth
    apart_y = abs(first.y - second.y) >= (first.cy + second.cy) / 2 + depth
    return not (apart_x or apart_y)


def _group_punching(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[dict[str, BarRow], float],
                    cases: Cases) -> list[Check]:
    """Perímetro común de las dos columnas si sus perímetros se traslapan (ACI R13.2.7.2, NSR-10 CR15.5.2; D-086): el
    menor rectángulo que contiene los dos perímetros, que es el perímetro a d/2 de la caja que contiene las dos columnas,
    recortado con la base; la carga es la suma de las acciones de las dos columnas menos la carga neta dentro de él. Se
    agrega a las revisiones individuales, que se conservan."""
    bottom, depth = rows
    if not _overlap(footing, depth):
        return []
    first, second = footing.columns
    left = min(first.x - first.cx / 2, second.x - second.cx / 2)
    right = max(first.x + first.cx / 2, second.x + second.cx / 2)
    low = min(first.y - first.cy / 2, second.y - second.cy / 2)
    high = max(first.y + first.cy / 2, second.y + second.cy / 2)
    size, centre = (right - left, high - low), ((left + right) / 2, (low + high) / 2)
    bounds = ((-footing.lx / 2, -footing.ly / 2), (footing.lx / 2, footing.ly / 2))
    perimeter = critical_perimeter(centre, *size, depth, bounds)
    punched = PunchedColumn(*size, *centre, _punching_rows(basis, footing, bottom, [first, second]),
                            f"Columnas {first.id} y {second.id} (perimetro comun)", MINIMUM_NOTE, _top_rows(basis, footing),
                            DIRECTIONS)
    checks = []
    for pressure, loads in cases:
        actions = [column_action(footing, soil, column, load) for column, load in zip(footing.columns, loads, strict=True)]
        total = (actions[0][0] + actions[1][0], actions[0][1] + actions[1][1], actions[0][2] + actions[1][2])
        load = transferred_load(total, pressure, perimeter)
        result = two_way_shear(basis.profile, basis.materials, perimeter, (*size, basis.profile.footing.punching_size_factor()), load)
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


def transverse_bottom(footing: CombinedFooting, row: BarRow) -> BarRow:
    """La malla inferior en Y de la zapata combinada (D-097): solo fuera de las zonas de band, porque el band es el único
    refuerzo inferior transversal en el ancho de su franja; sin band, la malla en todo el largo."""
    zones = [strip_limits(footing, column, row.depth) for column in footing.columns if column.band is not None]
    if not zones:
        return row
    kept = tuple(p for p in row.positions if not any(x0 - _TOLERANCE <= p <= x1 + _TOLERANCE for x0, x1 in zones))
    return replace(row, positions=kept)


def _inside(row: BarRow, limits: tuple[float, float]) -> list[float]:
    x0, x1 = limits
    return [position for position in row.positions if x0 - _TOLERANCE <= position <= x1 + _TOLERANCE]


def strip_member(footing: CombinedFooting, column: CombinedColumn, rows: tuple[BarRow, BarRow | None, BarRow | None]) -> Member:
    """La franja como viga (D-082): ancho de franja × h, a lo largo de Y, con las barras inferiores que caen en ella (el
    band si lo hay, D-097; si no, la malla y) y las superiores transversales (D-097), con x desde el borde −X de la franja
    y la profundidad desde la cara superior."""
    row, band, top = rows
    x0, x1 = strip_limits(footing, column, row.depth)
    layers = []
    for source, depth in ((row, row.depth), (band, row.depth), (top, None if top is None else footing.h - top.depth)):
        if source is None or depth is None:
            continue
        inside = _inside(source, (x0, x1))
        if inside:
            layers.append(BarLayer(depth=depth, role="flexure",
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


def strip_load(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
               given: tuple[float, float]) -> tuple[Callable[[float, float], tuple[float, float]], str]:
    """Carga neta de la franja a lo largo de Y (D-095): la fuerza F de la columna repartida en el ancho B con la forma de
    `_strip_shape` y la carga uniforme w (zapata, relleno y sobrecargas, mayorada) en el ancho b de la franja:
    q(y) = s·forma(y) − w·b, con s tal que ∫q dy = F. Con la forma uniforme es F/B, como antes de D-095; donde la presión
    se anula queda −w·b (hacia abajo). Devuelve (∫q dy, ∫y·q dy) entre y0 y y1 (N, N·mm) y la nota de la forma."""
    force, depth = given
    half = footing.ly / 2
    shape, note = _strip_shape(footing, pressure, column, depth)
    x0, x1 = strip_limits(footing, column, depth)
    uniform = pressure.net_load * (x1 - x0)
    scale = (force + uniform * footing.ly) / shape(-half, half)[0]

    def load(y0: float, y1: float) -> tuple[float, float]:
        force_part, first = shape(y0, y1)
        return scale * force_part - uniform * (y1 - y0), scale * first - uniform * (y1**2 - y0**2) / 2

    return load, note


def strip_cantilever(footing: CombinedFooting, load: Callable[[float, float], tuple[float, float]], at: float,
                     side: float) -> tuple[float, float]:
    """(M, V) en y = at del voladizo de la franja hacia el borde `side` (+1: +Y; −1: −Y), con el cuerpo libre entre la
    sección y el borde: M > 0 tracciona la cara inferior; V es la carga neta hacia arriba de ese tramo."""
    half = footing.ly / 2
    y0, y1 = (at, half) if side > 0 else (-half, at)
    net, first = load(y0, y1)
    return side * (first - at * net), net


def strip_demands(footing: CombinedFooting, pressure: FactoredCase, column: CombinedColumn,
                  given: tuple[float, float]) -> tuple[list[tuple[float, float, float, str]], str]:
    """(y, Mu, Vu, sección) en las caras ±Y de la columna, a d de ellas hacia el borde y, en cada voladizo, en el mayor
    momento negativo si no está en la cara (D-095), y la nota de la forma de carga usada. given = (F, d)."""
    depth = given[1]
    half = footing.ly / 2
    load, note = strip_load(footing, pressure, column, given)
    result = []
    for side, face, name in ((1.0, column.y + column.cy / 2, "+Y"), (-1.0, column.y - column.cy / 2, "-Y")):
        at_d = face + side * depth
        inside = -half < at_d < half
        if not -half < face < half:
            continue
        # En la cara, el cortante es el de la sección a d (ACI 9.4.3.2 y 13.2.7.2, NSR-10 C.11.1.3; D-082).
        moment, shear = strip_cantilever(footing, load, face, side)
        result.append((face, moment, abs(strip_cantilever(footing, load, at_d, side)[1] if inside else shear), f"cara {name}"))
        if inside:
            moment, shear = strip_cantilever(footing, load, at_d, side)
            result.append((at_d, moment, abs(shear), f"a d de la cara {name}"))
        points = [face + side * (half - side * face) * index / _SWEEP for index in range(1, _SWEEP)]
        y, moment = min(((point, strip_cantilever(footing, load, point, side)[0]) for point in points), key=lambda item: item[1])
        if moment < -_NEGLIGIBLE_MOMENT and moment < strip_cantilever(footing, load, face, side)[0]:
            shear = strip_cantilever(footing, load, y, side)[1]
            result.append((y, moment, abs(shear), f"mayor momento negativo hacia el borde {name}"))
    return result, note


def _strip_checks(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, int], cases: Cases) -> list[Check]:
    row, index = rows
    column = footing.columns[index]
    x0, x1 = strip_limits(footing, column, row.depth)
    top = top_rows(footing, basis.bars).get("y")
    has_top = top is not None and bool(_inside(top, (x0, x1)))
    member = strip_member(footing, column, (row, _band_row(footing, column, row, basis), top))
    title = f"Franja transversal de la columna {column.id}"
    checks = []
    for pressure, loads in cases:
        force = column_vertical(footing, soil, column, loads[index])
        demands, shape = strip_demands(footing, pressure, column, (force, row.depth))
        for y, moment, shear, label in demands:
            z = y + footing.ly / 2
            section = f"{title}, {label}, {moment_sign(moment)}"
            station = Station.model_construct(z=z, layout=member.stations[0].layout, case=pressure.case,
                                              demands=Demands.model_construct(pu=0.0, mu=moment, m2=0.0, vu=shear, v3=0.0, tu=0.0))
            # Las caras laterales de la franja quedan dentro del concreto: sin refuerzo superficial (D-083).
            given = StationInput(basis.profile, basis.materials, member, station, basis.bars, foundation=True, side_faces=False)
            if moment < 0 and not has_top:
                # Momento negativo sin barras superiores transversales: concreto simple en el ancho de la franja (D-072,
                # D-095) y el cortante de vigas. Con top.y lo revisa la flexión de vigas con esas barras (D-097).
                note = section + (f": {shape}" if shape else "")
                checks.append(replace(plain_strip_check(basis, footing, -moment, (label, pressure.case, note), x1 - x0), z=z))
                selected = list(shear_and_torsion_checks(given))
            else:
                selected = list(checks_for(given))
            for check in selected:
                note = section + "".join(f": {text}" for text in (check.note, shape) if text)
                checks.append(replace(check, note=note, member=footing.id, case=pressure.case, z=z))
    return checks


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
    cada capa no excede la del perfil. Zonas en Y: cada zona de band (band + superior transversal) y el resto (malla y +
    superior transversal); en X, todo el ancho (malla x + superior x)."""
    profile, h = basis.profile, footing.h
    ratio = profile.footing.shrinkage_temperature_ratio(basis.materials.fy)
    required = ratio * h * 1000.0
    maximum = profile.footing.shrinkage_temperature_max_spacing(h)
    clause = profile.footing.clauses()["shrinkage_temperature"]
    top_x = [("superiores", footing.top.x)] if footing.top is not None and footing.top.x is not None else []
    top_y = [("superiores", footing.top.y)] if footing.top is not None and footing.top.y is not None else []
    banded = [column for column in footing.columns if column.band is not None]
    zones: list[tuple[str, str, list[tuple[str, BarSet]]]] = [
        ("x", "en todo el ancho", [("inferiores", footing.bottom.x), *top_x]),
        ("y", "fuera de las zonas de band" if banded else "en todo el largo", [("inferiores", footing.bottom.y), *top_y])]
    zones += [("y", f"zona de band de la columna {column.id}", [("band", column.band), *top_y])
              for column in banded if column.band is not None]
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


def steel_excess(basis: Basis, section: tuple[float, float, float], provided: float, moment: float) -> float:
    """As requerido / As suministrado (≤ 1): el mayor entre el de análisis y el mínimo de vigas efectivo. section = (ancho,
    h, d)."""
    width, h, depth = section
    profile, materials = basis.profile, basis.materials
    analysis = required_area(profile, materials, RectangularSection(width, h), depth, moment)
    if analysis is None or provided <= 0:
        return 1.0
    as_min = profile.flexure.min_flexural_reinforcement(materials.fc, materials.fy, width, depth)
    return min(max(analysis, profile.flexure.effective_min_reinforcement(as_min, analysis)) / provided, 1.0)


def bar_development_check(basis: Basis, footing: CombinedFooting, row: BarRow, anchorage: tuple[float, str, float, float],
                          text: tuple[str, str]) -> Check:
    """anchorage = (menor separación, capa: "bottom" o "top", As requerido / As suministrado, longitud disponible);
    text = (nombre, nota). El tipo de extremo es el de la malla inferior o el de las barras superiores (D-082, D-099)."""
    spacing, layer, excess, available = anchorage
    name, note = text
    bottom = layer == "bottom"
    end = footing.bottom.end if bottom or footing.top is None else footing.top.end
    # La altura bajo las barras superiores es la total (en la T invertida, la de la viga, D-093).
    bar = bar_anchorage(row, (end, spacing, bottom), (footing.total_height, footing.cover), excess)
    required = required_length(basis.profile, basis.materials, bar, basis.seismic_level)
    kind = "Barras con gancho estandar" if end == "hook" else "Barras rectas"
    return replace(development_check(name, required, available, f"{note}; {kind}"), member=footing.id)


def x_development(basis: Basis, footing: CombinedFooting, soil: Soil, rows: tuple[BarRow, BarRow | None], cases: Cases) -> list[Check]:
    """Barras x desde la sección de mayor momento de su signo hasta el extremo más cercano, menos el recubrimiento."""
    bottom, top = rows
    positive, negative = extreme_moments(footing, soil, cases)
    half = footing.lx / 2
    checks = []
    top_spacing = footing.top.x.spacing if footing.top is not None and footing.top.x is not None else 0.0
    for moment_at, row, spacing, label in ((positive, bottom, footing.bottom.x.spacing, "inferiores"),
                                           (negative, top, top_spacing, "superiores")):
        moment, x = moment_at
        if row is None or moment <= 0:
            continue
        # En la T invertida la sección no es rectangular: sin reducción por As requerido / As provisto (D-093).
        excess = 1.0 if footing.beam is not None else steel_excess(basis, (footing.ly, footing.h, row.depth), row.area, moment)
        available = min(x + half, half - x) - footing.cover
        sign = "positivo" if label == "inferiores" else "negativo"
        note = f"Desde la seccion de mayor momento {sign} (z = {x + half:.0f} mm)"
        checks.append(bar_development_check(basis, footing, row, (spacing, "bottom" if label == "inferiores" else "top", excess,
                                                                  available), (f"{DEVELOPMENT} barras {label}, {PRINCIPAL}", note)))
    return checks


def _y_development(basis: Basis, footing: CombinedFooting, soil: Soil, row: BarRow, cases: Cases) -> list[Check]:
    """Barras y de cada franja desde la cara de la columna hasta el borde, menos el recubrimiento: las inferiores (el band
    si lo hay, que es el único refuerzo inferior de la franja, D-097; si no, la malla y) con el mayor momento positivo de
    las caras, y las superiores y (D-097, D-099) con el mayor momento negativo de la franja."""
    half = footing.ly / 2
    top = top_rows(footing, basis.bars).get("y")
    checks = []
    for index, column in enumerate(footing.columns):
        band = _band_row(footing, column, row, basis)
        limits = strip_limits(footing, column, row.depth)
        width = limits[1] - limits[0]
        positive = negative = 0.0
        for pressure, loads in cases:
            demands, _ = strip_demands(footing, pressure, column, (column_vertical(footing, soil, column, loads[index]), row.depth))
            positive = max([positive, *(moment for _, moment, _, label in demands if label.startswith("cara"))])
            negative = max([negative, *(-moment for _, moment, _, _ in demands)])
        available = min(half - (column.y + column.cy / 2), column.y - column.cy / 2 + half) - footing.cover
        note = f"Franja transversal de la columna {column.id}, desde la cara de la columna"
        bottom = band if band is not None else row
        bottom_area = len(_inside(bottom, limits)) * bottom.bar_area
        if positive > 0 and bottom_area > 0:
            spacing = column.band.spacing if column.band is not None else footing.bottom.y.spacing
            excess = steel_excess(basis, (width, footing.h, row.depth), bottom_area, positive)
            name = (f"{DEVELOPMENT} refuerzo band (columna {column.id})" if band is not None
                    else f"{DEVELOPMENT} barras inferiores, {SECONDARY} (franja de la columna {column.id})")
            checks.append(bar_development_check(basis, footing, bottom, (spacing, "bottom", excess, available), (name, note)))
        if top is None or footing.top is None or footing.top.y is None or negative <= _NEGLIGIBLE_MOMENT:
            continue
        top_area = len(_inside(top, limits)) * top.bar_area
        if top_area > 0:
            excess = steel_excess(basis, (width, footing.h, top.depth), top_area, negative)
            checks.append(bar_development_check(basis, footing, top, (footing.top.y.spacing, "top", excess, available),
                                                (f"{DEVELOPMENT} barras superiores, {SECONDARY} (franja de la columna {column.id})", note)))
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
    checks += x_development(basis, footing, soil, (bottom["x"], top_rows(footing, basis.bars).get("x")), cases)
    checks += _y_development(basis, footing, soil, mesh["y"], cases)
    first = footing.bottom.first
    for index, column in enumerate(footing.columns):
        support = Support(column.cx, column.cy, column.x, column.y, column.dowels, _note(column))
        dowels, area = dowel_checks(basis, footing, support, (bottom[first], bottom["y" if first == "x" else "x"]))
        loads = [(pressure.case, loads[index].p) for pressure, loads in cases]
        checks += [*dowels, *bearing_checks(basis, footing, support, (loads, area))]
    return checks
