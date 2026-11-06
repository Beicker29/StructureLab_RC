import math

import pytest

from structurelab_rc.mechanics.flexure import SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel
from structurelab_rc.mechanics.section import SteelPoint, area_centroid, biaxial_state, section_state

CONCRETE = ConcreteBlock(28.0, 0.85, 0.85, 0.003)
STEEL = SteelModel(420.0, 200_000.0)
MATERIALS = (CONCRETE, STEEL)
SQUARE = ((0.0, 0.0), (400.0, 0.0), (400.0, 400.0), (0.0, 400.0))
# Cuatro barras #8 (510 mm²) a 60 mm de cada cara.
CORNERS = tuple(SteelPoint(x, y, 510.0) for x in (60.0, 340.0) for y in (60.0, 340.0))


def test_polygon_area_and_centroid() -> None:
    t_shape = ((0.0, 0.0), (300.0, 0.0), (300.0, 400.0), (650.0, 400.0), (650.0, 500.0), (-350.0, 500.0), (-350.0, 400.0), (0.0, 400.0))
    area, cx, cy = area_centroid(t_shape)
    assert area == pytest.approx(300.0 * 500.0 + 700.0 * 100.0)
    assert cx == pytest.approx(150.0)
    assert cy == pytest.approx((300.0 * 500.0 * 250.0 + 700.0 * 100.0 * 450.0) / area)


def test_horizontal_neutral_axis_matches_the_strip_solution() -> None:
    bars = (SteelPoint(60.0, 440.0, 600.0), SteelPoint(240.0, 440.0, 600.0), SteelPoint(150.0, 60.0, 1530.0))
    polygon = ((0.0, 0.0), (300.0, 0.0), (300.0, 500.0), (0.0, 500.0))
    state = section_state(polygon, bars, MATERIALS, 150e3, math.pi / 2)
    strips = compression_strips(300.0, 500.0, 300.0, 250.0, flange_in_compression=True)
    reference = flexure_state(strips, (SteelLayer(60.0, 1200.0), SteelLayer(440.0, 1530.0)), CONCRETE, STEEL, 150e3)
    assert state.c == pytest.approx(reference.c)
    assert state.mn3 == pytest.approx(reference.nominal_moment)
    assert state.mn2 == pytest.approx(0.0, abs=1e-3)


def test_triangular_block_at_45_degrees_matches_hand_values() -> None:
    # Una barra de 300 mm² en la esquina (340, 60); el bloque es un triángulo isósceles en la esquina (0, 400).
    bar = (SteelPoint(340.0, 60.0, 300.0),)
    theta = math.radians(135.0)
    state = section_state(SQUARE, bar, MATERIALS, 0.0, theta)
    # Equilibrio con la barra en fluencia: 0.85·f'c·a² = As·fy, porque el triángulo de altura a tiene área a².
    a = math.sqrt(300.0 * 420.0 / (0.85 * 28.0))
    assert state.a == pytest.approx(a, rel=1e-9)
    # El centroide del triángulo está a 2a/3 del vértice (0, 400), sobre la dirección (−1, 1)/√2.
    offset = 2 * a / 3 / math.sqrt(2)
    block = 0.85 * 28.0 * a**2
    expected_mn3 = block * (400.0 - offset - 200.0) + 300.0 * 420.0 * (200.0 - 60.0)
    expected_mn2 = block * (offset - 200.0) - 300.0 * 420.0 * (340.0 - 200.0)
    assert state.mn3 == pytest.approx(expected_mn3, rel=1e-9)
    assert state.mn2 == pytest.approx(expected_mn2, rel=1e-9)


def test_a_square_section_gives_the_same_capacity_about_both_axes() -> None:
    strong = section_state(SQUARE, CORNERS, MATERIALS, 100e3, math.pi / 2)
    weak = section_state(SQUARE, CORNERS, MATERIALS, 100e3, 0.0)
    assert strong.mn3 == pytest.approx(weak.mn2)
    assert strong.c == pytest.approx(weak.c)


def test_rotating_a_rectangle_swaps_the_axes() -> None:
    upright = ((0.0, 0.0), (300.0, 0.0), (300.0, 500.0), (0.0, 500.0))
    lying = ((0.0, 0.0), (500.0, 0.0), (500.0, 300.0), (0.0, 300.0))
    bars = (SteelPoint(60.0, 60.0, 510.0), SteelPoint(240.0, 60.0, 510.0), SteelPoint(60.0, 440.0, 284.0), SteelPoint(240.0, 440.0, 284.0))
    turned = tuple(SteelPoint(bar.y, 300.0 - bar.x, bar.area) for bar in bars)
    about_3 = section_state(upright, bars, MATERIALS, 0.0, -math.pi / 2)
    about_2 = section_state(lying, turned, MATERIALS, 0.0, math.pi)
    assert abs(about_3.mn3) == pytest.approx(abs(about_2.mn2))


def test_biaxial_state_points_its_moment_along_the_demand() -> None:
    for demand in ((100e6, 60e6), (-80e6, 30e6), (0.0, -50e6), (120e6, 0.0)):
        state = biaxial_state(SQUARE, CORNERS, MATERIALS, 50e3, demand)
        assert math.atan2(state.mn2, state.mn3) == pytest.approx(math.atan2(demand[1], demand[0]), abs=1e-9)


def test_symmetric_demand_on_a_square_uses_a_45_degree_neutral_axis() -> None:
    state = biaxial_state(SQUARE, CORNERS, MATERIALS, 0.0, (70e6, 70e6))
    assert math.degrees(state.theta) % 360 == pytest.approx(45.0, abs=1e-6)
