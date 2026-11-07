"""Aplastamiento del concreto según ACI CODE-318-25, 22.8 y Tabla 21.2.1."""

import math

_PHI_BEARING = 0.65
_RATIO_MAX = 2.0


def clauses() -> dict[str, str]:
    return {"bearing": "22.8.3.2 y Tabla 21.2.1"}


def strength_reduction() -> float:
    """Tabla 21.2.1 (d): aplastamiento, φ = 0.65."""
    return _PHI_BEARING


def nominal_bearing(fc: float, a1: float, a2: float) -> float:
    """Tabla 22.8.3.2: Bn = √(A2/A1)·0.85f'c·A1, no mayor que 2·0.85f'c·A1; con A2 = A1 queda 0.85f'c·A1, en N."""
    return min(math.sqrt(a2 / a1), _RATIO_MAX) * 0.85 * fc * a1
