"""Flexión uniaxial por franjas y capas, resuelta con el motor de sección poligonal (mechanics.section).

Es la forma cómoda de describir una sección rectangular o T con la cara comprimida arriba: franjas de ancho
constante y capas de acero con su profundidad desde la cara comprimida. La carga axial es positiva en compresión
y actúa en el centroide de la sección bruta.
"""

import math
from dataclasses import dataclass

from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel
from structurelab_rc.mechanics.polygon import Point
from structurelab_rc.mechanics.roots import find_root
from structurelab_rc.mechanics.section import SteelPoint, section_state


@dataclass(frozen=True)
class CompressionStrip:
    """Franja de ancho constante, con distancias medidas desde la cara comprimida."""

    width: float
    start: float
    end: float


@dataclass(frozen=True)
class SteelLayer:
    """Capa de acero, con la profundidad medida desde la cara comprimida."""

    depth: float
    area: float


@dataclass(frozen=True)
class LayerState:
    depth: float
    area: float
    strain: float
    stress: float


@dataclass(frozen=True)
class FlexureState:
    """Las deformaciones y esfuerzos del acero son positivos en tracción; el momento es respecto al centroide."""

    c: float
    a: float
    extreme_strain: float
    nominal_moment: float
    layers: tuple[LayerState, ...]


def compression_strips(bw: float, h: float, bf: float, hf: float, *, flange_in_compression: bool) -> tuple[CompressionStrip, ...]:
    """Franjas de una sección T; una sección rectangular es el caso bf = bw."""
    if flange_in_compression:
        return (CompressionStrip(bf, 0.0, hf), CompressionStrip(bw, hf, h))
    return (CompressionStrip(bw, 0.0, h - hf), CompressionStrip(bf, h - hf, h))


def _polygon(strips: tuple[CompressionStrip, ...]) -> tuple[Point, ...]:
    """Contorno de las franjas apiladas y centradas en x = 0, con la cara comprimida en y = altura total."""
    height = strips[-1].end
    right = [point for strip in strips for point in ((strip.width / 2, height - strip.start), (strip.width / 2, height - strip.end))]
    return (*right, *((-x, y) for x, y in reversed(right)))


def flexure_state(
    strips: tuple[CompressionStrip, ...],
    layers: tuple[SteelLayer, ...],
    concrete: ConcreteBlock,
    steel: SteelModel,
    axial: float = 0.0,
) -> FlexureState:
    height = strips[-1].end
    points = tuple(SteelPoint(0.0, height - layer.depth, layer.area) for layer in layers)
    state = section_state(_polygon(strips), points, (concrete, steel), axial, math.pi / 2)
    return FlexureState(
        c=state.c,
        a=state.a,
        extreme_strain=state.extreme_strain,
        nominal_moment=state.mn3,
        layers=tuple(LayerState(bar.depth, bar.area, bar.strain, bar.stress) for bar in state.bars),
    )


def cracked_steel_stress(moment: float, strips: tuple[CompressionStrip, ...], layers: tuple[SteelLayer, ...],
                         modular_ratio: float) -> float:
    """Esfuerzo de la capa de acero más alejada de la cara comprimida en la sección fisurada elástica (concreto lineal
    sin tracción, acero transformado n·As). Solo cuentan las capas en tracción; el acero comprimido se desprecia, del lado
    de la seguridad. El eje neutro c iguala el momento estático del concreto comprimido al del acero en tracción;
    Icr = Σ b·[(c − y0)³ − (c − y1)³]/3 + n·Σ As·(d − c)² y fs = n·M·(d_max − c)/Icr. Con una sección rectangular y una
    capa es fs = M/(As·j·d), con j = 1 − k/3. Distancias desde la cara comprimida; en N, mm y MPa."""

    def compressed(c: float) -> list[tuple[float, float, float]]:
        return [(strip.width, strip.start, min(c, strip.end)) for strip in strips if strip.start < c]

    def balance(c: float) -> float:
        concrete = sum(width * (top - start) * (c - (start + top) / 2) for width, start, top in compressed(c))
        steel = modular_ratio * sum(layer.area * (layer.depth - c) for layer in layers if layer.depth > c)
        return concrete - steel

    deepest = max(layer.depth for layer in layers)
    c = find_root(balance, (0.0, deepest), (balance(0.0), balance(deepest)), lambda _: deepest * 1e-13)
    inertia = (sum(width * ((c - start) ** 3 - (c - top) ** 3) / 3 for width, start, top in compressed(c))
               + modular_ratio * sum(layer.area * (layer.depth - c) ** 2 for layer in layers if layer.depth > c))
    return modular_ratio * moment * (deepest - c) / inertia
