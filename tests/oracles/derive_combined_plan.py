"""Deriva el oráculo de la zapata combinada trapezoidal y en planta T o L (D-164): tests/oracles/derived_combined_plan.json.

No importa el paquete. La planta se arma aquí desde su declaración (trapecio o tramos, en el sistema a, t con el origen en
el borde negativo y la línea de referencia) como unión de piezas convexas; el centroide sale de las piezas y las columnas
pasan a él. Dirección principal X (la rotación de la Y global la revisa la prueba aparte). Para cada caso:

1. Resultante en el centroide (columnas con F = P + fd·(γc·A·hp − (γf·hf + qD)·A) − fl·qL·A en su eje, su par y su
   cortante a la altura h + hp; la zapata, el relleno y las sobrecargas en el centroide) y la presión por las ecuaciones
   de Bellos sobre la planta, resueltas con el Newton de derive_polygon_pressure.py (triángulos y diferencias).
2. Viga: cuerpo libre a la izquierda de x, con la planta recortada en x' ≤ x y la carga neta (presión recortada en cero
   menos w): V, M (positivo tracciona abajo) y T = ∫y·q − Σ(F·y − Mx + H·Vy) de las columnas a la izquierda.
3. Franja de cada columna: ancho columna + d/2 a cada lado (d de las barras y inferiores, con las x más cerca de la cara),
   recortado con la base y en el punto medio si se monta con la vecina; bordes locales en el eje de la columna o, si la
   franja cruza un escalón, los del tramo más angosto. La fuerza F de la columna con la forma de la presión en su línea,
   q(y) = s·p(y) − w·b, y M en cada cara hacia su borde.
4. Punzonamiento (planta convexa): el rectángulo a d/2 recortado con la planta (Cyrus-Beck aquí), b0 = lo que queda
   dentro y los lados descontados por las esquinas dentro: 4 → 0, 3 → 1, 2 → 1, 1 → 2.
5. Volcamiento (servicio): alrededor de cada lado de la envolvente convexa, resistente N·d (d del centroide al lado) y
   volcador N·(e·n); rige la mayor razón FS·Mo/Mr.

Uso: python tests/oracles/derive_combined_plan.py
"""

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).parent
OUT = HERE / "derived_combined_plan.json"


def _load_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PP = _load_module("derive_polygon_pressure")
_F = _load_module("derive_footing_flexure")
_C = _load_module("derive_combined_service")

GAMMA_C, GAMMA_F = 24e-6, 18e-6  # N/mm³
BARS = _F.BARS
Point = tuple[float, float]


def _pieces(plan: dict) -> list[list[Point]]:
    """Piezas convexas (a, t), antihorarias."""
    if plan["shape"] == "trapezoid":
        length, start, end = plan["length"], plan["start"], plan["end"]
        return [[(0.0, start["low"]), (length, end["low"]), (length, end["high"]), (0.0, start["high"])]]
    pieces, a = [], 0.0
    for part in plan["parts"]:
        pieces.append([(a, part["low"]), (a + part["length"], part["low"]), (a + part["length"], part["high"]), (a, part["high"])])
        a += part["length"]
    return pieces


def _across(plan: dict, centroid: Point, x: float) -> tuple[float, float]:
    """Bordes −Y y +Y en x (coordenadas desde el centroide), leídos de la declaración."""
    a = x + centroid[0]
    if plan["shape"] == "trapezoid":
        r = a / plan["length"]
        low = plan["start"]["low"] + r * (plan["end"]["low"] - plan["start"]["low"])
        high = plan["start"]["high"] + r * (plan["end"]["high"] - plan["start"]["high"])
        return low - centroid[1], high - centroid[1]
    start = 0.0
    for part in plan["parts"]:
        if start <= a <= start + part["length"]:
            return part["low"] - centroid[1], part["high"] - centroid[1]
        start += part["length"]
    raise ValueError(a)


def _steps(plan: dict, centroid: Point) -> list[float]:
    if plan["shape"] == "trapezoid":
        return []
    out, a = [], 0.0
    for part in plan["parts"][:-1]:
        a += part["length"]
        out.append(a - centroid[0])
    return out


def _clip_x(piece: list[Point], x: float) -> list[Point]:
    """La parte de la pieza con x' ≤ x (q = x − x' ≥ 0)."""
    return _PP._clip(piece, (x, -1.0, 0.0))


def _net(pieces: list[list[Point]], plane: tuple[float, float, float], w: float) -> tuple[float, float, float]:
    force, sx, sy = _PP._resultant(pieces, plane)
    area, ax, ay = _PP._resultant(pieces, (1.0, 0.0, 0.0))
    return force - w * area, sx - w * ax, sy - w * ay


