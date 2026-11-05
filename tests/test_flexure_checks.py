from typing import Any

import pytest

from structurelab_rc.codes.registry import PROFILES
from structurelab_rc.domain.beam.flexure import MIN_REINFORCEMENT, NET_TENSILE_STRAIN, STRENGTH
from structurelab_rc.domain.beam.station import SCOPE, station_checks
from structurelab_rc.domain.check import Check
from structurelab_rc.domain.status import Status
from structurelab_rc.model.project import Materials, Member
from structurelab_rc.setup import load_engine

BARS = load_engine().bars
MATERIALS = Materials(fc=28.0, fy=420.0, fyt=420.0, concrete="normalweight")


def _member(layers: list[dict[str, Any]], demands: dict[str, float], **changes: Any) -> Member:
    data: dict[str, Any] = {
        "id": "V",
        "type": "beam",
        "length": 6000.0,
        "section": {"bw": 300.0, "h": 500.0, "cover": 40.0},
        "stations": [{"x": 0.0, "layout": {"layers": layers, "stirrups": None}, "demands": demands}],
    }
    return Member.model_validate(data | changes)


def _checks(member: Member, profile: str = "nsr-10") -> dict[str, Check]:
    """Verificaciones de alcance y flexión de la única estación; el cortante se prueba en test_shear_checks.py."""
    checks = station_checks(PROFILES[profile], MATERIALS, member, member.stations[0], BARS)
    return {check.name: check for check in checks if not check.name.startswith("Cortante")}


BOTTOM = [{"designation": "#8", "count": 3, "depth": 440.0, "role": "flexure"}]


def test_a_well_reinforced_beam_passes_every_check() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 180.0}))
    assert {name: check.status for name, check in checks.items()} == {
        STRENGTH: Status.PASS,
        NET_TENSILE_STRAIN: Status.PASS,
        MIN_REINFORCEMENT: Status.PASS,
    }
    phi = dict(checks[STRENGTH].values)["phi"]
    assert checks[STRENGTH].capacity == pytest.approx(phi * dict(checks[STRENGTH].values)["Mn"])
    assert checks[STRENGTH].member == "V"
    assert checks[STRENGTH].x == 0.0


def test_insufficient_strength_fails() -> None:
    assert _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 300.0}))[STRENGTH].status is Status.FAIL


def test_axial_compression_at_the_limit_is_blocked_as_not_a_beam() -> None:
    limit_kn = 0.10 * 28.0 * 300.0 * 500.0 / 1e3
    checks = _checks(_member(BOTTOM, {"Pu_kN": limit_kn, "Mu_kNm": 100.0}))
    assert list(checks) == [SCOPE]
    assert checks[SCOPE].status is Status.BLOCKED


def test_axial_tension_is_carried_in_equilibrium() -> None:
    no_axial = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 100.0}))[STRENGTH]
    tension = _checks(_member(BOTTOM, {"Pu_kN": -200.0, "Mu_kNm": 100.0}))[STRENGTH]
    assert dict(tension.values)["Mn"] < dict(no_axial.values)["Mn"]


def test_tension_beyond_the_steel_capacity_fails() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": -700.0, "Mu_kNm": 10.0}))
    assert checks[STRENGTH].status is Status.FAIL
    assert "tracción axial" in checks[STRENGTH].note


def test_missing_axial_load_is_incomplete() -> None:
    assert _checks(_member(BOTTOM, {"Mu_kNm": 100.0}))[STRENGTH].status is Status.INCOMPLETE


def test_other_member_types_are_blocked() -> None:
    checks = _checks(_member(BOTTOM, {"Pu_kN": 0.0, "Mu_kNm": 100.0}, type="column"))
    assert checks[SCOPE].status is Status.BLOCKED


def test_net_tensile_strain_limit_differs_between_profiles() -> None:
    # εt queda entre 0.004 (NSR-10 C.10.3.5) y εty + 0.003 (ACI 9.3.3.1).
    layers = [{"designation": "#8", "count": 5, "depth": 440.0, "role": "flexure"}]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 250.0})
    nsr, aci = _checks(member, "nsr-10")[NET_TENSILE_STRAIN], _checks(member, "aci-318-25")[NET_TENSILE_STRAIN]
    assert 0.004 < nsr.capacity < 0.0051  # type: ignore[operator]
    assert nsr.status is Status.PASS
    assert aci.status is Status.FAIL


def test_below_minimum_reinforcement_is_blocked_until_the_exception_exists() -> None:
    layers = [{"designation": "#4", "count": 2, "depth": 440.0, "role": "flexure"}]
    check = _checks(_member(layers, {"Pu_kN": 0.0, "Mu_kNm": 20.0}))[MIN_REINFORCEMENT]
    assert check.status is Status.BLOCKED
    assert "C.10.5.3" in check.errors[0].message


T_SECTION = {"bw": 300.0, "h": 500.0, "cover": 40.0, "bf": 1000.0, "hf": 100.0, "flange_sides": 2}
TOP = [{"designation": "#6", "count": 4, "depth": 60.0, "role": "flexure"}]


def test_flange_in_tension_needs_the_determinacy_declared() -> None:
    member = _member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0}, section=T_SECTION)
    assert _checks(member)[MIN_REINFORCEMENT].status is Status.INCOMPLETE


def test_determinate_beam_uses_the_reduced_flange_width() -> None:
    continuous = _checks(_member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0}, section=T_SECTION, statically_determinate=False))
    determinate = _checks(_member(TOP, {"Pu_kN": 0.0, "Mu_kNm": -100.0}, section=T_SECTION, statically_determinate=True))
    assert determinate[MIN_REINFORCEMENT].demand == pytest.approx(2 * continuous[MIN_REINFORCEMENT].demand)  # type: ignore[operator]


def test_aci_caps_fy_at_550_mpa_for_minimum_reinforcement() -> None:
    flexure = PROFILES["aci-318-25"].flexure
    assert flexure.min_flexural_reinforcement(28.0, 690.0, 300.0, 440.0) == flexure.min_flexural_reinforcement(28.0, 550.0, 300.0, 440.0)
    nsr = PROFILES["nsr-10"].flexure
    assert nsr.min_flexural_reinforcement(28.0, 690.0, 300.0, 440.0) < nsr.min_flexural_reinforcement(28.0, 550.0, 300.0, 440.0)


def test_minimum_reinforcement_counts_every_bar_in_tension() -> None:
    # El eje neutro queda por encima de las 2#5 superiores, que también trabajan a tracción (D-025).
    layers = [
        {"designation": "#5", "count": 2, "depth": 60.0, "role": "flexure"},
        {"designation": "#8", "count": 3, "depth": 440.0, "role": "flexure"},
    ]
    member = _member(layers, {"Pu_kN": 0.0, "Mu_kNm": 180.0}, section=T_SECTION, statically_determinate=False)
    check = _checks(member)[MIN_REINFORCEMENT]
    area = 2 * 199.0 + 3 * 510.0
    depth = (2 * 199.0 * 60.0 + 3 * 510.0 * 440.0) / area
    assert check.capacity == pytest.approx(area)
    assert check.demand == pytest.approx(1.4 * 300.0 * depth / 420.0)
