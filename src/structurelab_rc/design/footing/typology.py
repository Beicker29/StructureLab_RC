"""Diseño de una tipología de zapata para un grupo de columnas (V3F, D-069).

El diseño no tiene fórmulas propias: propone zapatas y las aprueba con la misma verificación de V3C y V3D
(`domain/footing/checks.footing_checks`). Para proponer barras usa los momentos de `domain/footing/flexure` y el As
requerido de `domain/flexure_strength`; para los pasadores, el aplastamiento de `codes` y A2 de `domain/footing`.

Orden de la búsqueda: planta (crece si fallan la presión o el contacto; la primera viable y dos más, una heurística),
espesor (el menor con solución, por bisección, y luego los mayores mientras la cota inferior del costo no alcance el
mejor, D-076) y, para cada espesor, las mallas de menor costo: la inferior con sus pasadores y la superior más liviana que
pasa, que se verifican por separado y se confirman juntas. Una tipología fija la zapata (dimensiones, mallas y f'c);
cada columna del grupo se verifica con su propia sección, sus cargas y sus pasadores.
"""

import json
import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.domain.footing.checks import footing_checks
from structurelab_rc.domain.footing.connection import bearing_area
from structurelab_rc.domain.footing.flexure import PLAIN, face_moments
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.design import DesignColumn, FootingDesign, FootingDesignProject
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials

_MAT_PREFIXES = ("Flexion malla", "Deformacion neta de traccion malla", "Acero minimo malla", "Separacion maxima malla",
                 "Franja central", "Desarrollo malla", PLAIN)
_MAT_TRIES = 12
_DOWELS_MIN = 4
_DOWEL_PREFIX = "Pasadores"
_EXTRA_PLANS = 2  # plantas mayores que se exploran después de la primera viable
_MM3_PER_M3 = 1e9


@dataclass(frozen=True)
class Typology:
    """Zapata tipo: f'c (MPa), dimensiones (mm) y mallas en el formato de entrada (top None si no hay malla superior)."""

    fc: float
    lx: float
    ly: float
    h: float
    bottom: dict[str, Any]
    top: dict[str, Any] | None


def typology_key(typology: Typology) -> tuple[Any, ...]:
    """Tipologías iguales (D-074): coinciden f'c, lx, ly, h, malla inferior y malla superior; los pasadores son de cada
    columna y no cuentan."""
    return (typology.fc, typology.lx, typology.ly, typology.h, json.dumps(typology.bottom, sort_keys=True),
            json.dumps(typology.top, sort_keys=True))


@dataclass(frozen=True)
class GroupDesign:
    """Tipología aprobada para todas las columnas del grupo, con los pasadores de cada una y su costo."""

    typology: Typology
    dowels: dict[str, dict[str, Any]]
    cost: float
    concrete: float
    steel: float


@dataclass(frozen=True)
class Context:
    """Lo que no cambia durante la búsqueda."""

    project: FootingDesignProject
    profile: Profile
    bars: Sequence[RebarSpec]

    @property
    def design(self) -> FootingDesign:
        return self.project.design

    @property
    def soil(self) -> Soil:
        return self.project.soil

    def materials(self, fc: float) -> Materials:
        m = self.project.materials
        return Materials(fc=fc, fy=m.fy, fyt=m.fyt, concrete=m.concrete, coating=m.coating)

    def spec(self, designation: str) -> RebarSpec:
        return next(bar for bar in self.bars if bar.designation == designation)


def footing_for(ctx: Context, typology: Typology, column: DesignColumn, dowels: dict[str, Any] | None) -> Footing:
    """La zapata de una columna con la tipología: columna centrada, con sus cargas y sus pasadores."""
    design = ctx.design
    data = {"id": column.id, "lx": typology.lx, "ly": typology.ly, "h": typology.h, "cover": design.cover,
            "fill_height": design.fill_height, "pedestal_height": design.pedestal_height,
            "surcharge_dead_kNm2": design.surcharge_dead, "surcharge_live_kNm2": design.surcharge_live,
            "column": {"cx": column.cx, "cy": column.cy, "offset_x": 0.0, "offset_y": 0.0, "dowels": dowels},
            "bottom": typology.bottom, "top": typology.top, "loads": list(column.loads)}
    return Footing.model_validate(data)


