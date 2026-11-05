"""Conversión de unidades internas (N, mm) a unidades de presentación."""


def kN(force: float) -> float:
    return force / 1e3


def kNm(moment: float) -> float:
    return moment / 1e6


def display(value: float | None, unit: str) -> str:
    if value is None:
        return "-"
    if unit == "N*mm":
        return f"{kNm(value):.1f} kN-m"
    if unit == "N":
        return f"{kN(value):.1f} kN"
    if unit == "mm2":
        return f"{value:.0f} mm2"
    return f"{value:.5f}"
