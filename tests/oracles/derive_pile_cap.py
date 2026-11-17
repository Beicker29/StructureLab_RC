"""Deriva el oráculo de los cabezales sobre pilotes (D-138) para los dos perfiles. No importa el paquete.

Casos:
- A: cuatro pilotes simétricos con las cargas de la columna (cabezal rígido, pilotes articulados).
- B: dos pilotes con las cargas de cada pilote (reacción, fuerza horizontal y momento en la cabeza), sin el peso.

Para cada caso:
1. Reacciones. Columna: N = P + fd·(γc·A·h + (γf·hf + qD)·(A − Ac)) + fl·qL·(A − Ac); momentos en el plano de la cabeza
   de los pilotes (a e del fondo): My = My_col + (h − e)·Vx, Mx = Mx_col − (h − e)·Vy; R = N/n + My·x/Σx² − Mx·y/Σy²; la
   mala ubicación suma ΔR = N·t·√((x/Σx²)² + (y/Σy²)²). Pilotes: R = P (+ peso/n si no lo incluyen).
2. Revisiones geotécnicas con los casos de servicio (fs = factor sísmico en los casos con sismo): máx(R + ΔR) ≤ fm·fs·Qa
   (fm = 1.10 en ACI 13.4.1.4 con cargas de la columna); H = |V| ≤ fs·Qh; ΣR ≤ η·n·fs·Qa; sin sismo, la excentricidad
   de la resultante de las reacciones respecto al centroide del grupo ≤ e,máx.
3. Momento en cada cara de la columna con los casos mayorados: Σ R·(distancia + t) de los pilotes con brazo positivo,
   más la acción de la cabeza de los pilotes cuyo centro queda más allá (su momento y el de su fuerza horizontal a
   e − h/2 del eje), menos el peso q·b·L²/2.
4. As mínimo de la malla inferior (guía CRSI 4.5): As = máx(As análisis, mín(ηbd, 4/3·As análisis), mín(ηbd, ρt·b·h)),
   η = máx(0.25√f'c, 1.4)/fy, ρt = 0.0018 (fy = 420), As análisis de la ecuación cuadrática con φ = 0.9; la retracción
   ρt·b·h se revisa además con las dos mallas sumadas (D-140).
5. Cortante en una dirección a d de la cara con la reacción interpolada (0.5 + (dist + t)/dpile, entre 0 y 1). ACI 22.5
   sin Av,min: Vc = 0.66λs·λ·ρw^(1/3)·√f'c·b·d (λs = √(2/(1 + d/250)) ≤ 1), entre 0.083 y 0.42 λ√f'c·b·d; con pilotes a
   4D o menos, el mayor entre ese y 0.17λ√f'c·b·d (13.4.6.8(a), decisión del usuario). NSR-10: el
   mayor de 0.17λ√f'c·b·d y (0.16λ√f'c + 17ρw·Vu·d/Mu)·b·d ≤ 0.29λ√f'c·b·d.
6. Guía CRSI, cara de la columna (factor 0.083 de √psi a √MPa): estado límite 4 con un pilote a menos de d/2,
   vc = mín((d/w)(1 + d/c)·0.166, 2.656)·√f'c en bs = 2(cx + cy); estados límite 5 y 6 con un pilote a menos de d,
   vc = mín((d/w)(3.5 − 2.5r)(0.1577 + 0.0083/r), 0.83)·√f'c en todo el ancho, r = mín(Mu/(Vu·d), 1).
7. Guía CRSI P2 (dos pilotes vecinos) y P4 (cortante de esquina), con las reacciones mayoradas (D-138).
8. Punzonamiento del pilote P1 (cuadrado de igual área, lado √π·D/2), perímetro a d/2 completo: vu = R/(b0·d) y
   φvc = 0.75·mín(0.33, 0.17 + 0.33/β, 0.17 + 0.083·40·d/b0)·λs·√f'c en ACI (λs = 1 con pilotes a 4D o menos) y
   0.75·mín(0.17(1 + 2/β), 0.083(40·d/b0 + 2), 0.33)·√f'c en NSR-10.

Uso: python tests/oracles/derive_pile_cap.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
FC, FY, PHI_V, PHI_M = 28.0, 420.0, 0.75, 0.9
GAMMA_C, GAMMA_F = 24e-6, 18e-6
BARS = {"#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0), "#8": (25.4, 510.0)}
SQRT_FC = min(math.sqrt(FC), 8.3)
SOIL = {"E": {'unit_weight_concrete_kNm3': 24.0,
              'unit_weight_fill_kNm3': 18.0,
              'pile_capacity_compression_kN': 850.0,
              'pile_capacity_tension_kN': 250.0,
              'pile_capacity_lateral_kN': 80.0,
              'seismic_capacity_factor': 1.33,
              'group_efficiency': 0.85,
              'max_eccentricity_mm': 150.0},
        "D": {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 1500.0,
              "pile_capacity_tension_kN": 300.0, "pile_capacity_lateral_kN": 80.0, "seismic_capacity_factor": 1.0,
              "group_efficiency": 0.9, "max_eccentricity_mm": 150.0},
        "C": {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 850.0,
              "pile_capacity_tension_kN": 250.0, "pile_capacity_lateral_kN": 80.0, "seismic_capacity_factor": 1.0,
              "group_efficiency": 0.9, "max_eccentricity_mm": 150.0},
        "A": {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 850.0,
              "pile_capacity_tension_kN": 250.0, "pile_capacity_lateral_kN": 80.0, "seismic_capacity_factor": 1.33,
              "group_efficiency": 0.85, "max_eccentricity_mm": 150.0},
        "B": {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 1300.0,
              "pile_capacity_tension_kN": 300.0, "pile_capacity_lateral_kN": 50.0, "seismic_capacity_factor": 1.2,
              "group_efficiency": 0.9, "max_eccentricity_mm": 20.0}}


def _load(case: str, kind: str, fd: float, fl: float, values: tuple[float, ...], seismic: bool = False) -> dict:
    p, vx, vy, mx, my = values
    return {"case": case, "kind": kind, "dead_factor": fd, "live_factor": fl, "seismic": seismic,
            "P_kN": p, "Vx_kN": vx, "Vy_kN": vy, "Mx_kNm": mx, "My_kNm": my}


def _mat(designation: str, spacing: float) -> dict:
    return {"designation": designation, "spacing": spacing, "end": "hook90"}


COLUMN = [_load("S1", "service", 1.0, 1.0, (2000.0, 6.0, 4.0, -10.0, 15.0)),
          _load("S2", "service", 1.0, 1.0, (2100.0, 80.0, 10.0, -20.0, 250.0), True),
          _load("U1", "factored", 1.2, 1.6, (2900.0, 9.0, 6.0, -14.0, 22.0)),
          _load("U2", "factored", 1.2, 1.0, (2600.0, 120.0, 15.0, -30.0, 400.0), True)]
CAP_A = {"id": "A", "loads_from": "column",
         "lx": 2000.0, "ly": 2000.0, "h": 900.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 600.0,
         "pedestal_height": 0.0, "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0,
         "column": {"cx": 500.0, "cy": 500.0, "offset_x": 0.0, "offset_y": 0.0},
         "bottom": {"first": "x", "x": _mat("#7", 150.0), "y": _mat("#7", 150.0)},
         "top": {"first": "x", "x": _mat("#5", 250.0), "y": _mat("#5", 250.0)},
         "pile": {"shape": "circular", "size": 400.0, "embedment": 75.0},
         "mislocation_mm": 75.0,
         "piles": [{"id": f"P{i + 1}", "x": x, "y": y}
                   for i, (x, y) in enumerate(((-600.0, -600.0), (600.0, -600.0), (600.0, 600.0), (-600.0, 600.0)))],
         "loads": COLUMN}
# Dos pilotes a lo largo de Y: (P de P1, P de P2), Vy y Mx de la cabeza de cada pilote.
PILE_CASES = [("S1", "service", 1.0, 1.0, False, (1100.0, 1150.0), 10.0, 20.0),
              ("U1", "factored", 1.2, 1.6, False, (1500.0, 1600.0), 15.0, 30.0),
              ("U2", "factored", 1.2, 1.0, True, (1200.0, 1900.0), 60.0, 120.0)]
CAP_B = {"id": "B", "loads_from": "piles", "lx": 1200.0, "ly": 3600.0, "h": 800.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 0.0,
         "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
         "column": {"cx": 500.0, "cy": 500.0, "offset_x": 0.0, "offset_y": 0.0},
         "bottom": {"first": "y", "x": _mat("#6", 150.0), "y": _mat("#8", 100.0)},
         "top": {"first": "x", "x": _mat("#6", 150.0), "y": _mat("#6", 150.0)},
         "pile": {"shape": "circular", "size": 600.0, "embedment": 75.0},
         "mislocation_mm": 75.0, "reactions_include_weight": False,
         "piles": [{"id": name, "x": 0.0, "y": y,
                    "loads": [_load(case, kind, fd, fl, (reactions[index], 0.0, vy, mx, 0.0), seismic)
                              for case, kind, fd, fl, seismic, reactions, vy, mx in PILE_CASES]}
                   for index, (name, y) in enumerate((("P1", -1200.0), ("P2", 1200.0)))]}


# Simétrico, sin momentos: reacciones parcialmente interpoladas a d de las caras y a d/2 de la columna, y pilotes de
# esquina (P3).
CAP_C = {"id": "C", "loads_from": "column", "symmetric": True,
         "lx": 2000.0, "ly": 2000.0, "h": 700.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 0.0,
         "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
         "column": {"cx": 500.0, "cy": 500.0, "offset_x": 0.0, "offset_y": 0.0},
         "bottom": {"first": "x", "x": _mat("#7", 150.0), "y": _mat("#7", 150.0)},
         "top": {"first": "x", "x": _mat("#5", 250.0), "y": _mat("#5", 250.0)},
         "pile": {"shape": "circular", "size": 400.0, "embedment": 75.0}, "mislocation_mm": 75.0,
         "piles": [{"id": f"P{i + 1}", "x": x, "y": y} for i, (x, y) in enumerate(((-550.0, -550.0), (550.0, -550.0), (550.0, 550.0),
                                                                                     (-550.0, 550.0)))],
         "loads": [_load("S1", "service", 1.0, 1.0, (2400.0, 0.0, 0.0, 0.0, 0.0)),
                   _load("U1", "factored", 1.2, 1.6, (3400.0, 0.0, 0.0, 0.0, 0.0))]}


# Seis pilotes en dos filas de tres, lejos de la columna: cada fila punzona en conjunto (grupo de tres, D-138).
CAP_D = {"id": "D", "loads_from": "column",
         "lx": 3600.0, "ly": 3800.0, "h": 850.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 0.0,
         "pedestal_height": 0.0, "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
         "column": {"cx": 500.0, "cy": 500.0, "offset_x": 0.0, "offset_y": 0.0},
         "bottom": {"first": "x", "x": _mat("#7", 150.0), "y": _mat("#7", 150.0)},
         "top": {"first": "x", "x": _mat("#5", 250.0), "y": _mat("#5", 250.0)},
         "pile": {"shape": "circular", "size": 500.0, "embedment": 75.0}, "mislocation_mm": 75.0,
         "piles": [{"id": f"P{i + 1}", "x": x, "y": y} for i, (x, y) in enumerate(
             [(x, y) for y in (-1500.0, 1500.0) for x in (-1200.0, 0.0, 1200.0)])],
         "loads": [_load("S1", "service", 1.0, 1.0, (3000.0, 0.0, 0.0, 0.0, 0.0)),
                   _load("U1", "factored", 1.2, 1.6, (4200.0, 0.0, 0.0, 0.0, 0.0))]}


# Tres pilotes en triángulo con las dos esquinas superiores recortadas y la columna en el centroide del grupo (D-141).
CAP_E = {'loads_from': 'column',
         'lx': 2200.0,
         'ly': 2200.0,
         'h': 1000.0,
         'cover': 75.0,
         'bottom_cover': 150.0,
         'fill_height': 600.0,
         'pedestal_height': 0.0,
         'surcharge_dead_kNm2': 2.0,
         'surcharge_live_kNm2': 5.0,
         'column': {'cx': 500.0,
                    'cy': 500.0,
                    'offset_x': 0.0,
                    'offset_y': -253.6,
                    'dowels': {'designation': '#6', 'count': 8, 'end': 'hook90'}},
         'bottom': {'first': 'x',
                    'x': {'designation': '#7', 'spacing': 150.0, 'end': 'hook90'},
                    'y': {'designation': '#7', 'spacing': 150.0, 'end': 'hook90'}},
         'top': {'first': 'x',
                 'x': {'designation': '#5', 'spacing': 250.0, 'end': 'hook90'},
                 'y': {'designation': '#5', 'spacing': 250.0, 'end': 'hook90'}},
         'pile': {'shape': 'circular', 'size': 400.0, 'embedment': 75.0},
         'mislocation_mm': 75.0,
         'piles': [{'id': 'P1', 'x': 0.0, 'y': 439.2}, {'id': 'P2', 'x': -600.0, 'y': -600.0}, {'id': 'P3', 'x': 600.0, 'y': -600.0}],
         'loads': [{'case': 'D+L',
                    'kind': 'service',
                    'dead_factor': 1.0,
                    'live_factor': 1.0,
                    'P_kN': 1500.0,
                    'Vx_kN': 6.0,
                    'Vy_kN': 4.0,
                    'Mx_kNm': -10.0,
                    'My_kNm': 15.0},
                   {'case': 'D+L+0.7EX',
                    'kind': 'service',
                    'dead_factor': 1.0,
                    'live_factor': 1.0,
                    'seismic': True,
                    'P_kN': 1575.0,
                    'Vx_kN': 80.0,
                    'Vy_kN': 10.0,
                    'Mx_kNm': -20.0,
                    'My_kNm': 250.0},
                   {'case': '0.6D+0.7EX',
                    'kind': 'service',
                    'dead_factor': 0.6,
                    'live_factor': 0.0,
                    'seismic': True,
                    'P_kN': 675.0,
                    'Vx_kN': 80.0,
                    'Vy_kN': 10.0,
                    'Mx_kNm': -20.0,
                    'My_kNm': 250.0},
                   {'case': '1.2D+1.6L',
                    'kind': 'factored',
                    'dead_factor': 1.2,
                    'live_factor': 1.6,
                    'P_kN': 2175.0,
                    'Vx_kN': 9.0,
                    'Vy_kN': 6.0,
                    'Mx_kNm': -14.0,
                    'My_kNm': 22.0},
                   {'case': '1.2D+L+EX',
                    'kind': 'factored',
                    'dead_factor': 1.2,
                    'live_factor': 1.0,
                    'seismic': True,
                    'P_kN': 1950.0,
                    'Vx_kN': 120.0,
                    'Vy_kN': 15.0,
                    'Mx_kNm': -30.0,
                    'My_kNm': 400.0},
                   {'case': '0.9D+EX',
                    'kind': 'factored',
                    'dead_factor': 0.9,
                    'live_factor': 0.0,
                    'seismic': True,
                    'P_kN': 825.0,
                    'Vx_kN': 120.0,
                    'Vy_kN': 15.0,
                    'Mx_kNm': -30.0,
                    'My_kNm': 400.0}],
         'clipped_corners': [{'corner': '-x+y', 'along_x': 700.0, 'along_y': 1100.0},
                             {'corner': '+x+y', 'along_x': 700.0, 'along_y': 1100.0}],
         'id': 'E'}


def _uniform(cap: dict, load: dict) -> float:
    """q hacia abajo en N/mm²."""
    dead = GAMMA_C * cap["h"] + GAMMA_F * cap["fill_height"] + cap["surcharge_dead_kNm2"] * 1e-3
    return load["dead_factor"] * dead + load["live_factor"] * cap["surcharge_live_kNm2"] * 1e-3


def _outline(cap: dict) -> list[tuple[float, float]]:
    """Contorno antihorario con las esquinas recortadas (D-141)."""
    hx, hy = cap["lx"] / 2, cap["ly"] / 2
    clips = {c["corner"]: c for c in cap.get("clipped_corners", [])}
    points = []
    for key, sx, sy in (("-x-y", -1, -1), ("+x-y", 1, -1), ("+x+y", 1, 1), ("-x+y", -1, 1)):
        c = clips.get(key)
        if c is None:
            points.append((sx * hx, sy * hy))
            continue
        side, top = (sx * hx, sy * (hy - c["along_y"])), (sx * (hx - c["along_x"]), sy * hy)
        points += [side, top] if key in ("-x-y", "+x+y") else [top, side]
    return points


def _shoelace(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Área y centroide de un polígono."""
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        k = x1 * y2 - x2 * y1
        a, cx, cy = a + k, cx + (x1 + x2) * k, cy + (y1 + y2) * k
    return (abs(a) / 2, cx / (3 * a), cy / (3 * a)) if abs(a) > 1e-9 else (0.0, 0.0, 0.0)


