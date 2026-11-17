"""Diseño de un cabezal sobre pilotes (D-141).

El diseño no tiene fórmulas propias: propone cabezales y los aprueba con la verificación de D-138
(`domain/pile_cap/checks.pile_cap_checks`). Para proponer las mallas usa los momentos de cara del análisis
(`domain/pile_cap/loads`), el As mínimo del cabezal (`domain/pile_cap/flexure.cap_rules`) y las barras de
`design/bars`; los pasadores, los de la zapata (`design/footing/typology.dowel_choices`).

Orden de la búsqueda, por cabezal:
- con las cargas de la columna, el número de pilotes desde la cota de la capacidad del grupo (servicio, sin pesos) y, para
  cada número, los arreglos de design/pile_cap/patterns, de menor a mayor área; se para cuando el costo de los pilotes más
  el concreto mínimo ya no puede ganar. Con las de los pilotes, el arreglo declarado (coordenadas desde el eje de la
  columna) con el rectángulo que lo encierra más E;
- para cada arreglo y f'c, los espesores desde h_min: uno que no cumple lo geotécnico termina el arreglo (más espesor pesa
  más); uno al que le falta cortante sigue con el siguiente; tras el primero con solución, los mayores mientras la cota
  inferior del costo no alcance el mejor;
- para cada espesor, la malla inferior de menor peso que aprueba lo que no depende de la superior (con sus pasadores) y
  luego la superior más liviana que completa el momento negativo y la retracción (D-140). Sin momento negativo ni falta
  de retracción, no hay malla superior.
El costo es el del concreto, el acero (la cartilla si el proyecto declara detailing, D-127; si no, el estimado) y los
pilotes.
"""

import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import Any

from structurelab_rc.codes.registry import Profile
from structurelab_rc.design.bars import Spread, band_options, bar_options
from structurelab_rc.design.footing.typologies import COST_BASIS, design_outputs, load_input
from structurelab_rc.design.footing.typology import dowel_choices
from structurelab_rc.design.pile_cap.patterns import Arrangement, arrangements, declared
from structurelab_rc.detailing.schedule import schedule
from structurelab_rc.domain.basis import Basis
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.footing.connection import Support
from structurelab_rc.domain.footing.detailing import footing_runs, moment_envelope
from structurelab_rc.domain.footing.flexure import PLAIN
from structurelab_rc.domain.footing.mesh import mat_rows
from structurelab_rc.domain.pile_cap.checks import EDGE, EMBEDMENT, MISLOCATION, cap_analysis, pile_cap_checks
from structurelab_rc.domain.pile_cap.flexure import SHRINKAGE, cap_rules
from structurelab_rc.domain.pile_cap.outline import bar_span
from structurelab_rc.domain.pile_cap.service import ECCENTRICITY, GROUP, PILE_COMPRESSION, PILE_LATERAL, PILE_TENSION, UNRESISTED
from structurelab_rc.domain.status import Status
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.footing import N_MM3_PER_KN_M3, N_PER_KN, Mat
from structurelab_rc.model.layout import public
from structurelab_rc.model.pile_cap import PileCap, PileCapSoil
from structurelab_rc.model.pile_cap_design import DesignCap, PileCapDesign, PileCapDesignProject
from structurelab_rc.model.project import Materials

_GEOTECHNICAL = (PILE_COMPRESSION, PILE_TENSION, PILE_LATERAL, GROUP, ECCENTRICITY, UNRESISTED)
_DECLARED = (EMBEDMENT, EDGE, MISLOCATION)  # dependen solo de datos declarados: el diseño no los puede cambiar
_MAT_PREFIXES = ("Flexion malla", "Deformacion neta de traccion malla", "Acero minimo malla", "Separacion maxima malla",
                 "Separacion minima", "Franja central", "Fuera de la franja central", "Desarrollo malla", SHRINKAGE, PLAIN)
_DOWEL_PREFIXES = ("Pasadores", "Aplastamiento")
_MAT_TRIES = 12
_MM3_PER_M3 = 1e9
_MAX_ASPECT = 2.5  # arreglos más alargados no se prueban (salvo los de dos y tres pilotes)
Mats = tuple[dict[str, Any], dict[str, Any] | None]  # mallas inferior y superior en el formato de entrada


