"""Deriva el oráculo de estabilidad y presiones del muro de contención en voladizo (D-173) para los dos perfiles.

No importa el paquete. Unidades de trabajo: kN, m y kPa, por metro de muro. Para cada caso de servicio:

1. Empuje (Das 2016, decisión 9 de D-173), con relleno horizontal (α = 0):
   - Rankine: Ka = tan²(45° − φ'/2), sobre el plano vertical por el extremo del talón (AB), horizontal, a H'/3, con
     H' = espesor de la base + relleno. El suelo que cuenta como peso es todo el relleno sobre el talón. Con talón corto
     el paquete usa Chu sobre AC más la cuña, que equivale exactamente a esto: la prueba comprueba la equivalencia.
   - Coulomb con talón corto (θ_v < η, con η = 45° − φ'/2 y θ_v = atan(talón/H')): plano AC, β = 90° − θ_v y δ = φ';
     Ka con la ec. 12.26 escrita aquí; a H'/3 sobre AC. El suelo que cuenta es la cuña entre la pantalla, la cara
     superior del talón y AC, menos la cuña de concreto del talón entre AC y AB.
   - Ko de Jaky: 1 − sen φ', sobre AB, horizontal. El coeficiente declarado, sobre AB, horizontal.
2. Pesos: pantalla y base con γc; suelo con γs; todo por su factor del caso. Momentos alrededor del borde de la puntera.
3. Volcamiento: Mr = Σ W·x + Pv·x_P contra Mo = Ph·y_P. Deslizamiento: R = μ·N + Pp, con Pp = ½·Kp·γf·hb² sobre el
   espesor de la base (si se declara), contra Ph.
4. Presiones: x_r = (Mr − Mo)/N, e = x_r − B/2. Con |e| ≤ B/6, q = N/B·(1 ± 6e/B) y contacto total; con B/6 < |e| < B/2,
   triángulo de largo 3·(B/2 − |e|) y q_max = 2N/(3·(B/2 − |e|)).

Uso: python tests/oracles/derive_wall_stability.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
GAMMA_C = 23.56  # kN/m³
STABILITY = {"aci_318_25": ("13.3.1.1", "13.2.6.1"), "nsr_10": ("C.15.2.2", "Titulo H (remision), factores declarados (D-070)")}


def _coulomb(beta: float, phi: float, delta: float, alpha: float) -> float:
    """Ec. 12.26 de Das 2016 (ángulos en grados)."""
    b, p, d, a = (math.radians(value) for value in (beta, phi, delta, alpha))
    root = math.sqrt(math.sin(p + d) * math.sin(p - a) / (math.sin(b - d) * math.sin(a + b)))
    return math.sin(b + p) ** 2 / (math.sin(b) ** 2 * math.sin(b - d) * (1 + root) ** 2)


def _thrust(wall: dict, soil: dict) -> tuple[float, float, float, float, float]:
    """Sin factores: P_h, P_v, la x de P_a y el suelo que cuenta como peso con su x (kN/m y m, desde el borde de la
    puntera)."""
    t, toe, heel, hb, hf = (wall[key] / 1e3 for key in ("stem_thickness", "toe", "heel", "base_thickness", "backfill_height"))
    width, height = toe + t + heel, hb + hf
    gamma_s, phi = soil["unit_weight_backfill"], soil["friction_angle"]
    stem_face = toe + t
    method = wall["earth_pressure"]["method"]
    theta_v = math.degrees(math.atan(heel / height))
    eta = 45.0 - phi / 2
    if method == "coulomb" and theta_v < eta:
        # Talón corto con Coulomb: AC, β = 90° − θ_v y δ = φ'; P_a forma con la horizontal 90° − β + φ' y actúa a H'/3
        # sobre AC. Peso: la cuña de suelo entre la pantalla, la cara superior del talón y AC, menos la cuña de concreto
        # del talón entre AC y AB bajo la cara superior del talón.
        beta = 90.0 - theta_v
        ka = _coulomb(beta, phi, phi, 0.0)
        pa = 0.5 * ka * gamma_s * height**2
        angle = math.radians(90.0 - beta + phi)
        ph, pv = pa * math.cos(angle), pa * math.sin(angle)
        x_p = width + (stem_face - width) / 3
        edge = width + (stem_face - width) * hb / height  # donde AC corta la cara superior del talón
        wedge, wedge_x = 0.5 * (edge - stem_face) * hf, (2 * stem_face + edge) / 3
        sliver, sliver_x = 0.5 * hb * (width - edge), (2 * width + edge) / 3
        soil_weight = gamma_s * (wedge - sliver)
        soil_x = (wedge * wedge_x - sliver * sliver_x) / (wedge - sliver)
    else:
        if method == "declared":
            k = wall["earth_pressure"]["coefficient"]
        elif method == "jaky":
            k = 1 - math.sin(math.radians(phi))
        else:
            k = math.tan(math.radians(45.0 - phi / 2)) ** 2
        ph, pv, x_p = 0.5 * k * gamma_s * height**2, 0.0, width
        soil_weight, soil_x = gamma_s * heel * hf, stem_face + heel / 2
    return ph, pv, x_p, soil_weight, soil_x


def _expected(wall: dict, soil: dict, case: dict) -> dict:
    t, hs, toe, heel, hb, hf = (wall[key] / 1e3 for key in ("stem_thickness", "stem_height", "toe", "heel", "base_thickness",
                                                           "backfill_height"))
    width, height = toe + t + heel, hb + hf
    ph, pv, x_p, soil_weight, soil_x = _thrust(wall, soil)
    y_p = height / 3
    stem = GAMMA_C * t * hs * case["dead_factor"]
    base = GAMMA_C * width * hb * case["dead_factor"]
    fill = soil_weight * case["fill_factor"]
    ph, pv = ph * case["earth_factor"], pv * case["earth_factor"]
    n = stem + base + fill + pv
    mr = stem * (toe + t / 2) + base * width / 2 + fill * soil_x + pv * x_p
    mo = ph * y_p
    kp = soil.get("passive_coefficient")
    pp = 0.0 if kp is None else 0.5 * kp * soil["unit_weight_front"] * hb**2
    resistance = soil["friction_coefficient"] * n + pp
    x_r = (mr - mo) / n
    e = x_r - width / 2
    common = {"N_kN": n, "H_kN": ph, "Mr_kNm": mr, "Mo_kNm": mo}
    if abs(e) >= width / 2:  # la resultante sale de la base: sin equilibrio, las cuatro revisiones fallan
        return {**common, "equilibrium": False, "bearing": "FAIL", "contact_status": "FAIL", "sliding": "FAIL",
                "overturning": "FAIL"}
    if abs(e) <= width / 6:
        q_toe, q_heel = n / width * (1 - 6 * e / width), n / width * (1 + 6 * e / width)
        contact = 1.0
    else:
        length = 3 * (width / 2 - abs(e))
        q_peak = 2 * n / length
        q_toe, q_heel = (q_peak, 0.0) if e < 0 else (0.0, q_peak)
        contact = length / width
    q_max = max(q_toe, q_heel)
    return {**common, "equilibrium": True, "R_kN": resistance, "Pp_kN": pp, "e_m": e,
            "q_max_kPa": q_max, "q_toe_kPa": q_toe, "q_heel_kPa": q_heel, "contact": contact,
            "FS_overturning": mr / mo, "FS_sliding": resistance / ph,
            "bearing": "PASS" if q_max <= soil["allowable_pressure_kPa"] else "FAIL",
            "contact_status": "PASS" if contact >= soil["min_contact_fraction"] else "FAIL",
            "sliding": "PASS" if soil["sliding_safety_factor"] * ph <= resistance else "FAIL",
            "overturning": "PASS" if soil["overturning_safety_factor"] * mo <= mr else "FAIL"}


def _soil(**change: object) -> dict:
    """El suelo del ejemplo 2 del manual ACI MNL-17(21) en SI (sin el peso del concreto, que va en concrete)."""
    return {"unit_weight_backfill": 17.28, "friction_angle": 35.0, "friction_coefficient": 0.5, "allowable_pressure_kPa": 143.64,
            "min_contact_fraction": 1.0, "sliding_safety_factor": 1.5, "overturning_safety_factor": 2.0, **change}


def _wall(**change: object) -> dict:
    """El muro del ejemplo 2 del manual con la base de 24 in (la revisada), en mm."""
    return {"stem_height": 4876.8, "stem_thickness": 381.0, "toe": 762.0, "heel": 1676.4, "base_thickness": 609.6,
            "backfill_height": 4876.8, "earth_pressure": {"state": "active", "method": "rankine"}, **change}


SERVICE = {"case": "D+H", "kind": "service", "dead_factor": 1.0, "fill_factor": 1.0, "earth_factor": 1.0}
COULOMB = {"state": "active", "method": "coulomb", "wall_friction_angle": 20.0}
CASES = [
    ("manual-ejemplo-2", "el ejemplo 2 del manual con la base de 24 in: cumple todo", _wall(), _soil(), SERVICE),
    ("pasiva", "la pasiva frente a la puntera suma al deslizamiento", _wall(), _soil(passive_coefficient=3.69,
                                                                                   unit_weight_front=17.28), SERVICE),
    ("talon-corto-coulomb", "talón corto con Coulomb: plano AC con δ = φ', la cuña y la componente vertical",
     _wall(heel=1200.0, earth_pressure=COULOMB), _soil(cohesion=0.0), SERVICE),
    ("reposo-jaky", "Ko de Jaky: el empuje crece y el deslizamiento no cumple", _wall(earth_pressure={"state": "at_rest",
                                                                                                   "method": "jaky"}),
     _soil(), SERVICE),
    ("contacto-parcial", "puntera corta y talón corto con Ka declarado: la resultante sale del tercio medio",
     _wall(toe=300.0, heel=1300.0, earth_pressure={"state": "active", "method": "declared", "coefficient": 0.25}),
     _soil(min_contact_fraction=0.5, allowable_pressure_kPa=400.0), SERVICE),
    ("sin-equilibrio", "Ka declarado grande: la resultante sale de la base y las cuatro revisiones fallan",
     _wall(toe=300.0, heel=1300.0, earth_pressure={"state": "active", "method": "declared", "coefficient": 0.6}),
     _soil(min_contact_fraction=0.5, allowable_pressure_kPa=400.0), SERVICE),
    ("factores", "factores de servicio distintos de 1 en el peso y el empuje",
     _wall(), _soil(), {"case": "0.9D+H", "kind": "service", "dead_factor": 0.9, "fill_factor": 0.9, "earth_factor": 1.0}),
]


def main() -> None:
    cases = [{"id": case_id, "description": text, "wall": wall, "soil": soil, "case": case,
              "expected": _expected(wall, soil, case)} for case_id, text, wall, soil, case in CASES]
    for folder, (bearing, stability) in STABILITY.items():
        data = {"description": "Estabilidad y presiones del muro en voladizo con casos de servicio (D-173). Empuje de Rankine, "
                               "Coulomb (ec. 12.26) o Jaky escritos aquí; presión trapezoidal o triangular cerrada.",
                "unit_weight_concrete_kNm3": GAMMA_C, "bearing_clause": bearing, "stability_clause": stability,
                "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_wall_stability.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                                                                   encoding="utf-8")


if __name__ == "__main__":
    main()
