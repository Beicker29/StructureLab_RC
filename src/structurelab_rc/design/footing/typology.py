"""Diseño de una tipología de zapata para un grupo de columnas (V3F, D-069).

El diseño no tiene fórmulas propias: propone zapatas y las aprueba con la misma verificación de V3C y V3D
(`domain/footing/checks.footing_checks`). Para proponer barras usa los momentos de `domain/footing/flexure` y el As
requerido de `domain/flexure_strength`; para los pasadores, el aplastamiento de `codes` y A2 de `domain/footing`.

Orden de la búsqueda: planta (crece si fallan la presión o el contacto), espesor (crece si fallan el cortante, el
punzonamiento, la altura, el anclaje de los pasadores o el aplastamiento) y, para cada espesor, las mallas de menor peso
que aprueban la flexión, los mínimos, la separación, la franja y el desarrollo. Una tipología fija la zapata
(dimensiones, mallas y f'c); cada columna del grupo se verifica con su propia sección, sus cargas y sus pasadores.
"""

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
from structurelab_rc.domain.footing.flexure import face_moments
from structurelab_rc.domain.footing.loads import factored_cases
from structurelab_rc.domain.footing.service import service_checks
from structurelab_rc.domain.status import Status
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.design import DesignColumn, FootingDesign, FootingDesignProject
from structurelab_rc.model.footing import Footing, Soil
from structurelab_rc.model.project import Materials

_MAT_PREFIXES = ("Flexion malla", "Deformacion neta de traccion malla", "Acero minimo malla", "Separacion maxima malla",
                 "Franja central", "Desarrollo malla")
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
    """Cota inferior de la planta: la carga de servicio mayor sobre la presión admisible (sin pesos ni momentos)."""
    largest = max((load.p for column in columns for load in column.loads if load.kind == "service"), default=0.0)
    side = math.sqrt(max(largest, 0.0) / ctx.soil.allowable_pressure)
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


def _cost(
    ctx: Context, typology: Typology, columns: Sequence[DesignColumn], dowels: dict[str, dict[str, Any]]
) -> tuple[float, float, float]:
    """Costo, volumen de concreto (m³) y peso de acero (kg) del grupo: mallas rectas de borde a borde menos el
    recubrimiento y pasadores hasta la malla inferior."""
    design = ctx.design
    concrete = steel = 0.0
    for column in columns:
        concrete += (typology.lx * typology.ly * typology.h + column.cx * column.cy * design.pedestal_height) / _MM3_PER_M3
        steel += _mat_mass(ctx, typology, typology.bottom) + (0.0 if typology.top is None else _mat_mass(ctx, typology, typology.top))
        spec = ctx.spec(dowels[column.id]["designation"])
        steel += dowels[column.id]["count"] * spec.mass_kg_m * (typology.h - design.cover) / 1000
    price = ctx.design.prices
    return concrete * price.concrete(typology.fc) + steel * price.steel_per_kg, concrete, steel


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


def _at_height(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h: float) -> GroupDesign | str:
    """Solución de menor peso de mallas con este espesor; "soil" si la planta no cumple el suelo, "h" si falta espesor."""
    design = ctx.design
    any_bars = {"designation": design.bars[0], "spacing": design.spacing_step * 4}
    provisional = Typology(fc, plan[0], plan[1], h, {"first": "x", "end": design.end, "x": any_bars, "y": any_bars}, None)
    if not _soil_ok(ctx, columns, provisional):
        return "soil"
    positive = _demands(ctx, columns, provisional, 1.0)
    negative = _demands(ctx, columns, provisional, -1.0)
    for bottom in _mat_candidates(ctx, provisional, positive):
        top = next(_mat_candidates(ctx, provisional, negative), None) if max(negative.values()) > 0 else None
        typology = Typology(fc, plan[0], plan[1], h, bottom, top)
        failures, dowels = _verify(ctx, typology, columns)
        if not failures:
            return priced(ctx, typology, columns, dowels)
        if not all(failure.name.startswith(_MAT_PREFIXES) for failure in failures):
            return "h"  # falla algo que depende del espesor
    return "h"


def _for_plan(ctx: Context, columns: Sequence[DesignColumn], fc: float, plan: tuple[float, float], h_start: float) -> GroupDesign | bool:
    """La solución del menor espesor con solución en esta planta, buscado por bisección; False si la planta no cumple el
    suelo ni con el espesor inicial y True si no hay solución hasta h_max."""
    design = ctx.design
    count = int(round((design.h_max - h_start) / design.h_step)) + 1
    heights = [h_start + index * design.h_step for index in range(max(count, 1))]
    first = _at_height(ctx, columns, fc, plan, heights[0])
    if first == "soil":
        return False
    if isinstance(first, GroupDesign):
        return first
    best: GroupDesign | None = None
    low, high = 1, len(heights) - 1
    while low <= high:
        middle = (low + high) // 2
        result = _at_height(ctx, columns, fc, plan, heights[middle])
        if isinstance(result, GroupDesign):
            best, high = result, middle - 1
        elif result == "soil":
            high = middle - 1  # el peso propio ya no cabe: espesores menores
        else:
            low = middle + 1
    return True if best is None else best


def design_group(ctx: Context, columns: Sequence[DesignColumn], fc: float, start: Typology | None = None) -> GroupDesign | None:
    """La tipología más económica entre la menor planta viable y las _EXTRA_PLANS siguientes (D-069), o None si nada
    cumple dentro de los límites."""
    initial = _initial_size(ctx, columns)
    lower = (start.lx, start.ly) if start is not None else (initial, initial)
    h_start = start.h if start is not None else ctx.design.h_min
    best: GroupDesign | None = None
    extra = None
    for plan in _plans(ctx, columns, lower):
        result = _for_plan(ctx, columns, fc, plan, h_start)
        if isinstance(result, GroupDesign) and (best is None or result.cost < best.cost):
            best = result
        if best is not None:
            extra = _EXTRA_PLANS if extra is None else extra - 1
            if extra <= 0:
                break
    return best