@dataclass(frozen=True)
class Context:
    """Lo que no cambia durante el diseño."""

    project: PileCapDesignProject
    profile: Profile
    bars: Sequence[RebarSpec]

    @property
    def design(self) -> PileCapDesign:
        return self.project.pile_cap_design

    def basis(self, fc: float) -> Basis:
        m = self.project.materials
        materials = Materials(fc=fc, fy=m.fy, fyt=m.fyt, concrete=m.concrete, coating=m.coating, max_aggregate=m.max_aggregate)
        return Basis(self.profile, materials, self.bars, self.project.seismic.level)

    def spec(self, designation: str) -> RebarSpec:
        return next(bar for bar in self.bars if bar.designation == designation)


@dataclass(frozen=True)
class CapSolution:
    """Un cabezal aprobado: f'c, arreglo, espesor, mallas y pasadores en el formato de entrada (data, el del proyecto de
    verificación), con su costo, el volumen de concreto (m³), el peso de acero (kg) y el costo de los pilotes."""

    fc: float
    arrangement: Arrangement
    h: float
    data: dict[str, Any]
    cost: float
    concrete: float
    steel: float
    piles: float


@dataclass(frozen=True)
class Trial:
    """Un arreglo probado con un f'c: su mejor solución o por qué no tiene."""

    arrangement: Arrangement
    fc: float
    solution: CapSolution | None
    failure: str


@dataclass(frozen=True)
class CapDesign:
    """El diseño de un cabezal: la solución de menor costo (None si ninguna cumple), los arreglos probados y el motivo
    si no hay solución."""

    cap: DesignCap
    best: CapSolution | None
    trials: tuple[Trial, ...]
    failure: str = ""


@dataclass(frozen=True)
class _Candidate:
    """Lo que fija un cabezal durante la búsqueda de sus mallas."""

    cap: DesignCap
    arrangement: Arrangement
    fc: float
    h: float


def _pile_entries(cap: DesignCap, arrangement: Arrangement) -> list[dict[str, Any]]:
    if cap.loads_from == "piles":
        return [{"id": pile.id, "x": x, "y": y, "loads": [load_input(load) for load in pile.loads]}
                for pile, (x, y) in zip(cap.piles, arrangement.piles, strict=True)]
    return [{"id": f"P{index}", "x": x, "y": y} for index, (x, y) in enumerate(arrangement.piles, start=1)]


def cap_data(ctx: Context, candidate: _Candidate, mats: Mats, dowels: dict[str, Any] | None) -> dict[str, Any]:
    """El cabezal en el formato de entrada del proyecto de verificación (D-138)."""
    design, cap, arrangement = ctx.design, candidate.cap, candidate.arrangement
    bottom, top = mats
    column = {"id": "C1", "cx": cap.column.cx, "cy": cap.column.cy, "offset_x": arrangement.column[0],
              "offset_y": arrangement.column[1], "dowels": dowels}
    data: dict[str, Any] = {
        "id": cap.id, "loads_from": cap.loads_from, "lx": arrangement.lx, "ly": arrangement.ly, "h": candidate.h,
        "cover": design.cover, "bottom_cover": design.bottom_cover, "fill_height": design.fill_height,
        "pedestal_height": design.pedestal_height, "surcharge_dead_kNm2": design.surcharge_dead,
        "surcharge_live_kNm2": design.surcharge_live, "columns": [column], "bottom": bottom, "top": top,
        "pile": design.pile.model_dump(), "mislocation_mm": design.mislocation, "piles": _pile_entries(cap, arrangement),
    }
    if cap.loads_from == "piles":
        data["reactions_include_weight"] = cap.reactions_include_weight
    else:
        column["loads"] = [load_input(load) for load in cap.loads]
    if arrangement.clips:
        data["clipped_corners"] = [clip.model_dump() for clip in arrangement.clips]
    if cap.location is not None:  # D-130: la planta de localización, con el cabezal como su tipo
        data |= {"typology": cap.id, "location": cap.location.model_dump()}
    return data


def _build(ctx: Context, candidate: _Candidate, mats: Mats, dowels: dict[str, Any] | None) -> PileCap:
    return PileCap.model_validate(cap_data(ctx, candidate, mats, dowels))


