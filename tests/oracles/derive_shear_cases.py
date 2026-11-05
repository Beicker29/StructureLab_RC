"""Genera los casos derivados del oráculo de cortante (Vc) con las ecuaciones escritas a mano. No importa el paquete.

Uso: python tests/oracles/derive_shear_cases.py
"""

import json
import math
from pathlib import Path
from typing import Any


def aci_vc(fc: float, bw: float, d: float, rho: float, nu: float, ag: float, av_ge_min: bool) -> float:
    """ACI CODE-318-25, Tabla 22.5.5.1 y 22.5.5.1.1 a 22.5.5.1.3 (λ = 1)."""
    root = math.sqrt(fc) if av_ge_min else min(math.sqrt(fc), 8.3)
    axial = min(nu / (6 * ag), 0.05 * fc)
    if av_ge_min:
        stress = max(0.17 * root + axial, 0.66 * rho ** (1 / 3) * root + axial)
    else:
        stress = 0.66 * min(math.sqrt(2 / (1 + d / 250)), 1.0) * rho ** (1 / 3) * root + axial
    vc = min(max(stress * bw * d, 0.0), 0.42 * root * bw * d)
    return max(vc, 0.083 * root * bw * d) if nu >= 0 else vc


def nsr_vc(fc: float, bw: float, d: float, h: float, rho: float, nu: float, ag: float, vu: float, mu: float) -> float:
    """NSR-10, mayor entre C.11.2.1 y C.11.2.2 (λ = 1, f'c ≤ 69 MPa)."""
    root = math.sqrt(fc)
    if nu > 0:
        simple = 0.17 * (1 + nu / (14 * ag)) * root * bw * d
        cap = 0.29 * root * bw * d * math.sqrt(1 + 0.29 * nu / ag)
        mm = mu - nu * (4 * h - d) / 8
        detailed = cap if mm <= 0 else min((0.16 * root + 17 * rho * vu * d / mm) * bw * d, cap)
    elif nu < 0:
        simple = 0.0
        detailed = max(0.17 * (1 + 0.29 * nu / ag) * root * bw * d, 0.0)
    else:
        simple = 0.17 * root * bw * d
        detailed = min((0.16 * root + 17 * rho * min(vu * d / mu, 1.0)) * bw * d, 0.29 * root * bw * d)
    return max(simple, detailed)


BASE: dict[str, Any] = {
    "fc": 28.0, "bw": 300.0, "d": 440.0, "h": 500.0, "rho_w": 0.0086, "nu": 0.0, "ag": 150000.0, "vu": 120e3, "mu": 150e6, "av_ge_min": True
}


def case(case_id: str, **changes: Any) -> dict[str, Any]:
    return {"id": case_id, **BASE, **changes}


ACI = [
    case("a_rige"),
    case("b_rige_cuantia_alta", rho_w=0.03),
    case("c_efecto_de_tamano", av_ge_min=False, d=900.0, h=1000.0, ag=300000.0, rho_w=0.01),
    case("compresion_con_tope_de_axial", fc=21.0, nu=3000e3),
    case("traccion_sin_minimo_de_tabla", nu=-400e3),
    case("raiz_de_fc_limitada", fc=81.0, av_ge_min=False, d=400.0, rho_w=0.02),
]
NSR = [
    case("simple_rige"),
    case("detallado_rige", rho_w=0.03, vu=200e3, mu=40e6),
    case("compresion_mm_positivo", nu=500e3),
    case("compresion_mm_negativo", nu=500e3, mu=50e6),
    case("traccion", nu=-400e3),
]


def main() -> None:
    root = Path(__file__).parent
    source = "Derivado a mano con las ecuaciones de cada perfil (derive_shear_cases.py); no proviene de un libro. N, mm, MPa."
    for folder, cases, function in (("aci_318_25", ACI, "aci"), ("nsr_10", NSR, "nsr")):
        for item in cases:
            fc, bw, d, rho, nu, ag = (item[key] for key in ("fc", "bw", "d", "rho_w", "nu", "ag"))
            if function == "aci":
                vc = aci_vc(fc, bw, d, rho, nu, ag, item["av_ge_min"])
            else:
                vc = nsr_vc(fc, bw, d, item["h"], rho, nu, ag, item["vu"], item["mu"])
            item["expected_Vc_N"] = vc
        payload = {"source": source, "tolerance_rel": 1e-9, "cases": cases}
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        (root / folder / "derived_shear.json").write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
