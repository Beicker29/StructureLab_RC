"""Diseño por tipologías con zapatas combinadas (D-153, enfoque 2 de D-109): los pares de columnas declarados en la
plantilla van cada uno en su zapata combinada, diseñada con el diseño de la combinada (D-107, D-110, D-113), y el resto
por tipologías aisladas (D-069). Un solo f'c para toda la cimentación: cada combinada se diseña en todos los f'c y el
diseño por tipologías elige el f'c de menor costo total (aisladas más combinadas). No hay fórmulas nuevas: solo orquesta.
"""

import math
from dataclasses import dataclass, replace
from typing import Any

from structurelab_rc.design.footing import combined
from structurelab_rc.design.footing.typologies import DesignResult, design_typologies, designed_project
from structurelab_rc.design.footing.typology import Context
from structurelab_rc.model.design import DesignPair, pair_project


@dataclass(frozen=True)
class PairDesign:
    """Una zapata combinada del diseño por tipologías: su par, el contexto y el resultado de su diseño en cada f'c, y la
    solución en el f'c elegido para toda la cimentación (None hasta elegirlo o si no la hay)."""

    pair: DesignPair
    ctx: combined.Context
    result: combined.CombinedDesignResult
    solution: combined.CombinedSolution | None = None

    def at(self, fc: float) -> combined.CombinedSolution | None:
        return next((option.solution for option in self.result.options if option.fc == fc), None)


def design_pairs(ctx: Context, workers: int = 1) -> tuple[PairDesign, ...]:
    """Cada par diseñado con el diseño de la combinada, en todos los f'c (D-153)."""
    designs = []
    for pair in ctx.project.combined_footings:
        own = combined.Context(pair_project(ctx.project, pair), ctx.profile, ctx.bars)
        designs.append(PairDesign(pair, own, combined.design_combined(own, workers)))
    return tuple(designs)


def pair_costs(pairs: tuple[PairDesign, ...], fc_options: tuple[float, ...]) -> dict[float, float]:
    """El costo de las combinadas en cada f'c; infinito si alguna no tiene solución con él."""
    costs = {}
    for fc in fc_options:
        solutions = [pair.at(fc) for pair in pairs]
        costs[fc] = math.inf if any(solution is None for solution in solutions) else sum(
            solution.cost for solution in solutions if solution is not None)
    return costs


def design_with_pairs(ctx: Context, workers: int = 1) -> DesignResult:
    """Las tipologías aisladas y las combinadas con un solo f'c, el de menor costo total; el resultado lleva las
    combinadas (combined) y su costo (combined_cost)."""
    pairs = design_pairs(ctx, workers)
    if not pairs:
        return design_typologies(ctx, workers)
    result = design_typologies(ctx, workers, pair_costs(pairs, ctx.design.fc_options))
    if result.fc is None:
        return replace(result, combined=pairs)
    fc = result.fc
    chosen = tuple(replace(pair, solution=pair.at(fc)) for pair in pairs)
    return replace(result, combined=chosen, combined_cost=sum(pair.solution.cost for pair in chosen if pair.solution is not None))


def designed_with_pairs(ctx: Context, result: DesignResult) -> dict[str, Any]:
    """El proyecto de verificación con las zapatas aisladas de las tipologías y cada combinada en el f'c elegido, con la
    ubicación de sus columnas (D-130) para la planta de localización."""
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
        footings.append({**footing, "id": pair.pair.id, "columns": columns})
    total = result.cost + result.combined_cost
    project["description"] += (f" Con {len(pairs)} zapatas combinadas ({', '.join(pair.pair.id for pair in pairs)}, D-153), costo "
                               f"{result.combined_cost:.2f}; costo de la cimentacion {total:.2f} con un solo f'c.")
    project["combined_footings"] = footings
    return project
