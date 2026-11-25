"""Polígonos simples: área y centroide, recorte por un semiplano e integración de un campo lineal, en mm."""

import math
from collections.abc import Iterator

Point = tuple[float, float]

_TOLERANCE = 1e-12
_NEAR = 1e-6  # mm: un punto a menos de esto del borde está sobre él
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


def _point_segment(point: Point, a: Point, b: Point) -> float:
    """Distancia de un punto a un segmento."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length))
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def _crossing(p: Point, q: Point, a: Point, b: Point) -> bool:
    """Si los segmentos pq y ab se cruzan propiamente (cada uno corta al otro en su interior)."""
    d1, d2, d3, d4 = _cross(a, b, p), _cross(a, b, q), _cross(p, q, a), _cross(p, q, b)
    return d1 * d2 < 0 and d3 * d4 < 0


def _boundary_distance(point: Point, polygon: tuple[Point, ...]) -> float:
    return min(_point_segment(point, a, b) for a, b in _edges(polygon))


def _probes(polygon: tuple[Point, ...]) -> list[Point]:
    """Los vértices y los puntos medios de los lados: si alguno queda en el interior del otro polígono, se traslapan."""
    return [*polygon, *(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in _edges(polygon))]


def _strictly_within(point: Point, polygon: tuple[Point, ...]) -> bool:
    """Dentro del polígono y no sobre su borde (a más de 1e-6 mm)."""
    return contains(point, polygon) and _boundary_distance(point, polygon) > _NEAR


def separation(first: tuple[Point, ...], second: tuple[Point, ...]) -> float:
    """La separación libre entre dos polígonos simples (convexos o no, D-170): sin traslapo, la distancia mínima entre
    sus bordes (cero si se tocan); traslapados (un vértice o el punto medio de un lado de uno en el interior del otro, o
    dos lados que se cruzan), negativa: menos el menor traslapo de sus cajas en un eje (en dos rectángulos alineados con
    los ejes, el traslapo exacto)."""
    overlapping = (any(_strictly_within(p, second) for p in _probes(first))
                   or any(_strictly_within(p, first) for p in _probes(second))
                   or any(_crossing(p, q, a, b) for p, q in _edges(first) for a, b in _edges(second)))
    if overlapping:
        xs_a, ys_a = [p[0] for p in first], [p[1] for p in first]
        xs_b, ys_b = [p[0] for p in second], [p[1] for p in second]
        overlap_x = min(max(xs_a), max(xs_b)) - max(min(xs_a), min(xs_b))
        overlap_y = min(max(ys_a), max(ys_b)) - max(min(ys_a), min(ys_b))
        return -min(overlap_x, overlap_y)
    return min(min(_boundary_distance(p, second) for p in first), min(_boundary_distance(p, first) for p in second))


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
