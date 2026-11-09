"""Concreto estructural simple según NSR-10 Título C, capítulo C.22 (D-072)."""

import math

_PHI = 0.60  # C.9.3.5
_TENSION = 0.42  # C.22.5.1, ecuación (C.22-2): Mn = 0.42λ√f'c·Sm
_SOIL_CAST_REDUCTION = 50.0  # mm, C.22.4.7
# C.22.10.1: con DES no hay cimentaciones de concreto simple, salvo viviendas o zapatas de muro (no implementadas, D-072).
_FOUNDATION_LEVELS = frozenset({"DMI", "DMO"})


def clauses() -> dict[str, str]:
    return {"flexure": "C.22.5.1, C.22.4.7 y C.9.3.5", "seismic": "C.22.10.1"}


def strength_reduction() -> float:
    """C.9.3.5: φ del concreto estructural simple para flexión, compresión, cortante y aplastamiento."""
    return _PHI


def flexural_tension_stress(fc: float, lam: float) -> float:
    """C.22.5.1, ecuación (C.22-2): esfuerzo de tracción por flexión del momento nominal, 0.42λ√f'c (MPa)."""
    return _TENSION * lam * math.sqrt(fc)


def soil_cast_reduction() -> float:
    """C.22.4.7: el espesor total del concreto construido contra el suelo se toma 50 mm menor (mm)."""
    return _SOIL_CAST_REDUCTION


def permitted_in_foundations(seismic_level: str) -> bool:
    """C.22.10.1: las estructuras DES no pueden tener cimentaciones de concreto simple (salvo excepciones no
    implementadas); con DMI y DMO se permiten (D-072)."""
    return seismic_level in _FOUNDATION_LEVELS