def checks_for(ctx: Context, typology: Typology, column: DesignColumn, dowels: dict[str, Any] | None) -> list[Check]:
    footing = footing_for(ctx, typology, column, dowels)
    return footing_checks(Basis(ctx.profile, ctx.materials(typology.fc), ctx.bars, ctx.project.seismic.level), footing, ctx.soil)


def _failures(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.status is not Status.PASS]


def _plans(ctx: Context, columns: Sequence[DesignColumn], start: tuple[float, float]) -> Iterator[tuple[float, float]]:
    """Plantas candidatas en orden creciente, desde start, según la forma pedida (D-069), hasta plan_max."""
    design = ctx.design
    step = design.plan_step
    cx, cy = max(column.cx for column in columns), max(column.cy for column in columns)
    size = max(start[0], start[1], min(cx, cy) + 2 * step)
    while True:
        if design.shape == "square":
            lx = ly = size
        elif design.shape == "ratio":
            assert design.ratio is not None
            ly = size
            lx = math.ceil(design.ratio * ly / step) * step
        else:
            cantilever = size / 2
            lx, ly = cx + 2 * cantilever, cy + 2 * cantilever
        if max(lx, ly) > design.plan_max:
            return
        if lx >= start[0] and ly >= start[1]:
            yield lx, ly
        size += step


def _initial_size(ctx: Context, columns: Sequence[DesignColumn]) -> float:
    """Cota inferior de la planta: el mayor cociente de la carga de servicio sobre la presión admisible de su caso (con el
    aumento sísmico, D-079), sin pesos ni momentos."""
    largest = max((load.p / ctx.soil.bearing_capacity(load.seismic) for column in columns for load in column.loads
                   if load.kind == "service"), default=0.0)
    side = math.sqrt(max(largest, 0.0))
    return math.floor(side / ctx.design.plan_step) * ctx.design.plan_step


def _bar_options(ctx: Context, fc: float, section: tuple[float, float], depth_of: Any, demand: float) -> list[tuple[float, dict[str, Any]]]:
    """Barras de una dirección: para cada designación, la separación que da el As requerido (y As,min), con su peso por
    unidad de largo de la dirección; ordenadas por peso."""
    design, profile = ctx.design, ctx.profile
    materials = ctx.materials(fc)
    width, h = section
    max_spacing = math.floor(profile.footing.max_bar_spacing(h) / design.spacing_step) * design.spacing_step
    options = []
    for designation in design.bars:
        spec = ctx.spec(designation)
        depth = depth_of(spec.diameter_mm)
        needed = required_area(profile, materials, RectangularSection(width, h), depth, demand)
        if needed is None:  # ninguna cuantía alcanza el momento con esta altura
            continue
        area = max(needed, profile.footing.min_reinforcement_ratio(materials.fy) * width * h)
        count = max(math.ceil(area / spec.area_mm2), 2)
        usable = width - 2 * design.cover - spec.diameter_mm
        spacing = min(math.floor(usable / (count - 1) / design.spacing_step) * design.spacing_step, max_spacing)
        while spacing > spec.diameter_mm + design.spacing_step / 2:
            bars = math.floor(usable / spacing + 1e-6) + 1
            options.append((bars * spec.mass_kg_m, {"designation": designation, "spacing": spacing}))
            spacing -= design.spacing_step
            if len(options) > _MAT_TRIES * len(design.bars):
                break
    return sorted(options, key=lambda option: option[0])


def _mat_candidates(ctx: Context, typology: Typology, demands: dict[str, float]) -> Iterator[dict[str, Any]]:
    """Mallas candidatas de menor a mayor peso; la dirección larga va primero (más cerca de la cara)."""
    lx, ly, h, fc = typology.lx, typology.ly, typology.h, typology.fc
    first = "x" if lx >= ly else "y"
    second = "y" if first == "x" else "x"
    cover = ctx.design.cover
    widths = {"x": ly, "y": lx}
    lengths = {"x": lx, "y": ly}
    first_options = _bar_options(ctx, fc, (widths[first], h), lambda db: h - cover - db / 2, demands[first])
    combos = []
    for weight_a, set_a in first_options[:_MAT_TRIES]:
        db_a = ctx.spec(set_a["designation"]).diameter_mm
        second_options = _bar_options(ctx, fc, (widths[second], h), lambda db, db_a=db_a: h - cover - db_a - db / 2,
                                      demands[second])
        for weight_b, set_b in second_options[:_MAT_TRIES]:
            total = weight_a * lengths[first] + weight_b * lengths[second]
            combos.append((total, {"first": first, "end": ctx.design.end, first: set_a, second: set_b}))
    for _, mat in sorted(combos, key=lambda combo: combo[0])[: _MAT_TRIES * 2]:
        yield mat


