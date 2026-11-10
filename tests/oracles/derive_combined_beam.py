"""Deriva el oráculo de la viga en la dirección larga de zapatas combinadas (D-080, V3J.2) para los dos perfiles.

No importa el paquete. Unidades de trabajo: N y mm. Para cada caso mayorado:

1. Resultante en el centroide de la base por suma de r × F (cada columna en (x, y, h + hp); su pedestal y el área que
   ocupa, sin relleno ni sobrecarga, en su eje; la zapata, el relleno y las sobrecargas en el centroide) y la presión
   sin tracción por el equilibrio de derive_soil_pressure.py.
2. Cuerpo libre a la izquierda de cada sección x: la carga neta (presión recortada en cero menos la carga uniforme
   w = fd·(γc·h + γf·hf + qD) + fl·qL) sobre [−L/2, x] × [−B/2, B/2], integrada con el recorte exacto de
   derive_footing_shear.py; cada columna a la izquierda baja F = P + fd·(γc·A·hp − (γf·hf + qD)·A) − fl·qL·A en su eje
   y aplica el par My + (h + hp)·Vx. V = suma de fuerzas hacia arriba; M = suma de momentos respecto a la sección
   (positivo tracciona abajo).
3. Momentos en las cuatro caras y extremos de cada tramo sin columna, buscados por barrido fino de M y sección áurea
   (no por las raíces de V, como el paquete); cortante a d (de las barras inferiores x) de cada cara hacia su tramo, con
   Vc de 13.2.6.2(a) o de C.11.2 (el mayor de C.11.2.1 y C.11.2.2).
4. Resistencia con el bloque de Whitney y φ por perfil (derive_footing_flexure.py); sin barras superiores, concreto
   simple (D-072). As,min de vigas: max(0.25√f'c, 1.4)/fy·b·d, o 4/3 del As requerido por el mayor momento si es menor
   (ACI 9.6.1.3, NSR-10 C.10.5.3), con As = (0.85·f'c·b/fy)·(d − √(d² − 2·Mu/(0.9·0.85·f'c·b))). Separación máxima:
   min(3h, 450), 380·(280/fs) − 2.5·cc y 300·(280/fs) con fs = 2/3·fy (cc libre a la cara), en los dos perfiles.

Uso: python tests/oracles/derive_combined_beam.py
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
_S = _load_module("derive_footing_shear")
_C = _load_module("derive_combined_service")

FC, FY = _F.FC, _F.FY
GAMMA_C, GAMMA_F = _F.GAMMA_C, _F.GAMMA_F  # N/mm³
BARS = _F.BARS
PHI_SHEAR = _S.PHI
SCAN, GOLDEN_STEPS = 4000, 200
CLAUSES = {"aci_318_25": {"strength": "9.5.1.1(a) y Tabla 21.2.2", "min": "9.6.1.2 y 9.6.1.3",
                          "shear": "13.2.6.2(a) y 13.2.7.2", "strain": "9.3.3.1", "spacing": "13.3.2.1, 7.7.2.3 y 24.3.2"},
           "nsr_10": {"strength": "C.9.3.2.1 y C.9.3.2.2", "min": "C.10.5.1 y C.10.5.2 y C.10.5.3",
                      "shear": "C.15.5.1, C.15.5.2 y C.11.2", "strain": "C.10.3.5", "spacing": "C.10.5.4 y C.10.6.4"}}


def _beam(f: dict, case: str) -> dict | None:
    """Presión, carga uniforme y fuerzas de las columnas de un caso; None si la resultante sale de la base."""
    lx, ly, h, hp, hf = f["lx"], f["ly"], f["h"], f["pedestal_height"], f["fill_height"]
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in f["columns"]]
    fd, fl = loads[0]["dead_factor"], loads[0]["live_factor"]
    dead_area = GAMMA_F * hf + f["surcharge_dead_kNm2"] * 1e-3
    live_area = f["surcharge_live_kNm2"] * 1e-3
    w = fd * (GAMMA_C * h + dead_area) + fl * live_area
    n = w * lx * ly
    mx = my = 0.0
    columns = []
    for column, load in zip(f["columns"], loads, strict=True):
        area = column["cx"] * column["cy"]
        force = load["P_kN"] * 1e3 + fd * (GAMMA_C * area * hp - dead_area * area) - fl * live_area * area
        vx, vy = load["Vx_kN"] * 1e3, load["Vy_kN"] * 1e3
        r = (column["x"], column["y"], h + hp)
        # r × F con F = (Vx, Vy, −force), más los pares de la columna.
        mx += load["Mx_kNm"] * 1e6 + r[1] * (-force) - r[2] * vy
        my += load["My_kNm"] * 1e6 + r[2] * vx - r[0] * (-force)
        n += force
        columns.append({"id": column["id"], "x": column["x"], "half": column["cx"] / 2, "force": force,
                        "couple": load["My_kNm"] * 1e6 + (h + hp) * vx})
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return None
    plane, _ = _P.solve(lx, ly, n, my / n, -mx / n)
    return {"plane": plane, "w": w, "columns": sorted(columns, key=lambda c: c["x"]), "lx": lx, "ly": ly}


def _shear_moment(beam: dict, x: float) -> tuple[float, float]:
    hx, hy = beam["lx"] / 2, beam["ly"] / 2
    force = sx = 0.0
    if x > -hx:
        force, sx, _ = _S._net(beam["plane"], beam["w"], (-hx, -hy, x, hy))
    shear, moment = force, x * force - sx
    for column in beam["columns"]:
        if column["x"] < x:
            shear -= column["force"]
            moment -= column["force"] * (x - column["x"]) - column["couple"]
    return shear, moment


def _regions(beam: dict) -> list[tuple[float, float]]:
    a, b = beam["columns"]
    return [(-beam["lx"] / 2, a["x"] - a["half"]), (a["x"] + a["half"], b["x"] - b["half"]), (b["x"] + b["half"], beam["lx"] / 2)]


def _faces(beam: dict) -> list[tuple[float, float]]:
    return [(c["x"] + side * c["half"], side) for c in beam["columns"] for side in (-1.0, 1.0)]


def _extreme(beam: dict, low: float, high: float, sign: float) -> list[tuple[float, float]]:
    """Máximos interiores de sign·M en el tramo: barrido y sección áurea."""
    if high - low <= 0:
        return []
    xs = [low + (high - low) * i / SCAN for i in range(SCAN + 1)]
    values = [sign * _shear_moment(beam, x)[1] for x in xs]
    found = []
    for i in range(1, SCAN):
        if values[i] >= values[i - 1] and values[i] >= values[i + 1] and values[i] > min(values[i - 1], values[i + 1]):
            a, b = xs[i - 1], xs[i + 1]
            g = (math.sqrt(5) - 1) / 2
            for _ in range(GOLDEN_STEPS):
                c, d = b - g * (b - a), a + g * (b - a)
                if sign * _shear_moment(beam, c)[1] >= sign * _shear_moment(beam, d)[1]:
                    b = d
                else:
                    a = c
            x = (a + b) / 2
            found.append((x, _shear_moment(beam, x)[1]))
    return found


def _moments(beam: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """(M+, x) y (M−, x), con M− positivo; 0 si no hay momento de ese signo."""
    candidates = [(x, _shear_moment(beam, x)[1]) for x, _ in _faces(beam)]
    for low, high in _regions(beam):
        candidates += _extreme(beam, low, high, 1.0) + _extreme(beam, low, high, -1.0)
    top = max(candidates, key=lambda item: item[1])
    bottom = min(candidates, key=lambda item: item[1])
    return (max(top[1], 0.0), top[0]), (max(-bottom[1], 0.0), bottom[0])


def _rows(f: dict) -> tuple[dict, dict | None]:
    mat = f["bottom"]
    first = mat["first"]
    d1 = BARS[mat[first]["designation"]][0]
    db, ab = BARS[mat["x"]["designation"]]
    offset = f["cover"] + db / 2 if first == "x" else f["cover"] + d1 + db / 2
    n = _F._count(f["ly"], f["cover"], db, mat["x"]["spacing"])
    bottom = {"depth": f["h"] - offset, "area": n * ab, "spacing": mat["x"]["spacing"], "cc": offset - db / 2}
    top = None
    if f.get("top"):
        db, ab = BARS[f["top"]["designation"]]
        n = _F._count(f["ly"], f["cover"], db, f["top"]["spacing"])
        top = {"depth": f["h"] - f["cover"] - db / 2, "area": n * ab, "spacing": f["top"]["spacing"], "cc": f["cover"]}
    return bottom, top


def _required(moment: float, width: float, depth: float) -> float:
    k = 0.85 * FC * width
    return k / FY * (depth - math.sqrt(depth**2 - 2 * moment / (0.9 * k)))


def _flexure(folder: str, f: dict, row: dict, moment: float, bars: str) -> dict:
    profile = _F.PROFILES[folder]
    nominal, phi, strain = _F._strength(row["area"], f["ly"], row["depth"], profile)
    return {"name": f"Viga larga: flexion ({bars})", "status": "PASS" if phi * nominal >= moment else "FAIL",
            "demand_Nmm": moment, "capacity_Nmm": phi * nominal, "phi": phi, "et": strain, "clause": CLAUSES[folder]["strength"]}


def _shear(folder: str, f: dict, beam: dict, rows: tuple[dict, dict | None]) -> dict:
    bottom, top = rows
    depth = bottom["depth"]
    worst = None
    for face, side in _faces(beam):
        x = face + side * depth
        if not any(low < x < high and low <= face <= high for low, high in _regions(beam)):
            continue
        shear, moment = _shear_moment(beam, x)
        tension = bottom["area"] if moment >= 0 else (top["area"] if top else 0.0)
        capacity = PHI_SHEAR * _S._one_way_vc(folder, f["ly"], depth, tension / (f["ly"] * depth), abs(shear), abs(moment))
        if worst is None or abs(shear) / capacity > worst[0]:
            worst = (abs(shear) / capacity, abs(shear), capacity, x)
    name = "Viga larga: cortante en una direccion"
    if worst is None:
        return {"name": name, "status": "PASS"}
    return {"name": name, "status": "PASS" if worst[1] <= worst[2] else "FAIL", "demand_N": worst[1], "capacity_N": worst[2],
            "x_mm": worst[3], "clause": CLAUSES[folder]["shear"]}


def _section(folder: str, f: dict, row: dict, demand: float, bars: str) -> list[dict]:
    profile = _F.PROFILES[folder]
    _, _, strain = _F._strength(row["area"], f["ly"], row["depth"], profile)
    as_min = max(0.25 * math.sqrt(FC), 1.4) / FY * f["ly"] * row["depth"]
    required = min(as_min, 4 / 3 * _required(demand, f["ly"], row["depth"]))
    # Separación: min(3h, 450) (ACI 7.7.2.3, NSR-10 C.10.5.4) y fisuración con fs = 2/3·fy (Tabla 24.3.2, Ec. C.10-4).
    fs = 2 / 3 * FY
    spacing = min(3 * f["h"], 450.0, 380 * 280 / fs - 2.5 * row["cc"], 300 * 280 / fs)
    return [
        {"name": f"Viga larga: deformacion neta de traccion ({bars})", "status": "PASS" if strain >= profile["strain_min"] else "FAIL",
         "capacity": strain, "clause": CLAUSES[folder]["strain"]},
        {"name": f"Viga larga: acero minimo ({bars})", "status": "PASS" if row["area"] >= required else "FAIL",
         "demand_mm2": required, "capacity_mm2": row["area"], "as_min_mm2": as_min, "clause": CLAUSES[folder]["min"]},
        {"name": f"Viga larga: separacion maxima ({bars})", "status": "PASS" if row["spacing"] <= spacing else "FAIL",
         "demand_mm": row["spacing"], "capacity_mm": spacing, "clause": CLAUSES[folder]["spacing"]},
    ]


def _expected(folder: str, f: dict, level: str) -> dict:
    rows = _rows(f)
    bottom, top = rows
    profile = _F.PROFILES[folder]
    checks, failures = [], []
    positive_max = negative_max = 0.0
    for load in f["columns"][0]["loads"]:
        if load["kind"] != "factored":
            continue
        case = load["case"]
        beam = _beam(f, case)
        if beam is None:
            failures.append(case)
            continue
        (positive, x_pos), (negative, x_neg) = _moments(beam)
        positive_max, negative_max = max(positive_max, positive), max(negative_max, negative)
        checks.append({**_flexure(folder, f, bottom, positive, "barras inferiores x"), "case": case, "x_mm": x_pos})
        if negative > 1e-6:
            if top is None:
                plain = _F._plain(f, "x", negative, case, profile, level)
                checks.append({**plain, "x_mm": x_neg})
            else:
                checks.append({**_flexure(folder, f, top, negative, "barras superiores x"), "case": case, "x_mm": x_neg})
        checks.append({**_shear(folder, f, beam, rows), "case": case})
    if positive_max > 1e-6:
        checks += _section(folder, f, bottom, positive_max, "barras inferiores x")
    if top is not None and negative_max > 1e-6:
        checks += _section(folder, f, top, negative_max, "barras superiores x")
    return {"checks": checks, "equilibrium_failures": failures}


def _load(case: str, p: float, dead: float = 1.2, live: float = 1.6, mx: float = 0.0, my: float = 0.0, vx: float = 0.0,
          vy: float = 0.0, seismic: bool = False) -> dict:
    load = {"case": case, "kind": "factored", "dead_factor": dead, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": vy,
            "Mx_kNm": mx, "My_kNm": my}
    return {**load, "seismic": True} if seismic else load


def _column(name: str, x: float, loads: list[dict], cx: float = 450.0, cy: float = 450.0, y: float = 0.0) -> dict:
    return {"id": name, "cx": cx, "cy": cy, "x": x, "y": y, "loads": loads}


def _footing(columns: list[dict], **changes: object) -> dict:
    data = {"id": "ZC", "lx": 6000.0, "ly": 2000.0, "h": 700.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns,
            "bottom": {"first": "x", "end": "straight", "x": {"designation": "#7", "spacing": 150.0},
                       "y": {"designation": "#5", "spacing": 200.0}},
            "top": {"designation": "#7", "spacing": 150.0}}
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


CASES = [
    ("simetrica", "dos columnas iguales simétricas: presión uniforme, momento negativo entre columnas y voladizos",
     _footing([_column("C1", -2000.0, [_load("U1", 1300.0)]), _column("C2", 2000.0, [_load("U1", 1300.0)])])),
    ("borde-desigual", "columna de borde y cargas desiguales (como el manual del ACI): presión trapezoidal",
     _footing([_column("C1", -2700.0, [_load("U1", 900.0)], cx=450.0), _column("C2", 1000.0, [_load("U1", 1600.0)], cx=500.0, cy=500.0)],
              lx=6000.0, ly=2400.0, h=800.0, bottom={"first": "x", "end": "straight", "x": {"designation": "#8", "spacing": 150.0},
                                                       "y": {"designation": "#5", "spacing": 200.0}},
              top={"designation": "#8", "spacing": 150.0})),
    ("momentos-sismo", "dos casos: gravedad y sismo con My, Vx, pedestal y columnas desplazadas en Y",
     _footing([_column("C1", -2200.0, [_load("U1", 1100.0, mx=20.0), _load("U2", 800.0, dead=1.0, live=0.5, my=250.0,
         vx=90.0, seismic=True)],
                       y=200.0),
               _column("C2", 2100.0, [_load("U1", 1400.0, mx=-30.0), _load("U2", 1000.0, dead=1.0, live=0.5, my=300.0,
                   vx=110.0, seismic=True)],
                       y=-150.0)], pedestal_height=600.0)),
    ("sin-superior", "sin barras superiores: el momento negativo lo resiste el concreto simple (D-072)",
     _footing([_column("C1", -2000.0, [_load("U1", 500.0)]), _column("C2", 2000.0, [_load("U1", 500.0)])], top=None)),
    ("cortante-no-cumple", "zapata delgada y cargas grandes: no cumple el cortante sin estribos",
     _footing([_column("C1", -2000.0, [_load("U1", 2200.0)]), _column("C2", 2000.0, [_load("U1", 2200.0)])], h=450.0)),
    ("minimo-excepcion", "cargas pequeñas: As < As,min de vigas pero ≥ 4/3 del requerido (excepción)",
     _footing([_column("C1", -1500.0, [_load("U1", 250.0)]), _column("C2", 1500.0, [_load("U1", 250.0)])], lx=4500.0,
              bottom={"first": "x", "end": "straight", "x": {"designation": "#5", "spacing": 250.0},
                  "y": {"designation": "#5", "spacing": 250.0}},
              top={"designation": "#5", "spacing": 250.0})),
    ("minimo-no-cumple", "As menor que As,min y que 4/3 del requerido",
     _footing([_column("C1", -1200.0, [_load("U1", 1300.0)]), _column("C2", 1200.0, [_load("U1", 1300.0)])],
              bottom={"first": "y", "end": "straight", "x": {"designation": "#4", "spacing": 350.0},
                  "y": {"designation": "#5", "spacing": 200.0}},
              top={"designation": "#8", "spacing": 120.0})),
    ("contacto-parcial", "momento grande: contacto parcial, la carga uniforme supera la presión en un voladizo",
     _footing([_column("C1", -2000.0, [_load("U1", 900.0, my=900.0, live=0.0, dead=1.2)]),
               _column("C2", 2000.0, [_load("U1", 400.0, my=900.0, live=0.0, dead=1.2)])])),
]


def main() -> None:
    for folder in ("aci_318_25", "nsr_10"):
        level = _F.PROFILES[folder]["levels"]["bajo"]
        cases = [{"id": case_id, "description": text, "footing": footing, "expected": _expected(folder, footing, level)}
                 for case_id, text, footing in CASES]
        data = {"description": "Viga en la dirección larga de zapatas combinadas (D-080, V3J.2): diagramas V y M del cuerpo "
                               "libre con la presión de Bellos y Bakas, resistencia de Whitney, As,min de vigas con la "
                               "excepción de 4/3 y cortante sin estribos.",
                "soil": _C.SOIL, "materials": {"fc": FC, "fy": FY, "fyt": FY, "concrete": "normalweight", "coating": "uncoated"},
                "seismic_level": level, "tolerance_rel": 1e-7, "cases": cases}
        (HERE / folder / "derived_combined_beam.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