def _half(points: list[tuple[float, float]], axis: int, plane: float, outward: float) -> list[tuple[float, float]]:
    """La parte del polígono con outward·(coordenada − plane) ≥ 0."""
    out = []
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        fa, fb = outward * (a[axis] - plane), outward * (b[axis] - plane)
        if fa >= 0:
            out.append(a)
        if (fa >= 0) != (fb >= 0):
            t = fa / (fa - fb)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return out


def _weight(cap: dict, load: dict) -> float:
    area = _shoelace(_outline(cap))[0]
    net = area - cap["column"]["cx"] * cap["column"]["cy"]
    dead = GAMMA_C * area * cap["h"] + (GAMMA_F * cap["fill_height"] + cap["surcharge_dead_kNm2"] * 1e-3) * net
    return load["dead_factor"] * dead + load["live_factor"] * cap["surcharge_live_kNm2"] * 1e-3 * net


def _cases(cap: dict) -> list[dict]:
    """Por caso: carga de referencia, R, ΔR y fuerzas de la cabeza (Vx, Vy, Mx, My) de cada pilote, en N y N·mm."""
    piles, tolerance, e = cap["piles"], cap["mislocation_mm"], cap["pile"]["embedment"]
    n = len(piles)
    out = []
    if "loads" in cap:
        for load in cap["loads"]:
            p, vx, vy = load["P_kN"] * 1e3, load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
            mx, my = load["Mx_kNm"] * 1e6, load["My_kNm"] * 1e6
            total = p + _weight(cap, load)
            arm = cap["h"] + cap["pedestal_height"] - e
            column = cap["column"]
            ox, oy, acol = column["offset_x"], column["offset_y"], column["cx"] * column["cy"]
            # La columna desplaza el relleno y las sobrecargas que el peso uniforme cuenta en todo el contorno.
            vertical = p - (load["dead_factor"] * (GAMMA_F * cap["fill_height"] + cap["surcharge_dead_kNm2"] * 1e-3)
                            + load["live_factor"] * cap["surcharge_live_kNm2"] * 1e-3) * acol
            area, xc, yc = _shoelace(_outline(cap))
            spread_weight = _uniform(cap, load) * area
            my_h = my + arm * vx + vertical * ox + spread_weight * xc
            mx_h = mx - arm * vy - vertical * oy - spread_weight * yc
            # Reparto rígido respecto al centroide del grupo con la matriz completa (resuelta por Cramer).
            xg, yg = sum(p_["x"] for p_ in piles) / n, sum(p_["y"] for p_ in piles) / n
            dxs, dys = [p_["x"] - xg for p_ in piles], [p_["y"] - yg for p_ in piles]
            kxx, kyy = sum(v * v for v in dxs), sum(v * v for v in dys)
            kxy = sum(a_ * b_ for a_, b_ in zip(dxs, dys, strict=True))
            det = kxx * kyy - kxy * kxy
            my_c, mx_c = my_h - total * xg, mx_h + total * yg
            bx = (my_c * kyy - kxy * -mx_c) / det
            by = (kxx * -mx_c - kxy * my_c) / det
            reactions = [total / n + bx * dxs[i] + by * dys[i] for i in range(n)]
            gx = [(kyy * dxs[i] - kxy * dys[i]) / det for i in range(n)]
            gy = [(kxx * dys[i] - kxy * dxs[i]) / det for i in range(n)]
            spread = [abs(total) * tolerance * math.hypot(gx[i], gy[i]) for i in range(n)]
            heads = [(vx / n, vy / n, 0.0, 0.0)] * n
            out.append({"load": load, "R": reactions, "dR": spread, "heads": heads, "column": p, "spread_on_cap": True})
        return out
    for index, load in enumerate(piles[0]["loads"]):
        own = [pile["loads"][index] for pile in piles]
        share = 0.0 if cap["reactions_include_weight"] else _weight(cap, load) / n
        reactions = [item["P_kN"] * 1e3 + share for item in own]
        heads = [(item["Vx_kN"] * 1e3, item["Vy_kN"] * 1e3, item["Mx_kNm"] * 1e6, item["My_kNm"] * 1e6) for item in own]
        out.append({"load": load, "R": reactions, "dR": [0.0] * n, "heads": heads,
                    "column": sum(reactions) - _weight(cap, load), "spread_on_cap": False})
    return out