def _failures(checks: list[Check]) -> list[Check]:
    return [check for check in checks if check.status is not Status.PASS]


def _starts(check: Check, prefixes: tuple[str, ...]) -> bool:
    return check.name.startswith(prefixes)


def _top_related(check: Check) -> bool:
    """Lo que depende de la malla superior: sus verificaciones y la retracción (las dos mallas sumadas, D-140)."""
    return "malla superior" in check.name or _starts(check, (SHRINKAGE, PLAIN))


def _provisional(ctx: Context) -> dict[str, Any]:
    bars = {"designation": ctx.design.bars[0], "spacing": ctx.design.spacing_step * 4, "end": ctx.design.ends.bottom}
    return {"first": "x", "x": bars, "y": bars}


def _mat_candidates(ctx: Context, given: tuple[PileCap, Basis], needs: dict[str, tuple[float, float]], top: bool) -> list[dict[str, Any]]:
    """Mallas de menor a mayor peso para (Mu, As requerido) de cada dirección; la de mayor momento va más cerca de la
    cara. Las barras se reparten en todo el ancho del rectángulo; la verificación decide."""
    cap, basis = given
    design = ctx.design
    face = design.cover if top else design.bottom_cover
    max_spacing = math.floor(ctx.profile.footing.max_bar_spacing(cap.h) / design.spacing_step) * design.spacing_step
    specs = [ctx.spec(designation) for designation in design.bars]
    widths, lengths = {"x": cap.ly, "y": cap.lx}, {"x": cap.lx, "y": cap.ly}
    first = "x" if needs["x"][0] >= needs["y"][0] else "y"
    second = "y" if first == "x" else "x"
    end = design.ends.top if top else design.ends.bottom

    def options(direction: str, depth_of: Callable[[float], float]) -> list[tuple[float, dict[str, Any]]]:
        spread = Spread(widths[direction], cap.h, design.cover, design.spacing_step, max_spacing)
        given = (ctx.profile, basis.materials, specs)
        if direction == cap.short_direction:  # franja central de la dirección corta (decisión del usuario, D-138)
            short = min(cap.lx, cap.ly)
            gamma = ctx.profile.footing.band_fraction(max(cap.lx, cap.ly) / short)
            return band_options(given, spread, depth_of, needs[direction], (short, gamma))[:_MAT_TRIES]
        return bar_options(given, spread, depth_of, needs[direction], _MAT_TRIES * len(specs))[:_MAT_TRIES]

    def depth(below: float) -> Callable[[float], float]:
        return lambda db: cap.h - face - below - db / 2

    combos = []
    for weight_a, set_a in options(first, depth(0.0)):
        for weight_b, set_b in options(second, depth(ctx.spec(set_a["designation"]).diameter_mm)):
            total = weight_a * lengths[first] + weight_b * lengths[second]
            combos.append((total, {"first": first, first: {**set_a, "end": end}, second: {**set_b, "end": end}}))
    return [mat for _, mat in sorted(combos, key=lambda combo: combo[0])[: _MAT_TRIES * 2]]


def _needs(basis: Basis, cap: PileCap, demands: dict[str, float], mat: str, floor: dict[str, float]) -> dict[str, tuple[float, float]]:
    """(Mu, As requerido) por dirección con el As mínimo del cabezal (cap_rules) y un piso (la retracción que falta)."""
    rules = cap_rules(basis, cap)
    rows = mat_rows(cap, cap.bottom, basis.bars)
    needs = {}
    for direction, row in rows.items():
        demand = max(demands[direction], 0.0)
        # La malla inferior lleva su mínimo aunque no haya momento positivo; la superior, solo con momento negativo.
        required = rules.minimum(mat, row, demand)[0] if demand > 0 or mat == "bottom" else 0.0
        needs[direction] = (demand, max(required, floor.get(direction, 0.0)))
    return needs


