"""Medición del diseño por tipologías (etapa E0 de docs/planes/plan-tipologias.md); no cambia el resultado.

Corre el mismo `_design` de typologies con un ejecutor que cronometra cada tarea (también dentro de los procesos) y anota
cuándo empieza y termina cada lote. Por cada f'c, `_for_fc` lanza tres lotes en orden (`single`, `covers`, `design`); el
tiempo entre lotes es trabajo del proceso principal: orden y tramos, costeo de los tramos cubiertos y partición. Después
analiza la solución sin modificarla: muestra de la matriz de cobertura, tipologías repetidas y columnas que otra
tipología elegida cubriría más barato.

Con milp_iter (E3b, D-077) los lotes no siguen ese orden: cada uno se registra por el tipo de sus tareas (single, design,
covers, refine) y por f'c se resume el tiempo de cada tipo, junto con las iteraciones del resultado.
"""

import random
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from structurelab_rc.design.footing import typologies
from structurelab_rc.design.footing.typologies import DesignResult, Task, _design, _run, _start_worker
from structurelab_rc.design.footing.typology import (
    _DOWEL_PREFIX,
    Context,
    GroupDesign,
    Typology,
    _dowel_options,
    _failures,
    _soil_ok,
    checks_for,
    covers,
    priced,
    typology_key,
)
from structurelab_rc.model.design import DesignColumn

SAMPLE_PAIRS = 500
SAMPLE_SEED = 20261109
# Orden de los lotes de _for_fc; un lote vacío, y el de coberturas de la reasignación (D-074), se identifican por él.
_NEXT = {"single": "covers", "covers": "design", "design": "reassign"}
Timed = Callable[[list[Task]], list[tuple[float, Any]]]


def _pair(ctx: Context, typology: Typology, index: int) -> dict[str, Any]:
    """Un par columna–candidato: tiempo de la revisión de suelo, tiempo de covers() y opciones de pasadores probadas."""
    column = ctx.project.columns[index]
    start = time.perf_counter()
    soil = _soil_ok(ctx, [column], typology)
    soil_s = time.perf_counter() - start
    start = time.perf_counter()
    covered = covers(ctx, typology, column) is not None
    covers_s = time.perf_counter() - start
    tried = 0
    for dowels in _dowel_options(ctx, typology, column):  # el recorrido de column_checks, solo para contar las opciones
        tried += 1
        if not any(failure.name.startswith(_DOWEL_PREFIX) for failure in _failures(checks_for(ctx, typology, column, dowels))):
            break
    return {"soil_ok": soil, "covered": covered, "soil_s": soil_s, "covers_s": covers_s, "dowel_options": tried}


def _timed(ctx: Context, task: Task) -> tuple[float, Any]:
    start = time.perf_counter()
    result = _pair(ctx, task[1], task[2]) if task[0] == "pair" else _run(ctx, task)
    return time.perf_counter() - start, result


def _timed_in_worker(task: Task) -> tuple[float, Any]:
    assert typologies._WORKER is not None
    return _timed(typologies._WORKER, task)


