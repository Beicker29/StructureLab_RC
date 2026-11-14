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
4. As mínimo (guía CRSI 4.5): As = máx(As análisis, mín(ηbd, 4/3·As análisis), mín(ηbd, ρt·b·h)), η = máx(0.25√f'c,
   1.4)/fy, ρt = 0.0018 (fy = 420), As análisis de la ecuación cuadrática con φ = 0.9.
5. Cortante en una dirección a d de la cara con la reacción interpolada (0.5 + (dist + t)/dpile, entre 0 y 1). ACI 22.5
   sin Av,min: Vc = 0.66λs·λ·ρw^(1/3)·√f'c·b·d (λs = √(2/(1 + d/250)) ≤ 1), entre 0.083 y 0.42 λ√f'c·b·d; con pilotes a
   4D o menos, el mayor entre ese y 0.17λ√f'c·b·d (13.4.6.8(a), decisión del usuario). NSR-10: el
   mayor de 0.17λ√f'c·b·d y (0.16λ√f'c + 17ρw·Vu·d/Mu)·b·d ≤ 0.29λ√f'c·b·d.
6. Guía CRSI, cara de la columna (factor 0.083 de √psi a √MPa): estado límite 4 con un pilote a menos de d/2,
   vc = mín((d/w)(1 + d/c)·0.166, 2.656)·√f'c en bs = 2(cx + cy); estados límite 5 y 6 con un pilote a menos de d,
   vc = mín((d/w)(3.5 − 2.5r)(0.1577 + 0.0083/r), 0.83)·√f'c en todo el ancho, r = mín(Mu/(Vu·d), 1).
