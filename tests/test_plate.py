"""Wood-Armer (mechanics/plate, D-118): cada rama con valores calculados a mano."""

import pytest

from structurelab_rc.mechanics.plate import FaceMoments, wood_armer


@pytest.mark.parametrize(("moments", "bottom", "top"), [
    # Sin flexión: |mxy| en las cuatro.
    ((0.0, 0.0, 5.0), (5.0, 5.0), (-5.0, -5.0)),
    # Inferior directo; en la superior mx* = −10 + 3 > 0 → 0, my* = −4 + 9/10 = −3.1 → del lado contrario, 0.
    ((10.0, 4.0, 3.0), (13.0, 7.0), (0.0, 0.0)),
    # Inferior: my* = −8 + 3 < 0 → my* = 0, mx* = 10 + 9/8. Superior: mx* = 10 − 3 > 0 → 0, my* = −8 − 9/10.
    ((10.0, -8.0, 3.0), (11.125, 0.0), (0.0, -8.9)),
    # Superior: my* = 6 − 4 > 0 → my* = 0, mx* = −2 − 16/6.
    ((-2.0, 6.0, 4.0), (2.0, 10.0), (-2.0 - 16.0 / 6.0, 0.0)),
    # El signo de mxy no importa.
    ((10.0, 4.0, -3.0), (13.0, 7.0), (0.0, 0.0)),
    # Sin torsión, cada momento en su cara.
    ((7.0, -3.0, 0.0), (7.0, 0.0), (0.0, -3.0)),
])
def test_wood_armer_branches(moments: tuple[float, float, float], bottom: tuple[float, float], top: tuple[float, float]) -> None:
    result = wood_armer(*moments)
    assert result.bottom == FaceMoments(*(pytest.approx(value) for value in bottom))  # type: ignore[arg-type]
    assert result.top == FaceMoments(*(pytest.approx(value) for value in top))  # type: ignore[arg-type]
    assert result.bottom.x >= 0 and result.bottom.y >= 0 and result.top.x <= 0 and result.top.y <= 0