def profile_typologies(ctx: Context, workers: int = 1) -> tuple[DesignResult, dict[str, Any]]:
    """El resultado de design_typologies (el mismo) y la medición; workers como en design_typologies."""
    if workers <= 1:
        return _profile(ctx, lambda tasks: [_timed(ctx, task) for task in tasks], workers)
    with ProcessPoolExecutor(workers, initializer=_start_worker, initargs=(ctx.project, tuple(ctx.bars))) as pool:
        def execute(tasks: list[Task]) -> list[tuple[float, Any]]:
            chunk = max(1, len(tasks) // (8 * workers))  # el mismo reparto que typologies._in_pool
            return list(pool.map(_timed_in_worker, tasks, chunksize=chunk))
        return _profile(ctx, execute, workers)


def _profile(ctx: Context, execute: Timed, workers: int) -> tuple[DesignResult, dict[str, Any]]:
    batches: list[dict[str, Any]] = []

    iterative = ctx.design.method == "milp_iter"

    def run(tasks: list[Task]) -> list[Any]:
        start = time.perf_counter()
        timed = execute(tasks)
        end = time.perf_counter()
        if iterative:  # por el tipo de sus tareas; un lote vacío no se registra
            if tasks:
                kind = tasks[0][0]
                fc = tasks[0][1].fc if kind == "covers" else tasks[0][1]
                batches.append({"kind": kind, "fc": fc, "start": start, "end": end, "times": [t for t, _ in timed],
                                "results": [result for _, result in timed]})
            return [result for _, result in timed]
        if tasks:
            kind = tasks[0][0]
            fc = tasks[0][1].fc if kind == "covers" else tasks[0][1]
            if kind == "covers" and batches[-1]["kind"] in ("design", "reassign"):
                kind = "reassign" if batches[-1]["kind"] == "design" else "matrix"  # matriz del MILP (E2)
        else:
            kind, fc = _NEXT[batches[-1]["kind"]], batches[-1]["fc"]
        batches.append({"kind": kind, "fc": fc, "start": start, "end": end, "times": [t for t, _ in timed],
                        "results": [result for _, result in timed]})
        return [result for _, result in timed]

    start = time.perf_counter()
    result = _design(ctx, run)
    end = time.perf_counter()
    stages = _iterative_stages if iterative else _fc_stages
    by_fc = [stages(ctx, fc, batches, end) for fc in sorted(ctx.design.fc_options)]
    if iterative:
        options = {option.fc: option for option in result.options}
        for stage in by_fc:
            option = options.get(stage["fc"])
            stage["iterations"] = [] if option is None else [
                {"number": step.number, "candidates": step.candidates, "cost": step.cost, "status": step.status,
                 "seconds": step.seconds} for step in option.iterations]
    for stage in by_fc:
        stage["sample"] = _sample(ctx, stage.pop("candidates"), execute, workers, end - start)
    measurement = {"workers": workers, "design_s": end - start, "fc": by_fc, "solution": _solution(ctx, result, execute)}
    return result, measurement


def _summary(times: Sequence[float], batch: dict[str, Any] | None) -> dict[str, Any]:
    return {"count": len(times), "sum_s": sum(times), "mean_s": sum(times) / len(times) if times else 0.0,
            "max_s": max(times, default=0.0), "batch_s": 0.0 if batch is None else batch["end"] - batch["start"]}


def _fc_stages(ctx: Context, fc: float, batches: list[dict[str, Any]], end: float) -> dict[str, Any]:
    own = {batch["kind"]: batch for batch in batches if batch["fc"] == fc}
    after = [batch["start"] for batch in batches if batch["start"] > own["single"]["end"] and batch["fc"] != fc]
    single, covered, design, moved = own["single"], own.get("covers"), own.get("design"), own.get("reassign")
    matrix = own.get("matrix")
    next_start = min(after, default=end)  # comienzo del f'c siguiente (o fin del diseño)
    count, groups = len(ctx.project.columns), ctx.design.typologies
    stage: dict[str, Any] = {"fc": fc, "columns": count, "typologies": groups,
                             "single": _summary(single["times"], single)}
    if covered is None or design is None:
        stage.update(failure="hay columnas sin zapata dentro de los límites", candidates=[])
        return stage
    segments = count * (count + 1) // 2  # la tabla de tramos no depende de N (E2)
    stage.update(
        covers={**_summary(covered["times"], covered), "not_covered": sum(r is None for r in covered["results"])},
        design={**_summary(design["times"], design), "infeasible": sum(r is None for r in design["results"])},
        segments=segments, covered_segments=segments - len(design["results"]), redesigned_segments=len(design["results"]),
        reassign=_summary([] if moved is None else moved["times"], moved),
        main_s={"order_and_segments": covered["start"] - single["end"], "priced_segments": design["start"] - covered["end"],
                "partition": (min(after, default=end) if moved is None else moved["start"]) - design["end"],
                "reassign_pricing": 0.0 if moved is None else (next_start if matrix is None else matrix["start"]) - moved["end"],
                "milp_solver": 0.0 if matrix is None else next_start - matrix["end"]},
        matrix=_summary([] if matrix is None else matrix["times"], matrix),
        candidates=[r.typology for r in (*single["results"], *design["results"]) if r is not None])
    return stage


def _iterative_stages(ctx: Context, fc: float, batches: list[dict[str, Any]], end: float) -> dict[str, Any]:
    """milp_iter: por tipo de tarea (single: diseños individuales; design: diseño de todas las columnas y repartos de
    pares; refine: grupos propuestos y finales con el barrido; covers: cobertura de los candidatos nuevos), la suma de
    tiempos y el tiempo de pared de sus lotes; el resto del tiempo del f'c es del proceso principal (MILP y costeo)."""
    own = [batch for batch in batches if batch["fc"] == fc]
    stage: dict[str, Any] = {"fc": fc, "columns": len(ctx.project.columns), "typologies": ctx.design.typologies}
    if not own:
        stage.update(failure="sin lotes medidos", candidates=[])
        return stage
    for kind in ("single", "design", "covers", "refine"):
        mine = [batch for batch in own if batch["kind"] == kind]
        times = [t for batch in mine for t in batch["times"]]
        stage[kind] = {"batches": len(mine), "count": len(times), "sum_s": sum(times), "max_s": max(times, default=0.0),
                       "batch_s": sum(batch["end"] - batch["start"] for batch in mine)}
    later = [batch["start"] for batch in batches if batch["start"] > own[-1]["end"]]
    wall = min(later, default=end) - own[0]["start"]
    stage["wall_s"] = wall
    stage["main_s"] = wall - sum(stage[kind]["batch_s"] for kind in ("single", "design", "covers", "refine"))
    stage["candidates"] = [result.typology for batch in own if batch["kind"] in ("single", "design", "refine")
                           for result in batch["results"] if result is not None]
    return stage


def _sample(ctx: Context, raw: list[Typology], execute: Timed, workers: int, design_s: float) -> dict[str, Any]:
    """Muestra fija de pares columna–candidato del catálogo sin repetidas y extrapolación a la matriz completa."""
    candidates = list({typology_key(typology): typology for typology in raw}.values())
    columns = len(ctx.project.columns)
    full = len(candidates) * columns
    if not full:
        return {}
    picked = sorted(random.Random(SAMPLE_SEED).sample(range(full), min(SAMPLE_PAIRS, full)))
    start = time.perf_counter()
    pairs = [result for _, result in execute([("pair", candidates[i // columns], i % columns) for i in picked])]
    elapsed = time.perf_counter() - start
    covers_s = [pair["covers_s"] for pair in pairs]
    mean = sum(covers_s) / len(pairs)
    return {
        "seed": SAMPLE_SEED, "candidates_raw": len(raw), "candidates": len(candidates), "pairs_full": full,
        "pairs_sampled": len(pairs), "sample_wall_s": elapsed,
        "covers_mean_s": mean, "covers_max_s": max(covers_s), "covers_min_s": min(covers_s),
        "soil_mean_s": sum(pair["soil_s"] for pair in pairs) / len(pairs),
        "covered_fraction": sum(pair["covered"] for pair in pairs) / len(pairs),
        "soil_reject_fraction": sum(not pair["soil_ok"] for pair in pairs) / len(pairs),
        "soil_rejects_but_covers": sum(pair["covered"] and not pair["soil_ok"] for pair in pairs),
        "dowel_options_mean": sum(pair["dowel_options"] for pair in pairs) / len(pairs),
        "dowel_options_max": max(pair["dowel_options"] for pair in pairs),
        "estimate_serial_s": full * mean, "estimate_parallel_s": full * mean / max(workers, 1),
        "estimate_over_design": full * mean / max(workers, 1) / design_s,
    }


def _solution(ctx: Context, result: DesignResult, execute: Timed) -> dict[str, Any]:
    """Repetidas y columnas reasignables de la solución elegida (solo se cuentan)."""
    if result.fc is None:
        return {}
    keys = [typology_key(item.design.typology) for item in result.typologies]
    position = {column.id: index for index, column in enumerate(ctx.project.columns)}
    owner = {column_id: item for item in result.typologies for column_id in item.columns}
    tasks = [("covers", item.design.typology, position[column_id]) for column_id in owner for item in result.typologies
             if item is not owner[column_id]]
    start = time.perf_counter()
    dowels = iter(result for _, result in execute(tasks))
    elapsed = time.perf_counter() - start
    moves = []
    for column_id, origin in owner.items():
        column = ctx.project.columns[position[column_id]]
        current = _column_cost(ctx, origin.design, column_id, origin.design.dowels[column_id], column)
        best: tuple[float, str] | None = None
        for item in result.typologies:
            if item is origin:
                continue
            found = next(dowels)
            if found is not None:
                cost = _column_cost(ctx, item.design, column_id, found, column)
                if cost < current and (best is None or cost < best[0]):
                    best = (cost, item.name)
        if best is not None:
            moves.append({"column": column_id, "from": origin.name, "to": best[1], "saving": current - best[0]})
    sizes = {item.name: len(item.columns) for item in result.typologies}
    return {"fc": result.fc, "typologies": len(keys), "cost": result.cost, "repeated": len(keys) - len(set(keys)),
            "covers_checked": len(tasks), "covers_wall_s": elapsed, "reassignable": len(moves),
            "saving_if_each_moves": sum(move["saving"] for move in moves),
            "emptied_typologies": sorted(name for name, size in sizes.items()
                                         if size == sum(move["from"] == name for move in moves)),
            "moves": moves}


def _column_cost(ctx: Context, design: GroupDesign, column_id: str, dowels: dict[str, Any], column: DesignColumn) -> float:
    return priced(ctx, design.typology, [column], {column_id: dowels}).cost
