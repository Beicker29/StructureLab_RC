"""Deriva el oráculo de la verificación geotécnica de zapatas (V3C) para los dos perfiles.

No importa el paquete. Para cada caso:

1. Cargas propias, en kN: zapata γc·lx·ly·h, pedestal γc·cx·cy·hp, relleno γf·hf y sobrecargas qD y qL por
   unidad de área sobre lx·ly − cx·cy. Los pesos y qD llevan el factor de carga muerta del caso; qL, el de viva.
2. Momento en el centroide de la base: suma de r × F de cada fuerza. La columna aplica F = (Vx, Vy, −P) en
   r = (ox, oy, H) con H = h + hp, más su par (Mx, My); el pedestal pesa en (ox, oy); la zapata, el relleno y las
   sobrecargas sobre toda la base actúan en el centroide, y la parte que ocupa la columna se resta en (ox, oy).
3. ex = My/N y ey = −Mx/N; la presión, con el equilibrio por Newton de derive_soil_pressure.py.

Uso: python tests/oracles/derive_footing_service.py
"""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent
_SPEC = importlib.util.spec_from_file_location("derive_soil_pressure", HERE / "derive_soil_pressure.py")
assert _SPEC is not None and _SPEC.loader is not None
_PRESSURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PRESSURE)
solve = _PRESSURE.solve

GAMMA_C, GAMMA_F = 24.0, 18.0  # kN/m³
QA, MIN_CONTACT = 250.0, 0.6  # kPa, -
CLAUSES = {"aci_318_25": "13.3.1.1", "nsr_10": "C.15.2.2"}
# Datos de estabilidad (D-070): obligatorios en el suelo; este oráculo no los usa (ver derive_footing_stability.py).
STABILITY = {"friction_coefficient": 0.45, "adhesion_kPa": 0.0, "passive_coefficient": 3.0, "cohesion_kPa": 0.0,
             "passive_factor": 0.5, "sliding_safety_factor": 1.5, "sliding_safety_factor_seismic": 1.1,
             "overturning_safety_factor": 2.0, "overturning_safety_factor_seismic": 1.5}


def _cross(r: tuple[float, float, float], f: tuple[float, float, float]) -> tuple[float, float, float]:
    return (r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0])


def _expected(footing: dict, load: dict) -> dict:
    lx, ly, h = footing["lx"] / 1e3, footing["ly"] / 1e3, footing["h"] / 1e3  # m
    col = footing["column"]
    cx, cy, ox, oy = col["cx"] / 1e3, col["cy"] / 1e3, col["offset_x"] / 1e3, col["offset_y"] / 1e3
    hp, hf = footing["pedestal_height"] / 1e3, footing["fill_height"] / 1e3
    fd, fl = load["dead_factor"], load["live_factor"]
    per_area = fd * (GAMMA_F * hf + footing["surcharge_dead_kNm2"]) + fl * footing["surcharge_live_kNm2"]  # kN/m²
    forces = [  # (punto, fuerza) en m y kN
        ((ox, oy, h + hp), (load["Vx_kN"], load["Vy_kN"], -load["P_kN"])),
        ((0.0, 0.0, 0.0), (0.0, 0.0, -fd * GAMMA_C * lx * ly * h)),
        ((0.0, 0.0, 0.0), (0.0, 0.0, -per_area * lx * ly)),
        ((ox, oy, 0.0), (0.0, 0.0, -fd * GAMMA_C * cx * cy * hp)),
        ((ox, oy, 0.0), (0.0, 0.0, per_area * cx * cy)),
    ]
    n = -sum(f[2] for _, f in forces)
    mx, my = load["Mx_kNm"], load["My_kNm"]
    for r, f in forces:
        m = _cross(r, f)
        mx, my = mx + m[0], my + m[1]
    result = {"N_kN": n, "Mx_base_kNm": mx, "My_base_kNm": my}
    if n <= 0 or abs(my / n) >= lx / 2 or abs(mx / n) >= ly / 2:
        return {**result, "equilibrium": False, "bearing": "FAIL", "contact": "FAIL"}
    ex, ey = my / n, -mx / n
    plane, fraction = solve(lx, ly, n, ex, ey)
    corners = [plane[0] + plane[1] * x + plane[2] * y for x in (-lx / 2, lx / 2) for y in (-ly / 2, ly / 2)]
    pmax = max(corners)
    return {**result, "equilibrium": True, "ex_mm": ex * 1e3, "ey_mm": ey * 1e3, "pmax_kPa": pmax,
            "contact_fraction": fraction, "bearing": "PASS" if pmax <= QA else "FAIL",
            "contact": "PASS" if fraction >= MIN_CONTACT else "FAIL"}


