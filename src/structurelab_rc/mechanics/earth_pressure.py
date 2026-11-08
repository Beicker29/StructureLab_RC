"""Empuje pasivo de Rankine con coeficiente Kp dado, por unidad de ancho (N, mm, MPa).

La presión a la profundidad z es Kp·γ·z + 2c·√Kp. Entre las profundidades top y top + height:

    Pp = ½·Kp·γ·((top + height)² − top²) + 2c·√Kp·height
"""

import math


def passive_force(kp: float, unit_weight: float, top: float, height: float, cohesion: float) -> float:
    """Empuje pasivo por unidad de ancho (N/mm) sobre la altura height que empieza a la profundidad top."""
    return 0.5 * kp * unit_weight * ((top + height) ** 2 - top**2) + 2 * cohesion * math.sqrt(kp) * height
