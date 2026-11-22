"""Diseño por tipologías con zapatas combinadas (D-153, enfoque 2 de D-109): los pares de columnas declarados en la
plantilla van en zapatas combinadas, diseñadas con el diseño de la combinada (D-107, D-110, D-113), y el resto por
tipologías aisladas (D-069). Un solo f'c para toda la cimentación: las combinadas se diseñan en todos los f'c y el
diseño por tipologías elige el f'c de menor costo total (aisladas más combinadas). No hay fórmulas nuevas: solo orquesta.

Tipologías de combinadas (D-157), con design.combined_typologies = N (sin él, una combinada por par, D-153):

- Familias: solo comparten tipo los pares que se construyen con el mismo plano: la misma dirección principal, la misma
  separación entre columnas (a 1 mm, en orden a lo largo de la dirección principal), las mismas secciones y linderos en
  ese orden y el mismo combined_design (forma y lo propio del par). Sin volteo.
- Diseño de un grupo: una sola combinada con los casos de carga de todos sus pares (cada caso marcado con su par), así
  que el tipo cumple con cualquiera de ellos. La base se busca en una rejilla, cada plan_step en las dos direcciones,
  entre la menor y la mayor de las resultantes de placement_case de los pares (corrida por los linderos), y gana la más
  barata. Un grupo de un solo par es su diseño individual (D-153).
- Agrupación: en cada familia, los pares en orden de su costo individual se parten en grupos seguidos (programación
  dinámica); los N tipos se reparten entre las familias para el menor costo total (cada par construye una zapata de su
  tipo). Hay error, antes de diseñar, si hay más familias que N.
- Rendimiento: cada búsqueda (un par en un f'c; un grupo en un f'c y una posición de la base) es independiente; las de
  cada etapa se reparten entre los procesos de workers sin cambiar el resultado.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from structurelab_rc.design.footing import combined
from structurelab_rc.design.footing.typologies import COST_BASIS, DesignResult, FcOption, design_typologies, designed_project
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.model.design import CombinedDesignProject, DesignPair, pair_project

_TYPE_PREFIX = "ZCT"


@dataclass(frozen=True)
class PairDesign:
    """Una zapata combinada del diseño por tipologías: su par, el contexto y el resultado de su diseño individual en cada
    f'c, y la solución en el f'c elegido para toda la cimentación (la de su tipo, D-157; None hasta elegirla o si no la
    hay) con el nombre de su tipo."""

    pair: DesignPair
    ctx: combined.Context
    result: combined.CombinedDesignResult
    solution: combined.CombinedSolution | None = None
    typology: str | None = None

    def at(self, fc: float) -> combined.CombinedSolution | None:
        return next((option.solution for option in self.result.options if option.fc == fc), None)


@dataclass(frozen=True)
class Group:
    """Un tipo de combinadas en un f'c: sus pares y su solución, diseñada con las columnas de source (D-157)."""

    pairs: tuple[PairDesign, ...]
    solution: combined.CombinedSolution
    source: combined.Context


@dataclass(frozen=True)
class Grouping:
    """La agrupación de las combinadas en un f'c: sus tipos y el costo total (cada par construye una zapata de su tipo)."""

    groups: tuple[Group, ...]
    cost: float


def pair_contexts(ctx: Context) -> list[combined.Context]:
    """El contexto del diseño de la combinada de cada par (D-153)."""
    return [combined.Context(pair_project(ctx.project, pair), ctx.profile, ctx.bars) for pair in ctx.project.combined_footings]


def design_pairs(ctx: Context, workers: int = 1) -> tuple[PairDesign, ...]:
    """Cada par diseñado con el diseño de la combinada, en todos los f'c (D-153); workers reparte entre procesos todas
    las búsquedas (par y f'c), sin cambiar el resultado."""
    owns = pair_contexts(ctx)
    fcs = ctx.design.fc_options
    options = combined.design_tasks([(own.project, tuple(own.bars), fc, None) for own in owns for fc in fcs], workers)
    return tuple(PairDesign(pair, own, combined.combined_result(own, options[index * len(fcs):(index + 1) * len(fcs)]))
                 for index, (pair, own) in enumerate(zip(ctx.project.combined_footings, owns, strict=True)))


