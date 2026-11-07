"""Cortante en vigas no preesforzadas según NSR-10 Título C (C.9.3.2.3, C.11.1 a C.11.4)."""

import math

_PHI_SHEAR = 0.75
_SQRT_FC_MAX = 8.3
_FYT_MAX = 420.0
_SHALLOW_DEPTH = 250.0
_INTEGRAL_DEPTH_MAX = 600.0


def clauses() -> dict[str, str]:
    return {
        "strength": "C.11.1.1 y C.9.3.2.3",
        "section": "C.11.4.7.9",
        "min_reinforcement": "C.11.4.6.1 y C.11.4.6.3",
        "spacing": "C.11.4.5.1 y C.11.4.5.3",
        "biaxial": "no aplica en NSR-10",
        "concrete": "C.11.2.1 y C.11.2.2",
        "punching": "C.11.11.2.1 y C.11.11.7",
    }


def strength_reduction() -> float:
    """C.9.3.2.3."""
    return _PHI_SHEAR


def limited_sqrt_fc(fc: float, av_ge_min: bool) -> float:
    """C.11.1.2 y C.11.1.2.1: √f'c ≤ 8.3 MPa salvo con refuerzo mínimo."""
    return math.sqrt(fc) if av_ge_min else min(math.sqrt(fc), _SQRT_FC_MAX)


def _detailed(
    *, sqrt_fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, nu: float, ag: float, vu: float, mu: float
) -> float:
    """C.11.2.2.1 a C.11.2.2.3."""
    if nu < 0:
        return max(0.17 * (1 + 0.29 * nu / ag) * lam * sqrt_fc * bw * d, 0.0)  # (C.11-8)
    if nu > 0:
        cap = 0.29 * lam * sqrt_fc * bw * d * math.sqrt(1 + 0.29 * nu / ag)  # (C.11-7)
        mm = mu - nu * (4 * h - d) / 8  # (C.11-6)
        if mm <= 0:
            return cap
        return min((0.16 * lam * sqrt_fc + 17 * rho_w * vu * d / mm) * bw * d, cap)
    ratio = min(vu * d / mu, 1.0) if mu > 0 else 1.0
    return min((0.16 * lam * sqrt_fc + 17 * rho_w * ratio) * bw * d, 0.29 * lam * sqrt_fc * bw * d)  # (C.11-5)


def concrete_shear(
    *, fc: float, lam: float, bw: float, d: float, h: float, rho_w: float, nu: float, ag: float, vu: float, mu: float, av_ge_min: bool
) -> float:
    """Mayor entre C.11.2.1 y C.11.2.2 (D-030), en N. Nu es positiva en compresión; Vu y Mu en valor absoluto."""
    sqrt_fc = limited_sqrt_fc(fc, av_ge_min)
    if nu > 0:
        simple = 0.17 * (1 + nu / (14 * ag)) * lam * sqrt_fc * bw * d  # (C.11-4)
    elif nu < 0:
        simple = 0.0  # C.11.2.1.3
    else:
        simple = 0.17 * lam * sqrt_fc * bw * d  # (C.11-3)
    detailed = _detailed(sqrt_fc=sqrt_fc, lam=lam, bw=bw, d=d, h=h, rho_w=rho_w, nu=nu, ag=ag, vu=vu, mu=mu)
    return max(simple, detailed)


def max_stirrup_yield() -> float:
    """C.11.4.2: fyt ≤ 420 MPa."""
    return _FYT_MAX


def steel_shear(av: float, fyt: float, d: float, s: float) -> float:
    """C.11.4.7.2, ecuación (C.11-15), en N."""
    return av * fyt * d / s


def max_steel_shear(fc: float, bw: float, d: float) -> float:
    """C.11.4.7.9: Vs no mayor que 0.66√f'c·bw·d, en N."""
    return 0.66 * math.sqrt(fc) * bw * d


def min_shear_reinforcement(fc: float, bw: float, fyt: float) -> float:
    """C.11.4.6.3, ecuación (C.11-13): Av,min/s, en mm²/mm."""
    return max(0.062 * math.sqrt(fc) * bw / fyt, 0.35 * bw / fyt)


def min_reinforcement_exempt(h: float, bw: float, hf: float | None) -> bool:
    """C.11.4.6.1 (d) y (e): h ≤ 250 mm, o viga integral con losa (ala hf) con h ≤ 600 mm y ≤ mayor de 2.5hf y 0.5bw."""
    if h <= _SHALLOW_DEPTH:
        return True
    return hf is not None and h <= max(2.5 * hf, 0.5 * bw) and h <= _INTEGRAL_DEPTH_MAX


def min_reinforcement_threshold(vc: float, fc: float, lam: float, bw: float, d: float, exempt: bool) -> float | None:
    """C.11.4.6.1: Av,min se exige si Vu > 0.5φVc; en los casos exceptuados no se exige."""
    return None if exempt else 0.5 * _PHI_SHEAR * vc


def max_spacing(vs: float, fc: float, bw: float, d: float) -> float:
    """C.11.4.5.1 y C.11.4.5.3, con el Vs requerido."""
    if vs <= 0.33 * math.sqrt(fc) * bw * d:
        return min(d / 2, 600.0)
    return min(d / 4, 300.0)


def max_leg_spacing_across(vs: float, fc: float, bw: float, d: float) -> float | None:
    """NSR-10 no limita la separación de las ramas a lo ancho del miembro."""
    return None


def biaxial_interaction(ratio_2: float, ratio_3: float) -> bool | None:
    """NSR-10 no tiene regla de interacción del cortante en dos direcciones: cada una se verifica por separado (D-046)."""
    return None


_PUNCHING_ALPHA = {0: 40.0, 1: 30.0, 2: 20.0}


def punching_concrete_stress(*, fc: float, lam: float, lam_s: float, beta: float, alpha_s: float, d: float, b0: float) -> float:
    """C.11.11.2.1, ecuaciones (C.11-31) a (C.11-33) divididas por b0·d, en MPa: el menor de 0.17(1 + 2/β),
    0.083(αs·d/b0 + 2) y 0.33, por λ·√f'c, con √f'c ≤ 8.3 MPa (C.11.1.2). NSR-10 no tiene λs: se ignora."""
    sqrt_fc = min(math.sqrt(fc), _SQRT_FC_MAX)
    factor = min(0.17 * (1 + 2 / beta), 0.083 * (alpha_s * d / b0 + 2), 0.33)
    return factor * lam * sqrt_fc


def punching_alpha_s(sides_outside: int) -> float | None:
    """C.11.11.2.1(b): 40 (columna interior), 30 (de borde) o 20 (de esquina)."""
    return _PUNCHING_ALPHA.get(sides_outside)


def moment_transfer_fraction(b1: float, b2: float) -> float:
    """C.13.5.3.2, ecuación (C.13-1): γf = 1/(1 + (2/3)√(b1/b2)); por cortante, γv = 1 − γf (C.11.11.7.1)."""
    return 1 / (1 + 2 / 3 * math.sqrt(b1 / b2))


def effective_slab_width(c2: float, h: float) -> float:
    """C.13.5.3.2: ancho de la columna más 1.5h a cada lado."""
    return c2 + 3 * h


def punching_min_reinforcement(*, vuv: float, fc: float, lam: float, lam_s: float, alpha_s: float, fy: float, b0: float,
                               bslab: float) -> float | None:
    """NSR-10 no tiene acero mínimo adicional por cortante en dos direcciones (D-059)."""
    return None