def _depths(cap: dict) -> dict[str, float]:
    first = cap["bottom"]["first"]
    second = "y" if first == "x" else "x"
    d1 = BARS[cap["bottom"][first]["designation"]][0]
    d2 = BARS[cap["bottom"][second]["designation"]][0]
    return {first: cap["h"] - cap["bottom_cover"] - d1 / 2, second: cap["h"] - cap["bottom_cover"] - d1 - d2 / 2}


def _rows(cap: dict, direction: str, mat: str = "bottom") -> tuple[float, float]:
    """(ancho, As) de las barras de una malla en una dirección: centradas en el ancho menos recubrimiento y medio diámetro."""
    bar = cap[mat][direction]
    db, area = BARS[bar["designation"]]
    width = cap["ly"] if direction == "x" else cap["lx"]
    span = width - 2 * cap["cover"] - db
    count = math.floor(span / bar["spacing"] + 1e-6) + 1
    return width, count * area


def _beyond(cap: dict, case: dict, axis: int, plane: float, outward: float, sense: float) -> tuple[float, float, float]:
    """(V interpolado, V completo, M) más allá del plano, con R + sense·ΔR. Un pilote cuenta si su distancia más la
    tolerancia queda más allá: reacción completa, brazo y acción de la cabeza."""
    tolerance, size, lever = cap["mislocation_mm"], cap["pile"]["size"], cap["pile"]["embedment"] - cap["h"] / 2
    q = _uniform(cap, case["load"])
    shear = full = moment = 0.0
    for i, pile in enumerate(cap["piles"]):
        r = case["R"][i] + sense * case["dR"][i]
        arm = outward * ((pile["x"], pile["y"])[axis] - plane) + tolerance
        shear += min(max(0.5 + arm / size, 0.0), 1.0) * r
        if arm <= 0:
            continue
        full += r
        moment += r * arm
        vx, vy, mx, my = case["heads"][i]
        moment += -outward * (my + lever * vx) if axis == 0 else outward * (mx - lever * vy)
    piece = _half(_outline(cap), axis, plane, outward)
    area, xc, yc = _shoelace(piece) if len(piece) >= 3 else (0.0, 0.0, 0.0)
    w = q * area
    return shear - w, full - w, moment - w * outward * ((xc, yc)[axis] - plane)


