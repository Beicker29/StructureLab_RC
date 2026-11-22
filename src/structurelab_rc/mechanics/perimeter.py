"""Perímetro crítico rectangular para cortante en dos direcciones, recortado con el borde del elemento, en mm.

El perímetro rodea un área cargada rectangular c1 × c2 (c1 a lo largo de x) a la distancia d/2, con lados rectos. Un
lado que cae fuera del contorno rectangular del elemento no existe; los lados que quedan se recortan con él. Las
propiedades son las de la sección crítica de espesor d: longitud b0, centroide de los lados y la propiedad análoga al
momento polar de inercia Jc respecto a cada eje centroidal (para la columna interior coincide con la expresión del
comentario ACI R8.4.4.2.3). No conoce φ ni numerales.
"""

from dataclasses import dataclass

from structurelab_rc.mechanics.polygon import Point, contains, segment_inside

_EMPTY = 1e-12  # fracción del lado: por debajo, el lado queda fuera del contorno
_OUTSIDE_BY_CORNERS = {4: 0, 3: 1, 2: 1, 1: 2, 0: 4}  # esquinas dentro → lados que se descuentan para αs (D-164)


@dataclass(frozen=True)
class Side:
    start: Point
    end: Point

    @property
    def length(self) -> float:
        return abs(self.end[0] - self.start[0]) + abs(self.end[1] - self.start[1])

    @property
    def along_x(self) -> bool:
        return self.start[1] == self.end[1]


@dataclass(frozen=True)
class Perimeter:
    """Lados de la sección crítica; outside cuenta los lados del rectángulo completo que cayeron fuera del elemento."""

    sides: tuple[Side, ...]
    outside: int
    depth: float
    region: tuple[Point, Point]

    @property
    def length(self) -> float:
        return sum(side.length for side in self.sides)

    @property
    def centroid(self) -> Point:
        total = self.length
        x = sum(side.length * (side.start[0] + side.end[0]) / 2 for side in self.sides) / total
        y = sum(side.length * (side.start[1] + side.end[1]) / 2 for side in self.sides) / total
        return x, y

    def polar(self, axis: int) -> float:
        """Jc para el esfuerzo que varía a lo largo de x (axis = 0) o de y (axis = 1), respecto al centroide."""
        centre = self.centroid[axis]
        d = self.depth
        total = 0.0
        for side in self.sides:
            a, b = side.start[axis] - centre, side.end[axis] - centre
            if a == b:  # lado perpendicular al eje: todo a la misma distancia
                total += d * side.length * a**2
            else:  # lado paralelo al eje: ∫ d·u² du más su propia rigidez d³·L/12
                low, high = min(a, b), max(a, b)
                total += d * (high**3 - low**3) / 3 + side.length * d**3 / 12
        return total

    def corners(self) -> tuple[Point, ...]:
        """Extremos de los lados, donde el esfuerzo lineal alcanza sus extremos."""
        return tuple({point for side in self.sides for point in (side.start, side.end)})


def critical_perimeter(centre: Point, c1: float, c2: float, depth: float, bounds: tuple[Point, Point]) -> Perimeter:
    """Perímetro a d/2 de un área cargada c1 × c2 centrada en centre, dentro del rectángulo bounds = ((x0, y0), (x1, y1))."""
    (x0, y0), (x1, y1) = bounds
    left, right = centre[0] - (c1 + depth) / 2, centre[0] + (c1 + depth) / 2
    bottom, top = centre[1] - (c2 + depth) / 2, centre[1] + (c2 + depth) / 2
    inside = {"left": left > x0, "right": right < x1, "bottom": bottom > y0, "top": top < y1}
    cl, cr, cb, ct = max(left, x0), min(right, x1), max(bottom, y0), min(top, y1)
    candidates = {"bottom": Side((cl, bottom), (cr, bottom)), "right": Side((right, cb), (right, ct)),
                  "top": Side((cr, top), (cl, top)), "left": Side((left, ct), (left, cb))}
    sides = tuple(side for name, side in candidates.items() if inside[name])
    return Perimeter(sides, sum(1 for present in inside.values() if not present), depth, ((cl, cb), (cr, ct)))


