"""Deriva el oráculo de deslizamiento y volcamiento de zapatas (D-070) para los dos perfiles.

No importa el paquete. Unidades de trabajo: kN, m y kPa. La resultante en la base y la fracción en contacto salen de
derive_footing_service.py (que a su vez resuelve la presión por equilibrio, independiente del paquete). Para cada caso:

1. Pasiva por unidad de ancho: diagrama lineal de presiones σ(z) = Kp·γf·z + 2c·√Kp entre z1 = hf y z2 = hf + h,
   integrado como trapecio: (σ(z1) + σ(z2))/2·h. Pp,x actúa sobre la cara de ancho ly y Pp,y sobre la de ancho lx.
2. Deslizamiento: base = μ·N + ca·(fracción·lx·ly). Direcciones: resultante V = √(Vx² + Vy²) con
   R = base + fp·(Pp,x·|Vx| + Pp,y·|Vy|)/V; eje X con |Vx| y R = base + fp·Pp,x; eje Y igual. Gobierna la mayor razón
   FS·V/R; cumple si FS·V ≤ R.
3. Volcamiento: eje X con Mo = |My,base| y Mr = N·lx/2; eje Y con |Mx,base| y N·ly/2. Gobierna la mayor razón.
4. FS: el sísmico si el caso está marcado seismic. Sin equilibrio o en tracción, ambas revisiones fallan.

Uso: python tests/oracles/derive_footing_stability.py
"""

import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
_SPEC = importlib.util.spec_from_file_location("derive_footing_service", HERE / "derive_footing_service.py")
assert _SPEC is not None and _SPEC.loader is not None
_SERVICE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SERVICE)

MU, CA, KP, C, FP = 0.5, 20.0, 3.0, 10.0, 0.5  # -, kPa, -, kPa, -
FS_SLIDING, FS_SLIDING_SEISMIC, FS_OVERTURNING, FS_OVERTURNING_SEISMIC = 1.5, 1.1, 2.0, 1.5
SOIL = {"allowable_pressure_kPa": 400.0, "min_contact_fraction": 0.5, "unit_weight_concrete_kNm3": _SERVICE.GAMMA_C,
        "unit_weight_fill_kNm3": _SERVICE.GAMMA_F, "friction_coefficient": MU, "adhesion_kPa": CA,
        "passive_coefficient": KP, "cohesion_kPa": C, "passive_factor": FP, "sliding_safety_factor": FS_SLIDING,
        "sliding_safety_factor_seismic": FS_SLIDING_SEISMIC, "overturning_safety_factor": FS_OVERTURNING,
        "overturning_safety_factor_seismic": FS_OVERTURNING_SEISMIC}
STABILITY_CLAUSES = {"aci_318_25": "13.2.6.1", "nsr_10": "Titulo H (remision), factores declarados (D-070)"}


def _governing(options: list[tuple[str, float, float]]) -> tuple[list[str], float, float]:
    def ratio(item: tuple[str, float, float]) -> float:
        return 0.0 if item[1] == 0 else item[1] / item[2]

    worst = max(ratio(item) for item in options)
    names = [item[0] for item in options if ratio(item) == worst]
    chosen = next(item for item in options if ratio(item) == worst)
    return names, chosen[1], chosen[2]


def _expected(footing: dict, load: dict) -> dict:
    base_result = _SERVICE._expected(footing, load)
    if not base_result["equilibrium"]:
        return {"equilibrium": False, "sliding": "FAIL", "overturning": "FAIL"}
    lx, ly, h, hf = (footing[key] / 1e3 for key in ("lx", "ly", "h", "fill_height"))
    n = base_result["N_kN"]
    seismic = load.get("seismic", False)
    fs_sliding = FS_SLIDING_SEISMIC if seismic else FS_SLIDING
    fs_overturning = FS_OVERTURNING_SEISMIC if seismic else FS_OVERTURNING

    def sigma(z: float) -> float:
        return KP * _SERVICE.GAMMA_F * z + 2 * C * math.sqrt(KP)

    per_width = (sigma(hf) + sigma(hf + h)) / 2 * h  # kN/m
    pp_x, pp_y = per_width * ly, per_width * lx
    base = MU * n + CA * base_result["contact_fraction"] * lx * ly
    vx, vy = abs(load["Vx_kN"]), abs(load["Vy_kN"])
    v = math.hypot(vx, vy)
    options = [("eje X", vx, base + FP * pp_x), ("eje Y", vy, base + FP * pp_y)]
    if v > 0:
        options.insert(0, ("la resultante", v, base + FP * (pp_x * vx + pp_y * vy) / v))
    sliding_names, force, resistance = _governing(options)
    axes = [("eje X", abs(base_result["My_base_kNm"]), n * lx / 2), ("eje Y", abs(base_result["Mx_base_kNm"]), n * ly / 2)]
    overturning_names, moment, resisting = _governing(axes)
    return {"equilibrium": True, "N_kN": n, "Pp_x_kN": pp_x, "Pp_y_kN": pp_y,
            "sliding_governing": sliding_names, "V_kN": force, "R_kN": resistance, "sliding_demand_kN": fs_sliding * force,
            "sliding": "PASS" if fs_sliding * force <= resistance else "FAIL",
            "overturning_governing": overturning_names, "Mo_kNm": moment, "Mr_kNm": resisting,
            "overturning_demand_kNm": fs_overturning * moment,
            "overturning": "PASS" if fs_overturning * moment <= resisting else "FAIL"}


