"""Diseño de zapatas por tipologías (V3F, D-069): N zapatas tipo que cubren todas las columnas al menor costo.

Para cada f'c comercial con precio: (1) diseño individual de cada columna; (2) columnas ordenadas por el costo de su
diseño; (3) partición en N tramos continuos por programación dinámica, donde el costo de un tramo es el de la tipología
de su columna más exigente si cubre a todas, o el de un diseño del tramo completo si no; (4) reasignación: cada columna
pasa a la tipología elegida más barata que la cubre sin vaciar ningún grupo (D-074); (5) con el método milp (E2,
D-075), asignación óptima sobre el catálogo de la DP, sin la restricción de tramos continuos; (6) se elige el f'c de
menor costo total. Un solo f'c para todas las zapatas (D-069). Las tipologías repetidas se permiten y se marcan (D-074).
La tabla de tramos no depende de N: se diseñan todos los tramos de la lista ordenada.

Con milp_iter (E3b, D-077) no hay tabla de tramos: el catálogo parte de los diseños individuales y de un diseño de todas
las columnas; en cada iteración el MILP elige N tipologías, cada grupo propuesto se rediseña sobre exactamente sus
columnas y se agrega al catálogo, y se resuelve de nuevo desde la solución anterior, hasta que el costo no baja o se
alcanza el máximo de iteraciones o el tiempo límite.

Los diseños individuales, las coberturas y los diseños de tramo son independientes entre sí: con workers > 1 se reparten
entre procesos y la partición consulta la tabla ya calculada. El resultado es el mismo con cualquier número de procesos.
"""

import itertools
import math
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from typing import Any

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing.assignment import assign
from structurelab_rc.design.footing.grouping import partition, reassign
from structurelab_rc.design.footing.typology import (
    Context,
    GroupDesign,
    Typology,
    column_cost,
    covers,
    design_group,
    priced,
    typology_key,
)
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.design import DesignColumn, FootingDesignProject
from structurelab_rc.model.footing import MPA_PER_KPA, N_MM3_PER_KN_M3, N_PER_KN, NMM_PER_KNM, FootingLoad, Soil

# Tareas: ("single", fc, columna), ("covers", tipología, columna), ("design", fc, columnas, tipología de partida); las
# columnas son índices de project.columns, para no copiar las columnas a cada proceso en cada tarea.
Task = tuple[Any, ...]
Runner = Callable[[list[Task]], list[Any]]
_WORKER: Context | None = None  # contexto de cada proceso del pool, armado una vez por _start_worker
_G_PER_KG = 1000  # el acero entra al MILP en gramos enteros
_GROUP = 2  # milp_iter: un grupo propuesto se rediseña desde dos columnas


@dataclass(frozen=True)
class TypologyResult:
    name: str
    design: GroupDesign
    columns: tuple[str, ...]


@dataclass(frozen=True)
class Move:
    """Columna reasignada (D-074): de la tipología source a target, con el ahorro."""

    column: str
    source: str
    target: str
    saving: float


@dataclass(frozen=True)
class MilpInfo:
    """El MILP de un f'c (E2, D-075) frente a la DP de la que parte. status: optimal (óptimo certificado en el catálogo),
    time_limit (sin certificar) o infeasible (sin N tipologías distintas que cubran todo: queda la DP)."""

    status: str
    dp_cost: float
    dp_distinct_count: int
    milp_cost: float | None
    candidates: int
    seconds: float  # matriz de cobertura y solucionador
    note: str = ""


@dataclass(frozen=True)
class Iteration:
    """Una iteración de milp_iter (E3b, D-077): candidatos del catálogo, costo de la asignación del MILP, su estado y el
    tiempo transcurrido en el f'c."""

    number: int
    candidates: int
    cost: float
    status: str
    seconds: float = field(compare=False)  # medición, no resultado: no entra en la comparación de resultados


@dataclass(frozen=True)
class FcOption:
    """Un f'c evaluado: su costo total y sus tipologías distintas, o por qué no tiene solución."""

    fc: float
    cost: float | None
    distinct_count: int | None
    failure: str = ""
    milp: MilpInfo | None = None
    iterations: tuple[Iteration, ...] = ()


@dataclass(frozen=True)
class Duplicate:
    """Tipologías idénticas de la solución (D-074) y los límites de diseño en que está esa tipología: "plan_max" si el
    paso siguiente de planta lo supera, "h_max" si el de espesor lo supera."""

    typologies: tuple[str, ...]
    at_limit: tuple[str, ...]