def _footing(f: dict) -> dict:
    """La planta, el centroide, las piezas y las columnas en coordenadas desde el centroide."""
    raw = _pieces(f["plan"])
    moved, centroid = _PP._shift(raw)
    columns = [{**column, "x": column["x"] - centroid[0], "y": column["y"] - centroid[1]} for column in f["columns"]]
    area = _PP._resultant(moved, (1.0, 0.0, 0.0))[0]
    return {**f, "pieces": moved, "centroid": centroid, "area": area, "columns": columns}


def _case(g: dict, case: str) -> dict:
    h, hp, hf = g["h"], g["pedestal_height"], g["fill_height"]
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in g["columns"]]
    fd, fl = loads[0]["dead_factor"], loads[0]["live_factor"]
    dead_area = GAMMA_F * hf + g["surcharge_dead_kNm2"] * 1e-3
    live_area = g["surcharge_live_kNm2"] * 1e-3
    w = fd * (GAMMA_C * h + dead_area) + fl * live_area
    n = w * g["area"]
    mx = my = 0.0
    columns = []
    for column, load in zip(g["columns"], loads, strict=True):
        area = column["cx"] * column["cy"]
        force = load["P_kN"] * 1e3 + fd * (GAMMA_C * area * hp - dead_area * area) - fl * live_area * area
        vx, vy = load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
        mx += load["Mx_kNm"] * 1e6 - column["y"] * force - (h + hp) * vy
        my += load["My_kNm"] * 1e6 + (h + hp) * vx + column["x"] * force
        n += force
        columns.append({"id": column["id"], "x": column["x"], "y": column["y"], "cx": column["cx"], "cy": column["cy"],
                        "force": force, "couple": load["My_kNm"] * 1e6 + (h + hp) * vx,
                        "torque": force * column["y"] - load["Mx_kNm"] * 1e6 + (h + hp) * vy})
    xs = [p[0] for piece in g["pieces"] for p in piece]
    ys = [p[1] for piece in g["pieces"] for p in piece]
    scale = max(max(xs) - min(xs), max(ys) - min(ys))
    plane = _PP._newton(g["pieces"], my / n, -mx / n, scale, n)
    return {"plane": plane, "w": w, "n": n, "ex": my / n, "ey": -mx / n, "columns": sorted(columns, key=lambda c: c["x"])}


def _beam(g: dict, state: dict, x: float) -> tuple[float, float, float]:
    left = [_clip_x(piece, x) for piece in g["pieces"]]
    left = [piece for piece in left if len(piece) >= 3]
    force, sx, sy = _net(left, state["plane"], state["w"]) if left else (0.0, 0.0, 0.0)
    shear, moment, torque = force, x * force - sx, sy
    for column in state["columns"]:
        if column["x"] < x:
            shear -= column["force"]
            moment -= column["force"] * (x - column["x"]) - column["couple"]
            torque -= column["torque"]
    return shear, moment, torque


def _y_depth(g: dict) -> float:
    bottom = g["bottom"]
    first, other = (bottom["x"], bottom["y"]) if bottom["first"] == "x" else (bottom["y"], bottom["x"])
    dy = BARS[bottom["y"]["designation"]][0]
    if bottom["first"] == "x":
        return g["h"] - g["cover"] - BARS[first["designation"]][0] - dy / 2
    return g["h"] - g["cover"] - dy / 2


