"""Diseño de zapatas por tipologías (V3F, D-069): N zapatas tipo que cubren todas las columnas al menor costo.

Para cada f'c comercial con precio: (1) diseño individual de cada columna; (2) columnas ordenadas por el costo de su
diseño; (3) partición en N tramos continuos por programación dinámica, donde el costo de un tramo es el de la tipología
de su columna más exigente si cubre a todas, o el de un diseño del tramo completo si no; (4) se elige el f'c de menor costo
total y cada tipología final se verifica de nuevo con todas sus columnas. Un solo f'c para todas las zapatas (D-069).

Los diseños individuales, las coberturas y los diseños de tramo son independientes entre sí: con workers > 1 se reparten
entre procesos y la partición consulta la tabla ya calculada. El resultado es el mismo con cualquier número de procesos.
"""

import math
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.design.footing.grouping import partition
from structurelab_rc.design.footing.typology import Context, GroupDesign, Typology, covers, design_group, priced
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.design import DesignColumn, FootingDesignProject
from structurelab_rc.model.footing import MPA_PER_KPA, N_MM3_PER_KN_M3, N_PER_KN, NMM_PER_KNM, FootingLoad

# Tareas: ("single", fc, columna), ("covers", tipología, columna), ("design", fc, columnas, tipología de partida); las
# columnas son índices de project.columns, para no copiar las columnas a cada proceso en cada tarea.
Task = tuple[Any, ...]
Runner = Callable[[list[Task]], list[Any]]
_WORKER: Context | None = None  # contexto de cada proceso del pool, armado una vez por _start_worker


@dataclass(frozen=True)
class TypologyResult:
    name: str
    design: GroupDesign
    columns: tuple[str, ...]


@dataclass(frozen=True)
class DesignResult:
    """Solución: f'c, tipologías y costo total; failure explica por qué no la hay (dentro de los límites)."""

    fc: float | None
    typologies: tuple[TypologyResult, ...]
    cost: float
    failure: str = ""


def _run(ctx: Context, task: Task) -> Any:
    kind, *args = task
    columns = ctx.project.columns
    if kind == "single":
        fc, index = args
        return design_group(ctx, [columns[index]], fc)
    if kind == "covers":
        typology, index = args
        return covers(ctx, typology, columns[index])
    fc, indices, start = args
    return design_group(ctx, [columns[index] for index in indices], fc, start=start)


def _start_worker(project: FootingDesignProject, bars: Sequence[RebarSpec]) -> None:
    global _WORKER
    _WORKER = Context(project, PROFILES[project.profile], bars)  # el perfil (módulos) no se copia entre procesos


def _run_in_worker(task: Task) -> Any:
    assert _WORKER is not None
    return _run(_WORKER, task)


def _usable(start: int, end: int, count: int, groups: int) -> bool:
    """Si el tramo start..end puede ser uno de los `groups` tramos de una partición de 0..count−1 (los demás no
    entran en ninguna partición: no hace falta diseñarlos)."""
    before, after = start, count - 1 - end
    for k in range(groups):  # k tramos antes y groups − 1 − k después, cada uno con al menos un elemento
        rest = groups - 1 - k
        if (k == 0) == (before == 0) and k <= before and (rest == 0) == (after == 0) and rest <= after:
            return True
    return False


def _for_fc(ctx: Context, fc: float, run: Runner) -> tuple[float, list[tuple[GroupDesign, list[DesignColumn]]]] | str:
    columns = ctx.project.columns
    designs = run([("single", fc, index) for index in range(len(columns))])
    singles: dict[str, GroupDesign] = {}
    for column, single in zip(columns, designs, strict=True):
        if single is None:
            return f"f'c = {fc:g} MPa: la columna {column.id} no tiene zapata dentro de los límites"
        singles[column.id] = single
    position = {column.id: index for index, column in enumerate(columns)}
    ordered = sorted(columns, key=lambda column: (singles[column.id].cost, column.id))
    count, groups = len(ordered), ctx.design.typologies
    segments = [(start, end) for end in range(count) for start in range(end + 1) if _usable(start, end, count, groups)]

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
    tasks = [("design", fc, tuple(position[column.id] for column in ordered[start : end + 1]),
              _largest(singles, ordered[start : end + 1])) for start, end in pending]
    table.update(zip(pending, run(tasks), strict=True))

    def cost(start: int, end: int) -> float:
        result = table.get((start, end))
        return math.inf if result is None else result.cost

    total, chosen_segments = partition(count, groups, cost)
    if not chosen_segments:
        return f"f'c = {fc:g} MPa: no hay {groups} tipologías que cubran todas las columnas"
    chosen = []
    for start, end in chosen_segments:
        result = table[(start, end)]
        assert result is not None
        chosen.append((result, list(ordered[start : end + 1])))
    return total, chosen


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


