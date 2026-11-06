"""Posición de las barras longitudinales en la sección (D-040)."""

from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.project import Section
from structurelab_rc.model.reinforcement import BarLayer, ReinforcementLayout


@dataclass(frozen=True)
class Bar:
    """Barra ubicada: z desde la cara izquierda del alma y depth desde la fibra superior, en mm."""

    designation: str
    z: float
    depth: float
    area: float
    diameter: float
    role: str


def interior_limits(section: Section, layout: ReinforcementLayout, specs: dict[str, RebarSpec], diameter: float) -> tuple[float, float]:
    """Centro más a la izquierda y más a la derecha que admite una barra del diámetro dado dentro del estribo."""
    stirrup = 0.0 if layout.stirrups is None else specs[layout.stirrups.designation].diameter_mm
    inset = section.cover + stirrup + diameter / 2
    return inset, section.bw - inset


def _layer_bars(layer: BarLayer, section: Section, layout: ReinforcementLayout, specs: dict[str, RebarSpec]) -> list[Bar]:
    placed = []
    if all(isinstance(bar, str) for bar in layer.bars):
        names = [bar for bar in layer.bars if isinstance(bar, str)]
        if len(names) == 1:
            positions = [section.bw / 2]
        else:
            left, _ = interior_limits(section, layout, specs, specs[names[0]].diameter_mm)
            _, right = interior_limits(section, layout, specs, specs[names[-1]].diameter_mm)
            positions = [left + index * (right - left) / (len(names) - 1) for index in range(len(names))]
        pairs = list(zip(names, positions, strict=True))
    else:
        pairs = [(bar.designation, bar.z) for bar in layer.bars if not isinstance(bar, str)]
    for name, z in pairs:
        spec = specs[name]
        placed.append(Bar(name, z, layer.depth, spec.area_mm2, spec.diameter_mm, layer.role))
    return placed


def placed_bars(layout: ReinforcementLayout, section: Section, bars: Sequence[RebarSpec]) -> tuple[Bar, ...]:
    """Barras longitudinales con su posición; supone que las designaciones ya se validaron contra el catálogo."""
    specs = {bar.designation: bar for bar in bars}
    return tuple(bar for layer in layout.layers for bar in _layer_bars(layer, section, layout, specs))
