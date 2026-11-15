"""Deriva el oráculo del diseño de cabezales (D-141) para los dos perfiles. No importa el paquete.

1. Arreglos de n pilotes con la separación L y el borde E (familias de D-141), en ejes con el origen en el centro del
   rectángulo que encierra los pilotes más E; las distancias irracionales se redondean hacia arriba al milímetro:
   - malla nx × ny (nx ≥ ny, nx·ny = n) a L;
   - triángulo (n = 3): vértices (0, ⌈L√3/2⌉), (±L/2, 0). Cada esquina superior se recorta con la recta paralela al lado
     inclinado a E de él. Por triángulos semejantes, la recta corta la horizontal superior (y = h + E) y la vertical del
     borde (x = L/2 + E) a las distancias along_x = (L/2 + E) − x_sup y along_y = (h + E) − y_lat de la esquina;
   - malla gx × gy (gy ≤ gx) a ⌈L√2⌉ con un pilote en el centro de cada celda: n = gx·gy + (gx − 1)(gy − 1);
   - r filas a ⌈L√3/2⌉, alternando k y k − 1 pilotes centrados, o r filas de k desplazadas L/2 las impares.
   La columna va en el centroide del grupo; el oráculo da la planta, los pilotes ordenados, la columna y los recortes.
2. Cota inferior del número de pilotes: n0 = máx(2, ⌈máx P/(η·fs·Qa)⌉) con las cargas de servicio (fs con sismo).
3. Costo de una solución: (A·h + cx·cy·hp)/10⁹·precio(f'c) + acero·precio_acero + n·precio_pilote, con A el
   rectángulo menos los triángulos recortados.

Uso: python tests/oracles/derive_pile_cap_design.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
SPACING, EDGE = 1200.0, 500.0


def _framed(name: str, points: list[tuple[float, float]], clips: list[dict] | None = None) -> dict:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    gx, gy = sum(xs) / len(xs) - cx, sum(ys) / len(ys) - cy
    piles = sorted([round(x - cx, 1), round(y - cy, 1)] for x, y in points)
    return {"name": name, "lx": max(xs) - min(xs) + 2 * EDGE, "ly": max(ys) - min(ys) + 2 * EDGE, "piles": piles,
            "column": [round(gx, 1), round(gy, 1)], "clips": clips or []}


def _triangle() -> dict:
    h = math.ceil(SPACING * math.sqrt(3) / 2)
    half = SPACING / 2
    side = math.hypot(half, h)
    # Punto de la recta paralela al lado derecho, a E del vértice inferior derecho (normal hacia afuera (h, L/2)/lado).
    px, py = half + EDGE * h / side, EDGE * half / side
    slope = -h / half  # pendiente del lado: dy/dx
    top, right = h + EDGE, half + EDGE
    x_top = px + (top - py) / slope
    y_right = py + slope * (right - px)
    along_x, along_y = round(right - x_top, 1), round(top - y_right, 1)
    clips = [{"corner": corner, "along_x": along_x, "along_y": along_y} for corner in ("-x+y", "+x+y")]
    return _framed("triangulo 3 (esquinas recortadas)", [(0.0, float(h)), (-half, 0.0), (half, 0.0)], clips)


def _grid(nx: int, ny: int, step: float) -> list[tuple[float, float]]:
    return [(i * step, j * step) for j in range(ny) for i in range(nx)]


def _arrangements(n: int) -> list[dict]:
    found = []
    for nx in range(n, 0, -1):
        if n % nx == 0 and nx >= n // nx:
            found.append(_framed(f"malla {nx} x {n // nx}", _grid(nx, n // nx, SPACING)))
    if n == 3:
        found.append(_triangle())
    diagonal = math.ceil(SPACING * math.sqrt(2))
    for gx in range(2, n):
        for gy in range(2, gx + 1):
            if gx * gy + (gx - 1) * (gy - 1) == n:
                points = _grid(gx, gy, diagonal) + [(diagonal / 2 + p[0], diagonal / 2 + p[1]) for p in _grid(gx - 1, gy - 1, diagonal)]
                found.append(_framed(f"malla {gx} x {gy} con pilotes centrales", points))
    rise = math.ceil(SPACING * math.sqrt(3) / 2)
    for rows in range(2, n):
        for k in range(2, n):
            counts = [k if r % 2 == 0 else k - 1 for r in range(rows)]
            if sum(counts) == n:
                points = [((i - (c - 1) / 2) * SPACING, r * rise) for r, c in enumerate(counts) for i in range(c)]
                found.append(_framed(f"{rows} filas desplazadas de {k} y {k - 1}", points))
            if rows * k == n:
                points = [((i - (k - 1) / 2) * SPACING + (SPACING / 2 if r % 2 else 0.0), r * rise) for r in range(rows) for i in range(k)]
                found.append(_framed(f"{rows} filas desplazadas de {k}", points))
    unique: dict[str, dict] = {}
    for item in found:
        unique.setdefault(json.dumps(item["piles"]), item)
    return list(unique.values())


def _start_count() -> dict:
    loads = [(2000.0, False), (2100.0, True), (900.0, True)]
    capacity, efficiency, seismic = 850.0, 0.85, 1.33
    count = max(p / (efficiency * (seismic if s else 1.0) * capacity) for p, s in loads)
    return {"loads": [{"P_kN": p, "seismic": s} for p, s in loads], "capacity_kN": capacity, "efficiency": efficiency,
            "seismic_factor": seismic, "count": max(2, math.ceil(count - 1e-9))}


def _cost() -> dict:
    lx, ly, h, clips = 2200.0, 2040.0, 900.0, [(811.2, 1406.1), (811.2, 1406.1)]
    area = lx * ly - sum(a * b / 2 for a, b in clips)
    cx = cy = 500.0
    pedestal, steel, piles = 300.0, 215.4, 3
    prices = {"concrete": 747582.0, "steel": 4385.0, "pile": 9500000.0}
    concrete = (area * h + cx * cy * pedestal) / 1e9
    return {"lx": lx, "ly": ly, "h": h, "clips": [list(c) for c in clips], "column": [cx, cy], "pedestal": pedestal,
            "steel_kg": steel, "piles": piles, "prices": prices, "concrete_m3": concrete,
            "cost": concrete * prices["concrete"] + steel * prices["steel"] + piles * prices["pile"]}


def main() -> None:
    data = {"spacing": SPACING, "edge": EDGE, "tolerance_rel": 1e-9,
            "arrangements": {str(n): _arrangements(n) for n in range(2, 14)},
            "start_count": _start_count(), "cost": _cost()}
    for folder in ("aci_318_25", "nsr_10"):  # la geometría y el costo no dependen del perfil
        (HERE / folder / "derived_pile_cap_design.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
