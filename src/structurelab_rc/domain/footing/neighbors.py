"""Zapatas vecinas en planta (D-156): la huella de cada zapata en ejes globales, a partir de la ubicación de sus columnas
(D-130), y los pares del mismo nivel cuya separación libre entre bordes es menor que la mínima declarada
(min_clear_spacing) o que se traslapan. Solo informa: el diseño y la verificación no revisan la interacción entre
zapatas vecinas; el usuario decide qué pares unir con una zapata combinada (D-153).

Separación libre entre dos rectángulos alineados con los ejes: con huecos dx y dy entre ellos en cada eje (negativo si
se solapan en ese eje), √(dx² + dy²) si los dos son positivos (vecinas en diagonal), el positivo si solo uno lo es y el
mayor (negativo: traslapo) si ninguno lo es.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.model.combined import CombinedFooting, beam_to_global
from structurelab_rc.model.footing import FootingBody


@dataclass(frozen=True)
class Footprint:
    """La planta de una zapata en ejes globales: su id, su nivel, los nudos de ETABS de sus columnas, el centro, el tamaño
    (a lo largo de X y de Y globales) y, en la combinada, cuánto difieren los centros que da cada columna (mm)."""

    name: str
    story: str
    joints: tuple[str, ...]
    centre: tuple[float, float]
    size: tuple[float, float]
    mismatch: float = 0.0

    @property
    def box(self) -> tuple[float, float, float, float]:
        (x, y), (width, depth) = self.centre, self.size
        return x - width / 2, y - depth / 2, x + width / 2, y + depth / 2


@dataclass(frozen=True)
class Neighbors:
    """Dos zapatas del mismo nivel más cercanas que la separación mínima (o traslapadas): sus ids, sus nudos y la
    separación libre entre bordes (mm; negativa si se traslapan)."""

    first: Footprint
    second: Footprint
    clear: float


def isolated_footprint(footing: FootingBody) -> Footprint | None:
    """Zapata aislada o cabezal: location es la de su (primera) columna (D-130, D-143); None sin ubicación."""
    location, first = footing.location, footing.all_columns[0]
    if location is None:
        return None
    centre = (location.x - first.offset_x, location.y - first.offset_y)
    return Footprint(footing.id, location.story, (location.joint,), centre, (footing.lx, footing.ly))


def combined_footprint(footing: CombinedFooting) -> Footprint | None:
    """La combinada en ejes globales: el centro es el promedio de lo que da cada columna (D-130); con la viga en la Y
    global, las dimensiones y las posiciones vuelven de los ejes de la viga a los declarados (D-094, D-101). None si
    alguna columna no tiene ubicación."""
    if any(column.location is None for column in footing.columns):
        return None
    rotated = footing.principal_direction == "y"
    estimates = []
    for column in footing.columns:
        assert column.location is not None
        offset = beam_to_global(column.x, column.y) if rotated else (column.x, column.y)
        estimates.append((column.location.x - offset[0], column.location.y - offset[1]))
    centre = (sum(x for x, _ in estimates) / len(estimates), sum(y for _, y in estimates) / len(estimates))
    (x0, y0), (x1, y1) = estimates
    first = footing.columns[0].location
    assert first is not None
    joints = tuple(column.location.joint for column in footing.columns if column.location is not None)
    size = (footing.ly, footing.lx) if rotated else (footing.lx, footing.ly)
    return Footprint(footing.id, first.story, joints, centre, size, math.hypot(x1 - x0, y1 - y0))


def footprints(footings: Sequence[FootingBody], combined: Sequence[CombinedFooting]) -> list[Footprint]:
    """Las plantas de las zapatas con ubicación, aisladas (y cabezales) primero."""
    found = [isolated_footprint(footing) for footing in footings] + [combined_footprint(footing) for footing in combined]
    return [item for item in found if item is not None]


def clear_distance(first: Footprint, second: Footprint) -> float:
    """La separación libre entre los bordes de dos plantas (negativa si se traslapan)."""
    a, b = first.box, second.box
    dx, dy = max(b[0] - a[2], a[0] - b[2]), max(b[1] - a[3], a[1] - b[3])
    return math.hypot(dx, dy) if dx > 0 and dy > 0 else max(dx, dy)


def close_neighbors(placed: Sequence[Footprint], minimum: float | None) -> list[Neighbors]:
    """Los pares del mismo nivel con separación libre menor que minimum (sin él, solo los traslapados), en orden."""
    limit = 0.0 if minimum is None else minimum
    found = []
    for index, first in enumerate(placed):
        for second in placed[index + 1:]:
            if first.story != second.story:
                continue
            clear = clear_distance(first, second)
            if clear < limit:
                found.append(Neighbors(first, second, clear))
    return found


def neighbor_text(item: Neighbors, minimum: float | None) -> str:
    """El aviso de un par: los ids, sus nudos y la separación frente a la mínima."""
    names = f"{item.first.name} (nudo {', '.join(item.first.joints)}) y {item.second.name} (nudo {', '.join(item.second.joints)})"
    if item.clear < 0:
        return f"se traslapan {names}: {-item.clear:.0f} mm"
    return f"separacion libre de {item.clear:.0f} mm, menor que la minima de {minimum:.0f} mm, entre {names}"
