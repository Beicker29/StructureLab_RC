"""Barras para un acero requerido (v3 Fase 3A, D-107): pieza neutra del diseño, sin fórmulas propias, que comparten el
diseño de la zapata aislada (D-069), el de la combinada y, más adelante, el de las vigas.

Para cada designación, el As requerido sale de `domain/flexure_strength.required_area` (el del perfil, con φ y el
bloque de Whitney) y se lleva al mínimo que pida quien diseña; las barras se reparten en el ancho útil (ancho menos los
recubrimientos y una barra) a una separación múltiplo del paso, sin pasar de la máxima. Las opciones van de menor a
mayor peso; la verificación decide cuál cumple.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from structurelab_rc.codes.registry import Profile
from structurelab_rc.domain.flexure_strength import RectangularSection, required_area
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Materials


@dataclass(frozen=True)
class Spread:
    """Cómo se reparten las barras en una dirección: ancho (mm) y espesor (mm) de la sección, recubrimiento lateral (mm),
    paso de la separación (mm) y separación máxima (mm)."""

    width: float
    h: float
    cover: float
    step: float
    max_spacing: float


def bar_count(spread: Spread, diameter: float, spacing: float) -> int:
    """Barras a la separación dada en el ancho útil (las de los extremos al recubrimiento)."""
    return math.floor((spread.width - 2 * spread.cover - diameter) / spacing + 1e-6) + 1


def bar_options(
    given: tuple[Profile, Materials, Sequence[RebarSpec]], spread: Spread, depth_of: Callable[[float], float],
    demand: tuple[float, float], limit: int | None = None,
) -> list[tuple[float, dict[str, Any]]]:
    """Opciones de barras (designación y separación) con su peso por metro de barra en todo el ancho (kg/m), ordenadas
    por peso: para cada designación de given, la separación que da max(As requerido, As mínimo) y las menores, hasta que
    la luz libre no pase de un paso. demand es (Mu en N·mm, As mínimo en mm²); depth_of da la altura efectiva con el
    diámetro de la barra. Una designación cuya altura no alcanza el momento con ninguna cuantía se omite. limit corta la
    lista, como en el diseño por tipologías."""
    profile, materials, specs = given
    moment, min_area = demand
    options: list[tuple[float, dict[str, Any]]] = []
    for spec in specs:
        needed = required_area(profile, materials, RectangularSection(spread.width, spread.h), depth_of(spec.diameter_mm), moment)
        if needed is None:  # ninguna cuantía alcanza el momento con esta altura
            continue
        count = max(math.ceil(max(needed, min_area) / spec.area_mm2), 2)
        usable = spread.width - 2 * spread.cover - spec.diameter_mm
        spacing = min(math.floor(usable / (count - 1) / spread.step) * spread.step, spread.max_spacing)
        while spacing > spec.diameter_mm + spread.step / 2:
            options.append((bar_count(spread, spec.diameter_mm, spacing) * spec.mass_kg_m,
                            {"designation": spec.designation, "spacing": spacing}))
            spacing -= spread.step
            if limit is not None and len(options) > limit:
                break
    return sorted(options, key=lambda option: option[0])