@dataclass(frozen=True)
class DesignResult:
    """Solución: f'c, tipologías y costo total; failure explica por qué no la hay (dentro de los límites)."""

    fc: float | None
    typologies: tuple[TypologyResult, ...]
    cost: float
    failure: str = ""
    cost_before_reassignment: float = math.inf
    reassigned: tuple[Move, ...] = ()
    options: tuple[FcOption, ...] = ()
    distinct_count: int = 0
    duplicates: tuple[Duplicate, ...] = ()
    method: str = "dp"
    milp: MilpInfo | None = None
    iterations: tuple[Iteration, ...] = ()


def _duplicates(ctx: Context, typologies: Sequence[TypologyResult]) -> tuple[Duplicate, ...]:
    groups: dict[tuple[Any, ...], list[TypologyResult]] = {}
    for item in typologies:
        groups.setdefault(typology_key(item.design.typology), []).append(item)
    design = ctx.design
    found = []
    for items in groups.values():
        if len(items) == 1:
            continue
        t = items[0].design.typology
        limits = tuple(name for name, reached in (("plan_max", max(t.lx, t.ly) + design.plan_step > design.plan_max),
                                                  ("h_max", t.h + design.h_step > design.h_max)) if reached)
        found.append(Duplicate(tuple(item.name for item in items), limits))
    return tuple(found)


def _distinct_count(typologies: Sequence[Typology]) -> int:
    return len({typology_key(typology) for typology in typologies})


def _duplicates_warning(result: DesignResult) -> str:
    """Advertencia de tipologías repetidas (D-074), vacía si no las hay; va en la descripción del proyecto diseñado, que
    la memoria muestra en su encabezado."""
    if not result.duplicates:
        return ""
    groups = "; ".join(" = ".join(group.typologies) + (f" (en el límite {', '.join(group.at_limit)})" if group.at_limit else "")
                       for group in result.duplicates)
    return f" ADVERTENCIA: tipologías repetidas: {groups}; {result.distinct_count} distintas de {len(result.typologies)} (D-074)."


def _run(ctx: Context, task: Task) -> Any:
    kind, *args = task
    columns = ctx.project.columns
    if kind == "single":
        fc, index = args
        return design_group(ctx, [columns[index]], fc)
    if kind == "covers":
        typology, index = args
        return covers(ctx, typology, columns[index])
    # "design": tramo de la tabla, búsqueda rápida; "refine": grupo elegido, con el barrido de espesores (D-076).
    fc, indices, start = args
    return design_group(ctx, [columns[index] for index in indices], fc, start=start, sweep=kind == "refine")


def _start_worker(project: FootingDesignProject, bars: Sequence[RebarSpec]) -> None:
    global _WORKER
    _WORKER = Context(project, PROFILES[project.profile], bars)  # el perfil (módulos) no se copia entre procesos


def _run_in_worker(task: Task) -> Any:
    assert _WORKER is not None
    return _run(_WORKER, task)


Chosen = list[tuple[GroupDesign, list[DesignColumn]]]
Shift = tuple[str, int, int, float]  # columna, grupo de origen, grupo de destino (índices de Chosen) y ahorro


@dataclass(frozen=True)
class _FcSolution:
    total: float
    chosen: Chosen
    before: float  # costo de la partición, antes de reasignar
    shifts: list[Shift]
    milp: MilpInfo | None = None
    iterations: tuple[Iteration, ...] = ()


@dataclass(frozen=True)
class _Tables:
    """Lo que no depende de N en un f'c: columnas ordenadas por el costo de su diseño individual, esos diseños y el
    diseño de cada tramo start..end de la lista ordenada (None si no tiene)."""

    fc: float
    ordered: list[DesignColumn]
    singles: dict[str, GroupDesign]
    table: dict[tuple[int, int], GroupDesign | None]


def _positions(ctx: Context) -> dict[str, int]:
    return {column.id: index for index, column in enumerate(ctx.project.columns)}


def _for_fc(ctx: Context, fc: float, run: Runner) -> _FcSolution | str:
    if ctx.design.method == "milp_iter":
        return _iterative(ctx, fc, run)
    tables = _tables(ctx, fc, run)
    return tables if isinstance(tables, str) else _from_tables(ctx, tables, run)


