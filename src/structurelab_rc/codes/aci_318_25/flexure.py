"""Flexión de vigas según ACI CODE-318-25 (21.2.2, 9.3.3.1, 9.5.2.1 y 9.6.1)."""

import math

_PHI_COMPRESSION = 0.65
_PHI_TENSION = 0.90
_TRANSITION_SPAN = 0.003
_FY_MAX_AS_MIN = 550.0
_EXEMPTION_FACTOR = 4 / 3
_CRACK_SPACING = 380.0
_CRACK_SPACING_CAP = 300.0
_CRACK_STRESS = 280.0
_CRACK_COVER = 2.5
_SERVICE_STRESS = 2 / 3


def clauses() -> dict[str, str]:
    return {
        "strength": "9.5.1.1(a) y Tabla 21.2.2",
        "net_tensile_strain": "9.3.3.1",
        "axial_limit": "9.5.2.1",
        "min_reinforcement": "9.6.1.2",
        "min_reinforcement_exception": "9.6.1.3",
        "crack_spacing": "24.3.2 y 24.3.2.1",
    }


def yield_strain(fy: float, es: float) -> float:
    """21.2.2.1: εty = fy/Es (D-020)."""
    return fy / es


def _tension_controlled_strain(ety: float) -> float:
    """Tabla 21.2.2 (e) y (f)."""
    return ety + _TRANSITION_SPAN


def strength_reduction_moment(et: float, ety: float) -> float:
    """Tabla 21.2.2, refuerzo transversal distinto de espiral: filas (b), (d) y (f)."""
    if et <= ety:
        return _PHI_COMPRESSION
    if et >= _tension_controlled_strain(ety):
        return _PHI_TENSION
    return 0.65 + 0.25 * (et - ety) / _TRANSITION_SPAN


def min_net_tensile_strain(ety: float) -> float:
    """Controlada por tracción: vigas con Pu < 0.10 f'c·Ag (9.3.3.1) y losas y zapatas (7.3.3.1, 8.3.3.1)."""
    return _tension_controlled_strain(ety)


def beam_axial_limit(fc: float, ag: float) -> float:
    """9.5.2.1: límite 0.10 f'c·Ag, en N."""
    return 0.10 * fc * ag


def min_flexural_reinforcement(fc: float, fy: float, bw: float, d: float) -> float:
    """9.6.1.2 (a) y (b), con fy limitado a 550 MPa (D-019); en mm²."""
    fy = min(fy, _FY_MAX_AS_MIN)
    return max(0.25 * math.sqrt(fc) / fy * bw * d, 1.4 / fy * bw * d)


def effective_min_reinforcement(as_min: float, as_analysis: float) -> float:
    """9.6.1.3: si el As provisto en cada sección es al menos un tercio mayor que el requerido por análisis, 9.6.1.2 no
    se exige; el As que debe proveerse es entonces el menor entre As,min y 4/3 del requerido por análisis, en mm²."""
    return min(as_min, _EXEMPTION_FACTOR * as_analysis)


def crack_control_spacing(fy: float, cc: float) -> float:
    """Tabla 24.3.2, barras corrugadas: el menor de 380·(280/fs) − 2.5·cc y 300·(280/fs), con fs = (2/3)·fy
    (24.3.2.1) y cc la menor distancia de la superficie del refuerzo a la cara en tracción; en mm."""
    fs = _SERVICE_STRESS * fy
    return min(_CRACK_SPACING * _CRACK_STRESS / fs - _CRACK_COVER * cc, _CRACK_SPACING_CAP * _CRACK_STRESS / fs)


def determinate_flange_width(bw: float, bf: float) -> float:
    """9.6.1.2: ancho para As,min en viga isostática con el ala a tracción."""
    return min(bf, 2 * bw)
