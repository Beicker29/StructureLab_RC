"""Flexión de vigas según NSR-10 Título C (C.9.3.2, C.10.3 y C.10.5)."""

import math

_PHI_COMPRESSION = 0.65
_PHI_TENSION = 0.90
_TENSION_CONTROLLED = 0.005
_BEAM_MIN_STRAIN = 0.004


def clauses() -> dict[str, str]:
    return {
        "strength": "C.9.3.2.1 y C.9.3.2.2",
        "net_tensile_strain": "C.10.3.5",
        "axial_limit": "C.10.3.5",
        "min_reinforcement": "C.10.5.1 y C.10.5.2",
        "min_reinforcement_exception": "C.10.5.3",
    }


def yield_strain(fy: float, es: float) -> float:
    """C.10.3.3: límite controlado por compresión, εty = fy/Es (D-020)."""
    return fy / es


def strength_reduction_moment(et: float, ety: float) -> float:
    """C.9.3.2.1 y C.9.3.2.2 (b): lineal entre εty y 0.005, límite controlado por tracción de C.10.3.4."""
    if et <= ety:
        return _PHI_COMPRESSION
    if et >= _TENSION_CONTROLLED:
        return _PHI_TENSION
    return 0.65 + 0.25 * (et - ety) / (_TENSION_CONTROLLED - ety)


def beam_min_net_tensile_strain(ety: float) -> float:
    """C.10.3.5: εt ≥ 0.004 en elementos a flexión con Pu < 0.10 f'c·Ag."""
    return _BEAM_MIN_STRAIN


def beam_axial_limit(fc: float, ag: float) -> float:
    """C.10.3.5: límite 0.10 f'c·Ag, en N."""
    return 0.10 * fc * ag


def min_flexural_reinforcement(fc: float, fy: float, bw: float, d: float) -> float:
    """C.10.5.1, ecuación (C.10-3) y mínimo 1.4·bw·d/fy; en mm²."""
    return max(0.25 * math.sqrt(fc) / fy * bw * d, 1.4 * bw * d / fy)


def determinate_flange_width(bw: float, bf: float) -> float:
    """C.10.5.2: ancho para As,min en elemento isostático con el ala a tracción."""
    return min(2 * bw, bf)