def _from_tables(ctx: Context, tables: _Tables, run: Runner) -> _FcSolution | str:
    """dp o milp con N = design.typologies sobre la tabla de tramos de un f'c, que no depende de N (D-075), y el
    refinamiento de los grupos elegidos (D-076)."""
    solution = _dp(ctx, tables, run)
    if isinstance(solution, str):
        return solution
    if ctx.design.method == "milp":
        solution = _milp(ctx, tables, solution, run)
        if isinstance(solution, str):
            return solution
    return _refine(ctx, tables, solution, run)


def _refine(ctx: Context, tables: _Tables, solution: _FcSolution, run: Runner) -> _FcSolution:
    """Rediseña cada grupo elegido sobre exactamente sus columnas con el barrido de espesores (D-076): la tabla de tramos
    usa la búsqueda rápida y el barrido solo se paga donde decide el resultado. Un grupo se reemplaza solo si baja de
    costo, así que el total nunca sube."""
    chosen = _refined(ctx, tables.fc, tables.singles, solution.chosen, run)
    if all(new is old for (new, _), (old, _) in zip(chosen, solution.chosen, strict=True)):
        return solution
    return replace(solution, total=sum(design.cost for design, _ in chosen), chosen=chosen)


def _refined(ctx: Context, fc: float, singles: dict[str, GroupDesign], chosen: Chosen, run: Runner) -> Chosen:
    """Cada grupo con su rediseño por barrido sobre exactamente sus columnas si baja de costo (D-076)."""
    position = _positions(ctx)
    tasks: list[Task] = [("refine", fc, tuple(position[column.id] for column in members), _largest(singles, members))
                         for _, members in chosen]
    return [(refined, members) if refined is not None and refined.cost < design.cost else (design, members)
            for (design, members), refined in zip(chosen, run(tasks), strict=True)]


def _singles(ctx: Context, fc: float, run: Runner) -> dict[str, GroupDesign] | str:
    """Diseño individual de cada columna, o por qué una no tiene zapata dentro de los límites."""
    columns = ctx.project.columns
    designs = run([("single", fc, index) for index in range(len(columns))])
    singles: dict[str, GroupDesign] = {}
    for column, single in zip(columns, designs, strict=True):
        if single is None:
            return f"f'c = {fc:g} MPa: la columna {column.id} no tiene zapata dentro de los límites"
        singles[column.id] = single
    return singles


def _tables(ctx: Context, fc: float, run: Runner) -> _Tables | str:
    columns = ctx.project.columns
    singles = _singles(ctx, fc, run)
    if isinstance(singles, str):
        return singles
    position = _positions(ctx)
    ordered = sorted(columns, key=lambda column: (singles[column.id].cost, column.id))
    count = len(ordered)
    segments = [(start, end) for end in range(count) for start in range(end + 1)]  # todos: la tabla no depende de N

    # Pasadores con que la tipología individual de ordered[owner] cubre a ordered[member] (None si no lo cubre).
    pairs = sorted({(end, member) for start, end in segments for member in range(start, end)})
    covered: dict[tuple[int, int], dict[str, Any] | None] = {
        (owner, owner): singles[ordered[owner].id].dowels[ordered[owner].id] for owner in range(count)}
    tasks: list[Task] = [("covers", singles[ordered[owner].id].typology, position[ordered[member].id]) for owner, member in pairs]
    covered.update(zip(pairs, run(tasks), strict=True))

    # Costo de cada tramo: la tipología de su columna más exigente si cubre a todas, o un diseño del tramo completo.
    table: dict[tuple[int, int], GroupDesign | None] = {}
    pending = []
    for start, end in segments:
        members = ordered[start : end + 1]
        dowels = {ordered[member].id: covered[(end, member)] for member in range(start, end + 1)}
        if all(value is not None for value in dowels.values()):
            table[(start, end)] = priced(ctx, singles[ordered[end].id].typology, members,
                                         {key: value for key, value in dowels.items() if value is not None})
        else:
            pending.append((start, end))
    # Los tramos más largos primero: cuestan más y, al final de la lista, dejaban a unos pocos procesos trabajando solos.
    # El orden de cálculo no cambia el resultado: cada rediseño vuelve a su tramo.
    pending.sort(key=lambda segment: (segment[0] - segment[1], segment))
    tasks = [("design", fc, tuple(position[column.id] for column in ordered[start : end + 1]),
              _largest(singles, ordered[start : end + 1])) for start, end in pending]
    table.update(zip(pending, run(tasks), strict=True))
    return _Tables(fc, ordered, singles, table)