def _strip(g: dict, state: dict, index: int) -> dict:
    d = _y_depth(g)
    ordered = sorted(g["columns"], key=lambda c: c["x"])
    column = g["columns"][index]
    spans = [[c["x"] - c["cx"] / 2 - d / 2, c["x"] + c["cx"] / 2 + d / 2] for c in ordered]
    for i in range(len(ordered) - 1):
        if spans[i][1] > spans[i + 1][0]:
            middle = ((ordered[i]["x"] + ordered[i]["cx"] / 2) + (ordered[i + 1]["x"] - ordered[i + 1]["cx"] / 2)) / 2
            spans[i][1] = spans[i + 1][0] = middle
    xs = [p[0] for piece in g["pieces"] for p in piece]
    x0, x1 = spans[ordered.index(column)]
    x0, x1 = max(x0, min(xs)), min(x1, max(xs))
    steps = [s for s in _steps(g["plan"], g["centroid"]) if x0 < s < x1]
    if steps:  # el tramo más angosto entre x0 y x1
        probes = [x0 + 1e-6, x1 - 1e-6, *(s + side for s in steps for side in (-1e-6, 1e-6))]
        edges = [_across(g["plan"], g["centroid"], p) for p in probes]
        low, high = max(e[0] for e in edges), min(e[1] for e in edges)
    else:
        low, high = _across(g["plan"], g["centroid"], column["x"])
    p0, gx, gy = state["plane"]
    a = p0 + gx * column["x"]

    def line(y0: float, y1: float) -> tuple[float, float]:
        """∫p dy, ∫y·p dy en la línea de la columna con la presión recortada en cero."""
        if gy == 0:
            return (a * (y1 - y0), a * (y1**2 - y0**2) / 2) if a > 0 else (0.0, 0.0)
        root = -a / gy
        lo, hi = (max(y0, root), y1) if gy > 0 else (y0, min(y1, root))
        if hi <= lo:
            return 0.0, 0.0
        return a * (hi - lo) + gy * (hi**2 - lo**2) / 2, a * (hi**2 - lo**2) / 2 + gy * (hi**3 - lo**3) / 3

    force = next(c["force"] for c in state["columns"] if c["id"] == column["id"])
    b = x1 - x0
    uniform = state["w"] * b
    scale = (force + uniform * (high - low)) / line(low, high)[0]

    def cantilever(at: float, side: float) -> float:
        y0, y1 = (at, high) if side > 0 else (low, at)
        f0, f1 = line(y0, y1)
        net, first = scale * f0 - uniform * (y1 - y0), scale * f1 - uniform * (y1**2 - y0**2) / 2
        return side * (first - at * net)

    return {"column": column["id"], "x0": x0, "x1": x1, "low": low, "high": high, "depth": d,
            "M_face_plus": cantilever(column["y"] + column["cy"] / 2, 1.0),
            "M_face_minus": cantilever(column["y"] - column["cy"] / 2, -1.0)}


def _segment_in_convex(p: Point, q: Point, poly: list[Point]) -> float:
    lo, hi = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for i, (x1, y1) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        nx, ny = -(y2 - y1), x2 - x1  # hacia adentro (antihorario)
        num = nx * (p[0] - x1) + ny * (p[1] - y1)
        den = nx * dx + ny * dy
        if den == 0:
            if num < 0:
                return 0.0
            continue
        t = -num / den
        if den > 0:
            lo = max(lo, t)
        else:
            hi = min(hi, t)
    return max(hi - lo, 0.0) * math.hypot(dx, dy)


def _punching(g: dict, index: int, depth: float) -> dict:
    assert len(g["pieces"]) == 1, "solo plantas convexas"
    poly = g["pieces"][0]
    c = g["columns"][index]
    left, right = c["x"] - (c["cx"] + depth) / 2, c["x"] + (c["cx"] + depth) / 2
    bottom, top = c["y"] - (c["cy"] + depth) / 2, c["y"] + (c["cy"] + depth) / 2
    corners = [(left, bottom), (right, bottom), (right, top), (left, top)]
    b0 = sum(_segment_in_convex(corners[i], corners[(i + 1) % 4], poly) for i in range(4))

    def inside(point: Point) -> bool:
        return all((x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1) >= -1e-9
                   for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True))

    count = sum(1 for corner in corners if inside(corner))
    return {"column": c["id"], "depth": depth, "b0": b0, "corners_inside": count, "outside": {4: 0, 3: 1, 2: 1, 1: 2, 0: 4}[count]}


def _hull(points: list[Point]) -> list[Point]:
    pts = sorted(set(points))

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _overturning(g: dict, case: str) -> dict:
    state = _case(g, case)
    hull = _hull([p for piece in g["pieces"] for p in piece])
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in g["columns"]]
    safety = _C.FS["overturning"][1 if loads[0].get("seismic") else 0]
    best = None
    for i, (x1, y1) in enumerate(hull):
        x2, y2 = hull[(i + 1) % len(hull)]
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = (y2 - y1) / length, -(x2 - x1) / length
        distance = x1 * nx + y1 * ny
        mo = max(state["n"] * (state["ex"] * nx + state["ey"] * ny), 0.0)
        mr = state["n"] * distance
        ratio = safety * mo / mr
        if best is None or ratio > best["ratio"]:
            best = {"demand": safety * mo, "capacity": mr, "ratio": ratio}
    assert best is not None
    return best


def _load(case: str, kind: str, p: float, dead: float, live: float, **moments: float) -> dict:
    return {"case": case, "kind": kind, "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": moments.get("vx", 0.0),
            "Vy_kN": moments.get("vy", 0.0), "Mx_kNm": moments.get("mx", 0.0), "My_kNm": moments.get("my", 0.0)}


def _column(name: str, a: float, t: float, service: float, factored: float, **moments: float) -> dict:
    return {"id": name, "cx": 500.0, "cy": 500.0, "x": a, "y": t,
            "loads": [_load("D+L", "service", service, 1.0, 1.0, **moments), _load("U1", "factored", factored, 1.2, 1.6, **moments)],
            "dowels": {"designation": "#6", "count": 4, "end": "hook90"}}