def _verify(ctx: Context, candidate: _Candidate, mats: Mats,
            loads: list[float]) -> tuple[list[Check], dict[str, Any], PileCap]:
    """Fallas del cabezal con sus mallas y los pasadores de menor área que aprueban los suyos (si ninguno, los de menor
    área), con el cabezal en el formato de entrada y ya construido."""
    basis = ctx.basis(candidate.fc)
    first: tuple[list[Check], dict[str, Any], PileCap] | None = None
    provisional = _build(ctx, candidate, mats, None)
    column = provisional.columns[0]
    support = Support(column.cx, column.cy, column.offset_x, column.offset_y, None, "")
    for dowels in dowel_choices(basis, provisional, support, loads, (ctx.design.dowel_bars, ctx.design.ends.dowels)):
        data = cap_data(ctx, candidate, mats, dowels)
        cap = PileCap.model_validate(data)
        failures = _failures(pile_cap_checks(basis, cap, ctx.project.soil))
        if not any(_starts(failure, _DOWEL_PREFIXES) for failure in failures):
            return failures, data, cap
        first = first or (failures, data, cap)
    assert first is not None
    return first


def _mat_mass(ctx: Context, cap: PileCap, mat: Mat | None) -> float:
    """Peso estimado de una malla (kg): barras rectas de borde a borde del contorno menos el recubrimiento."""
    if mat is None:
        return 0.0
    mass = 0.0
    for direction, row in mat_rows(cap, mat, ctx.bars).items():
        unit = ctx.spec(row.designation).mass_kg_m / 1000
        for position in row.positions:
            span = bar_span(cap, direction, position)
            mass += 0.0 if span is None else (span[1] - span[0]) * unit
    return mass


def _dowel_mass(ctx: Context, cap: PileCap) -> float:
    return sum(dowels.count * ctx.spec(dowels.designation).mass_kg_m * (cap.h - ctx.design.cover) / 1000
               for column in cap.columns if (dowels := column.dowels) is not None)


def _concrete(ctx: Context, cap: PileCap) -> float:
    """Volumen del cabezal y el pedestal, en m³."""
    return (cap.area * cap.h + cap.column_area * ctx.design.pedestal_height) / _MM3_PER_M3


def _spans(cap: PileCap) -> Callable[[str, float], tuple[float, float] | None] | None:
    """El tramo de cada barra en un cabezal con esquinas recortadas (D-141), como en el despiece del motor."""
    if not cap.clipped_corners:
        return None
    return lambda direction, position: bar_span(cap, direction, position)


def priced(ctx: Context, candidate: _Candidate, data: dict[str, Any]) -> CapSolution:
    """La solución aprobada (data, en el formato de entrada) con su costo: el acero de la cartilla si el proyecto declara
    detailing; si no, el estimado (D-127)."""
    design, detailing = ctx.design, ctx.project.detailing
    cap = PileCap.model_validate(data)
    if detailing is not None:
        basis = ctx.basis(candidate.fc)
        analysis = cap_analysis(basis, cap, ctx.project.soil)
        runs = footing_runs(basis, cap, moment_envelope(list(analysis.moments)), _spans(cap))
        steel = sum(row.mass for row in schedule(cap.id, runs, detailing.stock_length))
    else:
        steel = _mat_mass(ctx, cap, cap.bottom) + _mat_mass(ctx, cap, cap.top) + _dowel_mass(ctx, cap)
    concrete = _concrete(ctx, cap)
    piles = len(cap.piles) * design.prices.pile_each
    cost = concrete * design.prices.concrete(candidate.fc) + steel * design.prices.steel_per_kg + piles
    return CapSolution(candidate.fc, candidate.arrangement, candidate.h, data, cost, concrete, steel, piles)


