"""Deriva el oráculo de la ubicación y el largo de la zapata combinada que propone el diseño (D-107), para los dos perfiles.

No importa el paquete. Unidades de trabajo: kN, m y kPa en las fuerzas; mm en la geometría. Para cada caso:

1. El caso que ubica la base: placement_case si se declara (D-108); si no, el de servicio sin sismo de mayor carga
   total (D+L, D-107).
2. Fuerza vertical de cada columna en su eje: v = P + fd·(γc·A·hp − (γf·hf + qd)·A) − fl·ql·A (su pedestal, menos el
   relleno y la sobrecarga muerta que desplaza, y la sobrecarga viva que desplaza), con A = cx·cy y los factores del caso.
3. Resultante: con H = h + hp, la suma de momentos en el plano de la base se anula en
   xr = Σ(v·x + My + H·Vx)/Σv,  yr = Σ(v·y − Mx + H·Vy)/Σv
   (la zapata, el relleno y las sobrecargas sobre toda la base actúan en su centroide y no dan momento).
4. Largo, a lo largo de la dirección principal: L = ⌈2·max(sr − s0, s1 − sr)/paso⌉·paso, con s0 y s1 las caras exteriores
   de las columnas y sr la coordenada de la resultante; la base va de sr − L/2 a sr + L/2. Con un voladizo máximo en el
   inicio (columna de lindero), la base empieza en s0 − voladizo y conserva el largo.
5. Ancho mínimo que cubre las columnas: ⌈2·max(|t − tr| + c/2)/paso⌉·paso en la dirección transversal.

Uso: python tests/oracles/derive_combined_design.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
GAMMA_C, GAMMA_F = 24.0, 18.0  # kN/m³
STEP = 100.0  # mm
LEVELS = {"aci_318_25": "special", "nsr_10": "DES"}


def _load(case: str, kind: str, factors: tuple[float, float], forces: tuple[float, float, float, float, float],
          seismic: bool = False) -> dict:
    p, vx, vy, mx, my = forces
    return {"case": case, "kind": kind, "dead_factor": factors[0], "live_factor": factors[1], "seismic": seismic,
            "P_kN": p, "Vx_kN": vx, "Vy_kN": vy, "Mx_kNm": mx, "My_kNm": my}


def _columns() -> list[dict]:
    first = [_load("D+L", "service", (1.0, 1.0), (900.0, 6.0, 4.0, -10.0, 15.0)),
             _load("D", "service", (1.0, 0.0), (650.0, 4.0, 3.0, -8.0, 10.0)),
             _load("D+0.7E", "service", (1.0, 0.0), (1400.0, 40.0, 0.0, 0.0, 90.0), seismic=True),
             _load("1.2D+1.6L", "factored", (1.2, 1.6), (1250.0, 8.0, 6.0, -14.0, 21.0))]
    second = [_load("D+L", "service", (1.0, 1.0), (1300.0, -5.0, 8.0, 20.0, -12.0)),
              _load("D", "service", (1.0, 0.0), (950.0, -3.0, 6.0, 15.0, -9.0)),
              _load("D+0.7E", "service", (1.0, 0.0), (300.0, 40.0, 0.0, 0.0, 95.0), seismic=True),
              _load("1.2D+1.6L", "factored", (1.2, 1.6), (1800.0, -7.0, 11.0, 28.0, -17.0))]
    return [{"id": "C1", "cx": 500.0, "cy": 500.0, "x": 0.0, "y": 0.0, "loads": first},
            {"id": "C2", "cx": 550.0, "cy": 600.0, "x": 5000.0, "y": 150.0, "loads": second}]


def _governing(columns: list[dict], declared: str | None) -> list[dict]:
    cases = [load["case"] for load in columns[0]["loads"] if load["kind"] == "service" and not load["seismic"]]
    def total(case: str) -> float:
        return sum(next(item["P_kN"] for item in c["loads"] if item["case"] == case) for c in columns)

    chosen = declared if declared is not None else max(cases, key=total)
    return [next(load for load in column["loads"] if load["case"] == chosen) for column in columns]


def resultant(columns: list[dict], design: dict, h: float) -> tuple[float, float]:
    """(xr, yr) en mm, ejes globales."""
    height = (h + design["pedestal_height"]) / 1000  # m
    fill, hp = design["fill_height"] / 1000, design["pedestal_height"] / 1000
    total = sx = sy = 0.0
    for column, load in zip(columns, _governing(columns, design.get("placement_case")), strict=True):
        area = column["cx"] * column["cy"] / 1e6  # m²
        displaced = (GAMMA_F * fill + design["surcharge_dead_kNm2"]) * area
        v = (load["P_kN"] + load["dead_factor"] * (GAMMA_C * area * hp - displaced)
             - load["live_factor"] * design["surcharge_live_kNm2"] * area)
        total += v
        sx += v * column["x"] / 1000 + load["My_kNm"] + height * load["Vx_kN"]
        sy += v * column["y"] / 1000 - load["Mx_kNm"] + height * load["Vy_kN"]
    return sx / total * 1000, sy / total * 1000


def geometry(columns: list[dict], design: dict, principal: str, h: float) -> dict:
    xr, yr = resultant(columns, design, h)
    along, across = ("x", "y") if principal == "x" else ("y", "x")
    size = {"x": "cx", "y": "cy"}
    center = {"x": xr, "y": yr}
    s0 = min(c[along] - c[size[along]] / 2 for c in columns)
    s1 = max(c[along] + c[size[along]] / 2 for c in columns)
    sr = center[along]
    length = math.ceil(round(2 * max(sr - s0, s1 - sr) / STEP, 9)) * STEP
    low = sr - length / 2
    limit = design.get("max_cantilever_start")
    if limit is not None and s0 - low > limit:
        low = s0 - limit
    middle = low + length / 2
    tr = center[across]
    width = math.ceil(round(2 * max(abs(c[across] - tr) + c[size[across]] / 2 for c in columns) / STEP, 9)) * STEP
    base = {along: middle, across: tr}
    return {"length_mm": length, "cover_width_mm": width, "center_mm": [base["x"], base["y"]]}


def _design(**changes: object) -> dict:
    design = {"fc_options": [28.0], "prices": {"concrete_per_m3": {"28": 575000.0}, "steel_per_kg": 6200.0},
              "plan_step": STEP, "plan_max": 9000.0, "h_min": 600.0, "h_step": 100.0, "h_max": 1200.0, "cover": 75.0,
              "fill_height": 1200.0, "pedestal_height": 300.0, "surcharge_dead_kNm2": 2.0, "surcharge_live_kNm2": 5.0,
              "bars": ["#5", "#6"], "spacing_step": 10.0, "end": "straight", "dowel_bars": ["#6"]}
    design.update(changes)
    return design


def _rotated(columns: list[dict]) -> list[dict]:
    """Las mismas columnas con la viga en la Y global: x → y, y → −x (y sus secciones y fuerzas, como vectores)."""
    turned = []
    for column in columns:
        loads = [{**load, "Vx_kN": -load["Vy_kN"], "Vy_kN": load["Vx_kN"], "Mx_kNm": -load["My_kNm"], "My_kNm": load["Mx_kNm"]}
                 for load in column["loads"]]
        turned.append({**column, "x": -column["y"], "y": column["x"], "cx": column["cy"], "cy": column["cx"], "loads": loads})
    return turned


CASES = [
    ("centrada", "base centrada en la resultante de D+L, viga en X", "x", _columns(), _design(), 800.0),
    ("lindero", "voladizo máximo 0 en el inicio: la columna C1 queda al ras del borde", "x", _columns(),
     _design(max_cantilever_start=0.0), 800.0),
    ("caso-declarado", "placement_case = D (D-108): la base se ubica con la resultante de D, no con la de mayor carga",
     "x", _columns(), _design(placement_case="D"), 800.0),
    ("viga-en-y", "las mismas columnas giradas, con la viga en la Y global (D-094)", "y", _rotated(_columns()), _design(), 800.0),
]


def derive(folder: str) -> dict:
    cases = []
    for case_id, description, principal, columns, design, h in CASES:
        cases.append({"id": case_id, "description": description, "h_mm": h,
                      "project": {"description": description, "profile": folder.replace("_", "-"),
                                  "seismic": {"level": LEVELS[folder], "justification": "Oráculo del diseño (D-107)."},
                                  "materials": {"fy": 420.0, "fyt": 420.0, "concrete": "normalweight", "coating": "uncoated"},
                                  "soil": {"allowable_pressure_kPa": 250.0, "min_contact_fraction": 0.5,
                                           "unit_weight_concrete_kNm3": GAMMA_C, "unit_weight_fill_kNm3": GAMMA_F,
                                           "friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0,
                                           "cohesion_kPa": 0.0, "passive_factor": 0.5, "sliding_safety_factor": 1.5,
                                           "sliding_safety_factor_seismic": 1.1, "overturning_safety_factor": 2.0,
                                           "overturning_safety_factor_seismic": 1.5, "seismic_bearing_factor": 1.33},
                                  "principal_direction": principal, "combined_design": design, "columns": columns},
                      "expected": geometry(columns, design, principal, h)})
    return {"source": "derive_combined_design.py (D-107)", "tolerance_mm": 1e-6, "cases": cases}


if __name__ == "__main__":
    for folder in LEVELS:
        target = HERE / folder / "derived_combined_design.json"
        target.write_text(json.dumps(derive(folder), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("escrito", target)
