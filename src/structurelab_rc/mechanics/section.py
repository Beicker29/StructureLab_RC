"""Equilibrio y compatibilidad de una sección poligonal con eje neutro de cualquier inclinación, en N, mm y MPa.

Coordenadas de la sección: x sobre el eje 3 y y sobre el eje 2 (hacia arriba). La compresión se mide en la dirección
u = (cos θ, sin θ); el bloque equivalente ocupa los puntos a menos de a = β1·c de la fibra extrema comprimida, con c
medido perpendicular al eje neutro. La carga axial es positiva en compresión y actúa en el centroide de la sección
bruta. Los momentos siguen la convención de ETABS: M3 positivo comprime la cara +y y M2 positivo la cara +x.
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from structurelab_rc.mechanics.materials import ConcreteBlock, NoEquilibrium, SteelModel
from structurelab_rc.mechanics.polygon import Point, area_centroid, clip
from structurelab_rc.mechanics.roots import find_root

_RELATIVE_TOLERANCE = 1e-13
_DIRECTION_STEP = math.radians(5.0)
_DIRECTION_WALK = 36
_DIRECTION_STEPS = 72
_TOLERANCE = 1e-12
# Estados guardados (D-124): el diseño repite secciones idénticas entre rondas; el estado es inmutable.
_CACHED_STATES = 8192


@dataclass(frozen=True)
class SteelPoint:
    x: float
    y: float
    area: float


@dataclass(frozen=True)
class PointState:
    """Barra en el estado nominal; depth es su distancia a la fibra extrema comprimida, y strain y stress son positivos en tracción."""

    x: float
    y: float
    area: float
    depth: float
    strain: float
    stress: float


@dataclass(frozen=True)
class SectionState:
    theta: float
    c: float
    a: float
    extreme_strain: float
    mn3: float
    mn2: float
    bars: tuple[PointState, ...]


class Stressed(Protocol):
    """Una barra (o capa) en un estado: profundidad desde la fibra extrema comprimida, área y esfuerzo (positivo en
    tracción)."""

    @property
    def depth(self) -> float: ...

    @property
    def area(self) -> float: ...

    @property
    def stress(self) -> float: ...


def force_centroid(bars: Iterable[Stressed]) -> float | None:
    """Profundidad del centroide de las fuerzas de las barras, Σ(Ai·fsi·di)/Σ(Ai·fsi); None si la fuerza es nula. Es la
    d de las barras a tracción de un estado (decisión de ingeniería del usuario, D-131): una barra poco esforzada, cerca
    del eje neutro, casi no la mueve."""
    items = list(bars)
    force = sum(bar.area * bar.stress for bar in items)
    if force <= 0:
        return None
    return sum(bar.area * bar.stress * bar.depth for bar in items) / force


@dataclass(frozen=True)
class _Frame:
    """Geometría de una orientación: dirección de compresión, nivel de la fibra extrema y distancias de las barras."""

    u: Point
    top: float
    depths: tuple[float, ...]


def _frame(polygon: tuple[Point, ...], steel: tuple[SteelPoint, ...], theta: float) -> _Frame:
    u = (math.cos(theta), math.sin(theta))
    top = max(u[0] * x + u[1] * y for x, y in polygon)
    return _Frame(u, top, tuple(top - (u[0] * bar.x + u[1] * bar.y) for bar in steel))


def _bar_state(bar: SteelPoint, depth: float, c: float, concrete: ConcreteBlock, model: SteelModel) -> PointState:
    strain = concrete.max_strain * (depth - c) / c
    stress = math.copysign(min(abs(model.modulus * strain), model.fy), strain)
    return PointState(bar.x, bar.y, bar.area, depth, strain, stress)


def _bar_force(depth: float, area: float, stress: float, c: float, concrete: ConcreteBlock) -> float:
    """Fuerza neta en tracción; una barra dentro del bloque descuenta el concreto que desplaza."""
    displaced = concrete.stress_factor * concrete.fc if depth < concrete.beta1 * c else 0.0
    return area * (stress + displaced)


def _block(polygon: tuple[Point, ...], frame: _Frame, a: float) -> tuple[float, float, float]:
    return area_centroid(clip(polygon, frame.u, frame.top - a))


def _residual(
    polygon: tuple[Point, ...], steel: tuple[SteelPoint, ...], frame: _Frame, c: float, materials: tuple[ConcreteBlock, SteelModel]
) -> float:
    concrete, model = materials
    area, _, _ = _block(polygon, frame, concrete.beta1 * c)
    steel_force = 0.0
    for bar, depth in zip(steel, frame.depths, strict=True):
        state = _bar_state(bar, depth, c, concrete, model)
        steel_force += _bar_force(depth, bar.area, state.stress, c, concrete)
    return concrete.stress_factor * concrete.fc * area - steel_force


def _neutral_axis(
    polygon: tuple[Point, ...], steel: tuple[SteelPoint, ...], frame: _Frame, materials: tuple[ConcreteBlock, SteelModel], axial: float
) -> float:
    """Menor raíz del equilibrio; la fuerza salta hacia abajo cuando el bloque alcanza una barra."""
    beta1 = materials[0].beta1
    deepest = max(*(frame.top - (frame.u[0] * x + frame.u[1] * y) for x, y in polygon), *frame.depths)
    ceiling = 2 * deepest / beta1
    jumps = sorted({depth / beta1 for depth in frame.depths if 0 < depth / beta1 < ceiling})
    low = ceiling * 1e-9

    def residual(c: float) -> float:
        return _residual(polygon, steel, frame, c, materials) - axial

    if residual(low) >= 0:
        raise NoEquilibrium("la tracción axial supera la capacidad del acero")
    for high in (*jumps, ceiling):
        if residual(high * (1 - 1e-12)) >= 0:
            break
        low = high * (1 + 1e-12)
    else:
        raise NoEquilibrium("la compresión axial supera la capacidad de la sección")
    high = high * (1 - 1e-12)
    # Dentro del tramo el equilibrio es continuo: la raíz por Brent, con la misma tolerancia que tenía la bisección (D-124).
    return find_root(residual, (low, high), (residual(low), residual(high)), lambda c: _RELATIVE_TOLERANCE * abs(c))


@lru_cache(maxsize=_CACHED_STATES)
def section_state(
    polygon: tuple[Point, ...],
    steel: tuple[SteelPoint, ...],
    materials: tuple[ConcreteBlock, SteelModel],
    axial: float,
    theta: float,
) -> SectionState:
    """Estado nominal con la dirección de compresión θ fija (θ = 90° comprime la cara +y; θ = 0 la cara +x)."""
    if not steel:
        raise ValueError("la sección no tiene acero")
    concrete, model = materials
    frame = _frame(polygon, steel, theta)
    c = _neutral_axis(polygon, steel, frame, materials, axial)
    a = concrete.beta1 * c
    _, gx, gy = area_centroid(polygon)
    area, bx, by = _block(polygon, frame, a)
    block = concrete.stress_factor * concrete.fc * area
    mn3, mn2 = block * (by - gy), block * (bx - gx)
    states = []
    for bar, depth in zip(steel, frame.depths, strict=True):
        state = _bar_state(bar, depth, c, concrete, model)
        force = _bar_force(depth, bar.area, state.stress, c, concrete)
        mn3 -= force * (bar.y - gy)
        mn2 -= force * (bar.x - gx)
        states.append(state)
    extreme = max(states, key=lambda state: state.depth).strain
    return SectionState(theta, c, a, extreme, mn3, mn2, tuple(states))


def _angle_gap(state: SectionState, target: float) -> float:
    gap = math.atan2(state.mn2, state.mn3) - target
    return (gap + math.pi) % (2 * math.pi) - math.pi


def biaxial_state(
    polygon: tuple[Point, ...],
    steel: tuple[SteelPoint, ...],
    materials: tuple[ConcreteBlock, SteelModel],
    axial: float,
    moments: tuple[float, float],
) -> SectionState:
    """Estado nominal cuyo momento resistente tiene la dirección de (M3, M2), a carga axial constante.

    Parte de la orientación estimada y avanza en pasos de 5° hasta encontrar el cambio de signo; si no lo encuentra,
    recorre media vuelta completa. Luego refina por Brent (D-124).
    """
    mu3, mu2 = moments
    if mu3 == 0 and mu2 == 0:
        return section_state(polygon, steel, materials, axial, math.pi / 2)
    target = math.atan2(mu2, mu3)

    def evaluate(theta: float) -> tuple[SectionState, float]:
        state = section_state(polygon, steel, materials, axial, theta)
        return state, _angle_gap(state, target)

    theta = math.pi / 2 - target
    state, gap = evaluate(theta)
    if abs(gap) < _TOLERANCE:
        return state
    # El ángulo del momento resistente disminuye al aumentar θ: con gap > 0 se avanza hacia θ mayores.
    step = _DIRECTION_STEP if gap > 0 else -_DIRECTION_STEP
    for _ in range(_DIRECTION_WALK):
        following_state, following_gap = evaluate(theta + step)
        if abs(following_gap) < _TOLERANCE:
            return following_state
        if (following_gap > 0) != (gap > 0) and abs(following_gap - gap) < math.pi:
            return _refine(evaluate, (theta, gap), (theta + step, following_gap))
        theta, gap = theta + step, following_gap
    return _scan(evaluate, math.pi / 2 - target)


def _scan(evaluate: Callable[[float], tuple[SectionState, float]], guess: float) -> SectionState:
    """Recorrido completo de media vuelta alrededor de la orientación estimada."""
    step = math.pi / _DIRECTION_STEPS
    previous: tuple[float, float] | None = None
    for index in range(_DIRECTION_STEPS + 1):
        theta = guess - math.pi / 2 + index * step
        state, gap = evaluate(theta)
        if abs(gap) < _TOLERANCE:
            return state
        if previous is not None and (previous[1] > 0) != (gap > 0) and abs(previous[1] - gap) < math.pi:
            return _refine(evaluate, previous, (theta, gap))
        previous = (theta, gap)
    raise NoEquilibrium("no se encontró un eje neutro con la dirección del momento demandado")


def _refine(
    evaluate: Callable[[float], tuple[SectionState, float]], low: tuple[float, float], high: tuple[float, float]
) -> SectionState:
    """La orientación entre dos con gaps de signo contrario, por Brent (D-124), con la tolerancia angular de siempre."""
    states: dict[float, SectionState] = {}

    def gap(theta: float) -> float:
        states[theta], value = evaluate(theta)
        return value

    theta = find_root(gap, (low[0], high[0]), (low[1], high[1]), lambda _: _TOLERANCE)
    return states[theta] if theta in states else evaluate(theta)[0]
