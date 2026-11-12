"""Longitudes de desarrollo de barras corrugadas según NSR-10 Título C, capítulo C.12, con los factores de recubrimiento
(ψe), de recubrimiento de ganchos (C.12.5.3(a)) y de refuerzo en exceso (C.12.2.5, C.12.5.3(d)); sin los factores por
estribos o espirales (D-071)."""

import math

_SQRT_FC_MAX = 8.3
_CONFINEMENT_MAX = 2.5
_TOP_BAR_CONCRETE = 300.0
_LD_MIN = 300.0
_LDH_MIN = 150.0
_LDH_BARS = 8.0
_LDC_MIN = 200.0
_SMALL_BAR = 21.0  # mm: barras No. 6 (3/4") o 20M y menores (ψs = 0.8)
_EPOXY = frozenset({"epoxy", "zinc_epoxy"})
_EPOXY_CLOSE, _EPOXY_OTHER = 1.5, 1.2  # C.12.2.4(b): recubrimiento < 3db o separación libre < 6db
_EPOXY_COVER_BARS, _EPOXY_SPACING_BARS = 3.0, 6.0
_TOP_EPOXY_MAX = 1.7  # ψt·ψe
_HOOK_EPOXY = 1.2  # C.12.5.2
_HOOK_COVER_FACTOR = 0.7  # C.12.5.3(a)
_HOOK_COVER_MAX_DB = 36.0  # No. 11, 32M y menores
_HOOK_SIDE_COVER, _HOOK_EXTENSION_COVER = 65.0, 50.0
_EXCESS_LEVELS = frozenset({"DMI"})  # C.12.2.5 remite a "C.21.2.1.6", inexistente en NSR-10 (D-071)


def clauses() -> dict[str, str]:
    return {
        "tension": "C.12.2.1, C.12.2.3 y C.12.2.4",
        "hook": "C.12.5.1 y C.12.5.2",
        "compression": "C.12.3.1 y C.12.3.2",
        "excess": "C.12.2.5 y C.12.5.3(d)",
        "min_spacing": "C.7.6.1 y C.3.3.2(c)",
    }


_MIN_CLEAR_SPACING = 25.0  # mm
_AGGREGATE_FACTOR = 4.0 / 3.0  # C.3.3.2(c): agregado ≤ 3/4 de la separación libre mínima


def min_clear_spacing(db: float, aggregate: float) -> float:
    """C.7.6.1: separación libre mínima entre barras paralelas de una capa, db pero no menor de 25 mm; C.3.3.2(c): el
    tamaño máximo nominal del agregado no supera 3/4 de la separación libre, así que esta es al menos (4/3)·agregado."""
    return max(db, _MIN_CLEAR_SPACING, _AGGREGATE_FACTOR * aggregate)


def _sqrt_fc(fc: float) -> float:
    """C.12.1.2: √f'c ≤ 8.3 MPa en el cálculo de longitudes de desarrollo."""
    return min(math.sqrt(fc), _SQRT_FC_MAX)


def tension_coating_factor(coating: str, *, db: float, clear_cover: float, clear_spacing: float) -> float:
    """C.12.2.4(b), ψe: epóxico (o zinc y epóxico) 1.5 con recubrimiento < 3db o separación libre < 6db y 1.2 en otro
    caso; sin recubrimiento o galvanizado, 1.0."""
    if coating not in _EPOXY:
        return 1.0
    close = clear_cover < _EPOXY_COVER_BARS * db or clear_spacing < _EPOXY_SPACING_BARS * db
    return _EPOXY_CLOSE if close else _EPOXY_OTHER


def hook_coating_factor(coating: str) -> float:
    """C.12.5.2, ψe: 1.2 para barras con recubrimiento epóxico; 1.0 en otro caso."""
    return _HOOK_EPOXY if coating in _EPOXY else 1.0


def hook_cover_factor(*, db: float, side_cover: float, extension_cover: float) -> float:
    """C.12.5.3(a): 0.7 en ganchos de barras No. 11 y menores con recubrimiento lateral (normal al plano del gancho)
    ≥ 65 mm y, en ganchos de 90°, recubrimiento en la extensión ≥ 50 mm; 1.0 en otro caso (D-071)."""
    ok = db <= _HOOK_COVER_MAX_DB and side_cover >= _HOOK_SIDE_COVER and extension_cover >= _HOOK_EXTENSION_COVER
    return _HOOK_COVER_FACTOR if ok else 1.0


def excess_factor_permitted(end: str, seismic_level: str) -> bool:
    """C.12.2.5 (barras rectas) y C.12.5.3(d) (ganchos): As requerido/As suministrado solo con nivel DMI, porque la
    excepción sísmica de C.12.2.5 remite a un numeral que no existe en NSR-10; los pasadores a compresión no lo usan
    (D-071)."""
    return end in ("straight", "hook") and seismic_level in _EXCESS_LEVELS


def tension_development_length(*, fy: float, fc: float, lam: float, db: float, cb: float, concrete_below: float,
                               psi_e: float, excess: float) -> float:
    """C.12.2.3, ecuación (C.12-1), con Ktr = 0, multiplicada por excess = As requerido/As suministrado (C.12.2.5; 1 si no
    aplica) y no menor que 300 mm (C.12.2.1), en mm.

    cb es el menor entre la distancia del centro de la barra a la superficie más cercana y la mitad de la separación;
    concrete_below es el concreto fresco bajo la barra (ψt = 1.3 si supera 300 mm, C.12.2.4(a)); ψt·ψe ≤ 1.7.
    """
    psi_t = 1.3 if concrete_below > _TOP_BAR_CONCRETE else 1.0
    psi_s = 0.8 if db < _SMALL_BAR else 1.0
    confinement = min(cb / db, _CONFINEMENT_MAX)
    location = min(psi_t * psi_e, _TOP_EPOXY_MAX)
    length = fy / (1.1 * lam * _sqrt_fc(fc)) * location * psi_s / confinement * db
    return max(length * excess, _LD_MIN)


def hook_development_length(*, fy: float, fc: float, lam: float, db: float, psi_e: float, psi_cc: float, excess: float) -> float:
    """C.12.5.2: ldh = (0.24ψe·fy/(λ√f'c))·db, multiplicada por los factores de C.12.5.3 (a) psi_cc y (d) excess, no menor
    que 8db ni 150 mm (C.12.5.1), en mm."""
    return max(0.24 * psi_e * fy / (lam * _sqrt_fc(fc)) * db * psi_cc * excess, _LDH_BARS * db, _LDH_MIN)


def compression_development_length(*, fy: float, fc: float, lam: float, db: float) -> float:
    """C.12.3.2: el mayor de (0.24fy/(λ√f'c))·db y 0.043fy·db, sin los factores de C.12.3.3, no menor que 200 mm
    (C.12.3.1), en mm."""
    return max(0.24 * fy / (lam * _sqrt_fc(fc)) * db, 0.043 * fy * db, _LDC_MIN)