def family_key(ctx: combined.Context) -> tuple[Any, ...]:
    """Lo que dos pares deben tener igual para compartir tipo (D-157): dirección principal, separación entre columnas en
    orden (a 1 mm), secciones y linderos en ese orden y el mismo combined_design."""
    project = ctx.project
    first, second = combined.ordered(ctx)
    columns = tuple((column.cx, column.cy, tuple(sorted((column.property_lines or {}).items()))) for column in (first, second))
    return (project.principal_direction, round(second.x - first.x), round(second.y - first.y), columns,
            project.combined_design.model_dump_json())


def families(pairs: Sequence[PairDesign]) -> list[list[PairDesign]]:
    """Los pares agrupados por familia, en el orden en que aparece cada una."""
    found: dict[tuple[Any, ...], list[PairDesign]] = {}
    for design in pairs:
        found.setdefault(family_key(design.ctx), []).append(design)
    return list(found.values())


def merged_project(group: Sequence[PairDesign]) -> CombinedDesignProject:
    """El proyecto de diseño de un tipo: las columnas del primer par (en orden) con los casos de todos los pares, cada uno
    marcado con su par ("ZC3: COMB1"); placement_case, el del primer par."""
    first = group[0]
    base = first.ctx.project
    loads: list[list[Any]] = [[], []]
    for design in group:
        for index, column in enumerate(combined.ordered(design.ctx)):
            loads[index] += [load.model_copy(update={"case": f"{design.pair.id}: {load.case}"}) for load in column.loads]
    columns = tuple(column.model_copy(update={"loads": tuple(own)}) for column, own in zip(combined.ordered(first.ctx), loads, strict=True))
    chosen = base.combined_design.placement_case
    design_block = base.combined_design.model_copy(update={"placement_case": None if chosen is None else f"{first.pair.id}: {chosen}"})
    names = ", ".join(design.pair.id for design in group)
    return base.model_copy(update={"columns": columns, "combined_design": design_block,
                                   "description": f"Tipo de zapata combinada para {names} (D-157)."})


def _axis(low: float, high: float, step: float) -> list[float]:
    """Los valores cada step de low a high, con los dos extremos."""
    count = max(math.ceil(round((high - low) / step, 9)), 0)
    return sorted({*(low + index * step for index in range(count)), high})


def anchors(group: Sequence[PairDesign], h: float) -> list[tuple[float, float]]:
    """Las posiciones de la base que se prueban para un tipo (D-157): la rejilla, cada plan_step en X y en Y globales,
    entre la menor y la mayor de las resultantes de placement_case de los pares, llevadas a las columnas del primero."""
    origin = combined.ordered(group[0].ctx)[0]
    points = []
    for design in group:
        resultant = combined.placement(design.ctx, h)
        own = combined.ordered(design.ctx)[0]
        points.append((origin.x + resultant[0] - own.x, origin.y + resultant[1] - own.y))
    step = group[0].ctx.design.plan_step
    xs = _axis(min(x for x, _ in points), max(x for x, _ in points), step)
    ys = _axis(min(y for _, y in points), max(y for _, y in points), step)
    return [(x, y) for x in xs for y in ys]


Designed = dict[tuple[float, tuple[str, ...]], Group | None]


def _ranked(family: Sequence[PairDesign], fc: float) -> list[PairDesign]:
    """Los pares de la familia en orden de su costo individual en este f'c."""
    def individual(design: PairDesign) -> float:
        solution = design.at(fc)
        return math.inf if solution is None else solution.cost

    return sorted(family, key=individual)


def _spans(size: int, most: int) -> list[tuple[int, int, int]]:
    """Los (m, inicio, fin) que recorre la programación dinámica de una familia de size pares en a lo más most grupos:
    con m < most, todos los fines (los usa m + 1); con m = most, solo el último; un solo grupo empieza en el primero."""
    return [(m, start, end) for m in range(1, most + 1) for end in (range(m, size + 1) if m < most else (size,))
            for start in (range(m - 1, end) if m > 1 else (0,))]


