"""Empuje del relleno sobre el muro (D-173, decisión 9): ecuaciones de Das 2016 (Rankine, Chu y Coulomb), el plano
según el talón y las verificaciones no válidas (BLOCKED)."""

import math
from typing import Any

import pytest
from wall_inputs import internal_soil, wall

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.retaining_wall.checks import PENDING, THRUST, retaining_wall_checks
from structurelab_rc.domain.retaining_wall.thrust import (
    COHESIVE,
    COHESIVE_COULOMB,
    LONG,
    NO_HEEL,
    SHORT,
    SLOPED_AT_REST,
    STEEP,
    Backfill,
    stability_thrust,
    stem_thrust,
    thrust_plane,
)
from structurelab_rc.domain.status import Status
from structurelab_rc.mechanics.earth_pressure import (
    chu_active_coefficient,
    chu_inclination,
    coulomb_active_coefficient,
    jaky_at_rest_coefficient,
    mayne_kulhawy_at_rest_coefficient,
    rankine_active_coefficient,
    rankine_wedge_angle,
)
from structurelab_rc.model.retaining_wall import EarthPressure, RetainingSoil, RetainingWall

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


@pytest.mark.parametrize(("alpha", "theta", "phi", "ka", "beta"), [(0, 10, 30, 0.377, 17.878), (10, 8, 34, 0.363, 24.999),
                                                                (20, 15, 40, 0.488, 39.491), (5, 0, 32, 0.311, 5.000),
                                                                (15, 4, 28, 0.448, 19.840)])
def test_chu_matches_tables_12_1_and_12_2_of_das(alpha: float, theta: float, phi: float, ka: float, beta: float) -> None:
    """Ka (ec. 12.17, tabla 12.1) y β'_a (ec. 12.15, tabla 12.2) de Das 2016."""
    assert chu_active_coefficient(r(phi), r(alpha), r(theta)) == pytest.approx(ka, abs=5e-4)
    assert math.degrees(chu_inclination(r(phi), r(alpha), r(theta))) == pytest.approx(beta, abs=5e-4)


@pytest.mark.parametrize(("alpha", "ph", "pv", "beta"), [(0, 60.75, 60.75, 26.57), (10, 70.32, 76.72, 29.06),
                                                         (20, 89.19, 100.58, 30.00)])
def test_chu_on_ac_matches_the_specification(alpha: float, ph: float, pv: float, beta: float) -> None:
    """φ' = 30°, γ = 18 kN/m³, talón de 1.5 m y AC de 4.5 m de altura: P_h, P_v en AC y β'_a."""
    theta_v = math.atan(1500.0 / 4500.0)  # con α = 20° cae justo en θ_v = η, donde AC y AB coinciden
    inclination = chu_inclination(r(30), r(alpha), theta_v)
    assert math.degrees(inclination) == pytest.approx(beta, abs=0.005)
    force = 0.5 * chu_active_coefficient(r(30), r(alpha), theta_v) * 18e-6 * 4500.0**2
    angle = theta_v + inclination  # θ_v + β'_a respecto a la horizontal
    assert (force * math.cos(angle), force * math.sin(angle)) == (pytest.approx(ph, abs=0.005), pytest.approx(pv, abs=0.005))


def test_chu_on_ac_equals_rankine_on_ab_with_the_triangle() -> None:
    """Con α = 0: P_h igual y P_v(AC) = P_v(AB) + W(ABC) = 0 + γ·½·1.5·4.5 = 60.75 kN/m."""
    thrust = stability_thrust(*_example(1500.0))
    assert (thrust.plane.heel, thrust.plane.name) == (SHORT, "AC") and not thrust.blocked
    assert thrust.horizontal == pytest.approx(0.5 * (1 / 3) * 18e-6 * 4500.0**2)
    assert thrust.vertical == pytest.approx(18e-6 * 0.5 * 1500.0 * 4500.0)
    assert thrust.inside_weight == pytest.approx(thrust.vertical)  # el triángulo ABC, que P_a contiene


def test_coulomb_with_a_short_heel_takes_ac_with_phi() -> None:
    """Talón corto con Coulomb: AC con β = 90° − θ_v y δ = φ' (el ejemplo de la especificación: φ' = 30°, γ = 18 kN/m³,
    pantalla de 4.0 m, base de 0.5 m, talón de 1.5 m)."""
    thrust = stability_thrust(*_example(1500.0, earth_pressure=COULOMB))
    plane = thrust.plane
    assert (plane.heel, plane.name) == (SHORT, "AC") and not thrust.blocked
    assert (plane.eta, plane.theta_v, plane.beta, plane.delta) == (
        pytest.approx(r(30.0)), pytest.approx(r(18.43), abs=r(0.005)), pytest.approx(r(71.57), abs=r(0.005)),
        pytest.approx(r(30.0)))
    assert thrust.coefficient == pytest.approx(0.4803, abs=5e-5)
    assert (thrust.force, thrust.horizontal, thrust.vertical) == (
        pytest.approx(87.53, abs=0.005), pytest.approx(58.07, abs=0.005), pytest.approx(65.49, abs=0.005))
    edge = 1500.0 * 4000.0 / 4500.0  # donde AC corta la cara superior del talón
    wedge, sliver = 0.5 * edge * 4000.0, 0.5 * 500.0 * (1500.0 - edge)  # la cuña de suelo y la de concreto
    assert thrust.soil_weight == pytest.approx(18e-6 * (wedge - sliver)) and thrust.inside_weight == 0.0


