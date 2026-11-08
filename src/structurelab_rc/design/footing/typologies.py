"""Diseño de zapatas por tipologías (V3F, D-069): N zapatas tipo que cubren todas las columnas al menor costo.

Para cada f'c comercial con precio: (1) diseño individual de cada columna; (2) columnas ordenadas por el costo de su
diseño; (3) partición en N tramos continuos por programación dinámica, donde el costo de un tramo es el de la tipología
de su columna más exigente si cubre a todas, o el de un diseño del tramo completo si no; (4) se elige el f'c de menor costo
total y cada tipología final se verifica de nuevo con todas sus columnas. Un solo f'c para todas las zapatas (D-069).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Any

from structurelab_rc.design.footing.grouping import partition
from structurelab_rc.design.footing.typology import Context, GroupDesign, Typology, covers, design_group, priced
from structurelab_rc.model.design import DesignColumn
from structurelab_rc.model.footing import MPA_PER_KPA, N_MM3_PER_KN_M3, N_PER_KN, NMM_PER_KNM, FootingLoad


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


def _for_fc(ctx: Context, fc: float) -> tuple[float, list[tuple[GroupDesign, list[DesignColumn]]]] | str:
    columns = ctx.project.columns
    singles = {}
    for column in columns:
        single = design_group(ctx, [column], fc)
        if single is None:
            return f"f'c = {fc:g} MPa: la columna {column.id} no tiene zapata dentro de los límites"
        singles[column.id] = single
    ordered = sorted(columns, key=lambda column: (singles[column.id].cost, column.id))

    @cache
    def covered(typology_owner: int, member: int) -> dict[str, Any] | None:
        """Pasadores con que la tipología individual de typology_owner cubre a member (None si no lo cubre)."""
        if typology_owner == member:
            return singles[ordered[member].id].dowels[ordered[member].id]
        return covers(ctx, singles[ordered[typology_owner].id].typology, ordered[member])

    @cache
    def group(start: int, end: int) -> GroupDesign | None:
        members = ordered[start : end + 1]
        owner = singles[ordered[end].id]
        dowels = {ordered[member].id: covered(end, member) for member in range(start, end + 1)}
        if all(value is not None for value in dowels.values()):
            return priced(ctx, owner.typology, members, {key: value for key, value in dowels.items() if value is not None})
        return design_group(ctx, members, fc, start=_largest(singles, members))

    def cost(start: int, end: int) -> float:
        result = group(start, end)
        return math.inf if result is None else result.cost

    total, segments = partition(len(ordered), ctx.design.typologies, cost)
    if not segments:
        return f"f'c = {fc:g} MPa: no hay {ctx.design.typologies} tipologías que cubran todas las columnas"
    chosen = []
    for start, end in segments:
        result = group(start, end)
        assert result is not None
        chosen.append((result, list(ordered[start : end + 1])))
    return total, chosen


def _largest(singles: dict[str, GroupDesign], members: Sequence[DesignColumn]) -> Typology:
    """Punto de partida de un tramo: la mayor planta y el mayor espesor de sus diseños individuales."""
    typologies = [singles[column.id].typology for column in members]
    widest = max(typologies, key=lambda typology: (typology.lx * typology.ly, typology.h))
    return Typology(widest.fc, max(t.lx for t in typologies), max(t.ly for t in typologies),
                    max(t.h for t in typologies), widest.bottom, widest.top)


def design_typologies(ctx: Context) -> DesignResult:
    best: tuple[float, float, list[tuple[GroupDesign, list[DesignColumn]]]] | None = None
    failures = []
    for fc in ctx.design.prices.fc_options:
        outcome = _for_fc(ctx, fc)
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
            "P_kN": load.p / N_PER_KN, "Vx_kN": load.vx / N_PER_KN, "Vy_kN": load.vy / N_PER_KN, "Mx_kNm": load.mx / NMM_PER_KNM,
            "My_kNm": load.my / NMM_PER_KNM}


def _soil_input(ctx: Context) -> dict[str, float]:
    soil = ctx.soil
    return {"allowable_pressure_kPa": soil.allowable_pressure / MPA_PER_KPA, "min_contact_fraction": soil.min_contact_fraction,
            "unit_weight_concrete_kNm3": soil.unit_weight_concrete / N_MM3_PER_KN_M3,
            "unit_weight_fill_kNm3": soil.unit_weight_fill / N_MM3_PER_KN_M3}