def _sense(case: dict) -> float:
    """+1 si la mala ubicación aumenta las reacciones (cargas de la columna), 0 si no."""
    return 1.0 if case["spread_on_cap"] else 0.0


def _perimeter(centre: tuple[float, float], size: tuple[float, float], d: float, bounds: tuple[float, float]) -> tuple[float, int] | None:
    """Longitud b0 y lados perdidos del perímetro a d/2 de un rectángulo c1 × c2 recortado con el cabezal (|x| ≤ hx,
    |y| ≤ hy); None si pierde más de dos lados."""
    (x, y), (c1, c2), (hx, hy) = centre, size, bounds
    left, right, bottom, top = x - (c1 + d) / 2, x + (c1 + d) / 2, y - (c2 + d) / 2, y + (c2 + d) / 2
    inside = {"left": left > -hx, "right": right < hx, "bottom": bottom > -hy, "top": top < hy}
    lost = sum(1 for value in inside.values() if not value)
    if lost > 2:
        return None
    width = min(right, hx) - max(left, -hx)
    height = min(top, hy) - max(bottom, -hy)
    b0 = (inside["bottom"] + inside["top"]) * width + (inside["left"] + inside["right"]) * height
    return b0, lost


def _vc_two_way(folder: str, given: tuple[float, float, float, float]) -> float:
    """vc de dos direcciones (MPa) con (β, αs, d/b0, λs)."""
    beta, alpha, ratio, lam_s = given
    if folder == "aci_318_25":
        return min(0.33, 0.17 + 0.33 / beta, 0.17 + 0.083 * alpha * ratio) * lam_s * SQRT_FC
    return min(0.17 * (1 + 2 / beta), 0.083 * (alpha * ratio + 2), 0.33) * SQRT_FC


def _required_area(b: float, d: float, mu: float) -> float:
    k = 0.85 * FC * b
    return (k / FY) * (d - math.sqrt(d * d - 2 * mu / (PHI_M * k))) if mu > 0 else 0.0


