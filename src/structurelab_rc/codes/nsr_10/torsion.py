"""Torsión según NSR-10 Título C (C.11.5.1 y C.11.1.2). Por ahora, solo el umbral."""

import math

_PHI_TORSION = 0.75
_SQRT_FC_MAX = 8.3


def clauses() -> dict[str, str]:
    return {"threshold": "C.11.5.1"}


def strength_reduction() -> float:
    """C.9.3.2.3."""
    return _PHI_TORSION


def threshold_torsion(fc: float, lam: float, acp: float, pcp: float, nu: float, ag: float) -> float:
    """C.11.5.1 (a) y (c), con √f'c ≤ 8.3 MPa (C.11.1.2); en N·mm, sin φ. Nu positiva en compresión."""
    sqrt_fc = min(math.sqrt(fc), _SQRT_FC_MAX)
    factor = 1 + nu / (0.33 * ag * lam * sqrt_fc)
    return 0.083 * lam * sqrt_fc * acp**2 / pcp * math.sqrt(max(factor, 0.0))