def _dp(ctx: Context, tables: _Tables, run: Runner) -> _FcSolution | str:
    """Partición en N tramos continuos de la lista ordenada y reasignación (D-074)."""
    ordered, table, groups = tables.ordered, tables.table, ctx.design.typologies

    def cost(start: int, end: int) -> float:
        result = table.get((start, end))
        return math.inf if result is None else result.cost

    total, chosen_segments = partition(len(ordered), groups, cost)
    if not chosen_segments:
        return f"f'c = {tables.fc:g} MPa: no hay {groups} tipologías que cubran todas las columnas"
    chosen = []
    for start, end in chosen_segments:
        result = table[(start, end)]
        assert result is not None
        chosen.append((result, list(ordered[start : end + 1])))
    regrouped, shifts = _reassign(ctx, chosen, run, _positions(ctx))
    if not shifts:  # sin cambios: la misma solución y el mismo total que la partición
        return _FcSolution(total, chosen, total, [])
    return _FcSolution(sum(design.cost for design, _ in regrouped), regrouped, total, shifts)


def _milp(ctx: Context, tables: _Tables, dp: _FcSolution, run: Runner) -> _FcSolution | str:
    """MILP (E2, D-075) sobre el catálogo de la DP: los diseños individuales y los de los tramos, sin repetidas; matriz
    completa de cobertura con covers(); arranque desde la DP si no tiene repetidas."""
    begin = time.perf_counter()
    columns, groups = ctx.project.columns, ctx.design.typologies
    raw = [tables.singles[column.id].typology for column in tables.ordered]
    raw += [design.typology for _, design in sorted(tables.table.items(), key=lambda item: item[0]) if design is not None]
    catalog = list({typology_key(typology): typology for typology in raw}.values())
    width = len(catalog)
    found = run([("covers", typology, index) for index in range(len(columns)) for typology in catalog])
    dowels = [found[index * width : (index + 1) * width] for index in range(len(columns))]
    cost, steel = _pair_costs(ctx, catalog, dowels)

    index = {typology_key(typology): j for j, typology in enumerate(catalog)}
    position = _positions(ctx)
    dp_choice = [0] * len(columns)
    for design, members in dp.chosen:
        for column in members:
            dp_choice[position[column.id]] = index[typology_key(design.typology)]
    dp_distinct = len(set(dp_choice))
    start = dp_choice if dp_distinct == groups else None  # con repetidas la DP no es factible en el modelo
    result = assign(cost, steel, groups, start, ctx.design.milp_time_limit)
    seconds = time.perf_counter() - begin
    if not result.choice:
        note = f"sin {groups} tipologías distintas del catálogo que cubran todas las columnas: queda la DP"
        return replace(dp, milp=MilpInfo(result.status, dp.total, dp_distinct, None, width, seconds, note))
    if start is not None:  # C_MILP ≤ C_DP, en pesos enteros (D-074: solo si la DP no tiene repetidas)
        dp_cost = sum(cost[i][j] or 0 for i, j in enumerate(dp_choice))
        if result.cost > dp_cost:
            return f"f'c = {tables.fc:g} MPa: el MILP dio {result.cost} y la DP {dp_cost}; resultado rechazado (error interno)"
    chosen = _chosen(ctx, catalog, dowels, result.choice)
    total = sum(design.cost for design, _ in chosen)
    note = "" if start is not None else (f"la DP tiene repetidas ({dp_distinct} distintas de {groups}): no sirve de arranque "
                                         "y C_MILP ≤ C_DP no se exige (D-074)")
    return _FcSolution(total, chosen, total, [], MilpInfo(result.status, dp.total, dp_distinct, total, width, seconds, note))


def _pair_costs(
    ctx: Context, catalog: Sequence[Typology], dowels: Sequence[Sequence[dict[str, Any] | None]]
) -> tuple[list[list[int | None]], list[list[int | None]]]:
    """Costo (pesos enteros) y acero (gramos enteros) de cada columna con cada candidato del catálogo; None si no la cubre
    (dowels[i][j] son los pasadores con que el candidato j cubre la columna i)."""
    columns = ctx.project.columns
    pairs = [[None if (found := dowels[i][j]) is None else column_cost(ctx, catalog[j], columns[i], found) for j in range(len(catalog))]
             for i in range(len(columns))]
    cost = [[None if pair is None else round(pair[0]) for pair in row] for row in pairs]
    steel = [[None if pair is None else round(pair[2] * _G_PER_KG) for pair in row] for row in pairs]
    return cost, steel