def plan_perimeter(centre: Point, c1: float, c2: float, depth: float, outline: tuple[Point, ...]) -> Perimeter:
    """Perímetro a d/2 de un área cargada c1 × c2 en una planta trapezoidal o en T/L (D-164): de cada lado del
    rectángulo queda lo que cae dentro del contorno (convexo o no; el borde libre no es sección). outside sale de las
    esquinas del rectángulo dentro del contorno, criterio del usuario: 4 → 0 lados afuera (interior), 3 → 1 (un borde
    corta una esquina), 2 → 1 (borde: un lado entero afuera), 1 → 2 (esquina); sin ninguna, 4 (sin αs)."""
    left, right = centre[0] - (c1 + depth) / 2, centre[0] + (c1 + depth) / 2
    bottom, top = centre[1] - (c2 + depth) / 2, centre[1] + (c2 + depth) / 2
    corners = ((left, bottom), (right, bottom), (right, top), (left, top))
    sides = [Side(*part) for index, start in enumerate(corners)
             for part in segment_inside(start, corners[(index + 1) % 4], outline)]
    inside = sum(1 for corner in corners if contains(corner, outline))
    points = [point for side in sides for point in (side.start, side.end)] or [centre]
    region = ((min(p[0] for p in points), min(p[1] for p in points)), (max(p[0] for p in points), max(p[1] for p in points)))
    return Perimeter(tuple(sides), _OUTSIDE_BY_CORNERS[inside], depth, region)


def _inside_part(start: Point, end: Point, outline: tuple[Point, ...]) -> tuple[Point, Point] | None:
    """La parte de un segmento dentro de un polígono convexo en sentido antihorario (Cyrus-Beck); None si queda fuera."""
    low, high = 0.0, 1.0
    dx, dy = end[0] - start[0], end[1] - start[1]
    for index, (x1, y1) in enumerate(outline):
        x2, y2 = outline[(index + 1) % len(outline)]
        normal = (-(y2 - y1), x2 - x1)  # hacia adentro
        num = normal[0] * (start[0] - x1) + normal[1] * (start[1] - y1)
        den = normal[0] * dx + normal[1] * dy
        if den == 0:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            low = max(low, t)
        else:
            high = min(high, t)
    if high - low <= _EMPTY:
        return None
    return (start[0] + low * dx, start[1] + low * dy), (start[0] + high * dx, start[1] + high * dy)


def polygon_perimeter(centre: Point, c1: float, c2: float, depth: float, outline: tuple[Point, ...]) -> Perimeter:
    """Perímetro a d/2 de un área cargada c1 × c2, recortado con un contorno poligonal convexo (cabezal con esquinas
    recortadas, D-141): de cada lado queda la parte dentro del contorno; outside cuenta los lados que quedan del todo
    fuera; region es el rectángulo que encierra lo que queda de los lados."""
    left, right = centre[0] - (c1 + depth) / 2, centre[0] + (c1 + depth) / 2
    bottom, top = centre[1] - (c2 + depth) / 2, centre[1] + (c2 + depth) / 2
    corners = ((left, bottom), (right, bottom), (right, top), (left, top))
    sides = []
    for index, start in enumerate(corners):
        part = _inside_part(start, corners[(index + 1) % 4], outline)
        if part is not None:
            sides.append(Side(*part))
    points = [point for side in sides for point in (side.start, side.end)] or [centre]
    region = ((min(p[0] for p in points), min(p[1] for p in points)), (max(p[0] for p in points), max(p[1] for p in points)))
    return Perimeter(tuple(sides), 4 - len(sides), depth, region)