def _at_height(ctx: Context, candidate: _Candidate) -> CapSolution | str:
    """Solución de menor peso de acero con este espesor; "soil" si no cumple lo geotécnico, "declared" si falla un dato
    declarado y "h" si falta espesor."""
    basis = ctx.basis(candidate.fc)
    provisional = _build(ctx, candidate, (_provisional(ctx), None), None)
    analysis = cap_analysis(basis, provisional, ctx.project.soil)
    first = _failures(pile_cap_checks(basis, provisional, ctx.project.soil, analysis))
    if any(_starts(check, _DECLARED) for check in first):
        return "declared"
    if any(_starts(check, _GEOTECHNICAL) for check in first):
        return "soil"
    envelope = moment_envelope(list(analysis.moments)) or {"x": (0.0, 0.0), "y": (0.0, 0.0)}
    loads = [pu for item in analysis.factored if (pu := item.case.bearing[0]) is not None]
    positive = {direction: values[0] for direction, values in envelope.items()}
    negative = {direction: values[1] for direction, values in envelope.items()}
    bottoms = _mat_candidates(ctx, (provisional, basis), _needs(basis, provisional, positive, "bottom", {}), top=False)
    chosen: tuple[list[Check], dict[str, Any], PileCap] | None = None
    for bottom in bottoms:
        failures, data, cap = _verify(ctx, candidate, (bottom, None), loads)
        own = [failure for failure in failures if not _top_related(failure)]
        if not own:
            chosen = failures, data, cap
            break
        if not all(_starts(failure, (*_MAT_PREFIXES, *_DOWEL_PREFIXES)) for failure in own):
            return "h"  # falla algo que depende del espesor
    if chosen is None:
        return "h"
    return _with_top(ctx, candidate, chosen, (negative, loads))


def _with_top(ctx: Context, candidate: _Candidate, chosen: tuple[list[Check], dict[str, Any], PileCap],
              given: tuple[dict[str, float], list[float]]) -> CapSolution | str:
    """Con la malla inferior elegida, la superior más liviana que completa el momento negativo y la retracción (D-140);
    ninguna si ya cumple todo."""
    failures, data, cap = chosen
    if not failures:
        return priced(ctx, candidate, data)
    negative, loads = given
    basis = ctx.basis(candidate.fc)
    ratio = ctx.profile.footing.shrinkage_temperature_ratio(basis.materials.fy)
    rows = mat_rows(cap, cap.bottom, ctx.bars)
    floor = {direction: max(ratio * row.width * cap.h - row.area, 0.0) for direction, row in rows.items()}
    for top in _mat_candidates(ctx, (cap, basis), _needs(basis, cap, negative, "top", floor), top=True):
        failures, data, _ = _verify(ctx, candidate, (data["bottom"], top), loads)
        if not failures:
            return priced(ctx, candidate, data)
        if not all(_top_related(failure) for failure in failures):
            return "h"
    return "h"


def _heights(design: PileCapDesign) -> list[float]:
    count = int(round((design.h_max - design.h_min) / design.h_step)) + 1
    return [design.h_min + index * design.h_step for index in range(max(count, 1))]


def _steel_floor(ctx: Context, arrangement: Arrangement, h: float) -> float:
    """Cota inferior del acero (kg) de un cabezal rectangular: la retracción ρt·b·h en cada dirección (D-140), con la
    menor masa por área de las barras candidatas; 0 con esquinas recortadas."""
    if arrangement.clips:
        return 0.0
    ratio = ctx.profile.footing.shrinkage_temperature_ratio(ctx.project.materials.fy)
    unit = min(ctx.spec(designation).mass_kg_m / ctx.spec(designation).area_mm2 for designation in ctx.design.bars)
    cover = ctx.design.cover
    lx, ly = arrangement.lx, arrangement.ly
    return ratio * h * (ly * (lx - 2 * cover) + lx * (ly - 2 * cover)) * unit / 1000


def _lower_bound(ctx: Context, arrangement: Arrangement, fc: float, h: float) -> float:
    """Cota inferior del costo con este arreglo y espesor: pilotes, concreto (el rectángulo menos los recortes) y la
    retracción mínima; crece con h, así que la poda no pierde el óptimo."""
    design = ctx.design
    area = arrangement.lx * arrangement.ly - sum(clip.along_x * clip.along_y / 2 for clip in arrangement.clips)
    concrete = area * h / _MM3_PER_M3
    return (len(arrangement.piles) * design.prices.pile_each + concrete * design.prices.concrete(fc)
            + _steel_floor(ctx, arrangement, h) * design.prices.steel_per_kg)


_REASONS = {"soil": "no cumple lo geotecnico (capacidad de los pilotes o del grupo, excentricidad)",
            "h": "sin solucion hasta h_max",
            "h_soil": "falta espesor y, con mas espesor, el peso ya no cumple lo geotecnico",
            "declared": "falla un dato declarado (empotramiento, borde o tolerancia)",
            "geometry": "la columna no cabe en el contorno"}