def _chosen(
    ctx: Context, catalog: Sequence[Typology], dowels: Sequence[Sequence[dict[str, Any] | None]], choice: Sequence[int]
) -> Chosen:
    """Los grupos de una asignación del MILP: cada candidato elegido con sus columnas y sus pasadores."""
    columns = ctx.project.columns
    chosen: Chosen = []
    for j in sorted(set(choice)):
        rows = [i for i, chosen_j in enumerate(choice) if chosen_j == j]
        dowel_map: dict[str, dict[str, Any]] = {}
        for i in rows:
            found = dowels[i][j]
            assert found is not None  # el MILP solo asigna pares que covers() aprueba
            dowel_map[columns[i].id] = found
        chosen.append((priced(ctx, catalog[j], [columns[i] for i in rows], dowel_map), [columns[i] for i in rows]))
    return chosen


@dataclass
class _Catalog:
    """Estado de milp_iter en un f'c (E3b, D-077): diseños individuales, candidatos sin repetir, pasadores con que cada
    candidato cubre cada columna (dowels[i][j]) y los grupos ya rediseñados. No depende de N: la curva costo–N (D-078) lo
    conserva entre valores de N, y solo crece."""

    fc: float
    singles: dict[str, GroupDesign]
    catalog: list[Typology] = field(default_factory=list)
    keys: set[Any] = field(default_factory=set)
    dowels: list[list[dict[str, Any] | None]] = field(default_factory=list)
    redesigned: set[tuple[int, ...]] = field(default_factory=set)


def _new_catalog(ctx: Context, fc: float, run: Runner) -> _Catalog | str:
    """Catálogo inicial: los diseños individuales y uno de todas las columnas (con él siempre hay N tipologías que cubren
    todo: esa y N − 1 individuales)."""
    columns = ctx.project.columns
    singles = _singles(ctx, fc, run)
    if isinstance(singles, str):
        return singles
    seed = run([("design", fc, tuple(range(len(columns))), _largest(singles, columns))])[0]
    state = _Catalog(fc, singles, dowels=[[] for _ in columns])
    _extend(ctx, state, [singles[column.id].typology for column in columns] + ([] if seed is None else [seed.typology]), run)
    return state


def _extend(ctx: Context, state: _Catalog, candidates: Sequence[Typology], run: Runner) -> None:
    """Agrega los candidatos nuevos y calcula con covers() solo su cobertura."""
    columns = ctx.project.columns
    new = []
    for typology in candidates:
        if typology_key(typology) not in state.keys:
            state.keys.add(typology_key(typology))
            new.append(typology)
    found = run([("covers", typology, index) for index in range(len(columns)) for typology in new])
    for index in range(len(columns)):
        state.dowels[index].extend(found[index * len(new) : (index + 1) * len(new)])
    state.catalog.extend(new)


def _iterative(ctx: Context, fc: float, run: Runner) -> _FcSolution | str:
    """milp_iter (E3b, D-077) en un f'c: catálogo inicial e iteraciones."""
    state = _new_catalog(ctx, fc, run)
    return state if isinstance(state, str) else _iterate(ctx, state, run)


def _iterate(ctx: Context, state: _Catalog, run: Runner) -> _FcSolution | str:
    """Iteraciones de milp_iter con N = design.typologies (E3b, D-077): MILP desde la solución anterior y rediseño de lo
    propuesto. El catálogo solo crece, así que el costo nunca sube. Para cuando el costo no baja, cuando los rediseños no
    agregan candidatos, en design.iter_max iteraciones o al pasar design.iter_time_limit_s."""
    begin = time.perf_counter()
    design, groups, fc, singles = ctx.design, ctx.design.typologies, state.fc, state.singles
    iterations: list[Iteration] = []
    start: Sequence[int] | None = None
    best: Chosen | None = None
    best_total = math.inf
    while True:
        cost, steel = _pair_costs(ctx, state.catalog, state.dowels)
        result = assign(cost, steel, groups, start, design.milp_time_limit)
        if not result.choice:
            break
        chosen = _chosen(ctx, state.catalog, state.dowels, result.choice)
        total = sum(group.cost for group, _ in chosen)
        iterations.append(Iteration(len(iterations) + 1, len(state.catalog), total, result.status, time.perf_counter() - begin))
        improved = total < best_total - 1e-6
        if improved:
            best, best_total, start = chosen, total, result.choice
        tasks = [task for task in _proposals(ctx, fc, singles, chosen) if task[2] not in state.redesigned]
        if (not improved or not tasks or len(iterations) >= design.iter_max
                or time.perf_counter() - begin >= design.iter_time_limit):
            break
        state.redesigned.update(task[2] for task in tasks)
        size = len(state.catalog)
        _extend(ctx, state, [found.typology for found in run(tasks) if found is not None], run)
        if len(state.catalog) == size:
            break  # los rediseños ya estaban en el catálogo: el MILP daría lo mismo
    if best is None:
        return f"f'c = {fc:g} MPa: no hay {groups} tipologías del catálogo que cubran todas las columnas"
    best = _refined(ctx, fc, singles, best, run)
    total = sum(group.cost for group, _ in best)
    return _FcSolution(total, best, total, [], iterations=tuple(iterations))


