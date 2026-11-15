"""Geometría del contorno de un cabezal con esquinas recortadas (D-141): el polígono convexo de PileCap.outline.

Las cuerdas, las regiones más allá de un plano y las barras que cruzan una sección se miden sobre el polígono; en un
cabezal rectangular coinciden con las del rectángulo. El recubrimiento de las barras en un recorte se mide a lo largo de
la barra (aproximación del lado seguro: la barra queda un poco más corta).
"""

import math
from dataclasses import replace

from structurelab_rc.domain.footing.mesh import BarRow
from structurelab_rc.mechanics.polygon import Point, area_centroid, clip
from structurelab_rc.model.pile_cap import PileCap

_TOLERANCE = 1e-6


def centroid(cap: PileCap) -> tuple[float, float, float]:
    """Área y centroide del contorno, en mm² y mm."""
    return area_centroid(cap.outline)


def beyond(cap: PileCap, axis: int, plane: float, outward: float) -> tuple[float, float, float]:
    """Área y centroide de la parte del contorno más allá de un plano normal a x (axis = 0) o a y (axis = 1), del lado
    outward (+1 o −1)."""
    u: Point = (outward, 0.0) if axis == 0 else (0.0, outward)
    piece = clip(cap.outline, u, outward * plane)
    return area_centroid(piece) if len(piece) >= 3 else (0.0, 0.0, 0.0)  # noqa: PLR2004 - un polígono


def chord(cap: PileCap, axis: int, plane: float) -> tuple[float, float] | None:
    """Intervalo de la otra coordenada en que la recta x = plane (axis = 0) o y = plane (axis = 1) queda dentro del
    contorno; None si no lo corta."""
    values = []
    outline = cap.outline
    for index, start in enumerate(outline):
        end = outline[(index + 1) % len(outline)]
        a, b = start[axis], end[axis]
        if (a - plane) * (b - plane) > 0 or a == b:
            if a == b == plane:
                values += [start[1 - axis], end[1 - axis]]
            continue
        t = (plane - a) / (b - a)
        values.append(start[1 - axis] + t * (end[1 - axis] - start[1 - axis]))
    return (min(values), max(values)) if values else None


def bar_span(cap: PileCap, direction: str, position: float) -> tuple[float, float] | None:
    """Tramo de una barra paralela a X (direction x, en y = position) o a Y, de borde a borde del contorno menos el
    recubrimiento; None si no cabe."""
    found = chord(cap, 1 if direction == "x" else 0, position)
    if found is None or found[1] - found[0] <= 2 * cap.cover:
        return None
    return found[0] + cap.cover, found[1] - cap.cover


def section_row(cap: PileCap, row: BarRow, plane: float) -> BarRow:
    """Las barras de una fila que cruzan la sección normal a su dirección en plane, con el ancho real del contorno en esa
    sección (D-141): así se revisan la flexión y el cortante de los cabezales con esquinas recortadas."""
    axis = 0 if row.direction == "x" else 1
    across = chord(cap, axis, plane)
    width = 0.0 if across is None else across[1] - across[0]
    crossing = []
    for position in row.positions:
        span = bar_span(cap, row.direction, position)
        if span is not None and span[0] - _TOLERANCE <= plane <= span[1] + _TOLERANCE:
            crossing.append(position)
    return replace(row, width=width, positions=tuple(crossing), band_positions=tuple(p for p in row.band_positions if p in crossing))


def edge_distance(cap: PileCap, point: Point) -> float:
    """Menor distancia de un punto a los bordes del contorno, en mm."""
    outline = cap.outline
    best = float("inf")
    for index, (x1, y1) in enumerate(outline):
        x2, y2 = outline[(index + 1) % len(outline)]
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        best = min(best, abs((x2 - x1) * (y1 - point[1]) - (x1 - point[0]) * (y2 - y1)) / length)
    return best


def inside(cap: PileCap, region: tuple[Point, Point]) -> tuple[float, float, float]:
    """Área y centroide de la parte del contorno dentro de un rectángulo ((x0, y0), (x1, y1))."""
    (x0, y0), (x1, y1) = region
    piece = cap.outline
    for u, level in (((1.0, 0.0), x0), ((-1.0, 0.0), -x1), ((0.0, 1.0), y0), ((0.0, -1.0), -y1)):
        piece = clip(piece, u, level)
        if len(piece) < 3:  # noqa: PLR2004 - un polígono
            return 0.0, 0.0, 0.0
    return area_centroid(piece)


def parallel_chord(cap: PileCap, edge: tuple[Point, Point], offset: float) -> float:
    """Longitud, dentro del contorno, de la recta paralela al borde edge a la distancia offset hacia adentro (la
    sección de cortante de esquina de un recorte, D-141); 0 si no lo corta."""
    (ax, ay), (bx, by) = edge
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    normal = (-(by - ay) / length, (bx - ax) / length)  # hacia adentro: el contorno va en sentido antihorario
    level = normal[0] * ax + normal[1] * ay + offset
    points = []
    outline = cap.outline
    for index, start in enumerate(outline):
        end = outline[(index + 1) % len(outline)]
        p, q = normal[0] * start[0] + normal[1] * start[1] - level, normal[0] * end[0] + normal[1] * end[1] - level
        if p == q or p * q > 0:
            continue
        t = p / (p - q)
        points.append((start[0] + t * (end[0] - start[0]), start[1] + t * (end[1] - start[1])))
    if len(points) < 2:  # noqa: PLR2004 - una cuerda
        return 0.0
    return max(math.dist(a, b) for a in points for b in points)
