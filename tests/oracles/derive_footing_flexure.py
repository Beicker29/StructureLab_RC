"""Deriva el oráculo de la flexión de zapatas (V3D.1) para los dos perfiles.

No importa el paquete. Para cada caso mayorado:

1. Resultante en el centroide de la base (suma de r × F, como derive_footing_service.py) y presión sin tracción por
   equilibrio de Newton (derive_soil_pressure.py).
2. Momento en cada cara de la columna: integral exacta de (x − xf)·p sobre el voladizo recortado donde p > 0, menos
   la carga uniforme w = fd·(γc·h + γf·hf + qD) + fl·qL sobre el voladizo completo, con brazo L/2.
3. Resistencia con el bloque de Whitney: a = As·fy/(0.85·f'c·b), c = a/β1, εt = 0.003·(d − c)/c y
   Mn = As·fy·(d − a/2); φ por perfil (ACI: 0.90 si εt ≥ εty + 0.003; NSR-10: 0.90 si εt ≥ 0.005).
4. Número de barras: n = ⌊(ancho − 2·recubrimiento − db)/s⌋ + 1; en la franja, las que caen en ella.
5. As requerido de la franja: As = (0.85·f'c·b/fy)·(d − √(d² − 2·Mu/(φ·0.85·f'c·b))) con φ = 0.90.

Uso: python tests/oracles/derive_footing_flexure.py
"""

import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
_SPEC = importlib.util.spec_from_file_location("derive_soil_pressure", HERE / "derive_soil_pressure.py")
assert _SPEC is not None and _SPEC.loader is not None
_PRESSURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PRESSURE)

