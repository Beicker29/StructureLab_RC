"""Deriva el oráculo de la pantalla del muro en voladizo (D-173, fase A, etapa 3) para los dos perfiles.

No importa el paquete. Por franja de 1 m, en N, mm y MPa:

1. Empuje sobre la cara de la pantalla, con la altura del relleno sobre la base H: Rankine, Ka = tan²(45° − φ'/2),
   horizontal; Coulomb, Ka de la ec. 12.26 con β = 90° y el δ' declarado, P_h = P_a·cos δ'. Vu = factor·P_h y
   Mu = Vu·H/3 en la unión con la base.
2. Flexión con el bloque rectangular: a = As·fy/(0.85·f'c·b), c = a/β1 (β1 = 0.85 hasta 28 MPa y 0.05 menos cada 7 MPa,
   no menor que 0.65), εt = 0.003·(d − c)/c, φ = 0.90 si la sección es controlada por tracción (ACI: εt ≥ fy/Es + 0.003;
   NSR-10: εt ≥ 0.005), Mn = As·fy·(d − a/2), con d = t − recubrimiento − db/2. Tracción controlada: ACI εt ≥ εty + 0.003;
   NSR-10 εt ≥ 0.004 (C.10.3.5).
3. Cortante sin refuerzo de cortante (Vn = Vc, λ = 1, √f'c ≤ 8.3, φ = 0.75, Vu ≤ φVc), ρw = As/(b·d):
   - ACI: el mayor de 0.17·√f'c·b·d (13.3.6.1.1) y la fila (c) de la Tabla 22.5.5.1, 0.66·λs·ρw^(1/3)·√f'c·b·d con
     λs = √(2/(1 + d/250)) ≤ 1, no mayor que 0.42·√f'c·b·d ni menor que 0.083·√f'c·b·d.
   - NSR-10: el mayor de 0.17·√f'c·b·d (C.11-3) y (0.16·√f'c + 17·ρw·Vu·d/Mu)·b·d con Vu·d/Mu ≤ 1, no mayor que
     0.29·√f'c·b·d (C.11-5).
   - Límite de dimensiones de la sección: Vu ≤ φ(Vc + 0.66·√f'c·b·d) (ACI 22.5.1.2; NSR-10 C.11.4.7.9).
4. As mínimo 0.0018·b·t en los dos perfiles (ACI 7.6.1.1; NSR-10 C.10.5.4 y C.7.12.2.1 con 350 < fy ≤ 420); separación
   máxima el menor de 3t y 450 mm; agrietamiento s ≤ min(380·280/fs − 2.5·cc, 300·280/fs), fs = 2/3·fy.
5. Horizontal en cada cara: ACI la mitad de 0.0018 (24.4.3.2), separación ≤ min(5t, 450); NSR-10 la mitad de 0.0020
   (barras ≤ 16 mm con fy ≥ 420) o de 0.0025, separación ≤ min(3t, 450) (C.14.3.3 y C.14.3.5).
6. Verticales de la cara exterior: la mitad de 0.0018 en los dos perfiles, separación ≤ min(5t, 450).

Uso: python tests/oracles/derive_wall_stem.py
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
STRIP = 1000.0
ES = 200000.0
BARS = {"#4": (12.7, 129.0), "#5": (15.9, 199.0), "#6": (19.1, 284.0), "#7": (22.2, 387.0)}  # diámetro (mm), área (mm²)
CLAUSES = {"aci_318_25": ("13.3.6.1 y 7.5.1.1(a)", "22.5.1.2"), "nsr_10": ("C.14.1.2 y C.10", "C.11.4.7.9")}


def _coulomb(beta: float, phi: float, delta: float) -> float:
    """Ec. 12.26 de Das 2016 con relleno horizontal (ángulos en grados)."""
    b, p, d = (math.radians(value) for value in (beta, phi, delta))
    root = math.sqrt(math.sin(p + d) * math.sin(p) / (math.sin(b - d) * math.sin(b)))
    return math.sin(b + p) ** 2 / (math.sin(b) ** 2 * math.sin(b - d) * (1 + root) ** 2)


def _beta1(fc: float) -> float:
    return max(0.65, min(0.85, 0.85 - 0.05 * (fc - 28.0) / 7.0))


def _expected(profile: str, data: dict) -> dict:
    wall, soil, fc, fy = data["wall"], data["soil"], data["fc"], data["fy"]
    t, height, cover = wall["stem_thickness"], wall["backfill_height"], wall["stem_cover"]
    gamma, phi = soil["unit_weight_backfill"] * 1e-6, soil["friction_angle"]  # N/mm³
    pressure = wall["earth_pressure"]
    if pressure["method"] == "coulomb":
        delta = pressure["wall_friction_angle"]
        ph = 0.5 * _coulomb(90.0, phi, delta) * gamma * height**2 * math.cos(math.radians(delta))
    else:
        ph = 0.5 * math.tan(math.radians(45.0 - phi / 2)) ** 2 * gamma * height**2
    vu = data["earth_factor"] * ph * STRIP
    mu = vu * height / 3
    db, bar_area = BARS[wall["stem"]["back"]["designation"]]
    spacing = wall["stem"]["back"]["spacing"]
    area = bar_area * STRIP / spacing
    depth = t - cover - db / 2
    a = area * fy / (0.85 * fc * STRIP)
    c = a / _beta1(fc)
    strain = 0.003 * (depth - c) / c
    controlled = fy / ES + 0.003 if profile == "aci_318_25" else 0.005
    phi_m = 0.90 if strain >= controlled else float("nan")
    mn = area * fy * (depth - a / 2)
    minimum_strain = fy / ES + 0.003 if profile == "aci_318_25" else 0.004
    root = min(math.sqrt(fc), 8.3)
    rho = area / (STRIP * depth)
    if profile == "aci_318_25":
        size = min(math.sqrt(2 / (1 + depth / 250)), 1.0)
        table = min(max(0.66 * size * rho ** (1 / 3) * root, 0.083 * root), 0.42 * root) * STRIP * depth
    else:
        table = min(0.16 * root + 17 * rho * min(vu * depth / mu, 1.0), 0.29 * root) * STRIP * depth
    vc = max(0.17 * root * STRIP * depth, table)
    section = 0.75 * (vc + 0.66 * root * STRIP * depth)
    fs = 2 / 3 * fy
    crack = min(380.0 * 280.0 / fs - 2.5 * cover, 300.0 * 280.0 / fs)
    h_db, h_area = BARS[wall["stem"]["horizontal"]["designation"]]
    if profile == "aci_318_25":
        horizontal_ratio, horizontal_max = 0.0018, min(5 * t, 450.0)
    else:
        horizontal_ratio = 0.0020 if h_db <= 16.0 and fy >= 420.0 else 0.0025
        horizontal_max = min(3 * t, 450.0)
    horizontal = h_area * STRIP / wall["stem"]["horizontal"]["spacing"]
    front = BARS[wall["stem"]["front"]["designation"]][1] * STRIP / wall["stem"]["front"]["spacing"]
    return {"Mu": mu, "Vu": vu, "As": area, "d": depth, "phiMn": phi_m * mn, "et": strain, "phiVc": 0.75 * vc,
            "Vc_table": table, "section": section, "section_status": "PASS" if vu <= section else "FAIL",
            "As_min": 0.0018 * STRIP * t, "spacing_max": min(3 * t, 450.0), "crack": crack,
            "horizontal_each_face": horizontal_ratio * STRIP * t / 2, "horizontal": horizontal, "horizontal_max": horizontal_max,
            "front_required": 0.0018 / 2 * STRIP * t, "front": front, "front_max": min(5 * t, 450.0),
            "flexure": "PASS" if phi_m * mn >= mu else "FAIL", "strain": "PASS" if strain >= minimum_strain else "FAIL",
            "minimum": "PASS" if area >= 0.0018 * STRIP * t else "FAIL", "spacing": "PASS" if spacing <= min(3 * t, 450.0) else "FAIL",
            "crack_status": "PASS" if spacing <= crack else "FAIL", "shear": "PASS" if vu <= 0.75 * vc else "FAIL",
            "horizontal_status": "PASS" if horizontal >= horizontal_ratio * STRIP * t / 2 else "FAIL",
            "front_status": "PASS" if front >= 0.0018 / 2 * STRIP * t else "FAIL"}


def _bars(designation: str, spacing: float) -> dict:
    return {"designation": designation, "spacing": spacing, "end": "straight"}


def _wall(**change: object) -> dict:
    """La pantalla del ejemplo 2 del manual (15 in, relleno de 16 ft sobre la base), en mm."""
    return {"stem_thickness": 381.0, "backfill_height": 4876.8, "stem_cover": 50.8,
            "earth_pressure": {"state": "active", "method": "rankine"},
            "stem": {"back": _bars("#7", 228.6), "front": _bars("#5", 457.2), "horizontal": _bars("#5", 457.2)}, **change}


SOIL = {"unit_weight_backfill": 17.28, "friction_angle": 35.0}
CASES = [
    ("manual-ejemplo-2", "la pantalla del ejemplo 2 del manual (N.° 7 cada 9 in), 1.6H", _wall()),
    ("coulomb", "Coulomb sobre la cara con δ' = 20°", _wall(earth_pressure={"state": "active", "method": "coulomb",
                                                                            "wall_friction_angle": 20.0})),
    ("delgada", "pantalla de 250 mm con N.° 5 cada 300 mm: no alcanza la flexión y la separación pasa la de agrietamiento",
     _wall(stem_thickness=250.0, stem={"back": _bars("#5", 300.0), "front": _bars("#4", 450.0),
                                       "horizontal": _bars("#4", 450.0)})),
    ("cuantia-alta", "pantalla de 300 mm con N.° 7 cada 90 mm (ρw = 0.018, controlada por tracción): en el ACI gobierna "
                     "la fila (c) de la Tabla 22.5.5.1",
     _wall(stem_thickness=300.0, stem={"back": _bars("#7", 90.0), "front": _bars("#4", 450.0),
                                       "horizontal": _bars("#4", 450.0)})),
]


def main() -> None:
    for folder, (clause, section_clause) in CLAUSES.items():
        cases = []
        for case_id, text, wall in CASES:
            data = {"wall": wall, "soil": SOIL, "fc": 31.03, "fy": 413.7, "earth_factor": 1.6}
            cases.append({"id": case_id, "description": text, **data, "expected": _expected(folder, data)})
        payload = {"description": "Pantalla del muro en voladizo (D-173): flexión, cortante, mínimos, separaciones y refuerzo "
                                  "de distribución, con fórmulas cerradas escritas aquí.",
                   "strength_clause": clause, "section_clause": section_clause, "tolerance_rel": 1e-9, "cases": cases}
        (HERE / folder / "derived_wall_stem.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                                              encoding="utf-8")


if __name__ == "__main__":
    main()