def _demands(ctx: Context, columns: Sequence[DesignColumn], typology: Typology, sign: float) -> dict[str, float]:
    """Mayor momento de cada dirección (positivo con sign = 1, negativo con sign = −1) entre las columnas del grupo."""
    demands = {"x": 0.0, "y": 0.0}
    for column in columns:
        footing = footing_for(ctx, typology, column, None)
        cases, _ = factored_cases(footing, ctx.soil)
        for case in cases:
            moments = face_moments(footing, case).moments
            for direction in ("x", "y"):
                demands[direction] = max(demands[direction], *(sign * moment for moment in moments[direction]))
    return demands


def _dowel_options(ctx: Context, typology: Typology, column: DesignColumn) -> list[dict[str, Any]]:
    """Pasadores candidatos, de menor a mayor área: cubren 0.005Ag y la compresión que excede φBn (D-065), en número
    par, al menos 4; el anclaje lo decide la verificación."""
    footing = footing_for(ctx, typology, column, None)
    a1, a2 = bearing_area(footing)
    bearing = ctx.profile.bearing
    phi = bearing.strength_reduction()
    capacity = phi * bearing.nominal_bearing(typology.fc, a1, a2)
    excess = max((load.p - capacity for load in column.loads if load.kind == "factored"), default=0.0)
    required = max(ctx.profile.footing.dowel_min_ratio() * a1, max(excess, 0.0) / (phi * ctx.project.materials.fy))
    options = []
    for designation in ctx.design.dowel_bars:
        spec = ctx.spec(designation)
        count = max(_DOWELS_MIN, math.ceil(required / spec.area_mm2))
        count += count % 2
        options.append((count * spec.area_mm2, {"designation": designation, "count": count}))
    return [option for _, option in sorted(options, key=lambda option: option[0])]


def column_checks(ctx: Context, typology: Typology, column: DesignColumn) -> tuple[list[Check], dict[str, Any]]:
    """Fallas de la columna con la tipología y sus pasadores: los de menor área que aprueban sus verificaciones (área,
    anclaje y exceso de aplastamiento); si ninguno, los de menor área."""
    first: tuple[list[Check], dict[str, Any]] | None = None
    for dowels in _dowel_options(ctx, typology, column):
        failures = _failures(checks_for(ctx, typology, column, dowels))
        if not any(failure.name.startswith(_DOWEL_PREFIX) for failure in failures):
            return failures, dowels
        first = first or (failures, dowels)
    assert first is not None
    return first


def column_cost(ctx: Context, typology: Typology, column: DesignColumn, dowels: dict[str, Any]) -> tuple[float, float, float]:
    """Costo, volumen de concreto (m³) y peso de acero (kg) de la zapata de una columna con la tipología y sus pasadores:
    mallas rectas de borde a borde menos el recubrimiento y pasadores hasta la malla inferior. Es el costo por par de la
    DP y del MILP (E2): el de un grupo es la suma del de sus columnas."""
    design = ctx.design
    concrete = (typology.lx * typology.ly * typology.h + column.cx * column.cy * design.pedestal_height) / _MM3_PER_M3
    steel = _mat_mass(ctx, typology, typology.bottom) + (0.0 if typology.top is None else _mat_mass(ctx, typology, typology.top))
    steel += dowels["count"] * ctx.spec(dowels["designation"]).mass_kg_m * (typology.h - design.cover) / 1000
    price = design.prices
    return concrete * price.concrete(typology.fc) + steel * price.steel_per_kg, concrete, steel


