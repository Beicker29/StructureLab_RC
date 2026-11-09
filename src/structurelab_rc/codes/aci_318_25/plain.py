"""Concreto estructural simple según ACI CODE-318-25, capítulo 14 (D-072)."""

import math

_PHI = 0.60  # Tabla 21.2.1(f)
_TENSION = 0.42  # 14.5.2.1(a): Mn = 0.42λ√f'c·Sm
_SOIL_CAST_REDUCTION = 50.0  # mm, 14.5.1.7
# 14.1.3: en categorías de diseño sísmico D a F solo viviendas o zapatas de muro; special se toma como D a F (D-072).
_FOUNDATION_LEVELS = frozenset({"none", "ordinary", "intermediate"})


def clauses() -> dict[str, str]:
    return {"flexure": "14.5.2.1, 14.5.1.7 y Tabla 21.2.1(f)", "seismic": "14.1.3"}


def strength_reduction() -> float:
    """Tabla 21.2.1(f): φ de los elementos de concreto simple, igual para todos los modos de falla."""
    return _PHI


def flexural_tension_stress(fc: float, lam: float) -> float:
    """14.5.2.1(a): esfuerzo de tracción por flexión del momento nominal, 0.42λ√f'c (MPa); Mn = este valor por Sm."""
    return _TENSION * lam * math.sqrt(fc)


def soil_cast_reduction() -> float:
    """14.5.1.7: el espesor total del concreto vaciado contra el suelo se toma 50 mm menor (mm)."""
    return _SOIL_CAST_REDUCTION


def permitted_in_foundations(seismic_level: str) -> bool:
    """14.1.3: concreto simple en cimentaciones fuera de las categorías de diseño sísmico D a F (D-072)."""
    return seismic_level in _FOUNDATION_LEVELS