def _spaced(cap: dict) -> bool:
    piles = cap["piles"]
    nearest = [min(math.dist((a["x"], a["y"]), (b["x"], b["y"])) for b in piles if b is not a) for a in piles]
    return len(piles) > 1 and max(nearest) <= 4 * cap["pile"]["size"]


def _vc_one_way(folder: str, section: tuple[float, float, float], vu: float, mu: float, spaced: bool) -> float:
    b, d, rho = section
    if folder == "aci_318_25":
        lam_s = min(math.sqrt(2 / (1 + d / 250)), 1.0)
        vc = 0.66 * lam_s * rho ** (1 / 3) * SQRT_FC * b * d
        vc = max(min(vc, 0.42 * SQRT_FC * b * d), 0.083 * SQRT_FC * b * d)
        return max(vc, 0.17 * SQRT_FC * b * d) if spaced else vc
    ratio = min(vu * d / mu, 1.0) if mu > 0 else 1.0
    detailed = min((0.16 * SQRT_FC + 17 * rho * ratio) * b * d, 0.29 * SQRT_FC * b * d)
    return max(0.17 * SQRT_FC * b * d, detailed)


def _service(folder: str, cap: dict, cases: list[dict]) -> list[dict]:
    soil = SOIL[cap["id"]]
    mislocation = 1.10 if folder == "aci_318_25" and "loads" in cap else 1.0
    spread, n = "loads" in cap, len(cap["piles"])
    expected = []
    for case in (case for case in cases if case["load"]["kind"] == "service"):
        name, seismic = case["load"]["case"], case["load"].get("seismic", False)
        fs = soil["seismic_capacity_factor"] if seismic else 1.0
        demand = max(r + (dr if spread else 0.0) for r, dr in zip(case["R"], case["dR"], strict=True))
        qa = soil["pile_capacity_compression_kN"] * 1e3
        expected.append({"name": "Presion admisible del pilote: compresion", "case": name, "demand": demand,
                         "capacity": mislocation * fs * qa})
        lateral = max(math.hypot(h[0], h[1]) for h in case["heads"])
        if lateral > 1.0:
            expected.append({"name": "Deslizamiento del pilote", "case": name, "demand": lateral,
                             "capacity": fs * soil["pile_capacity_lateral_kN"] * 1e3})
        expected.append({"name": "Capacidad del grupo de pilotes", "case": name, "demand": sum(case["R"]),
                         "capacity": soil["group_efficiency"] * n * fs * qa})
        if not seismic:
            total = sum(case["R"])
            xc, yc = sum(p["x"] for p in cap["piles"]) / n, sum(p["y"] for p in cap["piles"]) / n
            ex = sum(r * p["x"] for r, p in zip(case["R"], cap["piles"], strict=True)) / total - xc
            ey = sum(r * p["y"] for r, p in zip(case["R"], cap["piles"], strict=True)) / total - yc
            expected.append({"name": "Excentricidad en servicio", "case": name, "demand": math.hypot(ex, ey),
                             "capacity": soil["max_eccentricity_mm"]})
    return expected


def _faces(cap: dict) -> dict[str, tuple[float, float]]:
    column = cap["column"]
    ox, oy = column["offset_x"], column["offset_y"]
    return {"x": (ox + column["cx"] / 2, ox - column["cx"] / 2), "y": (oy + column["cy"] / 2, oy - column["cy"] / 2)}


def _minimum(cap: dict, moments: dict) -> list[dict]:
    depths, minimum = _depths(cap), []
    for direction in ("x", "y"):
        b, area = _rows(cap, direction)
        d = depths[direction]
        mu = max(max(pair) for (_, axis), pair in moments.items() if axis == direction)
        analysis = _required_area(b, d, mu)
        eta_bd = max(0.25 * math.sqrt(FC), 1.4) / FY * b * d
        required = max(analysis, min(eta_bd, 4 / 3 * analysis), min(eta_bd, 0.0018 * b * cap["h"]))
        minimum.append({"direction": direction, "required": required, "provided": area})
    return minimum


def _line_interval(outline: list[tuple[float, float]], axis: int, value: float) -> tuple[float, float] | None:
    """Intervalo de la otra coordenada de la recta (x = value si axis = 0) dentro del contorno."""
    hits = []
    for a, b in zip(outline, outline[1:] + outline[:1], strict=True):
        if (a[axis] - value) * (b[axis] - value) > 0 or a[axis] == b[axis]:
            continue
        t = (value - a[axis]) / (b[axis] - a[axis])
        hits.append(a[1 - axis] + t * (b[1 - axis] - a[1 - axis]))
    return (min(hits), max(hits)) if hits else None


def _section(cap: dict, direction: str, plane: float) -> tuple[float, float]:
    """(ancho, As) de la sección normal a las barras de una dirección en plane, con el contorno recortado: la cuerda y
    las barras cuyo tramo (de borde a borde menos el recubrimiento) cruza la sección."""
    axis = 0 if direction == "x" else 1
    outline = _outline(cap)
    across = _line_interval(outline, axis, plane)
    bar = cap["bottom"][direction]
    db, ab = BARS[bar["designation"]]
    width = cap["ly"] if direction == "x" else cap["lx"]
    half = width / 2 - cap["cover"] - db / 2
    count = math.floor(2 * half / bar["spacing"] + 1e-6) + 1
    start = -half + (2 * half - (count - 1) * bar["spacing"]) / 2
    crossing = 0
    for i in range(count):
        span = _line_interval(outline, 1 - axis, start + i * bar["spacing"])
        if span is not None and span[0] + cap["cover"] - 1e-6 <= plane <= span[1] - cap["cover"] + 1e-6:
            crossing += 1
    return (0.0 if across is None else across[1] - across[0]), crossing * ab


