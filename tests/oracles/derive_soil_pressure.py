"""Deriva el oráculo de presión del suelo bajo una zapata rígida (tests/oracles/mechanics/soil_pressure.json).

No importa el paquete. Dos fuentes independientes de las fórmulas de Bellos y Bakas (2017):

1. Casos frontera del artículo con resultado cerrado (casos 1 a 5).
2. Equilibrio resuelto por Newton: se busca el plano p0 + gx·x + gy·y, recortado en cero, cuya resultante sobre la
   base es P en (ex, ey). Las integrales sobre la zona en contacto son exactas (teorema de Green). La región se
   deduce del número de esquinas comprimidas: 4 → C, 3 → B, 2 → D (lado paralelo a x) o E (paralelo a y), 1 → A.

Uso: python tests/oracles/derive_soil_pressure.py
"""

import json
import random
from pathlib import Path

LX, LY, LOAD = 2000.0, 1500.0, 1.0e6  # mm, mm, N
PM = LOAD / (LX * LY)
OUT = Path(__file__).parent / "mechanics" / "soil_pressure.json"


def _base(lx: float, ly: float) -> list[tuple[float, float]]:
    return [(-lx / 2, -ly / 2), (lx / 2, -ly / 2), (lx / 2, ly / 2), (-lx / 2, ly / 2)]


def _clip(poly: list[tuple[float, float]], plane: list[float]) -> list[tuple[float, float]]:
    q0, gx, gy = plane
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        fp, fq = q0 + gx * p[0] + gy * p[1], q0 + gx * q[0] + gy * q[1]
        if fp >= 0:
            out.append(p)
        if (fp >= 0) != (fq >= 0):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def _moments(poly: list[tuple[float, float]]) -> list[float]:
    s = [0.0] * 6
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        cr = x1 * y2 - x2 * y1
        s[0] += cr / 2
        s[1] += (x1 + x2) * cr / 6
        s[2] += (y1 + y2) * cr / 6
        s[3] += (x1 * x1 + x1 * x2 + x2 * x2) * cr / 12
        s[4] += (x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) * cr / 24
        s[5] += (y1 * y1 + y1 * y2 + y2 * y2) * cr / 12
    return s


def _resultants(plane: list[float], lx: float, ly: float) -> tuple[float, float, float, float]:
    poly = _clip(_base(lx, ly), plane)
    if len(poly) < 3:
        return 0.0, 0.0, 0.0, 0.0
    m = _moments(poly)
    q0, gx, gy = plane
    return (q0 * m[0] + gx * m[1] + gy * m[2], q0 * m[1] + gx * m[3] + gy * m[4], q0 * m[2] + gx * m[4] + gy * m[5],
            m[0])


def _solve3(a: list[list[float]], b: list[float]) -> list[float]:
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(3):
        piv = max(range(c, 3), key=lambda i: abs(m[i][c]))
        m[c], m[piv] = m[piv], m[c]
        for i in range(3):
            if i != c:
                f = m[i][c] / m[c][c]
                m[i] = [m[i][j] - f * m[c][j] for j in range(4)]
    return [m[i][3] / m[i][i] for i in range(3)]


def solve(lx: float, ly: float, load: float, ex: float, ey: float) -> tuple[list[float], float]:
    """Plano sin tracción en equilibrio con P en (ex, ey), por Newton con jacobiano por diferencias."""
    plane = [load / (lx * ly), 12 * load * ex / (ly * lx**3), 12 * load * ey / (lx * ly**3)]
    target = (load, load * ex, load * ey)
    scale = (load, load * lx, load * ly)

    def error(r: tuple[float, float, float, float]) -> float:
        return max(abs(r[i] - target[i]) / scale[i] for i in range(3))

    for _ in range(300):
        r = _resultants(plane, lx, ly)
        if error(r) < 1e-15:
            break
        jac = []
        for k in range(3):
            h = 1e-7 * max(abs(plane[k]), 1e-12)
            shifted = plane[:]
            shifted[k] += h
            rk = _resultants(shifted, lx, ly)
            jac.append([(rk[i] - r[i]) / h for i in range(3)])
        step = _solve3([[jac[k][i] for k in range(3)] for i in range(3)], [target[i] - r[i] for i in range(3)])
        lam, current = 1.0, error(r)
        while lam > 1e-6:
            trial = [plane[i] + lam * step[i] for i in range(3)]
            if error(_resultants(trial, lx, ly)) < current:
                break
            lam /= 2
        plane = trial
    return plane, _resultants(plane, lx, ly)[3] / (lx * ly)


