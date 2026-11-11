"""Vigas altas según NSR-10 Título C (C.11.7 y C.10.7): límite de sección y refuerzo distribuido. La condición de viga
alta (C.11.7.1) la declara el usuario; el diseño con la distribución no lineal de deformaciones o el Apéndice C-A
(C.11.7.2, C.10.7.1) no se implementa (D-089)."""

import math

_SECTION_FACTOR = 0.83
_SQRT_FC_MAX = 8.3
_MIN_DISTRIBUTED_RATIO = 0.0025
_SPACING_MAX = 300.0
_DEPTH_DIVISOR = 5.0


def clauses() -> dict[str, str]:
    return {
        "section": "C.11.7.3",
        "transverse": "C.11.7.4.1",
        "longitudinal": "C.11.7.4.2",
        "spacing": "C.11.7.4.1 y C.11.7.4.2",
        "curtains": "C.11.7.4",
    }


def section_limit(fc: float, bw: float, d: float) -> float:
    """C.11.7.3 sin φ: 0.83√f'c·bw·d, en N, con √f'c ≤ 8.3 MPa (C.11.1.2)."""
    return _SECTION_FACTOR * min(math.sqrt(fc), _SQRT_FC_MAX) * bw * d


def min_distributed_ratio() -> float:
    """C.11.7.4.1 y C.11.7.4.2: Av ≥ 0.0025·bw·s y Avh ≥ 0.0025·bw·s2."""
    return _MIN_DISTRIBUTED_RATIO


def max_distributed_spacing(d: float) -> float:
    """C.11.7.4.1 y C.11.7.4.2: s y s2, el menor entre d/5 y 300 mm."""
    return min(d / _DEPTH_DIVISOR, _SPACING_MAX)


def max_curtain_spacing(bw: float) -> float | None:
    """C.11.7.4 pide el refuerzo distribuido en las dos caras laterales, sin límite de separación entre cortinas: None."""
    return None