def _most(found: Sequence[Sequence[PairDesign]], family: Sequence[PairDesign], count: int) -> int:
    """Los tipos que puede usar una familia: los suyos sin dejar a las demás sin uno."""
    return min(len(family), count - len(found) + 1)


def _key(fc: float, group: Sequence[PairDesign]) -> tuple[float, tuple[str, ...]]:
    return fc, tuple(design.pair.id for design in group)


def group_designs(pairs: Sequence[PairDesign], fc_options: Sequence[float], count: int, workers: int = 1) -> Designed:
    """El tipo de cada grupo de dos o más pares que puede usar la agrupación en cada f'c (D-157): la combinada más barata
    entre las posiciones de anchors, diseñada con los casos de todos sus pares; None si no tiene solución. workers reparte
    entre procesos todas las búsquedas (f'c, grupo y posición), sin cambiar el resultado."""
    if not pairs:
        return {}
    found = families(pairs)
    jobs: list[tuple[float, tuple[PairDesign, ...], CombinedDesignProject, tuple[float, float]]] = []
    for fc in fc_options:
        if any(design.at(fc) is None for design in pairs) or len(found) > count:
            continue
        for family in found:
            ranked = _ranked(family, fc)
            spans = sorted({(start, end) for _, start, end in _spans(len(ranked), _most(found, family, count)) if end - start > 1})
            for start, end in spans:
                group = tuple(ranked[start:end])
                project = merged_project(group)
                jobs += [(fc, group, project, anchor) for anchor in anchors(group, project.combined_design.h_min)]
    first = pairs[0].ctx
    options = combined.design_tasks([(project, tuple(first.bars), fc, anchor) for fc, _, project, anchor in jobs], workers)
    designed: Designed = {}
    for (fc, group, project, anchor), option in zip(jobs, options, strict=True):
        key = _key(fc, group)
        best = designed.setdefault(key, None)
        if option.solution is not None and (best is None or option.solution.cost < best.solution.cost):
            designed[key] = Group(group, option.solution, combined.Context(project, first.profile, first.bars, anchor))
    return designed


def _family_parts(family: list[PairDesign], fc: float, most: int, designed: Designed) -> list[tuple[float, list[Group]] | None]:
    """Para m = 1 … most tipos, la mejor partición de la familia en m grupos seguidos (en orden del costo individual) y
    su costo; None si m grupos no tienen solución. Un grupo de un solo par es su diseño individual (D-153)."""
    ranked = _ranked(family, fc)
    size = len(ranked)

    def segment(start: int, end: int) -> tuple[float, Group | None]:
        if end - start == 1:
            solution = ranked[start].at(fc)
            found = None if solution is None else Group((ranked[start],), solution, ranked[start].ctx)
        else:
            found = designed.get(_key(fc, ranked[start:end]))
        return (math.inf, None) if found is None else (found.solution.cost * (end - start), found)

    # best[m][j]: el menor costo de los primeros j pares en m grupos, con sus grupos.
    best: list[list[tuple[float, list[Group]]]] = [[(math.inf, [])] * (size + 1) for _ in range(most + 1)]
    best[0][0] = (0.0, [])
    for m, start, end in _spans(size, most):
        previous = best[m - 1][start]
        if math.isinf(previous[0]):
            continue
        cost, found = segment(start, end)
        if found is not None and previous[0] + cost < best[m][end][0]:
            best[m][end] = (previous[0] + cost, [*previous[1], found])
    return [None if math.isinf(best[m][size][0]) else best[m][size] for m in range(1, most + 1)]


