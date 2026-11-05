"""Genera los casos derivados del oráculo con solución cerrada. No importa el paquete.

Uso: python tests/oracles/derive_flexure_cases.py
Cada función verifica las hipótesis de su solución antes de devolver el resultado.
"""

import json
import math
from pathlib import Path

ECU = 0.003
ALPHA = 0.85
ES = 200_000.0
BAR_AREA = {"#5": 199.0, "#8": 510.0, "#9": 645.0}


def t_block_in_web(fc: float, fy: float, section: dict[str, float], area: float, d: float, beta1: float) -> dict[str, float]:
    bw, bf, hf = section["bw"], section["bf"], section["hf"]
    flange_force = ALPHA * fc * (bf - bw) * hf
    web_force = area * fy - flange_force
    a = web_force / (ALPHA * fc * bw)
    c = a / beta1
    strain = ECU * (d - c) / c
    assert a > hf
    assert strain > fy / ES
    return {"c": c, "a": a, "extreme_strain": strain, "Mn_Nmm": flange_force * (d - hf / 2) + web_force * (d - a / 2)}


def doubly_reinforced(
    fc: float, fy: float, b: float, tension: tuple[float, float], compression: tuple[float, float], beta1: float
) -> dict[str, float]:
    area, d = tension
    area_c, dc = compression
    displaced = ALPHA * fc
    a_coef = ALPHA * fc * b * beta1
    b_coef = area_c * ES * ECU - area_c * displaced - area * fy
    c_coef = -area_c * ES * ECU * dc
    c = (-b_coef + math.sqrt(b_coef**2 - 4 * a_coef * c_coef)) / (2 * a_coef)
    stress_c = ES * ECU * (c - dc) / c
    if stress_c > fy:
        c = (area * fy - area_c * (fy - displaced)) / a_coef
        stress_c = fy
    a = beta1 * c
    strain = ECU * (d - c) / c
    assert a > dc
    assert strain > fy / ES
    block = ALPHA * fc * b * a
    steel_c = area_c * (stress_c - displaced)
    return {"c": c, "a": a, "extreme_strain": strain, "Mn_Nmm": block * (d - a / 2) + steel_c * (d - dc)}


def tension_steel_elastic(fc: float, fy: float, b: float, area: float, d: float, beta1: float) -> dict[str, float]:
    a_coef = ALPHA * fc * b * beta1
    b_coef = area * ES * ECU
    c = (-b_coef + math.sqrt(b_coef**2 + 4 * a_coef * b_coef * d)) / (2 * a_coef)
    a = beta1 * c
    strain = ECU * (d - c) / c
    assert 0 < strain < fy / ES
    return {"c": c, "a": a, "extreme_strain": strain, "Mn_Nmm": ALPHA * fc * b * a * (d - a / 2)}


def with_axial(fc: float, fy: float, section: dict[str, float], area: float, d: float, axial: float, beta1: float) -> dict[str, float]:
    """Una capa a tracción en fluencia, bloque en el ala o en sección rectangular; Pn = Pu en el centroide bruto."""
    bw, h = section["bw"], section["h"]
    bf, hf = section.get("bf", bw), section.get("hf", h)
    gross = bw * h + (bf - bw) * hf
    centroid = (bw * h * h / 2 + (bf - bw) * hf * hf / 2) / gross
    tension = area * fy
    compression = tension + axial
    a = compression / (ALPHA * fc * bf)
    c = a / beta1
    strain = ECU * (d - c) / c
    assert a <= hf
    assert strain > fy / ES
    moment = compression * (centroid - a / 2) + tension * (d - centroid)
    return {"c": c, "a": a, "extreme_strain": strain, "Mn_Nmm": moment}


def layer(designation: str, count: int, depth: float) -> dict[str, object]:
    return {"designation": designation, "count": count, "depth": depth}


def area(designation: str, count: int) -> float:
    return count * BAR_AREA[designation]


