"""Deriva el oráculo del cortante de zapatas (V3D.2) para los dos perfiles.

No importa el paquete. Reutiliza solo las funciones de los otros oráculos (presión y resultante). Para cada caso mayorado:

1. Una dirección: sección a d de cada cara (d de las barras de esa dirección); Vu y Mu de la carga neta más allá, por
   integración exacta. ACI 13.2.6.2(a): Vc = 0.17λ√f'c·b·d. NSR-10: el mayor de (C.11-3) 0.17λ√f'c·b·d y (C.11-5)
   (0.16λ√f'c + 17ρw·Vu·d/Mu)·b·d ≤ 0.29λ√f'c·b·d, con Vu·d/Mu ≤ 1.
2. Punzonamiento: perímetro a d/2 con d promedio, sin los lados que caen fuera de la base. Vu es la carga neta fuera del
   área crítica; Msc, su momento respecto al centroide de los lados. Jc por cuadratura numérica a lo largo de cada lado
   (∫d·u² ds, más d³·L/12 en los lados paralelos al eje), γv = 1 − 1/(1 + (2/3)√(b1/b2)) y vu máximo en los extremos.
   vc: ACI 318-25 Tabla 22.6.5.2 con λs = 1; NSR-10 C.11.11.2.1. ACI 8.6.1.2: As,min = 5vuv·bslab·b0/(φαs·fy) si
   vuv > φ0.17√f'c, con bslab = c + 3h y las barras de la malla inferior dentro de bslab.

Uso: python tests/oracles/derive_footing_shear.py
"""

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).parent


