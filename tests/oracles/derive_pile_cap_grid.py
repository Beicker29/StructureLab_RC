"""Deriva el oráculo de un cabezal de cuatro columnas en cuadrícula 2 × 2 (D-145), caso G, para los dos perfiles. No
importa el paquete.

Cabezal 3400 × 3400 × 1100 mm, columnas de 500 × 500 en (±700, ±700), nueve pilotes de 400 mm en x, y ∈ {−1200, 0, 1200},
cargas de las columnas (sin pedestal). Unidades de trabajo: N y mm.

1. Reacciones como en el caso F: v = P − fd·(γf·hf + qD)·A − fl·qL·A; N = Σv + q·lx·ly; momentos en el plano de la
   cabeza de los pilotes respecto al centroide del grupo; R = N/n + My·x/Σx² − Mx·y/Σy²; ΔR = |N|·t·√((x/Σx²)² + (y/Σy²)²).
2. Franjas en las dos direcciones (las columnas no están alineadas). La franja de una columna a lo largo de la dirección
   a (sus barras) tiene ancho = lado + d_a en la otra dirección b, centrada en la columna; la tocan las columnas cuyo
   rectángulo la traslapa (aquí, la columna y la vecina en a). Secciones a lo largo de a: las caras de esas columnas y cada
   50 mm fuera de ellas, con el lado que tiene menos columnas de la franja (los dos si empatan). De ese lado: cada pilote con
   la fracción 0.5 + (distancia al borde de la franja + t)/dp de su reacción R ± ΔR, con su brazo + t y su cabeza; cada
   columna de la franja con −v·brazo + s·(su momento + h/2·su cortante) (alrededor del eje de la sección); y el peso
   q·b·L²/2. Gobiernan el mayor positivo y el mayor negativo (|M| > 1 kN·m) con +ΔR y −ΔR. Cortante a d de las caras con
   +ΔR (la fracción también a lo largo), el de mayor razón con el Vc del perfil.

Uso: python tests/oracles/derive_pile_cap_grid.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
FC, FY = 28.0, 420.0
SQRT_FC = math.sqrt(FC)
GAMMA_C, GAMMA_F = 24e-6, 18e-6
L, H, COVER, BOTTOM_COVER, FILL, QD, QL = 3400.0, 1100.0, 75.0, 150.0, 600.0, 2e-3, 5e-3
PILE, EMBED, TOL, SIZE = 400.0, 75.0, 75.0, 500.0
BARS = {"x": ("#8", 25.4, 510.0, 130.0), "y": ("#8", 25.4, 510.0, 130.0)}
DEPTH = {"x": H - BOTTOM_COVER - 25.4 / 2, "y": H - BOTTOM_COVER - 25.4 - 25.4 / 2}  # x primero
PILES = [(x, y) for y in (-1200.0, 0.0, 1200.0) for x in (-1200.0, 0.0, 1200.0)]
COLUMNS = [("C1", -700.0, -700.0), ("C2", 700.0, -700.0), ("C3", -700.0, 700.0), ("C4", 700.0, 700.0)]
LEVELS = {"aci_318_25": "special", "nsr_10": "DES"}
AXES = {"x": 0, "y": 1}


def _load(case: str, kind: str, factors: tuple[float, float], values: tuple[float, ...], seismic: bool = False) -> dict:
    p, vx, vy, mx, my = values
    return {"case": case, "kind": kind, "dead_factor": factors[0], "live_factor": factors[1], "seismic": seismic,
            "P_kN": p, "Vx_kN": vx, "Vy_kN": vy, "Mx_kNm": mx, "My_kNm": my}


SCALE = {"C1": 1.0, "C2": 0.9, "C3": 0.8, "C4": 1.1}
LOADS = {name: [_load("S1", "service", (1.0, 1.0), (1500.0 * f, 5.0, 4.0, -8.0, 9.0)),
                _load("U1", "factored", (1.2, 1.6), (2150.0 * f, 8.0, 6.0, -12.0, 14.0)),
                _load("U2", "factored", (1.2, 1.0), (1950.0 * f, 90.0, 20.0, -25.0, 180.0), True)]
         for name, f in SCALE.items()}


def _cap() -> dict:
    def mat(designation: str, spacing: float) -> dict:
        return {"designation": designation, "spacing": spacing, "end": "hook90"}

    return {"id": "G", "loads_from": "column", "lx": L, "ly": L, "h": H, "cover": COVER, "bottom_cover": BOTTOM_COVER,
            "fill_height": FILL, "pedestal_height": 0.0, "surcharge_dead_kNm2": QD * 1e3, "surcharge_live_kNm2": QL * 1e3,
            "columns": [{"id": name, "cx": SIZE, "cy": SIZE, "offset_x": x, "offset_y": y,
                         "dowels": {"designation": "#6", "count": 8, "end": "hook90"}, "loads": LOADS[name]} for name, x, y in COLUMNS],
            "bottom": {"first": "x", "x": mat("#8", 130.0), "y": mat("#8", 130.0)},
            "top": {"first": "x", "x": mat("#5", 200.0), "y": mat("#5", 200.0)},
            "pile": {"shape": "circular", "size": PILE, "embedment": EMBED}, "mislocation_mm": TOL,
            "piles": [{"id": f"P{i + 1}", "x": x, "y": y} for i, (x, y) in enumerate(PILES)]}


SOIL = {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 1500.0,
        "pile_capacity_tension_kN": 300.0, "pile_capacity_lateral_kN": 120.0, "seismic_capacity_factor": 1.33,
        "group_efficiency": 0.85, "max_eccentricity_mm": 150.0}


def _share(arm: float) -> float:
    return min(max(0.5 + arm / PILE, 0.0), 1.0)


def _case(index: int) -> dict:
    loads = [LOADS[name][index] for name, _, _ in COLUMNS]
    first = loads[0]
    q = first["dead_factor"] * (GAMMA_C * H + GAMMA_F * FILL + QD) + first["live_factor"] * QL
    area = SIZE * SIZE
    verticals = [load["P_kN"] * 1e3 - (load["dead_factor"] * (GAMMA_F * FILL + QD) + load["live_factor"] * QL) * area
                 for load in loads]
    total = sum(verticals) + q * L * L
    lever = H - EMBED
    triples = list(zip(loads, verticals, COLUMNS, strict=True))
    my = sum(load["My_kNm"] * 1e6 + v * x + lever * load["Vx_kN"] * 1e3 for load, v, (_, x, _) in triples)
    mx = sum(load["Mx_kNm"] * 1e6 - v * y - lever * load["Vy_kN"] * 1e3 for load, v, (_, _, y) in triples)
    sxx, syy = sum(x * x for x, _ in PILES), sum(y * y for _, y in PILES)
    n = len(PILES)
    reactions = [total / n + my * x / sxx - mx * y / syy for x, y in PILES]
    spread = [abs(total) * TOL * math.hypot(x / sxx, y / syy) for x, y in PILES]
    head = (sum(load["Vx_kN"] for load in loads) * 1e3 / n, sum(load["Vy_kN"] for load in loads) * 1e3 / n)
    return {"loads": loads, "q": q, "v": verticals, "R": reactions, "dR": spread, "head": head}


def _at(index: int, axis: int) -> float:
    """La coordenada x (axis = 0) o y (axis = 1) del eje de una columna."""
    _, x, y = COLUMNS[index]
    return x if axis == 0 else y


def _strip_members(along: str, column: int) -> tuple[tuple[float, float], list[int]]:
    """Ancho de la franja (en la otra dirección) y las columnas cuyo rectángulo la traslapa."""
    across = 1 - AXES[along]
    centre = _at(column, across)
    limits = (max(centre - SIZE / 2 - DEPTH[along] / 2, -L / 2), min(centre + SIZE / 2 + DEPTH[along] / 2, L / 2))
    members = [i for i in range(len(COLUMNS)) if _at(i, across) - SIZE / 2 < limits[1] and _at(i, across) + SIZE / 2 > limits[0]]
    return limits, members


Strip = tuple[str, tuple[float, float], list[int]]


def _section(case: dict, given: Strip, plane: float, outward: float, sense: float) -> tuple[float, float]:
    """(M, V interpolado) más allá del plano normal a la dirección along, dentro de la franja."""
    along, limits, members = given
    a, b = AXES[along], 1 - AXES[along]
    hx, hy = case["head"]
    head = hx if a == 0 else hy
    moment = shear = 0.0
    for point, r, dr in zip(PILES, case["R"], case["dR"], strict=True):
        portion = _share(min(point[b] - limits[0], limits[1] - point[b]) + TOL)
        if portion <= 0:
            continue
        reaction = portion * (r + sense * dr)
        arm = outward * (point[a] - plane) + TOL
        shear += _share(arm) * reaction
        if arm > 0:
            # Cabeza: alrededor de Y (−(e − h/2)·Vx) para secciones normales a X; alrededor de X ((e − h/2)·(−Vy)) para Y.
            moment += reaction * arm + portion * outward * (-(EMBED - H / 2) * head)
    for index in members:
        name, cx, cy = COLUMNS[index]
        centre = (cx, cy)[a]
        if outward * (centre - plane) <= 0:
            continue
        load, v = case["loads"][index], case["v"][index]
        about = -(load["My_kNm"] * 1e6 + H / 2 * load["Vx_kN"] * 1e3) if a == 0 else load["Mx_kNm"] * 1e6 - H / 2 * load["Vy_kN"] * 1e3
        moment += -v * outward * (centre - plane) + outward * about
        shear -= v
    length = L / 2 - outward * plane
    width = limits[1] - limits[0]
    return moment - case["q"] * width * length * length / 2, shear - case["q"] * width * length


def _sides(along: str, members: list[int], plane: float) -> list[float]:
    a = AXES[along]
    counts = {s: sum(1 for i in members if s * (_at(i, a) - plane) > 0) for s in (1.0, -1.0)}
    low = min(counts.values())
    return [s for s in (1.0, -1.0) if counts[s] == low]


def _vc(folder: str, b: float, d: float, rho: float, vu: float, mu: float) -> float:
    if folder == "aci_318_25":
        lam_s = min(math.sqrt(2 / (1 + d / 250)), 1.0)
        vc = max(min(0.66 * lam_s * rho ** (1 / 3) * SQRT_FC * b * d, 0.42 * SQRT_FC * b * d), 0.083 * SQRT_FC * b * d)
        return max(vc, 0.17 * SQRT_FC * b * d)  # pilotes a 1200 ≤ 4·400 mm (13.4.6.8)
    ratio = min(vu * d / mu, 1.0) if mu > 0 else 1.0
    return max(0.17 * SQRT_FC * b * d, min((0.16 * SQRT_FC + 17 * rho * ratio) * b * d, 0.29 * SQRT_FC * b * d))


def _bars_within(along: str, limits: tuple[float, float]) -> int:
    _, db, _, spacing = BARS[along]
    half = L / 2 - COVER - db / 2
    count = math.floor(2 * half / spacing + 1e-6) + 1
    offset = (2 * half - (count - 1) * spacing) / 2
    return sum(1 for i in range(count) if limits[0] - 1e-6 <= -half + offset + i * spacing <= limits[1] + 1e-6)


def _strip(folder: str, case: dict, along: str, column: int) -> dict:
    limits, members = _strip_members(along, column)
    a = AXES[along]
    spans = [(_at(i, a), SIZE) for i in members]
    planes = [p for centre, size in spans for p in (centre + size / 2, centre - size / 2)]
    planes += [-L / 2 + 50.0 * k for k in range(1, int(L // 50.0)) if -L / 2 + 50.0 * k < L / 2 - 1e-6
               and not any(c - s / 2 - 1e-6 <= -L / 2 + 50.0 * k <= c + s / 2 + 1e-6 for c, s in spans)]
    given = (along, limits, members)
    demands = []
    for sense in (1.0, -1.0):
        values = [_section(case, given, plane, side, sense)[0] for plane in planes for side in _sides(along, members, plane)]
        demands += [value for value in (max(values), min(values)) if abs(value) > 1e3]
    width, d = limits[1] - limits[0], DEPTH[along]
    rho = _bars_within(along, limits) * BARS[along][2] / (width * d)
    worst = None
    for centre, size in spans:
        for face, outward_face in ((centre + size / 2, 1.0), (centre - size / 2, -1.0)):
            plane = face + outward_face * d
            if abs(plane) >= L / 2 or any(c - s / 2 < plane < c + s / 2 for c, s in spans):
                continue
            for side in _sides(along, members, plane):
                moment, shear = _section(case, given, plane, side, 1.0)
                ratio = abs(shear) / (0.75 * _vc(folder, width, d, rho, abs(shear), abs(moment)))
                if worst is None or ratio > worst[0]:
                    worst = (ratio, abs(shear))
    return {"along": along, "column": COLUMNS[column][0], "members": [COLUMNS[i][0] for i in members],
            "moments": sorted(abs(value) for value in demands), "shear": None if worst is None else worst[1]}


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        cases = []
        for index in range(len(LOADS["C1"])):
            case = _case(index)
            name = case["loads"][0]["case"]
            entry: dict = {"case": name, "kind": case["loads"][0]["kind"], "R": case["R"], "dR": case["dR"]}
            if entry["kind"] == "factored":
                entry["strips"] = [_strip(folder, case, along, column) for along in ("x", "y") for column in range(len(COLUMNS))]
            cases.append(entry)
        data = {"description": "Oraculo del cabezal de cuatro columnas (D-145), derivado por tests/oracles/derive_pile_cap_grid.py",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated", "max_aggregate": 19.0},
                "seismic_level": LEVELS[folder], "tolerance_rel": 1e-6, "cap": _cap(), "soil": SOIL, "cases": cases}
        (HERE / folder / "derived_pile_cap_grid.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                                                                  encoding="utf-8", newline="\n")
    print("ok")


if __name__ == "__main__":
    main()
