"""Longitudes de desarrollo de barras corrugadas según ACI CODE-318-25, sección 25.4, con los factores de recubrimiento
(ψe), de recubrimiento de ganchos (ψcc) y de refuerzo en exceso (25.4.10); ψr = 1.0 (D-071)."""

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
_EPOXY = frozenset({"epoxy", "zinc_epoxy"})
_EPOXY_CLOSE, _EPOXY_OTHER = 1.5, 1.2  # Tabla 25.4.2.5: recubrimiento libre < 3db o separación libre < 6db
_EPOXY_COVER_BARS, _EPOXY_SPACING_BARS = 3.0, 6.0
_TOP_EPOXY_MAX = 1.7  # ψt·ψe
_HOOK_EPOXY = 1.2  # Tabla 25.4.3.2
_HOOK_COVER_FACTOR = 0.7  # ψcc
_HOOK_COVER_MAX_DB = 36.0  # No. 36 y menores
_HOOK_SIDE_COVER, _HOOK_EXTENSION_COVER = 65.0, 50.0
_EXCESS_LEVELS = frozenset({"none", "ordinary"})  # 25.4.10.2(e): fuera del sistema sísmico en categorías C a F (D-071)


def clauses() -> dict[str, str]:
    return {
        "tension": "25.4.2.1, 25.4.2.4 y 25.4.2.5",
        "hook": "25.4.3.1 y 25.4.3.2",
        "compression": "25.4.9.1 a 25.4.9.3",
        "excess": "25.4.10",
        "min_spacing": "25.2.1",
    }


_MIN_CLEAR_SPACING = 25.0  # mm
_AGGREGATE_FACTOR = 4.0 / 3.0


def min_clear_spacing(db: float, aggregate: float) -> float:
    """25.2.1: separación libre mínima entre barras paralelas de una capa, el mayor de 25 mm, db y (4/3)dagg."""
    return max(_MIN_CLEAR_SPACING, db, _AGGREGATE_FACTOR * aggregate)


def _sqrt_fc(fc: float) -> float:
    """25.4.1.4: √f'c ≤ 8.3 MPa en el cálculo de longitudes de desarrollo."""
    return min(math.sqrt(fc), _SQRT_FC_MAX)


def _grade_factor(fy: float) -> float:
    """Tabla 25.4.2.5, ψg: grado 280 o 420, 1.0; grado 550, 1.15; grado 690, 1.3."""
    return next((factor for limit, factor in _GRADES if fy <= limit), _GRADE_LARGEST)


def tension_coating_factor(coating: str, *, db: float, clear_cover: float, clear_spacing: float) -> float:
    """Tabla 25.4.2.5, ψe: epóxico (o zinc y epóxico) 1.5 con recubrimiento libre < 3db o separación libre < 6db y 1.2 en
    otro caso; sin recubrimiento o galvanizado, 1.0."""
    if coating not in _EPOXY:
        return 1.0
    close = clear_cover < _EPOXY_COVER_BARS * db or clear_spacing < _EPOXY_SPACING_BARS * db
    return _EPOXY_CLOSE if close else _EPOXY_OTHER


def hook_coating_factor(coating: str) -> float:
    """Tabla 25.4.3.2, ψe: epóxico (o zinc y epóxico) 1.2; sin recubrimiento o galvanizado, 1.0."""
    return _HOOK_EPOXY if coating in _EPOXY else 1.0


def hook_cover_factor(*, db: float, side_cover: float, extension_cover: float) -> float:
    """Tabla 25.4.3.2, ψcc: 0.7 en ganchos de barras No. 36 y menores con recubrimiento lateral (normal al plano del
    gancho) ≥ 65 mm y, en ganchos de 90°, recubrimiento sobre la extensión ≥ 50 mm; 1.0 en otro caso (D-071)."""
    ok = db <= _HOOK_COVER_MAX_DB and side_cover >= _HOOK_SIDE_COVER and extension_cover >= _HOOK_EXTENSION_COVER
    return _HOOK_COVER_FACTOR if ok else 1.0


def excess_factor_permitted(end: str, seismic_level: str) -> bool:
    """25.4.10: As,requerido/As,suministrado solo en barras rectas a tracción (no en ganchos, 25.4.10.2(d); los pasadores
    a compresión no lo usan, D-071) y fuera del sistema sísmico en categorías C a F (25.4.10.2(e)): niveles none y
    ordinary (D-071)."""
    return end == "straight" and seismic_level in _EXCESS_LEVELS


def tension_development_length(*, fy: float, fc: float, lam: float, db: float, cb: float, concrete_below: float,
                               psi_e: float, excess: float, minimum: bool = True) -> float:
    """25.4.2.4 (ecuación 25.4.2.4a) con Ktr = 0, multiplicada por excess = As,req/As,sum (25.4.10.1; 1 si no aplica) y no
    menor que 300 mm (25.4.2.1), en mm.

    cb es el menor entre la distancia del centro de la barra a la superficie más cercana y la mitad de la separación;
    concrete_below es el concreto fresco bajo la barra (ψt = 1.3 si supera 300 mm); ψt·ψe ≤ 1.7.
    minimum = False omite los 300 mm de 25.4.2.1(b): el ℓd de los empalmes por traslapo (25.5.2.1).
    """
    psi_t = 1.3 if concrete_below > _TOP_BAR_CONCRETE else 1.0
    psi_s = 0.8 if db < _SMALL_BAR else 1.0
    confinement = min(cb / db, _CONFINEMENT_MAX)
    location = min(psi_t * psi_e, _TOP_EPOXY_MAX)
    length = fy * location * psi_s * _grade_factor(fy) / (1.1 * lam * _sqrt_fc(fc) * confinement) * db
    return max(length * excess, _LD_MIN) if minimum else length * excess


def hook_development_length(*, fy: float, fc: float, lam: float, db: float, psi_e: float, psi_cc: float, excess: float) -> float:
    """25.4.3.1 con ψr = 1.0, no menor que 8db ni 150 mm, en mm. excess debe ser 1: 25.4.10.2(d) no permite el factor de
    refuerzo en exceso en ganchos.

    El PDF imprime 21 en el denominador; se usa 4.2, la constante SI de la ecuación del ACI 318-14 que R25.4.3.1 dice
    restaurar (D-066).
    """
    if excess != 1.0:
        raise ValueError("25.4.10.2(d): el factor de refuerzo en exceso no se permite en ganchos")
    psi_s = next((factor for limit, factor in _HOOK_SIZE if db <= limit), _HOOK_SIZE_LARGEST)
    length = fy * psi_e * psi_s * psi_cc / (_HOOK_CONSTANT * lam * _sqrt_fc(fc)) * db
    return max(length, _LDH_BARS * db, _LDH_MIN)


def compression_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """25.4.9.2 con ψr = 1.0: el mayor de fy·db/(4.2λ√f'c) y 0.043fy·db, no menor que 200 mm (25.4.9.1), en mm."""
    return max(fy / (4.2 * lam * _sqrt_fc(fc)) * db, 0.043 * fy * db, _LDC_MIN)
