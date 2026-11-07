"""Deriva el oráculo de desarrollo, aplastamiento y pasadores de zapatas (V3D.3) para los dos perfiles.

No importa el paquete; reutiliza las funciones de los otros oráculos para la presión y los momentos en las caras.

1. Desarrollo de cada dirección: disponible = menor distancia de una cara de la columna al borde, menos el recubrimiento.
   Recta, ACI 25.4.2.4: ld = fy·ψt·ψs·ψg/(1.1λ√f'c·(cb/db)) db; NSR-10 (C.12-1): igual sin ψg; ambas ≥ 300 mm, cb/db ≤ 2.5,
   cb = min(recubrimiento + db/2, s/2), ψt = 1.3 con más de 300 mm de concreto debajo, ψs = 0.8 en barras ≤ No. 19 (No. 6).
   Gancho, ACI 25.4.3.1 corregida (D-066): ldh = fy·ψs/(4.2λ√f'c)·db; NSR-10 C.12.5.2: ldh = 0.24·fy/(λ√f'c)·db; ambas ≥ 8db y ≥ 150 mm.
   La malla superior se verifica solo si algún caso tiene momento negativo en esa dirección.
2. Pasadores: área ≥ 0.005·cx·cy; ldc (ACI 25.4.9.2: max(fy/(4.2λ√f'c), 0.043fy)·db; NSR-10 C.12.3.2:
   max(0.24fy/(λ√f'c), 0.043fy)·db; ≥ 200 mm) frente a h − recubrimiento − db1 − db2 de la malla inferior.
3. Aplastamiento: φ·0.85f'c·A1·min(√(A2/A1), 2), φ = 0.65, A2 = (cx + 2k)(cy + 2k), k = min(2h, distancias de la columna
   a los bordes). Si Pu > φBn, los pasadores deben cumplir As ≥ (Pu − φBn)/(φ·fy).

Uso: python tests/oracles/derive_footing_connection.py
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


_F = _load_module("derive_footing_flexure")
FC, FY = 28.0, 420.0
BARS = {"#4": (12.7, 129.0), "#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0), "#8": (25.4, 510.0)}
CLAUSES = {
    "aci_318_25": {"tension": "25.4.2.1, 25.4.2.4 y 25.4.2.5", "hook": "25.4.3.1 y 25.4.3.2",
                   "compression": "25.4.9.1 a 25.4.9.3", "bearing": "22.8.3.2 y Tabla 21.2.1"},
    "nsr_10": {"tension": "C.12.2.1, C.12.2.3 y C.12.2.4", "hook": "C.12.5.1 y C.12.5.2",
               "compression": "C.12.3.1 y C.12.3.2", "bearing": "C.10.14.1 y C.9.3.2.4"},
}


def _ld(folder: str, db: float, cb: float, below: float) -> float:
    psi_t = 1.3 if below > 300 else 1.0
    small = 22.0 if folder == "aci_318_25" else 21.0
    psi_s = 0.8 if db < small else 1.0
    return max(FY * psi_t * psi_s / (1.1 * math.sqrt(FC) * min(cb / db, 2.5)) * db, 300.0)


def _ldh(folder: str, db: float) -> float:
    length = FY / (4.2 * math.sqrt(FC)) * db if folder == "aci_318_25" else 0.24 * FY / math.sqrt(FC) * db
    return max(length, 8 * db, 150.0)


def _ldc(folder: str, db: float) -> float:
    first = FY / (4.2 * math.sqrt(FC)) * db if folder == "aci_318_25" else 0.24 * FY / math.sqrt(FC) * db
    return max(first, 0.043 * FY * db, 200.0)


def _faces(f: dict) -> dict[str, tuple[float, float]]:
    c = f["column"]
    return {"x": (c["offset_x"] + c["cx"] / 2, c["offset_x"] - c["cx"] / 2),
            "y": (c["offset_y"] + c["cy"] / 2, c["offset_y"] - c["cy"] / 2)}


def _development(folder: str, f: dict) -> list[dict]:
    out = []
    hx, hy = f["lx"] / 2, f["ly"] / 2
    faces = _faces(f)
    moments = [m for m in (_F._face_moments(f, load) for load in f["loads"]) if m is not None]
    negative = {"x": any(min(m["+X"], m["-X"]) < -1e-6 for m in moments), "y": any(min(m["+Y"], m["-Y"]) < -1e-6 for m in moments)}
    for mat, label in (("bottom", "inferior"), ("top", "superior")):
        if f[mat] is None:
            continue
        rows = _F._rows(f, f[mat])
        for direction, row in rows.items():
            if mat == "top" and not negative[direction]:
                continue
            half = hx if direction == "x" else hy
            plus, minus = faces[direction]
            available = min(half - plus, minus + half) - f["cover"]
            db = row["db"]
            if f[mat]["end"] == "hook":
                required, clause = _ldh(folder, db), CLAUSES[folder]["hook"]
            else:
                cb = min(f["cover"] + db / 2, f[mat][direction]["spacing"] / 2)
                below = f["h"] - row["depth"] if mat == "bottom" else row["depth"]
                required, clause = _ld(folder, db, cb, below), CLAUSES[folder]["tension"]
            out.append({"name": f"Desarrollo malla {label} (barras {direction})", "status": "PASS" if required <= available else "FAIL",
                        "demand": required, "capacity": available, "clause": clause})
    return out


def _dowels(folder: str, f: dict) -> tuple[list[dict], float | None]:
    out: list[dict] = []
    c = f["column"]
    dowels = c.get("dowels")
    dowel_area = None
    if dowels is None:
        out.append({"name": "Pasadores: area minima", "status": "INCOMPLETE"})
    else:
        db, ab = BARS[dowels["designation"]]
        dowel_area = dowels["count"] * ab
        required = 0.005 * c["cx"] * c["cy"]
        out.append({"name": "Pasadores: area minima", "status": "PASS" if dowel_area >= required else "FAIL",
                    "demand": required, "capacity": dowel_area})
        bottom = _F._rows(f, f["bottom"])
        first, second = bottom[f["bottom"]["first"]], bottom["y" if f["bottom"]["first"] == "x" else "x"]
        available = f["h"] - f["cover"] - first["db"] - second["db"]
        ldc = _ldc(folder, db)
        out.append({"name": "Pasadores: anclaje a compresion", "status": "PASS" if ldc <= available else "FAIL",
                    "demand": ldc, "capacity": available, "clause": CLAUSES[folder]["compression"]})
    return out, dowel_area


def _bearing(folder: str, f: dict, dowel_area: float | None) -> list[dict]:
    out = []
    c = f["column"]
    hx, hy = f["lx"] / 2, f["ly"] / 2
    faces = _faces(f)
    gaps = (hx - faces["x"][0], faces["x"][1] + hx, hy - faces["y"][0], faces["y"][1] + hy)
    k = min(2 * f["h"], *gaps)
    a1, a2 = c["cx"] * c["cy"], (c["cx"] + 2 * k) * (c["cy"] + 2 * k)
    capacity = 0.65 * 0.85 * FC * a1 * min(math.sqrt(a2 / a1), 2.0)
    for load in f["loads"]:
        pu = load["P_kN"] * 1e3
        if pu <= 0:
            continue
        out.append({"name": "Aplastamiento en la zapata", "case": load["case"], "status": "PASS" if pu <= capacity else "FAIL",
                    "demand": pu, "capacity": capacity, "clause": CLAUSES[folder]["bearing"]})
        if pu > capacity:
            if dowel_area is None:
                out.append({"name": "Pasadores: compresion sobre el aplastamiento", "case": load["case"], "status": "INCOMPLETE"})
            else:
                required = (pu - capacity) / (0.65 * FY)
                out.append({"name": "Pasadores: compresion sobre el aplastamiento", "case": load["case"],
                            "status": "PASS" if dowel_area >= required else "FAIL", "demand": required, "capacity": dowel_area})
    return out


def _expected(folder: str, f: dict) -> list[dict]:
    dowels, area = _dowels(folder, f)
    return [*_development(folder, f), *dowels, *_bearing(folder, f, area)]


def _mat(first: str, x: tuple[str, float], y: tuple[str, float], end: str = "straight") -> dict:
    return {"first": first, "end": end, "x": {"designation": x[0], "spacing": x[1]}, "y": {"designation": y[0], "spacing": y[1]}}


def _load(case: str, dead: float, live: float, p: float, mx: float = 0.0, my: float = 0.0) -> dict:
    return {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": 0.0,
            "Vy_kN": 0.0, "Mx_kNm": mx, "My_kNm": my}


def _footing(**changes: object) -> dict:
    data = {"id": "Z", "lx": 2400.0, "ly": 2400.0, "h": 550.0, "cover": 75.0, "fill_height": 1000.0,
            "pedestal_height": 0.0, "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0,
            "column": {"cx": 450.0, "cy": 450.0, "offset_x": 0.0, "offset_y": 0.0, "dowels": {"designation": "#6", "count": 8}},
            "bottom": _mat("x", ("#5", 150.0), ("#5", 150.0)), "top": None, "loads": [_load("1.2D+1.6L", 1.2, 1.6, 1500.0)]}
    data.update(changes)
    return data


CASES = [
    ("barras-rectas", "zapata cuadrada con barras rectas, pasadores y aplastamiento holgados", _footing()),
    ("ganchos-y-malla-superior", "voladizo corto con barras #8 en gancho y malla superior con momento negativo (ψt = 1.3)",
     _footing(lx=1600.0, ly=2400.0, h=700.0, column={"cx": 400.0, "cy": 400.0, "offset_x": 0.0, "offset_y": 0.0,
                                                      "dowels": {"designation": "#6", "count": 4}},
              bottom=_mat("x", ("#8", 200.0), ("#6", 200.0), end="hook"), top=_mat("y", ("#5", 200.0), ("#5", 200.0)),
              loads=[_load("0.9D+E", 0.9, 0.0, 250.0, mx=180.0)])),
    ("rectas-insuficientes", "barras #8 rectas a 110 mm en un voladizo corto: cb = s/2 gobierna y el desarrollo no cabe",
     _footing(lx=1500.0, ly=1500.0, h=600.0, bottom=_mat("x", ("#8", 110.0), ("#8", 110.0)), loads=[_load("1.2D", 1.2, 0.0, 600.0)])),
    ("aplastamiento-excedido", "columna pequeña cerca del borde (A2 limitada por el borde, √(A2/A1) < 2) y carga alta: excede φBn",
     _footing(lx=2000.0, ly=2000.0, h=600.0, column={"cx": 250.0, "cy": 250.0, "offset_x": 760.0, "offset_y": 0.0,
                                                     "dowels": {"designation": "#7", "count": 6}},
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 2600.0), _load("1.4D", 1.4, 0.0, 2200.0)])),
    ("sin-pasadores", "sin pasadores declarados: INCOMPLETE, también para el exceso de aplastamiento",
     _footing(column={"cx": 250.0, "cy": 250.0, "offset_x": 0.0, "offset_y": 0.0}, loads=[_load("1.2D+1.6L", 1.2, 1.6, 2600.0)])),
    ("pasadores-largos", "zapata delgada con pasadores #8: el anclaje a compresión no cabe",
     _footing(h=400.0, column={"cx": 450.0, "cy": 450.0, "offset_x": 0.0, "offset_y": 0.0, "dowels": {"designation": "#8", "count": 4}},
              loads=[_load("1.2D", 1.2, 0.0, 700.0)])),
]


def main() -> None:
    for folder in CLAUSES:
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing)}
                 for case_id, text, footing in CASES]
        data = {"description": "Desarrollo de las mallas, aplastamiento y pasadores de zapatas (D-059, D-065).",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight"},
                "soil": {"allowable_pressure_kPa": 250.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                         "unit_weight_fill_kNm3": 18.0},
                "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_footing_connection.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                       encoding="utf-8")


if __name__ == "__main__":
    main()