def _cost(
    ctx: Context, typology: Typology, columns: Sequence[DesignColumn], dowels: dict[str, dict[str, Any]]
) -> tuple[float, float, float]:
    """Costo, concreto y acero del grupo: la suma de los de sus columnas."""
    parts = [column_cost(ctx, typology, column, dowels[column.id]) for column in columns]
    return sum(part[0] for part in parts), sum(part[1] for part in parts), sum(part[2] for part in parts)


def _mat_mass(ctx: Context, typology: Typology, mat: dict[str, Any]) -> float:
    cover = ctx.design.cover
    mass = 0.0
    for direction, width, length in (("x", typology.ly, typology.lx), ("y", typology.lx, typology.ly)):
        spec = ctx.spec(mat[direction]["designation"])
        count = math.floor((width - 2 * cover - spec.diameter_mm) / mat[direction]["spacing"] + 1e-6) + 1
        mass += count * spec.mass_kg_m * (length - 2 * cover) / 1000
    return mass


def _verify(ctx: Context, typology: Typology, columns: Sequence[DesignColumn]) -> tuple[list[Check], dict[str, dict[str, Any]]]:
    failures, dowels = [], {}
    for column in columns:
        column_failures, dowels[column.id] = column_checks(ctx, typology, column)
        failures += column_failures
    return failures, dowels


def priced(ctx: Context, typology: Typology, columns: Sequence[DesignColumn], dowels: dict[str, dict[str, Any]]) -> GroupDesign:
    """Tipología ya aprobada para las columnas, con sus pasadores: su costo, sin volver a verificar."""
    cost, concrete, steel = _cost(ctx, typology, columns, dowels)
    return GroupDesign(typology, dowels, cost, concrete, steel)


def covers(ctx: Context, typology: Typology, column: DesignColumn) -> dict[str, Any] | None:
    """Los pasadores con que la tipología aprueba todas las verificaciones de la columna, o None si no la cubre."""
    failures, dowels = column_checks(ctx, typology, column)
    return None if failures else dowels


def _soil_ok(ctx: Context, columns: Sequence[DesignColumn], typology: Typology) -> bool:
    """Presión, contacto y equilibrio de los casos mayorados: dependen solo de la planta y del espesor, no de las mallas."""
    for column in columns:
        footing = footing_for(ctx, typology, column, None)
        if _failures(service_checks(ctx.profile, footing, ctx.soil)) or factored_cases(footing, ctx.soil)[1]:
            return False
    return True


def _top_related(check: Check) -> bool:
    """Verificaciones que dependen solo de la malla superior (o, sin ella, del concreto simple): separables de la inferior,
    cuya altura efectiva, cortante, punzonamiento y anclaje de pasadores no dependen de la superior (D-076)."""
    return "malla superior" in check.name or check.name.startswith(PLAIN)


def _at_height(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h: float) -> GroupDesign | str:
    """Solución de menor costo con este espesor (D-076); "soil" si la planta no cumple el suelo, "h" si falta espesor.

    Las verificaciones de las dos mallas son separables: la malla inferior de menor costo (con sus pasadores, cuyo anclaje
    depende de ella) se busca sin malla superior, ignorando lo que depende de la superior; con ella, la superior más liviana
    que pasa (ninguna primero, si el perfil permite concreto simple con el nivel sísmico, D-072; luego todas las
    candidatas). El par se confirma con una verificación completa."""
    design = ctx.design
    any_bars = {"designation": design.bars[0], "spacing": design.spacing_step * 4}
    provisional = Typology(fc, plan[0], plan[1], h, {"first": "x", "end": design.end, "x": any_bars, "y": any_bars}, None)
    if not _soil_ok(ctx, columns, provisional):
        return "soil"
    bottoms = sorted(_mat_candidates(ctx, provisional, _demands(ctx, columns, provisional, 1.0)),
                     key=lambda mat: _mat_mass(ctx, provisional, mat))
    negative = _demands(ctx, columns, provisional, -1.0)
    tops: list[dict[str, Any] | None] = [None]
    if max(negative.values()) > 0:
        candidates = sorted(_mat_candidates(ctx, provisional, negative), key=lambda mat: _mat_mass(ctx, provisional, mat))
        tops = [None, *candidates] if ctx.profile.plain.permitted_in_foundations(ctx.project.seismic.level) else [*candidates]
    bottom = _cheapest_bottom(ctx, columns, provisional, bottoms)
    if bottom is None:
        return "h"
    for top in tops:
        typology = Typology(fc, plan[0], plan[1], h, bottom, top)
        failures, dowels = _verify(ctx, typology, columns)
        if not failures:
            return priced(ctx, typology, columns, dowels)
        if not all(_top_related(failure) for failure in failures):
            return _jointly(ctx, columns, provisional, bottoms, tops)  # no separó: enumeración conjunta
    return "h"