T_SECTION = {"bw": 300.0, "h": 600.0, "bf": 800.0, "hf": 100.0}
RECTANGLE = {"bw": 300.0, "h": 500.0}
NARROW = {"bw": 250.0, "h": 460.0}


def cases(fc_t: float, beta_t: float, fc_d: float, beta_d: float, fc_e: float, beta_e: float) -> list[dict[str, object]]:
    return [
        {
            "id": "t_bloque_en_alma",
            "fc": fc_t,
            "fy": 420.0,
            "section": T_SECTION,
            "top_in_compression": True,
            "layers": [layer("#8", 12, 530.0)],
            "beta1": beta_t,
            "expected": t_block_in_web(fc_t, 420.0, T_SECTION, area("#8", 12), 530.0, beta_t),
        },
        {
            "id": "doble_refuerzo",
            "fc": fc_d,
            "fy": 420.0,
            "section": RECTANGLE,
            "top_in_compression": True,
            "layers": [layer("#5", 3, 60.0), layer("#8", 5, 440.0)],
            "beta1": beta_d,
            "expected": doubly_reinforced(fc_d, 420.0, 300.0, (area("#8", 5), 440.0), (area("#5", 3), 60.0), beta_d),
        },
        {
            "id": "t_momento_negativo_doble_refuerzo",
            "fc": fc_d,
            "fy": 420.0,
            "section": T_SECTION,
            "top_in_compression": False,
            "layers": [layer("#8", 8, 60.0), layer("#5", 2, 540.0)],
            "beta1": beta_d,
            "expected": doubly_reinforced(fc_d, 420.0, 300.0, (area("#8", 8), 540.0), (area("#5", 2), 60.0), beta_d),
        },
        {
            "id": "rectangular_compresion_axial",
            "fc": fc_d,
            "fy": 420.0,
            "section": RECTANGLE,
            "top_in_compression": True,
            "Pu_N": 300e3,
            "layers": [layer("#8", 3, 440.0)],
            "beta1": beta_d,
            "expected": with_axial(fc_d, 420.0, RECTANGLE, area("#8", 3), 440.0, 300e3, beta_d),
        },
        {
            "id": "rectangular_traccion_axial",
            "fc": fc_d,
            "fy": 420.0,
            "section": RECTANGLE,
            "top_in_compression": True,
            "Pu_N": -200e3,
            "layers": [layer("#8", 3, 440.0)],
            "beta1": beta_d,
            "expected": with_axial(fc_d, 420.0, RECTANGLE, area("#8", 3), 440.0, -200e3, beta_d),
        },
        {
            "id": "t_compresion_axial_centroide_bruto",
            "fc": fc_t,
            "fy": 420.0,
            "section": T_SECTION,
            "top_in_compression": True,
            "Pu_N": 400e3,
            "layers": [layer("#8", 4, 530.0)],
            "beta1": beta_t,
            "expected": with_axial(fc_t, 420.0, T_SECTION, area("#8", 4), 530.0, 400e3, beta_t),
        },
        {
            "id": "acero_a_traccion_elastico",
            "fc": fc_e,
            "fy": 420.0,
            "section": NARROW,
            "top_in_compression": True,
            "layers": [layer("#9", 8, 400.0)],
            "beta1": beta_e,
            "expected": tension_steel_elastic(fc_e, 420.0, 250.0, area("#9", 8), 400.0, beta_e),
        },
    ]


def main() -> None:
    root = Path(__file__).parent
    source = "Derivado a mano con solución cerrada (derive_flexure_cases.py); no proviene de un manual. Unidades: mm, MPa."
    profiles = {
        "aci_318_25": cases(28.0, 0.85, 35.0, 0.80, 21.0, 0.85),
        "nsr_10": cases(35.0, 0.80, 28.0, 0.85, 42.0, 0.75),
    }
    for folder, content in profiles.items():
        payload = {"source": source, "tolerance_rel": 1e-6, "cases": content}
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        (root / folder / "derived_flexure.json").write_text(text + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
