"""Presión lineal del suelo bajo una zapata rectangular rígida, sin tracción en el contacto, en N, mm y MPa.

Solución analítica de Bellos y Bakas (2017), "Complete Analytical Solution for Linear Soil Pressure Distribution
under Rigid Rectangular Spread Footings", Int. J. Geomech. 17(7): 04017005.

Coordenadas con origen en el centroide de la base: x a lo largo de lx y y a lo largo de ly. La carga P es positiva
en compresión contra el suelo y su resultante pasa por (ex, ey). El plano p(x, y) = p0 + gx·x + gy·y vale donde es
positivo; donde es negativo no hay contacto.

Bellos mide desde la esquina más cargada, con excentricidades en valor absoluto, interceptos xn y yn del eje neutro,
y p = pmax·(1 − x'/xn − y'/yn). Aquí se usan kx = 1/xn y ky = 1/yn, que valen cero cuando el eje neutro es paralelo
a un lado y evitan la división por cero de las Ecs. 15 y 21. En la región B, la Ec. 28 se resuelve con Newton en
lugar de la iteración directa del artículo, que converge lento cerca del borde con la región C (D-053).
"""

import math
from dataclasses import dataclass

from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.polygon import Point, area_centroid, clip, linear_resultant

_EDGE_OF_BASE = 0.5  # |e|/l: la resultante sale de la base.
_QUARTER = 0.25  # |e|/l: lados rectos de las regiones A, D y E.
_NEWTON_STEPS = 50
_NEWTON_TOLERANCE = 1e-14
_RESIDUAL_LIMIT = 1e-10
_STEP = 1e-9
_EDGE = 1e-12  # En los bordes entre regiones ambas fórmulas coinciden; evita que el redondeo cambie de región.


@dataclass(frozen=True)
class SoilPressure:
    """Presión del suelo: plano p0 + gx·x + gy·y recortado en cero, y la región de Bellos (A a E)."""

    lx: float
    ly: float
    p0: float
    gx: float
    gy: float
    region: str

    def base(self) -> tuple[Point, ...]:
        hx, hy = self.lx / 2, self.ly / 2
        return ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))

    def at(self, x: float, y: float) -> float:
        return max(self.p0 + self.gx * x + self.gy * y, 0.0)

    def along_y(self, x: float, y0: float, y1: float) -> tuple[float, float]:
        """∫p dy y ∫y·p dy sobre la línea de abscisa x entre y0 y y1, con la presión recortada en cero."""
        a, b = self.p0 + self.gx * x, self.gy
        low, high = y0, y1
        if b == 0:
            if a <= 0:
                return 0.0, 0.0
        else:
            root = -a / b
            low, high = (max(low, root), high) if b > 0 else (low, min(high, root))
        if high <= low:
            return 0.0, 0.0
        return (a * (high - low) + b * (high**2 - low**2) / 2,
                a * (high**2 - low**2) / 2 + b * (high**3 - low**3) / 3)

    def corners(self) -> tuple[float, float, float, float]:
        """Presión en las esquinas (−x, −y), (+x, −y), (+x, +y) y (−x, +y)."""
        a, b, c, d = (self.at(x, y) for x, y in self.base())
        return a, b, c, d

    @property
    def pmax(self) -> float:
        return max(self.corners())

    def contact(self, polygon: tuple[Point, ...] | None = None) -> tuple[Point, ...]:
        """Parte del polígono (por defecto, la base) en contacto con el suelo."""
        return clip(self.base() if polygon is None else polygon, (self.gx, self.gy), -self.p0)

    def contact_fraction(self) -> float:
        return area_centroid(self.contact())[0] / (self.lx * self.ly)

    def resultant(self, polygon: tuple[Point, ...]) -> tuple[float, float, float]:
        """Fuerza del suelo sobre la parte del polígono en contacto y sus momentos estáticos: ∫p dA, ∫x·p dA, ∫y·p dA."""
        return linear_resultant(self.contact(polygon), (self.p0, self.gx, self.gy))


def _trapezoid(u: float, v: float, length: float, width: float, pm: float) -> tuple[float, float, float]:
    """Región D (Ecs. 21 y 22) en coordenadas normalizadas: pmax, 1/xn y 1/yn. La región E es la misma, transpuesta."""
    s = math.sqrt(1 - 12 * u * u)
    pmax = pm / 3 * (2 - s) * (1 + 6 * u + s) / (0.5 - v)
    kx = 12 * u / (length * (1 + 6 * u + s))
    # (1 + 2u − s)/u escrito como 2 + 12u/(1 + s), que no se indetermina con u = 0.
    yn = 0.5 * width * (0.5 - v) * (2 + s) * (2 + 12 * u / (1 + s)) / (1 + 4 * u * u)
    return pmax, kx, 1 / yn