7. Punzonamiento del pilote P1 (cuadrado de igual área, lado √π·D/2), perímetro a d/2 completo: vu = R/(b0·d) y
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
SOIL = {"A": {"unit_weight_concrete_kNm3": 24.0, "unit_weight_fill_kNm3": 18.0, "pile_capacity_compression_kN": 850.0,
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
CAP_A = {"id": "A", "lx": 2000.0, "ly": 2000.0, "h": 900.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 600.0,
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
CAP_B = {"id": "B", "lx": 1200.0, "ly": 3600.0, "h": 800.0, "cover": 75.0, "bottom_cover": 150.0, "fill_height": 0.0,
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


def _uniform(cap: dict, load: dict) -> float:
    """q hacia abajo en N/mm²."""
    dead = GAMMA_C * cap["h"] + GAMMA_F * cap["fill_height"] + cap["surcharge_dead_kNm2"] * 1e-3
    return load["dead_factor"] * dead + load["live_factor"] * cap["surcharge_live_kNm2"] * 1e-3


def _weight(cap: dict, load: dict) -> float:
    area = cap["lx"] * cap["ly"]
    net = area - cap["column"]["cx"] * cap["column"]["cy"]
    dead = GAMMA_C * area * cap["h"] + (GAMMA_F * cap["fill_height"] + cap["surcharge_dead_kNm2"] * 1e-3) * net
    return load["dead_factor"] * dead + load["live_factor"] * cap["surcharge_live_kNm2"] * 1e-3 * net


def _cases(cap: dict) -> list[dict]:
    """Por caso: carga de referencia, R, ΔR y fuerzas de la cabeza (Vx, Vy, Mx, My) de cada pilote, en N y N·mm."""
    piles, tolerance, e = cap["piles"], cap["mislocation_mm"], cap["pile"]["embedment"]
    n = len(piles)
    sxx = sum(p["x"] ** 2 for p in piles)
    syy = sum(p["y"] ** 2 for p in piles)
    out = []
    if "loads" in cap:
        for load in cap["loads"]:
            p, vx, vy = load["P_kN"] * 1e3, load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
            mx, my = load["Mx_kNm"] * 1e6, load["My_kNm"] * 1e6
            total = p + _weight(cap, load)
            arm = cap["h"] + cap["pedestal_height"] - e
            my_h, mx_h = my + arm * vx, mx - arm * vy
            gx = [p_["x"] / sxx if sxx else 0.0 for p_ in piles]
            gy = [p_["y"] / syy if syy else 0.0 for p_ in piles]
            reactions = [total / n + my_h * gx[i] - mx_h * gy[i] for i in range(n)]
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


def _rows(cap: dict, direction: str) -> tuple[float, float]:
    """(ancho, As) de las barras inferiores de una dirección: centradas en el ancho menos recubrimiento y medio diámetro."""
    bar = cap["bottom"][direction]
    db, area = BARS[bar["designation"]]
    width = cap["ly"] if direction == "x" else cap["lx"]
    span = width - 2 * cap["cover"] - db
    count = math.floor(span / bar["spacing"] + 1e-6) + 1
    return width, count * area


def _beyond(cap: dict, case: dict, axis: int, plane: float, outward: float) -> tuple[float, float, float]:
    """(V interpolado, V completo, M) más allá del plano."""
    tolerance, size, lever = cap["mislocation_mm"], cap["pile"]["size"], cap["pile"]["embedment"] - cap["h"] / 2
    q = _uniform(cap, case["load"])
    shear = full = moment = 0.0
    for i, pile in enumerate(cap["piles"]):
        r = case["R"][i] + (case["dR"][i] if case["spread_on_cap"] else 0.0)
        dist = outward * ((pile["x"], pile["y"])[axis] - plane)
        if dist + tolerance > 0:
            moment += r * (dist + tolerance)
        if dist > 0:
            full += r
            vx, vy, mx, my = case["heads"][i]
            moment += -outward * (my + lever * vx) if axis == 0 else outward * (mx - lever * vy)
        shear += min(max(0.5 + (dist + tolerance) / size, 0.0), 1.0) * r
    half, width = (cap["lx"] / 2, cap["ly"]) if axis == 0 else (cap["ly"] / 2, cap["lx"])
    length = max(half - outward * plane, 0.0)
    w = q * width * length
    return shear - w, full - w, moment - w * length / 2


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
        name, seismic = case["load"]["case"], case["load"]["seismic"]
        fs = soil["seismic_capacity_factor"] if seismic else 1.0
        demand = max(r + (dr if spread else 0.0) for r, dr in zip(case["R"], case["dR"], strict=True))
        qa = soil["pile_capacity_compression_kN"] * 1e3
        expected.append({"name": "Presion admisible del pilote: compresion", "case": name, "demand": demand,
                         "capacity": mislocation * fs * qa})
        lateral = max(math.hypot(h[0], h[1]) for h in case["heads"])
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
    return {"x": (column["cx"] / 2, -column["cx"] / 2), "y": (column["cy"] / 2, -column["cy"] / 2)}


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
            v, _, m = _beyond(cap, case, axis, plane, outward)
            capacity = PHI_V * _vc_one_way(folder, (b, d, area / (b * d)), abs(v), abs(m), _spaced(cap))
            if worst is None or abs(v) / capacity > worst[0]:
                worst = (abs(v) / capacity, abs(v), capacity)
        if worst is not None:
            out.append({"name": f"Cortante en una direccion (barras {direction})", "case": name, "demand": worst[1], "capacity": worst[2]})
        for plane, outward in ((plus, 1.0), (minus, -1.0)):
            near = [value for value in (outward * ((p["x"], p["y"])[axis] - plane) for p in cap["piles"]) if value > 0]
            if not near or min(near) >= d:
                continue
            w = min(near) + cap["mislocation_mm"]
            _, v, m = _beyond(cap, case, axis, plane, outward)
            ratio = min(m / (v * d), 1.0)
            stress = min(d / w * (3.5 - 2.5 * ratio) * (1.9 * 0.083 + 0.1 * 0.083 / ratio), 10 * 0.083) * SQRT_FC
            out.append({"name": f"Cortante en la cara de la columna (barras {direction})", "case": name, "demand": v,
                        "capacity": PHI_V * stress * b * d})
    return out


def _two_way(folder: str, cap: dict, case: dict) -> list[dict]:
    """Estado límite 4 en la cara de la columna y punzonamiento P1 de cada pilote."""
    depths, column, pile, out = _depths(cap), cap["column"], cap["pile"], []
    davg = (depths["x"] + depths["y"]) / 2
    name = case["load"]["case"]
    outside = [(max(abs(p["x"]) - column["cx"] / 2, abs(p["y"]) - column["cy"] / 2), i) for i, p in enumerate(cap["piles"])]
    outside = [item for item in outside if item[0] > 0]
    if outside and min(outside)[0] < davg / 2:
        w = min(outside)[0] + cap["mislocation_mm"]
        c, bs = (column["cx"] + column["cy"]) / 2, 2 * (column["cx"] + column["cy"])
        v = sum(case["R"][i] + (case["dR"][i] if case["spread_on_cap"] else 0.0) for _, i in outside)
        v -= _uniform(cap, case["load"]) * (cap["lx"] * cap["ly"] - column["cx"] * column["cy"])
        stress = min(davg / w * (1 + davg / c) * 2 * 0.083, 32 * 0.083) * SQRT_FC
        out.append({"name": "Cortante en la cara de la columna (dos direcciones)", "case": name, "demand": v,
                    "capacity": PHI_V * stress * bs * davg})
    side = math.sqrt(math.pi) * pile["size"] / 2
    lam_s = 1.0 if folder == "nsr_10" or _spaced(cap) else min(math.sqrt(2 / (1 + davg / 250)), 1.0)
    for i, p in enumerate(cap["piles"]):
        if min(cap["lx"] / 2 - abs(p["x"]), cap["ly"] / 2 - abs(p["y"])) < (side + davg) / 2:
            continue  # el oráculo solo cubre el perímetro P1 completo
        r = case["R"][i] + (case["dR"][i] if case["spread_on_cap"] else 0.0)
        b0 = 4 * (side + davg)
        factor_vc = (min(0.33, 0.17 + 0.33, 0.17 + 0.083 * 40 * davg / b0) * lam_s if folder == "aci_318_25"
                     else min(0.17 * 3, 0.083 * (40 * davg / b0 + 2), 0.33))
        out.append({"name": "Punzonamiento del pilote", "case": name, "demand": r / (b0 * davg), "capacity": PHI_V * factor_vc * SQRT_FC})
    return out


def _derive(folder: str, cap: dict) -> dict:
    cases = _cases(cap)
    faces = _faces(cap)
    factored = [case for case in cases if case["load"]["kind"] == "factored"]
    moments = {}
    for case in factored:
        for direction, axis in (("x", 0), ("y", 1)):
            plus, minus = faces[direction]
            moments[(case["load"]["case"], direction)] = (_beyond(cap, case, axis, plus, 1.0)[2], _beyond(cap, case, axis, minus, -1.0)[2])
    checks = _service(folder, cap, cases)
    for case in factored:
        checks += [*_one_way(folder, cap, case), *_two_way(folder, cap, case)]
    return {"id": cap["id"], "cap": cap, "soil": SOIL[cap["id"]],
            "reactions": [{"case": c["load"]["case"], "R": c["R"], "dR": c["dR"]} for c in cases],
            "moments": [{"case": key[0], "direction": key[1], "plus": value[0], "minus": value[1]} for key, value in moments.items()],
            "minimum": _minimum(cap, moments), "checks": checks}


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        data = {"description": "Oraculo de cabezales (D-138), derivado por tests/oracles/derive_pile_cap.py",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated", "max_aggregate": 19.0},
                "tolerance_rel": 1e-6,
                "cases": [_derive(folder, cap) for cap in (CAP_A, CAP_B)]}
        (HERE / folder / "derived_pile_cap.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                                             newline="\n")
    print("ok")


if __name__ == "__main__":
    main()
