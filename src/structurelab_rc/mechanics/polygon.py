"""Polígonos simples: área y centroide, recorte por un semiplano e integración de un campo lineal, en mm."""

import math
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


Moments = tuple[float, float, float, float, float, float]


def moments(polygon: tuple[Point, ...]) -> Moments:
    """Momentos de área de orden 0 a 2 del polígono, (A, ∫x, ∫y, ∫x², ∫xy, ∫y²), por el teorema de Green; el signo no
    depende del sentido de recorrido. Un recorte de un polígono no convexo puede traer aristas de ida y vuelta sobre la
    misma recta: no tienen área y no cambian las integrales."""
    if len(polygon) < _MIN_VERTICES:
        return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
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
    return a, sx, sy, sxx, sxy, syy


def linear_resultant(polygon: tuple[Point, ...], plane: tuple[float, float, float]) -> tuple[float, float, float]:
    """Integrales exactas de q = q0 + gx·x + gy·y sobre el polígono: ∫q dA, ∫x·q dA y ∫y·q dA."""
    a, sx, sy, sxx, sxy, syy = moments(polygon)
    q0, gx, gy = plane
    return q0 * a + gx * sx + gy * sy, q0 * sx + gx * sxx + gy * sxy, q0 * sy + gx * sxy + gy * syy


def convex_hull(points: tuple[Point, ...]) -> tuple[Point, ...]:
    """Envolvente convexa en sentido antihorario (cadena monótona de Andrew), sin puntos alineados."""
    ordered = sorted(set(points))
    if len(ordered) < _MIN_VERTICES:
        return tuple(ordered)

    def half(sequence: list[Point]) -> list[Point]:
        chain: list[Point] = []
        for point in sequence:
            while len(chain) >= 2 and _cross(chain[-2], chain[-1], point) <= 0:  # noqa: PLR2004
                chain.pop()
            chain.append(point)
        return chain[:-1]

    return (*half(ordered), *half(ordered[::-1]))


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def strictly_inside(point: Point, convex: tuple[Point, ...]) -> bool:
    """Si el punto está en el interior de un polígono convexo antihorario (no en su borde)."""
    return len(convex) >= _MIN_VERTICES and all(_cross(a, b, point) > 0 for a, b in _edges(convex))


def contains(point: Point, polygon: tuple[Point, ...]) -> bool:
    """Si el punto está dentro del polígono simple (convexo o no) o sobre su borde (cruce de rayos)."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in _edges(polygon):
        aligned = abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) <= _TOLERANCE * max(1.0, abs(x2 - x1) + abs(y2 - y1))
        within = min(x1, x2) - _TOLERANCE <= x <= max(x1, x2) + _TOLERANCE and min(y1, y2) - _TOLERANCE <= y <= max(y1, y2) + _TOLERANCE
        if aligned and within:
            return True  # sobre el borde
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def segment_inside(start: Point, end: Point, polygon: tuple[Point, ...]) -> list[tuple[Point, Point]]:
    """Los tramos de un segmento dentro de un polígono simple (convexo o no): corta el segmento en sus cruces con los
    lados y conserva los tramos cuyo punto medio queda dentro."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    cuts = {0.0, 1.0}
    for (x1, y1), (x2, y2) in _edges(polygon):
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if den == 0:
            continue
        t = ((x1 - start[0]) * ey - (y1 - start[1]) * ex) / den
        u = ((x1 - start[0]) * dy - (y1 - start[1]) * dx) / den
        if 0.0 < t < 1.0 and -_TOLERANCE <= u <= 1.0 + _TOLERANCE:
            cuts.add(t)
    ordered = sorted(cuts)
    parts: list[tuple[Point, Point]] = []
    for a, b in zip(ordered, ordered[1:], strict=False):
        middle = (start[0] + (a + b) / 2 * dx, start[1] + (a + b) / 2 * dy)
        if b - a > _TOLERANCE and contains(middle, polygon):
            first = (start[0] + a * dx, start[1] + a * dy)
            if parts and parts[-1][1] == first:  # tramos seguidos: uno solo
                first = parts.pop()[0]
            parts.append((first, (start[0] + b * dx, start[1] + b * dy)))
    return parts


def inset(polygon: tuple[Point, ...], distance: float) -> tuple[Point, ...]:
    """El contorno antihorario corrido distance hacia adentro: cada lado paralelo a sí mismo y cada vértice en el cruce
    de los dos lados corridos (vale para plantas convexas y para las escalonadas con esquinas entrantes rectas)."""
    count = len(polygon)
    lines = []
    for index in range(count):
        (x1, y1), (x2, y2) = polygon[index], polygon[(index + 1) % count]
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length  # hacia adentro
        lines.append(((x1 + distance * nx, y1 + distance * ny), (x2 - x1, y2 - y1)))
    points = []
    for index in range(count):
        (p, d), (q, e) = lines[index - 1], lines[index]
        cross = d[0] * e[1] - d[1] * e[0]
        if abs(cross) < _TOLERANCE:
            points.append(q)
            continue
        t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / cross
        points.append((p[0] + t * d[0], p[1] + t * d[1]))
    return tuple(points)
