"""Deriva el oráculo de los anchos que propone el diseño de la combinada trapezoidal y escalonada (D-169):
tests/oracles/mechanics/plan_widths.json.

No importa el paquete. Para cada caso (largo L, centroide pedido x̄ desde el borde negativo, área A y, en la planta
escalonada, los límites entre tramos), los anchos de la planta son los que cumplen ∫dA = A y ∫x dA = A·x̄. Aquí se
plantean como un sistema lineal en los anchos con las integrales de cada pieza escritas a mano (el trapecio como dos
triángulos; cada tramo como un rectángulo) y se resuelve por la regla de Cramer, sin las fórmulas cerradas del
paquete. En la I, el tramo central tiene el ancho dado y los extremos salen del mismo sistema.

Uso: python tests/oracles/derive_plan_widths.py
"""

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).parent / "mechanics" / "plan_widths.json"


def _solve2(a: list[list[float]], b: list[float]) -> list[float]:
    det = a[0][0] * a[1][1] - a[0][1] * a[1][0]
    return [(b[0] * a[1][1] - a[0][1] * b[1]) / det, (a[0][0] * b[1] - b[0] * a[1][0]) / det]


def _trapezoid(length: float, xbar: float, area: float) -> list[float]:
    # Ancho lineal B(x) = B1·(1 − x/L) + B2·x/L: cada ancho aporta un triángulo de área L/2 con centroide en L/3 (B1) o
    # 2L/3 (B2).
    coefficients = [[length / 2, length / 2], [length / 2 * length / 3, length / 2 * 2 * length / 3]]
    return _solve2(coefficients, [area, area * xbar])


def _two_parts(length: float, xbar: float, area: float, split: float) -> list[float]:
    rest = length - split
    coefficients = [[split, rest], [split * split / 2, rest * (split + rest / 2)]]
    return _solve2(coefficients, [area, area * xbar])


def _three_parts(length: float, xbar: float, area: float, splits: tuple[float, float], middle: float) -> list[float]:
    s1, s2 = splits
    central = middle * (s2 - s1)
    coefficients = [[s1, length - s2], [s1 * s1 / 2, (length - s2) * (s2 + length) / 2]]
    first, last = _solve2(coefficients, [area - central, area * xbar - central * (s1 + s2) / 2])
    return [first, middle, last]


CASES: list[dict[str, Any]] = [
    {"id": "trapecio", "length": 6400.0, "xbar": 3450.0, "area": 11.2e6, "split": None, "need": 1300.0},
    {"id": "trapecio-inclinado", "length": 7000.0, "xbar": 4200.0, "area": 14.0e6, "split": None, "need": 1000.0},
    {"id": "dos-tramos", "length": 6500.0, "xbar": 3600.0, "area": 11.0e6, "split": [3000.0], "need": 1200.0},
    {"id": "dos-tramos-corto", "length": 6500.0, "xbar": 2900.0, "area": 10.5e6, "split": [1800.0], "need": 1200.0},
    {"id": "i", "length": 7000.0, "xbar": 3300.0, "area": 13.0e6, "split": [1500.0, 5300.0], "need": 1200.0},
]


def main() -> None:
    cases = []
    for case in CASES:
        split = case["split"]
        if split is None:
            widths = _trapezoid(case["length"], case["xbar"], case["area"])
        elif len(split) == 1:
            widths = _two_parts(case["length"], case["xbar"], case["area"], split[0])
        else:
            widths = _three_parts(case["length"], case["xbar"], case["area"], (split[0], split[1]), case["need"])
        cases.append({**case, "widths": widths})
    data = {"description": "Anchos de la planta trapezoidal o escalonada con el área y el centroide pedidos (D-169), por un "
                           "sistema lineal con las integrales de cada pieza.", "tolerance_rel": 1e-9, "cases": cases}
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