def _footing(**changes: object) -> dict:
    data = {"lx": 2400.0, "ly": 2000.0, "h": 500.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
            "column": {"cx": 400.0, "cy": 400.0, "offset_x": 0.0, "offset_y": 0.0}}
    data.update(changes)
    return data


def _load(p: float, vx: float = 0.0, vy: float = 0.0, mx: float = 0.0, my: float = 0.0, live: float = 1.0) -> dict:
    return {"dead_factor": 1.0, "live_factor": live, "P_kN": p, "Vx_kN": vx, "Vy_kN": vy, "Mx_kNm": mx, "My_kNm": my}


CASES = [
    ("centrada", "carga centrada, contacto total", _footing(), _load(900.0)),
    ("cortante-pedestal", "Vx a la altura h + hp, sin desplazamiento", _footing(pedestal_height=800.0), _load(800.0, vx=60.0)),
    ("desplazada", "columna desplazada con pedestal, sobrecargas y momentos en los dos ejes; supera la presión admisible",
     _footing(pedestal_height=600.0, surcharge_dead_kNm2=3.0, surcharge_live_kNm2=5.0,
              column={"cx": 500.0, "cy": 400.0, "offset_x": 300.0, "offset_y": -200.0}),
     _load(700.0, vx=-20.0, vy=30.0, mx=40.0, my=-25.0)),
    ("sobrecargas", "sobrecargas muerta y viva en una combinación con viva", _footing(surcharge_dead_kNm2=4.0,
                                                                                    surcharge_live_kNm2=10.0),
     _load(800.0, my=60.0)),
    ("sobrecargas-sin-viva", "las mismas sobrecargas en una combinación sin viva (factor 0)",
     _footing(surcharge_dead_kNm2=4.0, surcharge_live_kNm2=10.0), _load(800.0, my=60.0, live=0.0)),
    ("contacto-parcial", "momento grande en y: contacto parcial que cumple el mínimo", _footing(), _load(600.0, my=320.0)),
    ("contacto-insuficiente", "momento mayor: el contacto no alcanza el mínimo", _footing(), _load(500.0, my=480.0)),
    ("sobrepresion", "carga que supera la presión admisible", _footing(), _load(1300.0, mx=-60.0)),
    ("sin-equilibrio", "resultante fuera de la base", _footing(), _load(200.0, my=500.0)),
    ("traccion", "carga de tracción mayor que los pesos", _footing(), _load(-400.0)),
]


def main() -> None:
    cases = [{"id": case_id, "description": text, "footing": footing, "load": load, "expected": _expected(footing, load)}
             for case_id, text, footing, load in CASES]
    for folder, clause in CLAUSES.items():
        data = {"description": "Verificación geotécnica de zapatas con casos de servicio (D-052, D-057). Pesos y sobrecargas "
                               "con los factores del caso; "
                               "presión de Bellos y Bakas (2017) resuelta por equilibrio independiente.",
                "soil": {"allowable_pressure_kPa": QA, "min_contact_fraction": MIN_CONTACT,
                         "unit_weight_concrete_kNm3": GAMMA_C, "unit_weight_fill_kNm3": GAMMA_F, **STABILITY},
                "bearing_clause": clause, "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_footing_service.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