def _proposals(ctx: Context, fc: float, singles: dict[str, GroupDesign], chosen: Chosen) -> list[Task]:
    """Rediseños que propone una solución del MILP (E3b, D-077): cada grupo de dos o más columnas sobre exactamente sus
    columnas, con el barrido de espesores, y, con la búsqueda rápida, el reparto de cada par de grupos: la unión de sus
    columnas, ordenada por el costo de su diseño individual, cortada en dos en cada posición (las primeras s y las
    demás). Las columnas van como índices ordenados, sin repetir un conjunto."""
    position = _positions(ctx)
    tasks: list[Task] = []
    seen: set[tuple[int, ...]] = set()

    def add(kind: str, members: Sequence[DesignColumn]) -> None:
        indices = tuple(sorted(position[column.id] for column in members))
        if indices not in seen:
            seen.add(indices)
            tasks.append((kind, fc, indices, _largest(singles, members)))

    def cost_order(members: Sequence[DesignColumn]) -> list[DesignColumn]:
        return sorted(members, key=lambda column: (singles[column.id].cost, column.id))

    for _, members in chosen:
        if len(members) >= _GROUP:
            add("refine", members)
    groups = sorted((cost_order(members) for _, members in chosen), key=lambda members: (singles[members[-1].id].cost, members[-1].id))
    for first, second in itertools.combinations(groups, 2):
        union = cost_order([*first, *second])
        for cut in range(1, len(union)):
            for part in (union[:cut], union[cut:]):
                if len(part) >= _GROUP:
                    add("design", part)
    return tasks


def _reassign(ctx: Context, chosen: Chosen, run: Runner, position: dict[str, int]) -> tuple[Chosen, list[Shift]]:
    """Reasignación de D-074 entre las tipologías elegidas, sin rediseñarlas: solo las columnas de grupos con más de una
    pueden moverse, y solo a una tipología que las cubre (covers)."""
    members = [(column, group) for group, (_, columns) in enumerate(chosen) for column in columns]
    movable = [(column, group) for column, group in members if len(chosen[group][1]) > 1]
    pairs = [(column, other) for column, group in movable for other in range(len(chosen)) if other != group]
    found: dict[tuple[str, int], dict[str, Any] | None] = {
        (column.id, group): chosen[group][0].dowels[column.id] for column, group in members}
    tasks: list[Task] = [("covers", chosen[other][0].typology, position[column.id]) for column, other in pairs]
    found.update(zip(((column.id, other) for column, other in pairs), run(tasks), strict=True))

    costs: dict[tuple[int, int], float] = {}

    def cost(item: int, group: int) -> float:
        if (item, group) not in costs:
            column = members[item][0]
            dowels = found.get((column.id, group))
            costs[(item, group)] = math.inf if dowels is None else priced(
                ctx, chosen[group][0].typology, [column], {column.id: dowels}).cost
        return costs[(item, group)]

    order = sorted(range(len(members)), key=lambda item: members[item][0].id)
    owner = reassign([group for _, group in members], len(chosen), cost, order)
    shifts = [(members[item][0].id, group, owner[item], cost(item, group) - cost(item, owner[item]))
              for item, (_, group) in enumerate(members) if owner[item] != group]
    regrouped: Chosen = []
    for group, (design, columns) in enumerate(chosen):
        now = [members[item][0] for item in range(len(members)) if owner[item] == group]
        if [column.id for column in now] == [column.id for column in columns]:
            regrouped.append((design, columns))  # grupo sin cambios: el mismo diseño y el mismo costo
            continue
        dowels = {column.id: found[(column.id, group)] for column in now}
        regrouped.append((priced(ctx, design.typology, now, {key: value for key, value in dowels.items() if value is not None}), now))
    return regrouped, shifts


