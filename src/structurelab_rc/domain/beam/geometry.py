"""Posición de las barras longitudinales en la sección (D-040)."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.mechanics.polygon import Point
from structurelab_rc.mechanics.section import SteelPoint
from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Section
from structurelab_rc.model.reinforcement import BarLayer, BarPosition, BarSpacing, ReinforcementLayout


@dataclass(frozen=True)
class Bar:
    """Barra ubicada: x sobre el eje 3 desde la cara −3 del alma y depth desde la fibra superior, en mm (D-044)."""

    designation: str
    x: float
    depth: float
    area: float
    diameter: float
    role: str


def interior_limits(section: Section, layout: ReinforcementLayout, specs: dict[str, RebarSpec], diameter: float) -> tuple[float, float]:
    """Menor y mayor x del centro de una barra del diámetro dado dentro del estribo del alma."""
    stirrup = 0.0 if layout.stirrups is None else specs[layout.stirrups.designation].diameter_mm
    inset = section.cover + stirrup + diameter / 2
    return inset, section.bw - inset


def _layer_bars(layer: BarLayer, section: Section, layout: ReinforcementLayout, specs: dict[str, RebarSpec]) -> list[Bar]:
    placed = []
    if isinstance(layer.bars, BarSpacing):
        pairs = [(layer.bars.designation, x) for x in layer.bars.positions()]
    elif all(isinstance(bar, str) for bar in layer.bars):
        names = [bar for bar in layer.bars if isinstance(bar, str)]
        if len(names) == 1:
            positions = [section.bw / 2]
        else:
            left, _ = interior_limits(section, layout, specs, specs[names[0]].diameter_mm)
            _, right = interior_limits(section, layout, specs, specs[names[-1]].diameter_mm)
            positions = [left + index * (right - left) / (len(names) - 1) for index in range(len(names))]
        pairs = list(zip(names, positions, strict=True))
    else:
        pairs = [(bar.designation, bar.x) for bar in layer.bars if isinstance(bar, BarPosition)]
    for name, x in pairs:
        spec = specs[name]
        placed.append(Bar(name, x, layer.depth, spec.area_mm2, spec.diameter_mm, layer.role))
    return placed


def placed_bars(layout: ReinforcementLayout, section: Section, bars: Sequence[RebarSpec]) -> tuple[Bar, ...]:
    """Barras longitudinales con su posición; supone que las designaciones ya se validaron contra el catálogo."""
    specs = {bar.designation: bar for bar in bars}
    return tuple(bar for layer in layout.layers for bar in _layer_bars(layer, section, layout, specs))


def flange_limits(section: Section, diameter: float) -> tuple[float, float] | None:
    """Menor y mayor x del centro de una barra dentro del ala, con el recubrimiento en sus bordes; None sin ala."""
    if section.hf is None:
        return None
    inset = section.cover + diameter / 2
    return -(section.overhang_x_neg or 0.0) + inset, section.bw + (section.overhang_x_pos or 0.0) - inset


def inside_web(bar: Bar, section: Section) -> bool:
    return 0.0 <= bar.x <= section.bw


def section_polygon(section: Section) -> tuple[Point, ...]:
    """Contorno de la sección en coordenadas (x, y): x sobre el eje 3 desde la cara −3 del alma, y hacia arriba desde la base."""
    bw, h = section.bw, section.h
    if section.hf is None:
        return ((0.0, 0.0), (bw, 0.0), (bw, h), (0.0, h))
    neg, pos, base = section.overhang_x_neg or 0.0, section.overhang_x_pos or 0.0, h - section.hf
    return ((0.0, 0.0), (bw, 0.0), (bw, base), (bw + pos, base), (bw + pos, h), (-neg, h), (-neg, base), (0.0, base))


def flexure_points(layout: ReinforcementLayout, section: Section, bars: Sequence[RebarSpec]) -> tuple[SteelPoint, ...]:
    """Barras de flexión como puntos de la mecánica; las de torsión no cuentan como As (D-027)."""
    return tuple(SteelPoint(bar.x, section.h - bar.depth, bar.area) for bar in placed_bars(layout, section, bars) if bar.role == "flexure")
