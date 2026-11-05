"""Torsión en vigas macizas no preesforzadas según NSR-10 Título C (C.11.5, C.13.2.4 y C.11.1.2)."""

import math

_PHI_TORSION = 0.75
_SQRT_FC_MAX = 8.3
_FY_MAX = 420.0
_THETA = math.radians(45.0)
_SPACING_MAX = 300.0
_BAR_DIAMETER_MIN = 10.0


def clauses() -> dict[str, str]:
    return {
        "threshold": "C.11.5.1",
        "section": "C.11.5.3.1(a)",
        "transverse": "C.11.5.3.5, C.11.5.3.6, C.11.5.3.8 y C.11.5.4.1",
        "longitudinal": "C.11.5.3.7 y C.11.5.5.3",
        "min_transverse": "C.11.5.5.2",
        "spacing": "C.11.5.6.1",
        "detailing": "C.11.5.6.2",
    }


def strength_reduction() -> float:
    """C.9.3.2.3."""
    return _PHI_TORSION


def threshold_torsion(fc: float, lam: float, acp: float, pcp: float, nu: float, ag: float) -> float:
    """C.11.5.1 (a) y (c), con √f'c ≤ 8.3 MPa (C.11.1.2); en N·mm, sin φ. Nu positiva en compresión."""
    sqrt_fc = min(math.sqrt(fc), _SQRT_FC_MAX)
    factor = 1 + nu / (0.33 * ag * lam * sqrt_fc)
    return 0.083 * lam * sqrt_fc * acp**2 / pcp * math.sqrt(max(factor, 0.0))


def effective_overhang(h: float, hf: float) -> float:
    """C.11.5.1 y C.13.2.4: saliente del ala por lado, el menor entre la proyección bajo la losa y 4hf."""
    return min(h - hf, 4 * hf)


def max_yield() -> float:
    """C.11.5.3.4: fy y fyt ≤ 420 MPa para torsión."""
    return _FY_MAX


def required_transverse(tu: float, a0: float, fyt: float) -> float:
    """At/s requerido por la ecuación (C.11-21) con φTn = Tu (C.11-20) y θ = 45° (C.11.5.3.6); en mm²/mm por rama."""
    return tu / (_PHI_TORSION * 2 * a0 * fyt / math.tan(_THETA))


def required_longitudinal(tu: float, at_s: float, a0: float, ph: float, fyt: float, fy: float) -> float:
    """Ecuación (C.11-22) con el At/s calculado por (C.11-21); en mm². Tu y A₀ no intervienen en este perfil."""
    return at_s * ph * (fyt / fy) / math.tan(_THETA) ** 2


def min_transverse(fc: float, bw: float, fyt: float) -> float:
    """C.11.5.5.2, ecuación (C.11-23): (Av + 2At)min/s, en mm²/mm."""
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def min_longitudinal(fc: float, acp: float, fy: float, at_s: float, ph: float, fyt: float, bw: float) -> float:
    """C.11.5.5.3, ecuación (C.11-24), con At/s ≥ 0.175bw/fyt; en mm², no menor que cero."""
    at_s = max(at_s, 0.175 * bw / fyt)
    return max(0.42 * math.sqrt(fc) * acp / fy - at_s * ph * fyt / fy, 0.0)


def combined_stress(vu: float, tu: float, bw: float, d: float, ph: float, aoh: float) -> float:
    """Lado izquierdo de la ecuación (C.11-18), en MPa."""
    return math.hypot(vu / (bw * d), tu * ph / (1.7 * aoh**2))


def combined_stress_limit(vc: float, fc: float, bw: float, d: float) -> float:
    """Lado derecho de la ecuación (C.11-18), en MPa."""
    return _PHI_TORSION * (vc / (bw * d) + 0.66 * math.sqrt(fc))


def max_spacing(ph: float) -> float:
    """C.11.5.6.1: separación de estribos de torsión."""
    return min(ph / 8, _SPACING_MAX)


def max_longitudinal_spacing() -> float:
    """C.11.5.6.2: separación de las barras de Aℓ alrededor del perímetro."""
    return _SPACING_MAX


def min_longitudinal_diameter(s: float) -> float:
    """C.11.5.6.2: diámetro mínimo de las barras de Aℓ."""
    return max(0.042 * s, _BAR_DIAMETER_MIN)