def _load_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_P = _load_module("derive_soil_pressure")
_F = _load_module("derive_footing_flexure")
FC, FY, PHI = 28.0, 420.0, 0.75
GAMMA_C, GAMMA_F = 24e-6, 18e-6
BARS = {"#4": (12.7, 129.0), "#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0)}
CLAUSES = {"aci_318_25": {"one_way": "13.2.6.2(a) y 13.2.7.2", "punching": "22.6.5.2, 22.6.5.3 y 8.4.4.2"},
           "nsr_10": {"one_way": "C.15.5.1, C.15.5.2 y C.11.2", "punching": "C.11.11.2.1 y C.11.11.7"}}


def _plane(f: dict, load: dict) -> tuple[list[float], float] | None:
    n, mx, my = _F._resultant(f, load)
    if n <= 0 or abs(my / n) >= f["lx"] / 2 or abs(mx / n) >= f["ly"] / 2:
        return None
    plane, _ = _P.solve(f["lx"], f["ly"], n, my / n, -mx / n)
    w = load["dead_factor"] * (GAMMA_C * f["h"] + GAMMA_F * f["fill_height"] + f["surcharge_dead_kNm2"] * 1e-3) \
        + load["live_factor"] * f["surcharge_live_kNm2"] * 1e-3
    return plane, w


def _net(plane: list[float], w: float, rect: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """Carga neta (p − w) sobre el rectángulo (x0, y0, x1, y1): fuerza y momentos estáticos."""
    x0, y0, x1, y1 = rect
    poly = _P._clip([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], plane)
    force = sx = sy = 0.0
    if len(poly) >= 3:
        m = _P._moments(poly)
        q0, gx, gy = plane
        force = q0 * m[0] + gx * m[1] + gy * m[2]
        sx = q0 * m[1] + gx * m[3] + gy * m[4]
        sy = q0 * m[2] + gx * m[4] + gy * m[5]
    area = (x1 - x0) * (y1 - y0)
    return force - w * area, sx - w * area * (x0 + x1) / 2, sy - w * area * (y0 + y1) / 2


def _depths(f: dict) -> dict[str, float]:
    mat = f["bottom"]
    first, second = mat["first"], "y" if mat["first"] == "x" else "x"
    d1 = BARS[mat[first]["designation"]][0]
    d2 = BARS[mat[second]["designation"]][0]
    return {first: f["h"] - f["cover"] - d1 / 2, second: f["h"] - f["cover"] - d1 - d2 / 2}


def _one_way_vc(folder: str, b: float, d: float, rho: float, vu: float, mu: float) -> float:
    simple = 0.17 * math.sqrt(FC) * b * d
    if folder == "aci_318_25":
        return simple
    ratio = min(vu * d / mu, 1.0) if mu > 0 else 1.0
    detailed = min((0.16 * math.sqrt(FC) + 17 * rho * ratio) * b * d, 0.29 * math.sqrt(FC) * b * d)
    return max(simple, detailed)


def _one_way(folder: str, f: dict, plane: list[float], w: float, direction: str, depth: float) -> dict:
    hx, hy = f["lx"] / 2, f["ly"] / 2
    c = f["column"]
    db, ab = BARS[f["bottom"][direction]["designation"]]
    width = f["ly"] if direction == "x" else f["lx"]
    count = math.floor((width - 2 * f["cover"] - db) / f["bottom"][direction]["spacing"] + 1e-6) + 1
    rho = count * ab / (width * depth)
    if direction == "x":
        plus, minus = c["offset_x"] + c["cx"] / 2 + depth, c["offset_x"] - c["cx"] / 2 - depth
        regions = [((plus, -hy, hx, hy), plus, 1.0, 0, "+X"), ((-hx, -hy, minus, hy), minus, -1.0, 0, "-X")]
    else:
        plus, minus = c["offset_y"] + c["cy"] / 2 + depth, c["offset_y"] - c["cy"] / 2 - depth
        regions = [((-hx, plus, hx, hy), plus, 1.0, 1, "+Y"), ((-hx, -hy, hx, minus), minus, -1.0, 1, "-Y")]
    worst = None
    for rect, at, outward, axis, face in regions:
        if rect[2] - rect[0] <= 0 or rect[3] - rect[1] <= 0:
            force = moment = 0.0
        else:
            force, sx, sy = _net(plane, w, rect)
            moment = outward * ((sx if axis == 0 else sy) - at * force)
        capacity = PHI * _one_way_vc(folder, width, depth, rho, abs(force), abs(moment))
        if worst is None or abs(force) / capacity > worst[0]:
            worst = (abs(force) / capacity, abs(force), capacity, face)
    assert worst is not None
    return {"name": f"Cortante en una direccion (barras {direction})", "status": "PASS" if worst[1] <= worst[2] else "FAIL",
            "demand": worst[1], "capacity": worst[2]}


def _jc(sides: list[tuple[tuple[float, float], tuple[float, float]]], d: float, axis: int, centre: float) -> float:
    total = 0.0
    steps = 4000
    for start, end in sides:
        length = abs(end[0] - start[0]) + abs(end[1] - start[1])
        parallel = start[axis] != end[axis]
        for i in range(steps):
            t = (i + 0.5) / steps
            u = start[axis] + t * (end[axis] - start[axis]) - centre
            total += d * u * u * length / steps
        if parallel:
            total += length * d**3 / 12
    return total


def _punching(folder: str, f: dict, plane: list[float], w: float, depth: float) -> list[dict]:
    hx, hy = f["lx"] / 2, f["ly"] / 2
    c = f["column"]
    left, right = c["offset_x"] - (c["cx"] + depth) / 2, c["offset_x"] + (c["cx"] + depth) / 2
    bottom, top = c["offset_y"] - (c["cy"] + depth) / 2, c["offset_y"] + (c["cy"] + depth) / 2
    x0, x1, y0, y1 = max(left, -hx), min(right, hx), max(bottom, -hy), min(top, hy)
    sides, outside = [], 0
    for present, side in ((bottom > -hy, ((x0, bottom), (x1, bottom))), (right < hx, ((right, y0), (right, y1))),
                          (top < hy, ((x0, top), (x1, top))), (left > -hx, ((left, y0), (left, y1)))):
        if present:
            sides.append(side)
        else:
            outside += 1
    lengths = [abs(e[0] - s[0]) + abs(e[1] - s[1]) for s, e in sides]
    b0 = sum(lengths)
    xc = sum(size * (s[0] + e[0]) / 2 for size, (s, e) in zip(lengths, sides, strict=True)) / b0
    yc = sum(size * (s[1] + e[1]) / 2 for size, (s, e) in zip(lengths, sides, strict=True)) / b0
    total = _net(plane, w, (-hx, -hy, hx, hy))
    inside = _net(plane, w, (x0, y0, x1, y1))
    vu = total[0] - inside[0]
    msx = (total[1] - inside[1]) - xc * vu
    msy = (total[2] - inside[2]) - yc * vu
    b1, b2 = x1 - x0, y1 - y0
    gx = 1 - 1 / (1 + 2 / 3 * math.sqrt(b1 / b2))
    gy = 1 - 1 / (1 + 2 / 3 * math.sqrt(b2 / b1))
    jx, jy = _jc(sides, depth, 0, xc), _jc(sides, depth, 1, yc)
    vuv = vu / (b0 * depth)
    points = {p for side in sides for p in side}
    stress = max(vuv + gx * msx * (x - xc) / jx + gy * msy * (y - yc) / jy for x, y in points)
    alpha = {0: 40.0, 1: 30.0, 2: 20.0}[outside]
    beta = max(c["cx"], c["cy"]) / min(c["cx"], c["cy"])
    if folder == "aci_318_25":
        vc = min(0.33, 0.17 + 0.33 / beta, 0.17 + 0.083 * alpha * depth / b0) * math.sqrt(FC)
    else:
        vc = min(0.17 * (1 + 2 / beta), 0.083 * (alpha * depth / b0 + 2), 0.33) * math.sqrt(FC)
    checks = [{"name": "Punzonamiento", "status": "PASS" if stress <= PHI * vc else "FAIL", "demand": stress,
               "capacity": PHI * vc, "alpha_s": alpha, "b0": b0}]
    if folder == "aci_318_25" and vuv > PHI * 0.17 * math.sqrt(FC):
        for direction in ("x", "y"):
            db, ab = BARS[f["bottom"][direction]["designation"]]
            across, centre = (c["cy"], c["offset_y"]) if direction == "x" else (c["cx"], c["offset_x"])
            low, high, bslab = _slab(f, direction, across, centre)
            required = 5 * vuv * bslab * b0 / (PHI * alpha * FY)
            width = f["ly"] if direction == "x" else f["lx"]
            spacing = f["bottom"][direction]["spacing"]
            n = math.floor((width - 2 * f["cover"] - db) / spacing + 1e-6) + 1
            half = width / 2 - f["cover"] - db / 2
            start = -half + (2 * half - (n - 1) * spacing) / 2
            provided = sum(ab for i in range(n) if low - 1e-6 <= start + i * spacing <= high + 1e-6)
            checks.append({"name": f"Acero minimo por punzonamiento (barras {direction})",
                           "status": "PASS" if provided >= required else "FAIL", "demand": required, "capacity": provided})
    checks += _transfer(folder, f, {"x": (msx, 1 - gx), "y": (msy, 1 - gy)})
    return checks


def _slab(f: dict, direction: str, across: float, centre: float) -> tuple[float, float, float]:
    """bslab de las barras de una dirección: c + 1.5h a cada lado (ACI 8.4.2.2.3, NSR-10 C.13.5.3.2), sin pasar de los
    bordes de la zapata (D-102). Las barras x se cuentan a lo ancho de Y (ly); las y, a lo largo de X (lx).
    Devuelve (desde, hasta, ancho)."""
    edge = (f["ly"] if direction == "x" else f["lx"]) / 2
    half = (across + 3 * f["h"]) / 2
    low, high = max(centre - half, -edge), min(centre + half, edge)
    return low, high, high - low


def _positions(f: dict, mat: dict, direction: str) -> tuple[list[float], float]:
    """Posiciones (centradas) de las barras de una dirección de una malla y el área de cada una."""
    db, ab = BARS[mat[direction]["designation"]]
    width = f["ly"] if direction == "x" else f["lx"]
    spacing = mat[direction]["spacing"]
    n = math.floor((width - 2 * f["cover"] - db) / spacing + 1e-6) + 1
    half = width / 2 - f["cover"] - db / 2
    start = -half + (2 * half - (n - 1) * spacing) / 2
    return [start + i * spacing for i in range(n)], ab


def _transfer(folder: str, f: dict, moments: dict[str, tuple[float, float]], level: str = "") -> list[dict]:
    """Transferencia de momento por flexión (ACI 8.4.2.2, NSR-10 C.11.11.7.1 y C.13.5.3; D-087): γf·|Msc| frente a φMn de
    la malla inferior dentro de bslab = c + 3h; la parte negativa, frente a la malla superior en bslab o, sin ella, al
    concreto simple si el nivel lo permite (siempre cumple: lo que falte lo toma la viga de cimentación)."""
    c = f["column"]
    profile = _F.PROFILES[folder]
    depths = _depths(f)
    out = []
    for direction, (msc, gamma_f) in moments.items():
        across, centre = (c["cy"], c["offset_y"]) if direction == "x" else (c["cx"], c["offset_x"])
        low, high, bslab = _slab(f, direction, across, centre)
        positions, ab = _positions(f, f["bottom"], direction)
        area = sum(ab for p in positions if low - 1e-6 <= p <= high + 1e-6)
        demand = gamma_f * abs(msc)
        nominal, phi, _ = _F._strength(area, bslab, depths[direction], profile)
        out.append({"name": f"Transferencia de momento por flexion (barras {direction})",
                    "status": "PASS" if demand <= phi * nominal else "FAIL", "demand": demand, "capacity": phi * nominal})
        capacity = 0.0
        if f.get("top"):
            top_positions, top_ab = _positions(f, f["top"], direction)
            top_area = sum(top_ab for p in top_positions if low - 1e-6 <= p <= high + 1e-6)
            top_db = BARS[f["top"][direction]["designation"]][0]
            first = BARS[f["top"][f["top"]["first"]]["designation"]][0]
            offset = f["cover"] + top_db / 2 if direction == f["top"]["first"] else f["cover"] + first + top_db / 2
            nominal, phi, _ = _F._strength(top_area, bslab, f["h"] - offset, profile)
            capacity = phi * nominal
        elif level in profile["plain_levels"]:
            capacity = 0.60 * 0.42 * math.sqrt(FC) * bslab * (f["h"] - 50.0) ** 2 / 6
        negative = {"name": f"Transferencia de momento: parte negativa (barras {direction})", "status": "PASS", "capacity": capacity}
        out.append({**negative, "demand": demand} if demand <= capacity else negative)  # sin demanda si la toma la viga
    return out


def _expected(folder: str, f: dict) -> list[dict]:
    depths = _depths(f)
    out = []
    for load in f["loads"]:
        solved = _plane(f, load)
        if solved is None:
            continue
        plane, w = solved
        for direction in ("x", "y"):
            out.append({**_one_way(folder, f, plane, w, direction, depths[direction]), "case": load["case"]})
        out.extend({**item, "case": load["case"]} for item in _punching(folder, f, plane, w, (depths["x"] + depths["y"]) / 2))
    return out


def _mat(first: str, x: tuple[str, float], y: tuple[str, float]) -> dict:
    return {"first": first, "end": "straight", "x": {"designation": x[0], "spacing": x[1]},
            "y": {"designation": y[0], "spacing": y[1]}}


def _load(case: str, dead: float, live: float, p: float, mx: float = 0.0, my: float = 0.0, vx: float = 0.0) -> dict:
    return {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": vx,
            "Vy_kN": 0.0, "Mx_kNm": mx, "My_kNm": my}


def _footing(**changes: object) -> dict:
    data = {"id": "Z", "lx": 2400.0, "ly": 2400.0, "h": 550.0, "cover": 75.0, "fill_height": 1000.0,
            "pedestal_height": 0.0, "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0,
            "column": {"cx": 450.0, "cy": 450.0, "offset_x": 0.0, "offset_y": 0.0},
            "bottom": _mat("x", ("#5", 150.0), ("#5", 150.0)), "top": None,
            "loads": [_load("1.2D+1.6L", 1.2, 1.6, 1500.0)]}
    data.update(changes)
    return data


CASES = [
    ("interior-centrada", "columna interior sin momento", _footing()),
    ("interior-momento", "columna rectangular con momentos en los dos ejes: transferencia por excentricidad del cortante",
     _footing(lx=3000.0, ly=2400.0, h=600.0, column={"cx": 600.0, "cy": 400.0, "offset_x": 200.0, "offset_y": -100.0},
              loads=[_load("1.2D+L+E", 1.2, 1.0, 1300.0, mx=-150.0, my=280.0, vx=60.0)])),
    ("borde", "columna cerca del borde +X: un lado del perímetro fuera de la base (αs = 30)",
     _footing(lx=2600.0, ly=2400.0, column={"cx": 400.0, "cy": 450.0, "offset_x": 900.0, "offset_y": 0.0},
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 900.0, my=-250.0)])),
    ("esquina", "columna cerca de la esquina: dos lados fuera (αs = 20)",
     _footing(lx=2600.0, ly=2600.0, column={"cx": 400.0, "cy": 400.0, "offset_x": 950.0, "offset_y": 950.0},
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 700.0, mx=180.0, my=-180.0)])),
    ("columna-alargada", "columna de 900 x 300 (β = 3): gobierna la ecuación (b), distinta en cada perfil",
     _footing(lx=2800.0, ly=2400.0, h=500.0, column={"cx": 900.0, "cy": 300.0, "offset_x": 0.0, "offset_y": 0.0},
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 1400.0)])),
    ("delgada", "zapata delgada muy cargada: falla en una dirección y activa ACI 8.6.1.2",
     _footing(h=350.0, bottom=_mat("x", ("#5", 200.0), ("#5", 200.0)), loads=[_load("1.2D+1.6L", 1.2, 1.6, 1500.0)])),
]


def main() -> None:
    for folder, clauses in CLAUSES.items():
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing)}
                 for case_id, text, footing in CASES]
        data = {"description": "Cortante en una dirección y punzonamiento de zapatas con casos mayorados (D-059, D-063).",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "soil": {"allowable_pressure_kPa": 250.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                         "unit_weight_fill_kNm3": 18.0,
                         "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                         "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                         "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                         "overturning_safety_factor_seismic": 1.5},
                "clauses": clauses, "tolerance_rel": 1e-6, "cases": cases}
        (HERE / folder / "derived_footing_shear.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