def _one_way(folder: str, cap: dict, case: dict) -> list[dict]:
    """Cortante a d de las caras (interpolado) y estados límite 5 y 6 en las caras."""
    depths, faces, out = _depths(cap), _faces(cap), []
    name = case["load"]["case"]
    for direction, axis in (("x", 0), ("y", 1)):
        b, area = _rows(cap, direction)
        d = depths[direction]
        half = (cap["lx"] if axis == 0 else cap["ly"]) / 2
        plus, minus = faces[direction]
        worst = None
        for plane, outward in ((plus + d, 1.0), (minus - d, -1.0)):
            if abs(plane) >= half:
                continue
            v, _, m = _beyond(cap, case, axis, plane, outward, _sense(case))
            width, steel = _section(cap, direction, plane) if cap.get("clipped_corners") else (b, area)
            capacity = PHI_V * _vc_one_way(folder, (width, d, steel / (width * d)), abs(v), abs(m), _spaced(cap))
            if worst is None or abs(v) / capacity > worst[0]:
                worst = (abs(v) / capacity, abs(v), capacity)
        if worst is not None:
            out.append({"name": f"Cortante en una direccion (barras {direction})", "case": name, "demand": worst[1], "capacity": worst[2]})
        for plane, outward in ((plus, 1.0), (minus, -1.0)):
            t = cap["mislocation_mm"]
            near = [value for value in (outward * ((p["x"], p["y"])[axis] - plane) for p in cap["piles"]) if value + t > 0]
            if not near or min(near) >= d:
                continue
            w = min([value for value in near if value > 0], default=0.0) + t
            _, v, m = _beyond(cap, case, axis, plane, outward, _sense(case))
            v, m = max(v, 0.0), max(m, 0.0)  # sin cortante o momento positivos, el tope de vc
            if v <= 0 or m <= 0:
                stress = 10 * 0.083 * SQRT_FC
            else:
                ratio = min(m / (v * d), 1.0)
                stress = min(d / w * (3.5 - 2.5 * ratio) * (1.9 * 0.083 + 0.1 * 0.083 / ratio), 10 * 0.083) * SQRT_FC
            face_width = _section(cap, direction, plane)[0] if cap.get("clipped_corners") else b  # el ancho en la cara
            out.append({"name": f"Cortante en la cara de la columna (barras {direction})", "case": name, "demand": v,
                        "capacity": PHI_V * stress * face_width * d})
    return out


def _two_way(folder: str, cap: dict, case: dict) -> list[dict]:
    """Estado límite 4 en la cara de la columna y punzonamiento P1 de cada pilote."""
    depths, column, pile, out = _depths(cap), cap["column"], cap["pile"], []
    davg = (depths["x"] + depths["y"]) / 2
    name = case["load"]["case"]
    t, sense = cap["mislocation_mm"], _sense(case)
    outside = [(max(abs(p["x"] - column["offset_x"]) - column["cx"] / 2, abs(p["y"] - column["offset_y"]) - column["cy"] / 2), i)
               for i, p in enumerate(cap["piles"])]
    outside = [item for item in outside if item[0] + t > 0]
    if outside and min(outside)[0] < davg / 2:
        w = min([distance for distance, _ in outside if distance > 0], default=0.0) + t
        c, bs = (column["cx"] + column["cy"]) / 2, 2 * (column["cx"] + column["cy"])
        v = sum(case["R"][i] + sense * case["dR"][i] for _, i in outside)
        v -= _uniform(cap, case["load"]) * (_shoelace(_outline(cap))[0] - column["cx"] * column["cy"])
        stress = min(davg / w * (1 + davg / c) * 2 * 0.083, 32 * 0.083) * SQRT_FC
        out.append({"name": "Cortante en la cara de la columna (dos direcciones)", "case": name, "demand": v,
                    "capacity": PHI_V * stress * bs * davg})
    side = math.sqrt(math.pi) * pile["size"] / 2
    lam_s = 1.0 if folder == "nsr_10" or _spaced(cap) else min(math.sqrt(2 / (1 + davg / 250)), 1.0)
    bounds = (cap["lx"] / 2, cap["ly"] / 2)
    alpha = {0: 40.0, 1: 30.0, 2: 20.0}
    for i, p in enumerate(cap["piles"]):
        r = case["R"][i] + sense * case["dR"][i]
        if r <= 1.0:
            continue
        shapes = [((p["x"], p["y"]), (side, side))]
        key = f"{'+' if p['x'] > 0 else '-'}x{'+' if p['y'] > 0 else '-'}y"
        if p["x"] and p["y"] and key not in {c["corner"] for c in cap.get("clipped_corners", [])}:
            c1, c2 = bounds[0] - abs(p["x"]) + side / 2, bounds[1] - abs(p["y"]) + side / 2
            shapes.append(((math.copysign(bounds[0] - c1 / 2, p["x"]), math.copysign(bounds[1] - c2 / 2, p["y"])), (c1, c2)))
        best = None
        for centre, size in shapes:
            clipped_cap = cap.get("clipped_corners")
            found = _poly_perimeter(centre, size, davg, _outline(cap)) if clipped_cap else _perimeter(centre, size, davg, bounds)
            if found is None:
                continue
            b0, lost = found
            beta = max(size) / min(size)
            demand, capacity = r / (b0 * davg), PHI_V * _vc_two_way(folder, (beta, alpha[lost], davg / b0, lam_s))
            if best is None or demand / capacity > best[0]:
                best = (demand / capacity, demand, capacity)
        if best is not None:
            out.append({"name": "Punzonamiento del pilote", "case": name, "demand": best[1], "capacity": best[2]})
    out += _pairs_and_corners(folder, cap, case, (davg, lam_s, sense))
    if cap.get("symmetric"):  # punzonamiento de la columna sin momento transferido (oráculo del caso simétrico)
        found = _perimeter((0.0, 0.0), (column["cx"], column["cy"]), davg, bounds)
        assert found is not None
        b0, lost = found
        hx, hy = (column["cx"] + davg) / 2, (column["cy"] + davg) / 2
        region = (2 * min(hx, bounds[0])) * (2 * min(hy, bounds[1]))
        force = -_uniform(cap, case["load"]) * (cap["lx"] * cap["ly"] - region)
        for i, p in enumerate(cap["piles"]):
            share = min(max(0.5 + (max(abs(p["x"]) - hx, abs(p["y"]) - hy) + t) / pile["size"], 0.0), 1.0)
            force += share * (case["R"][i] + sense * case["dR"][i])
        beta = max(column["cx"], column["cy"]) / min(column["cx"], column["cy"])
        out.append({"name": "Punzonamiento", "case": name, "demand": force / (b0 * davg),
                    "capacity": PHI_V * _vc_two_way(folder, (beta, alpha[lost], davg / b0, lam_s))})
    return out


