"""Polígonos simples: área y centroide, recorte por un semiplano e integración de un campo lineal, en mm."""

from collections.abc import Iterator

Point = tuple[float, float]

_TOLERANCE = 1e-12
_MIN_VERTICES = 3


def _edges(polygon: tuple[Point, ...]) -> Iterator[tuple[Point, Point]]:
    return zip(polygon, (*polygon[1:], polygon[0]), strict=True)


def area_centroid(polygon: tuple[Point, ...]) -> tuple[float, float, float]:
    """Área y centroide de un polígono simple (fórmula del área de Gauss); área cero si es degenerado."""
    area = cx = cy = 0.0
    for (x1, y1), (x2, y2) in _edges(polygon):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < _TOLERANCE:
        return 0.0, 0.0, 0.0
    return abs(area) / 2, cx / (3 * area), cy / (3 * area)


def clip(polygon: tuple[Point, ...], u: Point, level: float) -> tuple[Point, ...]:
    """Parte del polígono con u·p ≥ level (algoritmo de Sutherland-Hodgman con un solo semiplano)."""
    kept: list[Point] = []
    for current, following in _edges(polygon):
        p1 = u[0] * current[0] + u[1] * current[1] - level
        p2 = u[0] * following[0] + u[1] * following[1] - level
        if p1 >= 0:
            kept.append(current)
        if (p1 >= 0) != (p2 >= 0):
            t = p1 / (p1 - p2)
            kept.append((current[0] + t * (following[0] - current[0]), current[1] + t * (following[1] - current[1])))
    return tuple(kept)


def linear_resultant(polygon: tuple[Point, ...], plane: tuple[float, float, float]) -> tuple[float, float, float]:
    """Integrales exactas de q = q0 + gx·x + gy·y sobre el polígono: ∫q dA, ∫x·q dA y ∫y·q dA.

    Usa los momentos de área de orden 0 a 2 por el teorema de Green; el signo no depende del sentido de recorrido.
    """
    if len(polygon) < _MIN_VERTICES:
        return 0.0, 0.0, 0.0
    a = sx = sy = sxx = sxy = syy = 0.0
    for (x1, y1), (x2, y2) in _edges(polygon):
        cross = x1 * y2 - x2 * y1
        a += cross / 2
        sx += (x1 + x2) * cross / 6
        sy += (y1 + y2) * cross / 6
        sxx += (x1 * x1 + x1 * x2 + x2 * x2) * cross / 12
        sxy += (x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) * cross / 24
        syy += (y1 * y1 + y1 * y2 + y2 * y2) * cross / 12
    if a < 0:
        a, sx, sy, sxx, sxy, syy = -a, -sx, -sy, -sxx, -sxy, -syy
    q0, gx, gy = plane
    return q0 * a + gx * sx + gy * sy, q0 * sx + gx * sxx + gy * sxy, q0 * sy + gx * sxy + gy * syy
