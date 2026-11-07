"""Conversión de unidades internas (N, mm) a unidades de presentación."""


def kN(force: float) -> float:
    return force / 1e3


def kNm(moment: float) -> float:
    return moment / 1e6


def kPa(pressure: float) -> float:
    """Presión interna en MPa (N/mm²) a kPa."""
    return pressure * 1e3


def display(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    if unit == "N*mm":
        return f"{kNm(value):.1f} kN-m"
    if unit == "N":
        return f"{kN(value):.1f} kN"
    if unit == "N/mm2":
        return f"{kPa(value):.1f} kPa"
    decimals = {"mm2": 0, "mm": 0, "mm2/mm": 3, "MPa": 2}.get(unit)
    return f"{value:.5f}" if decimals is None else f"{value:.{decimals}f} {unit}"