def _gift_wrap(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Envolvente convexa por envoltura de regalo (otro algoritmo que el del programa)."""
    unique = sorted(set(points))
    if len(unique) <= 2:
        return unique
    hull, start = [], unique[0]
    current = start
    while True:
        hull.append(current)
        candidate = unique[0] if unique[0] != current else unique[1]
        for point in unique:
            turn = (candidate[0] - current[0]) * (point[1] - current[1]) - (candidate[1] - current[1]) * (point[0] - current[0])
            if turn < 0 or (turn == 0 and math.dist(current, point) > math.dist(current, candidate)):
                candidate = point
        current = candidate
        if current == start:
            return hull


def _segment_to_box(a: tuple[float, float], b: tuple[float, float], box: tuple[float, float, float, float]) -> float:
    """Distancia exacta segmento–rectángulo: 0 si el segmento cruza el rectángulo (Liang–Barsky); si no, la menor entre
    los extremos al rectángulo y las esquinas al segmento."""
    x0, y0, x1, y1 = box
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                low, high = 1.0, 0.0
        else:
            t = q / p
            low, high = (max(low, t), high) if p < 0 else (low, min(high, t))
    if low <= high:
        return 0.0
    def to_box(x: float, y: float) -> float:
        return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))
    def to_segment(x: float, y: float) -> float:
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else min(max(((x - a[0]) * dx + (y - a[1]) * dy) / length, 0.0), 1.0)
        return math.hypot(x - a[0] - t * dx, y - a[1] - t * dy)
    return min(to_box(*a), to_box(*b), *(to_segment(x, y) for x in (x0, x1) for y in (y0, y1)))


def _groups(folder: str, cap: dict, case: dict, given: tuple[float, float, float]) -> list[dict]:
    """Grupos de 3 o más pilotes conexos (L < π(dp + d)/2), con b0 = perímetro de la envolvente convexa + π(dp + d) menor
    que el de los aislados y sin alcanzar el perímetro crítico de la columna: el que gobierna en el caso."""
    import itertools
    d, lam_s, sense = given
    piles, dp, name = cap["piles"], cap["pile"]["size"], case["load"]["case"]
    single, radius = math.pi * (dp + d), (dp + d) / 2
    column = cap["column"]
    box = (-(column["cx"] + d) / 2, -(column["cy"] + d) / 2, (column["cx"] + d) / 2, (column["cy"] + d) / 2)
    reaction = [case["R"][i] + sense * case["dR"][i] for i in range(len(piles))]
    best = None
    for size in range(3, len(piles) + 1):
        for members in itertools.combinations(range(len(piles)), size):
            linked, todo = {members[0]}, [members[0]]
            while todo:
                i = todo.pop()
                for j in members:
                    if j not in linked and math.dist((piles[i]["x"], piles[i]["y"]), (piles[j]["x"], piles[j]["y"])) < single / 2:
                        linked.add(j)
                        todo.append(j)
            if len(linked) != size or min(reaction[i] for i in members) <= 1.0:
                continue
            hull = _gift_wrap([(piles[i]["x"], piles[i]["y"]) for i in members])
            edges = list(zip(hull, hull[1:] + hull[:1], strict=True)) if len(hull) > 2 else [(hull[0], hull[-1])]
            length = sum(math.dist(a, b) for a, b in edges) if len(hull) > 2 else 2 * math.dist(hull[0], hull[-1])
            b0 = length + single
            if b0 >= size * single or min(_segment_to_box(a, b, box) for a, b in edges) < radius:
                continue
            xs, ys = [piles[i]["x"] for i in members], [piles[i]["y"] for i in members]
            sides = sorted((max(xs) - min(xs) + dp, max(ys) - min(ys) + dp))
            vc = _vc_two_way(folder, (sides[1] / sides[0], 40.0, d / b0, lam_s))
            demand = sum(reaction[i] for i in members) / (b0 * d)
            if best is None or demand / (PHI_V * vc) > best[0]:
                best = (demand / (PHI_V * vc), demand, PHI_V * vc)
    return [] if best is None else [{"name": "Punzonamiento de un grupo de pilotes", "case": name, "demand": best[1],
                                     "capacity": best[2]}]


def _pairs_and_corners(folder: str, cap: dict, case: dict, given: tuple[float, float, float]) -> list[dict]:
    """Guía CRSI P2 (dos pilotes vecinos con L < π(dp + d)/2: b0 = π(dp + d) + 2L, vc de la norma con β = (L + dp)/dp y
    αs = 40) y P4 (esquina: b = 2·((Ex + Ey)/√2 + dp/2 + mín(d, 330)), φ·0.166√f'c·b·d), con las reacciones mayoradas."""
    d, lam_s, sense = given
    piles, dp, name = cap["piles"], cap["pile"]["size"], case["load"]["case"]
    reaction = [case["R"][i] + sense * case["dR"][i] for i in range(len(piles))]
    out = []
    for i in range(len(piles)):
        for j in range(i + 1, len(piles)):
            spacing = math.dist((piles[i]["x"], piles[i]["y"]), (piles[j]["x"], piles[j]["y"]))
            if spacing >= math.pi * (dp + d) / 2 or min(reaction[i], reaction[j]) <= 1.0:
                continue
            b0 = math.pi * (dp + d) + 2 * spacing
            vc = _vc_two_way(folder, ((spacing + dp) / dp, 40.0, d / b0, lam_s))
            out.append({"name": "Punzonamiento de dos pilotes", "case": name, "demand": (reaction[i] + reaction[j]) / (b0 * d),
                        "capacity": PHI_V * vc})
    out += _groups(folder, cap, case, given)
    hx, hy = cap["lx"] / 2, cap["ly"] / 2
    corners = []
    clipped = {c["corner"] for c in cap.get("clipped_corners", [])}
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        if f"{'+' if sx > 0 else '-'}x{'+' if sy > 0 else '-'}y" in clipped:
            continue
        k = min(range(len(piles)), key=lambda i: math.dist((sx * hx, sy * hy), (piles[i]["x"], piles[i]["y"])))
        if piles[k]["x"] * sx > 0 and piles[k]["y"] * sy > 0 and k not in corners:
            corners.append(k)
    for k in corners:
        if reaction[k] <= 1.0:
            continue
        ex, ey = hx - abs(piles[k]["x"]), hy - abs(piles[k]["y"])
        reach = (ex + ey) / math.sqrt(2) + dp / 2 + min(d, 330.0)
        if reach * math.sqrt(2) > min(cap["lx"], cap["ly"]):
            continue
        out.append({"name": "Cortante de esquina del pilote", "case": name, "demand": reaction[k],
                    "capacity": PHI_V * 2 * 0.083 * SQRT_FC * 2 * reach * d})
    for c in cap.get("clipped_corners", []):  # P4 de cada recorte: la sección paralela al recorte (D-141)
        sx, sy = (1 if c["corner"][0] == "+" else -1), (1 if c["corner"][2] == "+" else -1)
        a, b = (sx * hx, sy * (hy - c["along_y"])), (sx * (hx - c["along_x"]), sy * hy)
        middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        k = min(range(len(piles)), key=lambda i: math.dist(middle, (piles[i]["x"], piles[i]["y"])))
        if reaction[k] <= 1.0:
            continue
        length = math.dist(a, b)
        distance = abs((b[0] - a[0]) * (a[1] - piles[k]["y"]) - (a[0] - piles[k]["x"]) * (b[1] - a[1])) / length
        offset = distance + dp / 2 + min(d, 330.0)
        width = _chord_parallel(_outline(cap), (a, b), offset, (piles[k]["x"], piles[k]["y"]))
        out.append({"name": "Cortante de esquina del pilote", "case": name, "demand": reaction[k],
                    "capacity": PHI_V * 2 * 0.083 * SQRT_FC * width * d})
    return out


def _poly_perimeter(centre: tuple[float, float], size: tuple[float, float], d: float,
                    outline: list[tuple[float, float]]) -> tuple[float, int] | None:
    """b0 y lados perdidos del perímetro a d/2 recortado con un contorno convexo: cada lado se recorta muestreando su
    parte dentro del contorno con bisección en los extremos (otro método que el del programa)."""
    (x, y), (c1, c2) = centre, size
    corners = [(x - (c1 + d) / 2, y - (c2 + d) / 2), (x + (c1 + d) / 2, y - (c2 + d) / 2), (x + (c1 + d) / 2, y + (c2 + d) / 2),
               (x - (c1 + d) / 2, y + (c2 + d) / 2)]

    def inside(point: tuple[float, float]) -> bool:
        return all((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) >= -1e-9
                   for a, b in zip(outline, outline[1:] + outline[:1], strict=True))

    total, lost = 0.0, 0
    for a, b in zip(corners, corners[1:] + corners[:1], strict=True):
        steps = 2000
        ts = [i / steps for i in range(steps + 1)]
        kept = [t for t in ts if inside((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))]
        if not kept:
            lost += 1
            continue
        def edge(t_in: float, t_out: float, a: tuple[float, float] = a, b: tuple[float, float] = b) -> float:
            for _ in range(60):
                mid = (t_in + t_out) / 2
                if inside((a[0] + mid * (b[0] - a[0]), a[1] + mid * (b[1] - a[1]))):
                    t_in = mid
                else:
                    t_out = mid
            return t_in
        low = kept[0] if kept[0] == 0.0 else edge(kept[0], kept[0] - 1 / steps)
        high = kept[-1] if kept[-1] == 1.0 else edge(kept[-1], kept[-1] + 1 / steps)
        total += (high - low) * math.dist(a, b)
    return (total, lost) if lost <= 2 else None


def _chord_parallel(outline: list[tuple[float, float]], edge: tuple[tuple[float, float], tuple[float, float]], offset: float,
                    toward: tuple[float, float]) -> float:
    """Longitud dentro del contorno de la recta paralela a edge a la distancia offset, del lado del punto toward."""
    (ax, ay), (bx, by) = edge
    length = math.dist(edge[0], edge[1])
    ux, uy = (bx - ax) / length, (by - ay) / length
    nx, ny = -uy, ux
    if nx * (toward[0] - ax) + ny * (toward[1] - ay) < 0:
        nx, ny = -nx, -ny
    px, py = ax + nx * offset, ay + ny * offset
    ts = []
    for a, b in zip(outline, outline[1:] + outline[:1], strict=True):
        den = (b[0] - a[0]) * uy - (b[1] - a[1]) * ux
        if abs(den) < 1e-12:
            continue
        s_edge = ((px - a[0]) * uy - (py - a[1]) * ux) / den
        if -1e-12 <= s_edge <= 1 + 1e-12:
            hit = (a[0] + s_edge * (b[0] - a[0]), a[1] + s_edge * (b[1] - a[1]))
            ts.append((hit[0] - px) * ux + (hit[1] - py) * uy)
    return max(ts) - min(ts) if len(ts) >= 2 else 0.0


def _as_input(cap: dict) -> dict:
    """El cabezal en el formato de entrada (D-143): la columna, con sus cargas si las hay, en columns."""
    out = {key: value for key, value in cap.items() if key not in ("symmetric", "column", "loads")}
    column = {"id": "C1", **cap["column"], **({"loads": cap["loads"]} if cap.get("loads") else {})}
    return {**out, "columns": [column]}


def _derive(folder: str, cap: dict) -> dict:
    cases = _cases(cap)
    faces = _faces(cap)
    factored = [case for case in cases if case["load"]["kind"] == "factored"]
    moments = {}
    for case in factored:
        variants = [("", 0.0)] if not case["spread_on_cap"] else [(" (+ΔR)", 1.0), (" (−ΔR)", -1.0)]
        for suffix, sense in variants:
            for direction, axis in (("x", 0), ("y", 1)):
                plus, minus = faces[direction]
                moments[(case["load"]["case"] + suffix, direction)] = (_beyond(cap, case, axis, plus, 1.0, sense)[2],
                                                                       _beyond(cap, case, axis, minus, -1.0, sense)[2])
    checks = _service(folder, cap, cases)
    for case in factored:
        checks += [*_one_way(folder, cap, case), *_two_way(folder, cap, case)]
    for direction in ("x", "y"):  # retracción con las dos mallas sumadas (D-140)
        b, bottom = _rows(cap, direction)
        top = _rows(cap, direction, "top")[1] if cap["top"] is not None else 0.0
        checks.append({"name": f"Retraccion y temperatura: cuantia (barras {direction})", "case": None,
                       "demand": 0.0018 * b * cap["h"], "capacity": bottom + top})
    return {"id": cap["id"], "cap": _as_input(cap), "soil": SOIL[cap["id"]],
            "reactions": [{"case": c["load"]["case"], "R": c["R"], "dR": c["dR"]} for c in cases],
            "moments": [{"case": key[0], "direction": key[1], "plus": value[0], "minus": value[1]} for key, value in moments.items()],
            "minimum": _minimum(cap, moments), "checks": checks}


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        data = {"description": "Oraculo de cabezales (D-138), derivado por tests/oracles/derive_pile_cap.py",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated", "max_aggregate": 19.0},
                "tolerance_rel": 1e-6,
                "cases": [_derive(folder, cap) for cap in (CAP_A, CAP_B, CAP_C, CAP_D, CAP_E)]}
        (HERE / folder / "derived_pile_cap.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                                             newline="\n")
    print("ok")


if __name__ == "__main__":
    main()