FC, FY, ES, BETA1 = 28.0, 420.0, 200000.0, 0.85
GAMMA_C, GAMMA_F = 24e-6, 18e-6  # N/mm³
BARS = {"#4": (12.7, 129.0), "#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0)}  # diámetro, área
PROFILES = {
    "aci_318_25": {"min_ratio": 0.0018, "spacing": lambda h: min(2 * h, 450.0), "tension": FY / ES + 0.003,
                   "strain_min": FY / ES + 0.003, "depth": lambda h, c, d1, d2: h - c - d1 - d2 / 2,
                   "clauses": {"strength": "13.2.6.6 y 13.2.7.1", "band": "13.3.3.3"}},
    "nsr_10": {"min_ratio": 0.0018, "spacing": lambda h: min(3 * h, 450.0), "tension": 0.005, "strain_min": 0.004,
               "depth": lambda h, c, d1, d2: h - c - d1 - d2,
               "clauses": {"strength": "C.15.4.1 y C.15.4.2", "band": "C.15.4.4.2"}},
}


def _phi(strain: float, profile: dict) -> float:
    ety = FY / ES
    if strain <= ety:
        return 0.65
    if strain >= profile["tension"]:
        return 0.90
    return 0.65 + 0.25 * (strain - ety) / (profile["tension"] - ety)


def _strength(area: float, width: float, depth: float, profile: dict) -> tuple[float, float, float]:
    a = area * FY / (0.85 * FC * width)
    c = a / BETA1
    strain = 0.003 * (depth - c) / c
    nominal = area * FY * (depth - a / 2)
    return nominal, _phi(strain, profile), strain


def _resultant(f: dict, load: dict) -> tuple[float, float, float]:
    """N (N), Mx y My (N·mm) en el centroide de la base."""
    lx, ly, h = f["lx"], f["ly"], f["h"]
    c = f["column"]
    fd, fl = load["dead_factor"], load["live_factor"]
    per_area = fd * (GAMMA_F * f["fill_height"] + f["surcharge_dead_kNm2"] * 1e-3) + fl * f["surcharge_live_kNm2"] * 1e-3
    forces = [((c["offset_x"], c["offset_y"], h + f["pedestal_height"]),
               (load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3, -load["P_kN"] * 1e3)),
              ((0.0, 0.0, 0.0), (0.0, 0.0, -fd * GAMMA_C * lx * ly * h - per_area * lx * ly)),
              ((c["offset_x"], c["offset_y"], 0.0),
               (0.0, 0.0, -fd * GAMMA_C * c["cx"] * c["cy"] * f["pedestal_height"] + per_area * c["cx"] * c["cy"]))]
    n = -sum(force[2] for _, force in forces)
    mx, my = load["Mx_kNm"] * 1e6, load["My_kNm"] * 1e6
    for (rx, ry, rz), (fx, fy, fz) in forces:
        mx += ry * fz - rz * fy
        my += rz * fx - rx * fz
    return n, mx, my


def _face_moments(f: dict, load: dict) -> dict[str, float] | None:
    n, mx, my = _resultant(f, load)
    lx, ly = f["lx"], f["ly"]
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return None
    plane, _ = _PRESSURE.solve(lx, ly, n, my / n, -mx / n)
    w = load["dead_factor"] * (GAMMA_C * f["h"] + GAMMA_F * f["fill_height"] + f["surcharge_dead_kNm2"] * 1e-3) \
        + load["live_factor"] * f["surcharge_live_kNm2"] * 1e-3
    c = f["column"]
    faces = {"+X": (0, c["offset_x"] + c["cx"] / 2, 1.0), "-X": (0, c["offset_x"] - c["cx"] / 2, -1.0),
             "+Y": (1, c["offset_y"] + c["cy"] / 2, 1.0), "-Y": (1, c["offset_y"] - c["cy"] / 2, -1.0)}
    result = {}
    for name, (axis, face, outward) in faces.items():
        half = (lx if axis == 0 else ly) / 2
        width = ly if axis == 0 else lx
        a, b = (face, half) if outward > 0 else (-half, face)
        rect = ([(a, -ly / 2), (b, -ly / 2), (b, ly / 2), (a, ly / 2)] if axis == 0
                else [(-lx / 2, a), (lx / 2, a), (lx / 2, b), (-lx / 2, b)])
        poly = _PRESSURE._clip(rect, plane)
        moment = 0.0
        if len(poly) >= 3:
            m = _PRESSURE._moments(poly)
            q0, gx, gy = plane
            force = q0 * m[0] + gx * m[1] + gy * m[2]
            static = (q0 * m[1] + gx * m[3] + gy * m[4]) if axis == 0 else (q0 * m[2] + gx * m[4] + gy * m[5])
            moment = outward * (static - face * force)
        length = b - a
        result[name] = moment - w * length * width * length / 2
    return result


def _count(width: float, cover: float, db: float, spacing: float) -> int:
    return math.floor((width - 2 * cover - db) / spacing + 1e-6) + 1


def _rows(f: dict, mat: dict) -> dict[str, dict]:
    first = mat["first"]
    second = "y" if first == "x" else "x"
    d1 = BARS[mat[first]["designation"]][0]
    rows = {}
    for index, direction in enumerate((first, second)):
        db, ab = BARS[mat[direction]["designation"]]
        width = f["ly"] if direction == "x" else f["lx"]
        n = _count(width, f["cover"], db, mat[direction]["spacing"])
        offset = f["cover"] + db / 2 if index == 0 else f["cover"] + d1 + db / 2
        rows[direction] = {"width": width, "depth": f["h"] - offset, "area": n * ab, "count": n, "db": db, "ab": ab}
    return rows


def _band_count(f: dict, direction: str, row: dict, spacing: float) -> int:
    """Barras uniformes (centradas en el ancho útil) que caen en la franja de ancho del lado corto."""
    half = row["width"] / 2 - f["cover"] - row["db"] / 2
    n = row["count"]
    start = -half + (2 * half - (n - 1) * spacing) / 2
    centre = f["column"]["offset_x"] if direction == "y" else f["column"]["offset_y"]
    short = min(f["lx"], f["ly"])
    return sum(1 for i in range(n) if centre - short / 2 - 1e-6 <= start + i * spacing <= centre + short / 2 + 1e-6)


def _expected(f: dict, profile: dict) -> dict:
    checks: list[dict] = []
    rows = {"bottom": _rows(f, f["bottom"])}
    if f["top"] is not None:
        rows["top"] = _rows(f, f["top"])
    moments = []
    for load in f["loads"]:
        faces = _face_moments(f, load)
        if faces is None:
            checks.append({"name": "Zapata: equilibrio con cargas mayoradas", "case": load["case"], "status": "FAIL"})
            continue
        moments.append(faces)
        for direction, (plus, minus) in (("x", ("+X", "-X")), ("y", ("+Y", "-Y"))):
            for mat, sign, label in (("bottom", 1.0, "inferior"), ("top", -1.0, "superior")):
                demand = max(sign * faces[plus], sign * faces[minus])
                if mat == "top" and demand <= 1e-6:
                    continue
                name = f"Flexion malla {label} (barras {direction})"
                if mat not in rows:
                    checks.append({"name": name, "case": load["case"], "status": "BLOCKED", "demand_Nmm": demand})
                    continue
                row = rows[mat][direction]
                nominal, phi, _ = _strength(row["area"], row["width"], row["depth"], profile)
                checks.append({"name": name, "case": load["case"], "status": "PASS" if phi * nominal >= demand else "FAIL",
                               "demand_Nmm": max(demand, 0.0), "capacity_Nmm": phi * nominal})
    for mat, label in (("bottom", "inferior"), ("top", "superior")):
        if mat not in rows:
            continue
        for direction, row in rows[mat].items():
            negative = any(min(m["+X" if direction == "x" else "+Y"], m["-X" if direction == "x" else "-Y"]) < -1e-6
                           for m in moments)
            _, _, strain = _strength(row["area"], row["width"], row["depth"], profile)
            checks.append({"name": f"Deformacion neta de traccion malla {label} (barras {direction})",
                           "status": "PASS" if strain >= profile["strain_min"] else "FAIL", "capacity": strain})
            if mat == "bottom" or negative:
                required = profile["min_ratio"] * row["width"] * f["h"]
                checks.append({"name": f"Acero minimo malla {label} (barras {direction})",
                               "status": "PASS" if row["area"] >= required else "FAIL", "demand": required,
                               "capacity": row["area"]})
            spacing = f[mat][direction]["spacing"]
            checks.append({"name": f"Separacion maxima malla {label} (barras {direction})",
                           "status": "PASS" if spacing <= profile["spacing"](f["h"]) else "FAIL", "demand": spacing,
                           "capacity": profile["spacing"](f["h"])})
            short = "y" if f["lx"] > f["ly"] else ("x" if f["lx"] < f["ly"] else None)
            if direction == short and (mat == "bottom" or negative):
                sign = 1.0 if mat == "bottom" else -1.0
                keys = ("+X", "-X") if direction == "x" else ("+Y", "-Y")
                mu = max([sign * m[k] for m in moments for k in keys], default=0.0)
                k = 0.85 * FC * row["width"]
                needed = (k / FY) * (row["depth"] - math.sqrt(row["depth"] ** 2 - 2 * mu / (0.9 * k))) if mu > 0 else 0.0
                total = max(needed, profile["min_ratio"] * row["width"] * f["h"])
                beta = max(f["lx"], f["ly"]) / min(f["lx"], f["ly"])
                required = 2 / (beta + 1) * total
                band = _band_count(f, direction, row, spacing) * row["ab"]
                checks.append({"name": f"Franja central malla {label} (barras {direction})",
                               "status": "PASS" if band >= required else "FAIL", "demand": required, "capacity": band})
    bottom = rows["bottom"]
    first, second = bottom[f["bottom"]["first"]], bottom["y" if f["bottom"]["first"] == "x" else "x"]
    measured = profile["depth"](f["h"], f["cover"], first["db"], second["db"])
    checks.append({"name": "Altura minima de la zapata", "status": "PASS" if measured >= 150 else "FAIL",
                   "demand": 150.0, "capacity": measured})
    return {"checks": checks}


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
    ("cuadrada-centrada", "zapata cuadrada con carga centrada: flexión, εt, As,min, separación y altura", _footing()),
    ("rectangular-desplazada", "rectangular con la columna desplazada y momento: franja γs y malla superior",
     _footing(lx=3200.0, ly=2200.0, h=600.0, column={"cx": 400.0, "cy": 500.0, "offset_x": 350.0, "offset_y": 0.0},
              bottom=_mat("y", ("#6", 200.0), ("#5", 180.0)), top=_mat("x", ("#4", 250.0), ("#4", 250.0)),
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 1400.0, my=60.0), _load("0.9D+E", 0.9, 0.0, 450.0, my=420.0, vx=90.0)])),
    ("sin-malla-superior", "momento negativo sin malla superior: BLOCKED (concreto simple)",
     _footing(loads=[_load("0.9D+E", 0.9, 0.0, 300.0, my=330.0)])),
    ("sin-equilibrio", "resultante mayorada fuera de la base", _footing(loads=[_load("0.9D+E", 0.9, 0.0, 100.0, my=900.0)])),
    ("separacion-excesiva", "separación mayor que la permitida y acero bajo el mínimo",
     _footing(h=200.0, bottom=_mat("x", ("#4", 420.0), ("#4", 420.0)), loads=[_load("1.2D", 1.2, 0.0, 200.0)])),
]


def main() -> None:
    for folder, profile in PROFILES.items():
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(footing, profile)}
                 for case_id, text, footing in CASES]
        data = {"description": "Flexión de zapatas con casos mayorados (D-059, D-061): momentos por integración exacta, "
                               "resistencia con el bloque de Whitney.",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight"},
                "soil": {"allowable_pressure_kPa": 250.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                         "unit_weight_fill_kNm3": 18.0},
                "clauses": profile["clauses"], "tolerance_rel": 1e-6, "cases": cases}
        (HERE / folder / "derived_footing_flexure.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
