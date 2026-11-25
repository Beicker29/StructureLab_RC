"""Zapatas vecinas en planta (D-156): la huella de cada zapata en ejes globales, a partir de la ubicación de sus columnas
(D-130), y los pares del mismo nivel cuya separación libre entre bordes es menor que la mínima declarada
(min_clear_spacing) o que se traslapan. Solo informa: el diseño y la verificación no revisan la interacción entre
zapatas vecinas; el usuario decide qué pares unir con una zapata combinada (D-153).

La separación libre se mide entre los contornos reales en ejes globales (D-170): el rectángulo, el contorno recortado
del cabezal o la planta trapezoidal, en T, L o I de la combinada (mechanics/polygon.separation).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from structurelab_rc.mechanics.polygon import separation
from structurelab_rc.model.combined import CombinedFooting, beam_to_global
from structurelab_rc.model.footing import FootingBody
from structurelab_rc.model.pile_cap import PileCap

Point = tuple[float, float]


@dataclass(frozen=True)
class Footprint:
    """La planta de una zapata en ejes globales: su id, su nivel, los nudos de ETABS de sus columnas, el centro (el
    centroide de la base), su contorno en ejes globales y, en la combinada, cuánto difieren los centros que da cada
    columna (mm)."""

    name: str
    story: str
    joints: tuple[str, ...]
    centre: Point
    outline: tuple[Point, ...]
    mismatch: float = 0.0

    @property
    def box(self) -> tuple[float, float, float, float]:
        xs, ys = [p[0] for p in self.outline], [p[1] for p in self.outline]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def size(self) -> Point:
        """El tamaño de la caja que contiene la planta, a lo largo de X y de Y globales."""
        x0, y0, x1, y1 = self.box
        return x1 - x0, y1 - y0


def _placed(outline: Sequence[Point], centre: Point, rotated: bool = False) -> tuple[Point, ...]:
    """Un contorno en ejes de la zapata (origen en su centroide) llevado a ejes globales: girado si la viga va en la Y
    global (D-094) y corrido al centro."""
    return tuple((centre[0] + x, centre[1] + y) for x, y in (beam_to_global(*p) if rotated else p for p in outline))


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
    hx, hy = footing.lx / 2, footing.ly / 2
    outline = footing.outline if isinstance(footing, PileCap) else ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))
    return Footprint(footing.id, location.story, (location.joint,), centre, _placed(outline, centre))


def combined_footprint(footing: CombinedFooting) -> Footprint | None:
    """La combinada en ejes globales: el centro (el centroide de la base) es el promedio de lo que da cada columna
    (D-130), con dos o más columnas (D-163); con la viga en la Y global, el contorno y las posiciones vuelven de los ejes
    de la viga a los declarados (D-094, D-101). El contorno es el rectángulo o la planta trapezoidal, en T, L o I (D-170);
    la diferencia entre columnas, la mayor distancia entre los centros que dan. None si alguna columna no tiene
    ubicación."""
    if any(column.location is None for column in footing.columns):
        return None
    rotated = footing.principal_direction == "y"
    estimates = []
    for column in footing.columns:
        assert column.location is not None
        offset = beam_to_global(column.x, column.y) if rotated else (column.x, column.y)
        estimates.append((column.location.x - offset[0], column.location.y - offset[1]))
    centre = (sum(x for x, _ in estimates) / len(estimates), sum(y for _, y in estimates) / len(estimates))
    mismatch = max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in combinations(estimates, 2))
    first = footing.columns[0].location
    assert first is not None
    joints = tuple(column.location.joint for column in footing.columns if column.location is not None)
    return Footprint(footing.id, first.story, joints, centre, _placed(footing.outline, centre, rotated), mismatch)


def footprints(footings: Sequence[FootingBody], combined: Sequence[CombinedFooting]) -> list[Footprint]:
    """Las plantas de las zapatas con ubicación, aisladas (y cabezales) primero."""
    found = [isolated_footprint(footing) for footing in footings] + [combined_footprint(footing) for footing in combined]
    return [item for item in found if item is not None]


def clear_distance(first: Footprint, second: Footprint) -> float:
    """La separación libre entre los bordes de dos plantas, entre sus contornos reales (negativa si se traslapan, D-170)."""
    return separation(first.outline, second.outline)


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