def grouping(pairs: Sequence[PairDesign], fc: float, count: int, designed: Designed) -> Grouping | None:
    """La agrupación de menor costo de los pares en a lo más count tipos en este f'c (D-157), con los tipos de
    group_designs; None si no la hay."""
    found = families(pairs)
    if any(design.at(fc) is None for design in pairs) or len(found) > count:
        return None
    parts = [_family_parts(family, fc, _most(found, family, count), designed) for family in found]
    # Reparto de los tipos entre las familias: options[k] = el menor costo usando k tipos en las familias vistas.
    options: dict[int, tuple[float, list[Group]]] = {0: (0.0, [])}
    for own in parts:
        updated: dict[int, tuple[float, list[Group]]] = {}
        for used, (cost, groups) in options.items():
            for index, part in enumerate(own, start=1):
                if part is None or used + index > count:
                    continue
                total = cost + part[0]
                if used + index not in updated or total < updated[used + index][0]:
                    updated[used + index] = (total, [*groups, *part[1]])
        options = updated
    if not options:
        return None
    cost, groups = min(options.values(), key=lambda item: item[0])
    return Grouping(tuple(groups), cost)


def pair_costs(pairs: tuple[PairDesign, ...], fc_options: tuple[float, ...]) -> dict[float, float]:
    """El costo de las combinadas en cada f'c, una por par; infinito si alguna no tiene solución con él."""
    costs = {}
    for fc in fc_options:
        solutions = [pair.at(fc) for pair in pairs]
        costs[fc] = math.inf if any(solution is None for solution in solutions) else sum(
            solution.cost for solution in solutions if solution is not None)
    return costs


def _chosen(pairs: tuple[PairDesign, ...], fc: float, groupings: dict[float, Grouping | None]) -> tuple[PairDesign, ...]:
    """Cada par con su solución en el f'c elegido: la de su tipo, puesta bajo sus columnas (D-157), o la suya (D-153)."""
    found = groupings.get(fc)
    if found is None:
        return tuple(replace(pair, solution=pair.at(fc)) for pair in pairs)
    typed: dict[str, PairDesign] = {}
    for index, group in enumerate(found.groups, start=1):
        for design in group.pairs:
            solution = group.solution if design.ctx is group.source else combined.transplanted(design.ctx, group.solution, group.source)
            typed[design.pair.id] = replace(design, solution=solution, typology=f"{_TYPE_PREFIX}{index}")
    return tuple(typed[pair.pair.id] for pair in pairs)


@dataclass(frozen=True)
class CombinedPart:
    """Las combinadas del diseño por tipologías, diseñadas una vez (D-153, D-157): los pares, su costo en cada f'c
    (infinito si alguno no tiene solución con él) y, con combined_typologies, sus tipos en cada f'c."""

    pairs: tuple[PairDesign, ...]
    costs: dict[float, float]
    groupings: dict[float, Grouping | None]

    def chosen(self, fc: float) -> tuple[PairDesign, ...]:
        """Cada par con la solución de su tipo (o la suya) en el f'c dado."""
        return _chosen(self.pairs, fc, self.groupings)


def combined_part(ctx: Context, workers: int = 1) -> CombinedPart | str:
    """Las combinadas del proyecto, que no dependen de las tipologías aisladas: la usan el diseño por tipologías y la
    curva costo–N (D-165, en la curva su costo es constante en cada f'c). Devuelve el error si hay más familias que
    combined_typologies (antes de diseñar)."""
    count = ctx.design.combined_typologies
    shapes = {own.design.shape for own in pair_contexts(ctx)}
    pending = sorted(combined.PENDING_SHAPES[shape] for shape in shapes if shape in combined.PENDING_SHAPES)
    if pending:  # la forma se declara, pero su diseño no está implementado (D-164, D-165)
        return "; ".join(pending)
    if count is not None:
        kinds = len({family_key(own) for own in pair_contexts(ctx)})  # antes de diseñar: las familias no dependen del diseño
        if kinds > count:
            return (f"hay {kinds} familias de pares compatibles y combined_typologies = {count}: cada familia necesita al menos "
                    "un tipo (D-157)")
    pairs = design_pairs(ctx, workers)
    groupings: dict[float, Grouping | None] = {}
    if not pairs:
        return CombinedPart(pairs, {}, groupings)
    if count is None:
        costs = pair_costs(pairs, ctx.design.fc_options)
    else:
        designed = group_designs(pairs, ctx.design.fc_options, count, workers)
        groupings = {fc: grouping(pairs, fc, count, designed) for fc in ctx.design.fc_options}
        costs = {fc: math.inf if found is None else found.cost for fc, found in groupings.items()}
    return CombinedPart(pairs, costs, groupings)


