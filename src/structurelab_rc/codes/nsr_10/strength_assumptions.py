"""Suposiciones de diseño para resistencia según NSR-10 Título C (C.10.2, C.8.5 y C.8.6)."""

_FC_MIN = 17.0
_FC_UPPER_PLATEAU = 28.0


def max_concrete_strain() -> float:
    """C.10.2.3."""
    return 0.003


def stress_block_factor() -> float:
    """C.10.2.7.1."""
    return 0.85


def beta1(fc: float) -> float | None:
    """C.10.2.7.3, fc en MPa; None por debajo de 17 MPa, donde el numeral no define valor."""
    if fc < _FC_MIN:
        return None
    if fc <= _FC_UPPER_PLATEAU:
        return 0.85
    return max(0.85 - 0.05 * (fc - 28.0) / 7.0, 0.65)


def steel_modulus() -> float:
    """C.8.5.2, en MPa."""
    return 200_000.0


def concrete_lambda(concrete: str) -> float | None:
    """C.8.6.1: λ = 1.0 para concreto de peso normal; el concreto liviano no está implementado (D-028)."""
    return 1.0 if concrete == "normalweight" else None
