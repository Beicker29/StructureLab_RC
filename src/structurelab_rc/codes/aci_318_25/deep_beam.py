"""Vigas de gran altura según ACI CODE-318-25 (9.9): límite de sección, refuerzo distribuido y su colocación. La
condición de viga alta (9.9.1.1) la declara el usuario; la resistencia por análisis no lineal o puntal-tensor (9.9.1.2,
9.9.1.3) no se implementa (D-089)."""

import math

_SECTION_FACTOR = 0.83
_MIN_DISTRIBUTED_RATIO = 0.0025
_SPACING_MAX = 300.0
_DEPTH_DIVISOR = 5.0
_SPAN_TO_DEPTH = 4.0
_CURTAIN_WIDTH = 200.0
_CURTAIN_SPACING_MAX = 600.0


def clauses() -> dict[str, str]:
    return {
        "definition": "9.9.1.1(a)",
        "section": "9.9.2.1",
        "transverse": "9.9.3.1(a)",
        "longitudinal": "9.9.3.1(b)",
        "spacing": "9.9.4.3",
        "curtains": "9.9.4.4",
    }


def max_span_to_depth() -> float:
    """9.9.1.1(a): viga de gran altura si la luz libre no excede 4h. El diseño usa este límite para declarar la viga alta (D-109)."""
    return _SPAN_TO_DEPTH


def section_limit(fc: float, bw: float, d: float) -> float:
    """Ecuación (9.9.2.1) sin φ: 0.83√f'c·bw·d, en N."""
    return _SECTION_FACTOR * math.sqrt(fc) * bw * d


def min_distributed_ratio() -> float:
    """9.9.3.1(a) y (b): Atd ≥ 0.0025·bw·std y Aℓd ≥ 0.0025·bw·sd."""
    return _MIN_DISTRIBUTED_RATIO


def max_distributed_spacing(d: float) -> float:
    """9.9.4.3: separación del refuerzo distribuido, la menor entre d/5 y 300 mm."""
    return min(d / _DEPTH_DIVISOR, _SPACING_MAX)


def max_curtain_spacing(bw: float) -> float | None:
    """9.9.4.4: con bw > 200 mm, una cortina cerca de cada cara y no más de 600 mm entre cortinas; None si no aplica."""
    return _CURTAIN_SPACING_MAX if bw > _CURTAIN_WIDTH else None