def _footing(**changes: object) -> dict:
    data = {"lx": 2400.0, "ly": 2000.0, "h": 500.0, "cover": 75.0, "fill_height": 1000.0, "pedestal_height": 0.0,
            "surcharge_dead_kNm2": 0.0, "surcharge_live_kNm2": 0.0,
            "column": {"cx": 400.0, "cy": 400.0, "offset_x": 0.0, "offset_y": 0.0}}
    data.update(changes)
    return data


def _load(p: float, vx: float = 0.0, vy: float = 0.0, mx: float = 0.0, my: float = 0.0, seismic: bool = False,
          dead: float = 1.0, live: float = 1.0) -> dict:
    return {"dead_factor": dead, "live_factor": live, "seismic": seismic, "P_kN": p, "Vx_kN": vx, "Vy_kN": vy,
            "Mx_kNm": mx, "My_kNm": my}


CASES = [
    ("sin-cortante", "sin fuerza horizontal: el deslizamiento no tiene demanda", _footing(), _load(800.0)),
    ("cortante-x", "Vx solo: la resultante coincide con el eje X", _footing(), _load(600.0, vx=180.0)),
    ("cortante-y-pedestal", "Vy solo con pedestal: el cortante por h + hp genera momento en X",
     _footing(pedestal_height=800.0), _load(600.0, vy=150.0)),
    ("biaxial", "cortante en los dos ejes y momentos", _footing(), _load(500.0, vx=200.0, vy=200.0, mx=-30.0, my=40.0)),
    ("biaxial-alargada", "zapata alargada en X con cortante desbalanceado: la cara de ancho ly resiste poco",
     _footing(lx=4000.0, ly=1200.0), _load(250.0, vx=260.0, vy=20.0, seismic=True)),
    ("contacto-parcial", "momento grande: la adherencia actúa solo sobre el área en contacto",
     _footing(), _load(600.0, vx=120.0, my=380.0)),
    ("cohesion-y-sobrecargas", "relleno alto, sobrecargas y combinación sin viva",
     _footing(fill_height=1800.0, surcharge_dead_kNm2=3.0, surcharge_live_kNm2=8.0), _load(400.0, vx=230.0, live=0.0)),
    ("sismo-cumple", "con el factor sísmico cumple", _footing(), _load(300.0, vx=330.0, seismic=True)),
    ("sin-sismo-falla", "las mismas fuerzas sin marca de sismo no cumplen", _footing(), _load(300.0, vx=330.0)),
    ("volcamiento-falla", "excentricidad mayor que L/4: no cumple el volcamiento", _footing(), _load(500.0, my=420.0)),
    ("volcamiento-y-sismo", "momento en X con sismo: gobierna el eje Y", _footing(),
     _load(500.0, mx=-300.0, my=60.0, seismic=True)),
    ("desplazada", "columna desplazada con pedestal: el peso del pedestal y P cambian el momento en la base",
     _footing(pedestal_height=600.0, column={"cx": 500.0, "cy": 400.0, "offset_x": 400.0, "offset_y": 0.0}),
     _load(700.0, vx=-90.0, vy=40.0)),
    ("traccion", "carga de tracción: sin equilibrio, ambas fallan", _footing(), _load(-400.0, vx=50.0)),
]


def main() -> None:
    cases = [{"id": case_id, "description": text, "footing": footing, "load": load, "expected": _expected(footing, load)}
             for case_id, text, footing, load in CASES]
    for folder, clause in STABILITY_CLAUSES.items():
        data = {"description": "Deslizamiento y volcamiento de zapatas con casos de servicio (D-070). Resultante y contacto "
                               "de derive_footing_service.py; pasiva integrada como diagrama trapezoidal.",
                "soil": SOIL, "stability_clause": clause, "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_footing_stability.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
