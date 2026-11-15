"""Arreglos de pilotes que prueba el diseño de cabezales (D-141), generados con la separación mínima entre centros L y
la distancia E del centro de los pilotes al borde, ambas declaradas.

Familias (decisión del usuario, en lugar de transcribir los 26 patrones de la guía CRSI):
- malla nx × ny con separación L;
- triángulo de tres pilotes de lado L, con las dos esquinas superiores recortadas paralelas a sus lados, a E de ellos;
- malla con pilote central: una malla gx × gy de separación L·√2 con un pilote en el centro de cada celda (los vecinos
  quedan a L);
- filas desplazadas: r filas a L·√3/2 entre sí, desplazadas L/2, de k y k − 1 pilotes o todas de k.
Las distancias irracionales (L·√3/2, L·√2) se redondean hacia arriba al milímetro, para que ningún par de pilotes
quede a menos de L al presentar las coordenadas. El cabezal es el rectángulo que encierra los pilotes más E a cada
lado, con el origen en su centro; la columna va en el centroide del grupo.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from structurelab_rc.model.pile_cap import CornerClip, Pile

Point = tuple[float, float]


@dataclass(frozen=True)
class Arrangement:
    """Un arreglo: su nombre, los centros de los pilotes, la planta lx × ly, el desplazamiento de la columna (en el
    centroide del grupo) y las esquinas recortadas."""

    name: str
    piles: tuple[Point, ...]
    lx: float
    ly: float
    column: Point
    clips: tuple[CornerClip, ...] = ()


def _framed(name: str, points: list[Point], edge: float, clips: tuple[CornerClip, ...] = (), column: Point | None = None) -> Arrangement:
    """El rectángulo que encierra los pilotes más E, con el origen en su centro; la columna en column (en los ejes de
    points) o, si no se da, en el centroide del grupo."""
    xs, ys = [x for x, _ in points], [y for _, y in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    shifted = tuple((round(x - cx, 1), round(y - cy, 1)) for x, y in points)
    if column is None:
        column = (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))
    return Arrangement(name, shifted, max(xs) - min(xs) + 2 * edge, max(ys) - min(ys) + 2 * edge,
                       (round(column[0] - cx, 1), round(column[1] - cy, 1)), clips)


def declared(piles: Sequence[Pile], edge: float, clips: tuple[CornerClip, ...] = ()) -> Arrangement:
    """El arreglo declarado (cargas de los pilotes): sus coordenadas desde el eje de la columna, con el rectángulo que lo
    encierra más E y los recortes declarados."""
    return _framed("declarado", [(pile.x, pile.y) for pile in piles], edge, clips, column=(0.0, 0.0))


def _grid(nx: int, ny: int, spacing: float) -> list[Point]:
    return [((i - (nx - 1) / 2) * spacing, (j - (ny - 1) / 2) * spacing) for j in range(ny) for i in range(nx)]


def _triangle(spacing: float, edge: float) -> Arrangement:
    """Tres pilotes en triángulo equilátero; las esquinas superiores se recortan con rectas paralelas a los lados del
    triángulo a la distancia E de ellos."""
    height = float(math.ceil(spacing * math.sqrt(3) / 2))
    points = [(0.0, height), (-spacing / 2, 0.0), (spacing / 2, 0.0)]
    hx, top = spacing / 2 + edge, height + edge
    side = math.hypot(spacing / 2, height)
    normal = (height / side, spacing / 2 / side)  # normal unitaria hacia afuera del lado derecho
    level = normal[1] * height + edge  # la recta paralela al lado a E de él
    x_top = (level - normal[1] * top) / normal[0]
    y_side = (level - normal[0] * hx) / normal[1]
    along_x, along_y = hx - x_top, top - y_side
    if along_x <= 0 or along_y <= 0:
        return _framed("triangulo 3", points, edge)
    clips = tuple(CornerClip(corner=corner, along_x=round(along_x, 1), along_y=round(along_y, 1)) for corner in ("-x+y", "+x+y"))
    return _framed("triangulo 3 (esquinas recortadas)", points, edge, clips)


def _quincunx(gx: int, gy: int, spacing: float) -> list[Point]:
    corner = float(math.ceil(spacing * math.sqrt(2)))
    points = _grid(gx, gy, corner)
    points += [((i - (gx - 2) / 2) * corner, (j - (gy - 2) / 2) * corner) for j in range(gy - 1) for i in range(gx - 1)]
    return points


def _rows(counts: list[int], spacing: float) -> list[Point]:
    """Filas a L·√3/2, cada una centrada; las de distinta paridad quedan desplazadas L/2."""
    rise = float(math.ceil(spacing * math.sqrt(3) / 2))
    points = []
    for row, count in enumerate(counts):
        shift = spacing / 2 if row % 2 and count == counts[0] else 0.0
        points += [((i - (count - 1) / 2) * spacing + shift, row * rise) for i in range(count)]
    return points


def arrangements(count: int, spacing: float, edge: float) -> list[Arrangement]:
    """Los arreglos de exactamente count pilotes (2 o más), sin repetir forma."""
    found: list[Arrangement] = []
    for nx in range(count, 0, -1):
        if count % nx == 0 and nx >= count // nx:
            found.append(_framed(f"malla {nx} x {count // nx}", _grid(nx, count // nx, spacing), edge))
    if count == 3:  # noqa: PLR2004 - el triángulo de la guía
        found.append(_triangle(spacing, edge))
    for gx in range(2, count):
        for gy in range(2, gx + 1):
            if gx * gy + (gx - 1) * (gy - 1) == count:
                found.append(_framed(f"malla {gx} x {gy} con pilotes centrales", _quincunx(gx, gy, spacing), edge))
    for rows in range(2, count):
        for k in range(2, count):
            alternating = [k if row % 2 == 0 else k - 1 for row in range(rows)]
            if sum(alternating) == count:
                found.append(_framed(f"{rows} filas desplazadas de {k} y {k - 1}", _rows(alternating, spacing), edge))
            if rows * k == count and rows > 1:
                found.append(_framed(f"{rows} filas desplazadas de {k}", _rows([k] * rows, spacing), edge))
    unique: dict[tuple[Point, ...], Arrangement] = {}
    for item in found:
        unique.setdefault(tuple(sorted(item.piles)), item)
    return list(unique.values())
