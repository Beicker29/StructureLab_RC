"""Equilibrio y compatibilidad de deformaciones a flexión con carga axial, en N, mm y MPa.

La carga axial es positiva en compresión y actúa en el centroide de la sección bruta.
"""

import math
from dataclasses import dataclass

_BISECTION_STEPS = 100


class NoEquilibrium(ValueError):
    """La sección no puede equilibrar la carga axial."""


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
class ConcreteBlock:
    fc: float
    stress_factor: float
    beta1: float
    max_strain: float


@dataclass(frozen=True)
class SteelModel:
    fy: float
    modulus: float


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


def _block(strips: tuple[CompressionStrip, ...], a: float) -> tuple[float, float]:
    """Área del bloque de profundidad a y su primer momento respecto a la cara comprimida."""
    area = moment = 0.0
    for strip in strips:
        end = min(a, strip.end)
        if end <= strip.start:
            break
        part = strip.width * (end - strip.start)
        area += part
        moment += part * (strip.start + end) / 2
    return area, moment


def _layer_state(layer: SteelLayer, c: float, concrete: ConcreteBlock, steel: SteelModel) -> LayerState:
    strain = concrete.max_strain * (layer.depth - c) / c
    stress = math.copysign(min(abs(steel.modulus * strain), steel.fy), strain)
    return LayerState(layer.depth, layer.area, strain, stress)


def _layer_force(layer: SteelLayer, c: float, concrete: ConcreteBlock, steel: SteelModel) -> float:
    """Fuerza neta en tracción; una capa dentro del bloque descuenta el concreto que desplaza."""
    stress = _layer_state(layer, c, concrete, steel).stress
    displaced = concrete.stress_factor * concrete.fc if layer.depth < concrete.beta1 * c else 0.0
    return layer.area * (stress + displaced)


def _section_forces(
    strips: tuple[CompressionStrip, ...], layers: tuple[SteelLayer, ...], c: float, concrete: ConcreteBlock, steel: SteelModel
) -> float:
    """Compresión del concreto menos la fuerza neta del acero: es cero en equilibrio."""
    area, _ = _block(strips, concrete.beta1 * c)
    block_force = concrete.stress_factor * concrete.fc * area
    return block_force - sum(_layer_force(layer, c, concrete, steel) for layer in layers)


def _neutral_axis(
    strips: tuple[CompressionStrip, ...], layers: tuple[SteelLayer, ...], concrete: ConcreteBlock, steel: SteelModel, axial: float
) -> float:
    """Menor raíz del equilibrio; la fuerza salta hacia abajo cuando el bloque alcanza una capa."""

    def residual(c: float) -> float:
        return _section_forces(strips, layers, c, concrete, steel) - axial

    deepest = max(strips[-1].end, *(layer.depth for layer in layers))
    ceiling = 2 * deepest / concrete.beta1
    jumps = sorted({layer.depth / concrete.beta1 for layer in layers if layer.depth / concrete.beta1 < ceiling})
    low = ceiling * 1e-9
    if residual(low) >= 0:
        raise NoEquilibrium("la tracción axial supera la capacidad del acero")
    for high in (*jumps, ceiling):
        if residual(high * (1 - 1e-12)) >= 0:
            break
        low = high * (1 + 1e-12)
    else:
        raise NoEquilibrium("la compresión axial supera la capacidad de la sección")
    high = high * (1 - 1e-12)
    for _ in range(_BISECTION_STEPS):
        middle = (low + high) / 2
        if residual(middle) >= 0:
            high = middle
        else:
            low = middle
    return (low + high) / 2


def gross_centroid(strips: tuple[CompressionStrip, ...]) -> float:
    """Profundidad del centroide de la sección bruta, medida desde la cara comprimida."""
    area, moment = _block(strips, strips[-1].end)
    return moment / area


def flexure_state(
    strips: tuple[CompressionStrip, ...],
    layers: tuple[SteelLayer, ...],
    concrete: ConcreteBlock,
    steel: SteelModel,
    axial: float = 0.0,
) -> FlexureState:
    if not layers:
        raise ValueError("la sección no tiene acero")
    c = _neutral_axis(strips, layers, concrete, steel, axial)
    a = concrete.beta1 * c
    _, block_moment = _block(strips, a)
    steel_moment = sum(_layer_force(layer, c, concrete, steel) * layer.depth for layer in layers)
    face_moment = steel_moment - concrete.stress_factor * concrete.fc * block_moment
    return FlexureState(
        c=c,
        a=a,
        extreme_strain=_layer_state(max(layers, key=lambda layer: layer.depth), c, concrete, steel).strain,
        # Trasladar el momento de la cara comprimida al centroide suma la carga axial por su brazo.
        nominal_moment=face_moment + axial * gross_centroid(strips),
        layers=tuple(_layer_state(layer, c, concrete, steel) for layer in layers),
    )
