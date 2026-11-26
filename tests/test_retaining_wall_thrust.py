"""Empuje del relleno sobre el muro en voladizo (D-173, decisión 9): ecuaciones de Das 2016, clasificación del talón,
δ' según el plano y verificaciones no válidas (BLOCKED)."""

import math
from typing import Any

import pytest
from wall_inputs import internal_soil, wall

from structurelab_rc.domain.retaining_wall.checks import PENDING, THRUST, retaining_wall_checks
from structurelab_rc.domain.retaining_wall.thrust import (
    COHESIVE,
    COHESIVE_COULOMB,
    SHORT_HEEL,
    SLOPED_AT_REST,
    STEEP,
    stability_thrust,
    stem_thrust,
)
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.earth_pressure import (
    coulomb_active_coefficient,
    jaky_at_rest_coefficient,
    mayne_kulhawy_at_rest_coefficient,
    rankine_active_coefficient,
    rankine_wedge_angle,
)
from structurelab_rc.model.retaining_wall import RetainingSoil, RetainingWall

r = math.radians
N_MM_PER_KN_M = 1.0  # 1 kN/m = 1 N/mm
COULOMB = {"state": "active", "method": "coulomb", "wall_friction_angle": 20.0}


@pytest.mark.parametrize(("beta", "alpha", "expected"), [(90, 0, 0.2973), (85, 0, 0.3349), (80, 0, 0.3769), (75, 0, 0.4245),
                                                         (70, 0, 0.4794), (80, 10, 0.4376)])
def test_coulomb_matches_table_12_6_of_das(beta: float, alpha: float, expected: float) -> None:
    """Tabla 12.6 de Das 2016 (φ' = 30°, δ' = 20°)."""
    assert coulomb_active_coefficient(r(beta), r(30), r(20), r(alpha)) == pytest.approx(expected, abs=5e-5)


def test_coulomb_on_a_vertical_frictionless_plane_is_rankine() -> None:
    assert coulomb_active_coefficient(r(90), r(30), 0.0, 0.0) == pytest.approx(math.tan(r(45 - 15)) ** 2)


@pytest.mark.parametrize(("alpha", "expected"), [(0, 0.3333), (10, 0.3495), (20, 0.4142), (25, 0.4936)])
def test_coulomb_with_beta_90_and_delta_alpha_is_rankine(alpha: float, expected: float) -> None:
    """Caso 4a: con β = 90° y δ' = α, la ec. 12.26 se reduce a Rankine con relleno inclinado (φ' = 30°)."""
    coulomb = coulomb_active_coefficient(r(90), r(30), r(alpha), r(alpha))
    assert coulomb == pytest.approx(expected, abs=5e-5)
    assert coulomb == pytest.approx(rankine_active_coefficient(r(30), r(alpha)), rel=1e-12)


def test_at_rest_coefficients() -> None:
    assert jaky_at_rest_coefficient(r(30)) == pytest.approx(0.5)
    assert mayne_kulhawy_at_rest_coefficient(r(30), 4.0) == pytest.approx(0.5 * 4.0**0.5)


def _example(heel: float, **change: Any) -> tuple[RetainingWall, RetainingSoil]:
    """El ejemplo de la especificación: φ' = 30°, α = 0, γ = 18 kN/m³, pantalla vertical de 4.0 m, base de 0.5 m."""
    own = RetainingWall.model_validate(wall(stem_height=4000.0, backfill_height=4000.0, base_thickness=500.0, heel=heel,
                                            stem_thickness=300.0, toe=600.0, **change))
    return own, RetainingSoil.model_validate(internal_soil(friction_angle=30.0, unit_weight_backfill=18.0, cohesion=0.0))