def _region(corners: list[float], lx: float, ly: float, plane: list[float]) -> str:
    compressed = sum(1 for c in corners if c > 1e-9 * max(corners))
    if compressed == 2:
        # Lado comprimido completo: paralelo a x si las dos esquinas comprimidas comparten y.
        return "D" if abs(plane[2] * ly) > abs(plane[1] * lx) else "E"
    return {4: "C", 3: "B", 1: "A"}[compressed]


def _case(case_id: str, ex: float, ey: float, source: str) -> dict[str, object]:
    plane, fraction = solve(LX, LY, LOAD, ex, ey)
    corners = [max(plane[0] + plane[1] * x + plane[2] * y, 0.0) for x, y in _base(LX, LY)]
    return {"id": case_id, "source": source, "ex": ex, "ey": ey, "region": _region(corners, LX, LY, plane),
            "corners": [round(c, 12) for c in corners], "contact_fraction": round(fraction, 12)}


def main() -> None:
    closed = [
        # Caso 1 (Ec. 33): excentricidad en una dirección dentro del núcleo, p = pm(1 ± 6e/l).
        {"id": "caso1", "source": "Bellos caso 1, Ec. 33", "ex": 200.0, "ey": 0.0, "region": "C",
         "corners": [PM * (1 - 6 * 200 / LX), PM * (1 + 6 * 200 / LX), PM * (1 + 6 * 200 / LX), PM * (1 - 6 * 200 / LX)],
         "contact_fraction": 1.0},
        # Caso 2 (Ec. 36): una dirección fuera del núcleo, pmax = 2P/(3·ly·(lx/2 − e)), contacto 3(lx/2 − e)/lx.
        {"id": "caso2", "source": "Bellos caso 2, Ec. 36", "ex": -500.0, "ey": 0.0, "region": "E",
         "corners": [2 * LOAD / (3 * LY * (LX / 2 - 500)), 0.0, 0.0, 2 * LOAD / (3 * LY * (LX / 2 - 500))],
         "contact_fraction": 3 * (LX / 2 - 500) / LX},
        # Caso 3 (Ec. 40): punto c, ex = lx/6: eje neutro sobre el lado opuesto, pmax = 2pm.
        {"id": "caso3", "source": "Bellos caso 3, Ec. 40", "ex": LX / 6, "ey": 0.0, "region": "C",
         "corners": [0.0, 2 * PM, 2 * PM, 0.0], "contact_fraction": 1.0},
        # Caso 4 (Ecs. 42 y 43): punto a, ex = lx/4 y ey = ly/4: eje neutro en la diagonal, pmax = 6pm.
        {"id": "caso4", "source": "Bellos caso 4, Ecs. 42 y 43", "ex": LX / 4, "ey": LY / 4, "region": "A",
         "corners": [0.0, 0.0, 6 * PM, 0.0], "contact_fraction": 0.5},
        # Caso 5 (Ecs. 46 y 47): sobre la línea bc del núcleo (u + v = 1/6, u = 1/9, v = 1/18): pmax = 2pm en
        # (−x, −y), pp = 12·pm·v en (+x, −y), pr = 0 en (+x, +y) y pq = pm(1 + 6u − 6v) en (−x, +y).
        {"id": "caso5", "source": "Bellos caso 5, Ecs. 46 y 47", "ex": -LX / 9, "ey": -LY / 18, "region": "C",
         "corners": [2 * PM, 12 * PM / 18, 0.0, PM * (1 + 6 / 9 - 6 / 18)], "contact_fraction": 1.0},
    ]
    random.seed(20171)
    solved = [_case(f"newton{i:02d}", random.uniform(-0.48, 0.48) * LX, random.uniform(-0.48, 0.48) * LY,
                    "equilibrio por Newton") for i in range(40)]
    # Puntos en cada región y cerca de sus bordes.
    for name, (u, v) in {"C": (0.08, -0.05), "A": (-0.3, 0.35), "D": (0.1, 0.3), "E": (-0.35, -0.1), "B": (0.12, 0.12),
                         "B-borde-C": (0.01, 0.1595), "B-borde-D": (0.2, 0.245), "D-u0": (0.0, 0.3)}.items():
        solved.append(_case(f"region-{name}", u * LX, v * LY, "equilibrio por Newton"))
    data = {"description": "Presión del suelo bajo zapata rígida rectangular sin tracción (Bellos y Bakas 2017). "
                           "Esquinas en el orden (−x, −y), (+x, −y), (+x, +y), (−x, +y); MPa.",
            "lx": LX, "ly": LY, "load": LOAD, "tolerance_rel": 1e-9, "cases": closed + solved}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