def _largest(singles: dict[str, GroupDesign], members: Sequence[DesignColumn]) -> Typology:
    """Punto de partida de un tramo: la mayor planta y el mayor espesor de sus diseños individuales."""
    typologies = [singles[column.id].typology for column in members]
    widest = max(typologies, key=lambda typology: (typology.lx * typology.ly, typology.h))
    return Typology(widest.fc, max(t.lx for t in typologies), max(t.ly for t in typologies),
                    max(t.h for t in typologies), widest.bottom, widest.top)


def design_typologies(ctx: Context, workers: int = 1) -> DesignResult:
    """workers: procesos entre los que se reparte el diseño (1: en este proceso); no cambia el resultado."""
    if workers <= 1:
        return _design(ctx, lambda tasks: [_run(ctx, task) for task in tasks])
    with ProcessPoolExecutor(workers, initializer=_start_worker, initargs=(ctx.project, tuple(ctx.bars))) as pool:
        return _design(ctx, lambda tasks: _in_pool(pool, tasks, workers))


@dataclass(frozen=True)
class CurvePoint:
    """Un punto de la curva costo–N (D-078): el diseño con N tipologías, el ahorro frente al punto anterior (None en el
    primero) y si su costo sube respecto a él."""

    count: int
    result: DesignResult
    saving: float | None
    rises: bool


def typology_curve(ctx: Context, counts: Sequence[int], workers: int = 1) -> tuple[CurvePoint, ...]:
    """Curva costo–N (D-078): el diseño con cada N de counts (en orden creciente). Lo que no depende de N se calcula una
    vez por f'c y se conserva: con milp_iter, el catálogo y su cobertura (que siguen creciendo entre valores de N); con
    milp y dp, la tabla de tramos. Determinista: la misma curva da el mismo resultado con cualquier número de procesos."""
    if workers <= 1:
        return _curve(ctx, sorted(counts), lambda tasks: [_run(ctx, task) for task in tasks])
    with ProcessPoolExecutor(workers, initializer=_start_worker, initargs=(ctx.project, tuple(ctx.bars))) as pool:
        return _curve(ctx, sorted(counts), lambda tasks: _in_pool(pool, tasks, workers))


def _curve(ctx: Context, counts: Sequence[int], run: Runner) -> tuple[CurvePoint, ...]:
    cache: dict[float, _Catalog | _Tables | str] = {}

    def solve(ctx_n: Context, fc: float, run: Runner) -> _FcSolution | str:
        if fc not in cache:
            cache[fc] = _new_catalog(ctx, fc, run) if ctx.design.method == "milp_iter" else _tables(ctx, fc, run)
        state = cache[fc]
        if isinstance(state, str):
            return state
        return _iterate(ctx_n, state, run) if isinstance(state, _Catalog) else _from_tables(ctx_n, state, run)

    points: list[CurvePoint] = []
    for count in counts:
        project = ctx.project.model_copy(update={"design": ctx.design.model_copy(update={"typologies": count})})
        result = _design(Context(project, ctx.profile, ctx.bars), run, solve)
        previous = points[-1].result.cost if points and points[-1].result.fc is not None else None
        if result.fc is None or previous is None:
            points.append(CurvePoint(count, result, None, False))
        else:
            points.append(CurvePoint(count, result, previous - result.cost, result.cost > previous + 1e-6))
    return tuple(points)