def test_long_heel_with_coulomb_is_ab_and_equals_rankine() -> None:
    long_heel = 4500.0 * math.tan(r(30.0))  # 2.598 m: desde aquí θ_v ≥ η
    coulomb = stability_thrust(*_example(long_heel + 1.0, earth_pressure=COULOMB))
    rankine = stability_thrust(*_example(long_heel + 1.0))
    assert (coulomb.plane.heel, coulomb.plane.name, coulomb.plane.beta) == (LONG, "AB", pytest.approx(r(90)))
    assert rankine.plane.name == "AB" and not rankine.blocked
    assert (coulomb.coefficient, coulomb.force, coulomb.horizontal) == pytest.approx(
        (rankine.coefficient, rankine.force, rankine.horizontal))
    assert stability_thrust(*_example(long_heel - 1.0, earth_pressure=COULOMB)).plane.name == "AC"


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
    assert flat.plane.name == "AB" and flat.coefficient == pytest.approx(0.5) and flat.vertical == pytest.approx(0.0)


def test_the_stem_takes_coulomb_with_the_declared_wall_friction() -> None:
    own, granular = _example(1500.0, earth_pressure=COULOMB)
    thrust = stem_thrust(own, granular)
    assert thrust.plane.delta == pytest.approx(r(20.0)) and thrust.plane.height == pytest.approx(4000.0)
    assert thrust.coefficient == pytest.approx(coulomb_active_coefficient(r(90), r(30), r(20), 0.0))


def test_eta_of_equation_13_1() -> None:
    assert rankine_wedge_angle(r(30), 0.0) == pytest.approx(r(30))


_COULOMB_PRESSURE = EarthPressure.model_validate(COULOMB)


@pytest.mark.parametrize(("beta", "expected"), [(90, 0.2973), (85, 0.3349), (80, 0.3769), (75, 0.4245), (70, 0.4794)])
def test_a_gravity_wall_without_heel_takes_coulomb_on_its_face(beta: float, expected: float) -> None:
    """Sin talón, el plano es la cara real con el δ' declarado (Das fig. 13.4c): la tabla 12.6 (φ' = 30°, δ' = 20°)."""
    plane = thrust_plane(Backfill(0.0, 4000.0, 4000.0, r(beta)), _COULOMB_PRESSURE, r(30), 0.0)
    assert (plane.heel, plane.name, plane.soil_area) == (NO_HEEL, "cara", 0.0)
    assert (plane.beta, plane.delta) == pytest.approx((r(beta), r(20)))
    assert coulomb_active_coefficient(plane.beta, r(30), plane.delta, 0.0) == pytest.approx(expected, abs=5e-5)


@pytest.mark.parametrize(("projection", "expected"), [(1500.0, ("AC", SHORT)), (3000.0, ("AB", LONG))])
def test_a_gravity_wall_with_a_heel_never_takes_its_face(projection: float, expected: tuple[str, str]) -> None:
    """Con Coulomb y talón, el plano es AC (δ = φ') o AB (δ = α) según θ_v y η, nunca la cara (aunque esté inclinada)."""
    plane = thrust_plane(Backfill(projection, 4500.0, 4000.0, r(80)), _COULOMB_PRESSURE, r(30), 0.0)
    assert (plane.name, plane.heel) == expected
    assert plane.delta == pytest.approx(r(30) if plane.name == "AC" else 0.0)


def test_gravity_and_cantilever_with_the_same_heel_take_the_same_plane() -> None:
    """La misma geometría de talón y relleno da el mismo plano, δ y P_a en gravedad y en voladizo."""
    for heel in (1500.0, 3000.0):
        own, granular = _example(heel, earth_pressure=COULOMB)
        cantilever = stability_thrust(own, granular)
        gravity = thrust_plane(Backfill(heel, 4500.0, 4000.0), _COULOMB_PRESSURE, r(30), 0.0)
        assert (cantilever.plane.name, cantilever.plane.beta, cantilever.plane.delta) == (
            gravity.name, pytest.approx(gravity.beta), pytest.approx(gravity.delta))
        coefficient = coulomb_active_coefficient(gravity.beta, r(30), gravity.delta, 0.0)
        assert cantilever.force == pytest.approx(0.5 * coefficient * 18e-6 * gravity.height**2)


def test_a_wall_is_never_pass_before_it_is_verified() -> None:
    """Mientras la fase A está en construcción, la última verificación queda BLOCKED; con la fórmula que no vale, el
    empuje lo dice."""
    own, granular = _example(1500.0)
    checks = retaining_wall_checks(PROFILES["aci-318-25"], own, granular)
    assert checks[-1].name == PENDING and checks[-1].status is Status.BLOCKED and THRUST not in [check.name for check in checks]
    cohesive = retaining_wall_checks(PROFILES["aci-318-25"], own, granular.model_copy(update={"cohesion": 0.01}))
    assert [check.name for check in cohesive] == [THRUST, PENDING] and cohesive[0].errors[0].message == COHESIVE
