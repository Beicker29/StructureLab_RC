"""Deriva el oráculo de la revisión geotécnica de zapatas combinadas (D-080, V3J.1) para los dos perfiles.

No importa el paquete. Unidades de trabajo: kN, m y kPa. Para cada caso:

1. Fuerzas: cada columna aplica F = (Vx, Vy, −P) en r = (x, y, h + hp) más su par (Mx, My); su pedestal pesa en (x, y);
   la zapata, el relleno y las sobrecargas sobre toda la base actúan en el centroide, y la parte que ocupa cada columna
   se resta en su eje. Los pesos y la sobrecarga muerta llevan el factor de carga muerta del caso; la viva, el de viva.
2. N y el momento en el centroide de la base por suma de r × F; ex = My/N, ey = −Mx/N; la presión, con el equilibrio de
   derive_soil_pressure.py; presión admisible qa (× 1.33 con sismo, D-079) y contacto mínimo.
3. Deslizamiento (D-070): μ·N + ca·Ac + fp·Pp con la fuerza horizontal total de las dos columnas, en la dirección de la
   resultante y en cada eje; volcamiento: N·L/2 frente a |M| en cada eje.

Uso: python tests/oracles/derive_combined_service.py
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
solve = _PRESSURE.solve

GAMMA_C, GAMMA_F = 24.0, 18.0  # kN/m³
QA, MIN_CONTACT, SEISMIC_QA = 300.0, 0.5, 1.33
MU, CA, KP, C, FP = 0.5, 10.0, 3.0, 0.0, 0.5
FS = {"sliding": (1.5, 1.1), "overturning": (2.0, 1.5)}  # sin sismo, con sismo
SOIL = {"allowable_pressure_kPa": QA, "min_contact_fraction": MIN_CONTACT, "unit_weight_concrete_kNm3": GAMMA_C,
        "unit_weight_fill_kNm3": GAMMA_F, "friction_coefficient": MU, "adhesion_kPa": CA, "passive_coefficient": KP,
        "cohesion_kPa": C, "passive_factor": FP, "sliding_safety_factor": FS["sliding"][0],
        "sliding_safety_factor_seismic": FS["sliding"][1], "overturning_safety_factor": FS["overturning"][0],
        "overturning_safety_factor_seismic": FS["overturning"][1], "seismic_bearing_factor": SEISMIC_QA}
CLAUSES = {"aci_318_25": "13.3.1.1", "nsr_10": "C.15.2.2"}


def _cross(r: tuple[float, float, float], f: tuple[float, float, float]) -> tuple[float, float, float]:
    return (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])


def _expected(footing: dict, case: str) -> dict:
    lx, ly, h = footing["lx"] / 1e3, footing["ly"] / 1e3, footing["h"] / 1e3
    hp, hf = footing["pedestal_height"] / 1e3, footing["fill_height"] / 1e3
    loads = [next(load for load in column["loads"] if load["case"] == case) for column in footing["columns"]]
    fd, fl, seismic = loads[0]["dead_factor"], loads[0]["live_factor"], loads[0].get("seismic", False)
    per_area = fd * (GAMMA_F * hf + footing["surcharge_dead_kNm2"]) + fl * footing["surcharge_live_kNm2"]
    forces = [((0.0, 0.0, 0.0), (0.0, 0.0, -fd * GAMMA_C * lx * ly * h - per_area * lx * ly))]
    moments = [0.0, 0.0]
    for column, load in zip(footing["columns"], loads, strict=True):
        x, y, area = column["x"] / 1e3, column["y"] / 1e3, column["cx"] * column["cy"] / 1e6
        forces.append(((x, y, h + hp), (load["Vx_kN"], load["Vy_kN"], -load["P_kN"])))
        forces.append(((x, y, 0.0), (0.0, 0.0, -fd * GAMMA_C * area * hp + per_area * area)))
        moments[0] += load["Mx_kNm"]
        moments[1] += load["My_kNm"]
    n = -sum(force[2] for _, force in forces)
    mx, my = moments
    for r, f in forces:
        m = _cross(r, f)
        mx, my = mx + m[0], my + m[1]
    vx, vy = abs(sum(load["Vx_kN"] for load in loads)), abs(sum(load["Vy_kN"] for load in loads))
    result = {"N_kN": n, "Mx_base_kNm": mx, "My_base_kNm": my}
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return {**result, "equilibrium": False}
    ex, ey = my / n, -mx / n
    plane, fraction = solve(lx, ly, n, ex, ey)
    corners = [max(plane[0] + plane[1] * px + plane[2] * py, 0.0)
               for px, py in ((-lx / 2, -ly / 2), (lx / 2, -ly / 2), (lx / 2, ly / 2), (-lx / 2, ly / 2))]
    capacity = QA * (SEISMIC_QA if seismic else 1.0)
    # Deslizamiento: pasiva de Rankine sobre el espesor, con la sobrecarga del relleno, por unidad de ancho (kN/m).
    per_width = (KP * GAMMA_F * (hf + h) + KP * GAMMA_F * hf) / 2 * h + 2 * C * math.sqrt(KP) * h
    pp_x, pp_y = per_width * ly, per_width * lx
    base = MU * n + CA * fraction * lx * ly
    options = [(vx, base + FP * pp_x), (vy, base + FP * pp_y)]
    if math.hypot(vx, vy) > 0:
        v = math.hypot(vx, vy)
        options.insert(0, (v, base + FP * (pp_x * vx + pp_y * vy) / v))
    force, resistance = max(options, key=lambda item: 0.0 if item[0] == 0 else item[0] / item[1])
    fs_s = FS["sliding"][1 if seismic else 0]
    axes = [(abs(my), n * lx / 2), (abs(mx), n * ly / 2)]
    moment, resisting = max(axes, key=lambda item: 0.0 if item[0] == 0 else item[0] / item[1])
    fs_o = FS["overturning"][1 if seismic else 0]
    return {**result, "equilibrium": True, "ex_mm": ex * 1e3, "ey_mm": ey * 1e3, "pmax_kPa": max(corners),
            "corners_kPa": corners, "capacity_kPa": capacity, "bearing": "PASS" if max(corners) <= capacity else "FAIL",
            "contact_fraction": fraction, "contact": "PASS" if fraction >= MIN_CONTACT else "FAIL",
            "sliding_demand_kN": fs_s * force, "sliding_capacity_kN": resistance,
            "sliding": "PASS" if fs_s * force <= resistance else "FAIL",
            "overturning_demand_kNm": fs_o * moment, "overturning_capacity_kNm": resisting,
            "overturning": "PASS" if fs_o * moment <= resisting else "FAIL"}


def _load(case: str, p: float, vx: float = 0.0, vy: float = 0.0, mx: float = 0.0, my: float = 0.0, live: float = 1.0,
          seismic: bool = False) -> dict:
    load = {"case": case, "kind": "service", "dead_factor": 1.0, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": vy,
            "Mx_kNm": mx, "My_kNm": my}
    return {**load, "seismic": True} if seismic else load


def _column(name: str, x: float, loads: list[dict], cx: float = 450.0, cy: float = 450.0, y: float = 0.0) -> dict:
    return {"id": name, "cx": cx, "cy": cy, "x": x, "y": y, "loads": loads}


def _footing(columns: list[dict], **changes: object) -> dict:
    mat = {"first": "x", "end": "straight", "x": {"designation": "#6", "spacing": 200.0}, "y": {"designation": "#5", "spacing": 200.0}}
    data = {"id": "ZC", "lx": 6000.0, "ly": 2000.0, "h": 700.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0, "columns": columns, "bottom": mat}
    data.update(changes)
    return data


CASES = [
    ("simetrica", "dos columnas iguales simétricas: resultante en el centroide y presión uniforme",
     _footing([_column("C1", -2000.0, [_load("D+L", 900.0)]), _column("C2", 2000.0, [_load("D+L", 900.0)])])),
    ("desigual", "cargas desiguales: la resultante se corre hacia la columna más cargada",
     _footing([_column("C1", -2000.0, [_load("D+L", 600.0)]), _column("C2", 2000.0, [_load("D+L", 1400.0)])])),
    ("borde-pedestal", "columna de borde, pedestal, columnas desplazadas en Y y momentos en los dos ejes",
     _footing([_column("C1", -2775.0, [_load("D+L", 800.0, mx=30.0, my=-60.0)], cx=450.0, cy=400.0, y=150.0),
               _column("C2", 1500.0, [_load("D+L", 1200.0, mx=-20.0, my=80.0)], y=-100.0)], pedestal_height=600.0)),
    ("sismo", "combinación con sismo: cortantes, momentos y qa × 1.33",
     _footing([_column("C1", -2000.0, [_load("D+0.7E", 950.0, vx=60.0, vy=20.0, my=150.0, live=0.0, seismic=True)]),
               _column("C2", 2000.0, [_load("D+0.7E", 1250.0, vx=80.0, vy=25.0, my=180.0, live=0.0, seismic=True)])])),
    ("deslizamiento", "cortante grande con poca carga vertical: no cumple el deslizamiento",
     _footing([_column("C1", -2000.0, [_load("D", 200.0, vx=250.0, live=0.0)]),
               _column("C2", 2000.0, [_load("D", 200.0, vx=250.0, live=0.0)])])),
    ("sin-equilibrio", "momento enorme: resultante fuera de la base",
     _footing([_column("C1", -2000.0, [_load("D", 100.0, my=4000.0, live=0.0)]),
               _column("C2", 2000.0, [_load("D", 100.0, my=4000.0, live=0.0)])])),
]


def main() -> None:
    for folder, clause in CLAUSES.items():
        cases = [{"id": case_id, "description": text, "footing": footing,
                  "expected": {load["case"]: _expected(footing, load["case"]) for load in footing["columns"][0]["loads"]}}
                 for case_id, text, footing in CASES]
        data = {"description": "Revisión geotécnica de zapatas combinadas (D-080): resultante de las dos columnas por suma de "
                               "r × F, presión de Bellos y Bakas por equilibrio independiente, deslizamiento y volcamiento.",
                "soil": SOIL, "bearing_clause": clause, "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_combined_service.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                     encoding="utf-8")


if __name__ == "__main__":
    main()