def _in_pool(pool: Executor, tasks: list[Task], workers: int) -> list[Any]:
    chunk = max(1, len(tasks) // (8 * workers))  # tareas de duración dispar: lotes pequeños reparten mejor la carga
    return list(pool.map(_run_in_worker, tasks, chunksize=chunk))


Solver = Callable[[Context, float, Runner], "_FcSolution | str"]


def _design(ctx: Context, run: Runner, solve: Solver = _for_fc) -> DesignResult:
    best: tuple[float, _FcSolution] | None = None
    failures = []
    options = []
    for fc in sorted(ctx.design.fc_options):
        outcome = solve(ctx, fc, run)
        if isinstance(outcome, str):
            failures.append(outcome)
            options.append(FcOption(fc, None, None, outcome))
            continue
        options.append(FcOption(fc, outcome.total, _distinct_count([design.typology for design, _ in outcome.chosen]),
                                milp=outcome.milp, iterations=outcome.iterations))
        if best is None or outcome.total < best[1].total:
            best = (fc, outcome)
    if best is None:
        return DesignResult(None, (), math.inf, "; ".join(failures), options=tuple(options))
    fc, solution = best
    chosen = solution.chosen
    ranked = sorted(range(len(chosen)), key=lambda group: (chosen[group][0].typology.lx * chosen[group][0].typology.ly,
                                                            chosen[group][0].typology.h))
    names = {group: f"Z{index}" for index, group in enumerate(ranked, start=1)}
    typologies = tuple(TypologyResult(names[group], chosen[group][0], tuple(column.id for column in chosen[group][1]))
                       for group in ranked)
    moves = tuple(Move(column, names[source], names[target], saving) for column, source, target, saving in solution.shifts)
    return DesignResult(fc, typologies, solution.total, cost_before_reassignment=solution.before, reassigned=moves,
                        options=tuple(options), distinct_count=_distinct_count([item.design.typology for item in typologies]),
                        duplicates=_duplicates(ctx, typologies), method=ctx.design.method, milp=solution.milp,
                        iterations=solution.iterations)


def designed_project(ctx: Context, result: DesignResult) -> dict[str, Any]:
    """Proyecto de verificación (formato de entrada) con una zapata por columna, nombrada <tipología>-<columna>."""
    project = ctx.project
    assert result.fc is not None
    design = ctx.design
    columns = {column.id: column for column in project.columns}
    footings = []
    for typology in result.typologies:
        t = typology.design.typology
        for column_id in typology.columns:
            column = columns[column_id]
            footings.append({
                "id": f"{typology.name}-{column_id}", "lx": t.lx, "ly": t.ly, "h": t.h, "cover": design.cover,
                "fill_height": design.fill_height, "pedestal_height": design.pedestal_height,
                "surcharge_dead_kNm2": design.surcharge_dead, "surcharge_live_kNm2": design.surcharge_live,
                "column": {"cx": column.cx, "cy": column.cy, "offset_x": 0.0, "offset_y": 0.0,
                           "dowels": typology.design.dowels[column_id]},
                "bottom": t.bottom, "top": t.top,
                "loads": [load_input(load) for load in column.loads],
            })
    materials = project.materials
    return {
        "description": f"{project.description} Diseño por tipologías (D-069): {len(result.typologies)} tipologías, "
                       f"f'c = {result.fc:g} MPa, costo total {result.cost:.2f}.{_duplicates_warning(result)}",
        "profile": project.profile,
        "seismic": project.seismic.model_dump(),
        "materials": {"fc": result.fc, "fy": materials.fy, "fyt": materials.fyt, "concrete": materials.concrete,
                      "coating": materials.coating,
                      **({} if materials.max_aggregate is None else {"max_aggregate": materials.max_aggregate})},
        "soil": soil_input(ctx.soil),
        "footings": footings,
    }


def load_input(load: FootingLoad) -> dict[str, Any]:
    return {"case": load.case, "kind": load.kind, "dead_factor": load.dead_factor, "live_factor": load.live_factor,
            "seismic": load.seismic, "P_kN": load.p / N_PER_KN, "Vx_kN": load.vx / N_PER_KN, "Vy_kN": load.vy / N_PER_KN,
            "Mx_kNm": load.mx / NMM_PER_KNM, "My_kNm": load.my / NMM_PER_KNM}


def soil_input(soil: Soil) -> dict[str, float]:
    return {"allowable_pressure_kPa": soil.allowable_pressure / MPA_PER_KPA, "min_contact_fraction": soil.min_contact_fraction,
            "unit_weight_concrete_kNm3": soil.unit_weight_concrete / N_MM3_PER_KN_M3,
            "unit_weight_fill_kNm3": soil.unit_weight_fill / N_MM3_PER_KN_M3,
            "friction_coefficient": soil.friction_coefficient, "adhesion_kPa": soil.adhesion / MPA_PER_KPA,
            "passive_coefficient": soil.passive_coefficient, "cohesion_kPa": soil.cohesion / MPA_PER_KPA,
            "passive_factor": soil.passive_factor, "sliding_safety_factor": soil.sliding_safety_factor,
            "sliding_safety_factor_seismic": soil.sliding_safety_factor_seismic,
            "overturning_safety_factor": soil.overturning_safety_factor,
            "overturning_safety_factor_seismic": soil.overturning_safety_factor_seismic,
            "seismic_bearing_factor": soil.seismic_bearing_factor}