def test_short_heel_with_coulomb_is_case_4b() -> None:
    thrust = stability_thrust(*_example(1500.0, earth_pressure=COULOMB))
    assert thrust.case == "4b" and thrust.plane == "AC" and not thrust.blocked
    assert thrust.eta == pytest.approx(r(30.0))
    assert thrust.theta_v == pytest.approx(r(18.43), abs=r(0.005))
    assert thrust.beta == pytest.approx(r(71.57), abs=r(0.005))
    assert thrust.delta == pytest.approx(r(30.0))  # δ' = φ', rotura suelo contra suelo
    assert thrust.coefficient == pytest.approx(0.4803, abs=5e-5)
    assert thrust.force == pytest.approx(87.53 * N_MM_PER_KN_M, abs=0.005)
    assert thrust.horizontal == pytest.approx(58.07 * N_MM_PER_KN_M, abs=0.005)
    assert thrust.vertical == pytest.approx(65.49 * N_MM_PER_KN_M, abs=0.005)


def test_long_heel_with_coulomb_is_case_4a_and_equals_rankine() -> None:
    long_heel = 4500.0 * math.tan(r(30.0))  # 2.598 m: desde aquí θ_v ≥ η
    coulomb = stability_thrust(*_example(long_heel + 1.0, earth_pressure=COULOMB))
    rankine = stability_thrust(*_example(long_heel + 1.0))
    assert coulomb.case == "4a" and coulomb.plane == "AB" and coulomb.beta == pytest.approx(r(90))
    assert rankine.case == "1" and not rankine.blocked
    assert (coulomb.coefficient, coulomb.force, coulomb.horizontal) == pytest.approx(
        (rankine.coefficient, rankine.force, rankine.horizontal))
    assert stability_thrust(*_example(long_heel - 1.0, earth_pressure=COULOMB)).case == "4b"


def test_rankine_with_a_short_heel_is_blocked() -> None:
    thrust = stability_thrust(*_example(1500.0))
    assert thrust.case == "1" and thrust.blocked == SHORT_HEEL and thrust.force == 0.0


def test_coulomb_with_cohesion_and_rankine_with_cohesion_are_blocked() -> None:
    own, granular = _example(3000.0, earth_pressure=COULOMB)
    cohesive = granular.model_copy(update={"cohesion": 0.01})
    assert stability_thrust(own, cohesive).blocked == COHESIVE_COULOMB
    rankine, _ = _example(3000.0)
    assert stability_thrust(rankine, cohesive).blocked == COHESIVE


def test_a_backfill_steeper_than_phi_and_a_sloped_at_rest_backfill_are_blocked() -> None:
    own, granular = _example(3000.0)
    assert stability_thrust(own, granular, alpha=r(31.0)).blocked == STEEP
    at_rest, _ = _example(3000.0, earth_pressure={"state": "at_rest", "method": "jaky"})
    assert stability_thrust(at_rest, granular, alpha=r(10.0)).blocked == SLOPED_AT_REST
    flat = stability_thrust(at_rest, granular)
    assert flat.case == "reposo" and flat.coefficient == pytest.approx(0.5) and flat.vertical == pytest.approx(0.0)


def test_the_stem_takes_coulomb_with_the_declared_wall_friction() -> None:
    own, granular = _example(1500.0, earth_pressure=COULOMB)
    thrust = stem_thrust(own, granular)
    assert thrust.delta == pytest.approx(r(20.0)) and thrust.height == pytest.approx(4000.0)
    assert thrust.coefficient == pytest.approx(coulomb_active_coefficient(r(90), r(30), r(20), 0.0))


def test_eta_of_equation_13_1() -> None:
    assert rankine_wedge_angle(r(30), 0.0) == pytest.approx(r(30))


def test_a_wall_is_never_pass_before_it_is_verified() -> None:
    """Mientras la fase A está en construcción, el muro queda BLOCKED; con la teoría que no vale, lo dice."""
    own, granular = _example(3000.0)
    assert [check.name for check in retaining_wall_checks(own, granular)] == [PENDING]
    checks = retaining_wall_checks(*_example(1500.0))
    assert [check.name for check in checks] == [THRUST, PENDING]
    assert all(check.status is Status.BLOCKED for check in checks) and checks[0].errors[0].message == SHORT_HEEL
