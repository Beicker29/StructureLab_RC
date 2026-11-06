"""Flexión uniaxial por franjas y capas, resuelta con el motor de sección poligonal (mechanics.section).

Es la forma cómoda de describir una sección rectangular o T con la cara comprimida arriba: franjas de ancho
constante y capas de acero con su profundidad desde la cara comprimida. La carga axial es positiva en compresión
y actúa en el centroide de la sección bruta.
"""

import math
from dataclasses import dataclass

from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel
from structurelab_rc.mechanics.section import Point, SteelPoint, section_state


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
