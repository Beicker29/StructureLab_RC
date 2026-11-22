"""Deriva el oráculo de presión del suelo bajo una zapata rígida de planta poligonal (D-164):
tests/oracles/mechanics/polygon_pressure.json.

No importa el paquete. Mismo modelo que Bellos y Bakas (2017): plano p0 + gx·x + gy·y recortado en cero cuya resultante
sobre la planta es P en (ex, ey). Se calcula de otra manera que el paquete:

1. La planta se da como unión de piezas convexas (el trapecio es una; la T y la L, dos rectángulos). Cada pieza se
   recorta con el semiplano p ≥ 0 y se parte en triángulos desde su primer vértice. En cada triángulo, ∫p dA es el área
   por el promedio de los vértices y ∫x·p dA, ∫y·p dA, con la regla de los puntos medios de los lados (exacta para
   polinomios de grado 2).
2. El equilibrio se resuelve con Newton y jacobiano por diferencias centrales, con paso amortiguado.
3. Trapecio con la resultante sobre su eje de simetría (excentricidad solo a lo largo de x): el eje neutro es paralelo a
   los lados paralelos, x = c, y p = k·(x − c) del lado cargado. Con el ancho w(x) lineal, las integrales son
   polinomios de c y c sale por bisección de ∫x·w·(x − c) dx = e·∫w·(x − c) dx; k = P/∫w·(x − c) dx. Es la forma
   cerrada con que se compara el Newton.

Las coordenadas van desde el centroide de la planta, que el oráculo calcula con sus piezas.

Uso: python tests/oracles/derive_polygon_pressure.py
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).parent / "mechanics" / "polygon_pressure.json"
LOAD = 1.5e6  # N

Point = tuple[float, float]


def _clip(piece: list[Point], plane: tuple[float, float, float]) -> list[Point]:
    q0, gx, gy = plane
    out: list[Point] = []
    for i, p in enumerate(piece):
        q = piece[(i + 1) % len(piece)]
        fp, fq = q0 + gx * p[0] + gy * p[1], q0 + gx * q[0] + gy * q[1]
        if fp >= 0:
            out.append(p)
        if (fp >= 0) != (fq >= 0):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _triangle(a: Point, b: Point, c: Point, plane: tuple[float, float, float]) -> tuple[float, float, float]:
    area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2

    def p(point: Point) -> float:
        return plane[0] + plane[1] * point[0] + plane[2] * point[1]

    mids = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2), ((c[0] + a[0]) / 2, (c[1] + a[1]) / 2)]
    force = area * (p(a) + p(b) + p(c)) / 3
    sx = area * sum(m[0] * p(m) for m in mids) / 3
    sy = area * sum(m[1] * p(m) for m in mids) / 3
    return force, sx, sy


def _resultant(pieces: list[list[Point]], plane: tuple[float, float, float]) -> tuple[float, float, float]:
    total = [0.0, 0.0, 0.0]
    for piece in pieces:
        kept = _clip(piece, plane)
        for i in range(1, len(kept) - 1):
            for k, value in enumerate(_triangle(kept[0], kept[i], kept[i + 1], plane)):
                total[k] += value
    return total[0], total[1], total[2]


def _centroid(pieces: list[list[Point]]) -> Point:
    area, sx, sy = _resultant(pieces, (1.0, 0.0, 0.0))
    return sx / area, sy / area


def _solve3(m: list[list[float]], r: list[float]) -> list[float]:
    """Eliminación de Gauss con pivoteo parcial."""
    a = [row[:] + [value] for row, value in zip(m, r, strict=True)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(a[row][col]))
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col + 1, 3):
            f = a[row][col] / a[col][col]
            a[row] = [x - f * y for x, y in zip(a[row], a[col], strict=True)]
    x = [0.0, 0.0, 0.0]
    for row in (2, 1, 0):
        x[row] = (a[row][3] - sum(a[row][k] * x[k] for k in range(row + 1, 3))) / a[row][row]
    return x


def _newton(pieces: list[list[Point]], ex: float, ey: float, scale: float, load: float = LOAD) -> tuple[float, float, float]:
    target = (load, load * ex, load * ey)
    area = _resultant(pieces, (1.0, 0.0, 0.0))[0]
    theta = [load / area, 0.0, 0.0]
    steps = (load / area * 1e-6, load / area / scale * 1e-6, load / area / scale * 1e-6)

    def residual(t: list[float]) -> list[float]:
        got = _resultant(pieces, (t[0], t[1], t[2]))
        return [got[k] - target[k] for k in range(3)]

    def norm(r: list[float]) -> float:
        return math.hypot(r[0], r[1] / scale, r[2] / scale) / load

    r = residual(theta)
    for _ in range(200):
        if norm(r) < 1e-13:
            break
        jac = [[0.0] * 3 for _ in range(3)]
        for k in range(3):
            up, down = theta[:], theta[:]
            up[k] += steps[k]
            down[k] -= steps[k]
            ru, rd = residual(up), residual(down)
            for row in range(3):
                jac[row][k] = (ru[row] - rd[row]) / (2 * steps[k])
        delta = _solve3(jac, [-value for value in r])
        length = 1.0
        while length > 1e-12:
            trial = [theta[k] + length * delta[k] for k in range(3)]
            rt = residual(trial)
            if norm(rt) < norm(r):
                theta, r = trial, rt
                break
            length /= 2
        else:
            break
    assert norm(r) < 1e-9, norm(r)
    return theta[0], theta[1], theta[2]


def _trapezoid_closed(length: float, w0: float, w1: float, e: float) -> tuple[float, float, float] | None:
    """Trapecio simétrico de largo `length` (x de −L/2 a L/2 respecto a su mitad), anchos w0 en −L/2 y w1 en +L/2, y la
    resultante en x = e (desde la mitad). Devuelve (p0, gx, gy) desde el centroide, o None si hay contacto total."""
    half = length / 2
    slope = (w1 - w0) / length

    def w_moments(a: float, b: float) -> tuple[float, float, float]:
        # ∫w, ∫x·w, ∫x²·w de a a b con w = w0 + slope·(x + half).
        c0 = w0 + slope * half

        def prim(x: float) -> tuple[float, float, float]:
            return (c0 * x + slope * x**2 / 2, c0 * x**2 / 2 + slope * x**3 / 3, c0 * x**3 / 3 + slope * x**4 / 4)

        pa, pb = prim(a), prim(b)
        return pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]

    area, first, second = w_moments(-half, half)
    xc = first / area
    inertia = second - area * xc**2
    k_full = LOAD * (e - xc) / inertia  # contacto total: p = P/A + P·(e − xc)·(x − xc)/I
    p_low = LOAD / area + k_full * (-half - xc)
    p_high = LOAD / area + k_full * (half - xc)
    if min(p_low, p_high) >= 0:
        return None
    sign = 1.0 if e > xc else -1.0

    def ratio(c: float) -> float:
        a, b = (c, half) if sign > 0 else (-half, c)
        m0, m1, m2 = w_moments(a, b)
        force = sign * (m1 - c * m0)  # ∫w·(x − c)·sign
        moment = sign * (m2 - c * m1)
        return moment / force - e

    low, high = (-half, e) if sign > 0 else (e, half)
    for _ in range(200):
        mid = (low + high) / 2
        # En los dos sentidos, el centroide de la presión crece con c: en c = e queda de un lado y en el borde, del otro.
        if ratio(mid) > 0:
            high = mid
        else:
            low = mid
    c = (low + high) / 2
    a, b = (c, half) if sign > 0 else (-half, c)
    m0, m1, _ = w_moments(a, b)
    k = LOAD / (sign * (m1 - c * m0))
    # p = sign·k·(x − c) con x desde la mitad; en coordenadas desde el centroide, x = x' + xc.
    gx = sign * k
    return gx * (xc - c), gx, 0.0


def _shift(pieces: list[list[Point]]) -> tuple[list[list[Point]], Point]:
    cx, cy = _centroid(pieces)
    return [[(x - cx, y - cy) for x, y in piece] for piece in pieces], (cx, cy)


def _outline_trapezoid(length: float, low: tuple[float, float], high: tuple[float, float]) -> list[Point]:
    """Trapecio con lados paralelos en x = ∓L/2: low = (y mínimo, y máximo) en −L/2 y high en +L/2."""
    half = length / 2
    return [(-half, low[0]), (half, high[0]), (half, high[1]), (-half, low[1])]


SHAPES = {
    "trapecio-simetrico": ("trapecio simétrico de 6 m, anchos 3.0 m (−x) y 1.6 m (+x)",
                           [_outline_trapezoid(6000.0, (-1500.0, 1500.0), (-800.0, 800.0))],
                           _outline_trapezoid(6000.0, (-1500.0, 1500.0), (-800.0, 800.0))),
    "trapecio-lado-recto": ("trapecio de 6 m con el lado −y recto (lindero), anchos 2.8 m y 1.4 m",
                            [_outline_trapezoid(6000.0, (-1400.0, 1400.0), (-1400.0, 0.0))],
                            _outline_trapezoid(6000.0, (-1400.0, 1400.0), (-1400.0, 0.0))),
    "planta-t": ("planta en T: 3.5 m de 2.8 m de ancho y 3.0 m de 1.6 m, centrados en el eje",
                 [[(-3500.0, -1400.0), (0.0, -1400.0), (0.0, 1400.0), (-3500.0, 1400.0)],
                  [(0.0, -800.0), (3000.0, -800.0), (3000.0, 800.0), (0.0, 800.0)]],
                 [(-3500.0, -1400.0), (0.0, -1400.0), (0.0, -800.0), (3000.0, -800.0), (3000.0, 800.0), (0.0, 800.0),
                  (0.0, 1400.0), (-3500.0, 1400.0)]),
    "planta-l": ("planta en L: 3.5 m de 2.8 m de ancho y 3.0 m de 1.6 m, alineados por el borde −y",
                 [[(-3500.0, -1400.0), (0.0, -1400.0), (0.0, 1400.0), (-3500.0, 1400.0)],
                  [(0.0, -1400.0), (3000.0, -1400.0), (3000.0, 200.0), (0.0, 200.0)]],
                 [(-3500.0, -1400.0), (3000.0, -1400.0), (3000.0, 200.0), (0.0, 200.0), (0.0, 1400.0), (-3500.0, 1400.0)]),
}

# Excentricidades (mm, desde el centroide): contacto total, parcial uniaxial y parcial biaxial.
LOADS = [(150.0, 80.0), (-900.0, 0.0), (1100.0, 0.0), (900.0, 450.0), (-1300.0, -600.0), (400.0, -700.0)]


def main() -> None:
    cases = []
    for shape_id, (text, pieces, outline) in SHAPES.items():
        moved, (cx, cy) = _shift(pieces)
        outline_moved = [(x - cx, y - cy) for x, y in outline]
        scale = max(max(x for x, _ in outline) - min(x for x, _ in outline), max(y for _, y in outline) - min(y for _, y in outline))
        for ex, ey in LOADS:
            p0, gx, gy = _newton(moved, ex, ey, scale)
            corners = [max(p0 + gx * x + gy * y, 0.0) for x, y in outline_moved]
            contact = _resultant(moved, (p0, gx, gy))
            area = _resultant(moved, (1.0, 0.0, 0.0))[0]
            kept = sum(_resultant([_clip(piece, (p0, gx, gy))], (1.0, 0.0, 0.0))[0] for piece in moved)
            case = {"id": f"{shape_id} e=({ex:g}, {ey:g})", "description": text, "outline": outline_moved, "load_N": LOAD,
                    "ex": ex, "ey": ey, "p0": p0, "gx": gx, "gy": gy, "vertex_pressures": corners,
                    "contact_fraction": kept / area, "partial": min(p0 + gx * x + gy * y for x, y in outline_moved) < 0,
                    "check_resultant": list(contact)}
            if shape_id == "trapecio-simetrico" and ey == 0.0:
                closed = _trapezoid_closed(6000.0, 3000.0, 1600.0, ex + cx)
                if closed is not None:
                    case["closed_form"] = list(closed)
                    limit = LOAD / area / scale
                    assert all(abs(a - b) <= 1e-7 * max(abs(b), limit) for a, b in zip((p0, gx, gy), closed, strict=True)), closed
            cases.append(case)
    data = {"description": "Presión lineal sin tracción bajo plantas poligonales (D-164): las ecuaciones de equilibrio de "
                           "Bellos y Bakas resueltas con piezas convexas en triángulos y Newton con jacobiano por "
                           "diferencias; el trapecio con excentricidad sobre su eje, contra su forma cerrada.",
            "tolerance_rel": 1e-7, "cases": cases}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
