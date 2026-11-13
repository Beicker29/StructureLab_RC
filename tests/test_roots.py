"""Búsqueda de raíz por Brent (D-124): raíces conocidas, funciones con quiebre y la misma raíz que la bisección."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from structurelab_rc.mechanics.roots import find_root


def _tolerance(x: float) -> float:
    return 1e-13 * abs(x)


def test_polynomial_root_in_few_evaluations() -> None:
    calls = []

    def f(x: float) -> float:
        calls.append(x)
        return x**3 - 2 * x - 5

    root = find_root(f, (2.0, 3.0), (f(2.0), f(3.0)), _tolerance)
    assert root == pytest.approx(2.0945514815423265, rel=1e-13)
    assert len(calls) < 15  # la bisección necesita ~45 para la misma tolerancia


def test_kinked_function_like_steel_yield() -> None:
    def f(x: float) -> float:
        return math.copysign(min(abs(x - 0.7) * 5, 1.0), x - 0.7)

    assert find_root(f, (0.0, 2.0), (f(0.0), f(2.0)), _tolerance) == pytest.approx(0.7, rel=1e-12)


def test_endpoint_roots_and_missing_sign_change() -> None:
    assert find_root(lambda x: x - 1, (1.0, 2.0), (0.0, 1.0), _tolerance) == 1.0
    with pytest.raises(ValueError, match="no encierran"):
        find_root(lambda x: x, (1.0, 2.0), (1.0, 2.0), _tolerance)


def _bisection(f, low: float, high: float) -> float:  # type: ignore[no-untyped-def]
    for _ in range(200):
        if high - low <= 1e-13 * high:
            break
        middle = (low + high) / 2
        low, high = (low, middle) if f(middle) >= 0 else (middle, high)
    return (low + high) / 2


@given(root=st.floats(0.01, 100.0), slope=st.floats(0.1, 50.0), cap=st.floats(0.5, 20.0))
def test_same_root_as_bisection(root: float, slope: float, cap: float) -> None:
    """Una función monótona con tramo plástico (como el equilibrio de la sección): Brent y bisección dan la misma raíz."""
    def f(x: float) -> float:
        return math.copysign(min(slope * abs(x - root), cap), x - root) + 1e-3 * (x - root)

    low, high = root / 3, root * 3
    brent = find_root(f, (low, high), (f(low), f(high)), _tolerance)
    assert brent == pytest.approx(_bisection(f, low, high), rel=1e-11)