def _in_pool(pool: Executor, tasks: list[Task], workers: int) -> list[Any]:
    chunk = max(1, len(tasks) // (8 * workers))  # tareas de duración dispar: lotes pequeños reparten mejor la carga
    return list(pool.map(_run_in_worker, tasks, chunksize=chunk))


def _design(ctx: Context, run: Runner) -> DesignResult:
    best: tuple[float, float, list[tuple[GroupDesign, list[DesignColumn]]]] | None = None
    failures = []
    for fc in ctx.design.prices.fc_options:
        outcome = _for_fc(ctx, fc, run)
        if isinstance(outcome, str):
            failures.append(outcome)
            continue
        total, chosen = outcome
        if best is None or total < best[0]:
            best = (total, fc, chosen)
    if best is None:
        return DesignResult(None, (), math.inf, "; ".join(failures))
    total, fc, chosen = best
    chosen.sort(key=lambda item: (item[0].typology.lx * item[0].typology.ly, item[0].typology.h))
    typologies = tuple(TypologyResult(f"Z{index}", design, tuple(column.id for column in columns))
                       for index, (design, columns) in enumerate(chosen, start=1))
    return DesignResult(fc, typologies, total)


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
                "loads": [_load_input(load) for load in column.loads],
            })
    materials = project.materials
    return {
        "description": f"{project.description} Diseño por tipologías (D-069): {len(result.typologies)} tipologías, "
                       f"f'c = {result.fc:g} MPa, costo total {result.cost:.2f}.",
        "profile": project.profile,
        "seismic": project.seismic.model_dump(),
        "materials": {"fc": result.fc, "fy": materials.fy, "fyt": materials.fyt, "concrete": materials.concrete},
        "soil": _soil_input(ctx),
        "footings": footings,
    }


def _load_input(load: FootingLoad) -> dict[str, Any]:
    return {"case": load.case, "kind": load.kind, "dead_factor": load.dead_factor, "live_factor": load.live_factor,
            "seismic": load.seismic, "P_kN": load.p / N_PER_KN, "Vx_kN": load.vx / N_PER_KN, "Vy_kN": load.vy / N_PER_KN,
            "Mx_kNm": load.mx / NMM_PER_KNM, "My_kNm": load.my / NMM_PER_KNM}


def _soil_input(ctx: Context) -> dict[str, float]:
    soil = ctx.soil
    return {"allowable_pressure_kPa": soil.allowable_pressure / MPA_PER_KPA, "min_contact_fraction": soil.min_contact_fraction,
            "unit_weight_concrete_kNm3": soil.unit_weight_concrete / N_MM3_PER_KN_M3,
            "unit_weight_fill_kNm3": soil.unit_weight_fill / N_MM3_PER_KN_M3,
            "friction_coefficient": soil.friction_coefficient, "adhesion_kPa": soil.adhesion / MPA_PER_KPA,
            "passive_coefficient": soil.passive_coefficient, "cohesion_kPa": soil.cohesion / MPA_PER_KPA,
            "passive_factor": soil.passive_factor, "sliding_safety_factor": soil.sliding_safety_factor,
            "sliding_safety_factor_seismic": soil.sliding_safety_factor_seismic,
            "overturning_safety_factor": soil.overturning_safety_factor,
            "overturning_safety_factor_seismic": soil.overturning_safety_factor_seismic}
