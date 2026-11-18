"""Deriva el oráculo de un cabezal de dos columnas (D-143), caso F, para los dos perfiles. No importa el paquete.

Cabezal 3400 × 2200 × 1000 mm, columnas de 500 × 500 en x = ±700, seis pilotes de 400 mm en x = 0, ±1200 e y = ±600,
cargas de las columnas (sin pedestal). Unidades de trabajo: N y mm.

1. Fuerza vertical de cada columna: v = P − fd·(γf·hf + qD)·A − fl·qL·A (desplaza el relleno y las sobrecargas que la
   carga uniforme q = fd·(γc·h + γf·hf + qD) + fl·qL cuenta en todo el cabezal). N = Σv + q·lx·ly.
2. Momentos en el plano de la cabeza de los pilotes (a e del fondo) respecto al centroide del grupo (el origen):
   My = Σ(My + v·x + (h − e)·Vx), Mx = Σ(Mx − v·y − (h − e)·Vy); R = N/n + My·x/Σx² − Mx·y/Σy²;
   ΔR = |N|·t·√((x/Σx²)² + (y/Σy²)²); la cabeza de cada pilote recibe Vx/n y Vy/n.
3. Secciones normales a X en las caras de cada columna y en x = 0, con el lado que tiene menos columnas más allá (los
   dos si empatan): M = Σ R'·brazo de los pilotes cuyo centro más la tolerancia queda más allá (R' = R ± ΔR), más la acción
   de su cabeza (−s·(My + (e − h/2)·Vx)), menos cada columna más allá (v·brazo + s·(My + h/2·Vx)), menos q·ly·L²/2.
4. Cortante (barras x) a d de las caras, con la fracción 0.5 + brazo/dp (entre 0 y 1) de cada reacción, menos las
   columnas y el peso más allá; Vc del perfil (ACI con pilotes a 4D o menos: el mayor con 0.17√f'c·b·d). Gobierna el de
   mayor razón.
5. Franja de cada columna (dirección Y; las columnas están alineadas en X): ancho cx + d (d de las barras y); la otra
   columna no la toca. Cada pilote carga la fracción 0.5 + (distancia al borde de la franja + t)/dp de su reacción (D-145).
   Momento en las caras ±Y y cada 50 mm fuera de la columna (el lado sin columna), con +ΔR y −ΔR: los gobernantes de cada
   signo; cortante a d de las caras con +ΔR y la fracción también a lo largo, el de mayor razón.
6. Punzonamiento: la fuerza que atraviesa el perímetro a d/2 (d promedio) de cada columna desde afuera (pilotes con la
   fracción de 13.4.6.7, menos el peso de afuera y la otra columna) y desde adentro (la columna más el peso de adentro
   menos el resto de las reacciones) y, si los dos perímetros se traslapan (luz entre caras menor que d), la del perímetro
   común desde afuera; aquí no se traslapan (900 mm > d), y el programa no debe revisarlo.

Uso: python tests/oracles/derive_pile_cap_columns.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
FC, FY = 28.0, 420.0
SQRT_FC = math.sqrt(FC)
GAMMA_C, GAMMA_F = 24e-6, 18e-6
LX, LY, H, COVER, BOTTOM_COVER, FILL, QD, QL = 3400.0, 2200.0, 1000.0, 75.0, 150.0, 600.0, 2e-3, 5e-3
PILE, EMBED, TOL = 400.0, 75.0, 75.0
DX = H - BOTTOM_COVER - 25.4 / 2  # barras x #8, primera capa
DY = H - BOTTOM_COVER - 25.4 - 22.2 / 2  # barras y #7
PILES = [(-1200.0, -600.0), (0.0, -600.0), (1200.0, -600.0), (-1200.0, 600.0), (0.0, 600.0), (1200.0, 600.0)]
COLUMNS = [("C1", -700.0, 0.0), ("C2", 700.0, 0.0)]
SIZE = 500.0
LEVELS = {"aci_318_25": "special", "nsr_10": "DES"}


def _load(case: str, kind: str, factors: tuple[float, float], values: tuple[float, ...], seismic: bool = False) -> dict:
    p, vx, vy, mx, my = values
    return {"case": case, "kind": kind, "dead_factor": factors[0], "live_factor": factors[1], "seismic": seismic,
            "P_kN": p, "Vx_kN": vx, "Vy_kN": vy, "Mx_kNm": mx, "My_kNm": my}


LOADS = {
    "C1": [_load("S1", "service", (1.0, 1.0), (1700.0, 6.0, 4.0, -10.0, 9.0)),
           _load("U1", "factored", (1.2, 1.6), (2465.0, 9.0, 6.0, -14.0, 13.2)),
           _load("U2", "factored", (1.2, 1.0), (2210.0, 120.0, 15.0, -30.0, 240.0), True)],
    "C2": [_load("S1", "service", (1.0, 1.0), (2000.0, 6.0, 4.0, -10.0, 9.0)),
           _load("U1", "factored", (1.2, 1.6), (2900.0, 9.0, 6.0, -14.0, 13.2)),
           _load("U2", "factored", (1.2, 1.0), (2600.0, 120.0, 15.0, -30.0, 240.0), True)],
}


def _cap() -> dict:
    mat = lambda designation, spacing: {"designation": designation, "spacing": spacing, "end": "hook90"}  # noqa: E731
    return {"id": "F", "loads_from": "column", "lx": LX, "ly": LY, "h": H, "cover": COVER, "bottom_cover": BOTTOM_COVER,
            "fill_height": FILL, "pedestal_height": 0.0, "surcharge_dead_kNm2": QD * 1e3, "surcharge_live_kNm2": QL * 1e3,
            "columns": [{"id": name, "cx": SIZE, "cy": SIZE, "offset_x": x, "offset_y": y,
                         "dowels": {"designation": "#6", "count": 8, "end": "hook90"}, "loads": LOADS[name]} for name, x, y in COLUMNS],
            "bottom": {"first": "x", "x": mat("#8", 130.0), "y": mat("#7", 150.0)},
            "top": {"first": "x", "x": mat("#5", 250.0), "y": mat("#5", 250.0)},
            "pile": {"shape": "circular", "size": PILE, "embedment": EMBED}, "mislocation_mm": TOL,
            "piles": [{"id": f"P{i + 1}", "x": x, "y": y} for i, (x, y) in enumerate(PILES)]}


SOIL = {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 1500.0,
        "pile_capacity_tension_kN": 300.0, "pile_capacity_lateral_kN": 120.0, "seismic_capacity_factor": 1.33,
        "group_efficiency": 0.85, "max_eccentricity_mm": 150.0}


def _q(load: dict) -> float:
    return load["dead_factor"] * (GAMMA_C * H + GAMMA_F * FILL + QD) + load["live_factor"] * QL


def _vertical(load: dict) -> float:
    area = SIZE * SIZE
    return load["P_kN"] * 1e3 - (load["dead_factor"] * (GAMMA_F * FILL + QD) + load["live_factor"] * QL) * area


def _case(index: int) -> dict:
    loads = [LOADS[name][index] for name, _, _ in COLUMNS]
    q = _q(loads[0])
    verticals = [_vertical(load) for load in loads]
    n_total = sum(verticals) + q * LX * LY
    triples = list(zip(loads, verticals, COLUMNS, strict=True))
    my = sum(load["My_kNm"] * 1e6 + v * x + (H - EMBED) * load["Vx_kN"] * 1e3 for load, v, (_, x, _) in triples)
    mx = sum(load["Mx_kNm"] * 1e6 - v * y - (H - EMBED) * load["Vy_kN"] * 1e3 for load, v, (_, _, y) in triples)
    sxx, syy = sum(x * x for x, _ in PILES), sum(y * y for _, y in PILES)
    n = len(PILES)
    reactions = [n_total / n + my * x / sxx - mx * y / syy for x, y in PILES]
    spread = [abs(n_total) * TOL * math.hypot(x / sxx, y / syy) for x, y in PILES]
    vx, vy = sum(load["Vx_kN"] for load in loads) * 1e3 / n, sum(load["Vy_kN"] for load in loads) * 1e3 / n
    return {"loads": loads, "q": q, "v": verticals, "R": reactions, "dR": spread, "head": (vx, vy)}


def _share(arm: float) -> float:
    return min(max(0.5 + arm / PILE, 0.0), 1.0)


def _sides(plane: float) -> list[float]:
    counts = {s: sum(1 for _, x, _ in COLUMNS if s * (x - plane) > 0) for s in (1.0, -1.0)}
    low = min(counts.values())
    return [s for s in (1.0, -1.0) if counts[s] == low]


def _x_section(case: dict, plane: float, outward: float, sense: float) -> tuple[float, float]:
    """(M, V interpolado) más allá del plano normal a X."""
    vx, _ = case["head"]
    moment = shear = 0.0
    for (x, _), r, dr in zip(PILES, case["R"], case["dR"], strict=True):
        reaction = r + sense * dr
        arm = outward * (x - plane) + TOL
        shear += _share(arm) * reaction
        if arm > 0:
            moment += reaction * arm - outward * (EMBED - H / 2) * vx
    for (_, x, _), load, v in zip(COLUMNS, case["loads"], case["v"], strict=True):
        if outward * (x - plane) > 0:
            moment -= v * outward * (x - plane) + outward * (load["My_kNm"] * 1e6 + H / 2 * load["Vx_kN"] * 1e3)
            shear -= v
    length = LX / 2 - outward * plane
    return moment - case["q"] * LY * length * length / 2, shear - case["q"] * LY * length


def _vc(folder: str, b: float, d: float, rho: float, vu: float, mu: float) -> float:
    if folder == "aci_318_25":
        lam_s = min(math.sqrt(2 / (1 + d / 250)), 1.0)
        vc = max(min(0.66 * lam_s * rho ** (1 / 3) * SQRT_FC * b * d, 0.42 * SQRT_FC * b * d), 0.083 * SQRT_FC * b * d)
        return max(vc, 0.17 * SQRT_FC * b * d)  # pilotes a 1200 ≤ 4·400 mm (13.4.6.8)
    ratio = min(vu * d / mu, 1.0) if mu > 0 else 1.0
    return max(0.17 * SQRT_FC * b * d, min((0.16 * SQRT_FC + 17 * rho * ratio) * b * d, 0.29 * SQRT_FC * b * d))


def _count(width: float, db: float, spacing: float) -> int:
    return math.floor((width - 2 * COVER - db) / spacing + 1e-6) + 1


def _positions(width: float, db: float, spacing: float) -> list[float]:
    count = _count(width, db, spacing)
    half = width / 2 - COVER - db / 2
    offset = (2 * half - (count - 1) * spacing) / 2
    return [-half + offset + i * spacing for i in range(count)]


def _one_way(folder: str, case: dict) -> dict:
    area = _count(LY, 25.4, 130.0) * 510.0
    rho = area / (LY * DX)
    worst = None
    for _, x, _ in COLUMNS:
        for face, outward in ((x + SIZE / 2, 1.0), (x - SIZE / 2, -1.0)):
            plane = face + outward * DX
            if abs(plane) >= LX / 2 or any(c - SIZE / 2 < plane < c + SIZE / 2 for _, c, _ in COLUMNS):
                continue
            for side in _sides(plane):
                moment, shear = _x_section(case, plane, side, 1.0)
                capacity = 0.75 * _vc(folder, LY, DX, rho, abs(shear), abs(moment))
                if worst is None or abs(shear) / capacity > worst[0]:
                    worst = (abs(shear) / capacity, abs(shear), capacity)
    assert worst is not None
    return {"name": "Cortante en una direccion (barras x)", "demand": worst[1], "capacity": worst[2]}


def _strip_section(case: dict, x_column: float, plane: float, outward: float, sense: float) -> tuple[float, float]:
    """(M, V con la reacción interpolada a lo largo) más allá del plano y = plane, del lado outward, dentro de la franja de
    la columna en x_column (ancho cx + d de las barras y; la otra columna no la toca). La tolerancia acerca el pilote a la
    franja (D-145)."""
    x0, x1 = max(x_column - SIZE / 2 - DY / 2, -LX / 2), min(x_column + SIZE / 2 + DY / 2, LX / 2)
    _, vy = case["head"]
    moment = shear = 0.0
    for (x, y), r, dr in zip(PILES, case["R"], case["dR"], strict=True):
        portion = _share(min(x - x0, x1 - x) + TOL)
        if portion <= 0:
            continue
        reaction = portion * (r + sense * dr)
        arm = outward * (y - plane) + TOL
        shear += _share(arm) * reaction
        if arm > 0:
            moment += reaction * arm + portion * outward * (-(EMBED - H / 2) * vy)
    length = LY / 2 - outward * plane
    width = x1 - x0
    return moment - case["q"] * width * length * length / 2, shear - case["q"] * width * length


def _strip(folder: str, case: dict, x_column: float) -> dict:
    """Momentos gobernantes (el mayor positivo y el mayor negativo, |M| > 1 kN·m) con +ΔR y −ΔR en las caras ±Y de la
    columna y en secciones cada 50 mm fuera de ella (el lado sin columna), y el cortante a d de las caras con +ΔR, el de
    mayor razón."""
    planes = [(SIZE / 2, 1.0), (-SIZE / 2, -1.0)]
    planes += [(-LY / 2 + 50.0 * k, 1.0 if -LY / 2 + 50.0 * k > 0 else -1.0) for k in range(1, int(LY // 50.0))
               if abs(-LY / 2 + 50.0 * k) > SIZE / 2 + 1e-6 and -LY / 2 + 50.0 * k < LY / 2 - 1e-6]
    demands = []
    for sense in (1.0, -1.0):
        values = [_strip_section(case, x_column, plane, outward, sense)[0] for plane, outward in planes]
        demands += [value for value in (max(values), min(values)) if abs(value) > 1e3]
    x0, x1 = max(x_column - SIZE / 2 - DY / 2, -LX / 2), min(x_column + SIZE / 2 + DY / 2, LX / 2)
    bars = sum(1 for position in _positions(LX, 22.2, 150.0) if x0 - 1e-6 <= position <= x1 + 1e-6)
    rho = bars * 387.0 / ((x1 - x0) * DY)
    worst = None
    for face, outward in ((SIZE / 2, 1.0), (-SIZE / 2, -1.0)):
        moment, shear = _strip_section(case, x_column, face + outward * DY, outward, 1.0)
        capacity = 0.75 * _vc(folder, x1 - x0, DY, rho, abs(shear), abs(moment))
        if worst is None or abs(shear) / capacity > worst[0]:
            worst = (abs(shear) / capacity, abs(shear))
    assert worst is not None
    return {"moments": sorted(abs(value) for value in demands), "shear": worst[1]}


def _punching(case: dict) -> list[dict]:
    d = (DX + DY) / 2
    out = []
    areas = [(name, (x, 0.0), (SIZE, SIZE), [i]) for i, (name, x, _) in enumerate(COLUMNS)]
    if d > 1400.0 - SIZE:  # los perímetros a d/2 se traslapan si la luz entre caras es menor que d
        areas.append(("comun", (0.0, 0.0), (1400.0 + SIZE, SIZE), [0, 1]))
    for name, (cx, cy), (sx, sy), inside_columns in areas:
        hx, hy = (sx + d) / 2, (sy + d) / 2
        inside_area = 2 * hx * 2 * hy
        portions = []
        for (x, y) in PILES:
            offset = max(abs(x - cx) - hx, abs(y - cy) - hy) + TOL
            portions.append(_share(offset))
        reactions = [r + dr for r, dr in zip(case["R"], case["dR"], strict=True)]
        others = [i for i in range(len(COLUMNS)) if i not in inside_columns]
        forces = []
        if len(others) <= len(inside_columns):
            forces.append(sum(p * r for p, r in zip(portions, reactions, strict=True)) - case["q"] * (LX * LY - inside_area)
                          - sum(case["v"][i] for i in others))
        if len(inside_columns) <= len(others):
            forces.append(sum(case["v"][i] for i in inside_columns) + case["q"] * inside_area
                          - sum((1 - p) * r for p, r in zip(portions, reactions, strict=True)))
        out.append({"area": name, "forces": forces})
    return out


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        cases = []
        for index in range(len(LOADS["C1"])):
            case = _case(index)
            name = case["loads"][0]["case"]
            entry: dict = {"case": name, "kind": case["loads"][0]["kind"], "R": case["R"], "dR": case["dR"]}
            if entry["kind"] == "factored":
                sections = []
                for plane in (-950.0, -450.0, 0.0, 450.0, 950.0):
                    for sense, suffix in ((1.0, " (+ΔR)"), (-1.0, " (−ΔR)")):
                        values = sorted(_x_section(case, plane, side, sense)[0] for side in _sides(plane))
                        sections.append({"case": name + suffix, "plane": plane, "moments": values})
                entry["sections"] = sections
                entry["one_way"] = _one_way(folder, case)
                entry["strips"] = [{"column": column, **_strip(folder, case, x)} for column, x, _ in COLUMNS]
                entry["punching"] = _punching(case)
            cases.append(entry)
        data = {"description": "Oraculo del cabezal de dos columnas (D-143), derivado por tests/oracles/derive_pile_cap_columns.py",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated", "max_aggregate": 19.0},
                "seismic_level": LEVELS[folder], "tolerance_rel": 1e-6, "cap": _cap(), "soil": SOIL, "cases": cases}
        (HERE / folder / "derived_pile_cap_columns.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                                                                     encoding="utf-8", newline="\n")
    print("ok")


if __name__ == "__main__":
    main()