def _trapezoid_limit(t: float) -> float:
    """Borde curvo de las regiones D y E (Ecs. 24 y 27)."""
    s = math.sqrt(1 - 12 * t * t)
    return 0.5 - (2 - s) * (1 + 2 * t + s) / (6 * (1 + 4 * t))


def _pentagon_map(a: float, b: float, u: float, v: float) -> tuple[float, float]:
    """Lado derecho de la Ec. 28 con a = lx/xn y b = ly/yn: devuelve los nuevos a y b."""
    ca, cb = 1 - a, 1 - b
    numerator = 1 - ca**3 - cb**3
    common = 1 - ca**4 - cb**4
    return (common - 4 * ca**3 * a) / (4 * (0.5 - u) * numerator), (common - 4 * cb**3 * b) / (4 * (0.5 - v) * numerator)


def _pentagon(u: float, v: float, lx: float, ly: float, pm: float) -> tuple[float, float, float]:
    """Región B: Ec. 28 resuelta con Newton desde los interceptos de la región C, y pmax de la Ec. 30."""
    w = 1 + 6 * u + 6 * v
    a, b = min(12 * u / w, 1.0), min(12 * v / w, 1.0)
    for _ in range(_NEWTON_STEPS):
        fa, fb = _pentagon_map(a, b, u, v)
        ra, rb = fa - a, fb - b
        ga = _pentagon_map(a + _STEP, b, u, v)
        gb = _pentagon_map(a, b + _STEP, u, v)
        j11, j21 = (ga[0] - fa) / _STEP - 1, (ga[1] - fb) / _STEP
        j12, j22 = (gb[0] - fa) / _STEP, (gb[1] - fb) / _STEP - 1
        det = j11 * j22 - j12 * j21
        da, db = (-ra * j22 + rb * j12) / det, (-rb * j11 + ra * j21) / det
        a, b = min(max(a + da, _STEP), 1.0), min(max(b + db, _STEP), 1.0)
        if abs(da) + abs(db) < _NEWTON_TOLERANCE:
            break
    fa, fb = _pentagon_map(a, b, u, v)
    if abs(fa - a) + abs(fb - b) > _RESIDUAL_LIMIT:
        raise NoEquilibrium("la presión de la región B no convergió")
    pmax = 6 * pm * a * b / (1 - (1 - a) ** 3 - (1 - b) ** 3)
    return pmax, a / lx, b / ly


def footing_pressure(lx: float, ly: float, load: float, ex: float, ey: float) -> SoilPressure:
    """Presión bajo una base lx × ly con carga P (> 0) en (ex, ey); NoEquilibrium si la resultante sale de la base."""
    if load <= 0:
        raise NoEquilibrium("la carga sobre el suelo no es de compresión")
    u, v = abs(ex) / lx, abs(ey) / ly
    if u >= _EDGE_OF_BASE or v >= _EDGE_OF_BASE:
        raise NoEquilibrium("la resultante cae fuera de la base")
    pm = load / (lx * ly)  # Ec. 8
    if u + v <= 1 / 6 + _EDGE:  # Región C, Ecs. 15 a 17.
        w = 1 + 6 * u + 6 * v
        region, pmax, kx, ky = "C", pm * w, 12 * u / (lx * w), 12 * v / (ly * w)
    elif u >= _QUARTER and v >= _QUARTER:  # Región A, Ecs. 18 a 20.
        region, pmax = "A", 3 * pm / (8 * (0.5 - u) * (0.5 - v))
        kx, ky = 1 / (4 * lx * (0.5 - u)), 1 / (4 * ly * (0.5 - v))
    elif u <= _QUARTER and v >= _trapezoid_limit(u):  # Región D, Ecs. 21 a 24.
        region = "D"
        pmax, kx, ky = _trapezoid(u, v, lx, ly, pm)
    elif v <= _QUARTER and u >= _trapezoid_limit(v):  # Región E, Ecs. 25 a 27.
        region = "E"
        pmax, ky, kx = _trapezoid(v, u, ly, lx, pm)
    else:  # Región B, Ecs. 28 a 31.
        region = "B"
        pmax, kx, ky = _pentagon(u, v, lx, ly, pm)
    # Ec. 13 trasladada al centroide (Ec. 14): la esquina más cargada está del lado de la excentricidad.
    sx, sy = math.copysign(1.0, ex), math.copysign(1.0, ey)
    p0 = pmax * (1 - kx * lx / 2 - ky * ly / 2)
    return SoilPressure(lx, ly, p0, pmax * kx * sx, pmax * ky * sy, region)