def _plan_footing(plan: dict, columns: list[dict]) -> dict:
    return {"id": "ZP", "quantity": 1, "min_steel_exception": False, "h": 750.0, "cover": 75.0, "fill_height": 1000.0,
            "pedestal_height": 0.0, "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "plan": plan, "columns": columns,
            "bottom": {"first": "x", "x": {"designation": "#7", "spacing": 150.0, "end": "straight"},
                       "y": {"designation": "#5", "spacing": 150.0, "end": "straight"}},
            "top": {"first": "x", "x": {"designation": "#6", "spacing": 150.0, "end": "straight"},
                    "y": {"designation": "#5", "spacing": 250.0, "end": "straight"}}}


CASES = [
    ("trapecio", "trapecio de 7 m, 2.6 m de ancho en −x y 1.6 m con el lado −y recto en +x; tres columnas, C3 junto al "
                 "lado oblicuo (una esquina de su perímetro afuera)",
     _plan_footing({"shape": "trapezoid", "length": 7000.0, "start": {"low": -1300.0, "high": 1300.0},
                    "end": {"low": -1300.0, "high": 300.0}},
                   [_column("C1", 600.0, 0.0, 900.0, 1250.0, my=30.0), _column("C2", 6300.0, -500.0, 650.0, 900.0, mx=-20.0),
                    _column("C3", 3500.0, 300.0, 250.0, 350.0)]),
     [0, 1, 2]),
    ("trapecio-simetrico", "trapecio simétrico de 8 m, de 3.0 m a 1.8 m; tres columnas en el eje",
     _plan_footing({"shape": "trapezoid", "length": 8000.0, "start": {"low": -1500.0, "high": 1500.0},
                    "end": {"low": -900.0, "high": 900.0}},
                   [_column("C1", 500.0, 0.0, 1000.0, 1400.0), _column("C2", 4000.0, 0.0, 900.0, 1250.0),
                    _column("C3", 7500.0, 0.0, 500.0, 700.0)]),
     [0, 2]),
    ("planta-l", "planta en L: 3.5 m de 2.6 m y 3.5 m de 1.6 m alineados por el borde −y; dos columnas",
     _plan_footing({"shape": "stepped", "parts": [{"length": 3500.0, "low": -1300.0, "high": 1300.0},
                                                   {"length": 3500.0, "low": -1300.0, "high": 300.0}]},
                   [_column("C1", 600.0, 0.0, 900.0, 1250.0), _column("C2", 6300.0, -500.0, 650.0, 900.0, my=-25.0)]),
     []),
    ("planta-t", "planta en T de tres tramos (2.6, 1.6 y 2.2 m), centrados; columna sobre el escalón",
     _plan_footing({"shape": "stepped", "parts": [{"length": 3000.0, "low": -1300.0, "high": 1300.0},
                                                   {"length": 2000.0, "low": -800.0, "high": 800.0},
                                                   {"length": 2000.0, "low": -1100.0, "high": 1100.0}]},
                   [_column("C1", 600.0, 0.0, 950.0, 1300.0), _column("C2", 5000.0, 0.0, 700.0, 980.0),
                    _column("C3", 6500.0, 0.0, 300.0, 420.0)]),
     []),
]


def main() -> None:
    cases = []
    for case_id, text, footing, punched in CASES:
        g = _footing(footing)
        state = _case(g, "U1")
        xs = sorted({*(c["x"] + side * c["cx"] / 2 for c in state["columns"] for side in (-1, 1)),
                     *(min(p[0] for piece in g["pieces"] for p in piece) + k * 700.0 for k in range(1, 10))})
        beam = [{"x": x, "V": v, "M": m, "T": t} for x in xs for v, m, t in [_beam(g, state, x)]]
        strips = [_strip(g, state, index) for index in range(len(g["columns"]))]
        depth = (_y_depth(g) + _y_depth(g) + BARS[g["bottom"]["y"]["designation"]][0] / 2
                 + BARS[g["bottom"]["x"]["designation"]][0] / 2) / 2  # d promedio de las dos direcciones
        cases.append({"id": case_id, "description": text, "footing": footing, "centroid": list(g["centroid"]), "area": g["area"],
                      "plane": list(state["plane"]), "beam": beam, "strips": strips,
                      "punching": [_punching(g, index, depth) for index in punched],
                      "overturning": _overturning(g, "D+L")})
    data = {"description": "Combinada trapezoidal y en planta T o L (D-164): presión de Bellos sobre la planta, cuerpo libre de "
                           "la viga sobre el polígono, franjas con los bordes locales, perímetro de punzonamiento con αs por "
                           "esquinas y volcamiento por los lados de la envolvente.",
            "soil": _C.SOIL, "tolerance_rel": 1e-7, "cases": cases}
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