def _for_arrangement(ctx: Context, cap: DesignCap, arrangement: Arrangement, fc: float, bound: float) -> Trial:
    """La solución de menor costo con este arreglo y f'c (bound: el mejor costo ya hallado, para podar)."""
    best: CapSolution | None = None
    failure = "h"
    for h in _heights(ctx.design):
        limit = min(bound, best.cost if best is not None else math.inf)
        if _lower_bound(ctx, arrangement, fc, h) >= limit:
            failure = failure if best is not None else "pruned"
            break
        try:
            result = _at_height(ctx, _Candidate(cap, arrangement, fc, h))
        except ValueError:
            failure = "geometry"
            break
        if isinstance(result, CapSolution):
            if best is None or result.cost < best.cost:
                best = result
            continue
        if best is not None:
            continue
        if result == "soil" and failure == "h" and h > ctx.design.h_min:
            failure = "h_soil"  # los espesores menores no alcanzaron y con más ya no cumple lo geotécnico
            break
        failure = result
        if result in ("soil", "declared"):
            break
    reason = "" if best is not None else ("mas costoso que la mejor solucion" if failure == "pruned" else _REASONS[failure])
    return Trial(arrangement, fc, best, reason)


def _start_count(ctx: Context, cap: DesignCap) -> int:
    """Cota inferior del número de pilotes: la mayor carga de servicio sobre la capacidad del grupo por pilote (con el
    aumento sísmico y la eficiencia), sin pesos."""
    soil = ctx.project.soil
    count = max((load.p / (soil.group_efficiency * soil.factor(load.seismic) * soil.pile_capacity_compression)
                 for load in cap.loads if load.kind == "service"), default=0.0)
    return max(2, math.ceil(count - 1e-9))


def candidates(ctx: Context, count: int) -> list[Arrangement]:
    """Arreglos de count pilotes y sus giros de 90°, de menor a mayor área, sin los muy alargados."""
    design = ctx.design
    found = []
    for item in arrangements(count, design.pile_spacing, design.edge_distance):
        found.append(item)
        if not item.clips and item.lx != item.ly:
            found.append(replace(item, name=f"{item.name} (girado)", piles=tuple((y, x) for x, y in item.piles), lx=item.ly,
                                 ly=item.lx, column=(item.column[1], item.column[0])))
    slender = [item for item in found if count > 3 and max(item.lx, item.ly) / min(item.lx, item.ly) > _MAX_ASPECT]  # noqa: PLR2004
    return sorted((item for item in found if item not in slender), key=lambda item: (item.lx * item.ly, item.name))


def _arrangement_groups(ctx: Context, cap: DesignCap) -> Iterator[list[Arrangement]]:
    if cap.loads_from == "piles":
        yield [declared(cap.piles, ctx.design.edge_distance, cap.clipped_corners)]
        return
    for count in range(_start_count(ctx, cap), ctx.design.max_piles + 1):
        yield candidates(ctx, count)


def design_cap(ctx: Context, cap: DesignCap, fc: float) -> CapDesign:
    """El cabezal de menor costo con este f'c, los arreglos y los espesores permitidos."""
    design = ctx.design
    best: CapSolution | None = None
    trials: list[Trial] = []
    for group in _arrangement_groups(ctx, cap):
        if best is not None and group and min(_lower_bound(ctx, item, fc, design.h_min) for item in group) >= best.cost:
            break  # más pilotes ya no pueden ganar
        for arrangement in group:
            trial = _for_arrangement(ctx, cap, arrangement, fc, best.cost if best is not None else math.inf)
            trials.append(trial)
            if trial.solution is not None and (best is None or trial.solution.cost < best.cost):
                best = trial.solution
    failure = "" if best is not None else (f"Sin solucion para el cabezal '{cap.id}' con f'c = {fc:g} MPa dentro de los limites "
                                           f"(hasta {design.max_piles} pilotes)")
    return CapDesign(cap, best, tuple(trials), failure)


@dataclass(frozen=True)
class DesignResult:
    """Los cabezales de cada f'c y el f'c elegido: el de menor costo total con solución para todos (un proyecto declara un
    solo concreto); None si ningún f'c resuelve todos."""

    options: tuple[tuple[float, tuple[CapDesign, ...]], ...]
    fc: float | None

    @property
    def caps(self) -> tuple[CapDesign, ...]:
        return next(designs for fc, designs in self.options if fc == self.fc)

    @property
    def cost(self) -> float:
        return sum(design.best.cost for design in self.caps if design.best is not None)


