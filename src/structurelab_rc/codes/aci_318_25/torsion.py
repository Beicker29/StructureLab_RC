"""Torsión según ACI CODE-318-25 (9.5.4.1, 22.7.2.1 y Tabla 22.7.4.1(a)). Por ahora, solo el umbral."""

import math

_PHI_TORSION = 0.75
_SQRT_FC_MAX = 8.3


def clauses() -> dict[str, str]:
    return {"threshold": "9.5.4.1 y Tabla 22.7.4.1(a)"}


def strength_reduction() -> float:
    """Tabla 21.2.1(c)."""
    return _PHI_TORSION


def threshold_torsion(fc: float, lam: float, acp: float, pcp: float, nu: float, ag: float) -> float:
    """Tabla 22.7.4.1(a), filas (a) y (c), con √f'c ≤ 8.3 MPa (22.7.2.1); en N·mm. Nu positiva en compresión."""
    sqrt_fc = min(math.sqrt(fc), _SQRT_FC_MAX)
    factor = 1 + nu / (0.33 * ag * lam * sqrt_fc)
    return 0.083 * lam * sqrt_fc * acp**2 / pcp * math.sqrt(max(factor, 0.0))
