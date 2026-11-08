"""Deriva el oráculo de desarrollo, aplastamiento y pasadores de zapatas (V3D.3) para los dos perfiles.

No importa el paquete; reutiliza las funciones de los otros oráculos para la presión y los momentos en las caras.

1. Desarrollo de cada dirección: disponible = menor distancia de una cara de la columna al borde, menos el recubrimiento.
   Recta, ACI 25.4.2.4: ld = fy·ψt·ψs·ψg/(1.1λ√f'c·(cb/db)) db; NSR-10 (C.12-1): igual sin ψg; ambas ≥ 300 mm, cb/db ≤ 2.5,
   cb = min(recubrimiento + db/2, s/2), ψt = 1.3 con más de 300 mm de concreto debajo, ψs = 0.8 en barras ≤ No. 19 (No. 6).
   Gancho, ACI 25.4.3.1 corregida (D-066): ldh = fy·ψe·ψs·ψcc/(4.2λ√f'c)·db; NSR-10 C.12.5.2 y C.12.5.3:
   ldh = 0.24·ψe·fy/(λ√f'c)·db·ψcc·exceso; ambas ≥ 8db y ≥ 150 mm.
   La malla superior se verifica solo si algún caso tiene momento negativo en esa dirección.
   Factores (D-071): ψe (epóxico) 1.5 si el recubrimiento libre < 3db o la separación libre < 6db, 1.2 si no, con
   ψt·ψe ≤ 1.7; en ganchos ψe = 1.2. ψcc = 0.7 si db ≤ 36 mm y el recubrimiento (lateral y del extremo) ≥ 65 mm y ≥ 50 mm.
   Exceso = As requerido/As suministrado, con As requerido = max(As de flexión con φ = 0.9, 0.0018·b·h); se aplica en
   barras rectas con nivel bajo (ACI ordinary, NSR-10 DMI) y, solo en NSR-10, también en ganchos; luego los mínimos.
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
                   "compression": "25.4.9.1 a 25.4.9.3", "bearing": "22.8.3.2 y Tabla 21.2.1", "excess": "25.4.10"},
    "nsr_10": {"tension": "C.12.2.1, C.12.2.3 y C.12.2.4", "hook": "C.12.5.1 y C.12.5.2",
               "compression": "C.12.3.1 y C.12.3.2", "bearing": "C.10.14.1 y C.9.3.2.4", "excess": "C.12.2.5 y C.12.5.3(d)"},
}
LEVELS = {"aci_318_25": {"bajo": "ordinary", "alto": "special"}, "nsr_10": {"bajo": "DMI", "alto": "DES"}}


def _ld(folder: str, db: float, cb: float, below: float, psi_e: float, excess: float) -> float:
    psi_t = 1.3 if below > 300 else 1.0
    small = 22.0 if folder == "aci_318_25" else 21.0
    psi_s = 0.8 if db < small else 1.0
    return max(FY * min(psi_t * psi_e, 1.7) * psi_s / (1.1 * math.sqrt(FC) * min(cb / db, 2.5)) * db * excess, 300.0)


def _ldh(folder: str, db: float, psi_e: float, psi_cc: float, excess: float) -> float:
    if folder == "aci_318_25":
        length = FY * psi_e * psi_cc / (4.2 * math.sqrt(FC)) * db
    else:
        length = 0.24 * psi_e * FY / math.sqrt(FC) * db * psi_cc * excess
    return max(length, 8 * db, 150.0)


def _required_area(f: dict, mat: str, direction: str, row: dict, moments: list[dict]) -> float:
    sign = 1.0 if mat == "bottom" else -1.0
    keys = ("+X", "-X") if direction == "x" else ("+Y", "-Y")
    mu = max([sign * m[k] for m in moments for k in keys], default=0.0)
    k = 0.85 * FC * row["width"]
    needed = (k / FY) * (row["depth"] - math.sqrt(row["depth"] ** 2 - 2 * mu / (0.9 * k))) if mu > 0 else 0.0
    return max(needed, 0.0018 * row["width"] * f["h"])


def _ldc(folder: str, db: float) -> float:
    first = FY / (4.2 * math.sqrt(FC)) * db if folder == "aci_318_25" else 0.24 * FY / math.sqrt(FC) * db
    return max(first, 0.043 * FY * db, 200.0)


def _faces(f: dict) -> dict[str, tuple[float, float]]:
    c = f["column"]
    return {"x": (c["offset_x"] + c["cx"] / 2, c["offset_x"] - c["cx"] / 2),
            "y": (c["offset_y"] + c["cy"] / 2, c["offset_y"] - c["cy"] / 2)}


def _development(folder: str, f: dict, coating: str, level: str) -> list[dict]:
    out = []
    epoxy = coating in ("epoxy", "zinc_epoxy")
    low = level == LEVELS[folder]["bajo"]
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
            hook = f[mat]["end"] == "hook"
            ratio = min(_required_area(f, mat, direction, row, moments) / row["area"], 1.0)
            permitted = low and (not hook or folder == "nsr_10")
            excess = ratio if permitted else 1.0
            spacing = f[mat][direction]["spacing"]
            if hook:
                psi_e = 1.2 if epoxy else 1.0
                psi_cc = 0.7 if db <= 36 and f["cover"] >= 65 and f["cover"] >= 50 else 1.0
                required, clause = _ldh(folder, db, psi_e, psi_cc, excess), CLAUSES[folder]["hook"]
            else:
                clear_cover = min(f["h"] - row["depth"] - db / 2, f["cover"])
                psi_e = (1.5 if clear_cover < 3 * db or spacing - db < 6 * db else 1.2) if epoxy else 1.0
                psi_cc = None
                cb = min(f["cover"] + db / 2, spacing / 2)
                below = f["h"] - row["depth"] if mat == "bottom" else row["depth"]
                required, clause = _ld(folder, db, cb, below, psi_e, excess), CLAUSES[folder]["tension"]
            if excess < 1.0:
                clause += "; " + CLAUSES[folder]["excess"]
            item = {"name": f"Desarrollo malla {label} (barras {direction})", "status": "PASS" if required <= available else "FAIL",
                    "demand": required, "capacity": available, "clause": clause, "psi_e": psi_e, "excess_ratio": ratio,
                    "excess_applied": excess}
            if psi_cc is not None:
                item["psi_cc"] = psi_cc
            out.append(item)
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


def _expected(folder: str, f: dict, coating: str, level: str) -> list[dict]:
    dowels, area = _dowels(folder, f)
    return [*_development(folder, f, coating, level), *dowels, *_bearing(folder, f, area)]


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
# Casos de D-071: (id, descripción, zapata, recubrimiento de las barras, nivel sísmico "bajo" o "alto").
FACTOR_CASES = [
    ("epoxico-cerca", "barras #6 epóxicas a 120 mm: recubrimiento ≥ 3db pero separación libre < 6db, ψe = 1.5",
     _footing(lx=3000.0, ly=3000.0, h=600.0, bottom=_mat("x", ("#6", 120.0), ("#6", 120.0)),
              loads=[_load("1.2D+1.6L", 1.2, 1.6, 2600.0)]), "epoxy", "alto"),
    ("epoxico-holgado", "barras #4 epóxicas a 200 mm con recubrimiento 75 mm: ψe = 1.2",
     _footing(bottom=_mat("x", ("#4", 200.0), ("#4", 200.0))), "zinc_epoxy", "alto"),
    ("epoxico-superior-tope", "malla superior epóxica #8 a 250 mm (recubrimiento < 3db, separación ≥ 6db) y más de 300 mm "
                              "de concreto debajo: ψt·ψe = 1.95 se limita a 1.7",
     _footing(lx=2400.0, ly=2400.0, h=750.0, bottom=_mat("x", ("#6", 200.0), ("#6", 200.0)),
              top=_mat("y", ("#8", 250.0), ("#8", 250.0)), loads=[_load("0.9D+E", 0.9, 0.0, 200.0, mx=320.0)]), "epoxy", "alto"),
    ("exceso-rectas-nivel-bajo", "barras rectas con más acero del requerido (gobierna As,min) y nivel bajo: se aplica As,req/As,sum",
     _footing(lx=1800.0, ly=1800.0, h=600.0, bottom=_mat("x", ("#8", 250.0), ("#8", 250.0)),
              loads=[_load("1.2D", 1.2, 0.0, 1000.0)]), "uncoated", "bajo"),
    ("exceso-rectas-nivel-alto", "las mismas barras con nivel alto: no se aplica",
     _footing(lx=1800.0, ly=1800.0, h=600.0, bottom=_mat("x", ("#8", 250.0), ("#8", 250.0)),
              loads=[_load("1.2D", 1.2, 0.0, 1000.0)]), "uncoated", "alto"),
    ("exceso-minimo", "la reducción por exceso deja la longitud bajo 300 mm: gobierna el mínimo",
     _footing(lx=1800.0, ly=1800.0, h=600.0, bottom=_mat("x", ("#5", 140.0), ("#5", 140.0)),
              loads=[_load("1.2D", 1.2, 0.0, 1000.0)]), "uncoated", "bajo"),
    ("exceso-ganchos-nivel-bajo", "ganchos #8 con acero en exceso y nivel bajo: NSR-10 aplica el factor (C.12.5.3(d)), ACI no",
     _footing(lx=1600.0, ly=1600.0, h=650.0, bottom=_mat("x", ("#8", 150.0), ("#8", 150.0), end="hook"),
              loads=[_load("1.2D", 1.2, 0.0, 500.0)]), "epoxy", "bajo"),
    ("ganchos-recubrimiento-corto", "ganchos con recubrimiento de 60 mm: no alcanza 65 mm, ψcc = 1.0",
     _footing(cover=60.0, bottom=_mat("x", ("#6", 150.0), ("#6", 150.0), end="hook")), "uncoated", "alto"),
]


def main() -> None:
    for folder in CLAUSES:
        cases = [{"id": case_id, "description": text, "footing": footing, "coating": "uncoated",
                  "seismic_level": LEVELS[folder]["alto"], "expected": _expected(folder, footing, "uncoated", LEVELS[folder]["alto"])}
                 for case_id, text, footing in CASES]
        cases += [{"id": case_id, "description": text, "footing": footing, "coating": coating,
                   "seismic_level": LEVELS[folder][level], "expected": _expected(folder, footing, coating, LEVELS[folder][level])}
                  for case_id, text, footing, coating, level in FACTOR_CASES]
        data = {"description": "Desarrollo de las mallas, aplastamiento y pasadores de zapatas (D-059, D-065).",
                "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "soil": {"allowable_pressure_kPa": 250.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": 24.0,
                         "unit_weight_fill_kNm3": 18.0,
                         "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                         "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                         "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                         "overturning_safety_factor_seismic": 1.5},
                "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_footing_connection.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                       encoding="utf-8")


if __name__ == "__main__":
    main()
