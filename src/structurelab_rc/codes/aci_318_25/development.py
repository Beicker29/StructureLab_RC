"""Longitudes de desarrollo de barras corrugadas según ACI CODE-318-25, sección 25.4 (barras sin recubrimiento epóxico)."""

import math

_SQRT_FC_MAX = 8.3
_CONFINEMENT_MAX = 2.5
_TOP_BAR_CONCRETE = 300.0
_LD_MIN = 300.0
_LDH_MIN = 150.0
_LDH_BARS = 8.0
_LDC_MIN = 200.0
_SMALL_BAR = 22.0  # mm: No. 19 y menores (ψs = 0.8 en tracción recta)
_HOOK_SIZE = ((29.0, 1.0), (36.0, 1.15), (43.0, 1.3))  # diámetro máximo (mm) y ψs de ganchos; mayores: 1.5
_HOOK_SIZE_LARGEST = 1.5
_HOOK_CONSTANT = 4.2  # 25.4.3.1(a) corregida (D-066)
_GRADES = ((420.0, 1.0), (550.0, 1.15))  # fy máximo (MPa) y ψg; mayores: 1.3
_GRADE_LARGEST = 1.3


def clauses() -> dict[str, str]:
    return {
        "tension": "25.4.2.1, 25.4.2.4 y 25.4.2.5",
        "hook": "25.4.3.1 y 25.4.3.2",
        "compression": "25.4.9.1 a 25.4.9.3",
    }


def _sqrt_fc(fc: float) -> float:
    """25.4.1.4: √f'c ≤ 8.3 MPa en el cálculo de longitudes de desarrollo."""
    return min(math.sqrt(fc), _SQRT_FC_MAX)


def _grade_factor(fy: float) -> float:
    """Tabla 25.4.2.5, ψg: grado 280 o 420, 1.0; grado 550, 1.15; grado 690, 1.3."""
    return next((factor for limit, factor in _GRADES if fy <= limit), _GRADE_LARGEST)


def tension_development_length(*, fy: float, fc: float, lam: float, db: float, cb: float, concrete_below: float) -> float:
    """25.4.2.4 (ecuación 25.4.2.4a) con Ktr = 0 y ψe = 1, no menor que 300 mm (25.4.2.1), en mm.

    cb es el menor entre la distancia del centro de la barra a la superficie más cercana y la mitad de la separación;
    concrete_below es el concreto fresco bajo la barra (ψt = 1.3 si supera 300 mm).
    """
    psi_t = 1.3 if concrete_below > _TOP_BAR_CONCRETE else 1.0
    psi_s = 0.8 if db < _SMALL_BAR else 1.0
    confinement = min(cb / db, _CONFINEMENT_MAX)
    length = fy * psi_t * psi_s * _grade_factor(fy) / (1.1 * lam * _sqrt_fc(fc) * confinement) * db
    return max(length, _LD_MIN)


def hook_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """25.4.3.1 con ψe = 1 y ψcc = ψr = 1.0 (permitido por 25.4.3.2), no menor que 8db ni 150 mm, en mm.

    El PDF imprime 21 en el denominador; se usa 4.2, la constante SI de la ecuación del ACI 318-14 que R25.4.3.1 dice
    restaurar (D-066).
    """
    psi_s = next((factor for limit, factor in _HOOK_SIZE if db <= limit), _HOOK_SIZE_LARGEST)
    length = fy * psi_s / (_HOOK_CONSTANT * lam * _sqrt_fc(fc)) * db
    return max(length, _LDH_BARS * db, _LDH_MIN)


def compression_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """25.4.9.2 con ψr = 1.0: el mayor de fy·db/(4.2λ√f'c) y 0.043fy·db, no menor que 200 mm (25.4.9.1), en mm."""
    return max(fy / (4.2 * lam * _sqrt_fc(fc)) * db, 0.043 * fy * db, _LDC_MIN)
