"""Presión del suelo bajo plantas poligonales (D-164): las ecuaciones de Bellos y Bakas resueltas sobre el polígono,
frente al oráculo independiente y frente a la solución cerrada de Bellos en el rectángulo."""

import json
import random
from pathlib import Path

import pytest

from structurelab_rc.mechanics.materials import NoEquilibrium
from structurelab_rc.mechanics.soil_pressure import footing_pressure, polygon_pressure

ORACLE = json.loads((Path(__file__).parent / "oracles" / "mechanics" / "polygon_pressure.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", ORACLE["cases"], ids=[case["id"] for case in ORACLE["cases"]])
def test_polygon_pressure_matches_oracle(case: dict) -> None:
    outline = tuple((x, y) for x, y in case["outline"])
    pressure = polygon_pressure(outline, case["load_N"], case["ex"], case["ey"])
    peak = max(case["vertex_pressures"])
    tolerance = ORACLE["tolerance_rel"]
    for got, wanted in zip(pressure.vertices(), case["vertex_pressures"], strict=True):
        assert got == pytest.approx(wanted, rel=tolerance, abs=tolerance * peak)
    assert pressure.pmax == pytest.approx(peak, rel=tolerance)
    assert pressure.contact_fraction() == pytest.approx(case["contact_fraction"], rel=tolerance)
    assert pressure.region == ("parcial" if case["partial"] else "total")
    force, sx, sy = pressure.resultant(outline)
    assert (force, sx, sy) == pytest.approx((case["load_N"], case["load_N"] * case["ex"], case["load_N"] * case["ey"]), rel=1e-9,
                                       abs=1e-9 * case["load_N"] * 1000.0)


def test_polygon_pressure_on_a_rectangle_is_bellos() -> None:
    """En un rectángulo, la solución sobre el polígono es la cerrada de Bellos en las cinco regiones."""
    lx, ly, load = 3000.0, 2000.0, 1.5e6
    rectangle = ((-lx / 2, -ly / 2), (lx / 2, -ly / 2), (lx / 2, ly / 2), (-lx / 2, ly / 2))
    rng = random.Random(7)
    regions = set()
    for _ in range(400):
        ex, ey = rng.uniform(-0.49, 0.49) * lx, rng.uniform(-0.49, 0.49) * ly
        closed = footing_pressure(lx, ly, load, ex, ey)
        regions.add(closed.region)
        general = polygon_pressure(rectangle, load, ex, ey)
        assert general.vertices() == pytest.approx(closed.corners(), rel=1e-9, abs=1e-9 * closed.pmax)
    assert regions == {"A", "B", "C", "D", "E"}


def test_resultant_outside_the_hull_has_no_equilibrium() -> None:
    """La resultante fuera de la envolvente convexa de la planta no tiene equilibrio sin tracción."""
    l_shape = ((-3500.0, -1400.0), (3000.0, -1400.0), (3000.0, 200.0), (0.0, 200.0), (0.0, 1400.0), (-3500.0, 1400.0))
    with pytest.raises(NoEquilibrium):
        polygon_pressure(l_shape, 1e6, 3500.0, 0.0)
    with pytest.raises(NoEquilibrium):
        polygon_pressure(l_shape, -1e6, 0.0, 0.0)
