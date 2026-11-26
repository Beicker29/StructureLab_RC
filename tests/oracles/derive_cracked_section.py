"""Deriva el oráculo del esfuerzo de servicio del acero en la sección fisurada elástica (tests/oracles/mechanics/
cracked_section.json), para el control de agrietamiento con fs calculado (D-173, D-174).

No importa el paquete. Sección T con el ala en la cara comprimida (bf, hf; la rectangular es bf = bw) y capas de acero
en tracción a profundidad d desde esa cara; el acero comprimido no cuenta. El eje neutro c sale en forma cerrada de la
ecuación cuadrática del momento estático:
- c ≤ hf: bf·c²/2 = n·Σ As·(d − c);
- c > hf: bf·hf·(c − hf/2) + bw·(c − hf)²/2 = n·Σ As·(d − c).
Icr = el concreto comprimido respecto a c más n·Σ As·(d − c)², y fs = n·M·(d_max − c)/Icr en la capa más profunda.

Uso: python tests/oracles/derive_cracked_section.py
"""

import json
import math
from pathlib import Path

OUT = Path(__file__).parent / "mechanics" / "cracked_section.json"


def _root(a: float, b: float, c: float) -> float:
    """La raíz positiva de a·x² + b·x + c = 0 (a > 0, c < 0)."""
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)


def _expected(case: dict) -> dict:
    bw, bf, hf, n, moment = case["bw"], case["bf"], case["hf"], case["n"], case["moment"]
    layers = case["layers"]
    area = sum(a for _, a in layers)
    first = sum(a * d for d, a in layers)
    # Rectángulo bf: bf/2·c² + n·As·c − n·Σ As·d = 0 (todas las capas quedan en tracción en estos casos).
    c = _root(bf / 2, n * area, -n * first)
    if c > hf:  # bw/2·c² + (bf − bw)·hf·c + n·As·c − (bf − bw)·hf²/2 − n·Σ As·d = 0
        c = _root(bw / 2, (bf - bw) * hf + n * area, -(bf - bw) * hf**2 / 2 - n * first)
        concrete = bf * hf**3 / 12 + bf * hf * (c - hf / 2) ** 2 + bw * (c - hf) ** 3 / 3
    else:
        concrete = bf * c**3 / 3
    assert all(d > c for d, _ in layers)
    inertia = concrete + n * sum(a * (d - c) ** 2 for d, a in layers)
    deepest = max(d for d, _ in layers)
    return {"c": c, "Icr": inertia, "fs": n * moment * (deepest - c) / inertia}


CASES = [
    ("rectangular-manual", "ejemplo 2 del manual ACI: puntera de 24 in, N.° 7 cada 9 in, Ms = 7500 ft·lb/ft (fs = 5858 psi)",
     {"bw": 1000.0, "bf": 1000.0, "hf": 609.6, "h": 609.6, "n": 200000 / (4700 * math.sqrt(31.03)),
      "moment": 7500 * 1.3558179e3 / 0.3048, "layers": [[522.224, 0.8 * 645.16 / 0.3048]]}),
    ("t-eje-en-el-ala", "T con el eje neutro dentro del ala", {"bw": 400.0, "bf": 1500.0, "hf": 150.0, "h": 800.0, "n": 8.0,
                                                               "moment": 400e6, "layers": [[730.0, 2040.0], [670.0, 1020.0]]}),
    ("t-eje-en-el-alma", "T de ala delgada y mucho acero: el eje neutro baja al alma",
     {"bw": 300.0, "bf": 900.0, "hf": 100.0, "h": 700.0, "n": 7.5, "moment": 350e6, "layers": [[630.0, 4020.0], [570.0, 2010.0]]}),
]


def main() -> None:
    data = {"description": "Esfuerzo de servicio del acero en la sección fisurada elástica, en forma cerrada (N, mm, MPa).",
            "tolerance_rel": 1e-9,
            "cases": [{"id": case_id, "description": text, **case, "expected": _expected(case)} for case_id, text, case in CASES]}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
