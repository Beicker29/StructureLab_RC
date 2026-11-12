"""Estribos candidatos (v3 Fase 3A, D-110): pieza neutra del diseño, sin fórmulas propias, que usa la viga larga de la
zapata combinada y, más adelante, las vigas.

Propone estribos cerrados (designación, número de ramas y separación) de menor a mayor peso por unidad de largo del
miembro: ramas en número par a lo ancho y separaciones múltiplo del paso entre la máxima que dé el perfil y la mínima de
la constructibilidad. La verificación (cortante, Av,min, separaciones y torsión de vigas) decide cuál cumple.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from structurelab_rc.model.catalog import RebarSpec

MIN_SPACING = 75.0  # mm: separación mínima de estribos que se propone
MIN_LEG_GAP = 100.0  # mm: separación mínima entre ramas a lo ancho que se propone


@dataclass(frozen=True)
class StirrupFrame:
    """Sección donde van los estribos: ancho y alto (mm), recubrimiento (mm), paso de la separación (mm) y separación
    máxima a lo largo (mm, la del perfil)."""

    width: float
    h: float
    cover: float
    step: float
    max_spacing: float


def stirrup_options(specs: Sequence[RebarSpec], frame: StirrupFrame) -> list[dict[str, Any]]:
    """Estribos cerrados de menor a mayor peso por metro de miembro (kg/m): dos ramas verticales por estribo y ramas
    intermedias hasta que la separación entre ramas no baje de MIN_LEG_GAP. _mass es el peso, _area el Av/s (mm²/mm),
    _leg el área de una rama sobre la separación (la rama exterior de torsión), _legs las ramas y _spacing la separación,
    para que quien diseña compare las fallas."""
    inner_width = frame.width - 2 * frame.cover
    inner_height = frame.h - 2 * frame.cover
    most = max(2, 2 * math.floor((math.floor(inner_width / MIN_LEG_GAP) + 1) / 2))
    top = math.floor(frame.max_spacing / frame.step) * frame.step
    options = []
    for spec in specs:
        for legs in range(2, most + 1, 2):
            length = legs * inner_height + 2 * inner_width  # ramas verticales y el cierre a lo ancho, mm
            spacing = top
            while spacing >= MIN_SPACING - 1e-9:
                options.append({"designation": spec.designation, "legs": legs, "spacing": spacing, "closed": True,
                                "_mass": length / 1000 * spec.mass_kg_m / (spacing / 1000), "_area": legs * spec.area_mm2 / spacing,
                                "_per_m": legs * spec.area_mm2 / spacing, "_diameter": spec.diameter_mm, "_clear": spacing,
                                "_spacing": spacing, "_legs": legs, "_leg": spec.area_mm2 / spacing})
                spacing -= frame.step
    return sorted(options, key=lambda option: option["_mass"])
