"""Aplastamiento del concreto según NSR-10 Título C, C.10.14 y C.9.3.2.4."""

import math

_PHI_BEARING = 0.65
_RATIO_MAX = 2.0


def clauses() -> dict[str, str]:
    return {"bearing": "C.10.14.1 y C.9.3.2.4"}


def strength_reduction() -> float:
    """C.9.3.2.4: aplastamiento en el concreto, φ = 0.65."""
    return _PHI_BEARING


def nominal_bearing(fc: float, a1: float, a2: float) -> float:
    """C.10.14.1: 0.85f'c·A1 multiplicado por √(A2/A1), no mayor que 2, cuando el apoyo es más ancho que el área cargada,
    en N."""
    return min(math.sqrt(a2 / a1), _RATIO_MAX) * 0.85 * fc * a1
