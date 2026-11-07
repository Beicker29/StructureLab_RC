"""Longitudes de desarrollo de barras corrugadas según NSR-10 Título C, capítulo C.12 (barras sin recubrimiento epóxico)."""

import math

_SQRT_FC_MAX = 8.3
_CONFINEMENT_MAX = 2.5
_TOP_BAR_CONCRETE = 300.0
_LD_MIN = 300.0
_LDH_MIN = 150.0
_LDH_BARS = 8.0
_LDC_MIN = 200.0
_SMALL_BAR = 21.0  # mm: barras No. 6 (3/4") o 20M y menores (ψs = 0.8)


def clauses() -> dict[str, str]:
    return {
        "tension": "C.12.2.1, C.12.2.3 y C.12.2.4",
        "hook": "C.12.5.1 y C.12.5.2",
        "compression": "C.12.3.1 y C.12.3.2",
    }


def _sqrt_fc(fc: float) -> float:
    """C.12.1.2: √f'c ≤ 8.3 MPa en el cálculo de longitudes de desarrollo."""
    return min(math.sqrt(fc), _SQRT_FC_MAX)


def tension_development_length(*, fy: float, fc: float, lam: float, db: float, cb: float, concrete_below: float) -> float:
    """C.12.2.3, ecuación (C.12-1), con Ktr = 0 y ψe = 1, no menor que 300 mm (C.12.2.1), en mm.

    cb es el menor entre la distancia del centro de la barra a la superficie más cercana y la mitad de la separación;
    concrete_below es el concreto fresco bajo la barra (ψt = 1.3 si supera 300 mm, C.12.2.4(a)).
    """
    psi_t = 1.3 if concrete_below > _TOP_BAR_CONCRETE else 1.0
    psi_s = 0.8 if db < _SMALL_BAR else 1.0
    confinement = min(cb / db, _CONFINEMENT_MAX)
    length = fy / (1.1 * lam * _sqrt_fc(fc)) * psi_t * psi_s / confinement * db
    return max(length, _LD_MIN)


def hook_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """C.12.5.2: ldh = (0.24ψe·fy/(λ√f'c))·db con ψe = 1, sin los factores de C.12.5.3, no menor que 8db ni 150 mm
    (C.12.5.1), en mm."""
    return max(0.24 * fy / (lam * _sqrt_fc(fc)) * db, _LDH_BARS * db, _LDH_MIN)


def compression_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """C.12.3.2: el mayor de (0.24fy/(λ√f'c))·db y 0.043fy·db, sin los factores de C.12.3.3, no menor que 200 mm
    (C.12.3.1), en mm."""
    return max(0.24 * fy / (lam * _sqrt_fc(fc)) * db, 0.043 * fy * db, _LDC_MIN)