def _cheapest_bottom(
    ctx: Context, columns: Sequence[DesignColumn], provisional: Typology, bottoms: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """La malla inferior de menor costo (mallas y pasadores) que aprueba lo que no depende de la superior; None si falta
    espesor. Se recorre de menor a mayor peso y se para cuando su acero más los pasadores mínimos ya no pueden ganar."""
    price = ctx.design.prices.steel_per_kg
    dowels_floor = sum(min(option["count"] * ctx.spec(option["designation"]).mass_kg_m for option in
                           _dowel_options(ctx, provisional, column)) * (provisional.h - ctx.design.cover) / 1000 * price
                       for column in columns)
    best: tuple[float, dict[str, Any]] | None = None
    for bottom in bottoms:
        typology = Typology(provisional.fc, provisional.lx, provisional.ly, provisional.h, bottom, None)
        steel = len(columns) * _mat_mass(ctx, typology, bottom) * price
        if best is not None and steel + dowels_floor >= best[0]:
            break
        failures, dowels = _verify(ctx, typology, columns)
        own = [failure for failure in failures if not _top_related(failure)]
        if not own:
            cost = priced(ctx, typology, columns, dowels).cost - _concrete_cost(ctx, typology, columns)
            best = (cost, bottom) if best is None or cost < best[0] else best
        elif best is None and not all(failure.name.startswith(_MAT_PREFIXES) for failure in own):
            return None  # falla algo que depende del espesor
    return None if best is None else best[1]


def _jointly(
    ctx: Context, columns: Sequence[DesignColumn], provisional: Typology, bottoms: list[dict[str, Any]],
    tops: list[dict[str, Any] | None],
) -> GroupDesign | str:
    """Respaldo si las mallas no resultaran separables: todas las combinaciones, la de menor costo que pasa."""
    best: GroupDesign | None = None
    for bottom in bottoms:
        for top in tops:
            typology = Typology(provisional.fc, provisional.lx, provisional.ly, provisional.h, bottom, top)
            failures, dowels = _verify(ctx, typology, columns)
            if not failures:
                result = priced(ctx, typology, columns, dowels)
                best = result if best is None or result.cost < best.cost else best
    return "h" if best is None else best


def _concrete_cost(ctx: Context, typology: Typology, columns: Sequence[DesignColumn]) -> float:
    design = ctx.design
    volume = sum(typology.lx * typology.ly * typology.h + column.cx * column.cy * design.pedestal_height for column in columns)
    return volume / _MM3_PER_M3 * design.prices.concrete(typology.fc)


def _lower_bound(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h: float) -> float:
    """Cota inferior del costo con este espesor (D-076): concreto, la malla inferior mínima (acero mínimo del perfil, las
    longitudes de _mat_mass y la menor masa por área de las barras candidatas), los pasadores mínimos de cada columna (los
    de menor masa entre sus candidatos) y, si la malla superior es obligatoria (momento negativo sin concreto simple
    permitido, D-072), su acero mínimo en las direcciones con momento negativo. Todo lo que se suma está en cualquier
    solución con este espesor, así que la poda no pierde el óptimo; crece con h."""
    design = ctx.design
    lx, ly = plan
    ratio = ctx.profile.footing.min_reinforcement_ratio(ctx.project.materials.fy)
    unit = min(ctx.spec(designation).mass_kg_m / ctx.spec(designation).area_mm2 for designation in design.bars)
    # Barras x: As,min con el ancho ly y largo lx − 2r; barras y: ancho lx y largo ly − 2r (kg por zapata).
    per_direction = {"x": ratio * h * ly * (lx - 2 * design.cover) * unit / 1000,
                     "y": ratio * h * lx * (ly - 2 * design.cover) * unit / 1000}
    steel = len(columns) * sum(per_direction.values())
    bars = {"designation": design.bars[0], "spacing": design.spacing_step * 4}
    provisional = Typology(fc, lx, ly, h, {"first": "x", "end": design.end, "x": bars, "y": bars}, None)
    for column in columns:
        steel += min(option["count"] * ctx.spec(option["designation"]).mass_kg_m
                     for option in _dowel_options(ctx, provisional, column)) * (h - design.cover) / 1000
    if not ctx.profile.plain.permitted_in_foundations(ctx.project.seismic.level):
        negative = _demands(ctx, columns, provisional, -1.0)
        steel += len(columns) * sum(per_direction[direction] for direction, moment in negative.items() if moment > 0)
    return _concrete_cost(ctx, provisional, columns) + steel * design.prices.steel_per_kg


def _heights(ctx: Context, h_start: float) -> list[float]:
    count = int(round((ctx.design.h_max - h_start) / ctx.design.h_step)) + 1
    return [h_start + index * ctx.design.h_step for index in range(max(count, 1))]


def _thinnest(
    ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], heights: list[float]
) -> tuple[GroupDesign | bool, int]:
    """El menor espesor con solución en esta planta, por bisección, y su índice en heights (búsqueda rápida de la tabla de
    tramos). False si la planta no cumple el suelo ni con el espesor inicial y True si no hay solución hasta h_max."""
    first = _at_height(ctx, columns, fc, plan, heights[0])
    if first == "soil":
        return False, 0
    if isinstance(first, GroupDesign):
        return first, 0
    best: GroupDesign | None = None
    lowest = 0
    low, high = 1, len(heights) - 1
    while low <= high:
        middle = (low + high) // 2
        result = _at_height(ctx, columns, fc, plan, heights[middle])
        if isinstance(result, GroupDesign):
            best, lowest, high = result, middle, middle - 1
        elif result == "soil":
            high = middle - 1  # el peso propio ya no cabe: espesores menores
        else:
            low = middle + 1
    return (True, 0) if best is None else (best, lowest)


