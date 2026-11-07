import json
import math
from pathlib import Path
from typing import Any

import pytest

from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import footing_pressure

ORACLE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "oracles" / "mechanics" / "soil_pressure.json").read_text(encoding="utf-8")
)
LX, LY, LOAD = ORACLE["lx"], ORACLE["ly"], ORACLE["load"]
PM = LOAD / (LX * LY)


def _curved_side(t: float) -> float:
    """Borde curvo de las regiones D y E (Bellos, Ecs. 24 y 27)."""
    s = math.sqrt(1 - 12 * t * t)
    return 0.5 - (2 - s) * (1 + 2 * t + s) / (6 * (1 + 4 * t))


@pytest.mark.parametrize("case", ORACLE["cases"], ids=lambda case: case["id"])
def test_pressure_matches_oracle(case: dict[str, Any]) -> None:
    pressure = footing_pressure(LX, LY, LOAD, case["ex"], case["ey"])

    assert pressure.region == case["region"]
    tolerance = ORACLE["tolerance_rel"]
    for got, expected in zip(pressure.corners(), case["corners"], strict=True):
        assert got == pytest.approx(expected, rel=tolerance, abs=tolerance * PM)
    assert pressure.contact_fraction() == pytest.approx(case["contact_fraction"], rel=tolerance)


@pytest.mark.parametrize("case", ORACLE["cases"], ids=lambda case: case["id"])
def test_pressure_is_in_equilibrium(case: dict[str, Any]) -> None:
    pressure = footing_pressure(LX, LY, LOAD, case["ex"], case["ey"])

    force, moment_x, moment_y = pressure.resultant(pressure.base())

    assert force == pytest.approx(LOAD, rel=1e-10)
    assert moment_x == pytest.approx(LOAD * case["ex"], rel=1e-9, abs=1e-9 * LOAD * LX)
    assert moment_y == pytest.approx(LOAD * case["ey"], rel=1e-9, abs=1e-9 * LOAD * LY)


@pytest.mark.parametrize(
    ("u", "v"),
    [(0.1, 1 / 6 - 0.1), (0.25, 0.3), (0.3, 0.25), (0.1, _curved_side(0.1)), (_curved_side(0.1), 0.1), (0.0, 1 / 6), (0.25, 0.25)],
    ids=["C-B", "A-D", "A-E", "D-B", "E-B", "C-D", "A-B-D-E"],
)
def test_pressure_is_continuous_across_regions(u: float, v: float) -> None:
    """Bellos: en los bordes, las regiones vecinas dan la misma presión (casos frontera 3 a 7)."""
    step = 1e-7
    below = footing_pressure(LX, LY, LOAD, (u - step) * LX, (v - step) * LY) if u > step else None
    above = footing_pressure(LX, LY, LOAD, (u + step) * LX, (v + step) * LY)
    here = footing_pressure(LX, LY, LOAD, u * LX, v * LY)
    for other in (below, above):
        if other is not None:
            assert other.pmax == pytest.approx(here.pmax, rel=1e-5)


def test_resultant_on_half_base() -> None:
    """Con P centrada, cada mitad de la base recibe P/2 con su centroide a lx/4."""
    pressure = footing_pressure(LX, LY, LOAD, 0.0, 0.0)
    half = ((0.0, -LY / 2), (LX / 2, -LY / 2), (LX / 2, LY / 2), (0.0, LY / 2))

    force, moment_x, moment_y = pressure.resultant(half)

    assert pressure.region == "C"
    assert force == pytest.approx(LOAD / 2)
    assert moment_x / force == pytest.approx(LX / 4)
    assert moment_y == pytest.approx(0.0, abs=1e-6 * LOAD)


def test_resultant_ignores_area_without_contact() -> None:
    pressure = footing_pressure(LX, LY, LOAD, LX / 4, LY / 4)  # caso 4: contacto solo bajo la diagonal
    far_corner = ((-LX / 2, -LY / 2), (-LX / 4, -LY / 2), (-LX / 4, -LY / 4), (-LX / 2, -LY / 4))

    assert pressure.resultant(far_corner) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(("load", "ex", "ey"), [(LOAD, LX / 2, 0.0), (LOAD, 0.0, -LY / 2), (0.0, 0.0, 0.0), (-LOAD, 0.0, 0.0)])
def test_no_equilibrium(load: float, ex: float, ey: float) -> None:
    with pytest.raises(NoEquilibrium):
        footing_pressure(LX, LY, load, ex, ey)
