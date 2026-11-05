"""Cortante en vigas no preesforzadas según ACI CODE-318-25 (21.2.1, 22.5, 9.6.3 y 9.7.6.2)."""

import math

_PHI_SHEAR = 0.75
_SQRT_FC_MAX = 8.3
_FYT_MAX = 420.0
_SHALLOW_DEPTH = 250.0
_INTEGRAL_DEPTH_MAX = 600.0


def clauses() -> dict[str, str]:
    return {
        "strength": "9.5.1.1(b), 22.5.1.1 y Tabla 21.2.1(b)",
        "section": "22.5.1.2",
        "min_reinforcement": "9.6.3.1 y Tabla 9.6.3.4",
        "spacing": "Tabla 9.7.6.2.2",
        "concrete": "Tabla 22.5.5.1",
    }


def strength_reduction() -> float:
    """Tabla 21.2.1(b)."""
    return _PHI_SHEAR


def _sqrt_fc(fc: float, av_ge_min: bool) -> float:
    """22.5.3.1 y 22.5.3.2: √f'c ≤ 8.3 MPa salvo con Av,min."""
    return math.sqrt(fc) if av_ge_min else min(math.sqrt(fc), _SQRT_FC_MAX)


def concrete_shear(
    *, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, nu: float, ag: float, vu: float, mu: float, av_ge_min: bool
) -> float:
    """Tabla 22.5.5.1 con 22.5.5.1.1 a 22.5.5.1.3, en N; con Av ≥ Av,min toma la mayor de (a) y (b) (D-029).

    Nu es positiva en compresión. h, Vu y Mu no intervienen en este perfil.
    """
    sqrt_fc = _sqrt_fc(fc, av_ge_min)
    axial = min(nu / (6 * ag), 0.05 * fc)
    if av_ge_min:
        stress = max(0.17 * lam * sqrt_fc + axial, 0.66 * lam * math.cbrt(rho_w) * sqrt_fc + axial)
    else:
        lambda_s = min(math.sqrt(2 / (1 + d / 250)), 1.0)
        stress = 0.66 * lambda_s * lam * math.cbrt(rho_w) * sqrt_fc + axial
    vc = min(max(stress * bw * d, 0.0), 0.42 * lam * sqrt_fc * bw * d)
    if nu >= 0:
        # 22.5.5.1.1: Vc no necesita tomarse menor que 0.083λ√f'c·bw·d sin tracción axial neta.
        vc = max(vc, 0.083 * lam * sqrt_fc * bw * d)
    return vc


def max_stirrup_yield() -> float:
    """22.5.3.3 y Tabla 20.2.2.4(a): estribos de barra corrugada, fyt ≤ 420 MPa."""
    return _FYT_MAX


def steel_shear(av: float, fyt: float, d: float, s: float) -> float:
    """Ecuación (22.5.8.5.3), en N."""
    return av * fyt * d / s


def max_steel_shear(fc: float, bw: float, d: float) -> float:
    """22.5.1.2: Vu ≤ φ(Vc + 0.66√f'c·bw·d); devuelve el término 0.66√f'c·bw·d, en N."""
    return 0.66 * math.sqrt(fc) * bw * d


def min_shear_reinforcement(fc: float, bw: float, fyt: float) -> float:
    """Tabla 9.6.3.4 (a) y (b): Av,min/s, en mm²/mm."""
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def min_reinforcement_exempt(h: float, bw: float, hf: float | None) -> bool:
    """Tabla 9.6.3.1 (a) y (b): h ≤ 250 mm, o viga integral con losa (ala hf) con h ≤ mayor de 2.5hf y 0.5bw y h ≤ 600 mm."""
    if h <= _SHALLOW_DEPTH:
        return True
    return hf is not None and h <= max(2.5 * hf, 0.5 * bw) and h <= _INTEGRAL_DEPTH_MAX


def min_reinforcement_threshold(vc: float, fc: float, lam: float, bw: float, d: float, exempt: bool) -> float | None:
    """9.6.3.1: Av,min se exige si Vu supera φ·0.083λ√f'c·bw·d (D-031), o φVc en los casos de la Tabla 9.6.3.1."""
    if exempt:
        return _PHI_SHEAR * vc
    return _PHI_SHEAR * 0.083 * lam * math.sqrt(fc) * bw * d


def max_spacing(vs: float, fc: float, bw: float, d: float) -> float:
    """Tabla 9.7.6.2.2, a lo largo del miembro, con el Vs requerido."""
    if vs <= 0.33 * math.sqrt(fc) * bw * d:
        return min(d / 2, 600.0)
    return min(d / 4, 300.0)


def max_leg_spacing_across(vs: float, fc: float, bw: float, d: float) -> float | None:
    """Tabla 9.7.6.2.2, a lo ancho del miembro, con el Vs requerido."""
    return d if vs <= 0.33 * math.sqrt(fc) * bw * d else d / 2
