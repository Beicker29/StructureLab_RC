"""Barras de las mallas de una zapata: posiciones, franja central y altura efectiva de cada dirección (D-061).

Las barras x (paralelas a X) se reparten a lo largo de Y en el ancho ly; las barras y, a lo largo de X en lx. El
rango útil deja el recubrimiento libre y medio diámetro a cada lado. Sin franja, las barras van a la separación
declarada, centradas en el rango. Con franja (dirección corta de una zapata rectangular, D-059), las de la franja van
a band_spacing, centradas en ella, y fuera de ella a spacing contada desde la última barra de la franja. En la zapata
combinada con estribos, el recubrimiento es al estribo: las mallas y las barras superiores quedan por dentro de él (un
diámetro de estribo más hacia adentro desde las caras inferior y superior y, las barras x, desde las caras laterales
±Y; D-088).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.model.catalog import RebarSpec
from structurelab_rc.model.combined import CombinedFooting
from structurelab_rc.model.footing import BarSet, Footing, Mat

_TOLERANCE = 1e-6


@dataclass(frozen=True)
class BarRow:
    """Barras de una dirección de una malla. depth es la altura efectiva d, medida desde la cara opuesta a la malla."""

    direction: str
    designation: str
    diameter: float
    bar_area: float
    depth: float
    width: float
    positions: tuple[float, ...]
    band: tuple[float, float] | None
    band_positions: tuple[float, ...]

    @property
    def area(self) -> float:
        return len(self.positions) * self.bar_area

    @property
    def band_area(self) -> float:
        return len(self.band_positions) * self.bar_area


def uniform_positions(low: float, high: float, spacing: float) -> list[float]:
    """Barras a la separación dada, centradas en el rango útil [low, high]."""
    count = math.floor((high - low) / spacing + _TOLERANCE) + 1
    offset = (high - low - (count - 1) * spacing) / 2
    return [low + offset + index * spacing for index in range(count)]


def _positions(low: float, high: float, bar_set: BarSet, band: tuple[float, float] | None) -> tuple[list[float], list[float]]:
    """Posiciones de todas las barras y de las que caen en la franja (si la hay)."""
    if bar_set.band_spacing is None:
        positions = uniform_positions(low, high, bar_set.spacing)
        if band is None:
            return positions, []
        return positions, [p for p in positions if band[0] - _TOLERANCE <= p <= band[1] + _TOLERANCE]
    assert band is not None
    start, end = max(band[0], low), min(band[1], high)
    inner = uniform_positions(start, end, bar_set.band_spacing)
    left, right = [], []
    position = inner[0] - bar_set.spacing
    while position >= low - _TOLERANCE:
        left.append(position)
        position -= bar_set.spacing
    position = inner[-1] + bar_set.spacing
    while position <= high + _TOLERANCE:
        right.append(position)
        position += bar_set.spacing
    return [*reversed(left), *inner, *right], inner


def band_limits(footing: Footing, direction: str) -> tuple[float, float] | None:
    """Franja central de la dirección corta: ancho igual al lado corto, centrada en el eje de la columna."""
    if direction != footing.short_direction:
        return None
    short = min(footing.lx, footing.ly)
    centre = footing.column.offset_x if direction == "y" else footing.column.offset_y
    return centre - short / 2, centre + short / 2


def stirrup_diameter(footing: Footing | CombinedFooting, bars: Sequence[RebarSpec]) -> float:
    """Diámetro de los estribos de la zapata combinada (0 si no los tiene o es una zapata aislada)."""
    if not isinstance(footing, CombinedFooting) or footing.stirrups is None:
        return 0.0
    return next(bar.diameter_mm for bar in bars if bar.designation == footing.stirrups.designation)


def _row(footing: Footing | CombinedFooting, direction: str, bar_set: BarSet, spec: RebarSpec,
         faces: tuple[float, float]) -> BarRow:
    """faces = (distancia del centro de la barra a su cara, diámetro del estribo que la encierra lateralmente)."""
    from_face, stirrup = faces
    width = footing.ly if direction == "x" else footing.lx
    # Los estribos de la combinada encierran las barras x por los lados ±Y; a lo largo de X no hay estribo en los extremos.
    half = width / 2 - footing.cover - (stirrup if direction == "x" else 0.0) - spec.diameter_mm / 2
    band = band_limits(footing, direction) if isinstance(footing, Footing) else None
    positions, inner = _positions(-half, half, bar_set, band)
    return BarRow(direction, bar_set.designation, spec.diameter_mm, spec.area_mm2, footing.h - from_face, width,
                  tuple(positions), band, tuple(inner))


def mat_rows(footing: Footing | CombinedFooting, mat: Mat, bars: Sequence[RebarSpec]) -> dict[str, BarRow]:
    """Las dos direcciones de una malla; la de `first` va más cerca de la cara. Las barras deben estar en el catálogo.
    La zapata combinada no tiene franja central (su refuerzo bajo cada columna va aparte, D-080)."""
    specs = {bar.designation: bar for bar in bars}
    order = (mat.first, "y" if mat.first == "x" else "x")
    first_diameter = specs[getattr(mat, mat.first).designation].diameter_mm
    stirrup = stirrup_diameter(footing, bars)
    cover = footing.cover + stirrup
    rows = {}
    for index, direction in enumerate(order):
        bar_set: BarSet = getattr(mat, direction)
        spec = specs[bar_set.designation]
        from_face = cover + spec.diameter_mm / 2 if index == 0 else cover + first_diameter + spec.diameter_mm / 2
        rows[direction] = _row(footing, direction, bar_set, spec, (from_face, stirrup))
    return rows


def top_row(footing: CombinedFooting, bars: Sequence[RebarSpec]) -> BarRow | None:
    """Las barras superiores paralelas a X de una zapata combinada, una sola capa; None si no las tiene."""
    if footing.top is None:
        return None
    spec = next(bar for bar in bars if bar.designation == footing.top.designation)
    stirrup = stirrup_diameter(footing, bars)
    return _row(footing, "x", footing.top, spec, (footing.cover + stirrup + spec.diameter_mm / 2, stirrup))