def _quick_plan(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h_start: float) -> GroupDesign | bool:
    """Sin barrido: el menor espesor con solución (tabla de tramos, D-076)."""
    return _thinnest(ctx, columns, fc, plan, _heights(ctx, h_start))[0]


def _for_plan(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h_start: float) -> GroupDesign | bool:
    """La solución de menor costo en esta planta (D-076): el menor espesor con solución, por bisección, y luego los
    mayores hasta h_max, mientras la cota inferior no alcance el mejor costo (un espesor que no cumple el suelo se salta).
    False si la planta no cumple el suelo ni con el espesor inicial y True si no hay solución hasta h_max."""
    heights = _heights(ctx, h_start)
    best, lowest = _thinnest(ctx, columns, fc, plan, heights)
    if not isinstance(best, GroupDesign):
        return best
    for h in heights[lowest + 1 :]:
        if _lower_bound(ctx, columns, fc, plan, h) >= best.cost:
            break  # la cota crece con h: ningún espesor mayor puede ganar
        result = _at_height(ctx, columns, fc, plan, h)
        if isinstance(result, GroupDesign) and result.cost < best.cost:
            best = result
    return best


def design_group(
    ctx: Context, columns: Sequence[DesignColumn], fc: float, start: Typology | None = None, sweep: bool = True
) -> GroupDesign | None:
    """La tipología más económica entre la menor planta viable y las _EXTRA_PLANS siguientes (D-069), o None si nada
    cumple dentro de los límites. sweep recorre los espesores mayores que el mínimo con solución (D-076); sin él, la
    búsqueda rápida para la tabla de tramos."""
    initial = _initial_size(ctx, columns)
    lower = (start.lx, start.ly) if start is not None else (initial, initial)
    h_start = start.h if start is not None else ctx.design.h_min
    best: GroupDesign | None = None
    extra = None
    search = _for_plan if sweep else _quick_plan
    for plan in _plans(ctx, columns, lower):
        result = search(ctx, columns, fc, plan, h_start)
        if isinstance(result, GroupDesign) and (best is None or result.cost < best.cost):
            best = result
        if best is not None:
            extra = _EXTRA_PLANS if extra is None else extra - 1
            if extra <= 0:
                break
    return best