def design_with_pairs(ctx: Context, workers: int = 1) -> DesignResult:
    """Las tipologías aisladas y las combinadas (una por par o en tipos, D-157) con un solo f'c, el de menor costo total;
    el resultado lleva las combinadas (combined) y su costo (combined_cost)."""
    part = combined_part(ctx, workers)
    if isinstance(part, str):
        return DesignResult(None, (), math.inf, part, method=ctx.design.method)
    pairs, costs, groupings = part.pairs, part.costs, part.groupings
    if not pairs:
        return design_typologies(ctx, workers)
    if not ctx.project.columns:  # solo combinadas (D-156): el f'c de menor costo de las combinadas
        return _only_pairs(ctx, pairs, costs, groupings)
    result = design_typologies(ctx, workers, costs)
    if result.fc is None:
        return replace(result, combined=pairs)
    chosen = _chosen(pairs, result.fc, groupings)
    return replace(result, combined=chosen, combined_cost=sum(pair.solution.cost for pair in chosen if pair.solution is not None))


def _only_pairs(ctx: Context, pairs: tuple[PairDesign, ...], costs: dict[float, float],
                groupings: dict[float, Grouping | None]) -> DesignResult:
    """El diseño sin zapatas aisladas: las combinadas en el f'c de menor costo (con empate, el menor f'c)."""
    options = tuple(FcOption(fc, None if math.isinf(cost) else 0.0, None if math.isinf(cost) else 0,
                             "alguna zapata combinada no tiene solucion" if math.isinf(cost) else "")
                    for fc, cost in sorted(costs.items()))
    feasible = sorted((cost, fc) for fc, cost in costs.items() if not math.isinf(cost))
    basis = COST_BASIS[ctx.project.detailing is not None]
    if not feasible:
        return DesignResult(None, (), math.inf, "ninguna zapata combinada tiene solucion con un mismo f'c", options=options,
                            method=ctx.design.method, cost_basis=basis, combined=pairs)
    cost, fc = feasible[0]
    return DesignResult(fc, (), 0.0, options=options, method=ctx.design.method, cost_basis=basis,
                        combined=_chosen(pairs, fc, groupings), combined_cost=cost)


def designed_with_pairs(ctx: Context, result: DesignResult) -> dict[str, Any]:
    """El proyecto de verificación con las zapatas aisladas de las tipologías y cada combinada en el f'c elegido (con
    la geometría y el refuerzo de su tipo, D-157), con la ubicación de sus columnas (D-130) para la planta."""
    project = designed_project(ctx, result)
    pairs: tuple[PairDesign, ...] = result.combined
    if not pairs:
        return project
    footings = []
    for pair in pairs:
        assert pair.solution is not None
        footing = combined.designed_project(pair.ctx, pair.solution)["combined_footings"][0]
        locations = {column.id: column.location.model_dump() for column in pair.pair.columns if column.location is not None}
        columns = [{**column, **({"location": locations[column["id"]]} if column["id"] in locations else {})}
                   for column in footing["columns"]]
        footings.append({**footing, "id": pair.pair.id, **({"typology": pair.typology} if pair.typology else {}), "columns": columns})
    total = result.cost + result.combined_cost
    types = sorted({pair.typology for pair in pairs if pair.typology})
    typed = f" en {len(types)} tipos ({', '.join(types)}, D-157)" if types else ""
    project["description"] += (f" Con {len(pairs)} zapatas combinadas ({', '.join(pair.pair.id for pair in pairs)}, D-153){typed}, "
                               f"costo {result.combined_cost:.2f}; costo de la cimentacion {total:.2f} con un solo f'c.")
    project["combined_footings"] = footings
    return project
