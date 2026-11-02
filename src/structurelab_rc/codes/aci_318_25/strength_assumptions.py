"""Suposiciones de diseño para resistencia según ACI CODE-318-25 (22.2.2 y 20.2.2)."""

_FC_MIN = 17.0
_FC_UPPER_PLATEAU = 28.0
_FC_LOWER_PLATEAU = 55.0


def max_concrete_strain() -> float:
    """22.2.2.1."""
    return 0.003


def stress_block_factor() -> float:
    """22.2.2.4.1."""
    return 0.85


def beta1(fc: float) -> float | None:
    """Tabla 22.2.2.4.3, fc en MPa; None por debajo de 17 MPa, donde la tabla no define valor."""
    if fc < _FC_MIN:
        return None
    if fc <= _FC_UPPER_PLATEAU:
        return 0.85
    if fc >= _FC_LOWER_PLATEAU:
        return 0.65
    return 0.85 - 0.05 * (fc - 28.0) / 7.0


def steel_modulus() -> float:
    """20.2.2.2, en MPa."""
    return 200_000.0