def design_caps(ctx: Context) -> DesignResult:
    """Todos los cabezales con cada f'c; gana el de menor costo total."""
    options = tuple((fc, tuple(design_cap(ctx, cap, fc) for cap in ctx.project.caps)) for fc in ctx.design.fc_options)
    feasible = [(sum(design.best.cost for design in designs if design.best is not None), fc) for fc, designs in options
                if all(design.best is not None for design in designs)]
    return DesignResult(options, min(feasible)[1] if feasible else None)


def soil_input(soil: PileCapSoil) -> dict[str, Any]:
    """El suelo de los cabezales en el formato de entrada (D-139; el peso del concreto pasa a concrete con public)."""
    optional = {name: value / N_PER_KN for name, value in (("pile_capacity_tension_kN", soil.pile_capacity_tension),
                                                           ("pile_capacity_lateral_kN", soil.pile_capacity_lateral))
                if value is not None}
    return {"unit_weight_concrete_kNm3": soil.unit_weight_concrete / N_MM3_PER_KN_M3,
            "unit_weight_fill_kNm3": soil.unit_weight_fill / N_MM3_PER_KN_M3,
            "pile_capacity_compression_kN": soil.pile_capacity_compression / N_PER_KN, **optional,
            "seismic_capacity_factor": soil.seismic_capacity_factor, "group_efficiency": soil.group_efficiency,
            "max_eccentricity_mm": soil.max_eccentricity}


def designed_project(ctx: Context, result: DesignResult) -> dict[str, Any]:
    """Proyecto de verificación (formato de entrada) con los cabezales diseñados con el f'c elegido."""
    project = ctx.project
    materials = project.materials
    assert result.fc is not None
    fc, cost = result.fc, result.cost
    solutions = [design.best for design in result.caps if design.best is not None]
    return public({
        "description": f"{project.description} Diseño de cabezales (D-141): {len(solutions)} cabezales, f'c = {fc:g} MPa, costo total "
                       f"{cost:.2f} (concreto, acero y pilotes; acero: {COST_BASIS[project.detailing is not None]}, D-127).",
        "profile": project.profile,
        "seismic": project.seismic.model_dump(),
        "materials": {"fc": fc, "fy": materials.fy, "fyt": materials.fyt, "concrete": materials.concrete, "coating": materials.coating,
                      **({} if materials.max_aggregate is None else {"max_aggregate": materials.max_aggregate})},
        "soil": soil_input(project.soil),
        "pile_caps": [solution.data for solution in solutions],
        **design_outputs(project.detailing, project.drawing),
    })


def summary(result: DesignResult) -> dict[str, Any]:
    """El f'c elegido y, por f'c, los arreglos probados de cada cabezal (resumen.json): su mejor solución o por qué no
    tiene."""
    return {"fc [MPa]": result.fc, "cost": None if result.fc is None else round(result.cost, 2),
            "options": [{"fc [MPa]": fc, "caps": _caps_summary(designs)} for fc, designs in result.options]}


def _caps_summary(designs: Sequence[CapDesign]) -> list[dict[str, Any]]:
    caps = []
    for design in designs:
        trials = []
        for trial in design.trials:
            item = trial.arrangement
            entry: dict[str, Any] = {"arrangement": item.name, "piles": len(item.piles), "lx [mm]": item.lx, "ly [mm]": item.ly}
            solution = trial.solution
            if solution is None:
                entry["failure"] = trial.failure
            else:
                entry |= {"h [mm]": solution.h, "concrete [m3]": round(solution.concrete, 3), "steel [kg]": round(solution.steel, 1),
                          "piles cost": round(solution.piles, 2), "cost": round(solution.cost, 2)}
            trials.append(entry)
        best = design.best
        chosen = None if best is None else {"arrangement": best.arrangement.name, "piles": len(best.arrangement.piles),
                                            "h [mm]": best.h, "cost": round(best.cost, 2)}
        caps.append({"id": design.cap.id, "loads_from": design.cap.loads_from, "best": chosen, "failure": design.failure or None,
                     "trials": trials})
    return caps
