"""Asignación de columnas a N tipologías distintas de un catálogo por programación entera (MILP, E2, D-075).

    min  Σ_i Σ_j c_ij · x_ij
    s.a. Σ_j x_ij = 1  ∀ i;   x_ij ≤ y_j  ∀ i, j;   Σ_i x_ij ≥ y_j  ∀ j;   Σ_j y_j = N;
         x_ij = 0 si j no cubre a i;   x, y binarias.

Desempate en tres pasos, cada uno con brecha 0: el menor costo; con ese costo fijo, el menor peso de acero; con los dos
fijos, el orden del catálogo (Σ j · x_ij). Costos y acero llegan como enteros (pesos y gramos), así que fijar un paso es
exacto. Un hilo y semilla fija: el mismo resultado en cada corrida. highspy es un extra opcional (structurelab-rc[opt]).
"""

import importlib.util
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

OPTIMAL = "optimal"  # óptimo certificado en el catálogo
TIME_LIMIT = "time_limit"  # con solución, sin certificar
INFEASIBLE = "infeasible"  # sin solución (o sin solución dentro del límite de tiempo)
_SEED = 20261109
_FEASIBLE = 2  # HighsSolutionStatus.kSolutionStatusFeasible
_HALF = 0.5


@dataclass(frozen=True)
class Assignment:
    status: str
    choice: tuple[int, ...]  # candidato de cada columna; vacío si no hay solución
    cost: int
    seconds: float


def available() -> bool:
    """Si está instalado highspy (structurelab-rc[opt])."""
    return importlib.util.find_spec("highspy") is not None


def assign(
    cost: Sequence[Sequence[int | None]], steel: Sequence[Sequence[int | None]], groups: int, start: Sequence[int] | None,
    time_limit: float,
) -> Assignment:
    """cost[i][j] y steel[i][j]: costo (entero) y acero (entero) de la columna i con el candidato j, None si j no la cubre.
    start: un candidato por columna para arrancar (debe ser factible), o None."""
    import highspy  # extra opcional (trae numpy): solo se importa al usarlo
    import numpy as np

    begin = time.perf_counter()
    deadline = begin + time_limit
    candidates = len(cost[0]) if cost else 0
    priced = [(i, j, value, steel[i][j] or 0) for i, row in enumerate(cost) for j, value in enumerate(row) if value is not None]
    pairs = [(i, j) for i, j, _, _ in priced]
    y0 = len(pairs)
    h = highspy.Highs()
    for option, value in (("output_flag", False), ("threads", 1), ("random_seed", _SEED), ("mip_rel_gap", 0.0),
                          ("mip_abs_gap", 0.0)):
        h.setOptionValue(option, value)
    count = y0 + candidates
    h.addVars(count, [0.0] * count, [1.0] * count)
    integer = np.full(count, int(highspy.HighsVarType.kInteger), dtype=np.uint8)
    h.changeColsIntegrality(count, np.arange(count, dtype=np.int32), integer)
    inf = highspy.kHighsInf
    for i in range(len(cost)):  # cada columna, una tipología
        own = [k for k, (row, _) in enumerate(pairs) if row == i]
        h.addRow(1.0, 1.0, len(own), own, [1.0] * len(own))
    for k, (_, j) in enumerate(pairs):  # solo tipologías elegidas
        h.addRow(-inf, 0.0, 2, [k, y0 + j], [1.0, -1.0])
    for j in range(candidates):  # cada tipología elegida tiene al menos una columna
        used = [k for k, (_, column) in enumerate(pairs) if column == j]
        h.addRow(0.0, inf, len(used) + 1, [*used, y0 + j], [*([1.0] * len(used)), -1.0])
    h.addRow(groups, groups, candidates, [y0 + j for j in range(candidates)], [1.0] * candidates)  # exactamente N

    values: list[float] | None = None
    if start is not None:
        values = [1.0 if start[i] == j else 0.0 for i, j in pairs] + [1.0 if j in set(start) else 0.0 for j in range(candidates)]
    objectives = ([float(c) for _, _, c, _ in priced], [float(s) for _, _, _, s in priced], [float(j) for _, j in pairs])
    status, best = INFEASIBLE, None
    for stage, objective in enumerate(objectives):
        outcome, found = _solve(h, objective + [0.0] * candidates, values, deadline)
        if found is None:  # en un desempate se conserva la solución del paso anterior
            status = outcome if stage == 0 else status
            break
        best = values = found
        status = outcome if stage == 0 else status
        if outcome != OPTIMAL:
            break  # un paso de desempate solo sigue a un óptimo certificado
        fixed = round(sum(weight * value for weight, value in zip(objective, found[:y0], strict=True)))
        h.addRow(-inf, float(fixed), y0, list(range(y0)), objective)  # fija el paso: el siguiente no lo empeora
    seconds = time.perf_counter() - begin
    if best is None:
        return Assignment(status, (), 0, seconds)
    choice = [0] * len(cost)
    for (i, j), value in zip(pairs, best[:y0], strict=True):
        if value > _HALF:  # variable binaria
            choice[i] = j
    return Assignment(status, tuple(choice), sum(cost[i][j] or 0 for i, j in enumerate(choice)), seconds)


def _solve(h: Any, objective: list[float], start: list[float] | None, deadline: float) -> tuple[str, list[float] | None]:
    """Un paso: objective tiene un costo por variable (x y luego y); start, una solución factible para arrancar."""
    import highspy

    count = h.getNumCol()
    h.changeColsCost(count, list(range(count)), objective)
    h.setOptionValue("time_limit", max(deadline - time.perf_counter(), 0.01))
    if start is not None:
        solution = highspy.HighsSolution()
        solution.col_value = start
        h.setSolution(solution)
    h.run()
    model = h.getModelStatus()
    if model == highspy.HighsModelStatus.kInfeasible:
        return INFEASIBLE, None
    if h.getInfo().primal_solution_status != _FEASIBLE:
        return TIME_LIMIT, None
    values = list(h.getSolution().col_value)
    return (OPTIMAL if model == highspy.HighsModelStatus.kOptimal else TIME_LIMIT), values
