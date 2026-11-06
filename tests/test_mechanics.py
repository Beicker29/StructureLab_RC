import pytest
from hypothesis import given
from hypothesis import strategies as st

from structurelab_rc.mechanics.flexure import SteelLayer, compression_strips, flexure_state
from structurelab_rc.mechanics.materials import ConcreteBlock, SteelModel

CONCRETE = ConcreteBlock(28.0, 0.85, 0.85, 0.003)
STEEL = SteelModel(420.0, 200_000.0)
RECTANGLE = compression_strips(300.0, 600.0, 300.0, 300.0, flange_in_compression=True)


@given(
    tension=st.floats(200.0, 12_000.0),
    compression=st.floats(100.0, 4000.0),
    compression_depth=st.floats(30.0, 150.0),
)
def test_equilibrium_holds_for_rectangular_sections(tension: float, compression: float, compression_depth: float) -> None:
    layers = (SteelLayer(compression_depth, compression), SteelLayer(540.0, tension))
    state = flexure_state(RECTANGLE, layers, CONCRETE, STEEL)

    block = 0.85 * 28.0 * 300.0 * state.a
    steel_force = 0.0
    for layer, result in zip(layers, state.layers, strict=True):
        displaced = 0.85 * 28.0 if layer.depth < state.a else 0.0
        steel_force += layer.area * (result.stress + displaced)
    assert block == pytest.approx(steel_force, abs=1.0)
    assert state.nominal_moment > 0


def test_a_rectangle_is_a_t_section_with_equal_widths() -> None:
    layers = (SteelLayer(540.0, 3000.0),)
    t_shape = compression_strips(300.0, 600.0, 300.0, 100.0, flange_in_compression=False)
    assert flexure_state(t_shape, layers, CONCRETE, STEEL).c == pytest.approx(flexure_state(RECTANGLE, layers, CONCRETE, STEEL).c)


def test_steel_stress_is_limited_to_yield() -> None:
    state = flexure_state(RECTANGLE, (SteelLayer(540.0, 1000.0),), CONCRETE, STEEL)
    assert state.layers[0].stress == pytest.approx(420.0)
    assert state.extreme_strain > 420.0 / 200_000.0


def test_a_section_without_steel_is_rejected() -> None:
    with pytest.raises(ValueError, match="no tiene acero"):
        flexure_state(RECTANGLE, (), CONCRETE, STEEL)
