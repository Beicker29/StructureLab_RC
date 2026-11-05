"""Torsión en vigas macizas no preesforzadas según ACI CODE-318-25 (9.2.4.4, 9.5.4, 9.6.4, 9.7.5, 9.7.6.3 y 22.7)."""

import math

_PHI_TORSION = 0.75
_SQRT_FC_MAX = 8.3
_FY_MAX = 420.0
_THETA = math.radians(45.0)
_SPACING_MAX = 300.0
_BAR_DIAMETER_MIN = 10.0


def clauses() -> dict[str, str]:
    return {
        "threshold": "9.5.4.1 y Tabla 22.7.4.1(a)",
        "section": "22.7.7.1(a)",
        "transverse": "22.7.6.1(a), 9.5.4.3 y 9.7.6.3.1",
        "longitudinal": "22.7.6.1(b) y 9.6.4.3",
        "min_transverse": "9.6.4.2",
        "spacing": "9.7.6.3.3",
        "detailing": "9.7.5.1 y 9.7.5.2",
    }


def strength_reduction() -> float:
    """Tabla 21.2.1(c)."""
    return _PHI_TORSION


def threshold_torsion(fc: float, lam: float, acp: float, pcp: float, nu: float, ag: float) -> float:
    """Tabla 22.7.4.1(a), filas (a) y (c), con √f'c ≤ 8.3 MPa (22.7.2.1); en N·mm. Nu positiva en compresión."""
    sqrt_fc = min(math.sqrt(fc), _SQRT_FC_MAX)
    factor = 1 + nu / (0.33 * ag * lam * sqrt_fc)
    return 0.083 * lam * sqrt_fc * acp**2 / pcp * math.sqrt(max(factor, 0.0))


def effective_overhang(h: float, hf: float) -> float:
    """9.2.4.4(a): saliente del ala por lado, el menor entre la proyección de la viga bajo la losa y 4hf."""
    return min(h - hf, 4 * hf)


def max_yield() -> float:
    """22.7.2.2 y Tabla 20.2.2.4(a): fy y fyt ≤ 420 MPa para torsión."""
    return _FY_MAX


def required_transverse(tu: float, a0: float, fyt: float) -> float:
    """At/s requerido por la ecuación (22.7.6.1a) con φTn = Tu y θ = 45° (22.7.6.1.2); en mm²/mm por rama."""
    return tu / (_PHI_TORSION * 2 * a0 * fyt / math.tan(_THETA))


def required_longitudinal(tu: float, at_s: float, a0: float, ph: float, fyt: float, fy: float) -> float:
    """Aℓ requerido por la ecuación (22.7.6.1b) con φTn = Tu y θ = 45°; en mm². at_s no interviene en este perfil."""
    return tu * ph / (_PHI_TORSION * 2 * a0 * fy * math.tan(_THETA))


def min_transverse(fc: float, bw: float, fyt: float) -> float:
    """9.6.4.2: (Av + 2At)min/s, en mm²/mm."""
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def min_longitudinal(fc: float, acp: float, fy: float, at_s: float, ph: float, fyt: float, bw: float) -> float:
    """9.6.4.3: Aℓ,min, la menor de (a) y (b); en mm², no menor que cero."""
    base = 0.42 * math.sqrt(fc) * acp / fy
    option_a = base - at_s * ph * fyt / fy
    option_b = base - 0.175 * bw / fyt * ph * fyt / fy
    return max(min(option_a, option_b), 0.0)


def combined_stress(vu: float, tu: float, bw: float, d: float, ph: float, aoh: float) -> float:
    """Lado izquierdo de la ecuación (22.7.7.1a), en MPa."""
    return math.hypot(vu / (bw * d), tu * ph / (1.7 * aoh**2))


def combined_stress_limit(vc: float, fc: float, bw: float, d: float) -> float:
    """Lado derecho de la ecuación (22.7.7.1a), en MPa."""
    return _PHI_TORSION * (vc / (bw * d) + 0.66 * math.sqrt(fc))


def max_spacing(ph: float) -> float:
    """9.7.6.3.3: separación de estribos de torsión."""
    return min(ph / 8, _SPACING_MAX)


def max_longitudinal_spacing() -> float:
    """9.7.5.1: separación de las barras de Aℓ alrededor del perímetro."""
    return _SPACING_MAX


def min_longitudinal_diameter(s: float) -> float:
    """9.7.5.2: diámetro mínimo de las barras de Aℓ."""
    return max(0.042 * s, _BAR_DIAMETER_MIN)
